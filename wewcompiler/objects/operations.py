from itertools import zip_longest
from typing import Iterable, Tuple, Union, Optional, List

from tatsu.ast import AST

from wewcompiler.objects import types
from wewcompiler.objects.base import (CompileContext, ExpressionObject, with_ctx)
from wewcompiler.objects.ir_object import (Binary, Call, CompType, Compare, Dereference,
                                           Immediate, Jump, JumpTarget, Mov,
                                           Register, Resize, SetCmp, Unary)


class MemrefOp(ExpressionObject):

    __slots__ = ("expr",)

    def __init__(self, expr: ExpressionObject, *, ast: Optional[AST]=None):
        super().__init__(ast=ast)
        self.expr = expr

    @property
    async def type(self):
        return types.Pointer((await self.expr.type))

    @with_ctx
    async def compile(self, ctx: CompileContext) -> Register:
        return await self.expr.load_lvalue(ctx)


class UnaryOP(ExpressionObject):

    __slots__ = ("op", "expr")

    def __init__(self, op: str, expr: ExpressionObject, *, ast: Optional[AST]=None):
        super().__init__(ast=ast)
        self.op = op
        self.expr = expr

    @property
    async def type(self) -> types.Type:
        return await self.expr.type

    @with_ctx
    async def compile(self, ctx: CompileContext) -> Register:
        reg: Register = (await self.expr.compile(ctx))

        optype: types.Type = await self.type
        if not optype.signed:
            if self.op == "+":
                return reg  # '+' is a noop on unsigned types
            if self.op == "-":
                raise self.error("Unary negate has no meaning on unsigned types.")

        op = {
            "~": "binv",
            "!": "linv",
            "-": "neg",
            "+": "pos"
        }[self.op]

        ctx.emit(Unary(reg, op))
        return reg


class PreincrementOP(ExpressionObject):

    __slots__ = ("op", "expr")

    def __init__(self, op: str, expr: ExpressionObject, *, ast: Optional[AST]=None):
        super().__init__(ast=ast)
        self.op = {"++": "add",
                   "--": "sub"}[op]
        self.expr = expr

    @property
    async def type(self):
        return await self.expr.type

    async def load_lvalue(self, ctx: CompileContext) -> Register:
        return await self.expr.load_lvalue(ctx)

    @with_ctx
    async def compile(self, ctx: CompileContext) -> Register:
        my_type = await self.type

        ptr: Register = await self.load_lvalue(ctx)
        tmp = ctx.get_register(my_type.size, my_type.signed)

        increment = 1
        # in the case of pointer increments, increment by the size of the pointer's underlying type
        if isinstance(my_type, (types.Array, types.Pointer)):
            increment = my_type.to.size

        ctx.emit(Mov(tmp, Dereference(ptr, tmp.size)))
        ctx.emit(Binary(tmp, Immediate(increment, tmp.size), self.op))
        ctx.emit(Mov(Dereference(ptr, tmp.size), tmp))
        return tmp


class DereferenceOP(ExpressionObject):

    __slots__ = ("expr",)

    def __init__(self, expr: ExpressionObject, *, ast: Optional[AST]=None):
        super().__init__(ast=ast)
        self.expr = expr

    @property
    async def type(self):
        ptr: Union[types.Pointer, types.Array] = await self.expr.type
        if not isinstance(ptr, (types.Pointer, types.Array)):
            raise self.error(f"Operand to dereference is of type {ptr}, not of pointer or array type.")

        return ptr.to

    async def load_lvalue(self, ctx: CompileContext) -> Register:
        reg: Register = await self.expr.compile(ctx)
        if reg.size != types.Pointer.size:
            reg0 = reg.resize(types.Pointer.size)
            ctx.emit(Resize(reg, reg0))
            reg = reg0
        return reg

    @with_ctx
    async def compile(self, ctx: CompileContext) -> Register:
        ptr = await self.load_lvalue(ctx)
        my_type = await self.type

        reg = ctx.get_register(my_type.size, my_type.signed)
        ctx.emit(Mov(reg, Dereference(ptr, reg.size)))
        return reg


