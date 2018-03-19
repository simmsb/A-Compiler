from types import coroutine
from itertools import chain

from compiler.objects import types
from compiler.objects.base import (CompileContext, ExpressionObject,
                                   ObjectRequest, with_ctx)
from compiler.objects.variable import Variable
from compiler.objects.ir_object import Immediate, LoadVar, Mov, Register, Binary, Resize, Dereference
from typing import List, Tuple, Union, Optional, Coroutine

from tatsu.ast import AST


class IntegerLiteral(ExpressionObject):
    def __init__(self, lit: int, type: Optional[types.Type], ast: Optional[AST]=None):
        super().__init__(ast)
        self.lit = lit
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


class ArrayLiteral(ExpressionObject):
    def __init__(self, exprs: List[ExpressionObject], ast: Optional[AST]=None):
        super().__init__(ast)
        self.exprs = exprs
        self._type = None

        # For arrays we have to be special
        # When used on the right hand side of a variable declaration
        # the declaration will set the location for the array to be created.
        # if this is not set (and the array is not on the right hand side of a variable declaration)
        # then the array will allocate a hidden local for itself and that will be the location
        #
        # As a consequence of this, all arrays are built at runtime
        # In the future we could do some static analysis on the contents of the array and see if we can
        # pull out the contents into a static value.
        #
        # To make sure that this stuff is safe arrays default to being const type at all levels so that
        # assigning to elements of a literal array is not possible
        # ( `({1, 2}[0] = 3)` will be a compile time error)
        self.var: Variable = None

    @property
    async def type(self) -> types.Array:
        if self._type is None:
            self._type = types.Array((await self.first_elem.type), len(self.exprs), const=True)
        return self._type

    def to_ptr(self):
        """Convert this array to a pointer type.

        The logic of this is that something of type [*u8] is array of pointer to char,
        but should be able to be declared like: {"aaa", "bbb", "ccc"}.

        Ofcourse this only works in declarations where we can edit the types on the right hand side.

        When being compiled, we look at ourselves to see if we're pointer type or array type.

        If we're pointer type we allocate an array of size to fit each element and
        compile each of our elements and emit writes for them.

        If we're an array we pull out the inside array elements to the outer level
        """
        self._type = types.Pointer(self._type.to, const=True)


    def insert_type(self, type: types.Type):
        # this inserts a nested type into a nested initialiser.
        # this should be done before type checking the array so that
        # `var a: [[[u8]]] = {some_variable, some_other_variable}` can't be valid
        # but `var a: [*[u8]] = {some_variable, some_other_variable}` can be

        if not isinstance(self.first_elem, ArrayLiteral):
            return  # got to end of array literals

        if not isinstance(type, (types.Array, types.Pointer)):
            raise self.error("Cannot transmit non-array/pointer type to array.")

        if isinstance(type, types.Pointer):
            self.to_ptr()

        # we default to array so we wont have a to_array case

        for i in self.exprs:
            i.insert_type(type.to)


    # TODO:
    #
    #  Build if we're the outermost array (this is when we use the 'var' variable)
    #  Build if we're an inner array where we get a location to write pointers to.
    #  We dont need a 'inner array fn' where we are an array since the outer array
    #    *will* gather our elements for us.
    #

    #
    #   given {"aaa", "bbb"}
    #
    #   char *x[] = [*u8], {*ptr, *ptr}, size = 2 * ptr
    #   char x[][] = {"aaa\0" "bbb\0"}, size = 2 * 4 * u8
    #


    @property
    def first_elem(self):
        return self.exprs[0]

    def fill_types(self, type: types.Type, size: int, length: int):
        """Fill in the types and size of a nested array."""
        # TODO: me
        pass

