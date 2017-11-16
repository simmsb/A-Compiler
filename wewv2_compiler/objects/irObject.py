from enum import IntEnum, auto
from typing import Optional


class Register(IntEnum):  # TODO: move this?
    stackptr = 0
    baseptr = 1
    irptr = 2
    accumulator = 3
    aaa = 4
    bbb = 5
    ccc = 6
    ddd = 7
    eee = 8
    fff = 9


class Dereference:
    def __init__(self, loc):
        self.to = loc


class IRObject:
    """An instruction in internal representation

    if params are integers, they are treated as literals/ memory addresses
        depending on the param type of the instruction

    if params are of the register enum (TODO: write register enums),
        they will be treated as registers etc

    if params are instances of :class:`base.Variable` the variable is used appropriately
    """

    def __init__(self):
        self.jumps_from = []
        self.jumps_to = []
        self.owner = None

    def take_jumps_from(self, other: IRObject):
        """Take all the jumps from another objects and make them owned by this."""
        for i in other.jumps_from:
            i.jumps_to.remove(self)
            i.jumps_to.append(self)
        self.jumps_from = other.jumps_from
        other.jumps_from = []


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


class Return(IRObject):
    """Function return"""
    pass
