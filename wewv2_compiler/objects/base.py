from abc import ABCMeta, abstractmethod


class BaseObject(metaclass=ABCMeta):
    """Base class of compilables."""

    def __new__(cls, ast, *args, **kwargs):
        obj = super().__new__(cls, ast, *args, **kwargs)
        obj.__ast = ast

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
                for l in source[startl + 1:endl - 1]:
                    yield i
                    yield '-' * len(i)
                width = (len(source[endl]) - endp) - 2
                separator = '-' * width
                yield source[startl]
                yield f"{separator}^"

        highlight = "\n".join(fmtr())

        error = ("Compilation error {line}.\n"
                 "{reason}\n{highlight}").format(
                     (f"on line {startl}" if
                      startl == endl else
                      f"on lines {startl} to {endl}"),
                     reason, highlight)

        return Exception(error, *args, **kwarg)
