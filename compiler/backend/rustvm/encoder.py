from typing import Union, Tuple, Iterable
from enum import IntEnum
from dataclasses import dataclass, field

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
    (binv, linv, neg, pos) = range(4)

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

@dataclass(frozen=True)
class HardwareRegister:
    """Reference to a named hardware register."""
    index: int
    size = 8  # all hardware registers are just size 8


@dataclass(frozen=True)
class HardwareMemoryLocation:
    index: int


class SpecificRegisters:
    free_reg_offset = 3

    (stk, bas, cur, ret) = map(HardwareRegister, range(4))


@dataclass
class HardWareInstruction:
    instr: Union[BinaryInstructions,
                 UnaryInstructions,
                 Manip,
                 Mem,
                 IO]
    size: int
    args: Tuple[Union[Register,
                      Dereference,
                      DataReference,
                      HardwareMemoryLocation,
                      JumpTarget]]

    @property
    def code_size(self):
        # TODO: confirm this works
        return 2 * (1 + len(self.args))


def pack_instruction(instr: HardWareInstruction) -> bytes:
    """Pack an instruction into bytes."""
    idx = instr.instr

    size = {
        1: 0,
        2: 1,
        4: 2,
        8: 3
    }[instr.size]

    value = (size << 14) | (idx.group << 8) | idx
    return (value & 0xffff).to_bytes(2, byteorder="little")


def pack_param(param: int, reg: bool=False, deref: bool=False) -> bytes:
    """Packs a single parameter into bytes."""
    if param < 0:
        param = 0xffff + param + 1
    return (param | reg << 15 | deref << 14).to_bytes(2, byteorder="little")


class InstructionEncoder(metaclass=Emitter):

    @classmethod
    def encode_instr(cls, instr: ir_object.IRObject) -> Iterable[HardWareInstruction]:
        """Encode an IR Instruction into a hardware instruction.
        Some instructions may expand into multiple hardware instructions so the result is an iterable.
        """
        name = type(instr).__name__

        if name in ("JumpTarget",):  # leave in jump targets
            yield instr
            return

        if name not in cls.emitters:
            raise InternalCompileException(f"Missing encoder for instruction {name}")

        yield from cls.emitters[name](instr)

    @emits("Mov")
    def emit_mov(cls, instr: ir_object.Mov):
        yield HardWareInstruction(
            Manip.mov,
            instr.to.size,
            (instr.to, instr.from_)
        )

    @emits("Unary")
    def emit_unary(cls, instr: ir_object.Unary):

        hwin = getattr(UnaryInstructions, instr.op)

        yield HardWareInstruction(
            hwin,
            instr.arg.size,
            (instr.arg, instr.to)
        )

    @emits("Binary")
    def emit_binary(cls, instr: ir_object.Binary):

        replacements = {
            "and": "and_",
            "or": "or_"
        }

        # replace 'and' with 'and_', etc. leave everything else
        op = replacements.get(instr.op) or instr.op

        hwin = getattr(BinaryInstructions, op)

        yield HardWareInstruction(
            hwin,
            instr.left.size,
            (instr.left, instr.right, instr.to)
        )

    @emits("Compare")
    def emit_compare(cls, instr: ir_object.Compare):
        yield HardWareInstruction(
            Manip.tst,
            instr.left.size,
            (instr.left, instr.right)
        )

    @emits("SetCmp")
    def emit_setcmp(cls, instr: ir_object.SetCmp):
        yield HardWareInstruction(
            Manip.set,
            instr.dest.size,
            (instr.op, instr.dest)
        )

    @emits("Push")
    def emit_push(cls, instr: ir_object.Push):
        yield HardWareInstruction(
            Mem.push,
            instr.arg.size,
            (instr.arg,)
        )

    @emits("Pop")
    def emit_pop(cls, instr: ir_object.Pop):
        yield HardWareInstruction(
            Mem.pop,
            instr.arg.size,
            (instr.arg,)
        )

    @emits("Return")
    def emit_return(cls, instr: ir_object.Return):
        yield HardWareInstruction(
            Manip.mov,
            instr.arg.size,
            (SpecificRegisters.ret, instr.arg)
        )

        yield HardWareInstruction(
            Mem.ret,
            1,  # unused
            ()
        )

    @emits("Call")
    def emit_call(cls, instr: ir_object.Call):

        yield HardWareInstruction(
            Mem.call,
            instr.jump.size,  # size of return address (we have two byte pointers)
            (instr.jump,)
        )

        arg_len = ir_object.Immediate(instr.argsize, 8)

        yield HardWareInstruction(
            Manip.mov,
            arg_len.size,  # just use full size
            (arg_len,)
        )

        yield HardWareInstruction(
            Manip.mov,
            instr.result.size,
            (instr.result, SpecificRegisters.ret)
        )

    @emits("Jump")
    def emit_jump(cls, instr: ir_object.Jump):
        condition = instr.condition or ir_object.Immediate(1, 2)  # 2-byte containing 1

        yield HardWareInstruction(
            Manip.jmp,
            condition.size,
            (condition, instr.location)
        )

    @emits("Resize")
    def emit_resize(cls, instr: ir_object.Resize):

        # if source is signed, we emit signed resize
        hwin = Manip.sxi if instr.from_.sign else Manip.sxu

        # instruction size is size of 'from_' param
        # instruction size parameter is size of 'to' param

        size = {
            1: 0,
            2: 1,
            4: 2,
            8: 3
        }[instr.to.size]

        yield HardWareInstruction(
            hwin,
            instr.from_.size,
            (instr.from_, size, instr.to)
        )
