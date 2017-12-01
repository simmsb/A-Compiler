import types
from io import BytesIO

from base import BaseObject, CompileContext, ObjectRequest
from irObject import Immediate, LoadVar, Push, Register
from tatsu.ast import AST


def is_constant_expression(obj: BaseObject) -> Bool:
    return isinstance(obj, (IntegerLiteral, StringLiteral))


class IntegerLiteral(BaseObject):
    def __init__(self, ast: AST):
        super().__init__(ast)
        self.lit: int = ast.val
        self.type: types.Int = ast.type

    @property
    def bytes(self):
        return self.lit.to_bytes(self.type.size, "little", signed=self.type.signed)

    def compile(self, ctx: CompileContext):
        ctx.emit(Push(Immediate(self.lit, self.size)))


class StringLiteral(BaseObject):

    type = types.string_lit

    def __init__(self, ast: AST):
        super().__init__(ast)
        self.lit = ast.str

    def compile(self, ctx: CompileContext):
        var = ctx.compiler.add_string(self.lit)
        ctx.emit(LoadVar(var, Register.acc1(types.Pointer.size)))
        ctx.emit(Push(Register.acc1(types.Pointer.size)))


class Identifier(BaseObject):
    def __init__(self, ast: AST):
        super().__init__(ast)
        self.name = ast.identifier

    def compile(self, ctx: CompileContext):
        var = yield ObjectRequest(self.name)
        ctx.emit(LoadVar(var, Register.acc1(var.size)))
        ctx.emit(Push(Register.acc1(var.size)))


class ArrayLiteral(BaseObject):
    def __init__(self, ast: AST):
        super().__init__(ast)
        self.exprs = ast.obj

        if not all(i.type == self.type for i in self.exprs):
            raise self.error(f"Conflicting array literal types.")

    @property
    def type(self):
        return types.Pointer(self.exprs[0].type)

    def compile(self, ctx: CompileContext):
        #  this is only run if we're not in the form of a array initialisation.
        #  check that everything is a constant
        if not all(map(is_constant_expression, self.exprs)):
            raise self.error(f"Array literal terms are not constant.")
        if isinstance(self.type.to, types.Int):
            size = self.type.to.size
            bytes = b''.join(i.bytes for i in self.exprs)
            var = ctx.compiler.add_bytes(bytes)
        elif isinstance(self.type.to, types.string_lit):
            vars = [ctx.compiler.add_string(i.lit) for i in self.exprs]
            var = ctx.compiler.add_array(vars)
        ctx.emit(LoadVar(var, Register.acc1(var.type.size)))
        ctx.emit(Push(Register.acc1(var.type.size)))


def char_literal(ast):
    ast.val = ord(ast.chr)
    ast.size = types.const_char.size
    return IntegerLiteral(ast)
