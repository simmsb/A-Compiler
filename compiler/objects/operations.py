from compiler.objects import types
from compiler.objects.base import BaseObject, CompileContext, ExpressionObject
from compiler.objects.ir_object import (Binary, Call, Dereference, Immediate,
                                        Mov, NamedRegister, Push, Register,
                                        Resize, Unary)
from typing import Iterable

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
        self.expr = ast.right

    @property
    def type(self):
        return self.expr.type

    def compile(self, ctx: CompileContext) -> Register:
        reg = yield from self.expr.compile(ctx)
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
        self.val: ExpressionObject = ast.right
        self.op = ast.op

    @property
    def type(self):
        return self.val.type

    def load_lvalue(self, ctx: CompileContext) -> Register:
        return self.val.load_lvalue(ctx)

    def compile(self, ctx: CompileContext) -> Register:
        ptr = yield from self.load_lvalue(ctx)
        tmp = ctx.get_register((yield from self.size))
        ctx.emit(Mov(tmp, Dereference(ptr)))
        ctx.emit(Binary.add(tmp, Immediate(1, tmp.size)))
        ctx.emit(Mov(Dereference(ptr), tmp))
        return tmp


class DereferenceOP(ExpressionObject):
    def __init__(self, ast: AST):
        super().__init__(ast)
        self.val = ast.right

    @property
    def type(self):
        return (yield from self.val.type).to

    def load_lvalue(self, ctx: CompileContext) -> Register:
        return self.val.compile(ctx)

    def compile(self, ctx: CompileContext) -> Register:
        ptr = yield from self.load_lvalue(ctx)
        reg = ctx.get_register((yield from self.size))
        ctx.emit(Mov(reg, Dereference(ptr)))
        return reg


class CastExprOP(ExpressionObject):
    def __init__(self, ast: AST):
        super().__init__(ast)
        self._type = ast.t
        self.expr = ast.left
        self.op = ast.op

    @property
    def type(self):
        return self._type

    def compile(self, ctx: CompileContext) -> Register:
        reg = yield from self.expr.compile(ctx)
        res = reg.resize(self._type.size, self._type.sign)
        if self.op == "::":
            ctx.emit(Resize(reg, res))  # emit resize operation
        else:
            ctx.emit(Mov(res, reg))  # standard move, no entension
        return res


class FunctionCallOp(ExpressionObject):
    def __init__(self, ast: AST):
        super().__init__(ast)
        self.fun = ast.left
        self.args: Iterable[BaseObject] = ast.args

    @property
    def type(self):
        return (yield from self.fun).type.returns

    def compile(self, ctx: CompileContext) -> Register:
        for arg in self.args:
            res = yield from arg.compile(ctx)
            ctx.emit(Push(res))
        res = yield from self.fun.compile(ctx)
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
    def load_lvalue(self, ctx: CompileContext) -> Register:
        atype = yield from self.arg.type
        if not isinstance(atype, (types.Pointer, types.Array)):
            raise self.error(f"Incompatible type to array index base {atype}")

        argres = yield from self.arg.compile(ctx)
        offres = yield from self.offset.compile(ctx)

        size = yield from self.size

        offres0 = offres.resize(argres.size)  # resize pointer correctly
        ctx.emit(Resize(offres, offres0))
        offres = offres0

        res = ctx.get_register(size)
        ctx.emit(Binary.mul(offres, size))  # what to do what to do
        ctx.emit(Binary.add(argres, offres, res))
        return res

    def compile(self, ctx: CompileContext) -> Register:
        ptr = yield from self.load_lvalue(ctx)
        ctx.emit(Mov(ptr.resize((yield from self.size)), Dereference(ptr)))


class PostIncrementOp(ExpressionObject):
    def __init__(self, ast: AST):
        super().__init__(ast)
        self.arg = ast.left
        self.op = {"++": "add",
                   "--": "sub"}[ast.op]

    @property
    def type(self):
        return self.arg.type

    def compile(self, ctx: CompileContext) -> Register:
        ptr = yield from self.arg.load_lvalue(ctx)
        size = yield from self.size
        res, temp = ctx.get_register(size), ctx.get_register(size)
        ctx.emit(Mov(res, Dereference(ptr)))
        ctx.emit(Binary(res, Immediate(1, size), self.op[0], temp))
        ctx.emit(Mov(Dereference(ptr), temp))
        return res


class BinaryExpression(ExpressionObject):

    _compat_types = ()

    @property
    def size(self):
        return max((yield from self.left.size),
                   (yield from self.right.size))

    def __init__(self, ast: AST):
        super().__init__(ast)
        self.left = ast.left
        self.op = ast.op
        self.right = ast.right
        self._type = None

    def compile(self, ctx: CompileContext):
        op = self.op
        left = yield from self.left.type
        right = yield from self.right.type
        # typecheck operands here

        for o, (l, r), t in self._compat_types:
            if (isinstance(left, l) and isinstance(right, r) and o == op):
                self._type = t
                break
        else:
            raise self.error(f"Incompatible types for binary {op}: {left} and {right}")

        lhs = yield from self.left.compile(ctx)
        rhs = yield from self.right.compile(ctx)

        if lhs.size < rhs.size:
            lhs0 = lhs.resize(rhs.size)
            ctx.emit(Resize(lhs, lhs0))
            lhs = lhs0
        elif rhs.size < lhs.size:
            rhs0 = lhs.resize(lhs.size)
            ctx.emit(Resize(rhs, rhs0))
            rhs = rhs0

        return lhs, rhs


class BinAddOp(BinaryExpression):

    _compat_types = (  # maybe follow algebraic rules to reduce repetition
        ('+', (types.Pointer, types.Int), types.Pointer),
        ('+', (types.Int, types.Pointer), types.Pointer),
        ('+', (types.Int, types.Int), types.Int),
        ('-', (types.Pointer, types.Pointer), types.Int),
        ('-', (types.Int, types.Int), types.Int)
    )

    @property
    def type(self):
        if isinstance(self._type, types.Pointer):
            return types.Pointer(types.Int((yield from self.size)))
        return types.Int((yield from self.size))

    def compile(self, ctx: CompileContext):
        lhs, rhs = yield from super().compile(ctx)

        res = ctx.get_register(lhs.size)

        op = {"+": "add",
              "-": "sub"}[self.op]

        ctx.emit(Binary(lhs, rhs, op, res))
        return res
