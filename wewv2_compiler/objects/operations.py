from typing import Iterable

from tatsu.ast import AST

from base import BaseObject, CompileContext, ExpressionObject
from irObject import (Binary, Call, Dereference, Immediate, Mov, NamedRegister,
                      Push, Register, Resize)


def unary_prefix(ast: AST):
    """Build a unary prefix op from an ast node."""
    return {
        "*": DereferenceOP,
        "++": PreincrementOP,
        "--": PreincrementOP,
        "~": BitwiseNegateOP,
        "!": LogicalNegateOP,
        "-": NumericalNegateOp,
        "+": NumericAddOP
    }[ast.op](ast)


def unary_postfix(ast: AST):
    return {
        "f": FunctionCallOp,
        "b": ArrayIndexOp,
        "d": PostIncrementOp,
        "c": CastExprOP  # TODO: this
    }[ast.type](ast)


class CastExprOP(ExpressionObject):
    def __init__(self, ast: AST):
        super().__init__(ast)
        self.type = ast.t
        self.expr = ast.left
        self.op = ast.op

    def compile_to(self, ctx: CompileContext, to: Register):
        with ctx.reg(self.expr.size) as res:
            yield from self.expr.compile_to(ctx, res)
            if self.op == "::":
                ctx.emit(Resize(res, to))
            else:
                ctx.emit(Mov(to, res))


class FunctionCallOp(ExpressionObject):
    def __init__(self, ast: AST):
        super().__init__(ast)
        self.fun = ast.left
        self.args: Iterable[BaseObject] = ast.args

    @property
    def type(self):
        return self.fun.returns

    def compile_to(self, ctx: CompileContext, to: Register):
        for arg in self.args:
            with ctx.reg(arg.size) as res:
                yield from arg.compile_to(ctx, res)
                ctx.emit(Push(res))
        yield from self.fun.compile(ctx)
        ctx.emit(Call(sum(i.size for i in self.args)))
        ctx.emit(Mov(to, NamedRegister.ret(self.size)))


class ArrayIndexOp(ExpressionObject):
    def __init__(self, ast: AST):
        super().__init__(ast)
        self.arg = ast.left
        self.offset = ast.args

    @property
    def type(self):
        return self.arg.type.to  # extract pointer

    # Our lvalue is the memory to dereference
    def load_lvalue_to(self, ctx: CompileContext, to: Register):
        with ctx.context(self):
            with ctx.reg((self.arg.size, self.offset.size)) as (argres, offres):
                yield from self.arg.compile_to(ctx, argres)
                yield from self.offset.compile_to(ctx, offres)
                # resize to ptr size, we dont want this to grow XXX THINK
                if self.offset.size != self.arg.size:
                    ctx.emit(Resize(offres, offres.resize(self.arg.size)))
                ctx.emit(Binary(argres, offres, '+'))
                ctx.emit(Mov(to, NamedRegister.acc1(self.arg.size)))

    def compile_to(self, ctx: CompileContext, to: Register):
        with ctx.reg(self.arg.size) as ptr:
            yield from self.load_lvalue_to(ctx, ptr)
            ctx.emit(Mov(to, Dereference(ptr)))


class PostIncrementOp(BaseObject):
    def __init__(self, ast: AST):
        super().__init__(ast)
        self.arg = ast.left
        self.op = ast.op

    @property
    def type(self):
        return self.arg.type.to  # pointer type

    def compile_to(self, ctx: CompileContext, to: Register):
        with ctx.reg((self.arg.size, self.size)) as (ptr, temp):
            yield from self.arg.load_lvalue_to(ctx, ptr)
            ctx.emit(Mov(temp, Dereference(ptr)))
            ctx.emit(Binary(temp, Immediate(1, self.size), self.op[0]))
            ctx.emit(Mov(Dereference(ptr), NamedRegister.acc1(self.size)))
            ctx.emit(Mov(to, temp))
