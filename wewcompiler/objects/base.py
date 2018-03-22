"""Core compilation objects."""

from abc import ABC, abstractmethod
from contextlib import contextmanager
from functools import wraps
from itertools import accumulate
from typing import Any, Dict, List, Optional, Tuple, Union

from tatsu.ast import AST

from wewcompiler.objects import types
from wewcompiler.objects.astnode import BaseObject
from wewcompiler.objects.errors import CompileException, InternalCompileException
from wewcompiler.objects.ir_object import Epilog, IRObject, Prelude, Register, Return, Immediate
from wewcompiler.objects.variable import Variable, DataReference


# If we have many of these just use a tuple api instead
# (req.object_request, "name") or something nice like that
#
class ObjectRequest:
    """Request an object that might not be compiled yet."""

    __slots__ = ("name",)

    def __init__(self, name: str):
        self.name = name


def with_ctx(f):
    """Wraps a function to enter the :class:`CompileContext.context` context manager when called"""
    @wraps(f)
    async def internal(self, ctx: 'CompileContext', *args, **kwargs):
        with ctx.context(self):
            return await f(self, ctx, *args, **kwargs)
    return internal


class StatementObject(BaseObject):
    """Derived base ast for statements."""

    @with_ctx
    async def compile(self, ctx: 'CompileContext'):
        """Compile an object
        Statement objects do not return a register."""
        raise NotImplementedError


class ExpressionObject(BaseObject):
    """Derived base ast for expressions."""

    @property
    async def type(self) -> types.Type:
        raise NotImplementedError

    @property
    async def size(self) -> int:
        return (await self.type).size

    @property
    def pointer_to(self):
        return types.Pointer((yield from self.type))

    @with_ctx
    async def compile(self, ctx: 'CompileContext') -> Register:
        """Compiles an expression returning the register the result was placed in."""
        raise NotImplementedError

    async def load_lvalue(self, ctx: 'CompileContext') -> Register:  # pylint: disable=unused-argument
        """Load the lvalue of an expression, returning the register the value was placed in."""
        raise self.error(
            f"Object of type <{self.__class__.__name__}> Holds no LValue information.")


class IdentifierScope(ABC):

    @property
    @abstractmethod
    def vars(self) -> Dict[str, Variable]:
        pass

    def lookup_variable(self, name: str) -> Variable:
        return self.vars.get(name)

    def make_variable(self, name: str, typ: types.Type, obj: Optional[BaseObject] = None) -> Variable:
        """Create variable pointing to another object."""
        existing = self.lookup_variable(name)
        if existing is not None:
            if existing.type != typ:
                raise CompileException(
                    f"Variable {name} of type '{typ}' is already declared as type '{existing.type}'",
                )
            return existing  # variable already declared but is of the same type, ignore it

        var = Variable(name, typ, obj)
        self.vars[name] = var

        return var

    @abstractmethod
    def declare_variable(self, name: str, typ: types.Type) -> Variable:
        """Add a variable to this scope.

        raises if variable is redeclared to a different type than the already existing var.
        """
        return NotImplemented


class ModDecl(StatementObject):
    """Module declaration."""

    def __init__(self, name: str, body: List[StatementObject], ast: Optional[AST]=None):
        super().__init__(ast)
        self.name = name
        self.body = body

    @with_ctx
    async def compile(self, ctx: 'CompileContext'):

        # add in our namespace
        name = f"{self.namespace}{self.name}"

        for i in self.body:
            i.namespace = f"{name}.{i.namespace}"
            ctx.compiler.add_object(i)


def fully_qualified_name(obj: BaseObject, name: str) -> str:
    if name.startswith('..'):
        return name[2:]
    return f"{obj.namespace}{name}"


