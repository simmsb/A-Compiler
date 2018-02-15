from typing import List, Tuple, Callable, Dict, Iterator

from compiler.backend.rustvm.register_allocate import allocate
from compiler.backend.rustvm import encoder
from compiler.objects import ir_object
from compiler.objects.base import Compiler, FunctionDecl, StatementObject, CompileContext
from compiler.objects.errors import InternalCompileException


def group_fns_toplevel(code: List[StatementObject]) -> Tuple[List[FunctionDecl],
                                                             List[StatementObject]]:
    """Groups toplevel declarations and functions seperately."""
    fns, nfns = [], []

    for i in code:
        (fns if isinstance(i, FunctionDecl) else nfns).append(i)
    return fns, nfns


def allocate_code(compiler: Compiler, reg_count: int=10):
    """Allocates registers for toplevel and function level blocks."""

    functions, toplevel = group_fns_toplevel(compiler.compiled_objects)

    toplevel_spill_vars = 0

    for i in toplevel:
        allocator = allocate(reg_count, i.context.code)
        toplevel_spill_vars = max(toplevel_spill_vars, len(allocator.spilled_registers))

    compiler.add_spill_vars(toplevel_spill_vars)

    for i in functions:
        allocator = allocate(reg_count, i.context.code)
        i.add_spill_vars(len(allocator.spilled_registers))


def emits(name: str):
    """Decorator that marks a function for what it will desugar.
    Also marks as a static method.
    """
    def deco(fn):
        fn.emitter_for = name
        return staticmethod(fn)
    return deco



class Test:
    def __init__(self, a: int, b: str):
        self.a = a
        self.b = b



class DesugarIR:
    """Desugarer for the IR

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
    def desugar(cls, ctx: CompileContext):
        code = ctx.code
        desugared = []

        emitters = cls.get_emitters()

        for ir in code:
            if ir.__name__ in emitters:
                desugared.extend(emitters[ir.__name__](ir))
            else:
                desugared.append(ir)
        return desugared


    @emits("LoadVar")
    def emit_loadvar(ctx: CompileContext, load: ir_object.LoadVar):
        var = load.variable
        dest = load.to
        if var.stack_offset is not None:  # load from a stack address
            yield ir_object.Mov(dest, encoder.SpecificRegisters.bas)  # grab base pointer
            # load offset off of the base pointer
            yield ir_object.Binary.add(dest, ir_object.Immediate(var.stack_offset, var.size))
        elif var.global_offset is not None:
            yield ir_object.Mov(dest, ir_object.Immediate(var.global_offset, var.size))
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
            yield ir_object.Binary.add(reg, ir_object.Immediate(var.stack_offset, var.size))
        elif var.global_offset is not None:
            yield ir_object.Mov(reg, ir_object.Immediate(var.global_offset, var.size))
        else:
            raise InternalCompileException(f"Variable had no stack or global offset: {var}")

        # emit the dereference and store
        yield ir_object.Mov(ir_object.Dereference(reg), save.from_)

    @emits("Prelude")
    def emit_prelude(ctx: CompileContext, pre: ir_object.Prelude):
        # vm enters function with base pointer and stack pointer equal
        yield ir_object.Binary.add(encoder.SpecificRegisters.stk, ir_object.Immediate(pre.scope.size))

    @emits("Epilog")
    def emit_epilog(ctx: CompileContext, epi: ir_object.Epilog):
        yield ir_object.Binary.sub(encoder.SpecificRegisters.stk, ir_object.Immediate(epi.scope.size))

    @emits("Call")
    def emit_call(ctx: CompileContext, call: ir_object.Call):
        for i in call.args:
            yield ir_object.Push(i)
        # retain the call here, but we dont care about the arguments because they've been pushed
        yield call
