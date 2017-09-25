from enum import IntEnum, auto

class Instruction(IntEnum):
    mov  = 0  # val * 4 + log2(width)  -> 0 * 4 + 1 = mov1, 1 * 4 + 3 = add4
    add  = 1
    mul  = 2
    sub  = 3
    udiv = 4  # unsigned divide
    idiv = 5  # signed divide
    psh  = 6
    pop  = 7
    sxt  = 8  # sign extend,  1 -> 2, 10000000 -> 1111111110000000
    axt  = 9  # arith extend, 1 -> 2, 10000000 -> 0000000010000000


class IRObject:
    """An instruction in internal representation

    if params are integers, they are treated as literals/ memory addresses
        depending on the param type of the instruction

    if params are of the register enum (TODO: write register enums),
        they will be treated as registers etc

    if params are insances of :class:`base.Variable` the variable is used appropriately
    """
    def __init__(self, op, size, *params):  # TODO add types to this (op -> operation enum)
        self.op, self.params = op, params
        self.object = None  # object is given to use when yielded

    def emit(self):
        return self.op * 4 + {1:1, 2:2, 4:3, 8:4}[self.size]
