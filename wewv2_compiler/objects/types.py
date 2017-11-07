from typing import List


class Type:
    size = 0
    const = False


class Int(Type):

    def __init__(self, t: str, const: bool):
        self.t = t
        self.const = const

    @property
    def size(self):
        return int(self.t[1])

    @property
    def signed(self):
        return self.t[0] == 's'


class Pointer(Type):

    size = 2  # 16 bit pointers

    def __init__(self, to: Type, const: bool):
        self.to = to
        self.const = const

    @property
    def casts_to(self):
        return Int, Pointer, Function


class Array(Type):

    def __init__(self, t: str, s: int, const: bool):
        self.t = t
        self.size = s
        self.const = const


class Function(Type):

    def __init__(self, returns: Type, args: List[Type], const: bool):
        self.returns = returns
        self.args = args
        self.const = const
