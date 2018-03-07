from compiler.backend.rustvm import encoder
from compiler.objects import ir_object
from compiler.objects.variable import DataReference
from compiler.objects.base import StatementObject, CompileContext
from compiler.objects.errors import InternalCompileException
from compiler.utils.emitterclass import Emitter, emits


class Desugarer(metaclass=Emitter):

    @classmethod
    def desugar(cls, obj: StatementObject):
        """Desugars code for an object in place."""
        code = obj.ctx.code
        desugared = []

        for ir in code:
            if ir.__name__ in cls.emitters:
                desugared.extend(cls.emitters[ir.__name__](obj.ctx, ir))
            else:
                desugared.append(ir)
        obj.ctx.code[:] = desugared


class DesugarIR_Post(Desugarer):
    """Desugarer for the IR, Performed post-allocation."""

    @classmethod
    def desugar_instr(cls, ctx: CompileContext, instr: ir_object.IRObject):
        """Desugars an ir object"""
        if instr.__name__ in cls.emitters:
            return cls.emitters[instr.__name__](ctx, instr)
        return instr

    @classmethod
    def desugar(cls, obj: StatementObject):
        """Desugars code for an object in place."""
        code = obj.ctx.code
        obj.ctx.code = [cls.desugar_instr(obj.ctx, i) for i in code]

    @emits("Prelude")
    def emit_prelude(cls, ctx: CompileContext, pre: ir_object.Prelude):  # pylint: disable=unused-argument
        # vm enters function with base pointer and stack pointer equal
        for reg in pre.scope.regsaves:
            yield ir_object.push(ir_object.allocatedregister(8, reg))
        yield ir_object.Binary.add(encoder.SpecificRegisters.stk, ir_object.Immediate(pre.scope.size, 8))

    @emits("Epilog")
    def emit_epilog(cls, ctx: CompileContext, epi: ir_object.Epilog):  # pylint: disable=unused-argument
        for reg in reversed(epi.scope.regsaves):
            yield ir_object.Pop(ir_object.allocatedregister(8, reg))
        yield ir_object.Binary.sub(encoder.SpecificRegisters.stk, ir_object.Immediate(epi.scope.size, 8))


class DesugarIR_Pre(Desugarer):
    """Desugarer for the IR, Performed pre-allocation

    Operations such as LoadVar/ SaveVar are desugared into Mov instructions.
    """

    @emits("LoadVar")
    def emit_loadvar(cls, ctx: CompileContext, load: ir_object.LoadVar):  # pylint: disable=unused-argument
        var = load.variable
        dest = load.to
        if var.stack_offset is not None:  # load from a stack address
            yield ir_object.Mov(dest, encoder.SpecificRegisters.bas)  # grab base pointer
            # load offset off of the base pointer
            yield ir_object.Binary.add(dest, ir_object.Immediate(var.stack_offset))
        elif var.global_offset is not None:
            yield ir_object.Mov(dest, DataReference(var.identifier))
        else:
            raise InternalCompileException(f"Variable had no stack or global offset: {var}")

        if not load.lvalue:  # dereference if not lvalue load, otherwise load the memory location
            yield ir_object.Mov(dest, ir_object.Dereference(dest))

    @emits("SaveVar")
    def emit_savevar(cls, ctx: CompileContext, save: ir_object.SaveVar):
        var = save.variable

        # we need an extra register to store the temporary address
        reg = ctx.get_register(var.size)

        if var.stack_offset is not None:  # load from a stack address
            yield ir_object.Mov(reg, encoder.SpecificRegisters.bas)  # grab base pointer
            # load offset off of the base pointer
            yield ir_object.Binary.add(reg, encoder.Immediate(var.stack_offset))
        elif var.global_offset is not None:
            yield ir_object.Mov(reg, DataReference(var.global_offset))
        else:
            raise InternalCompileException(f"Variable had no stack or global offset: {var}")

        # emit the dereference and store
        yield ir_object.Mov(ir_object.Dereference(reg), save.from_)

    @emits("Call")
    def emit_call(cls, ctx: CompileContext, call: ir_object.Call):  # pylint: disable=unused-argument
        for i in call.args:
            yield ir_object.Push(i)
        # retain the call here, but we dont care about the arguments because they've been pushed
        yield call
