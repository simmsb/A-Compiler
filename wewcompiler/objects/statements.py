from typing import Optional, Union

from tatsu.ast import AST

from wewcompiler.objects.base import (CompileContext, ExpressionObject,
                                      Scope, StatementObject,
                                      with_ctx)
from wewcompiler.objects.ir_object import (Binary, Dereference,
                                           Immediate, Jump, JumpTarget, LoadVar,
                                           Mov, Register, Resize, Return, SaveVar,
                                           Compare, SetCmp, CompType, Epilog)
from wewcompiler.objects.literals import ArrayLiteral
from wewcompiler.objects.types import Pointer, Type, Array, Function


class VariableDecl(StatementObject):

    def __init__(self, name: str, type: Type, val: Optional[ExpressionObject]=None, ast: Optional[AST]=None):
        super().__init__(ast)
        self.name = name
        self._type = type
        self.val = val

    @property
    async def type(self) -> Type:
        if self._type is None or self._type == "infer":
            if self.val is None:
                raise self.error(f"Variable {self.name} has no initialiser or type.")
            self._type = await self.val.type
        return self._type

    @property
    def identifier(self) -> str:
        return self.name

    @with_ctx
    async def compile(self, ctx: CompileContext):
        my_type = await self.type
        if self.val is None:  # just a declaration, no types so exit here
            ctx.declare_variable(self.name, my_type)
            return

        if isinstance(self.val, ArrayLiteral) and isinstance(my_type, Array):
            await self.val.insert_type(my_type)
            await self.val.check_types(my_type)

            # copy back the type of the literal to retrieve the size info
            my_type = await self.val.type

            # setup storage location for the array
            var = ctx.declare_variable(self.name, my_type)
            var.lvalue_is_rvalue = True
            self.val.var = var

            await self.val.compile(ctx)

        elif isinstance(self.val, ExpressionObject):
            val_type = await self.val.type

            if not val_type.implicitly_casts_to(my_type):
                raise self.error(f"Specified type {my_type} does not match value type {val_type}")

            var = ctx.declare_variable(self.name, my_type)
            reg: Register = await self.val.compile(ctx)
            if reg.size != var.size:
                reg0 = reg.resize(var.size, var.type.signed)
                ctx.emit(Resize(reg, reg0))
                reg = reg0
            ctx.emit(SaveVar(var, reg))



class ReturnStmt(StatementObject):

    def __init__(self, expr: ExpressionObject, ast: Optional[AST]=None):
        super().__init__(ast)
        self.expr = expr

    @with_ctx
    async def compile(self, ctx: CompileContext):
        fn_type: Function = ctx.top_function.type
        expr_type: Type = await self.expr.type

        if not fn_type.returns.implicitly_casts_to(expr_type):
            raise self.error(f"Return type '{expr_type}' cannot be casted to '{fn_type.returns}'.")

        reg = await self.expr.compile(ctx)

        # all scopes but the function scope
        for i in reversed(ctx.scope_stack[1:]):
            ctx.emit(Epilog(i))
        if reg.size != fn_type.returns.size:
            reg0 = reg.resize(fn_type.returns.size, fn_type.returns.signed)
            ctx.emit(Resize(reg, reg0))
            reg = reg0
        ctx.emit(Return(ctx.top_function, reg))


class IFStmt(StatementObject):

    def __init__(self, cond: ExpressionObject, body: Scope, else_: Optional[Scope]=None, ast: Optional[AST]=None):
        super().__init__(ast)
        self.cond = cond
        self.body = body
        self.else_ = else_

    @with_ctx
    async def compile(self, ctx: CompileContext):
        cond: Register = await self.cond.compile(ctx)

        # if we have an else clause we rearrange to jump over that
        # instead of inverting the condition to jump over the truth case
        if self.else_:
            body = self.else_
            else_ = self.body
        else:
            body = self.else_

        end_jmp = JumpTarget()
        else_jmp = end_jmp if self.else_ is None else JumpTarget()
        ctx.emit(Jump(else_jmp, cond))
        await body.compile(ctx)
        if self.else_:  # if there is no else body, else_jmp = end_jmp so no need to emit anything but the end marker.
            ctx.emit(Jump(end_jmp))
            ctx.emit(else_jmp)
            await else_.compile(ctx)
        ctx.emit(end_jmp)


class LoopStmt(StatementObject):

    def __init__(self, cond: ExpressionObject, body: Scope, ast: Optional[AST]=None):
        super().__init__(ast)
        self.cond = cond
        self.body = body

    @with_ctx
    async def compile(self, ctx: CompileContext):
        test_jump = JumpTarget()
        continue_jump = JumpTarget()
        end_jump = JumpTarget()

        # the start of the loop (test the condition)
        ctx.emit(test_jump)
        cond: Register = await self.cond.compile(ctx)  # evaluate condition

        # if nonzero, jump over the jump to the end
        # (Alternatively, test for zero and jump to end if zero, but this is 1 op (Jump), vs 3 (Test, Set, Jump))
        ctx.emit(Jump(continue_jump, cond))
        ctx.emit(Jump(end_jump))
        ctx.emit(continue_jump)
        await self.body.compile(ctx)
        ctx.emit(Jump(test_jump))
        ctx.emit(end_jump)
