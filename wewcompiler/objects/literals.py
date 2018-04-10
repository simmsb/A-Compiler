from typing import List, Tuple, Union, Optional, Coroutine
from types import coroutine

from wewcompiler.objects import types, operations
from wewcompiler.objects.base import (CompileContext, ExpressionObject,
                                      ObjectRequest, with_ctx)
from wewcompiler.objects.variable import Variable
from wewcompiler.objects.ir_object import Immediate, LoadVar, Mov, Register, Binary, Resize, Dereference

from tatsu.ast import AST


class SizeOf(ExpressionObject):

    __slots__ = ("obj",)

    def __init__(self, obj: Union[types.Type, ExpressionObject], *, ast: Optional[AST]=None):
        super().__init__(ast=ast)
        self.obj = obj

    @property
    async def type(self):
        return types.Int.fromsize(8)  # maybe someone will make a massive array

    @with_ctx
    async def compile(self, ctx: CompileContext) -> Variable:
        if isinstance(self.obj, ExpressionObject):
            size = await self.obj.size
        else:
            size = self.obj.size
        ex = IntegerLiteral(size, types.Int.fromsize(8), ast=self.ast)
        return await ex.compile(ctx)


class IntegerLiteral(ExpressionObject):

    __slots__ = ("lit", "_type")

    def __init__(self, lit: int, type: Optional[types.Type]=None, *, ast: Optional[AST]=None):
        super().__init__(ast=ast)
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

    __slots__ = ("name", "var")

    def __init__(self, name: str, *, ast: Optional[AST]=None):
        super().__init__(ast=ast)
        assert isinstance(name, str)
        self.name = name
        self.var = None

    @property
    async def type(self):
        return (await self.retrieve_variable()).type

    # these have to be 'coroutine' functions instead of async
    # since we 'yield' inside them and return a value
    @coroutine
    def retrieve_variable(self) -> Coroutine[ObjectRequest, Variable, Tuple[Register, Variable]]:
        if self.var is None:
            self.var = yield ObjectRequest(self.name)
        return self.var

    async def load_lvalue(self, ctx: CompileContext) -> Register:
        var = await self.retrieve_variable()

        # if we load the lvalue when requested, error here since this is disallowed
        if var.lvalue_is_rvalue:
            raise self.error(f"Variable has no lvalue information.")
        reg = ctx.get_register(types.Pointer(self.var.type).size)
        ctx.emit(LoadVar(var, reg, lvalue=True))
        return reg

    @with_ctx
    async def compile(self, ctx: CompileContext) -> Register:
        var = await self.retrieve_variable()
        reg = ctx.get_register(var.type.size, var.type.signed)  # explicitly use the type size not the var size

        ctx.emit(LoadVar(var, reg))
        return reg