class Scope(StatementObject, IdentifierScope):
    """A object that contains variables that can be looked up."""

    def __init__(self, body: List[StatementObject], ast: Optional[AST]=None):
        super().__init__(ast)
        self._vars: Dict[str, Variable] = {}
        self.size = 0
        self.body = body
        self.used_hw_regs = []

    @property
    def vars(self) -> Dict[str, Variable]:
        return self._vars

    @with_ctx
    async def compile(self, ctx: 'CompileContext'):
        with ctx.scope(self):
            ctx.emit(Prelude(self))
            for i in self.body:
                await i.compile(ctx)
            ctx.emit(Epilog(self))

    def declare_variable(self, name: str, typ: types.Type) -> Variable:
        var = self.make_variable(name, typ)
        self.vars[name] = var
        var.stack_offset = self.size
        self.size += var.size
        return var

    def add_spill_vars(self, n: int):
        """Insert variables to spill registers into."""
        for i in range(n):
            self.declare_variable(
                f"spill-var-{i}",
                types.Int.fromsize(8)
            )


class FunctionDecl(Scope):
    """Function definition object.

    Function definitions should expand to a declaration with
    assignment to a const global variable with the name of the function.

    Stack shape: (not that it matters in this stage of the compiler)

    | p1 | p2 | p3 | p4 | return_addr | stored_base_pointer | v1 | v2 | v3 |
                                                              ^
    """

    def __init__(self, name: str, params: List[Tuple[str, types.Type]],
                 body: List[StatementObject], ast: Optional[AST]=None):
        super().__init__(body, ast)
        self.name = name
        self.params = {name: Variable(name, type) for (name, type) in params}

        # for my vm:
        # base pointer will be pointing to the first item on the stack
        # | p1 | p2 | ret | base | l1 | l2
        # first offset is -2 * the size of a pointer, etc, etc

        # reverse params to count offset from right to left
        params = list(reversed(list(self.params.values())))

        offsets = accumulate(i.size for i in params)

        initial_offset = -types.Pointer.size * 2

        for var, offset in zip(params, offsets):
            var.stack_offset = initial_offset - offset
        self._type = types.Function(ast.r or types.Void(), [i[2] for i in ast.params], const=True)

    @property
    def type(self) -> types.Type:
        return self._type

    @property
    def identifier(self) -> str:
        return f"{self.namespace}{self.name}"

    def lookup_variable(self, name: str) -> Optional[Variable]:
        var = super().lookup_variable(name)
        if var is None:
            return self.params.get(name)
        return var

    @with_ctx
    async def compile(self, ctx: 'CompileContext'):
        with ctx.scope(self):
            var = ctx.make_variable(self.name, self.type, self, global_only=True)
            var.global_offset = DataReference(self.identifier)  # set to our name
            var.lvalue_is_rvalue = True

            ctx.emit(Prelude(self))
            for i in self.body:
                await i.compile(ctx)

            # functions dont have an epilog unless from void function implicit returns

            if isinstance(self.type.returns, types.Void):
                ctx.emit(Return(self, Immediate(0, 1)))

            # TODO: support return statements with no expression


