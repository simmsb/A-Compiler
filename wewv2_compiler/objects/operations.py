import types
from typing import Iterable

from base import BaseObject, CompileContext, Variable
from expression_builder import OpRegister
from irObject import Binary, Call, Dereference, Mov, Pop, Push, Register


def unary_op(ast):
    """Build a unary op from an ast node."""
    if ast.op in ("*", "++", "--", "~", "!", "-", "+"):
        return UnaryPrefixOp(ast)  # TODO: this
    if ast.op in ("cast", "interpret"):
        return CastOp(ast)  # TODO: this
    return UnaryPostfixOp(ast)  # TODO: this


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
            ctx.emit(Call())
            expr = OpRegister.stackptr(2) - sum(i.size for i in self.args)
            for i in expr.emit():
                ctx.emit(i)
            ctx.emit(Pop(Register.stackptr(2)))  # stackptr is 2 bytes
            ctx.emit(Push(Register.ret(self.type.size)))


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
            ctx.emit(Pop(Register.acc1(self.arg.size)))
            ctx.emit(Pop(Register.acc2(self.offset.size)))
            expr = OpRegister.acc1 + OpRegister.acc2
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
        return self.arg.type.to  # pointer type

    def compile(self, ctx: CompileContext):
        with ctx.context():
            pointer_reg = Register.acc1(self.arg.size)
            value_reg = Register.acc2(self.type.size)
            yield from self.arg.load_lvalue(ctx)
            ctx.emit(Pop(pointer_reg))
            # copy the current value, to size is the size of what's pointed to
            ctx.emit(Mov(value_reg, Dereference(pointer_reg)))
            ctx.emit(Push(value_reg))
            ctx.emit(Binary(value_reg, 1, self.op[0]))
            ctx.emit(Mov(Dereference(pointer_reg), value_reg))
            # value is left on stack unmodified