class ArrayLiteral(ExpressionObject):

    __slots__ = ("exprs", "_type", "var", "_ptr", "float_size")

    def __init__(self, exprs: List[ExpressionObject], *, ast: Optional[AST]=None):
        super().__init__(ast=ast)
        assert isinstance(exprs, list)
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
        self._ptr = False
        self.float_size = 0

    @property
    async def type(self) -> types.Array:
        elem_type = await self.first_elem.type
        if self._ptr:
            return types.Pointer(elem_type, const=True)
        # array types dont get const since they have an automatic location on the stack
        return types.Array(elem_type, len(self.exprs))

    @property
    def first_elem(self):
        return self.exprs[0]

    async def to_ptr(self):
        """Convert this array to a pointer type.

        The logic of this is that something of type [*u8] is array of pointer to char,
        but should be able to be declared like: {"aaa", "bbb", "ccc"}.

        Ofcourse this only works in declarations where we can edit the types on the right hand side.

        When being compiled, we look at ourselves to see if we're pointer type or array type.

        If we're pointer type we allocate an array of size to fit each element and
        compile each of our elements and emit writes for them.

        If we're an array we pull out the inside array elements to the outer level
        """
        self._ptr = True

    async def check_types(self, type: types.Type):
        self_type = await self.type
        if not self_type.implicitly_casts_to(type):
            raise self.error(f"Cannot implicitly cast type: {self_type} to type: {type}")

        if isinstance(type, types.Array) and type.length is not None and type.length < len(self.exprs):
            raise self.error(f"Length of this array is constrained to {self_type.length}")

        if isinstance(self.first_elem, ArrayLiteral):
            first_elem_size = (await self.first_elem.type).size

            for i in self.exprs:
                if (await i.type).size > first_elem_size:
                    raise i.error(f"Element sizes of this array are constrained to {first_elem_size} by the first element.")
                await i.check_types(type.to)
        else:
            for idx, i in enumerate(self.exprs):
                e_type = await i.type
                if not e_type.implicitly_casts_to(type.to):
                    raise i.error(f"Cannot implicitly cast element {idx} of array literal from type: '{e_type}' to type: '{type.to}'")


    async def broadcast_length(self, length: Optional[int] = None):
        """Broadcast fill lengths to internal arrays.

        This should be done after inserting array types and also after typechecking.
        """

        if length is not None:
            self.float_size = length - len(self.exprs)

        if (not isinstance(self.first_elem, ArrayLiteral)) or (not isinstance((await self.type).to, types.Array)):
            return

        first_elem_len = len(self.first_elem.exprs)

        for i in self.exprs:
            await i.broadcast_length(first_elem_len)


    async def insert_type(self, type: types.Type):
        # this inserts a nested type into a nested initialiser.
        # this should be done before type checking the array so that
        # `var a: [[[u8]]] = {some_variable, some_other_variable}` can't be valid
        # but `var a: [*[u8]] = {some_variable, some_other_variable}` can be

        if not isinstance(type, (types.Array, types.Pointer)):
            raise self.error("Cannot transmit non-array/pointer type to array.")

        if isinstance(type, types.Pointer):
            await self.to_ptr()

        elif type.length is not None:
            (await self.type).length = type.length

        if not isinstance(self.first_elem, ArrayLiteral):

            for i in self.exprs:
                if not (await i.type).implicitly_casts_to(type.to):
                    return

            # if we can cast the inner elements of the array:
            # wrap our expressions inside casts
            # otherwise fail and let an error be emitted from the type check stage
            self.exprs = [
                operations.CastExprOP(type.to, i, ast=i.ast)
                for i in self.exprs
            ]

            return  # got to end of array literals

        for i in self.exprs:
            await i.insert_type(type.to)


    async def compile_as_ref(self, ctx: CompileContext) -> Register:
        """Compile to the array literal and return a reference to the start.

        This function is for when an array of references is the wanted outcome.
        This function will not work on array types.
        """

        if self.var is None:
            self.var = ctx.declare_unique_variable(await self.type)
            self.var.lvalue_is_rvalue = True

        if (isinstance(self.first_elem, ArrayLiteral) and
                (not isinstance((await self.type).to, types.Pointer))):
            raise self.error("Cannot compile to references if internal array type is an array and not a pointer")

        base = ctx.get_register(types.Pointer.size)
        index = ctx.get_register(types.Pointer.size)

        ctx.emit(LoadVar(self.var, base))
        ctx.emit(Mov(index, base))

        elem_type = (await self.type).to

        for i in self.exprs:
            r = await i.compile(ctx)

            if r.size != elem_type.size:
                r0 = r.resize(elem_type.size, elem_type.signed)
                ctx.emit(Resize(r, r0))
                r = r0

            ctx.emit(Mov(Dereference(index, r.size), r))
            ctx.emit(Binary.add(index, Immediate(r.size, types.Pointer.size)))

        if self.float_size:
            # fill in missing values
            ctx.emit(Binary.add(index, Immediate(elem_type.size * self.float_size, index.size)))

        return base

    async def compile_as_arr(self, ctx: CompileContext) -> Register:
        """Compile an array literal but inline the inner values."""

        if (isinstance((await self.type).to, types.Array) and
                (not isinstance(self.first_elem, ArrayLiteral))):
            # Maybe just cast the internal type to a pointer.
            raise self.error("Internal type is of array type but is not a literal.")

        if self.var is None:
            self.var = ctx.declare_unique_variable(await self.type)
            self.var.lvalue_is_rvalue = True

        base = ctx.get_register(types.Pointer.size)
        index = ctx.get_register(types.Pointer.size)

        ctx.emit(LoadVar(self.var, base))
        ctx.emit(Mov(index, base))

        elem_size = (await self.type).to.size

        for i in self.exprs:
            await i.compile_as_arr_helper(ctx, index)


        # NOTE: will we ever hit this?
        if self.float_size:
            ctx.emit(Binary.add(index, Immediate(elem_size * self.float_size)))

        return base

    async def compile_as_arr_helper(self, ctx: CompileContext, base: Register):
        if isinstance(self.first_elem, ArrayLiteral) and isinstance(await self.type, types.Array):
            for i in self.exprs:
                await i.compile_as_arr_helper(ctx, base)
        else:
            elem_type = (await self.type).to
            for i in self.exprs:
                r = await i.compile(ctx)
                if r.size != elem_type.size:
                    r0 = r.resize(elem_type.size, elem_type.signed)
                    ctx.emit(Resize(r, r0))
                    r = r0
                ctx.emit(Mov(Dereference(base, r.size), r))
                ctx.emit(Binary.add(base, Immediate(r.size, types.Pointer.size)))

    async def compile(self, ctx: CompileContext) -> Register:
        my_type = await self.type

        if isinstance(my_type, types.Array):
            length = my_type.length
        else:
            length = None

        await self.broadcast_length(length)

        if isinstance(my_type.to, types.Array):
            return await self.compile_as_arr(ctx)
        return await self.compile_as_ref(ctx)
