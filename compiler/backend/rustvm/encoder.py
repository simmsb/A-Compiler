from typing import Union, Tuple
from enum import IntEnum
from dataclasses import dataclass

from compiler.objects.ir_object import Register, Dereference, DataReference, JumpTarget
from compiler.objects.errors import InternalCompileException
from compiler.objects import ir_object
from compiler.utils.emitterclass import Emitter, emits

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


# Why have this? because we need to distinguish from allocated free-use registers
# and other registers (stack pointer, base pointer, current-instruction pointer, etc)

@dataclass
class HardwareRegister:
    index: int


@dataclass
class HardwareSpecificRegister:
    index: int


@dataclass
class HardwareMemoryLocation:
    index: int


class SpecificRegisters(IntEnum):
    (stk, bas, cur) = map(HardwareSpecificRegister, range(3))


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
                      HardwareMemoryLocation,
                      JumpTarget]]

    @property
    def code_size(self):
        # TODO: sort out this
        return 2 * (1 + len(self.args))

def pack_instruction(instr, size: int):
    value = size << 14 | instr.group << 8 | instr
    return value & 0xffff


def encodes(name: str):
    """Decorator that marks a function for what IR it will encode.
    Also marks as a static method.
    """
    def deco(fn):
        fn.encoder_for = name
        return staticmethod(fn)
    return deco


class InstructionEncoder(metaclass=Emitter):

    @classmethod
    def encode_instr(cls, instr: ir_object.IRObject):

        if instr.__name__ not in cls.emitters:
            raise InternalCompileException(f"Missing encoder for instruction {instr.__name__}")

        return cls.emitters[instr.__name__](instr)
