from itertools import chain
from typing import Iterable

from wewcompiler.backend.rustvm import encoder
from wewcompiler.objects import ir_object
from wewcompiler.objects.variable import DataReference
from wewcompiler.objects.base import StatementObject, CompileContext
from wewcompiler.objects.errors import InternalCompileException
from wewcompiler.utils.emitterclass import Emitter, emits


class Desugarer(Emitter):

    @staticmethod
    def default(_ctx, instr):
        yield instr

    @classmethod
    def desugar(cls, obj: StatementObject):
        """Desugars code for an object in place."""
        obj.context.code[:] = chain.from_iterable(
            cls.method_for(ir)(obj.context, ir)
            for ir in obj.context.code
        )


class DesugarIR_Post(Desugarer):
    """Desugarer for the IR, Performed post-allocation."""

    @classmethod
    def desugar_instr(cls, ctx: CompileContext, instr: ir_object.IRObject) -> Iterable[ir_object.IRObject]:
        """Desugars an ir object"""
        name = type(instr).__name__
        if name in cls.emitters:
            yield from cls.emitters[name](ctx, instr)
        else:
            yield instr

    @emits(ir_object.Prelude)
    def emit_prelude(cls, ctx: CompileContext, pre: ir_object.Prelude):  # pylint: disable=unused-argument
        # vm enters function with base pointer and stack pointer equal
        yield ir_object.Binary.add(encoder.SpecificRegisters.stk, ir_object.Immediate(pre.scope.size, 8))
        for reg in pre.scope.used_hw_regs:
            yield ir_object.Push(ir_object.AllocatedRegister(8, False, reg))

    @emits(ir_object.Epilog)
    def emit_epilog(cls, ctx: CompileContext, epi: ir_object.Epilog):  # pylint: disable=unused-argument
        for reg in reversed(epi.scope.used_hw_regs):
            yield ir_object.Pop(ir_object.AllocatedRegister(8, False, reg))
        yield ir_object.Binary.sub(encoder.SpecificRegisters.stk, ir_object.Immediate(epi.scope.size, 8))


class DesugarIR_Pre(Desugarer):
    """Desugarer for the IR, Performed pre-allocation

    Operations such as LoadVar/ SaveVar are desugared into Mov instructions.
    """

    @emits(ir_object.LoadVar)
    def emit_loadvar(cls, ctx: CompileContext, load: ir_object.LoadVar):  # pylint: disable=unused-argument
        var = load.variable

        if var.lvalue_is_rvalue and load.lvalue:
            raise InternalCompileException(f"Variable: {var} is marked that it's rvalue "
                                           "is it's lvalue and a lvalue load was requested.")

        # we need an extra register to store the temporary address
        temp_reg = ctx.get_register(2)

        if var.stack_offset is not None:  # load from a stack address
            yield ir_object.Mov(temp_reg, encoder.SpecificRegisters.bas)  # grab base pointer
            # load offset off of the base pointer
            if var.stack_offset < 0:
                instr = ir_object.Binary.sub
            else:
                instr = ir_object.Binary.add
            yield instr(temp_reg, ir_object.Immediate(abs(var.stack_offset), temp_reg.size))
        elif var.global_offset is not None:
            yield ir_object.Mov(temp_reg, var.global_offset)
        else:
            raise InternalCompileException(f"Variable had no stack or global offset: {var}")

        if var.lvalue_is_rvalue or load.lvalue:
            yield ir_object.Mov(load.to, temp_reg)
        else:
            yield ir_object.Mov(load.to, ir_object.Dereference(temp_reg, load.to.size))

    @emits(ir_object.SaveVar)
    def emit_savevar(cls, ctx: CompileContext, save: ir_object.SaveVar):
        var = save.variable

        # we need an extra register to store the temporary address
        temp_reg = ctx.get_register(2)

        if var.stack_offset is not None:  # load from a stack address
            yield ir_object.Mov(temp_reg, encoder.SpecificRegisters.bas)  # grab base pointer
            # load offset off of the base pointer
            if var.stack_offset < 0:
                instr = ir_object.Binary.sub
            else:
                instr = ir_object.Binary.add
            yield instr(temp_reg, ir_object.Immediate(abs(var.stack_offset), temp_reg.size))
        elif var.global_offset is not None:
            yield ir_object.Mov(temp_reg, var.global_offset)
        else:
            raise InternalCompileException(f"Variable had no stack or global offset: {var}")

        # emit the dereference and store
        yield ir_object.Mov(ir_object.Dereference(temp_reg, save.from_.size), save.from_)

    @emits(ir_object.Call)
    def emit_call(cls, ctx: CompileContext, call: ir_object.Call):  # pylint: disable=unused-argument
        for i in reversed(call.args):
            yield ir_object.Push(i)
        # retain the call here, but we dont care about the arguments because they've been pushed
        yield call
