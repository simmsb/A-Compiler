from itertools import chain
from typing import Tuple, List

from compiler.backend.rustvm.desugar import DesugarIR
from compiler.backend.rustvm import encoder
from compiler.backend.rustvm.register_allocate import allocate
from compiler.objects.base import FunctionDecl, StatementObject, Compiler
from compiler.objects.errors import InternalCompileException
from compiler.objects import ir_object

def group_fns_toplevel(code: List[StatementObject]) -> Tuple[List[FunctionDecl],
                                                             List[StatementObject]]:
    """Groups toplevel declarations and functions seperately."""
    fns, nfns = [], []

    for i in code:
        (fns if isinstance(i, FunctionDecl) else nfns).append(i)
    return fns, nfns


def allocate_code(compiler: Compiler, reg_count: int=10) -> Tuple[List[FunctionDecl],
                                               List[StatementObject]]:
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


def find_main_index(fns: List[FunctionDecl]) -> int:
    """Find the index of the main function in bytes"""
    index = 0
    for fn in fns:
        if fn.identifier == "main":
            return index
        index += fn.code_size
    raise InternalCompileException("Could not find reference to 'main'.")


def process_toplevel(compiler: Compiler, code: List[StatementObject]) -> List[ir_object.IRObject]:
    """Inserts scope around the toplevel assignment code."""
    return [
        ir_object.Binary.add(encoder.SpecificRegisters.stk, ir_object.Immediate(compiler.spill_size)),
        *chain.from_iterable(i.context.code for i in code),
        ir_object.Binary.sub(encoder.SpecificRegisters.stk, ir_object.Immediate(compiler.spill_size))
    ]


def process_immediates(compiler: Compiler, code: List[StatementObject]):
    for i in chain.from_iterable(i.context.code for i in code):
        for attr in i._touched_regs:
            o = arg = getattr(i, attr)
            if isinstance(arg, ir_object.Dereference):
                arg = arg.to
            if isinstance(arg, ir_object.Register):
                continue
            arg: ir_object.Immediate
            if arg.val.bit_length() > 14:
                # bit length wont fit in an argument, we need to allocate a variable and make this point to it
                var = compiler.add_bytes(arg.val.to_bytes(length=arg.size, byteorder="little"))  # TODO: check this is the correct byteorder
                ref = encoder.MemoryReference(var.global_offset)
                if isinstance(o, ir_object.Dereference):
                    o.to = ref
                else:
                    setattr(i, attr, ref)


def process_code(compiler: Compiler) -> List[encoder.HardWareInstruction]:
    """Process the IR for a program ready to be emitted.

    Steps:
      1. Desugar IR
      2. Allocate registers
      3. Process Immediate values, optionally converting to globals
      4. Flatten data, instructions, insert setup instructions and main jump
      4. Resolve Jump targets, checking for main
      5. Package into :class:`encoder.HardwareInstruction` objects
      """

    for object in compiler.compiled_objects:
        DesugarIR.desugar(object)

    functions, toplevel = allocate_code(compiler)

    toplevel = process_toplevel(compiler, toplevel)

    toplevel_size = sum(i.code_size for i in toplevel)

    code_size = (compiler.allocated_data
                 + sum(i.code_size for i in functions)
                 + toplevel_size)

    main_fn_index = toplevel_size + find_main_index(functions)


    pre_instructions = [
        encoder.HardWareInstruction(encoder.stks, code_size + 5), # leave 5 bytes because I feel like it
    ]

    post_instructions = [
        encoder.HardWareInstruction(encoder.call, [main_fn_index])
    ]

    pre_toplevel_code_offset = sum(i.code_size for i in pre_instructions)
    post_toplevel_code_offset = (pre_toplevel_code_offset
                                 + sum(i.code_size for i in post_instructions))

    # TODO: this code
