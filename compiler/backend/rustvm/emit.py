from itertools import chain
from typing import Tuple, List, Dict, Union

from compiler.backend.rustvm.desugar import DesugarIR_Pre, DesugarIR_Post
from compiler.backend.rustvm import encoder
from compiler.backend.rustvm.register_allocate import allocate
from compiler.objects.base import FunctionDecl, StatementObject, Compiler
from compiler.objects.variable import Variable, DataReference
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

    return functions, toplevel


def process_toplevel(compiler: Compiler, code: List[StatementObject]) -> List[ir_object.IRObject]:
    """Inserts scope around the toplevel assignment code."""
    return [
        ir_object.Binary.add(encoder.SpecificRegisters.stk, ir_object.Immediate(compiler.spill_size)),
        *chain.from_iterable(i.context.code for i in code),
        ir_object.Binary.sub(encoder.SpecificRegisters.stk, ir_object.Immediate(compiler.spill_size))
    ]


def process_immediates(compiler: Compiler, code: List[StatementObject]):
    """Replaces immediate values that are too large to fit into 14 bits by allocating
    global objects for them and referencing them in the arguments."""
    for i in chain.from_iterable(i.context.code for i in code):
        for attr in i.touched_regs:
            o = arg = getattr(i, attr)
            if isinstance(arg, ir_object.Dereference):
                arg = arg.to
            if isinstance(arg, ir_object.Register):
                continue
            arg: ir_object.Immediate
            if arg.val.bit_length() > 14:
                # bit length wont fit in an argument, we need to allocate a variable and make this point to it
                var = compiler.add_bytes(arg.val.to_bytes(length=arg.size, byteorder="little"))  # TODO: check this is the correct byteorder
                if isinstance(o, ir_object.Dereference):
                    o.to = var.global_offset
                else:
                    setattr(i, attr, var.global_offset)


def package_objects(compiler: Compiler,
                    fns: List[StatementObject],
                    toplevel: List[Union[encoder.HardWareInstruction,
                                         ir_object.IRObject]]) -> Dict[str, int]:
    """Packages objects into the binary, making multiple passes to resolve arguments

    if no substitutions are made in a pass, the data will be scanned for any remaining references.
    although remaining references should be minimal since the IR generator couldn't have worked
    properly for everything but a missing main reference

    :returns: The dict of identifier to byte offset.
    """

    packaged = []
    size = 0
    indexes = {}

    pre_instr = encoder.HardWareInstruction(encoder.stks, [0])
    packaged.append(pre_instr) # this will be filled at the end of allocating sizes
    size += pre_instr.size

    # do a single pass to place everything in the output table
    for (ident, index) in compiler.identifiers.copy().items():

        obj = compiler.data[index]
        indexes[ident] = size

        if isinstance(obj, bytes):
            size += len(obj)

        elif isinstance(obj, list):
            size += len(obj) * 2  # Variables become pointers

        packaged.append(obj)

    indexes["toplevel"] = size

    # add in startup code
    for i in toplevel:
        size += instr.size
        if isinstance(i, encoder.HardWareInstruction):
            for position, arg in enumerate(i.args):
                if isinstance(arg, ir_object.DataReference) and arg.name in indexes:
                    i.args[position] = encoder.HardwareMemoryLocation(indexes[arg.name])


    # add in code
    for i in fns:
        pass

    while True:
        replaced = False  # CLEANUP: factor out state variables maybe?
        for (ident, index) in compiler.identifiers.copy().items():

            obj = compiler.data[index]
            if ident not in indexes:
                indexes[ident] = size

                if isinstance(obj, bytes):
                    size += len(obj)
                    packaged.append(obj)

            if isinstance(obj, list):
                # process each item and if we have allocated the variable, replace with an index
                replacement = []  # CLEANUP: Nicer loop here maybe
                for elem in obj:
                    if isinstance(elem, Variable) and elem.name in indexes:
                        replaced = True
                        replacement.append(indexes[elem.name])
                    else:
                        replacement.append(elem)
                compiler.data[index] = replacement
        # TODO: workon this

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
        DesugarIR_Pre.desugar(object)

    functions, toplevel = allocate_code(compiler)

    toplevel = process_toplevel(compiler, toplevel)

    for object in (*functions, *toplevel):
        DesugarIR_Post.desugar(object)

    post_instructions = [
        encoder.HardWareInstruction(encoder.call, [DataReference("main")])
    ]


    # TODO: this code
