from typing import List, Optional
from enum import Enum, auto

from tatsu.ast import AST
from dataclasses import dataclass, field

from wewcompiler.objects.base import (CompileContext, StatementObject, with_ctx,
                                      ExpressionObject)
from wewcompiler.objects.ir_object import (Register, AllocatedRegister,
                                           Dereference, Immediate, IRParam,
                                           MachineInstr)
from wewcompiler.objects.errors import InternalCompileException


class ASMExprType(Enum):
    index_register = auto()
    int_immediate = auto()
    expr_index = auto()


@dataclass
class ASMExpr:
    operation: ASMExprType
    val: int
    deref: bool
    size: int
    set_val: IRParam = field(default=None, init=False)


def asm_expr_build(index=None,
                   int_imm=None, expr_idx=None,
                   deref=False, size=None, dsize=None):
    deref = deref is not None
    size = int(dsize or size or 0)

    if index is not None:
        return ASMExpr(ASMExprType.index_register, int(index), deref, size)
    if int_imm is not None:
        return ASMExpr(ASMExprType.int_immediate, int(int_imm), deref, size)
    if expr_idx is not None:
        return ASMExpr(ASMExprType.expr_index, int(expr_idx), deref, size)

    raise InternalCompileException("ASM expression without any body?")


@dataclass
class ASMInstruction:
    name: str
    size: int
    params: List[ASMExpr]

    def resolve_params(self, expr_registers: List[Register]):
        for i in self.params:
            if i.operation is ASMExprType.index_register:
                i.set_val = AllocatedRegister(i.size, i.val)
            elif i.operation is ASMExprType.int_immediate:
                i.set_val = Immediate(i.val, i.size)
            elif i.operation is ASMExprType.expr_index:
                if i.val not in range(len(expr_registers)):
                    raise InternalCompileException(f"Missing expression index for asm instruction {i.val}. regs: {expr_registers}")
                i.set_val = expr_registers[i.val].copy()  # make sure to copy the register object
            if i.deref:
                i.set_val = Dereference(i.set_val, i.size)

        return [i.set_val for i in self.params]


class ASMStmt(StatementObject):
    def __init__(self, body: List[ASMInstruction],
                 exprs: Optional[List[ExpressionObject]]=None,
                 *, ast: Optional[AST]=None):
        super().__init__(ast=ast)
        self.body = body
        self.exprs = exprs or ()

    @with_ctx
    async def compile(self, ctx: CompileContext):
        registers = [await i.compile(ctx) for i in self.exprs]
        for i in self.body:
            params = i.resolve_params(registers)
            ctx.emit(MachineInstr(i.name, i.size, params))
