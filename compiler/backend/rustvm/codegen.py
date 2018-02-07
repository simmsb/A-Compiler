from typing import List, Tuple

from compiler.objects.base import StatementObject, FunctionDecl, Compiler
from compiler.backend.rustvm.register_allocate import allocate

def group_fns_toplevel(code: List[StatementObject]) -> Tuple[List[StatementObject],
                                                             List[StatementObject]]:
    """Groups toplevel declarations and functions seperately."""

    fns, nfns = [], []

    for i in code:
        (fns if isinstance(i, FunctionDecl) else nfns).append(i)

    return (fns, nfns)


def allocate_code(compiler: Compiler, reg_count: int=10):
    """Allocates registers for toplevel and function level blocks."""

    functions, toplevel = group_fns_toplevel(compiler.compiled_objects)

    toplevel_spill_vars = 0

    for i in toplevel:
        allocator = allocate(i.context.code)
        toplevel_spill_vars = max(toplevel_spill_vars, len(allocator.spilled_registers))

    compiler.add_spill_vars(toplevel_spill_vars)

    for i in functions:
        allocator = allocate(i.context.code)
        i.add_spill_vars(len(allocator.spilled_registers))


