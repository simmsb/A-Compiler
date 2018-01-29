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

    def allocate_register(self, v_reg: Register) -> int:
        if v_reg in self.register_states:
            state, data = self.register_states[v_reg]
            if state is RegisterState.Allocated:
                return data

        if self.usable_registers:
            # best case, there is a register free to use.
            reg = self.usable_registers.pop()
            self.register_states[v_reg] = (RegisterState.Allocated, reg)
            self.allocated_registers[reg] = v_reg
            return reg


def allocate(reg_count: int, code: Iterable[ir_object.IRObject]):
    """Allocate registers for an ∞ register IR."""

    state = AllocationState(reg_count)


