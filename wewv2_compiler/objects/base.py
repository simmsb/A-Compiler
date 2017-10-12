from abc import ABCMeta, abstractmethod
from functools import wraps
from typing import Iterable, List

from wewv2_compiler.objects.irObject import IRObject


def hook_emit(fn):  # this is bad, delet
    """Inserts the object that yielded into the item that it yields."""

    @wraps(fn)
    def deco(self, *args, **kwargs):
        for i in fn(self, *args, **kwargs):
            i.object = self
            yield i

    return deco


class BaseObject:
    """Base class of compilables."""

    def __new__(cls, ast, *args, **kwargs):
        obj = super().__new__(cls, *args, **kwargs)
        obj.__ast = ast
        return obj

    @abstractmethod
    def compile(self, ctx: 'CompileContext'):
        return NotImplemented

    @property
    def highlight_lines(self):
        info = self.__ast.parseinfo
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

    def error(self, reason, *args, **kwargs):

        error = ("Compilation error {}.\n"
                 "{}\n{}").format((f"on line {startl}" if startl == endl else
                                   f"on lines {startl} to {endl}"), reason,
                                  highlight)

        return Exception(error, *args, **kwargs)


class Variable:
    def __init__(self, name, type, size=1):
        self.name = name
        self.type = type
        self.size = size
        self.stack_offset = 0


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
                raise self.raise_(
                    f"Variable {var} of type {var.type} is already declared as type {ax.type}"
                )
            return  # variable already declared but is of the same type, ignore it

        self.vars[var.name] = var
        var.stack_offset = self.size
        self.size += var.size


class CompileContext:
    def __init__(self):
        self.scope_stack: List[Scope] = []
        self.ir: IRObject = []
        # TODO: make the IrInstruction class that holds an instruction

    @property
    def current_scope(self):
        return self.scope_stack[-1]

    def lookup_variable(self, ident, callee: BaseObject) -> Variable:
        """Lookup a identifier in parent scope stack."""
        for i in reversed(self.scope_stack):
            var = i.lookup_variable(self, ident)
            if var is not None:
                return var
        raise callee.raise_(f"Identifier {ident} was not found in any scope.")

    def emit(self, instruction: IRObject):
        self.ir.append(instruction)

    def compile(self, objects: Iterable[BaseObject]):
        for i in objects:
            i.compile(self)
