from types import coroutine

from compiler.objects import types
from compiler.objects.base import (CompileContext, ExpressionObject,
                                   ObjectRequest, Variable, ExprCompileType, with_ctx)
from compiler.objects.ir_object import (Dereference, Immediate, LoadVar, Mov,
                                        Register)
from typing import Coroutine, List, Tuple, Union, Optional

from tatsu.ast import AST


def is_constant_expression(obj: ExpressionObject) -> bool:
    return isinstance(obj, (IntegerLiteral, StringLiteral))


class IntegerLiteral(ExpressionObject):
    def __init__(self, ast: AST):
        super().__init__(ast)
        self.lit: int = int(ast.val)
        if ast.type:
            self._type = ast.type
        else:
            bitlen = self.lit.bit_length()
            for (bitrange, s) in ((range(0,  8 ), 1),
                                  (range(8,  16), 2),
                                  (range(16, 32), 4)):
                if bitlen in bitrange:
                    size = s
                    break
            else:
                size = 8
            sign = self.lit < 0
            self._type = types.Int.fromsize(size, sign)

    @property
    async def type(self):
        return self._type

    async def bytes(self, size: Optional[int]=None):
        """Get the byte representation of this integer literal.

        :param size: Size to output, if None use size of type"""
        typ = await self.type
        size = typ.size if size is None else size
        return self.lit.to_bytes(size, "little", signed=typ.signed)

    @with_ctx
    async def compile(self, ctx: CompileContext) -> Register:
        reg = ctx.get_register(self._type.size, self._type.signed)
        ctx.emit(Mov(reg, Immediate(self.lit, self._type.size)))
        return reg


class StringLiteral(ExpressionObject):

    def __init__(self, ast: AST):
        super().__init__(ast)
        self.lit = ast.str

    @property
    async def type(self):
        return types.string_lit

    @with_ctx
    async def compile(self, ctx: CompileContext) -> ExprCompileType:
        var = ctx.compiler.add_string(self.lit)
        reg = ctx.get_register((await self.size))
        ctx.emit(LoadVar(var, reg, lvalue=True))
        return reg


class Identifier(ExpressionObject):
    def __init__(self, ast: AST):
        super().__init__(ast)
        self.name = ast.identifier
        self.var = None

    @property
    @coroutine  # these have to be coroutines since we 'yield' inside them and return a value
    def type(self):
        if self.var is None:
            self.var = yield ObjectRequest(self.name)
        return self.var.type

    @coroutine
    def load_value(self, ctx: CompileContext) -> Coroutine[ObjectRequest, Variable, Tuple[Register, Variable]]:
        if self.var is None:
            self.var = yield ObjectRequest(self.name)
        reg = ctx.get_register(types.Pointer(self.var.type).size)
        ctx.emit(LoadVar(self.var, reg, lvalue=True))
        return reg, self.var

    async def load_lvalue(self, ctx: CompileContext) -> ExprCompileType:
        reg, _ = await self.load_value(ctx)
        return reg

    @with_ctx
    async def compile(self, ctx: CompileContext) -> ExprCompileType:
        reg, var = await self.load_value(ctx)
        if isinstance(var.type, types.Array):
            return reg  # array type, value is the pointer
        rego = reg.resize(var.size)
        ctx.emit(Mov(rego, Dereference(reg)))
        return rego


class ArrayLiteral(ExpressionObject):
    def __init__(self, ast: AST):
        super().__init__(ast)
        self.exprs: List[ExpressionObject] = ast.obj

        self._type = None

    @property
    async def type(self) -> Coroutine[ObjectRequest, Variable, Union[types.Array, types.Pointer]]:
        if self._type is None:
            self._type = types.Pointer((await self.exprs[0].type), const=True)
        return self._type

    async def to_array(self):
        """Convert type to array object from pointer object."""
        to = (await self.exprs[0].type) if self._type is None else self._type.to
        self._type = types.Array(to, len(self.exprs))

    async def check_types(self):
        my_type = (await self.type).to
        # XXX: this will break in py3.7, change to a manual for loop instead
        expr_types = [(await i.type) for i in self.exprs]
        if not all(i.implicitly_casts_to(my_type) for i in expr_types):
            raise self.error(f"Conflicting array literal types.")

    @with_ctx
    async def compile(self, ctx: CompileContext) -> ExprCompileType:
        #  this is only run if we're not in the form of a array initialisation.
        #  check that everything is a constant
        my_type = (await self.type).to
        await self.check_types()

        if not all(map(is_constant_expression, self.exprs)):
            raise self.error(f"Array literal terms are not constant.")

        if isinstance(my_type, types.Int):
            self.exprs: List[IntegerLiteral]
            bytes_ = b''.join([(await i.bytes(my_type.size)) for i in self.exprs])
            var = ctx.compiler.add_bytes(bytes_)
        elif my_type == types.string_lit:
            self.exprs: List[StringLiteral]
            vars_ = [ctx.compiler.add_string(i.lit) for i in self.exprs]
            var = ctx.compiler.add_array(vars_)

        reg = ctx.get_register(var.size)
        ctx.emit(LoadVar(var, reg))
        return reg


def char_literal(ast):
    ast.val = ord(ast.chr)
    ast.size = types.const_char.size
    return IntegerLiteral(ast)