class CastExprOP(ExpressionObject):

    __slots__ = ("_type", "expr", "op")

    def __init__(self, type: types.Type, expr: ExpressionObject, op: str='::', *, ast: Optional[AST]=None):
        super().__init__(ast=ast)
        self._type = type
        self.expr = expr
        self.op = op

    @property
    async def type(self):
        return self._type

    async def load_lvalue(self, ctx: CompileContext) -> Register:
        # we should allow cast ops to pass the lvalue through
        return await self.expr.load_lvalue(ctx)

    @with_ctx
    async def compile(self, ctx: CompileContext) -> Register:
        reg = await self.expr.compile(ctx)
        my_type = await self.type

        res = reg.resize(my_type.size, my_type.signed)
        if self.op == "::" and reg.size != res.size:
            ctx.emit(Resize(reg, res))  # emit resize operation
        return res


class FunctionCallOp(ExpressionObject):

    __slots__ = ("fun", "args")

    def __init__(self, fun: ExpressionObject, args: List[ExpressionObject], *, ast: Optional[AST]=None):
        super().__init__(ast=ast)
        self.fun = fun
        self.args = args

    @property
    async def type(self):
        typ = await self.fun.type
        if not isinstance(typ, types.Function):
            raise self.error("Called object is not a function.")
        return typ.returns

    @with_ctx
    async def compile(self, ctx: CompileContext) -> Register:

        fun_typ: types.Function = await self.fun.type
        if not isinstance(fun_typ, types.Function):
            raise self.error("Called object is not a function.")

        if fun_typ.varargs:
            invalid_len = len(self.args) < len(fun_typ.args)
        else:
            invalid_len = len(self.args) != len(fun_typ.args)

        if invalid_len:
            raise self.error("Incorrect number of args to function.\n"
                             f"Expected {len(fun_typ.args)} got {len(self.args)}")

        # check that the argument types are valid
        # If this is a varargs function then the extra args wont be typechecked
        arg_types = [(i, (await i.type)) for i in self.args]
        for arg_n, (lhs_type, (rhs_obj, rhs_type)) in enumerate(zip(fun_typ.args, arg_types)):
            if not rhs_type.implicitly_casts_to(lhs_type):
                raise rhs_obj.error(
                    f"Argument {arg_n} to call '{self.fun.identifier}' was of "
                    f"type {rhs_type} instead of expected {lhs_type} and cannot be casted.")

        params = []

        for arg, typ in zip_longest(self.args, fun_typ.args):
            arg_reg = await arg.compile(ctx)

            if typ is not None and arg_reg.size != typ.size:
                arg_reg0 = arg_reg.resize(typ.size, typ.signed)
                ctx.emit(Resize(arg_reg, arg_reg0))
                arg_reg = arg_reg0

            params.append(arg_reg)

        fun: Register = await self.fun.compile(ctx)

        if isinstance(fun_typ.returns, types.Void):
            ctx.emit(Call(params, fun))
        else:
            await self.size
            result_reg = ctx.get_register(fun_typ.returns.size,
                                          fun_typ.returns.signed)
            ctx.emit(Call(params, fun, result_reg))
            return result_reg


class ArrayIndexOp(ExpressionObject):

    __slots__ = ("arg", "offset")

    def __init__(self, arg: ExpressionObject, offset: ExpressionObject, *, ast: Optional[AST]=None):
        super().__init__(ast=ast)
        self.arg = arg
        self.offset = offset

    @property
    async def type(self):
        ptr = await self.arg.type
        if not isinstance(ptr, (types.Pointer, types.Array)):
            raise self.error("Operand to index operator is not of pointer or array type.")
        return ptr.to

    async def load_lvalue(self, ctx: CompileContext) -> Register:
        atype = await self.arg.type

        if not isinstance(atype, (types.Pointer, types.Array)):
            raise self.error(f"Incompatible type to array index base {atype}")

        argument = await self.arg.compile(ctx)
        offset = await self.offset.compile(ctx)


        # get the size of the inner type if type.to is an array,
        # this will be the size of the internal array
        size = await self.size

        # make sure both the offset and the arguments are the correct size (size of a pointer)
        if argument.size != types.Pointer.size:
            argument0 = argument.resize(types.Pointer.size)
            ctx.emit(Resize(argument, argument0))
            argument = argument0


        if offset.size != types.Pointer.size:
            offset0 = offset.resize(types.Pointer.size)
            ctx.emit(Resize(offset, offset0))
            offset = offset0


        result = ctx.get_register(types.Pointer.size)
        # multiply to the size of the inner type of the pointer/ array
        ctx.emit(Binary.mul(offset, Immediate(size, offset.size)))
        ctx.emit(Binary.add(argument, offset, result))

        return result

    @with_ctx
    async def compile(self, ctx: CompileContext) -> Register:
        ptr: Register = await self.load_lvalue(ctx)
        if ptr.size != types.Pointer.size:
            ptr0 = ptr.resize(types.Pointer.size)
            ctx.emit(Resize(ptr, ptr0))
            ptr = ptr0


        # indexes that leave an array type dont dereference
        if isinstance(await self.type, types.Array):
            return ptr

        my_type = await self.type
        res = ctx.get_register(my_type.size, my_type.signed)
        ctx.emit(Mov(res, Dereference(ptr, res.size)))
        return res


