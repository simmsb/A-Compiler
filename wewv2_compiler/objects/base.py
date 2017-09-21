from abc import ABCMeta, abstractmethod
from functools import wraps
from typing import Dict, Iterable, List


class BaseObject(metaclass=ABCMeta):
    """Base class of compilables."""

    def __new__(cls, ast, *args, **kwargs):
        obj = super().__new__(cls, ast, *args, **kwargs)
        obj.__ast = ast
        return obj

    @abstractmethod
    def compile(self, ctx):
        return NotImplemented

    def raise_(self, reason, *args, **kwargs):
        info = self.__ast.parseinfo
        startl, endl = info.line, info.endline
        startp, endp = info.pos, info.endpos
        source = info.buffer.get_lines()

        # startp and endp are offsets from the start
        # calculate there positions on their source
        startp = startp - sum(map(len, source[:startl]))
        endp = endp - sum(map(len, source[:endl]))

        # strip newlines here (they are counted in startp and endp offsets)
        source = [i.rtrip('\n') for i in source]

        def fmtr():
            if startl == endl:
                # start and end on same line, only need simple fmt
                width = (endp - startp) - 2  # leave space for carats
                separator = '-' * width
                yield source[startl]
                yield f"{'^':startp}{separator}^"
            else:
                width = (len(source[startl]) - startp) - 2
                separator = '-' * width
                yield source[startl]
                yield f"{'^':startp}{separator}^"
                for i in source[startl + 1:endl - 1]:
                    yield i
                    yield '-' * len(i)
                width = (len(source[endl]) - endp) - 2
                separator = '-' * width
                yield source[startl]
                yield f"{separator}^"

        highlight = "\n".join(fmtr())

        error = ("Compilation error {}.\n"
                 "{}\n{}").format(
                     (f"on line {startl}" if
                      startl == endl else
                      f"on lines {startl} to {endl}"),
                     reason, highlight)

        return Exception(error, *args, **kwargs)


class Scope(BaseObject):
    """A object that contains variables that can be looked up."""

    @abstractmethod
    def lookup_variable(self, ident):
        return NotImplemented


def hook_emit(fn):
    """Inserts the object that yielded into the item that it yields."""
    @wraps(fn)
    def deco(self, *args, **kwargs):
        for i in fn(self, *args, **kwargs):
            i.object = self
            yield i
    return deco


class CompileContext:
    def __init__(self):
        self.scope_stack: List[Scope] = []
        self.globals: Dict[str, 'Variable'] = {}
        self.ir: 'IrInstruction' = []
        # TODO: make the IrInstruction class that holds an instruction

    @property
    def current_scope(self):
        return self.scope_stack[-1]

    def lookup_variable(self, ident, callee: BaseObject) -> 'Variable':
        """Lookup a identifier in parent scope stack."""
        for i in reversed(self.scope_stack):
            var = i.lookup_variable(self, ident)
            if var is not None:
                return var
        var = self.globals.get(ident)
        if var is not None:
            return var
        raise callee.raise_(f"Identifier {ident} was not found in any scope.")

    def emit(self, instruction: 'IrInstruction'):
        self.ir.append(instruction)

    def compile(self, objects: Iterable[BaseObject]):
        for i in objects:
            i.compile(self)
