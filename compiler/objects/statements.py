from typing import Optional, Union

from tatsu.ast import AST

from compiler.objects.base import (CompileContext, ExpressionObject,
                                   Scope, StatementObject,
                                   with_ctx)
from compiler.objects.ir_object import (Binary, Dereference,
                                        Immediate, Jump, JumpTarget, LoadVar,
                                        Mov, Register, Resize, Return, SaveVar,
                                        Compare, SetCmp, CompType, Epilog)
from compiler.objects.literals import ArrayLiteral
from compiler.objects.types import Pointer, Type, Array, Function


class VariableDecl(StatementObject):

    def __init__(self, name: str, type: Type, val: Optional[ExpressionObject]=None, ast: Optional[AST]=None=None):
        super().__init__(ast)
        self.name = name
        self._type = type
        self.val = val

    @property
    async def type(self) -> Type:
        if self._type == "infer":
            if self.val is None:
                raise self.error(f"Variable {self.name} has no initialiser or type.")
            self._type = await self.val.type
        return self._type

    @property
    def identifier(self) -> str:
        return self.name

    @with_ctx
    async def compile(self, ctx: CompileContext):
        if isinstance(self.val, ArrayLiteral) and isinstance(self._type, Array):
            # convert the array literal from pointer type to array type we have been declared as an array
            await self.val.to_array()

        my_type: Union[Pointer, Array] = await self.type
        if self.val is None:  # just a declaration, no initialiser so exit here
            ctx.declare_variable(self.name, my_type)
        else:
            val_type = await self.val.type

        if not val_type.implicitly_casts_to(my_type):
            raise self.error(f"Specified type {my_type} does not match value type {val_type}")

        if isinstance(self.val, ArrayLiteral) and isinstance(my_type, Array):

            # if the declared type has no size info, copy it across
            if my_type.length is None:
                my_type.length = val_type.length

            # now check that the sizes are correct
            if my_type.length != val_type.length:
                raise self.error(f"Array literal length {val_type.length} does "
                                 f"not match specified type length {my_type.length}")

            # we hold off declaring the variable here until we get our length information
            var = ctx.declare_variable(self.name, my_type)
            var.lvalue_is_rvalue = True  # we are an array, references to this identifer will get the stack position


            # as we are an array type we need to descend into our type
            # to find when we should stop building the multi-dimensional array
            #
            # IE: if our type is [[u8]] then we should expand {{1, 2, 3}, {1, 2, 3}} into {1, 2, 3, 1, 2, 3}
            # but if we have [*u8] then we should only be {ptr0, ptr1} but then ptr0 and ptr1 should be build aswell
            # to do this we find our size, declare a variable of that and then just go through our items and ask for
            # an array to be build for a type

            await self.val.check_types()
            ptr = ctx.get_register(Pointer(my_type.to).size)
            ctx.emit(LoadVar(var, ptr))  # load start of the array

            # this builds the array and writes each element
            await self.val.build_to_type(ctx, my_type, ptr)


        elif isinstance(self.val, ExpressionObject):
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
        self.expr: expr

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