class PostIncrementOp(ExpressionObject):

    __slots__ = ("arg", "op")

    def __init__(self, arg: ExpressionObject, op: str, *, ast: Optional[AST]=None):
        super().__init__(ast=ast)
        self.arg = arg
        self.op = {"++": "add",
                   "--": "sub"}[op]

    @property
    async def type(self):
        return await self.arg.type

    @with_ctx
    async def compile(self, ctx: CompileContext) -> Register:
        my_type = await self.type

        ptr: Register = await self.arg.load_lvalue(ctx)
        size = my_type.size
        res, temp = ctx.get_register(size, my_type.signed), ctx.get_register(size)

        increment = 1
        if isinstance(my_type, (types.Array, types.Pointer)):
            increment = my_type.to.size

        ctx.emit(Mov(res, Dereference(ptr, res.size)))
        ctx.emit(Binary(res, Immediate(increment, size), self.op, temp))
        ctx.emit(Mov(Dereference(ptr, temp.size), temp))
        return res


class BinaryExpression(ExpressionObject):

    """Generic binary expression (a `x` b)

    _compat_types is used to typecheck the expression and set the return type of it."""

    __slots__ = ("left", "op", "right", "ret_type", "left_type", "right_type")

    _compat_types: Tuple[Union[Tuple[str], str],
                         Tuple[types.Type, types.Type], types.Type] = ()

    @property
    async def size(self) -> int:
        return max((await self.left.size),
                   (await self.right.size))

    @property
    async def type(self) -> types.Type:
        await self.resolve_types()
        return self.ret_type

    @property
    def sign(self) -> bool:
        """Get the sign of this binary operation.
        Must be called after types are resolved.
        """
        return self.left_type.signed or self.right_type.signed

    def __init__(self, op: str, left: ExpressionObject,
                 right: ExpressionObject, *, ast: Optional[AST]=None):
        super().__init__(ast=ast)
        self.left = left
        self.op = op
        self.right = right
        self.ret_type = None
        self.left_type = None
        self.right_type = None

    @with_ctx
    async def compile(self, ctx: CompileContext) -> Register:
        raise NotImplementedError

    async def resolve_types(self):
        """Resolve types of a binary operation"""
        if self.ret_type is not None:
            return

        op = self.op
        left = self.left_type = await self.left.type
        right = self.right_type = await self.right.type
        # typecheck operands here

        for check_ops, (lhs_typ, rhs_type), result_type in self._compat_types:  # wew lad
            if not isinstance(check_ops, (list, tuple)):  # always an iterable
                check_ops = (check_ops,)
            for check_op in check_ops:
                if isinstance(left, lhs_typ) and isinstance(right, rhs_type) and check_op == op:
                    self.ret_type = result_type
                    break
            else:
                continue
            break
        else:
            raise self.error(
                f"Incompatible types for binary {op}: {left} and {right}")

    @with_ctx
    async def compile_meta(self, ctx: CompileContext) -> Tuple[Register, Register]:
        """Binary expression meta compile, returns registers of both side
        Both registers returned have equal size."""
        await self.resolve_types()  # force type resolution to typecheck

        lhs: Register = await self.left.compile(ctx)
        rhs: Register = await self.right.compile(ctx)

        # resize to the largest operand
        if lhs.size < rhs.size:
            lhs0 = lhs.resize(rhs.size, rhs.sign)
            ctx.emit(Resize(lhs, lhs0))
            lhs = lhs0
        elif rhs.size < lhs.size:
            rhs0 = rhs.resize(lhs.size, lhs.sign)
            ctx.emit(Resize(rhs, rhs0))
            rhs = rhs0

        return lhs, rhs


