"""Core compilation objects."""

from contextlib import contextmanager
from functools import wraps
from itertools import accumulate
from typing import Any, Dict, List, Optional, Tuple, Union

from tatsu.ast import AST

from wewcompiler.objects import types
from wewcompiler.objects.astnode import BaseObject
from wewcompiler.objects.errors import CompileException, InternalCompileException
from wewcompiler.objects.ir_object import Epilog, IRObject, Prelude, Register, Return
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
        assert isinstance(ctx, CompileContext)
        with ctx.context(self):
            return await f(self, ctx, *args, **kwargs)
    return internal


class StatementObject(BaseObject):
    """Derived base ast for statements."""

    __slots__ = ("_coro", )

    @with_ctx
    async def compile(self, ctx: 'CompileContext'):
        """Compile an object
        Statement objects do not return a register."""
        raise NotImplementedError


class ExpressionObject(BaseObject):
    """Derived base ast for expressions."""

    __slots__ = ()

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
            f"Object {self.identifier} holds no LValue information.")


class IdentifierScope:

    __slots__ = ()

    @property
    def vars(self) -> Dict[str, Variable]:
        pass

    def lookup_variable(self, name: str) -> Optional[Variable]:
        return self.vars.get(name)

    def make_variable(self, name: str, typ: types.Type) -> Variable:
        """Manufacture a variable object, checking that the variable does not exist already."""
        existing = self.lookup_variable(name)
        if existing is not None:
            if existing.type != typ:
                raise CompileException(
                    f"Variable {name} of type '{typ}' is already declared as type '{existing.type}'",
                )
            return existing  # variable already declared but is of the same type, ignore it

        return Variable(name, typ)

    def declare_variable(self, name: str, typ: types.Type) -> Variable:
        """Add a variable to this scope, creating space for it.
        raises if variable is redeclared to a different type than the already existing var.
        """
        var = self.make_variable(name, typ)
        self.own_variable(var)
        self.init_variable(var)
        return var

    def init_variable(self, var: Variable):
        """Sets up a variable to exist in this scope but does not
        make the variable visible in this scope.
        """
        raise NotImplementedError

    def own_variable(self, var: Variable):
        """Sets up a variable to be visible in this scope."""
        raise NotImplementedError


