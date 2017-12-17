from compiler.objects.base import (CompileContext, ExpressionObject, Scope,
                                   StatementObject, Variable)
from compiler.objects.ir_object import (Binary, Dereference, Immediate,
                                        LoadVar, Mov, Register, Resize, Return,
                                        SaveVar)
from compiler.objects.literals import ArrayLiteral
from compiler.objects.types import Function, Pointer, Type
from typing import Optional

from tatsu.ast import AST


class FunctionDecl(Scope):
    """Function definition object.

    Function definitions should expand to a declaration with
    assignment to a const global variable with the name of the function.


    function params:

    | return_addr| p1 | p2 | p3 | p4 | stored_base_pointer | v1 | v2 | v3 |
    where pX = paramX from where p1 is the first param in the declaration, left to right
    where vX = localX where v1 is the first declared param in this scope.

    functions are called such that when execution jumps to the start of the functions
    the stack pointer is above the location to store the base pointer

    """

    def __init__(self, ast: AST):
        super().__init__(ast)
        self.name = ast.name
        self.params = [Variable(i.identifier, i.type) for i in ast.params]
        self._type = Function(ast.r, [i.t for i in ast.params], True)
        # should functions be naturally const?

    @property
    def type(self):
        return self._type

    @property
    def identifier(self) -> str:
        return self.name

    def lookup_variable(self, name: str) -> Optional[Variable]:
        v = super().lookup_variable(name)
        if v is None:
            return self.params.get(name)
        return None  # shut up pylint

    def compile(self, ctx: CompileContext):
        yield from super().compile(ctx)
        ctx.emit(Return())


class VariableDecl(StatementObject):

    def __init__(self, ast: AST):
        super().__init__(ast)
        self.name = ast.name
        self._type = ast.typ
        self.val: Optional[ExpressionObject] = ast.val

        if isinstance(self.val, ArrayLiteral):
            self.val.to_array()

        if self._type == "infer":
            self._type = self.val.type

    @property
    def type(self) -> Type:
        return self._type

    @property
    def identifier(self) -> str:
        return self.name

    def compile(self, ctx: CompileContext):
        var = ctx.declare_variable(self.name, self.type)
        if isinstance(self.val, ArrayLiteral):
            ptr = ctx.get_register(Pointer(self.val.type.t))
            ctx.emit(LoadVar(var, ptr, lvalue=True))
            for i in self.val.exprs:
                res = yield from i.compile(ctx)
                ctx.emit(Mov(Dereference(ptr), res))
                ctx.emit(Binary.add(ptr, Immediate(self.size, Pointer(var.type).size)))

        if isinstance(self.val, ExpressionObject):
            reg = yield from self.val.compile(ctx)
            ctx.emit(SaveVar(var, reg))
        # otherwise do nothing


class ReturnStmt(StatementObject):

    def __init__(self, ast: AST):
        super().__init__(ast)
        self.expr = ast.e

    @property
    def type(self) -> Type:
        return self.expr.type

    def compile(self, ctx: CompileContext):
        fn_type = yield from ctx.top_function.type
        reg = yield from self.expr.compile(ctx)
        for i in reversed(ctx.scope_stack):
            ctx.emit(i.make_epilog())
        if reg.size != fn_type.size:
            reg0 = reg.resize(fn_type.size)
            ctx.emit(Resize(reg, reg0))
            reg = reg0
        ctx.emit(Return(reg))