class BinAddOp(BinaryExpression):

    _compat_types = (  # maybe follow algebraic rules to reduce repetition
        (('+', '-'), (types.Pointer, types.Int), types.Pointer),
        (('+', '-'), (types.Int, types.Pointer), types.Pointer),
        (('+', '-'), (types.Int, types.Int), types.Int),
        ('-', (types.Pointer, types.Pointer), types.Int),
    )

    @property
    async def type(self):
        await self.resolve_types()

        if self.ret_type is types.Pointer:
            ptr_side = (self.left_type
                        if isinstance(self.left_type, (types.Pointer, types.Array))
                        else self.right_type)
            return ptr_side
        return types.Int.fromsize(await self.size, self.sign)

    @with_ctx
    async def compile(self, ctx: CompileContext) -> Register:
        lhs, rhs = (await self.compile_meta(ctx))

        res = ctx.get_register(lhs.size, self.sign)

        op = {"+": "add",
              "-": "sub"}[self.op]

        if isinstance(await self.type, (types.Pointer, types.Array)):
            (ptr_type, non_ptr) = ((self.left_type, rhs)
                                   if isinstance(self.left_type, (types.Pointer, types.Array))
                                   else (self.right_type, lhs))

            ctx.emit(Binary.mul(non_ptr, Immediate(ptr_type.to.size, non_ptr.size)))

        ctx.emit(Binary(lhs, rhs, op, res))
        return res


class BinMulOp(BinaryExpression):
    """Binary multiplicative operation.

    Emits a signed operation of the rhs of a division is signed."""

    _compat_types = (
        (('*', '/', '%'), (types.Int, types.Int), types.Int),
    )

    @property
    async def type(self):
        await self.resolve_types()
        signed = self.left_type.signed or self.right_type.signed
        return types.Int.fromsize(await self.size, signed)

    @with_ctx
    async def compile(self, ctx: CompileContext) -> Register:
        lhs, rhs = await self.compile_meta(ctx)

        res = ctx.get_register(lhs.size, self.sign)

        if self.op == "*":
            op = "mul"
        elif self.op == "%":
            if self.sign:
                op = "imod"
            else:
                op = "umod"
        elif self.op == "/" and self.sign:
            op = "idiv"
        else:
            op = "udiv"

        ctx.emit(Binary(lhs, rhs, op, res))
        return res


class BinShiftOp(BinaryExpression):
    """Binary shift operation.

    Emits a signed operation if shifting left and any side of the expression is signed."""

    _compat_types = (
        (('>>', '<<'), (types.Int, types.Int), types.Int),
    )

    @property
    async def type(self):
        await self.resolve_types()
        if self.op == '>>':
            lhs = self.left_type
            signed = lhs.signed
        else:
            signed = False
        return types.Int.fromsize((await self.size), signed)

    @with_ctx
    async def compile(self, ctx: CompileContext) -> Register:
        lhs, rhs = await self.compile_meta(ctx)
        if rhs.sign:
            raise self.right.error("RHS operand to a binary shift op must be unsigned.")

        res = ctx.get_register(lhs.size, self.sign)

        if self.op == "<<":
            op = "shl"
        elif self.op == ">>" and lhs.sign:
            op = "sar"
        else:
            op = "shr"

        ctx.emit(Binary(lhs, rhs, op, res))
        return res


