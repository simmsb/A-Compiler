import types
from typing import Iterable

from base import BaseObject, CompileContext, Variable
from expression_builder import acc1, acc2, baseptr, stackptr
from irObject import Call, Dereference, Mov, Pop, Push, Register


def unary_op(ast):
    """Build a unary op from an ast node."""
    if ast.op in ("*", "++", "--", "~", "!", "-", "+"):
        return UnaryPrefixOp(ast)
    if ast.op in ("cast", "interpret"):
        return CastOp(ast)
    return UnaryPostfixOp(ast)


def unary_postfix(ast):
    return {
        "f": FunctionCallOp,
        "b": ArrayIndexOp,
        "d": PostIncrementOp
    }[ast.type](ast)


class FunctionCallOp(BaseObject):
    def __init__(self, ast):
        super().__init__(ast)
        self.fun = ast.left
        self.args: Iterable[Variable] = ast.args

    @property
    def type(self):
        return self.fun.returns

    def compile(self, ctx: CompileContext):
        with ctx.context():
            for arg in self.args:
                yield from arg.compile(ctx)
            yield from self.fun.compile(ctx)
            expr = stackptr - sum(i.size for i in self.args)
            for i in expr.emit():
                ctx.emit(i)
            ctx.emit(Pop(Register.stackptr))
            ctx.emit(Push(Register.ret))


class ArrayIndexOp(BaseObject):
    def __init__(self, ast):
        super().__init__(ast)
        self.arg = ast.left
        self.offset = ast.args

    @property
    def type(self):
        return self.arg.type.to  # extract pointer

    def load_lvalue(self, ctx: CompileContext):
        with ctx.context():
            yield from self.arg.compile(ctx)
            yield from self.offset.compile(ctx)
            ctx.emit(Pop(Register.acc1, size=self.arg.size))
            ctx.emit(Pop(Register.acc2, size=self.offset.size))
            expr = acc1 + acc2
            for i in expr.emit():
                ctx.emit(i)

    def compile(self, ctx: CompileContext):
        with ctx.context():
            yield from self.load_lvalue(ctx)
            ctx.emit(Pop(Dereference(Register.acc1)))
            ctx.emit(Push(Register.acc1))


class PostIncrementOp(BaseObject):
    def __init__(self, ast):
        super().__init__(ast)
        self.arg = ast.left
        self.op = ast.op

    @property
    def type(self):
        return self.arg.type

    def compile(self, ctx: CompileContext):
        with ctx.context():
            yield from self.arg.load_lvalue(ctx)
            ctx.emit(Pop(Register.acc1, size=self.arg.size))
            ctx.emit(Mov(Register.acc2, Dereference(Register.acc1), size=self.arg.size))
            expr = acc2 + 1
            for i in expr.emit():
                ctx.emit(i)
            ctx.emit(Push(Register.acc2))
            ctx.emit(Mov(Dereference(Register.acc1), Register.acc2), size=self.arg.size)
