from typing import Callable, Dict, Iterator

from compiler.backend.rustvm import encoder
from compiler.objects import ir_object
from compiler.objects.base import StatementObject, CompileContext
from compiler.objects.errors import InternalCompileException


def emits(name: str):
    """Decorator that marks a function for what it will desugar.
    Also marks as a static method.
    """
    def deco(fn):
        fn.emitter_for = name
        return staticmethod(fn)
    return deco


class DesugarIR_Post:
    """Desugarer for the IR, Performed post-allocation."""

    @classmethod
    def get_emitters(cls) -> Dict[str, Callable[[CompileContext, ir_object.IRObject], Iterator[ir_object.IRObject]]]:
        emitters = {}

        for member in dir(cls):
            if hasattr(member, "emitter_for"):
                emitters[member.emitter_for] = member

        return emitters

    @classmethod
    def desugar(cls, obj: StatementObject):
        """Desugars code for an object in place."""
        code = obj.ctx.code
        desugared = []

        emitters = cls.get_emitters()

        for ir in code:
            if ir.__name__ in emitters:
                desugared.extend(emitters[ir.__name__](obj.ctx, ir))
            else:
                desugared.append(ir)
        obj.ctx.code = desugared

    @emits("Prelude")
    def emit_prelude(ctx: CompileContext, pre: ir_object.Prelude):  # pylint: disable=unused-argument
        # vm enters function with base pointer and stack pointer equal
        yield ir_object.Binary.add(encoder.SpecificRegisters.stk, ir_object.Immediate(pre.scope.size, 8))

    @emits("Epilog")
    def emit_epilog(ctx: CompileContext, epi: ir_object.Epilog):  # pylint: disable=unused-argument
        yield ir_object.Binary.sub(encoder.SpecificRegisters.stk, ir_object.Immediate(epi.scope.size, 8))


class DesugarIR_Pre:
    """Desugarer for the IR, Performed pre-allocation

    Operations such as LoadVar/ SaveVar are desugared into Mov instructions.
    """

    @classmethod
    def get_emitters(cls) -> Dict[str, Callable[[CompileContext, ir_object.IRObject], Iterator[ir_object.IRObject]]]:
        emitters = {}

        for member in dir(cls):
            if hasattr(member, "emitter_for"):
                emitters[member.emitter_for] = member

        return emitters

    @classmethod
    def desugar(cls, obj: StatementObject):
        """Desugars code for an object in place."""
        code = obj.ctx.code
        desugared = []

        emitters = cls.get_emitters()

        for ir in code:
            if ir.__name__ in emitters:
                desugared.extend(emitters[ir.__name__](obj.ctx, ir))
            else:
                desugared.append(ir)
        obj.ctx.code = desugared

    @emits("LoadVar")
    def emit_loadvar(ctx: CompileContext, load: ir_object.LoadVar):
        var = load.variable
        dest = load.to
        if var.stack_offset is not None:  # load from a stack address
            yield ir_object.Mov(dest, encoder.SpecificRegisters.bas)  # grab base pointer
            # load offset off of the base pointer
            yield ir_object.Binary.add(dest, ir_object.Immediate(var.stack_offset))
        elif var.global_offset is not None:
            yield ir_object.Mov(dest, ir_object.DataReference(var.identifier))
        else:
            raise InternalCompileException(f"Variable had no stack or global offset: {var}")

        if not load.lvalue:  # dereference if not lvalue load, otherwise load the memory location
            yield ir_object.Mov(dest, ir_object.Dereference(dest))

    @emits("SaveVar")
    def emit_savevar(ctx: CompileContext, save: ir_object.SaveVar):
        var = save.variable

        # we need an extra register to store the temporary address
        reg = ctx.get_register(var.size)

        if var.stack_offset is not None:  # load from a stack address
            yield ir_object.Mov(reg, encoder.SpecificRegisters.bas)  # grab base pointer
            # load offset off of the base pointer
            yield ir_object.Binary.add(reg, encoder.Immediate(var.stack_offset))
        elif var.global_offset is not None:
            yield ir_object.Mov(reg, encoder.DataReference(var.global_offset))
        else:
            # TODO: figure out function references
            raise InternalCompileException(f"Variable had no stack or global offset: {var}")

        # emit the dereference and store
        yield ir_object.Mov(ir_object.Dereference(reg), save.from_)

    @emits("Call")
    def emit_call(ctx: CompileContext, call: ir_object.Call):
        for i in call.args:
            yield ir_object.Push(i)
        # retain the call here, but we dont care about the arguments because they've been pushed
        yield call
