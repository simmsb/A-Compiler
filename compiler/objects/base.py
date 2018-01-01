# pylint: disable=inconsistent-return-statements

import inspect
from compiler.objects import types
from compiler.objects.ir_object import Epilog, IRObject, Prelude, Register, Return
from contextlib import contextmanager
from functools import wraps
from typing import Dict, List, Optional, Union, Generator
from itertools import chain

from tatsu.ast import AST
from tatsu.infos import ParseInfo


class NotFinished(Exception):
    """Raised when a compilation is waiting on another object."""
    pass


class CompileException(Exception):

    def __init__(self, reason: str, trace: str=None):
        super().__init__(reason, trace)
        self.reason = reason
        self.trace = trace

StmtCompileType = Generator['ObjectRequest', 'BaseObject', None] # pylint: disable=invalid-name
ExprCompileType = Generator['ObjectRequest', 'BaseObject', Register]  # pylint: disable=invalid-name

# If we have many of these just use a tuple api instead
# (req.object_request, "name") or something nice like that
#
class ObjectRequest:
    """Request an object that might not be compiled yet."""

    def __init__(self, name: str):
        self.name = name


class ApplyMethodMeta(type):
    """Looks up _meta_fns in class and applies functions to asked methods."""

    def __new__(mcs, name, bases, attrs):
        # grab our meta functions stuff
        if "_meta_fns" in attrs:
            metas = attrs["_meta_fns"]
        else:
            for klass in chain.from_iterable(m.mro() for m in bases):
                if hasattr(klass, "_meta_fns"):
                    metas = klass._meta_fns
                    break
            else:
                metas = ()
        for k, v in metas:
            attr = attrs.get(k)
            if attr is not None:
                attrs[k] = v(attr)
        return super().__new__(mcs, name, bases, attrs)


def make_generator(f):
    """Make a function or a property getter a generator function."""
    if isinstance(f, property):
        if inspect.isgeneratorfunction(f.fget):
            return f

        @wraps(f.fget)
        def internal_p(*args, **kwargs):
            return f.fget(*args, **kwargs)
            yield  # pylint: disable=unreachable

        return property(internal_p)

    if inspect.isgeneratorfunction(f):
        return f

    @wraps(f)
    def internal(*args, **kwargs):
        return f(*args, **kwargs)
        yield  # pylint: disable=unreachable
    return internal


def wrap_add_compile_context(f):
    @wraps(f)
    def internal(self, ctx: 'CompileContext'):
        with ctx.context(self):
            return (yield from f(self, ctx))

    return internal


class BaseObject(metaclass=ApplyMethodMeta):
    """Base class of compilables."""

    def __init__(self, ast: AST):
        self.context = None
        self._ast = ast
        self._info: ParseInfo = ast.parseinfo
        if ast.parseinfo is None:
            raise Exception("Parseinfo was none somehow")

    @property
    def identifier(self) -> str:
        info = self._info
        return f"{info.line:info.pos:info.endpos}"

    @property
    def highlight_lines(self) -> str:
        info = self._info
        startl, endl = info.line, info.endline
        startp, endp = info.pos, info.endpos

        source = info.buffer.get_lines()
        # startp and endp are offsets from the start
        # calculate their offsets from the line they are on.
        startp = startp - sum(map(len, source[:startl])) + 1
        endp = endp - sum(map(len, source[:endl]))

        # strip newlines here (they are counted in startp and endp offsets)
        source = [i.rstrip('\n') for i in source]

        def fmtr():
            if startl == endl:
                # start and end on same line, only need simple fmt
                width = (
                    endp - startp) - 2  # leave space for carats + off by one
                separator = '-' * width
                yield source[startl]
                yield f"{'^':>{startp}}{separator}^"
            else:
                width = (len(source[startl]) - startp)
                separator = '-' * width
                yield source[startl]
                yield f"{'^':>{startp}}{separator}"
                for i in source[startl + 1:endl]:
                    yield i
                    yield '-' * len(i)
                width = endp - 1  # - len(source[endl])
                separator = '-' * width
                yield source[endl]
                yield f"{separator}^"

        return "\n".join(fmtr())

    def make_error(self) -> str:
        info = self._info
        startl, endl = info.line, info.endline

        return "\n".join(((f"on line {startl}"
                           if startl == endl else
                           f"on lines {startl} to {endl}"),
                          self.highlight_lines))

    def error(self, reason):
        return CompileException(reason, self.make_error())


class StatementObject(BaseObject):
    """Derived base ast for statements."""

    def compile(self, ctx: 'CompileContext'):
        """Compile an object
        Statement objects do not return a register."""
        raise NotImplementedError

    _meta_fns = (("compile", make_generator),
                 ("compile", wrap_add_compile_context))