class Compiler(IdentifierScope):
    def __init__(self, debug: bool=False):
        self.debug = debug
        self._vars: Dict[str, Variable] = {}
        self.compiled_objects: List[StatementObject] = []
        self.waiting_coros: Dict[str, List[Tuple[BaseObject, BaseObject]]] = {}
        self.data: List[Union[bytes, List[Variable]]] = []
        self.identifiers: Dict[str, int] = {}
        self.spill_size = 0

        self._objects: List[Tuple[StatementObject, Any]] = []

        #: counter for generating unique identifiers
        self.unique_counter = 0

    @property
    def vars(self) -> Dict[str, Variable]:
        return self._vars

    @property
    def allocated_data(self) -> int:
        """Get size of allocated data in bytes."""
        total = 0
        for i in self.data:
            if isinstance(i, bytes):
                total += len(i)
            elif isinstance(i, Variable):
                total += i.size
        return total

    def lookup_variable(self, name: str) -> Variable:
        return self.vars.get(name)

    def add_spill_vars(self, n: int):
        self.spill_size = 8 * n
        for i in range(n):
            self.declare_variable(
                f"global-spill-{i}",
                types.Int.fromsize(8)  # always make an 8 byte spill
            )  # MAYBE: give sizes to spill vars

    def declare_variable(self, name: str, typ: types.Type) -> Variable:
        """Add a variable to global scope.
        creates space for variable
        raises if variable is redeclared to a different type than the already existing var.
        """
        var = self.make_variable(name, typ)
        self.vars[vars] = var
        var.global_offset = DataReference(name)
        self.identifiers[name] = len(self.data)
        self.data.append(bytes((0,) * typ.size))
        return var

    def add_string(self, string: str) -> Variable:
        """Add a string to the object table.

        If string to insert already exists returns reference to exising.

        :param string: The string to insert.
        :returns: The variable reference created.
        """
        key = f"string-lit-{string}"
        val = Variable(key, types.string_lit)
        string = string.encode("utf-8")
        val.global_offset = DataReference(key)
        if key not in self.identifiers:
            self.identifiers[key] = len(self.data)
            self.data.append(string)
        return val

    def add_bytes(self, data: bytes) -> Variable:
        """Add bytes to the object table.

        :param data: The bytes to insert.
        :returns: The variable reference created.
        """
        index = len(self.data)
        key = f"raw-data-{index}"
        val = Variable(key, types.string_lit)
        val.global_offset = DataReference(key)
        self.identifiers[key] = index
        self.data.append(data)
        return val

    def add_array(self, elems: List[Union[Variable, bytes]]) -> Variable:
        """Add an array of vars or bytes to the object table.

        :param elems: The variables to insert.
        :returns: The variable reference created.
        """
        assert elems  # we shouldn't be adding empty arrays
        index = len(self.data)
        key = f"var-array-{index}"
        val = Variable(key, types.Pointer(elems[0].type))
        val.global_offset = DataReference(key)
        self.identifiers[key] = index
        self.data.append(elems)
        return val

    def add_waiting(self, name: str, obj: BaseObject, from_: Optional[BaseObject]=None):
        """Add a coro to the waiting list.

        :param name: The name to wait on.
        :param obj: The object that should sleep.
        :param from_: The object that made the request.
        """
        coros = self.waiting_coros.setdefault(name, [])
        coros.append((obj, from_))

    def add_object(self, obj: BaseObject):
        """Add an object to be compiled by the current compilation.

        :param obj: The object to add to the compile queue.

        If the compilation has finished this will have no effect.
        """
        self._objects.append((obj, None))

    def run_over(self, obj: StatementObject, to_send: Variable = None) -> bool:
        """Run over a compile coro. Returns true if finished, false if not.

        :param obj: The object to start compiling. May or may not have already been visited.
        :param to_send: Initial value to send to generator.
        """
        if obj.context is None:
            ctx = CompileContext(self)
            obj.context = ctx
        else:
            ctx = obj.context

        if hasattr(obj, "_coro"):
            coro = obj._coro  # pylint: disable=protected-access
        else:
            coro = obj.compile(ctx)
            obj._coro = coro  # pylint: disable=protected-access

        while True:
            try:
                r = coro.send(to_send)
            except StopIteration:
                return True

            assert isinstance(r, ObjectRequest)
            # look for either a global object or a scope variable.
            var = ctx.lookup_variable(r.name)
            if var is not None:
                to_send = var
                continue

            # when looking in globals add to the namespace
            name = fully_qualified_name(obj, r.name)

            var = self.lookup_variable(name)
            if var is not None:
                to_send = var
                continue

            # if nothing was found place coro on waiting list and start compiling something else.

            self.add_waiting(name, obj, ctx.current_object)
            return False

    def compile(self, objects: Optional[List[StatementObject]]=None):
        """Compile a list of objects or restart compilation of any lasting objects."""
        if objects:
            self._objects.extend((o, None) for o in objects)
        while self._objects:
            obj, to_send = self._objects.pop()
            if self.run_over(obj, to_send):
                # after completing a compilation, run over the waiting list,
                # adding any objects that are satisfied back on to the compilation list
                for name in tuple(self.waiting_coros.keys()):
                    var = self.lookup_variable(name)
                    if var is None:
                        continue
                    to_wake = self.waiting_coros.pop(name)
                    self._objects.extend((o, var) for (o, _) in to_wake)
                self.compiled_objects.append(obj)
        if self.waiting_coros:
            errs = []
            for name, sleeping in self.waiting_coros.items():
                for (waiting_obj, err_obj) in sleeping:
                    err = (waiting_obj if err_obj is None else err_obj).make_error()
                    err = f"{err}\nThis object is waiting on an object of name: '{name}' which never compiled."
                    errs.append(err)
            raise CompileException(
                *errs,
                "code remaining that was waiting on something that never appeared.")


