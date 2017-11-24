from enum import IntEnum, auto
from typing import Optional

from base import Variable


def pullsize(arg):
    if hasattr(arg, "size"):
        return arg.size
    return 4


class Register(IntEnum):  # TODO: move this?
    (stackptr, baseptr, irptr, ret, acc1, acc2, aaa, bbb, ccc, ddd, eee,
     fff) = range(10)


class Dereference:
    def __init__(self, loc):
        self.to = loc

    @property
    def size(self):
        return pullsize(self.to)


class IRObject:
    """An instruction in internal representation

    if params are integers, they are treated as literals/ memory addresses
        depending on the param type of the instruction

    if params are of the register enum (TODO: write register enums),
        they will be treated as registers etc

    if params are instances of :class:`base.Variable` the variable is used appropriately
    """

    def __init__(self, size=None):
        self.size = size
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


class MakeVar(IRObject):
    def __init__(self, variable):
        super().__init__(variable.size)
        self.var = variable


class LoadVar(IRObject):
    def __init__(self, variable, to):
        super().__init__(variable.size)
        self.variable = variable
        self.to = to


class SaveVar(IRObject):
    def __init__(self, variable, from_):
        super().__init__(variable.size)
        self.variable = variable
        self.from_ = from_


class Mov(IRObject):
    """More general than LoadVar/ SaveVar, for setting registers directly."""

    def __init__(self, to, from_, size=None):
        super().__init__(size or max(pullsize(to), pullsize(from_)))
        self.to = to
        self.from_ = from_

        # TODO: if sizes are different, emit extend operations


class Unary(IRObject):
    def __init__(self, arg, op: str, size=None):
        super().__init__(arg.size)
        self.arg = arg
        self.op = op

    @classmethod
    def __getattr__(cls, attr):
        return lambda arg: cls(arg, attr)


class Binary(IRObject):
    def __init__(self, left, right, op: str):
        super().__init__(max(pullsize(left), pullsize(right)))
        self.left = left
        self.right = right
        self.op = op

    @classmethod
    def __getattr__(cls, attr):
        return lambda left, right: cls(left, right, attr)


class Push(IRObject):
    def __init__(self, arg, size=None):
        super().__init__(pullsize(arg))
        self.arg = arg


class Pop(IRObject):
    def __init__(self, arg, size=None):
        super().__init__(size or pullsize(arg))
        self.arg = arg


class Prelude(IRObject):
    """Function prelude."""
    pass


class Return(IRObject):
    """Function return"""
    pass


class Call(IRObject):
    """Jump to location, push return address."""
