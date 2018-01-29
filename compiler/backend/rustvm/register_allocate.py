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

        #: the states of virtual registers, dict of Registers to Tuples of state and data
        self.register_states: Dict[Register, Tuple[RegisterState, Any]] = {}

        #: [x for x in list]st of extra memory places that are used to hold spilled registers
        self.spilled_registers: List[Optional[Register]] = []

        #: the stack of allocated registers, contains tuples of (real register, virtual register)
        self.allocated_registers: List[Tuple[int, Register]] = {}

    def allocate_register(self, reg: Register):
        ...

def find_usable_register(virtual_register: Register, spilled_registers, )


def allocate(reg_count: int, code: Iterable[ir_object.IRObject]):
    """Allocate registers for an ∞ register IR."""

    state = AllocationState(reg_count)


