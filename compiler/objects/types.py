from typing import List, Tuple

from compiler.objects.errors import CompileException


class Type:
    size = 0
    const = False
    signed = False

    can_cast_to: Tuple['Type'] = ()

    def implicitly_casts_to(self, other: 'Type') -> bool:
        """Determine if it is valid to implicitly cast the the other type to this type.
        does not care about size.
        """
        return isinstance(other, self.can_cast_to)


class Int(Type):

    def __init__(self, t: str, const: bool=False):
        self.t = t
        self.const = const

    @classmethod
    def fromsize(cls, size: int, sign: bool=False):
        return cls(f"{'s' if sign else 'u'}{size}")

    def __eq__(self, other: Type):
        if not isinstance(other, Int):
            return False
        return (self.const == other.const and
                self.t == other.t)

    def __str__(self):
        tp = self.t
        if self.const:
            tp = f"|{tp}|"
        return tp

    def __repr__(self):
        return f"Int({self.t!r}, {self.const!r})"

    @property
    def can_cast_to(self) -> Tuple[Type]:
        return Int,

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

    def __repr__(self):
        return f"Pointer({self.to!r}, {self.const!r})"

    @property
    def can_cast_to(self) -> Tuple[Type]:
        return Pointer, Function



class Array(Type):

    def __init__(self, to: Type, l: int=None, const: bool=False):
        self.to = to
        self.length = l
        self.const = const

    def __eq__(self, other: Type):
        if not isinstance(other, Array):
            return False
        return (self.to == other.to
                # if we dont know our length dont check the other's length
                and ((self.length is None) or (self.length == other.length))
                and self.const == other.const)

    def __str__(self):
        if self.length is not None:
            tp = f"[{self.to}@{self.length}]"
        else:
            tp = f"[{self.to}]"
        if self.const:
            tp = f"|{tp}|"
        return tp

    def __repr__(self):
        return f"Array({self.to!r}, {self.length!r}, {self.const!r})"

    @property
    def can_cast_to(self) -> Tuple[Type]:
        return Pointer, Function, Array

    @property
    def size(self) -> int:
        # return length of array in memory
        if self.length is None:
            raise CompileException(f"Array {self} has no size information.")

        if self.length < 0:
            raise CompileException(f"Array {self} has negative size.")

        return self.to.size * self.length

    @property
    def cellsize(self) -> int:
        return self.to.size


class Function(Type):

    def __init__(self, returns: Type, args: List[Type], const: bool=False):
        self.returns = returns
        self.args = args
        self.const = const

    def __str__(self):
        types = ", ".join(map(str, self.args))
        fns = f"({types}) -> {self.returns}"
        if self.const:
            fns = f"|{fns}|"
        return fns

    def __repr__(self):
        types = ", ".join(map(repr, self.args))
        return f"Function({self.returns!r}, ({types}), {self.const!r})"

    def __eq__(self, other: Type):
        if not isinstance(other, Function):
            return False
        return (self.returns == other.returns and
                all(a == b for a, b in zip(self.args, other.args)) and
                self.const == other.const)

    @property
    def can_cast_to(self) -> Tuple[Type]:
        return Pointer, Function


char = Int('u1')
const_char = Int('u1', True)
string_lit = Pointer(const_char)
