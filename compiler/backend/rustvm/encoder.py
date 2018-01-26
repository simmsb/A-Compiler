from enum import Enum

class BinaryInstructions(Enum):
    """Binary instructions."""
    (add, sub, mul, udiv, idiv, shl,
     shr, sar, and_, or_, xor) = range(11)


class UnaryInstructions(Enum):
    """Unary instructions."""
    (neg, pos, not_) = range(3)


class Manip(Enum):
    """Cpu manipulation instructions."""
    (mov, sxu, sxi, jmp, set, tst, halt) = range(7)


class Mem(Enum):
    """Memory manipulation instructions."""
    (stks, push, pop, call, ret) = range(5)


class IO(Enum):
    """IO instructions."""
    (getc, putc) = range(2)
