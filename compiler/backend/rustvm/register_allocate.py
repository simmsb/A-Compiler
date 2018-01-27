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


def allocate(reg_count: int, code: Iterable[ir_object.IRObject]):
    """Allocate registers for an ∞ register IR."""

    #: the states of virtual registers, dict of Registers to Tuples of state and data
    register_states: Dict[Register, Tuple[RegisterState, Any]] = {}

    #: list of extra memory places that are used to hold spilled registers
    spilled_registers: List[Optional[Register]] = []

    #: the stack of allocated registers, contains tuples of (real register, virtual register)
    allocated_registers: List[Tuple[int, Register]] = {}
