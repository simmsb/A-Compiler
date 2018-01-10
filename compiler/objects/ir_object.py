from enum import IntEnum
from typing import Optional


def pullsize(arg):
    if hasattr(arg, "size"):
        return arg.size
    return 4


class RegisterEnum(IntEnum):
    (stackptr, baseptr, irptr, ret, acc1,
     acc2, aaa, bbb, ccc, ddd, eee, fff) = range(12)


class CompType(IntEnum):
    (leq, lt, eq, neq, gt, geq, uncond) = range(7)


class Register:
    def __init__(self, reg: int, size: int, sign: bool=False):
        self.reg = reg
        self.size = size
        self.sign = sign

    def resize(self, new_size: int=None, new_sign: bool=None) -> 'Register':
        """Get a resized copy of this register."""
        self.size = new_size or self.size
        self.sign = new_sign or self.sign
        return Register(self.reg, new_size or self.size,
                        new_sign or self.sign)

    def __str__(self):
        return f"%{self.reg}{'s' if self.sign else 'u'}{self.size}"

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
        self.parent = None

    def add_jump_to(self, from_: 'IRObject'):
        self.jumps_from.append(from_)
        from_.jumps_to.append(self)

    def take_jumps_from(self, other: 'IRObject'):
        """Take all the jumps from another objects and make them owned by this."""
        for i in other.jumps_from:
            i.jumps_to.remove(self)
            i.jumps_to.append(self)
        self.jumps_from.extend(other.jumps_from)
        other.jumps_from = []

    def __str__(self):
        attrs = " ".join(f"<{k}: {v}>" for k, v in self.__dict__.items() if not k.startswith("_"))
        return f"<{self.__class__.__name__} {attrs}>"


class MakeVar(IRObject):
    def __init__(self, variable):
        super().__init__()
        self.var = variable


class LoadVar(IRObject):
    def __init__(self, variable, to, lvalue: bool=False):
        """Load a variable to a location.

        :param variable: Variable info object.
        :param to: Location to load to.
        :param lvalue: If true: load the memory location, if false, load the value.
        """
        super().__init__()
        self.variable = variable
        self.to = to
        self.lvalue = lvalue


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


class BinaryMeta(type):

    def __getattr__(cls, attr):
        if attr in cls.valid_ops:
            return lambda left, right, to=None: cls(left, right, attr, to)


class Binary(IRObject, metaclass=BinaryMeta):
    """Binary operation.

    if :param to: is not provided, defaults to :param left:
    """

    valid_ops = ("add", "sub", "mul", "div")

    def __init__(self, left, right, op: str, to=None):
        super().__init__()
        self.left = left
        self.right = right
        self.op = op
        self.to = to or left


class Compare(IRObject):
    """Comparison operation.

    Compares two operands and sets resultant registers.
    """

    def __init__(self, left, right):
        super().__init__()
        self.left = left
        self.right = right


class SetCmp(IRObject):
    """Set register from last comparison."""

    def __init__(self, reg, op):
        super().__init__()
        self.reg = reg
        self.op = op


class Push(IRObject):
    def __init__(self, arg):
        super().__init__()
        self.arg = arg


class Pop(IRObject):
    def __init__(self, arg):
        super().__init__()
        self.arg = arg


class Prelude(IRObject):
    """Function/ scope prelude."""

    def __init__(self, scope):
        """Prelude of a scope.
        :param scope: The scope this prelude is of."""
        super().__init__()
        self.scope = scope


class Epilog(IRObject):
    """Function/ scope epilog."""

    def __init__(self, scope):
        """Epilog of a scope
        :param scope: The scope this epilog is of."""
        super().__init__()
        self.scope = scope


class Return(IRObject):
    """Function return"""

    def __init__(self, reg: Optional[Register]=None):
        """Return from a scope.
        This should be placed after preludes to all scopes beforehand.
        :param reg: register to return. If this is None, return void.
        """
        super().__init__()
        self.reg = reg


class Call(IRObject):
    """Jump to location, push return address."""

    def __init__(self, argsize: int, jump: Register, result: Register):
        super().__init__()
        self.argsize = argsize
        self.jump = jump
        self.result = result


class Jump(IRObject):
    """Conditional jump."""

    def __init__(self, location, comparison):
        super().__init__()
        self.location = location
        self.comparison = comparison


class JumpTarget(IRObject):
    """Jump target."""
    pass


class Resize(IRObject):
    """Resize data."""

    def __init__(self, from_: Register, to: Register):
        super().__init__()
        self.from_ = from_
        self.to = to
