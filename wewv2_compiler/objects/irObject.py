from enum import IntEnum, auto
from typing import Optional


def pullsize(arg):
    if hasattr(arg, "size"):
        return arg.size
    return 4


class RegisterEnum(IntEnum):
    (stackptr, baseptr, irptr, ret, acc1, acc2, aaa, bbb, ccc, ddd, eee,
     fff) = range(12)


class Register:
    def __init__(self, reg: int, size: int, sign: bool=False):
        self.reg = reg
        self.size = size
        self.sign = sign

    def resize(self, new_size: int=None, new_sign: bool=None) -> 'Register':
        """Get a resized copy of this register."""
        return Register(self.reg, new_size or self.size,
                        new_sign or self.sign)

    def __str__(self):
        return f"%{self.reg}{'s' if self.sign else 'u'}{self.size}"

    __repr__ = __str__


class NamedRegister:
    def __init__(self, reg: RegisterEnum, size: int, sign: bool=False):
        self.reg = reg
        self.size = size
        self.sign = sign

    @classmethod
    def __getattr__(cls, attr: str) -> 'NamedRegister':
        return lambda size, sign=False: cls(RegisterEnum(attr), size, sign)

    def resize(self, new_size: int=None, new_sign: bool=None) -> 'Register':
        """Get a resized copy of this register."""
        return Register(self.reg, new_size or self.size,
                        new_sign or self.sign)

    def __str__(self):
        return f"%{self.reg.name}{'s' if self.sign else 'u'}{self.size}"

    __repr__ = __str__


class Immediate:
    def __init__(self, val: int, size: int):
        self.val = val
        self.size = size

    def __str__(self):
        return f"Imm({self.val}:{self.size})"

    __repr__ = __str__


class Dereference:
    def __init__(self, loc):
        self.to = loc

    @property
    def size(self):
        return pullsize(self.to)


class IRObject:
    """An instruction in internal representation."""

    def __init__(self):
        self.jumps_from = []
        self.jumps_to = []
        self.owner = None

    def take_jumps_from(self, other: 'IRObject'):
        """Take all the jumps from another objects and make them owned by this."""
        for i in other.jumps_from:
            i.jumps_to.remove(self)
            i.jumps_to.append(self)
        self.jumps_from = other.jumps_from
        other.jumps_from = []

    def __str__(self):
        attrs = " ".join(f"<{k}: {v}>" for k, v in self.__dict__.items() if not k.startswith("_"))
        return f"<{self.__class__.__name__} {attrs}>"


class MakeVar(IRObject):
    def __init__(self, variable):
        super().__init__()
        self.var = variable


class LoadVar(IRObject):
    def __init__(self, variable, to):
        super().__init__()
        self.variable = variable
        self.to = to


class SaveVar(IRObject):
    def __init__(self, variable, from_):
        super().__init__()
        self.variable = variable
        self.from_ = from_


class Mov(IRObject):
    """More general than LoadVar/ SaveVar, for setting registers directly."""

    def __init__(self, to, from_):
        super().__init__()
        self.to = to
        self.from_ = from_

        # TODO: if sizes are different, emit extend operations


class Unary(IRObject):
    def __init__(self, arg, op: str):
        super().__init__()
        self.arg = arg
        self.op = op

    @classmethod
    def __getattr__(cls, attr):
        return lambda arg: cls(arg, attr)


class Binary(IRObject):
    def __init__(self, left, right, op: str):
        super().__init__()
        self.left = left
        self.right = right
        self.op = op

    @classmethod
    def __getattr__(cls, attr):
        return lambda left, right: cls(left, right, attr)


class Push(IRObject):
    def __init__(self, arg):
        super().__init__()
        self.arg = arg


class Pop(IRObject):
    def __init__(self, arg):
        super().__init__()
        self.arg = arg


class Prelude(IRObject):
    """Function prelude."""
    pass


class Epilog(IRObject):
    """Function epilog."""

    def __init__(self, size: int):
        self.size = size


class Return(IRObject):
    """Function return"""
    pass


class Call(IRObject):
    """Jump to location, push return address."""

    def __init__(self, argsize: int):
        self.argsize = argsize


class Resize(IRObject):
    """Resize data."""

    def __init__(self, from_: Register, to: Register):
        super().__init__(to)
        self.from_ = from_
        self.to = to
