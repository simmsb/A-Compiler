from compiler.objects import types
from compiler.objects.base import (BaseObject, CompileContext,
                                   ExpressionObject, ObjectRequest, ExprCompileType)
from compiler.objects.ir_object import (Binary, Call, Compare, CompType,
                                        Dereference, Immediate, Jump,
                                        JumpTarget, Mov, NamedRegister, Push,
                                        Register, Resize, SetCmp, Unary)
from typing import Generator, Iterable, Tuple, Union

from tatsu.ast import AST

def unary_prefix(ast: AST):
    """Build a unary prefix op from an ast node."""
    return {
        "*": DereferenceOP,
        "++": PreincrementOP,
        "--": PreincrementOP,
        "~": UnaryOP,
        "!": UnaryOP,
        "-": UnaryOP,
        "+": UnaryOP
    }[ast.op](ast)


class UnaryOP(ExpressionObject):
    def __init__(self, ast: AST):
        super().__init__(ast)
        self.op = ast.op
        self.expr: ExpressionObject = ast.right

    @property
    def type(self):
        return self.expr.type

    def compile(self, ctx: CompileContext) -> ExprCompileType:
        reg: Register = (yield from self.expr.compile(ctx))
        ctx.emit(Unary(reg, self.op))
        return reg


def unary_postfix(ast: AST):
    return {
        "f": FunctionCallOp,
        "b": ArrayIndexOp,
        "d": PostIncrementOp,
        "c": CastExprOP
    }[ast.type](ast)


class PreincrementOP(ExpressionObject):
    def __init__(self, ast: AST):
        super().__init__(ast)
        self.expr: ExpressionObject = ast.right
        self.op = ast.op

    @property
    def type(self):
        return self.expr.type

    def load_lvalue(self, ctx: CompileContext) -> ExprCompileType:
        return self.expr.load_lvalue(ctx)

    def compile(self, ctx: CompileContext) -> ExprCompileType:
        ptr: Register = (yield from self.load_lvalue(ctx))
        tmp = ctx.get_register((yield from self.size))
        ctx.emit(Mov(tmp, Dereference(ptr)))
        ctx.emit(Binary.add(tmp, Immediate(1, tmp.size)))
        ctx.emit(Mov(Dereference(ptr), tmp))
        return tmp


class DereferenceOP(ExpressionObject):
    def __init__(self, ast: AST):
        super().__init__(ast)
        self.expr: ExpressionObject = ast.right

    @property
    def type(self):
        return (yield from self.expr.type).to

    def load_lvalue(self, ctx: CompileContext) -> ExprCompileType:
        return self.expr.compile(ctx)

    def compile(self, ctx: CompileContext) -> ExprCompileType:
        ptr: Register = (yield from self.load_lvalue(ctx))
        reg = ctx.get_register((yield from self.size))
        ctx.emit(Mov(reg, Dereference(ptr)))
        return reg


class CastExprOP(ExpressionObject):
    def __init__(self, ast: AST):
        super().__init__(ast)
        self._type = ast.t
        self.expr: ExpressionObject = ast.left
        self.op = ast.op

    @property
    def type(self):
        return self._type

    def compile(self, ctx: CompileContext) -> ExprCompileType:
        reg: Register = (yield from self.expr.compile(ctx))
        res = reg.resize(self._type.size, self._type.sign)
        if self.op == "::":
            ctx.emit(Resize(reg, res))  # emit resize operation
        else:
            ctx.emit(Mov(res, reg))  # standard move, no entension
        return res


class FunctionCallOp(ExpressionObject):
    def __init__(self, ast: AST):
        super().__init__(ast)
        self.fun: ExpressionObject = ast.left
        self.args: Iterable[BaseObject] = ast.args

    @property
    def type(self):
        return (yield from self.fun).type.returns

    def compile(self, ctx: CompileContext) -> ExprCompileType:
        fun_typ = yield from self.fun.type
        arg_types = ((i, (yield from i.type)) for i in self.args)

        if not isinstance(fun_typ, types.Function):
            raise self.error("Called object is not a function.")

        for arg_n, (lhs_type, (rhs_obj, rhs_type)) in enumerate(zip(fun_typ.args, arg_types)):
            if lhs_type != rhs_type:
                raise rhs_obj.error(
                    f"Argument {arg_n} to call {self.fun.identifier} was of "
                    f"type {rhs_type} instead of expected {lhs_type}.")

        for arg in self.args:
            res: Register = (yield from arg.compile(ctx))
            ctx.emit(Push(res))
        res: Register = (yield from self.fun.compile(ctx))
        ctx.emit(Call(sum((yield from i.size) for i in self.args), res))

        size = yield from self.size
        reg = ctx.get_register(size)
        ctx.emit(Mov(reg, NamedRegister.ret(size)))
        return reg


