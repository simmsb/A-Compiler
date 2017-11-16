from abc import abstractmethod
from contextlib import contextmanager
from typing import Dict, Iterable, List, Optional

from tatsu.ast import AST
from tatsu.infos import ParseInfo

from wewv2_compiler.objects import irObject, types
from wewv2_compiler.objects.irObject import IRObject


class NotFinished(Exception):
    """Raised when a compilation is waiting on another object."""
    pass


# XXX: If we have many of these just use a tuple api instead
# (req.object_request, "name") or something nice like that
class ObjectRequest:
    """Request an object that might not be compiled yet."""

    def __init__(self, name: str):
        self.name = name


class BaseObject:
    """Base class of compilables."""

    def __init__(self, ast: AST):
        self.__ast = ast
        self.__info: ParseInfo = ast.parseinfo

    @abstractmethod
    def compile(self, ctx: 'CompileContext'):
        return NotImplemented

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
        # TODO: make this neater
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
        with ctx.scope(self):
            for i in self.body:
                yield from i.compile(ctx)

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

    def add_waiting(self, name: str, obj: BaseObject):
        """Add a coro to the waiting list.

        :param name: The name to wait on.
        :param obj: The object that should sleep."""
        l = self.waiting_coros.setdefault(name, [])
        l.append(obj)

    def run_over(self, obj: BaseObject):
        """Run over a compile coro. If we dont finish raise :class:`NotFinished`

        :param obj: The object to start compiling. May or may not have already been visited."""
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
                r = coro.send(None)
            except StopIteration:
                return

            assert isinstance(r, ObjectRequest)

            # look for either a global object or a scope variable.

            var = self.compiled_objects.get(r.name)
            if var:
                coro.send(var)
                continue

            var = ctx.lookup_variable(r.name)
            if var:
                coro.send(var)
                continue

            # if nothing was found place coro on waiting list and start compiling something else.

            self.add_waiting(r.name, obj)
            raise NotFinished

    def compile(self, objects: List[BaseObject]):
        for i in objects:
            try:
                self.run_over(i)
            except NotFinished:
                pass
            else:
                remaining = self.waiting_coros.pop(i.identifier, ())
                for o in remaining:
                    o._coro.send(i)  # send our finished object
                    objects.append(o)  # put object back on process queue
        for k, i in self.waiting_coros.items():
            print(i.make_error(f"This object is waiting on name {k} which never compiled."))


class CompileContext:
    """A compilation context. Once context exists for every file level code object."""

    def __init__(self, compiler: Compiler):
        self.scope_stack: List[Scope] = []
        self.object_stack: List[BaseObject] = []
        self.compiler = compiler
        self.code: List[IRObject] = []

    @property
    def current_object(self) -> BaseObject:
        return self.object_stack[-1]

    @property
    def current_scope(self) -> Scope:
        return self.scope_stack[-1]

    @contextmanager
    def scope(self, scope: Scope):
        self.scope_stack.append(scope)
        with self.context(scope):
            yield
        self.scope_stack.pop()

    @contextmanager
    def context(self, obj: BaseObject):
        self.object_stack.append(obj)
        yield
        self.object_stack.pop()

    def lookup_variable(self, name: str) -> Variable:
        """Lookup a identifier in parent scope stack."""
        for i in reversed(self.scope_stack):
            var = i.lookup_variable(self, name)
            if var is not None:
                return var
        return None

    def emit(self, instr: IRObject):
        instr.parent = self.current_object
        self.code.append(instr)