class ExpressionObject(BaseObject):
    """Derived base ast for expressions."""

    _meta_fns = (("compile", make_generator),
                 ("compile", wrap_add_compile_context),
                 ("type", make_generator),
                 ("size", make_generator),
                 ("pointer_to", make_generator),
                 ("load_lvalue", make_generator))

    @property
    def type(self):
        raise NotImplementedError

    @property
    def size(self):
        return (yield from self.type).size

    @property
    def pointer_to(self):
        return types.Pointer((yield from self.type))

    def compile(self, ctx: 'CompileContext') -> ExprCompileType:
        """Compiles an expression returning the register the result was placed in."""
        raise NotImplementedError

    def load_lvalue(self, ctx: 'CompileContext') -> ExprCompileType:  # pylint: disable=unused-argument
        """Load the lvalue of an expression, returning the register the value was placed in."""
        raise self.error(
            f"Object of type <{self.__class__.__name__}> Holds no LValue information."
        )


class Variable:
    """A reference to a variable, holds scope and location information."""

    def __init__(self,
                 name: str,
                 type_: types.Type,
                 parent: Optional[BaseObject] = None):
        self.type = type_
        self.name = name
        self.parent = parent

        self.stack_offset = None
        self.global_offset = None
        # can either be global or offset to the base pointer.
        # maybe move these calculations somewhere else to be more abstract?

    @property
    def size(self):
        return self.type.size

    @property
    def identifier(self):
        return self.name


class Scope(StatementObject):
    """A object that contains variables that can be looked up."""

    def __init__(self, ast):
        super().__init__(ast)
        self.vars: Dict[str, Variable] = {}
        self.size = 0
        self.body = [i[0] for i in ast.body]

    def lookup_variable(self, name: str) -> Variable:
        return self.vars.get(name)

    def compile(self, ctx: 'CompileContext') -> StmtCompileType:
        with ctx.scope(self):
            ctx.emit(Prelude(self))
            for i in self.body:
                yield from i.compile(ctx)
            ctx.emit(self.make_epilog())

    def make_epilog(self) -> IRObject:
        return Epilog(self)

    def declare_variable(self, name: str, typ: types.Type):
        """Add a variable to this scope.

        raises if variable is redeclared to a different type than the already existing var.
        """
        ax = self.vars.get(name)
        if ax is not None:
            if ax.type != typ:
                raise self.error(
                    f"Variable {name} of type {typ} is already declared as type {ax.type}"
                )
            return ax  # variable already declared but is of the same type, ignore it

        var = Variable(name, typ, self)
        self.vars[name] = var
        var.stack_offset = self.size
        self.size += var.size
        return var


class FunctionDecl(Scope):
    """Function definition object.

    Function definitions should expand to a declaration with
    assignment to a const global variable with the name of the function.

    Stack shape:

    | p1 | p2 | p3 | p4 | return_addr | stored_base_pointer | v1 | v2 | v3 |

    """

    def __init__(self, ast: AST):
        super().__init__(ast)
        self.name = ast.name
        self.params = [Variable(i[0], i[2]) for i in ast.params]
        for var, offset in zip(self.params, range(len(self.params), 0, -1)):
            var.stack_offset = -offset
        self._type = types.Function(ast.r, [i[2] for i in ast.params], True)
        # should functions be naturally const?

    @property
    def type(self) -> types.Type:
        return self._type

    @property
    def identifier(self) -> str:
        return self.name

    def lookup_variable(self, name: str) -> Optional[Variable]:
        v = super().lookup_variable(name)
        if v is None:
            return self.params.get(name)
        return None  # shut up pylint

    def compile(self, ctx: 'CompileContext') -> StmtCompileType:
        yield from super().compile(ctx)
        ctx.emit(Return())