class ArrayIndexOp(ExpressionObject):
    def __init__(self, ast: AST):
        super().__init__(ast)
        self.arg = ast.left
        self.offset = ast.args

    @property
    def type(self):
        return (yield from self.arg.type).to  # extract pointer

    # Our lvalue is the memory to dereference
    def load_lvalue(self, ctx: CompileContext) -> ExprCompileType:
        atype = yield from self.arg.type
        if not isinstance(atype, (types.Pointer, types.Array)):
            raise self.error(f"Incompatible type to array index base {atype}")

        if isinstance(atype.to, types.Array):  # if we are indexing a multi-dimensional array, dont dereference
            argres: Register = (yield from self.arg.load_lvalue(ctx))
        else:
            argres: Register = (yield from self.arg.compile(ctx))
        offres: Register = (yield from self.offset.compile(ctx))

        size = yield from self.size  # if type.to is an array, this will be the size of the internal array

        offres0 = offres.resize(argres.size)  # resize pointer correctly
        ctx.emit(Resize(offres, offres0))
        offres = offres0

        res = ctx.get_register(size)
        ctx.emit(Binary.mul(offres, size))
        ctx.emit(Binary.add(argres, offres, res))
        return res

    def compile(self, ctx: CompileContext) -> ExprCompileType:
        ptr: Register = (yield from self.load_lvalue(ctx))
        res = ctx.get_register((yield from self.size))
        ctx.emit(Mov(res, Dereference(ptr)))
        return res


class PostIncrementOp(ExpressionObject):
    def __init__(self, ast: AST):
        super().__init__(ast)
        self.arg = ast.left
        self.op = {"++": "add",
                   "--": "sub"}[ast.op]

    @property
    def type(self):
        return self.arg.type

    def compile(self, ctx: CompileContext) -> ExprCompileType:
        ptr: Register = (yield from self.arg.load_lvalue(ctx))
        size = yield from self.size
        res, temp = ctx.get_register(size), ctx.get_register(size)
        ctx.emit(Mov(res, Dereference(ptr)))
        ctx.emit(Binary(res, Immediate(1, size), self.op[0], temp))
        ctx.emit(Mov(Dereference(ptr), temp))
        return res


class BinaryExpression(ExpressionObject):
    """Generic binary expression (a `x` b)

    _compat_types is used to typecheck the expression and set the return type of it."""

    _compat_types: Tuple[Union[Tuple[str], str],
                         Tuple[types.Type, types.Type], types.Type] = ()

    @property
    def size(self):
        return max((yield from self.left.size),
                   (yield from self.right.size))

    @property
    def type(self):
        return self._type

    def __init__(self, ast: AST):
        super().__init__(ast)
        self.left = ast.left
        self.op = ast.op
        self.right = ast.right
        self._type = None

    def compile_meta(self, ctx: CompileContext) -> Generator[BaseObject, ObjectRequest, Tuple[Register, Register]]:
        """Binary expression meta compile, returns registers of both side
        Both registers returned have equal size."""
        op = self.op
        left = yield from self.left.type
        right = yield from self.right.type
        # typecheck operands here

        for check_ops, (lhs_typ, rhs_type), result_type in self._compat_types:  # wew lad
            if not isinstance(check_ops, (list, tuple)):
                check_ops = (check_ops,)
            for check_op in check_ops:
                if (isinstance(left, lhs_typ) and isinstance(right, rhs_type) and check_op == op):
                    self._type = result_type
                    break
            else:
                continue
            break
        else:
            raise self.error(
                f"Incompatible types for binary {op}: {left} and {right}")

        lhs: Register = (yield from self.left.compile(ctx))
        rhs: Register = (yield from self.right.compile(ctx))

        if lhs.size < rhs.size:
            lhs0 = lhs.resize(rhs.size)
            ctx.emit(Resize(lhs, lhs0))
            lhs = lhs0
        elif rhs.size < lhs.size:
            rhs0 = rhs.resize(rhs.size)
            ctx.emit(Resize(rhs, rhs0))
            rhs = rhs0

        return lhs, rhs


class BinAddOp(BinaryExpression):

    _compat_types = (  # maybe follow algebraic rules to reduce repetition
        ('+', (types.Pointer, types.Int), types.Pointer),
        ('+', (types.Int, types.Pointer), types.Pointer),
        (('+', '-'), (types.Int, types.Int), types.Int),
        ('-', (types.Pointer, types.Pointer), types.Int),
    )

    @property
    def type(self):
        if isinstance(self._type, types.Pointer):
            return types.Pointer(types.Int.fromsize((yield from self.size)))
        return types.Int.fromsize((yield from self.size))

    def compile(self, ctx: CompileContext) -> ExprCompileType:
        lhs: Register
        rhs: Register
        lhs, rhs = (yield from self.compile_meta(ctx))

        res = ctx.get_register(lhs.size)

        op = {"+": "add",
              "-": "sub"}[self.op]

        ctx.emit(Binary(lhs, rhs, op, res))
        return res


