from itertools import count
from typing import Optional, Tuple, Iterable

import colorama

from wewcompiler.utils import add_line_count, strip_newlines
from wewcompiler.utils.formatter import format_lines
from wewcompiler.objects.errors import CompileException, InternalCompileException

from tatsu.ast import AST
from tatsu.infos import ParseInfo


def add_line_once(line: str, counter: Iterable[int]) -> str:
    return f"{next(counter):>3}| {line}"


class BaseObject:
    """Base class of compilables."""

    __slots__ = ("context", "ast", "namespace", "_info")

    def __init__(self, *, ast: Optional[AST] = None):
        self.context: 'CompileContext' = None
        self.ast = ast

        self.namespace = ""

        if ast is not None:
            assert isinstance(ast, AST)
            self._info: ParseInfo = ast.parseinfo
        else:
            self._info = None

    @property
    def identifier(self) -> str:
        startp, endp = self.get_text_positions()
        info = self._info
        startl, endl = info.line, info.endline

        return f"{type(self).__name__}:{startp}:{endp}:{startl}:{endl}"

    @property
    def code(self):
        if not hasattr(self, 'context'):
            raise InternalCompileException("AST node does not have context attached.")
        return self.context.code

    @property
    def matched_region(self) -> str:
        startp, endp = self.get_text_positions()
        startp -= 1  # why, because off by one errors memeing me

        source = [i.rstrip("\n") for i in self._info.text_lines()]
        srclen = len(source)
        if srclen == 1:
            return source[0][startp:endp]

        return "\n".join(
            (source[0][startp:],
             *source[1:-1],
             source[-1][:endp])
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

        return startp + 1, endp

    @property
    def highlight_lines(self) -> str:
        """Generate the error info line for this ast node."""

        info = self._info
        buffer = info.buffer

        startl, endl = info.line, info.endline
        startp, endp = self.get_text_positions()

        above_lines = strip_newlines(buffer.get_lines(max(startl - 5, 0), startl - 1))
        below_lines = strip_newlines(buffer.get_lines(endl + 1, endl + 5))

        source = list(strip_newlines(self._info.text_lines()))

        red = colorama.Fore.RED
        white = colorama.Fore.WHITE
        normal = colorama.Style.NORMAL
        # reset = colorama.Style.RESET_ALL + colorama.Fore.RESET
        dim = colorama.Style.DIM
        bright = colorama.Style.BRIGHT

        def make_red(s):
            return red + s + white

        def make_dim(s):
            return dim + s + normal

        def make_bright(s):
            return bright + s + normal

        line_pad = " " * 5  # 5 chars are used by the linecount that need to be padded on the arrows

        def fmtr(counter):
            if len(source) == 1:
                # start and end on same line, only need simple fmt
                yield add_line_once(source[0], counter)
                if startp == endp:  # only emit single carat when the error is a single character
                    yield make_red(line_pad + f"{'^':>{startp}}")
                else:
                    width = (endp - startp) - 1  # leave space for carats + off by one
                    separator = '-' * width
                    yield make_red(line_pad + f"{'^':>{startp}}{separator}^")
            else:
                width = (len(source[0]) - startp)
                separator = '-' * width
                yield add_line_once(source[0], counter)
                yield make_red(line_pad + f"{'^':>{startp}}{separator}")
                for i in source[1:-1]:
                    yield add_line_once(i, counter)
                    yield make_red(line_pad + '-' * len(i))
                width = endp - 1  # - len(source[endl])
                separator = '-' * width
                yield add_line_once(source[-1], counter)
                yield make_red(line_pad + f"{separator}^")

        line_counter = count(max(startl - 5, 1))

        above_lines = "\n".join(add_line_count(above_lines, line_counter))
        if above_lines:
            above_lines += "\n"
        error_lines = "\n".join(fmtr(line_counter))

        below_lines = "\n".join(add_line_count(below_lines, line_counter))
        if below_lines:
            below_lines = "\n" + below_lines

        return make_dim(above_lines) + make_bright(error_lines) + make_dim(below_lines)

    def make_error(self) -> Optional[str]:
        """Make an error for the ast node this object belongs to.

        if no ast node exists returns None
        """
        info = self._info
        if info is None:
            return None
        startl, endl = info.line, info.endline

        return "\n".join(((f"On line {startl}:"
                           if startl == endl else
                           f"On lines {startl} to {endl}:"),
                          self.highlight_lines))

    def error(self, *reasons: str):
        return CompileException(*reasons, trace=self.make_error())

    def pretty_print(self):
        instrs = map(str, self.code)
        return format_lines("\n".join(instrs))
