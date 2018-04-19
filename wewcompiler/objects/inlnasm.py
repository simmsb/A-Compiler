from typing import List, Optional
from enum import Enum, auto

from tatsu.ast import AST
from dataclasses import dataclass

from wewcompiler.objects.base import (CompileContext, StatementObject, with_ctx,
                                      ExpressionObject)
from wewcompiler.objects.ir_object import (Register, AllocatedRegister,
                                           Dereference, Immediate,
                                           MachineInstr)
from wewcompiler.objects.errors import InternalCompileException


class ASMExprType(Enum):
    index_register = auto()
    int_immediate = auto()
    expr_index = auto()


@dataclass
class ASMExpr:

    __slots__ = ("operation", "val", "deref", "size")

    operation: ASMExprType
    val: int
    deref: bool
    size: int


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
        def p_res(i):
            if i.operation is ASMExprType.index_register:
                r = AllocatedRegister(i.size, i.val)
            elif i.operation is ASMExprType.int_immediate:
                r = Immediate(i.val, i.size)
            elif i.operation is ASMExprType.expr_index:
                if i.val not in range(len(expr_registers)):
                    raise InternalCompileException(f"Missing expression index for asm instruction {i.val}. regs: {expr_registers}")
                r = expr_registers[i.val].copy()  # make sure to copy the register object
            if i.deref:
                r = Dereference(r, i.size)
            return r

        return [p_res(i) for i in self.params]


class ASMStmt(StatementObject):

    __slots__ = ("body", "exprs")

    def __init__(self, body: List[ASMInstruction],
                 exprs: Optional[List[ExpressionObject]] = None,
                 *, ast: Optional[AST] = None):
        super().__init__(ast=ast)
        self.body = body
        self.exprs = exprs or ()

    @with_ctx
    async def compile(self, ctx: CompileContext):
        registers = [await i.compile(ctx) for i in self.exprs]
        for i in self.body:
            params = i.resolve_params(registers)
            ctx.emit(MachineInstr(i.name, i.size, params))
