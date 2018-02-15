from enum import Enum, auto
from typing import Any, Dict, List, Optional, Sequence, Tuple

from compiler.objects import ir_object
from compiler.objects.ir_object import Register


class RegisterState(Enum):
    """The state of a virtual register."""

    #: allocated to a real register
    Allocated = auto()

    #: register is now inactive
    Empty = auto()

    #: register is saved to memory
    Spilled = auto()


class AllocationState:
    def __init__(self, reg_count: int):
        self.reg_count = reg_count
        self.usable_registers = set(range(reg_count))

        #: the states of virtual registers, dict of Registers to Tuples of state and data
        self.register_states: Dict[Register, Tuple[RegisterState, Any]] = {}

        #: list of extra memory places that are used to hold spilled registers
        self.spilled_registers: List[Optional[Register]] = []

        #: the stack of allocated registers, k:v of real register to virtual register
        self.allocated_registers: Dict[int, Register] = {}

    def emit_spill(self, v_reg: Register, reg: int):
        """Emit a spill for a register.
        :returns: The IR instruction to spill."""
        if None in self.spilled_registers:
            index = self.spilled_registers.index(None)
        else:
            index = len(self.spilled_registers)
            self.spilled_registers.append(None)
        self.spilled_registers[index] = v_reg
        self.register_states[v_reg] = (RegisterState.Spilled, index)
        return ir_object.Spill(reg, index)

    def emit_load(self, v_reg: Register, reg: int):
        """Emit a load for a spilled register.
        :returns: The IR instruction to load."""
        index = self.spilled_registers.index(v_reg)
        self.spilled_registers[index] = None
        self.register_states[v_reg] = (RegisterState.Allocated, reg)
        return ir_object.Load(reg, index)

    def free_register(self, v_reg: Register):
        state, data = self.register_states[v_reg]
        self.register_states[v_reg] = (RegisterState.Empty, None)
        if state is RegisterState.Allocated:
            del self.allocated_registers[data]
            self.usable_registers.add(data)
        elif state is RegisterState.Spilled:
            index = self.spilled_registers.index(v_reg)
            self.spilled_registers[index] = None
        else:
            raise Exception("Tried to free a dead register")

    def least_active_register(self, exclude: List[int]):
        """Return the current least active register.

        :param exclude: List of registers to not consider inactive at all."""
        # TODO: a better algorithm
        return set(range(self.reg_count)).difference(exclude).pop()

    def allocate_register(self, v_reg: Register,
                          source: ir_object.IRObject,
                          excludes: List[int]) -> int:
        """Allocate a register. If it is already allocated this is a noop."""
        if v_reg in self.register_states:
            state, data = self.register_states[v_reg]
            if state is RegisterState.Allocated:
                return data
            if state is RegisterState.Spilled:
                #  we need to recover the register, find a register to load,
                #  If all registers are taken: emit spill before load instruction
                if self.usable_registers:
                    register = self.usable_registers.pop()
                else:
                    register = self.least_active_register(excludes)
                    spilled_virtual = self.allocated_registers[register]
                    source.insert_pre_instrs(self.emit_spill(spilled_virtual, register))

                self.allocated_registers[register] = v_reg
                source.insert_pre_instrs(self.emit_load(v_reg, register))
                return register
            raise Exception(f"Register {v_reg} is marked dead but wants to be allocated.")

        if self.usable_registers:
            # best case, there is a register free to use.
            reg = self.usable_registers.pop()
            self.register_states[v_reg] = (RegisterState.Allocated, reg)
            self.allocated_registers[reg] = v_reg
            return reg

        register = self.least_active_register(excludes)
        spilled_virtual = self.allocated_registers[register]
        source.insert_pre_instrs(self.emit_spill(spilled_virtual, register))
        self.register_states[v_reg] = (RegisterState.Allocated, register)
        self.allocated_registers[register] = v_reg
        return register


def mark_last_usages(code: Sequence[ir_object.IRObject]):
    """Scans backwards over instructions, marking registers when they are last used."""
    spotted_registers = set()
    for instr in reversed(code):
        for v_reg in instr.touched_registers:
            if v_reg not in spotted_registers:
                instr.closing_registers.add(v_reg)
                spotted_registers.add(v_reg)


def allocate(reg_count: int, code: Sequence[ir_object.IRObject]) -> AllocationState:
    """Allocate registers for an ∞ register IR.
    returns the allocation state to be used in further processing.
    """

    state = AllocationState(reg_count)

    mark_last_usages(code)

    for i in code:
        regs_for_instruction = []
        i.clone_regs()
        for v_reg in i.touched_registers:
            assert v_reg.physical_register is None

            reg = state.allocate_register(v_reg, i, regs_for_instruction)
            assert reg is not None

            regs_for_instruction.append(reg)
            v_reg.physical_register = reg
        for v_reg in i.closing_registers:
            state.free_register(v_reg)

    return state
