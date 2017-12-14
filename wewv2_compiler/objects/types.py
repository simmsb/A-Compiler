from typing import List


class Type:
    size = 0
    const = False


class Int(Type):

    def __init__(self, t: str, const: bool=False):
        self.t = t
        self.const = const

    def __eq__(self, other: Type):
        if not isinstance(other, Int):
            return False
        return (self.const == other.const and
                self.t == other.t)

    def __str__(self):
        tp = str(self.t)
        if self.const:
            tp = f"|{tp}|"
        return tp

    @property
    def casts_to(self):
        return Int, Pointer, Function

    @property
    def size(self):
        return int(self.t[1])

    @property
    def signed(self):
        return self.t[0] == 's'


class Pointer(Type):

    size = 2  # 16 bit pointers ?

    def __init__(self, to: Type, const: bool=False):
        self.to = to
        self.const = const

    def __eq__(self, other: Type):
        if not isinstance(other, Pointer):
            return False
        return (self.to == other.to and
                self.const == other.const)

    def __str__(self):
        tp = f"*{self.to}"
        if self.const:
            tp = f"|{tp}|"
        return tp

    @property
    def casts_to(self):
        return Int, Pointer, Function


class Array(Type):

    def __init__(self, t: Type, l: int, const: bool):
        self.t = t
        self.length = l
        self.const = const

    def __eq__(self, other: Type):
        if not isinstance(other, Array):
            return False
        return (self.t == other.t and
                self.length == other.length and
                self.consts == other.const)

    def __str__(self):
        tp = f"[{self.t}@{self.length}]"
        if self.const:
            tp = f"|{tp}|"
        return tp

    @property
    def size(self) -> int:
        # return length of array in memory
        return self.t * self.length


class Function(Type):

    def __init__(self, returns: Type, args: List[Type], const: bool):
        self.returns = returns
        self.args = args
        self.const = const

    def __str__(self):
        types = ",".join(map(str, self.args))
        fns = f"({types}) -> {self.returns}"
        if self.const:
            fns = f"|{fns}|"
        return fns

    def __eq__(self, other: Type):
        if not isinstance(other, Function):
            return False
        return (self.returns == other.returns and
                all(a == b for a, b in zip(self.args, other.args)) and
                self.const == other.const)


char = Int('u1')
const_char = Int('u1', True)
string_lit = Pointer(const_char)
