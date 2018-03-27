from enum import Enum, auto
from typing import Any, Dict, List, Optional, Sequence, Tuple
from dataclasses import dataclass

from wewcompiler.objects import ir_object
from wewcompiler.objects.errors import InternalCompileException
from wewcompiler.objects.ir_object import Register


@dataclass
class ListView:
    """Provides a read only view into a section of a list."""

    lst: List[Any]
    slc: slice

    @dataclass
    class ListViewBuilderProxy:

        lst: List[Any]

        def __getitem__(self, key):
            return ListView(self.lst, key)

    @classmethod
    def from_list(cls, lst: List[Any]):
        return cls.ListViewBuilderProxy(lst)

    def __getitem__(self, key):
        if not isinstance(key, int):
            raise TypeError("ListView only accepts single indexes")

        step = self.slc.step or 1
        idx = self.slc.start + step * key

        return self.lst[idx]


@dataclass(frozen=True)
class Spill:
    """Spill a register to a location.

    :reg: Physical register to save
    :index: Index of saved registers to save to
    """

    reg: int
    index: int


@dataclass(frozen=True)
class Load:
    """Recover a spilled register.

    :reg: Physical register to load into
    :index: Index of saved registers to load from
    """

    reg: int
    index: int


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
        # We use a list for this so that we can check if it's full
        # (No None's) and to grow we just append a None
        self.spilled_registers: List[Optional[Register]] = []

        #: the stack of allocated registers, k:v of real register to virtual register
        self.allocated_registers: Dict[int, Register] = {}

    def emit_spill(self, v_reg: Register, reg: int):
        """Emit a spill for a register.
        :returns: The IR instruction to spill."""

        # There's an empty spill location, spill to that
        if None in self.spilled_registers:
            index = self.spilled_registers.index(None)
        # All slots to spill to are free, create a new one
        else:
            index = len(self.spilled_registers)
            self.spilled_registers.append(None)
        self.spilled_registers[index] = v_reg
        self.register_states[v_reg] = (RegisterState.Spilled, index)
        return Spill(reg, index)

    def emit_load(self, v_reg: Register, reg: int):
        """Emit a load for a spilled register.
        :returns: The IR instruction to load."""

        # find where this register was spilled to
        index = self.spilled_registers.index(v_reg)

        # mark the spill slot as free
        self.spilled_registers[index] = None
        self.register_states[v_reg] = (RegisterState.Allocated, reg)
        return Load(reg, index)

    def free_register(self, v_reg: Register):
        """Mark a virtual register as unused,
        any further attempts to access it will raise an Exception"""

        # get this register's current state. Because of the structure of the algorithm it's
        # unlikely to be anything but an Allocated state.
        state, data = self.register_states[v_reg]
        self.register_states[v_reg] = (RegisterState.Empty, None)

        # If allocated, delete it from the allocation table and mark it as used
        if state is RegisterState.Allocated:
            del self.allocated_registers[data]
            self.usable_registers.add(data)
        # if spilled, remove it from the array of spilled registers
        elif state is RegisterState.Spilled:
            index = self.spilled_registers.index(v_reg)
            self.spilled_registers[index] = None
        else:
            raise InternalCompileException("Tried to free a dead register")

    def least_active_register(self, exclude: List[int]):
        """Return the current least active register.

        :param exclude: List of registers to not consider inactive at all."""
        # TODO: a better algorithm
        # currently this just gets a random (by chance of program state)
        # register from the active pool
        return (set(range(self.reg_count))
                .difference(exclude)
                .difference(self.usable_registers)
                .pop())

    def allocate_register(self, v_reg: Register,
                          source: ir_object.IRObject,
                          excludes: List[int]) -> int:
        """Allocate a register. If it is already allocated this is a noop."""
        if v_reg in self.register_states:
            state, data = self.register_states[v_reg]
            if state is RegisterState.Allocated:
                # alread allocated: Just return
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
            # we're trying to use this register but we said it was dead earlier
            raise InternalCompileException(f"Register {v_reg} is marked dead but wants to be allocated.")

        # register not in our state table, allocate it for the first time
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

    # by scanning backwards, the first time we see a variable
    # is the last time it's used in the execution order
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

    # update each instruction to mark where registers become unused
    mark_last_usages(code)

    for i in code:
        regs_for_instruction = []

        # clone the registers of the instruction so that each instruction has it's own instance of a command
        i.clone_regs()
        for v_reg in i.touched_registers:
            # bad stuff could happen if the register has already been allocated in this instruction
            # or we're using a shared instance of the register objects
            assert v_reg.physical_register is None

            reg = state.allocate_register(v_reg, i, regs_for_instruction)

            # ensure we got a register (just a sanity check)
            assert reg is not None

            # ensure that this hw-reg isn't swapped out mid-instruction
            regs_for_instruction.append(reg)
            v_reg.physical_register = reg

        # mark the closing registers as free
        # prevents unneeded spills
        for v_reg in i.closing_registers:
            state.free_register(v_reg)

    return state
