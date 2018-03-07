from itertools import chain
from typing import Tuple, List, Dict, Union, Optional, Iterable, Any

from compiler.backend.rustvm.desugar import DesugarIR_Pre, DesugarIR_Post
from compiler.backend.rustvm import encoder
from compiler.backend.rustvm.register_allocate import allocate, Spill, Load
from compiler.objects.base import FunctionDecl, StatementObject, Compiler, CompileContext
from compiler.objects.astnode import BaseObject
from compiler.objects.errors import InternalCompileException
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
        allocator = allocate(reg_count, i.code)
        toplevel_spill_vars = max(toplevel_spill_vars, len(allocator.spilled_registers))

    compiler.add_spill_vars(toplevel_spill_vars)

    for i in functions:
        allocator = allocate(reg_count, i.code)
        i.add_spill_vars(len(allocator.spilled_registers))

    return functions, toplevel


def process_toplevel(compiler: Compiler, code: List[StatementObject]) -> List[ir_object.IRObject]:
    """Inserts scope around the toplevel assignment code."""
    return [
        ir_object.Binary.add(encoder.SpecificRegisters.stk, ir_object.Immediate(compiler.spill_size)),
        *chain.from_iterable(i.code for i in code),
        ir_object.Binary.sub(encoder.SpecificRegisters.stk, ir_object.Immediate(compiler.spill_size))
    ]


def process_immediates(compiler: Compiler, code: List[StatementObject]):
    """Replaces immediate values that are too large to fit into 14 bits by allocating
    global objects for them and referencing them in the arguments."""
    for i in chain.from_iterable(i.code for i in code):
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


def process_instruction(indexes: Dict[str, int],
                        size: int,
                        instr: Union[encoder.HardWareInstruction, ir_object.JumpTarget]) -> Optional[encoder.HardWareInstruction]:
    """Process an instruction for packaging.

    :returns: The instruction processed. Jump targets return None."""
    if isinstance(instr, encoder.HardWareInstruction):
        return instr.size

    elif isinstance(instr, ir_object.JumpTarget):
        indexes[instr.identifier] = size
        return 0

    raise InternalCompileException("Content of code that was not a hardware instruction or jump point")


InstrOrTarget = Union[encoder.HardWareInstruction, ir_object.JumpTarget]


def package_objects(compiler: Compiler,
                    fns: Iterable[Tuple[str, InstrOrTarget]],
                    toplevel: Iterable[InstrOrTarget]) -> Tuple[Dict[str, int], Any]:  # TODO: add correct type to this
    """Packages objects into the binary, making multiple passes to resolve arguments

    All IR instructions should have been moved into HardWareInstructions by this point.

    If no substitutions are made in a pass, the data will be scanned for any remaining references.
    although remaining references should be minimal since the IR generator couldn't have worked
    properly for everything but a missing main reference

    :returns: The dict of identifier to byte offset and the packaged objects.
    """

    packaged = []
    size = 0
    indexes = {}  # CLEANUP: factor out state variables maybe?

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
        instr = process_instruction(indexes, size, i)
        if instr:
            size += instr.size
            packaged.append(instr)


    # add in code
    for (name, code) in fns:
        indexes[name] = size
        for i in code:
            instr = process_instruction(indexes, size, i)
            if instr:
                size += instr.size
                packaged.append(instr)


    # begin replacing identifiers
    while True:  # pylint: disable=too-many-nested-blocks;  no go away they're not that bad
        # did we replace any references
        replaced = False

        # did we visit any references
        visited = False

        # If we visited some nodes but made no replacements,
        # we cannot make any replacements in the future and so must fail
        #
        # If we made some replacements then we should make another pass
        # (OPTIMISATION: maybe take note if we replaced all the references and can exit without checking)

        for obj in packaged:

            if isinstance(obj, encoder.HardWareInstruction):
                for position, arg in enumerate(instr.args):
                    # resolve data reference
                    if isinstance(arg, ir_object.DataReference):
                        visited = True
                        if arg.name in indexes:  # replace reference to actual location
                            replaced = True
                            instr.args[position] = encoder.HardwareMemoryLocation(indexes[arg.name])

                    # resolve jump target
                    if isinstance(arg, ir_object.JumpTarget):
                        visited = True
                        if arg.identifier in indexes:
                            replaced = True
                            instr.args[position] = encoder.HardwareMemoryLocation(indexes[arg.identifier])

            if isinstance(obj, list):
                replacement = []
                for elem in obj:
                    if isinstance(elem, Variable):
                        visited = True
                        if elem.name in indexes:
                            replaced = True
                            replacement.append(indexes[elem.name])
                    else:
                        replacement.append(elem)
                obj[:] = replacement

        if visited and not replaced:
            # FEATURE: keep track of what we're missing and display it
            raise InternalCompileException("Failed to resolve references!")

        if not replaced:
            break

    return indexes


