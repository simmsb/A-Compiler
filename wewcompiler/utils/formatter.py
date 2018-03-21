class StringViewIter:
    __slots__ = ("inp", "position")

    def __init__(self, inp: str):
        self.inp = inp
        self.position = 0

    def __iter__(self):
        return self

    def __next__(self):
        if self.position >= len(self.inp):
            raise StopIteration
        self.position += 1
        return self.inp[self.position - 1]

    def peek(self):
        return self.inp[self.position + 1]

    def prev(self):
        self.position -= 1


def format_lines(inp: str):
    def indent_loop():
        indent = 0
        view = StringViewIter(inp)
        for c in inp:
            if c == "<":
                yield "\n"
                yield indent * " "
                yield "<"
                indent += 1
            elif c == ">":
                indent -= 1
                for i in view:
                    if i != ">":
                        break
                    indent -= 1
                    yield ">"
                view.prev()
                yield ">"
            else:
                yield c
    return "".join(indent_loop())
