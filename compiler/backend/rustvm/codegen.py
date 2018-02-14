from typing import List, Tuple

from compiler.backend.rustvm.register_allocate import allocate
from compiler.objects import ir_object
from compiler.objects.base import Compiler, FunctionDecl, StatementObject


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
    def deco(fn):
        fn.emitter_for = name
        return fn
    return deco


class DesugarIR:
    """Desugarer for the IR

    Operations such as LoadVar/ SaveVar are desugared into Mov instructions.
    """

    @emits("LoadVar")
    def emit_loadvar(self, load: ir_object.LoadVar):
        var = load.variable
        dest = load.to
        # TODO: get this working
        if var.stack_offset is not None:  # load from a stack address
            # yield ir_object.Mov(dest )
            ...

