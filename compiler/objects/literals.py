from types import coroutine
from ast import literal_eval
from itertools import chain

from compiler.objects import types
from compiler.objects.base import (CompileContext, ExpressionObject,
                                   ObjectRequest, with_ctx)
from compiler.objects.variable import Variable
from compiler.objects.ir_object import Immediate, LoadVar, Mov, Register, Binary, Resize, Dereference
from typing import List, Tuple, Union, Optional, Coroutine

from tatsu.ast import AST


class LiteralObject:
    def to_bytes(self, size: Optional[int]=None) -> bytes:
        return NotImplemented

    @property
    def byte_length(self) -> int:
        return NotImplemented

    def compile_to_var(self, ctx: CompileContext) -> Variable:
        return NotImplemented


class IntegerLiteral(ExpressionObject, LiteralObject):
    def __init__(self, lit: int, type: Optional[types.Type], ast: Optional[AST]=None):
        super().__init__(ast)
        self.lit lit
        if type:
            self._type = type
        else:
            # if the size isn't given, determine the size from the value of the literal
            bitlen = self.lit.bit_length()
            for (bitrange, s) in ((range(0,   8), 1),
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

    @property
    def byte_length(self) -> int:
        return self._type.size

    def to_bytes(self, size: Optional[int]=None) -> bytes:
        """Get the byte representation of this integer literal.

        :param size: Size to output, if None use size of type"""
        size = self._type.size if size is None else size
        return self.lit.to_bytes(size, "little", signed=self._type.signed)

    def compile_to_var(self, ctx: CompileContext) -> Variable:
        return ctx.compiler.add_bytes(self.to_bytes())

    @with_ctx
    async def compile(self, ctx: CompileContext) -> Register:
        reg = ctx.get_register(self._type.size, self._type.signed)
        ctx.emit(Mov(reg, Immediate(self.lit, self._type.size)))
        return reg


class Identifier(ExpressionObject):
    def __init__(self, name: str, ast: Optional[AST]=None):
        super().__init__(ast)
        self.name = name
        self.var = None

    @property
    @coroutine  # these have to be coroutines since we 'yield' inside them and return a value
    def type(self):
        if self.var is None:
            self.var = yield ObjectRequest(self.name)
        return self.var.type

    @coroutine
    def retrieve_variable(self) -> Coroutine[ObjectRequest, Variable, Tuple[Register, Variable]]:
        if self.var is None:
            self.var = yield ObjectRequest(self.name)
        return self.var

    async def load_lvalue(self, ctx: CompileContext) -> Register:
        var = await self.retrieve_variable()

        reg = ctx.get_register(types.Pointer(self.var.type).size)
        ctx.emit(LoadVar(var, reg, lvalue=True))
        return reg

    @with_ctx
    async def compile(self, ctx: CompileContext) -> Register:
        var = await self.retrieve_variable()
        reg = ctx.get_register(types.Pointer(self.var.type).size)

        ctx.emit(LoadVar(var, reg))
        return reg


class ArrayLiteral(ExpressionObject, LiteralObject):
    def __init__(self, exprs: List[ExpressionObject], ast: Optional[AST]=None):
        super().__init__(ast)
        self.exprs = exprs

        self._type = None

    @property
    async def type(self) -> Union[types.Array, types.Pointer]:
        if self._type is None:
            self._type = types.Pointer((await self.first_elem.type), const=True)
        return self._type

    @property
    def is_pointer(self):
        # Are we a pointer type (nested arrays should be referenced)
        return isinstance(self._type, types.Pointer)

    @property
    def is_array(self):
        # Are we an array type (nested arrays should be inlined)
        return isinstance(self._type, types.Array)

    @property
    def first_elem(self):
        return self.exprs[0]

    def fill_types(self, type: types.Type, size: int, length: int):
        """Fill in the types and size of a nested array."""
        # TODO: me
        pass

    def compile_to_list(self, ctx: CompileContext) -> List[Union[Variable, bytes]]:
        if self.is_array:
            return list(chain.from_iterable(i.compile_to_list(ctx) for i in self.exprs))
        if self.is_pointer:
            return [i.compile_to_var(ctx) for i in self.exprs]

    def compile_to_var(self, ctx: CompileContext) -> Variable:
        if isinstance(self.first_elem, ArrayLiteral):
            return ctx.compiler.add_array(self.compile_to_list(ctx))
        if isinstance(self.first_elem, LiteralObject):
            return ctx.compiler.add_array([i.to_bytes() for i in self.exprs])

        raise InternalCompileException("Cannot compile this!")

    async def compile_as_array_of_pointer(self, ctx: CompileContext):
        if isinstance(self.first_elem, LiteralObject):
            return [i.compile_to_var(ctx) for i in self.exprs]