class BinMulOp(BinaryExpression):
    """Binary multiplicative operation.

    Emits a signed operation of the rhs of a division is signed."""

    _compat_types = (
        (('*', '/'), (types.Int, types.Int), types.Int),
    )

    @property
    def type(self):
        lhs = yield from self.left.type
        rhs = yield from self.right.type
        signed = (lhs.signed and rhs.signed) if self.op == "/" else False
        return types.Int.fromsize((yield from self.size), signed)

    def compile(self, ctx: CompileContext) -> ExprCompileType:
        lhs: Register
        rhs: Register
        lhs, rhs = yield from self.compile_meta(ctx)

        res = ctx.get_register(lhs.size)

        if self.op == "*":
            op = "add"
        elif self.op == "/" and rhs.sign:
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
    def type(self):
        if self.op == '>>':
            lhs = yield from self.left.type
            signed = lhs.signed
        else:
            signed = False
        return types.Int.fromsize((yield from self.size), signed)

    def compile(self, ctx: CompileContext) -> ExprCompileType:
        lhs: Register
        rhs: Register
        lhs, rhs = yield from self.compile_meta(ctx)

        res = ctx.get_register(lhs.size)

        if self.op == "<<":
            op = "shl"
        elif self.op == ">>" and (lhs.sign or rhs.sign):
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
    def type(self):
        # always results in 0 or 1 (unsigned 1 byte int)
        return types.Int('u1')

    @property
    def size(self):
        return (yield from self.type).size

    def compile(self, ctx: CompileContext) -> ExprCompileType:
        op = {
            '<=': CompType.leq,
            '<': CompType.lt,
            '==': CompType.eq,
            '!=': CompType.neq,
            '>': CompType.gt,
            '>=': CompType.geq
        }[self.op]

        lhs: Register
        rhs: Register
        lhs, rhs = yield from self.compile_meta(ctx)
        res = ctx.get_register(1)
        ctx.emit(Compare(lhs, rhs))
        ctx.emit(SetCmp(res, op))


class BitwiseOp(BinaryExpression):
    """Binary bitwise operators."""

    _compat_types = (
        (("|", "^", "&"), (types.Int, types.Int), types.Int),
    )

    def compile(self, ctx: CompileContext) -> ExprCompileType:
        op = {
            "|": "or",
            "^": "xor",
            "&": "and"
        }[self.op]

        lhs: Register
        rhs: Register
        lhs, rhs = yield from self.compile_meta(ctx)
        res = ctx.get_register(lhs.size)
        ctx.emit(Binary(lhs, rhs, op, res))
        return res


class AssignOp(ExpressionObject):
    """Assignment operation."""

    def __init__(self, ast: AST):
        super().__init__(ast)
        self.left: ExpressionObject = ast.left
        self.right: ExpressionObject = ast.right

    @property
    def type(self):
        return self.right.type

    def compile(self, ctx: CompileContext) -> ExprCompileType:
        lhs: Register = (yield from self.left.load_lvalue(ctx))
        rhs: Register = (yield from self.right.compile(ctx))

        lhs_size = yield from self.left.size
        if lhs_size != rhs.size:
            rhs_ = rhs.resize(lhs_size)
            ctx.emit(Resize(rhs, rhs_))
            rhs = rhs_
        ctx.emit(Mov(Dereference(lhs), rhs))
        return rhs


class BoolCompOp(ExpressionObject):
    """Short-circuiting boolean comparison operators."""

    def __init__(self, ast: AST):
        super().__init__(ast)
        self.op = ast.op
        self.left: ExpressionObject = ast.left
        self.right: ExpressionObject = ast.right

    @property
    def type(self):
        return types.Int('u1')

    def compile(self, ctx: CompileContext) -> ExprCompileType:
        r1: Register = (yield from self.left.compile(ctx))
        ctx.emit(Compare(r1, Immediate(0, r1.size)))
        target = JumpTarget()
        op = {
            '||': CompType.neq,
            '&&': CompType.eq
        }[self.op]

        jump = ctx.emit(Jump(target, op))
        r2: Register = (yield from self.right.compile(ctx))
        if r2.size != r1.size:
            r2_ = r2.resize(r1.size)
            ctx.emit(Resize(r2, r2_))
            r2 = r2_
        ctx.emit(Mov(r1, r2))
        ctx.emit(jump)
        return r1
