from compiler.objects import types
from compiler.objects.base import (CompileContext, ExpressionObject,
                                   ObjectRequest)
from compiler.objects.ir_object import (Dereference, Immediate, LoadVar, Mov,
                                        Register)

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
        typ = yield from self.type
        return self.lit.to_bytes(typ.size, "little", signed=typ.signed)

    def compile(self, ctx: CompileContext) -> Register:
        size = yield from self.size
        reg = ctx.get_register(size, self.lit.sign)
        ctx.emit(Mov(reg, Immediate(self.lit, size)))
        return reg


class StringLiteral(ExpressionObject):

    def __init__(self, ast: AST):
        super().__init__(ast)
        self.lit = ast.str

    @property
    def type(self):
        return types.string_lit

    def compile(self, ctx: CompileContext) -> Register:
        var = ctx.compiler.add_string(self.lit)
        reg = ctx.get_register((yield from self.size))
        ctx.emit(LoadVar(var, reg, lvalue=True))
        return reg


class Identifier(ExpressionObject):
    def __init__(self, ast: AST):
        super().__init__(ast)
        self.name = ast.identifier
        self.var = None

    @property
    def type(self):
        if self.var is None:
            self.var = yield ObjectRequest(self.name)
        return self.var.type

    def load_lvalue(self, ctx: CompileContext) -> Register:
        if self.var is None:
            self.var = yield ObjectRequest(self.name)
        reg = ctx.get_register(types.Pointer(self.var.type))
        ctx.emit(LoadVar(self.var, reg, lvalue=True))
        return reg, self.var

    def compile(self, ctx: CompileContext) -> Register:
        reg, var = yield from self.load_lvalue(ctx)
        if isinstance(var.type, types.Array):
            return reg  # array type, value is the pointer
        rego = reg.resize(var.size, var.sign)
        ctx.emit(Mov(rego, Dereference(reg)))
        return rego


class ArrayLiteral(ExpressionObject):
    def __init__(self, ast: AST):
        super().__init__(ast)
        self.exprs = ast.obj

        self._type = types.Pointer(self.exprs[0].type, const=True)

    @property
    def type(self):
        return self._type

    def to_array(self):
        """Convert type to array object from pointer object."""
        self._type = types.Array(self._type.to, len(self.exprs))

    def compile(self, ctx: CompileContext) -> Register:
        #  this is only run if we're not in the form of a array initialisation.
        #  check that everything is a constant
        if not all((yield from i.type) == self._type for i in self.exprs):
            raise self.error(f"Conflicting array literal types.")

        if not all(map(is_constant_expression, self.exprs)):
            raise self.error(f"Array literal terms are not constant.")

        type_ = yield from self.type

        if isinstance(type_.to, types.Int):
            bytes_ = b''.join(i.bytes for i in self.exprs)
            var = ctx.compiler.add_bytes(bytes_)
        elif isinstance(type_.to, types.string_lit):
            vars_ = [ctx.compiler.add_string(i.lit) for i in self.exprs]
            var = ctx.compiler.add_array(vars_)

        reg = ctx.get_register(var.size)
        ctx.emit(LoadVar(var, reg))
        return reg


def char_literal(ast):
    ast.val = ord(ast.chr)
    ast.size = types.const_char.size
    return IntegerLiteral(ast)