def insert_register_stores(fn: FunctionDecl):
    """Insert register stores to preserve registers used inside this function.

    Inserts extra variables into the function body and inserts stores/ loads before and after the function code.
    """

    # scan through the function and collect used registers
    touched_regs = set()

    for i in fn.code:
        touched_regs.update(
            {reg.physical_register for reg in i.touched_registers}
        )

    # Add vars here but dont actually insert instructions to save/restore
    # instead this will happen when prelude/ epilog are desugared
    for i in touched_regs:
        fn.add_reg_save_var(i)

    # pre_instructions = [
    #     ir_object.SaveVar(var, ir_object.AllocatedRegister(reg))
    #     for (reg, var) in vars
    # ]

    # post_instructions = [
    #     ir_object.LoadVar(var, ir_object.AllocatedRegister(reg))
    #     for (reg, var) in vars
    # ]

    # fn.code[:] = pre_instructions + fn.code + post_instructions


def process_spill(ctx: CompileContext, instr: Union[Spill, Load]) -> ir_object.IRObject:
    """Process spill instructions, emits LoadVar and SaveVar
    instructions so these need to be passed through the second stage desugar beforehand.
    """
    if isinstance(instr, Spill):
        ctor = ir_object.LoadVar
    else:
        ctor = ir_object.SaveVar

    var = ctx.vars[f"spill-var-{instr.index}"]
    return ctor(
        var,
        ir_object.AllocatedRegister(
            8, False, instr.reg,
        )
    )


def extract_spill_process(obj: BaseObject):
    """Extract the spill instructions for a context.
    the code body of the context is edited in place.
    """

    replacement = []
    for c in obj.context.code:
        spills = (process_spill(obj.context, i) for i in c.pre_instructions)
        replacement.extend(spills)
        replacement.append(c)
    obj.context.code[:] = replacement


def encode_instructions(instrs: List[ir_object.IRObject]) -> Iterable[encoder.HardWareInstruction]:
    """Encode a list of ir_object instructions into hardware instructions."""
    return chain.from_iterable(map(encoder.InstructionEncoder.encode_instr, instrs))

def process_code(compiler: Compiler) -> Tuple[Dict[str, int], Any]:
    """Process the IR for a program ready to be emitted.

    :returns: dictionary mapping identifiers to indexes, and the packaged objects in the order packed.

    Steps:
      1. Desugar IR
      2. Allocate registers
      3. Process Immediate values, optionally converting to globals
      4. Flatten data, instructions, insert setup instructions and main jump
      4. Resolve Jump targets, checking for main
      5. Package into :class:`encoder.HardwareInstruction` objects
      """

    for o in compiler.compiled_objects:
        DesugarIR_Pre.desugar(o)

    functions, toplevel = allocate_code(compiler)

    for fn in functions:
        insert_register_stores(fn)

    # NOTE: This mutates the objects contained in 'functions' and 'toplevel' on the line above
    for o in compiler.compiled_objects:
        extract_spill_process(o)
        DesugarIR_Post.desugar(o)

    toplevel_instructions = process_toplevel(compiler, toplevel)

    encoded_toplevel = encode_instructions(toplevel_instructions)

    encoded_functions = [(i.identifier, encode_instructions(i.code)) for i in functions]

    encoded_toplevel.extend([
        encoder.HardWareInstruction(encoder.call, [DataReference("main")])
    ])

    return package_objects(compiler, encoded_functions, encoded_toplevel)

    # TODO: here
    #
    # 1. decode instructions and fetch out pre_instruction load/spills 🗹
    # 2. transform load/spills into Mov's 🗹
    # 3. !! at some point we need to add register saves/ stores to instructions 🗹
    # 4. package everything  🗹
    # 5. spit it out
    #
