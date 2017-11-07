from abc import ABCMeta, abstractmethod
from functools import wraps
from typing import Iterable, List, Dict, Coroutine

from tatsu.ast import AST
from tatsu.infos import ParseInfo

from wewv2_compiler.objects.irObject import IRObject


class NotFinished(Exception):
    """Raised when a compilation is waiting on another object."""
    pass


class ObjectRequest:
    def __init__(self, name: str):
        self.name = name


class BaseObject:
    """Base class of compilables."""

    def __new__(cls, ast, *args, **kwargs):
        obj = super().__new__(cls, *args, **kwargs)
        obj.__ast: AST = ast
        obj.__info: ParseInfo = ast.parseinfo
        return obj

    @abstractmethod
    def compile(self, ctx: 'CompileContext'):
        return NotImplemented

    @property
    def identifier(self):
        info = self.__info
        return f"{info.line:info.pos:info.endpos}"

    @property
    def highlight_lines(self):
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

    def make_error(self, reason):

        return ("Compilation error {}.\n"
                "{}\n{}").format((f"on line {startl}" if startl == endl else
                                  f"on lines {startl} to {endl}"), reason,
                                 self.highlight_lines)

    def error(self, reason, *args, **kwargs):
        return Exception(self.make_error(reason), *args, **kwargs)


class Variable:

    def __init__(self, name, type, size=1):
        self.name = name
        self.type = type
        self.size = size
        self.stack_offset = 0

    @property
    def identifier(self):
        return self.name


class Scope(BaseObject):
    """A object that contains variables that can be looked up."""

    def __init__(self, ast):
        self.vars = {}
        self.size = 0
        self.body = ast.body

    def lookup_variable(self, ident):
        return self.vars.get(ident)

    @hook_emit
    def compile(self, ctx: 'CompileContext'):
        for i in self.body:
            yield from i.compile(ctx)
        # move up stack pointer to saved base pointer
        yield IRObject("sub", "stk", self.size)
        yield IRObject("mov", "stk", "acc")

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


class CompileContext:
    def __init__(self):
        self.scope_stack: List[Scope] = []
        self.compiled_objects: Dict[str, BaseObject] = {}
        self.waiting_coros: Dict[str, BaseObject] = {}

    @property
    def current_scope(self):
        return self.scope_stack[-1]

    def lookup_variable(self, ident, callee: BaseObject) -> Variable:
        """Lookup a identifier in parent scope stack."""
        for i in reversed(self.scope_stack):
            var = i.lookup_variable(self, ident)
            if var is not None:
                return var
        raise callee.error(f"Identifier {ident} was not found in any scope.")

    def add_waiting(self, name: str, obj: BaseObject):
        l = self.waiting_coros.setdefault(name, [])
        l.append(obj)

    def run_over(self, obj: BaseObject):
        if hasattr(obj, "_coro") and obj._coro is not None:
            coro = obj._coro
        else:
            coro = obj.compile(self)
            obj._coro = coro  # save the coroutine here
        for r in coro:
            assert isinstance(r, ObjectRequest)
            if r.name in self.compiled_objects:
                r.send(self.compiled_objects[r.name])
            else:
                self.add_waiting(r.name, obj)
                raise NotFinished

    def compile(self, objects: Iterable[BaseObject]):
        while objects:
            i = objects.pop()
            try:
                self.run_over(i)
            except NotFinished:
                pass
            else:
                self.compiled_objects[i.identifier] = i
                remaining = self.waiting_coros.pop(i.identifier, ())
                for o in remaining:
                    o._coro.send(i)  # send our finished object
                    objects.append(o)
        for k, i in self.waiting_coros.items():
            print(i.make_error(f"This object is waiting on name {k} which never compiled."))
