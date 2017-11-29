import types
from typing import Iterable

from base import BaseObject, CompileContext, Variable
from expression_builder import OpRegister
from irObject import Binary, Call, Dereference, Mov, Pop, Push, Register


def unary_prefix(ast):
    """Build a unary prefix op from an ast node."""
    if ast.op in ("*", "++", "--", "~", "!", "-", "+"):
        return UnaryPrefixOp(ast)  # TODO: this


def unary_postfix(ast):
    return {
        "f": FunctionCallOp,
        "b": ArrayIndexOp,
        "d": PostIncrementOp,
        "c": CastExprOP  # TODO: this
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

    def load_lvalue(self, ctx: CompileContext):  # Our lvalue is the memory to dereference
        with ctx.context(self):
            yield from self.arg.compile(ctx)
            yield from self.offset.compile(ctx)
            ctx.emit(Pop(Register.acc1(self.offset.size)))
            ctx.emit(Pop(Register.acc2(self.arg.size)))
            expr = OpRegister.acc1(self.offset.size) + OpRegister.acc2(self.arg.size)
            for i in expr.emit():
                ctx.emit(i)

    def compile(self, ctx: CompileContext):
        yield from self.load_lvalue(ctx)
        ctx.emit(Pop(Register.acc1(max(self.arg.size, self.offset.size))))
        ctx.emit(Push(Dereference(Register.acc1(self.type.size))))


class PostIncrementOp(BaseObject):
    def __init__(self, ast):
        super().__init__(ast)
        self.arg = ast.left
        self.op = ast.op

    @property
    def type(self):
        return self.arg.type.to  # pointer type

    def compile(self, ctx: CompileContext):
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
