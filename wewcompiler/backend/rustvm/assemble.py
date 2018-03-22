from itertools import chain
from typing import Tuple, List, Dict, Union, Optional, Iterable, Any

from wewcompiler.backend.rustvm.desugar import DesugarIR_Pre, DesugarIR_Post
from wewcompiler.backend.rustvm import encoder
from wewcompiler.backend.rustvm.register_allocate import allocate, Spill, Load
from wewcompiler.objects.base import FunctionDecl, StatementObject, Compiler, CompileContext, Scope
from wewcompiler.objects.astnode import BaseObject
from wewcompiler.objects.errors import InternalCompileException
from wewcompiler.objects.variable import Variable, DataReference
from wewcompiler.objects import ir_object


def group_fns_toplevel(code: List[StatementObject]) -> Tuple[List[FunctionDecl],
                                                             List[StatementObject]]:
    """Groups toplevel declarations and functions seperately."""
    fns, nfns = [], []

    for i in code:
        (fns if isinstance(i, FunctionDecl) else nfns).append(i)
    return fns, nfns


def allocate_code(compiler: Compiler, reg_count) -> Tuple[List[FunctionDecl],
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
        ir_object.Binary.add(encoder.SpecificRegisters.stk, ir_object.Immediate(compiler.spill_size, 8)),
        *chain.from_iterable(i.code for i in code),
        ir_object.Binary.sub(encoder.SpecificRegisters.stk, ir_object.Immediate(compiler.spill_size, 8))
    ]


def process_immediates(compiler: Compiler, code: List[StatementObject]):
    """Replaces immediate values that are too large to fit into 14 bits by allocating
    global objects for them and referencing them in the arguments."""
    for i in chain.from_iterable(i.code for i in code):
        for attr in i.touched_regs:
            arg = getattr(i, attr)

            # we just assume that dereferences of literals very large just wont happen lol
            # If this is a problem this will have to change into another desugar stage to
            # allow for multiple instructions to be generated
            #
            # HACK ALERT HACK ALERT

            if not isinstance(arg, ir_object.Immediate):
                continue

            # if value more than 14 bits or negative
            if arg.val > 0x3FFF or arg.val < 0:
                # bit length wont fit in an argument, we need to allocate a variable and make this point to it
                signed = arg.val < 0
                var = compiler.add_bytes(arg.val.to_bytes(length=arg.size, byteorder="little", signed=signed))  # TODO: check this is the correct byteorder
                setattr(i, attr, ir_object.Dereference(ir_object.Immediate(var.global_offset, 2), arg.size))


def process_instruction(indexes: Dict[str, int],
                        size: int,
                        instr: Union[encoder.HardWareInstruction, ir_object.JumpTarget]) -> Optional[encoder.HardWareInstruction]:
    """Process an instruction for packaging.

    :returns: The instruction processed. Jump targets return None."""
    if isinstance(instr, encoder.HardWareInstruction):
        return instr

    elif isinstance(instr, ir_object.JumpTarget):
        indexes[instr.identifier] = size
        return None

    raise InternalCompileException("Content of code that was not a hardware instruction or jump point")


InstrOrTarget = Union[encoder.HardWareInstruction, ir_object.JumpTarget]


def package_objects(compiler: Compiler,
                    fns: List[Tuple[str, InstrOrTarget]],
                    toplevel: List[InstrOrTarget]) -> Tuple[Dict[str, int], Any]:  # TODO: add correct type to this
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

    starting_jump = encoder.HardWareInstruction(encoder.Manip.jmp, 2,
                                                (ir_object.Immediate(1, 2),
                                                 ir_object.DataReference("toplevel-code")))

    packaged.append(starting_jump)

    size += starting_jump.code_size

    indexes["program-data"] = size

    # do a single pass to place everything in the output table
    for (ident, index) in compiler.identifiers.copy().items():

        obj = compiler.data[index]
        indexes[ident] = size

        if isinstance(obj, bytes):
            size += len(obj)

        elif isinstance(obj, list):
            size += len(obj) * 2  # Variables become pointers

        packaged.append(obj)

    indexes["toplevel-code"] = size

    pre_instr = encoder.HardWareInstruction(encoder.Mem.stks, 2, (None,))
    packaged.append(pre_instr)  # this will be filled at the end of allocating sizes
    size += pre_instr.code_size

    # add in startup code
    for i in toplevel:
        instr = process_instruction(indexes, size, i)
        if instr:
            size += instr.code_size
            packaged.append(instr)


    # add in code
    for (name, code) in fns:
        indexes[name] = size
        for i in code:
            instr = process_instruction(indexes, size, i)
            if instr:
                size += instr.code_size
                packaged.append(instr)

    # set stack position
    pre_instr.args = (ir_object.Immediate(size + 2, 2),)

    missing = []

    for obj in packaged:
        if isinstance(obj, encoder.HardWareInstruction):
            args = list(obj.args)  # create list from args to allow us to mutate indexes
            for position, arg in enumerate(args):
                # resolve data reference
                # we dont need to process dereferences as they can only be applied to registers or immediates
                if isinstance(arg, ir_object.DataReference):
                    if arg.name in indexes:  # replace reference to actual location
                        args[position] = encoder.HardwareMemoryLocation(indexes[arg.name])
                    else:
                        missing.append(arg.name)

                # resolve jump target
                if isinstance(arg, ir_object.JumpTarget):
                    if arg.identifier in indexes:
                        args[position] = encoder.HardwareMemoryLocation(indexes[arg.identifier])
                    else:
                        missing.append(arg.identifier)
            obj.args = tuple(args)

        if isinstance(obj, list):
            for index, elem in enumerate(obj):
                if isinstance(elem, Variable):
                    if elem.name in indexes:
                        obj[index] = encoder.HardwareMemoryLocation(indexes[elem.name])
                    else:
                        missing.append(elem.name)

    if missing:
        # FEATURE: keep track of what we're missing and display it
        raise InternalCompileException(f"Failed to resolve references: {missing}")

    return indexes, packaged


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

    fn.used_hw_regs = list(touched_regs)


