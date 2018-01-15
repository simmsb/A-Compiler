from compiler.objects.base import (CompileContext, ExpressionObject,
                                   ObjectRequest, Scope, StatementObject,
                                   StmtCompileType, Variable, with_ctx)
from compiler.objects.ir_object import (Binary, Compare, CompType, Dereference,
                                        Immediate, Jump, JumpTarget, LoadVar,
                                        Mov, Register, Resize, Return, SaveVar)
from compiler.objects.literals import ArrayLiteral
from compiler.objects.types import Pointer, Type
from typing import Coroutine, Optional

from tatsu.ast import AST


class VariableDecl(StatementObject):

    def __init__(self, ast: AST):
        super().__init__(ast)
        self.name = ast.name
        self._type = ast.typ
        self.val: Optional[ExpressionObject] = ast.val

    @property
    async def type(self) -> Coroutine[ObjectRequest, Variable, Type]:
        if self._type == "infer":
            if self.val is None:
                raise self.error(f"Variable {self.name} has no initialiser or type.")
            self._type = await self.val.type
        return self._type

    @property
    def identifier(self) -> str:
        return self.name

    @with_ctx
    async def compile(self, ctx: CompileContext) -> StmtCompileType:
        if isinstance(self.val, ArrayLiteral):
            await self.val.to_array()

        my_type = await self.type
        if self.val is None:
            val_type = my_type
        else:
            val_type = await self.val.type

        if not val_type.implicitly_casts_to(my_type):
            raise self.error(f"Specified type {my_type} does not match value type {val_type}")

        # TODO: but what about M u l t i - d i m e n s i o n a l arrays?
        if isinstance(self.val, ArrayLiteral):

            # if the declared type has no size info, copy it across
            if my_type.length is None:
                my_type.length = val_type.length

            # now check that the sizes are correct
            if my_type.length != val_type.length:
                raise self.error(f"Array literal length {val_type.length} does not match specified type length {my_type.length}")

            # hold off declaring the variable here until we get our length information
            var = ctx.declare_variable(self.name, my_type)

            await self.val.check_types()
            ptr = ctx.get_register(Pointer(my_type.to).size)
            ctx.emit(LoadVar(var, ptr, lvalue=True))
            for i in self.val.exprs:
                res = await i.compile(ctx)
                ctx.emit(Mov(Dereference(ptr), res))
                ctx.emit(Binary.add(ptr, Immediate(
                    my_type.size,
                    Pointer(my_type).size)))

        elif isinstance(self.val, ExpressionObject):
            var = ctx.declare_variable(self.name, my_type)
            reg = await self.val.compile(ctx)
            ctx.emit(SaveVar(var, reg))

        else:
            ctx.declare_variable(self.name, my_type)

        # otherwise just create the variable and do nothing


class ReturnStmt(StatementObject):

    def __init__(self, ast: AST):
        super().__init__(ast)
        self.expr: ExpressionObject = ast.e

    @with_ctx
    async def compile(self, ctx: CompileContext):
        fn_type = ctx.top_function.type
        expr_type: Type = await self.expr.type

        if not fn_type.returns.implicitly_casts_to(expr_type):
            raise self.error(f"Return type '{expr_type}' cannot be casted to '{fn_type.returns}'.")

        reg = await self.expr.compile(ctx)
        for i in reversed(ctx.scope_stack):
            ctx.emit(i.make_epilog())
        if reg.size != fn_type.returns.size:
            reg0 = reg.resize(fn_type.returns.size)
            ctx.emit(Resize(reg, reg0))
            reg = reg0
        ctx.emit(Return(reg))


class IFStmt(StatementObject):

    def __init__(self, ast: AST):
        super().__init__(ast)
        self.cond: ExpressionObject = ast.e
        self.body: Scope = ast.t
        self.else_: Optional[Scope] = ast.f

    @with_ctx
    async def compile(self, ctx: CompileContext) -> StmtCompileType:
        cond: Register = await self.cond.compile(ctx)
        ctx.emit(Compare(cond, Immediate(0, cond.size)))
        end_jmp = JumpTarget()
        else_jmp = end_jmp if self.else_ is None else JumpTarget()
        ctx.emit(Jump(else_jmp, CompType.eq))
        await self.body.compile(ctx)
        if self.else_:  # if there is no else body, else_jmp = end_jmp so no need to emit anything but the end marker.
            ctx.emit(Jump(end_jmp, CompType.uncond))
            ctx.emit(else_jmp)
            await self.else_.compile(ctx)
        ctx.emit(end_jmp)


class LoopStmt(StatementObject):

    def __init__(self, ast: AST):
        super().__init__(ast)
        self.cond: ExpressionObject = ast.e
        self.body: Scope = ast.t

    @with_ctx
    async def compile(self, ctx: CompileContext) -> StmtCompileType:
        test = JumpTarget()
        end = JumpTarget()
        ctx.emit(test)
        cond: Register = await self.cond.compile(ctx)
        ctx.emit(Compare(cond, Immediate(0, cond.size)))
        ctx.emit(Jump(end, CompType.eq))
        await self.body.compile(ctx)
        ctx.emit(Jump(test, CompType.uncond))
        ctx.emit(end)
