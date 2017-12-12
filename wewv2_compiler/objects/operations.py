import types
from typing import Iterable

from base import BaseObject, CompileContext, ExpressionObject
from irObject import (Binary, Call, Dereference, Immediate, Mov, NamedRegister,
                      Push, Register, Resize, Unary)
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
        return (yield from self.val.load_lvalue(ctx))

    def compile(self, ctx: CompileContext) -> Register:
        ptr = yield from self.load_lvalue(ctx)
        tmp = ctx.get_register(self.size)
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
        return self.val.type.to

    def load_lvalue(self, ctx: CompileContext) -> Register:
        return self.val.compile(ctx)

    def compile(self, ctx: CompileContext) -> Register:
        ptr = yield from self.load_lvalue(ctx)
        reg = ctx.get_register(self.size)
        ctx.emit(Mov(reg, Dereference(ptr)))
        return reg


class CastExprOP(ExpressionObject):
    def __init__(self, ast: AST):
        super().__init__(ast)
        self.type = ast.t
        self.expr = ast.left
        self.op = ast.op

    def compile(self, ctx: CompileContext) -> Register:
        reg = yield from self.expr.compile(ctx)
        res = reg.resize(self.type.size, self.type.sign)
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
        return self.fun.returns

    def compile(self, ctx: CompileContext) -> Register:
        for arg in self.args:
            res = yield from arg.compile(ctx)
            ctx.emit(Push(res))
        res = yield from self.fun.compile(ctx)
        ctx.emit(Call(sum(i.size for i in self.args), res))
        reg = ctx.get_register(self.size)
        ctx.emit(Mov(reg, NamedRegister.ret(self.size)))
        return reg


class ArrayIndexOp(ExpressionObject):
    def __init__(self, ast: AST):
        super().__init__(ast)
        self.arg = ast.left
        self.offset = ast.args

    @property
    def type(self):
        return self.arg.type.to  # extract pointer

    # Our lvalue is the memory to dereference
    def load_lvalue(self, ctx: CompileContext) -> Register:
        argres = yield from self.arg.compile(ctx)
        offres = yield from self.offset.compile(ctx)
        # resize to ptr size
        if self.offset.size != self.arg.size:
            offres0 = offres.resize(self.arg.size)
            ctx.emit(Resize(offres, offres0))
            offres = offres0
        res = ctx.get_register(self.size)
        ctx.emit(Binary.add(argres, offres, res))
        return res

    def compile(self, ctx: CompileContext) -> Register:
        ptr = yield from self.load_lvalue(ctx)
        ctx.emit(Mov(ptr.resize(self.size), Dereference(ptr)))


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
        res, temp = ctx.get_register(self.size), ctx.get_register(self.size)
        ctx.emit(Mov(res, Dereference(ptr)))
        ctx.emit(Binary(res, Immediate(1, self.size), self.op[0], temp))
        ctx.emit(Mov(Dereference(ptr), temp))
        return res
