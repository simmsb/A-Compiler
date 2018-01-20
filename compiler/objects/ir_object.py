from enum import IntEnum
from typing import Optional, Union


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
        size = new_size or self.size
        sign = new_sign or self.sign
        return Register(self.reg, size, sign)

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

    def __str__(self):
        return f"Dereference({self.to})"


def filter_reg(reg: Union[Dereference, Register, any]) -> Optional[Register]:
    """Filters a possible register object. returns None if not a register."""
    if isinstance(reg, Dereference):
        return reg.to
    if isinstance(reg, Register):
        return reg
    return None


class IRObject:
    """An instruction in internal representation."""

    def __init__(self):
        self.parent = None

    def __str__(self):
        print_ignore = ("parent", )

        attrs = " ".join(f"<{k}: {v}>" for k, v in self.__dict__.items() if (not k.startswith("_")) and k not in print_ignore)
        return f"<{self.__class__.__name__} {attrs}>"

    @property
    def touched_registers(self):
        """Get the registers that this instruction reads from and writes to."""
        regs = self._touched_regs()
        return set(filter(None, map(filter_reg, regs)))

    def _touched_regs(self):
        return ()


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

    def _touched_regs(self):
        return self.to,


class SaveVar(IRObject):
    def __init__(self, variable, from_):
        super().__init__()
        self.variable = variable
        self.from_ = from_

    def _touched_regs(self):
        return self.from_,


class Mov(IRObject):
    """More general than LoadVar/ SaveVar, for setting registers directly."""

    def __init__(self, to, from_):
        super().__init__()
        self.to = to
        self.from_ = from_

    def _touched_regs(self):
        return self.to, self.from_


class Unary(IRObject):
    def __init__(self, arg, op: str):
        super().__init__()
        self.arg = arg
        self.op = op

    @classmethod
    def __getattr__(cls, attr):
        return lambda arg: cls(arg, attr)

    def _touched_regs(self):
        return self.op,


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

    def _touched_regs(self):
        return self.left, self.right, self.to


class Compare(IRObject):
    """Comparison operation.

    Compares two operands and sets resultant registers.
    """

    def __init__(self, left, right):
        super().__init__()
        self.left = left
        self.right = right

    def _touched_regs(self):
        return self.left, self.right


class SetCmp(IRObject):
    """Set register from last comparison."""

    def __init__(self, reg, op):
        super().__init__()
        self.reg = reg
        self.op = op

    def _touched_regs(self):
        return self.reg,


class Push(IRObject):
    def __init__(self, arg):
        super().__init__()
        self.arg = arg

    def _touched_regs(self):
        return self.arg,


class Pop(IRObject):
    def __init__(self, arg):
        super().__init__()
        self.arg = arg

    def _touched_regs(self):
        return self.arg,


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

    def _touched_regs(self):
        return self.reg,


class Call(IRObject):
    """Jump to location, push return address."""

    def __init__(self, argsize: int, jump: Register, result: Register):
        super().__init__()
        self.argsize = argsize
        self.jump = jump
        self.result = result

    def _touched_regs(self):
        return self.jump, self.result


class Jumpable(IRObject):

    def __init__(self):
        super().__init__()
        self.jumps_from = []
        self.jumps_to = []

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


class Jump(Jumpable):
    """Conditional jump."""

    def __init__(self, location, comparison):
        super().__init__()
        self.location = location
        self.add_jump_to(location)
        self.comparison = comparison

    def _touched_regs(self):
        return self.location,


class JumpTarget(Jumpable):
    """Jump target."""
    pass


class Resize(IRObject):
    """Resize data."""

    def __init__(self, from_: Register, to: Register):
        super().__init__()
        self.from_ = from_
        self.to = to

    def _touched_regs(self):
        return self.from_, self.to
