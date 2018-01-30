from enum import Enum, auto
from typing import Iterable, Dict, List, Tuple, Any, Optional

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


class Spilled:
    """Stores to-be resolved spilled register locations."""
    __slots__ = ("v_reg")

    def __init__(self, v_reg: Register):
        self.v_reg = v_reg

class AllocationState:
    def __init__(self, register_count: int):
        self.register_count = register_count
        self.usable_registers = set(range(register_count))

        #: the states of virtual registers, dict of Registers to Tuples of state and data
        self.register_states: Dict[Register, Tuple[RegisterState, Any]] = {}

        #: [x for x in list]st of extra memory places that are used to hold spilled registers
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
        return ir_object.Spill(reg, index)

    def emit_load(self, v_reg: Register, reg: int):
        """Emit a load for a spilled register.
        :returns: The IR instruction to load."""
        index = self.spilled_registers.index(v_reg)
        self.spilled_registers[index] = None
        return ir_object.Load(reg, index)

    def least_active_register(self, exclude: List[int]):
        """Return the current least active register.

        :param exclude: List of registers to not consider inactive at all."""
        # TODO: a better algorithm
        return set(range(self.register_count)).difference(exclude).pop()

    def allocate_register(self, v_reg: Register,
                          source: ir_object.IRObject,
                          excludes: List[int]) -> int:
        """Allocate a register. If it is already allocated this is a noop."""
        if v_reg in self.register_states:
            state, data = self.register_states[v_reg]
            if state is RegisterState.Allocated:
                return data
            if state is RegisterState.Spilled:
                #  we need to recover the register, emit spill and load instructions onto the IR object
                register = self.least_active_register(excludes)
                spilled_virtual = self.allocated_registers[register]
                source.insert_pre_instrs(
                    self.emit_spill(spilled_virtual, register),
                    self.emit_load(v_reg, Register)
                )
                return register

        if self.usable_registers:
            # best case, there is a register free to use.
            reg = self.usable_registers.pop()
            self.register_states[v_reg] = (RegisterState.Allocated, reg)
            self.allocated_registers[reg] = v_reg
            return reg


def allocate(reg_count: int, code: Iterable[ir_object.IRObject]):
    """Allocate registers for an ∞ register IR."""

    state = AllocationState(reg_count)


