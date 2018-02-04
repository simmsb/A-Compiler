from enum import IntEnum

class Instruction:
    @property
    def group(self):
        raise NotImplementedError

class BinaryInstructions(IntEnum, Instruction):
    """Binary instructions."""
    (add, sub, mul, udiv, idiv, shl,
     shr, sar, and_, or_, xor) = range(11)

    @property
    def group(self):
        return 0


class UnaryInstructions(IntEnum, Instruction):
    """Unary instructions."""
    (neg, pos, not_) = range(3)

    @property
    def group(self):
        return 1


class Manip(IntEnum, Instruction):
    """Cpu manipulation instructions."""
    (mov, sxu, sxi, jmp, set, tst, halt) = range(7)

    @property
    def group(self):
        return 2


class Mem(IntEnum, Instruction):
    """Memory manipulation instructions."""
    (stks, push, pop, call, ret) = range(5)

    @property
    def group(self):
        return 3


class IO(IntEnum, Instruction):
    """IO instructions."""
    (getc, putc) = range(2)

    @property
    def group(self):
        return 4


def pack_instruction(instr: Instruction, size: int):
    value = size << 14 | instr.group << 8 | instr
    return value & 0xffff
