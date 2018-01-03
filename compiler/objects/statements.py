from compiler.objects.base import (CompileContext, ExpressionObject, Scope,
                                   StatementObject, StmtCompileType, ObjectRequest, Variable)
from compiler.objects.ir_object import (Binary, Dereference, Immediate,
                                        LoadVar, Mov, Register, Resize, Return,
                                        SaveVar, JumpTarget, Compare, CompType, Jump)
from compiler.objects.literals import ArrayLiteral
from compiler.objects.types import Pointer, Type
from typing import Optional, Generator

from tatsu.ast import AST


class VariableDecl(StatementObject):

    def __init__(self, ast: AST):
        super().__init__(ast)
        self.name = ast.name
        self._type = ast.typ
        self.val: Optional[ExpressionObject] = ast.val

        if isinstance(self.val, ArrayLiteral):
            self.val.to_array()

    @property
    def type(self) -> Generator[ObjectRequest, Variable, Type]:
        if self._type == "infer":
            if self.val is None:
                raise self.error(f"Variable {self.name} has no initialiser or type.")
            self._type = (yield from self.val.type)
        return self._type

    @property
    def identifier(self) -> str:
        return self.name

    def compile(self, ctx: CompileContext) -> StmtCompileType:
        var = ctx.declare_variable(self.name, (yield from self.type))
        # TODO: but what about M u l t i - d i m e n s i o n a l arrays?
        if isinstance(self.val, ArrayLiteral):
            ptr = ctx.get_register(Pointer((yield from self.val.type).to).size)
            ctx.emit(LoadVar(var, ptr, lvalue=True))
            for i in self.val.exprs:
                res = yield from i.compile(ctx)
                ctx.emit(Mov(Dereference(ptr), res))
                ctx.emit(Binary.add(ptr, Immediate(
                    (yield from self.type).size,
                    Pointer(var.type).size)))

        if isinstance(self.val, ExpressionObject):
            reg = yield from self.val.compile(ctx)
            ctx.emit(SaveVar(var, reg))
        # otherwise do nothing


class ReturnStmt(StatementObject):

    def __init__(self, ast: AST):
        super().__init__(ast)
        self.expr: ExpressionObject = ast.e

    def compile(self, ctx: CompileContext):
        fn_type = yield from ctx.top_function.type
        reg = yield from self.expr.compile(ctx)
        for i in reversed(ctx.scope_stack):
            ctx.emit(i.make_epilog())
        if reg.size != fn_type.size:
            reg0 = reg.resize(fn_type.size)
            ctx.emit(Resize(reg, reg0))
            reg = reg0
        ctx.emit(Return(reg))


class IFStmt(StatementObject):

    def __init__(self, ast: AST):
        super().__init__(ast)
        self.cond: ExpressionObject = ast.e
        self.body: Scope = ast.t
        self.else_: Optional[Scope] = ast.f

    def compile(self, ctx: CompileContext) -> StmtCompileType:
        cond: Register = (yield from self.cond.compile(ctx))
        ctx.emit(Compare(cond, Immediate(0, cond.size)))
        end_jmp = JumpTarget()
        else_jmp = end_jmp if self.else_ is None else JumpTarget()
        ctx.emit(Jump(else_jmp, CompType.eq))
        yield from self.body.compile(ctx)
        if self.else_:  # if there is no else body, just jump to the end
            ctx.emit(Jump(end_jmp, CompType.uncond))
            ctx.emit(else_jmp)
            yield from self.else_.compile(ctx)
        ctx.emit(end_jmp)


class LoopStmt(StatementObject):

    def __init__(self, ast: AST):
        super().__init__(ast)
        self.cond: ExpressionObject = ast.e
        self.body: Scope = ast.t

    def compile(self, ctx: CompileContext) -> StmtCompileType:
        test = JumpTarget()
        end = JumpTarget()
        ctx.emit(test)
        cond: Register = (yield from self.cond.compile(ctx))
        ctx.emit(Compare(cond, Immediate(0, cond.size)))
        ctx.emit(Jump(end, CompType.eq))
        yield from self.body.compile(ctx)
        ctx.emit(Jump(test, CompType.uncond))
        ctx.emit(end)
