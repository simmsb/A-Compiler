import types

from tatsu.ast import AST

from base import BaseObject, CompileContext, ObjectRequest
from irObject import Immediate, LoadVar, Push, Register


class IntegerLiteral(BaseObject):
    def __init__(self, ast: AST):
        super().__init__(ast)
        self.lit = ast.val
        self.size = ast.size

    def compile(self, ctx: CompileContext):
        ctx.emit(Push(Immediate(self.lit, self.size)))


class StringLiteral(BaseObject):
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


def char_literal(ast):
    ast.val = ord(ast.chr)
    ast.size = types.const_char.size
    return IntegerLiteral(ast)
