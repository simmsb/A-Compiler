class IRObject:
    """An instruction in internal representation

    if params are integers, they are treated as literals/ memory addresses
        depending on the param type of the instruction

    if params are of the register enum (TODO: write register enums),
        they will be treated as registers etc

    if params are insances of :class:`base.Variable` the variable is used appropriately
    """

    def __init__(self, op, *params):  # TODO add types to this (op -> operation enum)
        self.op, self.params = op, params
        self.object = None  # object is given to use when yielded
