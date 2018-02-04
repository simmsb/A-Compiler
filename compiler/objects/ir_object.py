from enum import IntEnum
from typing import Optional, Union, Iterable


def pullsize(arg):
    if hasattr(arg, "size"):
        return arg.size
    return 4


class CompType(IntEnum):
    (leq, lt, eq, neq, gt, geq, uncond) = range(7)


class Register:
    __slots__ = ("reg",
                 "physical_register",
                 "size",
                 "sign")

    def __init__(self, reg: int, size: int, sign: bool=False):
        self.reg = reg
        self.physical_register = None
        self.size = size
        self.sign = sign

    def resize(self, new_size: int=None, new_sign: bool=None) -> 'Register':
        """Get a resized copy of this register."""
        size = new_size or self.size
        sign = new_sign or self.sign
        return Register(self.reg, size, sign)

    def copy(self) -> 'Register':
        return Register(self.reg, self.size, self.sign)

    def __eq__(self, other):
        if not isinstance(other, Register):
            raise ValueError
        return self.reg == other.reg

    def __hash__(self):
        return hash(self.reg)

    def __str__(self):
        phys_reg = self.physical_register if self.physical_register is not None else ''
        return f"%{self.reg}@{phys_reg}({'s' if self.sign else 'u'}{self.size})"

    __repr__ = __str__


class Immediate:
    def __init__(self, val: int, size: int):
        self.val = val
        self.size = size

    def __str__(self):
        return f"Imm({self.val}:{self.size})"

    __repr__ = __str__


class Dereference:
    def __init__(self, loc: Register):
        self.to = loc.copy()
        assert loc.size == 2

    @property
    def size(self):
        return pullsize(self.to)

    def __str__(self):
        return f"Dereference({self.to})"


IRParam = Union[Register, Dereference, Immediate]


def filter_reg(reg: IRParam) -> Optional[Register]:
    """Filters a possible register object. returns None if not a register."""
    if isinstance(reg, Dereference):
        return reg.to
    if isinstance(reg, Register):
        return reg
    return None


class IRObject:
    """An instruction in internal representation."""

    def clone_regs(self):
        """Clone the registers of this instruction so that they can be mutated without affecting other IR instructions."""
        def copy_reg(arg):
            if isinstance(arg, Register):
                return arg.copy()
            return arg

        for attr in self._touched_regs:
            # copy the instances of the registers we're using
            setattr(self, attr, copy_reg(getattr(self, attr)))


    def __new__(cls, *args, **kwargs):
        self = super().__new__(cls)
        cls.__init__(self, *args, **kwargs)

        return self

    def __init__(self):
        #: list of instructions to be run before this instruction
        self.pre_instructions = []

        #: regisers that are dead after this instruction
        self.closing_registers = set()
        self.parent = None

    def __str__(self):
        print_ignore = ("parent", "jumps_to", "jumps_from")

        attrs = " ".join(f"<{k}: {v}>" for k, v in self.__dict__.items() if (not k.startswith("_")) and k not in print_ignore)
        return f"<{self.__class__.__name__} {attrs}>"

    __repr__ = __str__

    @property
    def touched_registers(self) -> Iterable[Register]:
        """Get the registers that this instruction reads from and writes to."""
        attrs = self._touched_regs
        regs = (filter_reg(getattr(self, i)) for i in attrs)
        return list(filter(None, regs))

    _touched_regs = ()

    def insert_pre_instrs(self, *instrs):
        self.pre_instructions.extend(instrs)


class MakeVar(IRObject):
    # TODO: why does this exist?

    def __init__(self, variable: 'Variable'):
        super().__init__()
        self.var = variable


class LoadVar(IRObject):
    def __init__(self, variable: 'Variable', to: IRParam, lvalue: bool=False):
        """Load a variable to a location.

        :param variable: Variable info object.
        :param to: Location to load to.
        :param lvalue: If true: load the memory location, if false, load the value.
        """
        super().__init__()
        self.variable = variable
        self.to = to
        self.lvalue = lvalue

    _touched_regs = "to",


class SaveVar(IRObject):
    def __init__(self, variable: 'Variable', from_: IRParam):
        super().__init__()
        self.variable = variable
        self.from_ = from_

    _touched_regs = "from_",


class Mov(IRObject):
    """More general than LoadVar/ SaveVar, for setting registers directly."""

    def __init__(self, to: IRParam, from_: IRParam):
        super().__init__()
        self.to = to
        self.from_ = from_

    _touched_regs = "to", "from_"


class Unary(IRObject):
    def __init__(self, arg: IRParam, op: str):
        super().__init__()
        self.arg = arg
        self.op = op

    @classmethod
    def __getattr__(cls, attr):
        return lambda arg: cls(arg, attr)

    _touched_regs = "op",


class BinaryMeta(type):

    def __getattr__(cls, attr):
        if attr in cls.valid_ops:
            return lambda left, right, to=None: cls(left, right, attr, to)


class Binary(IRObject, metaclass=BinaryMeta):
    """Binary operation.

    if :param to: is not provided, defaults to :param left:
    """

    valid_ops = ("add", "sub", "mul", "div")

    def __init__(self, left: IRParam, right: IRParam, op: str, to: Optional[IRParam]=None):
        super().__init__()
        self.left = left
        self.right = right
        self.op = op
        self.to = to or left

    _touched_regs = "left", "right", "to"


class Compare(IRObject):
    """Comparison operation.

    Compares two operands and sets resultant registers.
    """

    def __init__(self, left: IRParam, right: IRParam):
        super().__init__()
        self.left = left
        self.right = right

    _touched_regs = "left", "right"


class SetCmp(IRObject):
    """Set register from last comparison."""

    def __init__(self, reg: IRParam, op):
        super().__init__()
        self.reg = reg
        self.op = op

    _touched_regs = "reg",


class Push(IRObject):
    def __init__(self, arg: IRParam):
        super().__init__()
        self.arg = arg

    _touched_regs = "arg",


class Pop(IRObject):
    def __init__(self, arg: IRParam):
        super().__init__()
        self.arg = arg

    _touched_regs = "arg",


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

    def __init__(self, reg: Optional[IRParam]=None):
        """Return from a scope.
        This should be placed after preludes to all scopes beforehand.
        :param reg: register to return. If this is None, return void.
        """
        super().__init__()
        self.reg = reg

    _touched_regs = "reg",


class Call(IRObject):
    """Jump to location, push return address."""

    def __init__(self, argsize: int, jump: IRParam, result: IRParam):
        super().__init__()
        self.argsize = argsize
        self.jump = jump
        self.result = result

    _touched_regs = "jump", "result"


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
    """Conditional jump.

    If condition is not provided this is a unconditional jump."""

    def __init__(self, location, condition=None):
        super().__init__()
        self.location = location
        self.add_jump_to(location)
        self.condition = condition

    _touched_regs = "location",


class JumpTarget(Jumpable):
    """Jump target."""
    pass


class Resize(IRObject):
    """Resize data."""

    def __init__(self, from_: IRParam, to: IRParam):
        super().__init__()
        self.from_ = from_
        self.to = to

    _touched_regs = "from_", "to"


class Spill(IRObject):
    """Spill a register to a location."""

    def __init__(self, reg: int, index: int):
        super().__init__()
        self.reg = reg
        self.index = index


class Load(IRObject):
    """Recover a spilled register."""

    def __init__(self, reg: int, index: int):
        super().__init__()
        self.reg = reg
        self.index = index