class BinRelOp(BinaryExpression):
    """Binary relational comparison operation."""

    _compat_types = (
        (('<=', '>=', '<', '>', '==', '!='), (types.Int, types.Int), types.Int),
        (('<=', '>=', '<', '>', '==', '!='), (types.Pointer, types.Pointer), types.Int)
    )

    @property
    async def type(self):
        # always results in 0 or 1 (unsigned 1 byte int)
        return types.Int('u1')

    @with_ctx
    async def compile(self, ctx: CompileContext) -> Register:
        lhs, rhs = await self.compile_meta(ctx)

        # if signed, emit signed comparison
        if self.sign:
            op = {
                '<=': CompType.leqs,
                '<': CompType.lts,
                '==': CompType.eq,
                '!=': CompType.neq,
                '>': CompType.gts,
                '>=': CompType.geqs
            }[self.op]
        else:
            op = {
                '<=': CompType.leq,
                '<': CompType.lt,
                '==': CompType.eq,
                '!=': CompType.neq,
                '>': CompType.gt,
                '>=': CompType.geq
            }[self.op]

        res = ctx.get_register(1)
        ctx.emit(Compare(lhs, rhs))
        ctx.emit(SetCmp(res, op))
        return res


class BitwiseOp(BinaryExpression):
    """Binary bitwise operators."""

    _compat_types = (
        (("|", "^", "&"), (types.Int, types.Int), types.Int),
    )

    @property
    async def type(self):
        await self.resolve_types()
        assert self.ret_type is types.Int
        return self.ret_type.fromsize(await self.size, self.sign)

    @with_ctx
    async def compile(self, ctx: CompileContext) -> Register:
        op = {
            "|": "or",
            "^": "xor",
            "&": "and"
        }[self.op]

        lhs, rhs = await self.compile_meta(ctx)
        res = ctx.get_register(lhs.size, self.sign)
        ctx.emit(Binary(lhs, rhs, op, res))
        return res


class AssignOp(ExpressionObject):
    """Assignment operation."""

    __slots__ = ("left", "right")

    def __init__(self, left: ExpressionObject,
                 right: ExpressionObject, *, ast: Optional[AST]=None):
        super().__init__(ast=ast)
        self.left = left
        self.right = right

    @property
    async def type(self):
        return self.right.type

    @with_ctx
    async def compile(self, ctx: CompileContext) -> Register:
        rhs: Register = (await self.right.compile(ctx))
        lhs: Register = (await self.left.load_lvalue(ctx))

        lhs_type = await self.left.type
        lhs_sign = lhs_type.signed
        lhs_size = lhs_type.size

        if lhs_type.const:
            raise self.error("cannot assign to const type.")

        if lhs_size != rhs.size:
            rhs_ = rhs.resize(lhs_size, lhs_sign)
            ctx.emit(Resize(rhs, rhs_))
            rhs = rhs_
        ctx.emit(Mov(Dereference(lhs, rhs.size), rhs))
        return rhs


class BoolCompOp(ExpressionObject):
    """Short-circuiting boolean comparison operators."""

    __slots__ = ("op", "left", "right")

    def __init__(self, op: str, left: ExpressionObject,
                 right: ExpressionObject, *, ast: Optional[AST]=None):
        super().__init__(ast=ast)
        self.op = op
        self.left = left
        self.right = right

    @property
    async def type(self):
        return types.Int('u1')

    @with_ctx
    async def compile(self, ctx: CompileContext) -> Register:

        lhs_type, rhs_type = await self.left.type, await self.right.type

        if not rhs_type.implicitly_casts_to(lhs_type):
            raise self.error(f"Right argument to boolean operator: '{self.right.matched_region}'\n"
                             f"of type: {rhs_type} cannot be casted to left argument: '{self.left.matched_region}'\n"
                             f"of type {lhs_type}")

        if isinstance(lhs_type, types.Void):
            raise self.left.error("Void type argument to boolean operator")
        if isinstance(rhs_type, types.Void):
            raise self.right.error("Void type argument to boolean operator")


        r1: Register = await self.left.compile(ctx)
        ctx.emit(Compare(r1, Immediate(0, r1.size)))
        target = JumpTarget()
        op = {
            'or': CompType.neq,
            'and': CompType.eq
        }[self.op]

        cond = ctx.get_register(1)
        ctx.emit(SetCmp(cond, op))

        ctx.emit(Jump(target, cond))
        r2: Register = (await self.right.compile(ctx))
        if r2.size != r1.size:
            r2_ = r2.resize(r1.size, r1.sign)
            ctx.emit(Resize(r2, r2_))
            r2 = r2_
        ctx.emit(Mov(r1, r2))
        ctx.emit(target)
        return r1
