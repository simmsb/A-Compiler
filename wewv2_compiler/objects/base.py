import inspect
from abc import abstractmethod
from contextlib import contextmanager
from functools import wraps
from operator import itemgetter
from typing import Dict, Iterable, List, Optional, Tuple, Union

from tatsu.ast import AST
from tatsu.infos import ParseInfo
from wewv2_compiler.objects import irObject, types
from wewv2_compiler.objects.irObject import (Epilog, IRObject, Pop, Push,
                                             Register, RegisterEnum)


class NotFinished(Exception):
    """Raised when a compilation is waiting on another object."""
    pass


# XXX: If we have many of these just use a tuple api instead
# (req.object_request, "name") or something nice like that
class ObjectRequest:
    """Request an object that might not be compiled yet."""

    def __init__(self, name: str):
        self.name = name


class ApplyMethodMeta(type):
    """Looks up _meta_fns in class and applies functions to asked methods."""

    def __new__(cls, name, bases, attrs):
        for k, v in attrs.get("_meta_fns", ()):
            attr = attrs.get(k)
            if attr is not None:
                attrs[k] = v(attr)
        return super().__new__(cls, name, bases, attrs)


def make_generator(f):
    @wraps(f)
    def internal(*args, **kwargs):
        return f(*args, **kwargs)
        yield
    return internal


def wrap_add_compile_context(f):
    @wraps(f)
    def internal(self, ctx: 'CompileContext'):
        with ctx.context(self):
            yield from f(self, ctx)
    return internal


class BaseObject(metaclass=ApplyMethodMeta):
    """Base class of compilables."""

    _meta_fns = (("compile", make_generator),
                 ("compile", wrap_add_compile_context))

    def __init__(self, ast: AST):
        self.__ast = ast
        self.__info: ParseInfo = ast.parseinfo

    @abstractmethod
    def compile(self, ctx: 'CompileContext'):
        """Compile an object. If an expression, always pushes the result to the stack."""
        raise NotImplementedError

    @property
    def type(self):
        return NotImplemented

    @property
    def size(self):
        return self.type.size

    @property
    def identifier(self) -> str:
        info = self.__info
        return f"{info.line:info.pos:info.endpos}"

    @property
    def highlight_lines(self) -> str:
        info = self.__info
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
                width = (endp - startp) - 2  # leave space for carats + off by one
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

    def make_error(self, reason: str) -> str:
        info = self.__info
        startl, endl = info.line, info.endline

        return ("Compilation error {}.\n"
                "{}\n{}").format((f"on line {startl}" if startl == endl else
                                  f"on lines {startl} to {endl}"), reason,
                                 self.highlight_lines)

    def error(self, reason, *args, **kwargs):
        return Exception(self.make_error(reason), *args, **kwargs)


class ExpressionObject(BaseObject):

    _meta_fns = (("compile", make_generator),
                 ("compile", wrap_add_compile_context),
                 ("compile_to", make_generator),
                 ("compile_to", wrap_add_compile_context),
                 ("load_lvalue_to", make_generator))

    def compile_to(self, ctx: 'CompileContext', to: Register):
        """Compiles to a location instead of pushing to the stack."""
        yield from self.compile(ctx)
        ctx.emit(Pop(to))
        # just hope the optimiser will eliminate this.

    def load_lvalue_to(self, ctx: 'CompileContext', to: Register):
        raise self.error(f"Object of type <{self.__class__.__name__}> Holds no LValue information.")


class Variable:
    """A reference to a variable, holds scope and location information."""

    def __init__(self, name: str, type: types.Type, parent: Optional[BaseObject]=None):
        self.type = type
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


class Scope(BaseObject):
    """A object that contains variables that can be looked up."""

    def __init__(self, ast):
        super().__init__(ast)
        self.vars: Dict[str, Variable] = {}
        self.size = 0
        self.body = ast.body

    def lookup_variable(self, name: str) -> Variable:
        return self.vars.get(name)

    def compile(self, ctx: 'CompileContext'):
        # we need to allocate stack space, scan instructions for variables.

        with ctx.scope(self):
            for i in self.body:
                yield from i.compile(ctx)
            ctx.emit(Epilog(self.size))

    def declare_variable(self, var: Variable):
        """Add a variable to this scope.

        raises if variable is redeclared to a different type than the already existing var.
        """
        ax = self.vars.get(var.name)
        if ax is not None:
            if ax.type != var.type:
                raise self.error(
                    f"Variable {var} of type {var.type} is already declared as type {ax.type}"
                )
            return  # variable already declared but is of the same type, ignore it

        self.vars[var.name] = var
        var.stack_offset = self.size
        self.size += var.size


class Compiler:

    def __init__(self):
        self.compiled_objects: Dict[str, BaseObject] = {}
        self.waiting_coros: Dict[str, BaseObject] = {}
        self.data: List[Union[str, bytes]] = []

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

    def run_over(self, obj: BaseObject, to_send: BaseObject=None):
        """Run over a compile coro. If we dont finish raise :class:`NotFinished`

        :param obj: The object to start compiling. May or may not have already been visited.
        :param to_send: Initial value to send to generator.
        """
        if hasattr(obj, "_context"):
            ctx = obj._context
        else:
            ctx = CompileContext(self)  # if we already have a context

        if hasattr(obj, "_coro"):
            coro = obj._coro
        else:
            coro = obj.compile(self, ctx)
            obj._coro = coro
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
        for k, i in self.waiting_coros.items():
            print(i.make_error(f"This object is waiting on name {k} which never compiled."))


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

        #: Our in-use registers
        self.regs_used = 0

    @property
    def current_object(self) -> BaseObject:
        return self.object_stack[-1]

    @property
    def current_scope(self) -> Scope:
        return self.scope_stack[-1]

    @contextmanager
    def scope(self, scope: Scope):
        """Enter a scope for name lookup."""
        self.scope_stack.append(scope)
        with self.context(scope):
            yield
        self.scope_stack.pop()

    @contextmanager
    def context(self, obj: BaseObject):
        """Enter a context for compilation, minimises state passing between compiling objects and the context."""
        self.object_stack.append(obj)
        yield
        self.object_stack.pop()

    @contextmanager
    def reg(self, size: Union[int, Tuple[int]], sign: Union[bool, Tuple[bool]]=False) -> Union[Register, Tuple[Register]]:
        """Get a register of required size

        :param size: Size of register(s) to get.
        :param sign: Sign of register(s) to get.
        """
        if isinstance(size, int):
            size = (size,)
        if isinstance(sign, bool):
            sign = (sign,)
        sign += (False,) * (len(size) - len(sign))
        regs = tuple(Register(self.regs_used + i, si, sg) for i, (si, sg) in enumerate(zip(size, sign)))
        self.regs_used += len(size)
        yield regs[0] if len(regs) == 1 else regs
        self.regs_used -= len(size)

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
