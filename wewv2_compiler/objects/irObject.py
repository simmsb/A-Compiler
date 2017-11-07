from enum import IntEnum, auto


class IRObject:
    """An instruction in internal representation

    if params are integers, they are treated as literals/ memory addresses
        depending on the param type of the instruction

    if params are of the register enum (TODO: write register enums),
        they will be treated as registers etc

    if params are instances of :class:`base.Variable` the variable is used appropriately
    """


class MakeVar(IRObject):

    def __init__(self, variable):
        self.var = variable


class LoadVar(IRObject):

    def __init__(self, variable, to):
        self.variable = variable
        self.to = to


class SaveVar(IRObject):

    def __init__(self, variable, from_):
        self.variable = variable
        self.from_ = from_


class Numeric(IRObject):
    pass


class Add(Numeric):
    pass
