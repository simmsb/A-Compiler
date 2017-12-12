import types

from base import BaseObject, CompileContext, ExpressionObject, ObjectRequest
from irObject import Dereference, Immediate, LoadVar, Mov, Register
from tatsu.ast import AST


def is_constant_expression(obj: ExpressionObject) -> bool:
    return isinstance(obj, (IntegerLiteral, StringLiteral))


class IntegerLiteral(ExpressionObject):
    def __init__(self, ast: AST):
        super().__init__(ast)
        self.lit: int = ast.val
        self._type = ast.type

    @property
    def type(self):
        return self._type

    @property
    def bytes(self):
        return self.lit.to_bytes(self.type.size, "little", signed=self.type.signed)

    def compile(self, ctx: CompileContext) -> Register:
        reg = ctx.get_register(self.size, self.lit.sign)
        ctx.emit(Mov(reg, Immediate(self.lit, self.size)))
        return reg


class StringLiteral(ExpressionObject):

    type = types.string_lit

    def __init__(self, ast: AST):
        super().__init__(ast)
        self.lit = ast.str

    def compile(self, ctx: CompileContext) -> Register:
        var = ctx.compiler.add_string(self.lit)
        reg = ctx.get_register(self.type.size)
        ctx.emit(LoadVar(var, reg))
        return reg


class Identifier(ExpressionObject):
    def __init__(self, ast: AST):
        super().__init__(ast)
        self.name = ast.identifier

    def load_lvalue(self, ctx: CompileContext) -> Register:
        var = yield ObjectRequest(self.name)
        reg = ctx.get_register(var.size, var.sign)
        ctx.emit(LoadVar(var, reg))
        return reg, var

    def compile(self, ctx: CompileContext) -> Register:
        reg, var = yield from self.load_lvalue_to(ctx)
        rego = reg.resize(var.size, var.sign)
        ctx.emit(Mov(rego, Dereference(reg)))
        return rego


class ArrayLiteral(ExpressionObject):
    def __init__(self, ast: AST):
        super().__init__(ast)
        self.exprs = ast.obj

        if not all(i.type == self.type for i in self.exprs):
            raise self.error(f"Conflicting array literal types.")

    @property
    def type(self):
        return types.Pointer(self.exprs[0].type)

    def compile_to(self, ctx: CompileContext) -> Register:
        #  this is only run if we're not in the form of a array initialisation.
        #  check that everything is a constant
        if not all(map(is_constant_expression, self.exprs)):
            raise self.error(f"Array literal terms are not constant.")
        if isinstance(self.type.to, types.Int):
            bytes = b''.join(i.bytes for i in self.exprs)
            var = ctx.compiler.add_bytes(bytes)
        elif isinstance(self.type.to, types.string_lit):
            vars = [ctx.compiler.add_string(i.lit) for i in self.exprs]
            var = ctx.compiler.add_array(vars)
        reg = ctx.get_register(var.size)
        ctx.emit(LoadVar(var, reg))
        return reg


def char_literal(ast):
    ast.val = ord(ast.chr)
    ast.size = types.const_char.size
    return IntegerLiteral(ast)
