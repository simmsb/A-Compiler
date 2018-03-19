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
            self._type = types.Pointer((await self.exprs[0].type), const=True)
        return self._type

    @property
    def byte_length(self):
        return (self.exprs[0].byte_length) * len(self.exprs)

    async def to_array(self):
        """Convert type to array object from pointer object.

        :param subtype: The type of the inner element to this array.
        """

        # traverse down our tree setting to array types, stop when we hit something that isn't an array
        if isinstance(self.exprs[0], ArrayLiteral):
            for i in self.exprs:
                await i.to_array()

        self._type = types.Array(self.exprs[0].type, len(self.exprs))

    async def check_types(self):
        # used in literals only
        my_type = (await self.type).to
        # XXX: this will break in py3.7, change to a manual for loop instead
        expr_types = [(await i.type) for i in self.exprs]
        if not all(i.implicitly_casts_to(my_type) for i in expr_types):
            raise self.error(f"Conflicting array literal types.")


    async def build_to_type(self, ctx: CompileContext, type: types.Type, base_address: Register):
        """Build for a type.

        Used when initialising only

        :param type: The type we should build to,
            Array means we write our arguments to the base_address
            Pointer means we should just use the ArrayLiteral compile and do the LoadVar stuff

        If asked to build to an array, we go over the elements and ask them to build to a location.
        """

        # Building for an array
        if isinstance(type, types.Array):
            # if the sub-type is also an array, build that to the underlying type
            if isinstance(self.exprs[0], ArrayLiteral):
                for i in self.exprs:
                    await i.build_to_type(ctx, type.to, base_address)
                    ctx.emit(Binary.add(base_address, type.to.size))
            # if the sub-type is not an array, just compile each sub-element and write the value
            else:
                for i in self.exprs:
                    res = await i.compile(ctx)
                    if res.size != type.to.size:
                        res0 = res.resize(type.to.size, type.to.signed)
                        ctx.emit(Resize(res, res0))
                        res = res0
                    ctx.emit(Mov(Dereference(base_address, res.size), res))
                    ctx.emit(Binary.add(base_address, res.size))
        # Building for a pointer
        else:
            res = await self.compile(ctx)
            ctx.emit(Mov(Dereference(base_address, res.size), res))
            ctx.emit(Binary.add(base_address, res.size))


    # FIXME: Only do this if we are an array type but being pointed to (WHAT???)
    def to_bytes(self, size: Optional[int]=None) -> bytes:
        innersize = self.exprs[0].byte_length

        if size and innersize * len(self.exprs) > size:
            raise self.error(f"Array size too large to fit in: {size}")

        return b"".join(i.to_bytes(innersize) for i in self.exprs)

    @with_ctx
    async def compile(self, ctx: CompileContext) -> Register:
        #  this is only run if we're not in the form of a array initialisation.
        #  check that everything is a constant
        my_type = (await self.type).to
        await self.check_types()


        # What were we doing???
        # Working on getting 2d arrays and bytes and stuff working
        # ARRAYS SHOULD ALLOW FOR VARIABLE REFERENCES DEFAULT TO POINTER TYPE THANKS


        for i in self.exprs:
            if not isinstance(i, LiteralObject):
                raise i.error("Array literal element is non-constant")

        # if we are an array of arrays, gather out the inner elements

        byts = self.build_bytes()
        var = ctx.compiler.add_bytes(byts)

        reg = ctx.get_register(var.size)
        ctx.emit(LoadVar(var, reg))
        return reg


class StringLiteral(ArrayLiteral):

    def __init__(self, lit: str, ast: Optional[AST]=None):
        super().__init__(ast)
        self.lit = literal_eval(lit) + "\0"
        self.exprs = [
            IntegerLiteral()
        ]

    @property
    async def type(self):
        return types.string_lit

    @property
    def byte_length(self):
        return len(self.lit)

    def to_bytes(self, size: Optional[int]=None) -> bytes:
        # can't allocate if too small size requested
        if (size is not None) and (len(self) + 1 > size):
            raise self.error(f"String literal too large to be placed in buffer of size: {size}")
        return "{:\0<{size}}".format(self.lit, size=size).encode("utf-8")


    @with_ctx
    async def compile(self, ctx: CompileContext) -> Register:
        var = ctx.compiler.add_string(literal_eval(self.lit))
        var.lvalue_is_rvalue = True
        reg = ctx.get_register((await self.size))
        ctx.emit(LoadVar(var, reg))
        return reg



def char_literal(ast):
    ast.val = ord(ast.chr)
    ast.size = types.const_char.size
    return IntegerLiteral(ast)