class Compiler:
    def __init__(self):
        self.compiled_objects: Dict[str, BaseObject] = {}
        self.waiting_coros: Dict[str, BaseObject] = {}
        self.data: List[Union[str, bytes]] = []

    def declare_variable(self, name: str, typ: types.Type):
        """Add a variable to global scope.

        raises if variable is redeclared to a different type than the already existing var.
        """
        ax = self.compiled_objects.get(name)
        if ax is not None:
            if ax.type != type:
                raise CompileException(
                    f"Variable {name} of type {type} is already declared as type {ax.type}"
                )
            return ax  # variable already declared but is of the same type, ignore it

        var = Variable(name, type, self)
        self.compiled_objects[name] = var
        var.global_offset = len(self.data)
        self.data.append(bytes((0, ) * typ.size))
        return var

    def add_string(self, string: str) -> Variable:
        """Add a string to the object table.

        If string to insert already exists returns reference to exising.

        :param string: The string to insert.
        :returns: The variable reference created."""
        key = f"string-lit-{string}"
        val = Variable(key, types.string_lit)
        if string not in self.data:
            val.global_offset = len(self.data)
            self.data.append(string)
        else:
            val.global_offset = self.data.index(string)
        return val

    def add_bytes(self, data: bytes) -> Variable:
        """Add bytes to the object table.

        Unlike :func:`add_string` always creates a new object.

        :param data: The bytes to insert.
        :returns: The variable reference created."""
        index = len(self.data)
        key = f"raw-data-{index}"
        val = Variable(key, types.string_lit)
        val.global_offset = index
        self.data.append(data)
        return val

    def add_array(self, vars: List[Variable]) -> Variable:
        """Add a list of vars to the object table.

        Unlike :func:`add_string` always creates a new object.

        :param vars: The variables to insert.
        :returns: The variable reference created."""
        assert vars
        index = len(self.data)
        key = f"var-array-{index}"
        val = Variable(key, types.Pointer(vars[0].type))
        val.global_offset = index
        self.data.append(vars)
        return val

    def add_waiting(self, name: str, obj: BaseObject):
        """Add a coro to the waiting list.

        :param name: The name to wait on.
        :param obj: The object that should sleep."""
        l = self.waiting_coros.setdefault(name, [])
        l.append(obj)

    def run_over(self, obj: BaseObject, to_send: BaseObject = None):
        """Run over a compile coro. If we dont finish raise :class:`NotFinished`

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
                to_send = None
            except StopIteration:
                return

            assert isinstance(r, ObjectRequest)

            # look for either a global object or a scope variable.
            var = ctx.lookup_variable(r.name)
            if var:
                coro.send(var)
                continue

            var = self.compiled_objects.get(r.name)
            if var:
                coro.send(var)
                continue

            # if nothing was found place coro on waiting list and start compiling something else.

            self.add_waiting(r.name, obj)
            raise NotFinished

    def compile(self, objects: List[BaseObject]):
        """Compile a list of objects."""
        objects = [(o, None) for o in objects]
        for i, t in objects:
            try:
                self.run_over(i, t)
            except NotFinished:
                pass
            else:
                to_wake = self.waiting_coros.pop(i.identifier, ())
                objects.extend((o, i) for o in to_wake)
                self.compiled_objects[i.identifier] = i
        if self.waiting_coros:
            for k, i in self.waiting_coros.items():
                print(i.make_error(),
                      f"This object is waiting on name {k} which never compiled.")
            raise CompileException(
                "code remaining that was waiting on something that never appeared.")


class CompileContext:
    """A compilation context. Once context exists for every file level code object."""

    def __init__(self, compiler: Compiler):

        #: Stack of scopes for lookup
        self.scope_stack: List[Scope] = []

        #: Stack of compilation objects
        self.object_stack: List[BaseObject] = []

        self.compiler = compiler

        #: Output IR
        self.code: List[IRObject] = []

        #: Count of registers used
        self.regs_used = 0

    @property
    def current_object(self) -> Optional[BaseObject]:
        """Get the current object being compiled."""
        if self.object_stack:
            return self.object_stack[-1]

    @property
    def top_function(self) -> Optional[FunctionDecl]:
        """Get the top level object being compiled.
        :returns: None if not compiling a function. The function node otherwise.
        """
        if self.object_stack and isinstance(self.object_stack[0], FunctionDecl):
            return self.object_stack[0]

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
        except CompileException as e:
            if e.trace is None and self.current_object:  # add in the trace
                raise self.current_object.error(e.reason) from None
            raise e from None
        self.object_stack.pop()

    def get_register(self, size: int, sign: bool = False):
        """Get a unique register."""
        reg = Register(self.regs_used, size, sign)
        self.regs_used += 1
        return reg

    def declare_variable(self, name: str, typ: types.Type) -> Variable:
        if isinstance(self.current_scope, Scope):
            return self.current_scope.declare_variable(name, typ)
        return self.compiler.declare_variable(name, typ)

    def lookup_variable(self, name: str) -> Variable:
        """Lookup a identifier in parent scope stack."""
        for i in reversed(self.scope_stack):
            var = i.lookup_variable(self, name)
            if var is not None:
                return var
        return None

    def emit(self, instr: IRObject):
        """Emit an IR instruction."""
        instr.parent = self.current_object
        self.code.append(instr)
        return instr