class ModDecl(StatementObject):
    """Module declaration."""

    __slots__ = ("name", "body")

    def __init__(self, name: str, body: List[StatementObject], *, ast: Optional[AST] = None):
        super().__init__(ast=ast)
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

    __slots__ = ("_vars", "size", "body", "used_hw_regs")

    def __init__(self, body: List[StatementObject], *, ast: Optional[AST] = None):
        super().__init__(ast=ast)
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

    def init_variable(self, var: Variable):
        """Sets up a variable to exist in this scope but does not
        make the variable visible in this scope.
        """
        var.stack_offset = self.size
        self.size += var.size

    def own_variable(self, var: Variable):
        """Sets up a variable to be visible in this scope."""
        self.vars[var.name] = var

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

    | p4 | p3 | p2 | p1 | return_addr | stored_base_pointer | v1 | v2 | v3 |
                                                              ^
    """

    __slots__ = ("name", "params", "has_varargs", "_type")

    def __init__(self, name: str, params: List[Tuple[str, types.Type]], return_val: types.Type,
                 has_varargs: bool, body: List[StatementObject], *, ast: Optional[AST] = None):
        super().__init__(body, ast=ast)
        self.name = name

        self._type = types.Function(return_val or types.Void(), [t for _, t in params],
                                    has_varargs, const=True, ast=ast)

        self.params = {name: Variable(name, type) for name, type in params}

        self.has_varargs = has_varargs

        # for my vm:
        # base pointer will be pointing to the first item on the stack
        # | p2 | p1 | ret | base | l1 | l2
        # first offset is -2 * the size of a pointer, etc, etc

        params = list(self.params.values())

        offsets = accumulate(i.size for i in params)

        initial_offset = -types.Pointer.size * 2

        for var, offset in zip(params, offsets):
            var.stack_offset = initial_offset - offset

        # set the var_args 'param' to point to the location of the last parameter
        if params:
            last_offset = params[-1].stack_offset
        else:
            last_offset = initial_offset

        # insert the varargs pointer variable
        if has_varargs:
            self.params["var_args"] = Variable("var_args", types.Pointer(types.Void()),
                                               stack_offset=last_offset, lvalue_is_rvalue=True)

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
            var = ctx.make_variable(self.name, self.type, global_only=True)
            ctx.compiler.own_variable(var)
            var.global_offset = DataReference(self.identifier)  # set to our name
            var.lvalue_is_rvalue = True

            ctx.emit(Prelude(self))
            for i in self.body:
                await i.compile(ctx)

            # functions dont have an epilog unless from void function implicit returns

            if isinstance(self.type.returns, types.Void):
                ctx.emit(Return(self))


class Compiler(IdentifierScope):

    __slots__ = ("data", "_vars", "compiled_objects",
                 "waiting_coros", "data_identifiers",
                 "spill_size", "_objects", "unique_counter")

    def __init__(self):
        self._vars: Dict[str, Variable] = {}
        self.compiled_objects: List[StatementObject] = []
        self.waiting_coros: Dict[str, List[BaseObject]] = {}
        self.data: List[Union[bytes, List[Variable]]] = []
        self.data_identifiers: Dict[str, int] = {}
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
        def fn(i):
            if isinstance(i, bytes):
                return len(i)
            elif isinstance(i, Variable):
                return i.size
            raise InternalCompileException
        return sum(map(fn, self.data))

    def lookup_variable(self, name: str) -> Variable:
        return self.vars.get(name)

    def add_spill_vars(self, n: int):
        self.spill_size = 8 * n
        for i in range(n):
            self.declare_variable(
                f"global-spill-{i}",
                types.Int.fromsize(8)  # always make an 8 byte spill
            )  # MAYBE: give sizes to spill vars

    def init_variable(self, var: Variable):
        var.global_offset = DataReference(var.name)
        self.data_identifiers[var.name] = len(self.data)
        self.data.append(bytes((0,) * var.type.size))

    def own_variable(self, var: Variable):
        self.vars[var.name] = var

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
        if key not in self.data_identifiers:
            self.data_identifiers[key] = len(self.data)
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
        self.data_identifiers[key] = index
        self.data.append(data)
        return val

    def add_array(self, elems: List[Variable]) -> Variable:
        """Add an array of vars to the object table.

        :param elems: The variables to insert.
        :returns: The variable reference created.
        """
        assert elems  # we shouldn't be adding empty arrays
        index = len(self.data)
        key = f"var-array-{index}"
        val = Variable(key, types.Pointer(elems[0].type))
        val.global_offset = DataReference(key)
        self.data_identifiers[key] = index
        self.data.append(elems)
        return val

    def add_waiting(self, name: str, obj: BaseObject):
        """Add a coro to the waiting list.

        :param name: The name to wait on.
        :param obj: The object that should sleep.
        """
        coros = self.waiting_coros.setdefault(name, [])
        coros.append(obj)

    def add_object(self, obj: BaseObject):
        """Add an object to be compiled by the current compilation.

        :param obj: The object to add to the compile queue.

        If the compilation has finished this will have no effect.
        """
        self._objects.append((obj, None))

    def run_over(self, obj: StatementObject, to_send: Optional[Variable] = None) -> bool:
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
            self.add_waiting(name, obj)
            return False

    def compile(self, objects: Optional[List[StatementObject]] = None):
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
                    self._objects.extend((o, var) for o in to_wake)
                if not isinstance(obj, ModDecl):
                    self.compiled_objects.append(obj)

        # after compilation has finished, any waiting objects left means there were unresolved identifiers
        # abort and alert the user of the missing names
        if self.waiting_coros:
            errs = []
            for name, sleeping in self.waiting_coros.items():
                for waiting_obj in sleeping:
                    top_object = waiting_obj.context.top_object
                    err = top_object.make_error()
                    err = f"{err}\nThis object is waiting on an object of name: '{name}' which never compiled."
                    errs.append(err)
            raise CompileException(
                *errs,
                "code remaining that was waiting on something that never appeared.")


class CompileContext:
    """A compilation context. Once context exists for every file level code object."""

    __slots__ = ("scope_stack", "object_stack",
                 "compiler", "code", "regs_used")

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
    def top_function(self) -> FunctionDecl:
        """Get the top level object being compiled.
        :returns: The top function object.
        """
        if isinstance(self.top_object, FunctionDecl):
            return self.top_object
        raise InternalCompileException("Request for top_function when top object is not a function")

    @property
    def current_scope(self) -> Optional[Scope]:
        """Get the current active scope."""
        if self.scope_stack:
            return self.scope_stack[-1]
        return None

    @property
    def top_scope(self) -> Optional[Scope]:
        """Get the top scope."""
        if self.scope_stack:
            return self.scope_stack[0]
        return None

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
            raise exc from None
        self.object_stack.pop()

    def get_register(self, size: int, sign: bool = False) -> Register:
        """Get a unique register."""
        assert size in (1, 2, 4, 8)

        reg = Register(self.regs_used, size, sign)
        self.regs_used += 1
        return reg

    def make_variable(self, name: str, typ: types.Type, global_only: bool = False) -> Variable:
        if isinstance(self.current_scope, Scope) and not global_only:
            return self.current_scope.make_variable(name, typ)

        name = f"{self.top_object.namespace}{name}"
        return self.compiler.make_variable(name, typ)

    def declare_variable(self, name: str, typ: types.Type) -> Variable:
        if isinstance(self.current_scope, Scope):
            # this makes subscoped variables place the location of the variable
            # in the top scope, but the reference in themselves
            var = self.current_scope.make_variable(name, typ)
            self.top_scope.init_variable(var)
            self.current_scope.own_variable(var)
            return var

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
