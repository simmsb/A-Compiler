from typing import Optional

from compiler.utils.formatter import format_lines
from compiler.objects.errors import CompileException, InternalCompileException

from tatsu.ast import AST
from tatsu.infos import ParseInfo


class BaseObject:
    """Base class of compilables."""

    def __init__(self, ast: Optional[AST]=None):
        self.context: 'CompileContext' = None
        self._ast = ast
        if ast is not None:
            assert isinstance(ast, AST)
            self._info: ParseInfo = ast.parseinfo
        else:
            self._info = None

    @property
    def identifier(self) -> str:
        info = self._info
        return f"{info.line}:{info.pos}:{info.endpos}"

    @property
    def code(self):
        if not hasattr(self, 'context'):
            raise InternalCompileException("AST node does not have context attached.")
        return self.context.code

    @property
    def highlight_lines(self) -> str:
        """Generate the error info line for this ast node."""
        info = self._info
        startl, endl = info.line, info.endline
        startp, endp = info.pos, info.endpos

        source = info.buffer.get_lines()
        # startp and endp are offsets from the start
        # calculate their offsets from the line they are on.
        startp = startp - sum(map(len, source[:startl])) + 1
        endp -= sum(map(len, source[:endl]))

        # strip newlines here (they are counted in startp and endp offsets)
        source = [i.rstrip('\n') for i in source]

        def fmtr():
            if startl == endl:
                # start and end on same line, only need simple fmt
                yield source[startl]
                if startp == endp:  # only emit single carat when the error is a single character
                    yield f"'^':>{startp}"
                else:
                    width = (endp - startp) - 1  # leave space for carats + off by one
                    separator = '-' * width
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
                if endl < len(source):  # sometimes this is one more than the total number of lines
                    yield source[endl]
                yield f"{separator}^"

        return "\n".join(fmtr())

    def make_error(self) -> Optional[str]:
        """Make an error for the ast node this object belongs to.

        if no ast node exists returns None
        """
        info = self._info
        if info is None:
            return None
        startl, endl = info.line, info.endline

        return "\n".join(((f"on line {startl}"
                           if startl == endl else
                           f"on lines {startl} to {endl}"),
                          self.highlight_lines))

    def error(self, *reasons: str):
        return CompileException(*reasons, trace=self.make_error())

    def pretty_print(self):
        instrs = map(str, self.code)
        return format_lines("\n".join(instrs))
