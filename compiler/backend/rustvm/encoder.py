from typing import Union, Tuple
from enum import IntEnum
from dataclasses import dataclass

from compiler.objects.ir_object import Register, Dereference, DataReference


class BinaryInstructions(IntEnum):
    """Binary instructions."""
    (add, sub, mul, udiv, idiv, shl,
     shr, sar, and_, or_, xor) = range(11)

    @property
    def group(self):
        return 0


class UnaryInstructions(IntEnum):
    """Unary instructions."""
    (neg, pos, not_) = range(3)

    @property
    def group(self):
        return 1


class Manip(IntEnum):
    """Cpu manipulation instructions."""
    (mov, sxu, sxi, jmp, set, tst, halt) = range(7)

    @property
    def group(self):
        return 2


class Mem(IntEnum):
    """Memory manipulation instructions."""
    (stks, push, pop, call, ret) = range(5)

    @property
    def group(self):
        return 3


class IO(IntEnum):
    """IO instructions."""
    (getc, putc) = range(2)

    @property
    def group(self):
        return 4


# Why have this? because we need to distinguish from allocated free-use registers and other registers

@dataclass
class HardwareRegister:
    index: int


@dataclass
class HardwareMemoryLocation:
    index: int


class SpecificRegisters(IntEnum):
    (stk, bas, cur) = map(HardwareRegister, range(3))


@dataclass
class HardWareInstruction:
    instr: Union[BinaryInstructions,
                 UnaryInstructions,
                 Manip,
                 Mem,
                 IO]
    args: Tuple[Union[Register,
                      Dereference,
                      DataReference,
                      HardwareMemoryLocation]]

    @property
    def code_size(self):
        # TODO: sort out this
        return 2 * (1 + len(self.args))

def pack_instruction(instr, size: int):
    value = size << 14 | instr.group << 8 | instr
    return value & 0xffff
