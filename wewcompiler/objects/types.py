from typing import List, Tuple, Optional

from wewcompiler.objects.astnode import BaseObject

from tatsu.ast import AST


class Type(BaseObject):

    __slots__ = ()

    size = 0
    const = False
    signed = False

    can_cast_to: Tuple['Type'] = ()

    def implicitly_casts_to(self, other: 'Type') -> bool:
        """Determine if it is valid to implicitly cast the the other type to this type.
        does not care about size.
        """
        # we can always cast to the same type
        if self == other:
            return True

        return isinstance(other, self.can_cast_to)


class Void(Type):

    # void types have zero size
    size = 0

    def __str__(self):
        return "()"

    def __repr__(self):
        return "Void()"


class Int(Type):

    __slots__ = ("signed", "size", "const")

    def __init__(self, t: str, const: bool = False, *, ast: Optional[AST] = None):
        super().__init__(ast=ast)
        self.signed = t[0] == "s"
        self.size = int(t[1])
        self.const = const

    def __eq__(self, other: Type):
        if not isinstance(other, Int):
            return False
        return (self.const == other.const) and (self.signed == other.signed) and (self.size == other.size)

    def __str__(self):
        tp = self.t
        if self.const:
            tp = f"|{tp}|"
        return tp

    def __repr__(self):
        return f"Int({self.t!r}, {self.const!r})"

    @property
    def t(self):
        return f"{'s' if self.signed else 'u'}{self.size}"

    @property
    def can_cast_to(self) -> Tuple[Type]:
        return Int,

    @classmethod
    def fromsize(cls, size: int, sign: bool = False, *, ast: Optional[AST] = None):
        return cls(f"{'s' if sign else 'u'}{size}", ast=ast)


class Pointer(Type):

    __slots__ = ("to", "const")

    size = 2  # 16 bit pointers ?

    def __init__(self, to: Type, const: bool = False, *, ast: Optional[AST] = None):
        super().__init__(ast=ast)
        assert isinstance(to, Type)
        self.to = to
        self.const = const

    def __eq__(self, other: Type):
        if not isinstance(other, Pointer):
            return False
        return (self.to == other.to) and (self.const == other.const)

    def __str__(self):
        tp = f"*{self.to}"
        if self.const:
            tp = f"|{tp}|"
        return tp

    def __repr__(self):
        return f"Pointer({self.to!r}, {self.const!r})"

    def implicitly_casts_to(self, other: Type):
        if not isinstance(other, Pointer):
            return False

        if self == other:
            return True

        # void pointer to any pointer is allowed
        if isinstance(self.to, Void):
            return True

        # similarly we can cast the other way around
        if isinstance(other.to, Void):
            return True

        # any other type of pointer cast is disallowed implicitly
        return False

    @property
    def can_cast_to(self) -> Tuple[Type]:
        return Pointer, Function


class Array(Type):

    __slots__ = ("to", "length", "const")

    def __init__(self, to: Type, l: Optional[int] = None,
                 const: Optional[bool] = False, *, ast: Optional[AST] = None):
        super().__init__(ast=ast)
        assert isinstance(to, Type)
        self.to = to
        self.length = l
        self.const = const

    def __eq__(self, other: Type):
        if not isinstance(other, Array):
            return False

        # if we dont know our length dont check the other's length
        len_check = ((self.length is None) or (self.length == other.length))
        const_check = self.const == other.const

        return (self.to == other.to) and len_check and const_check

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
        return Pointer, Array

    @property
    def size(self) -> int:
        # return length of array in memory
        if self.length is None:
            raise self.error(f"Array {self} has no size information.")

        if self.length < 0:
            raise self.error(f"Array {self} has negative size.")

        return self.to.size * self.length

    def implicitly_casts_to(self, other: Type) -> bool:
        if self == other:
            return True

        if isinstance(other, (Array, Pointer)):
            return self.to.implicitly_casts_to(other.to)

        return False


class Function(Type):

    __slots__ = ("returns", "args", "varargs", "const")

    size = 2  # we are pointers aswell

    def __init__(self, returns: Type, args: List[Type], varargs: bool, const: bool = False, *, ast: Optional[AST] = None):
        super().__init__(ast=ast)
        self.returns = returns
        self.args = args
        self.varargs = varargs
        self.const = const

        for i in args:
            if isinstance(i, Array):
                raise i.error("Function arguments cannot have array type as the toplevel type, use pointer instead.")
        if isinstance(returns, Array):
            raise returns.error("Functions cannot return array types.")

    def __str__(self):
        types = ", ".join(map(str, self.args))
        if self.varargs:
            types += ", ..."
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

        arg_check = all(a == b for a, b in zip(self.args, other.args))
        return (self.returns == other.returns) and arg_check


char = Int('u1')
const_char = Int('u1', True)
string_lit = Pointer(const_char)
