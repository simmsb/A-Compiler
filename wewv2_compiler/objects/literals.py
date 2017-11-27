import types

from base import BaseObject, CompileContext
from irObject import Immediate, Push
from tatsu.ast import AST


class IntegerLiteral(BaseObject):
    def __init__(self, ast: AST):
        super().__init__(ast)
        self.lit = ast.val
        self.size = ast.size

    def compile(self, ctx: CompileContext):
        with ctx.context(self):
            ctx.emit(Push(Immediate(self.lit, self.size)))