class CompileContext:
    """A compilation context. Once context exists for every file level code object."""

    def __init__(self, compiler: Compiler):

        #: Stack of scopes for lookup
        self.scope_stack: List[Scope] = []

        #: Stack of compilation objects
        self.object_stack: List[Union[BaseObject, FunctionDecl]] = []

        self.compiler = compiler

        #: Output IR
        self.code: List[IRObject] = []

        #: Count of registers used
        self.regs_used = 0

    @property
    def current_object(self) -> BaseObject:
        """Get the current object being compiled."""
        if self.object_stack:
            return self.object_stack[-1]
        raise InternalCompileException("Context's object stack is empty")

    @property
    def top_object(self) -> BaseObject:
        if self.object_stack:
            return self.object_stack[0]
        raise InternalCompileException("Context's object stack is empty")

    @property
    def top_function(self) -> Optional[FunctionDecl]:
        """Get the top level object being compiled.
        :returns: None if not compiling a function. The function node otherwise.
        """
        if self.object_stack and isinstance(self.object_stack[0], FunctionDecl):
            return self.object_stack[0]
        return None

    @property
    def current_scope(self) -> Optional[Scope]:
        """Get the current active scope."""
        return self.scope_stack[-1] if self.scope_stack else None

    @contextmanager
    def scope(self, scope: Scope):
        """Enter a scope for name lookup."""
        self.scope_stack.append(scope)
        with self.context(scope):
            yield
        self.scope_stack.pop()

    @contextmanager
    def context(self, obj: BaseObject):
        """Enter a context for compilation.
        This minimises state passing between compiling objects and the context."""
        self.object_stack.append(obj)
        try:
            yield
        except CompileException as exc:
            # if the exception doesn't contain a trace, try to add it for them.
            if exc.trace is None and self.current_object:
                exc.trace = self.current_object.make_error()
            if self.compiler.debug:  # if we're debugging or testing, give the stack trace by raising
                raise exc from None
            print(exc)
            exit(0)  # We dont want to display a stacktrace in situations like this
        self.object_stack.pop()

    def get_register(self, size: int, sign: bool = False):
        """Get a unique register."""
        reg = Register(self.regs_used, size, sign)
        self.regs_used += 1
        return reg

    def make_variable(self, name: str, typ: types.Type, obj: BaseObject, global_only: bool=False) -> Variable:
        if isinstance(self.current_scope, Scope) and not global_only:
            return self.current_scope.make_variable(name, typ, obj)

        name = f"{self.top_object.namespace}{name}"
        print(f"Making global with name: {name}")
        return self.compiler.make_variable(name, typ, obj)

    def declare_variable(self, name: str, typ: types.Type) -> Variable:
        if isinstance(self.current_scope, Scope):
            return self.current_scope.declare_variable(name, typ)

        name = f"{self.top_object.namespace}{name}"
        return self.compiler.declare_variable(name, typ)

    def declare_unique_variable(self, typ: types.Type) -> Variable:
        name = f"unique-var-{self.compiler.unique_counter}"
        self.compiler.unique_counter += 1
        return self.declare_variable(name, typ)

    def lookup_variable(self, name: str) -> Optional[Variable]:
        """Lookup a identifier in parent scope stack."""
        for i in reversed(self.scope_stack):
            var = i.lookup_variable(name)
            if var is not None:
                return var
        return None

    def emit(self, instr: IRObject):
        """Emit an IR instruction."""
        instr.parent = self.current_object
        self.code.append(instr)
        return instr