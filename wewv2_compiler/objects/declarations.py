import types
from typing import Optional

from tatsu.ast import AST
from wewv2_compiler.objects.base import (CompileContext, ExpressionObject,
                                         Scope, StatementObject, Variable)
from wewv2_compiler.objects.irObject import (Dereference, Mov, Pop, Prelude,
                                             Push, Register, Return, SaveVar)
from wewv2_compiler.objects.types import Type


class FunctionDeclare(Scope):
    """Function definition object.

    Function definitions should expand to a declaration with assignment to a const global variable with the name of the function.


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
        self._type = types.Function(ast.r, [i.t for i in ast.params], True)
        # should functions be naturally const?

    @property
    def type(self):
        return self._type

    @property
    def identifier(self) -> str:
        return self.name

    def lookup_variable(self, name: str) -> Variable:
        v = super().lookup_variable(name)
        if v is None:
            return self.params.get(name)

    def compile(self, ctx: CompileContext):
        ctx.emit(Prelude())
        yield from super().compile(ctx)
        ctx.emit(Return())


class VariableDecl(StatementObject):

    def __init__(self, ast: AST):
        super().__init__(ast)
        self.name = ast.name
        self._type = ast.typ
        self.val: Optional[ExpressionObject] = ast.val

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
        if isinstance(self.val, ExpressionObject):
            reg = yield from self.val.compile(ctx)
            ctx.emit(SaveVar(var, reg))
        # otherwise do nothing