def process_spill(scope: Scope, instr: Union[Spill, Load]) -> Iterable[encoder.HardWareInstruction]:
    """Process spill instructions."""

    # Spill:
    # Push current value
    # load index of location to spill
    # Pop into location
    #
    # Load:
    # load index of location to load
    # dereference into register

    assert isinstance(instr, (Spill, Load))

    reg_s8 = ir_object.AllocatedRegister(8, False, instr.reg)
    reg_s2 = ir_object.AllocatedRegister(2, False, instr.reg)

    if isinstance(instr, Spill):
        yield encoder.HardWareInstruction(
            encoder.Mem.push,
            8,
            (reg_s8,)
        )

    yield encoder.HardWareInstruction(
        encoder.Manip.mov,
        2,
        (reg_s2,
        encoder.SpecificRegisters.bas)
    )

    var = scope.lookup_variable(f"spill-var-{instr.index}")
    assert var is not None

    yield encoder.HardWareInstruction(
        encoder.BinaryInstructions.add,
        2,
        (reg_s2, ir_object.Immediate(var.stack_offset, 2), reg_s2)
    )

    if isinstance(instr, Spill):
        yield encoder.HardWareInstruction(
            encoder.Mem.pop,
            8,
            (ir_object.Dereference(reg_s2, 8),)
        )
    else:
        yield encoder.HardWareInstruction(
            encoder.Manip.mov,
            8,
            (reg_s8, ir_object.Dereference(reg_s2, 8))
        )


def encode_instructions(obj: Scope, instrs: List[ir_object.IRObject]) -> List[encoder.HardWareInstruction]:
    """Encode a list of ir_object instructions into hardware instructions.
    This also pulls out loads and spills from instructions.
    """

    encoded = []

    for i in instrs:
        spills = chain.from_iterable(process_spill(obj, x) for x in i.pre_instructions)
        encoded.extend(spills)
        encoded.extend(encoder.InstructionEncoder.encode_instr(i))

    return encoded


def process_code(compiler: Compiler, reg_count) -> Tuple[Dict[str, int], Any]:
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

    functions, toplevel = allocate_code(compiler, reg_count)

    for fn in functions:
        insert_register_stores(fn)

    # NOTE: This mutates the objects contained in 'functions' and 'toplevel' on the line above
    for o in compiler.compiled_objects:
        DesugarIR_Post.desugar(o)

    process_immediates(compiler, toplevel)
    process_immediates(compiler, functions)

    toplevel_instructions = process_toplevel(compiler, toplevel)

    encoded_toplevel = encode_instructions(compiler, toplevel_instructions)

    encoded_functions = [(i.identifier, encode_instructions(i, i.code)) for i in functions]

    encoded_toplevel.extend([
        encoder.HardWareInstruction(encoder.Mem.call, 2, (DataReference("main"),)),
        encoder.HardWareInstruction(encoder.Manip.halt, 1, ())
    ])

    return package_objects(compiler, encoded_functions, encoded_toplevel)


def assemble_single(obj: Any) -> bytes:
    if isinstance(obj, bytes):
        return obj

    if isinstance(obj, list):
        return b"".join(map(assemble_single, obj))

    if isinstance(obj, encoder.HardwareMemoryLocation):
        return encoder.pack_param(obj.index)

    if isinstance(obj, ir_object.Dereference):
        if isinstance(obj.to, ir_object.Immediate):
            return encoder.pack_param(obj.to.val, deref=True)

        if isinstance(obj.to, (ir_object.Register, ir_object.AllocatedRegister)):
            return encoder.pack_param(obj.to.physical_register + encoder.SpecificRegisters.free_reg_offset, deref=True, reg=True)

    if isinstance(obj, ir_object.Immediate):
        return encoder.pack_param(obj.val)

    if isinstance(obj, (ir_object.Register, ir_object.AllocatedRegister)):
        return encoder.pack_param(obj.physical_register + encoder.SpecificRegisters.free_reg_offset, reg=True)

    if isinstance(obj, encoder.HardwareRegister):
        return encoder.pack_param(obj.index, reg=True)

    if isinstance(obj, int):
        return encoder.pack_param(obj)

    raise InternalCompileException(f"Could not assemble object: {obj} of type: {type(obj)}")


def assemble_instructions(packed_instructions: List[Any]) -> bytearray:
    assembled = bytearray()

    for i in packed_instructions:
        if isinstance(i, encoder.HardWareInstruction):
            assembled.extend(encoder.pack_instruction(i))
            for arg in i.args:
                assembled.extend(assemble_single(arg))
        else:
            assembled.extend(assemble_single(i))

    return assembled
