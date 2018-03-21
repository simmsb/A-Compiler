from typing import Optional, Tuple

from wewcompiler.utils.formatter import format_lines
from wewcompiler.objects.errors import CompileException, InternalCompileException

from tatsu.ast import AST
from tatsu.infos import ParseInfo


class BaseObject:
    """Base class of compilables."""

    def __init__(self, ast: Optional[AST]=None):
        self.context: 'CompileContext' = None
        self.ast = ast
        if ast is not None:
            assert isinstance(ast, AST)
            self._info: ParseInfo = ast.parseinfo
        else:
            self._info = None

    @property
    def identifier(self) -> str:
        return self.matched_region

    @property
    def code(self):
        if not hasattr(self, 'context'):
            raise InternalCompileException("AST node does not have context attached.")
        return self.context.code

    @property
    def matched_region(self) -> str:
        startp, endp = self.get_text_positions()

        source = [i.rstrip("\n") for i in self._info.text_lines()]
        srclen = len(source)
        if srclen == 1:
            return source[0][startp:endp]

        return "\n".join(
            source[0][startp:],
            *source[1:-1],
            source[-1][:endp]
        )

    def get_text_positions(self) -> Tuple[int, int]:
        info = self._info
        startl, endl = info.line, info.endline
        startp, endp = info.pos, info.endpos

        source = info.buffer.get_lines()
        # startp and endp are offsets from the start
        # calculate their offsets from the line they are on.
        startp = startp - sum(map(len, source[:startl]))
        endp -= sum(map(len, source[:endl]))

        return startp, endp

    @property
    def highlight_lines(self) -> str:
        """Generate the error info line for this ast node."""
        startp, endp = self.get_text_positions()

        source = [i.rstrip("\n") for i in self._info.text_lines()]

        def fmtr():
            if len(source) == 1:
                # start and end on same line, only need simple fmt
                yield source[0]
                if startp == endp:  # only emit single carat when the error is a single character
                    yield f"'^':>{startp}"
                else:
                    width = (endp - startp) - 1  # leave space for carats + off by one
                    separator = '-' * width
                    yield f"{'^':>{startp}}{separator}^"
            else:
                width = (len(source[0]) - startp)
                separator = '-' * width
                yield source[0]
                yield f"{'^':>{startp}}{separator}"
                for i in source[1:-1]:
                    yield i
                    yield '-' * len(i)
                width = endp - 1  # - len(source[endl])
                separator = '-' * width
                yield source[-1]
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
