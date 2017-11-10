import types
from typing import Optional

from wewv2_compiler.objects.base import CompileContext, Scope, Variable
from wewv2_compiler.objects.irObject import (Dereference, Mov, Pop, Push,
                                             Register, Ret)


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

    def __init__(self, ast):
        super().__init__(ast)
        self.name = ast.name
        self.params = [Variable(i.identifier, i.type) for i in ast.params]
        self.type = types.Function(ast.r, [i.t for i in ast.params], True)
        # should functions be naturally const?

    @property
    def identifier(self) -> str:
        return self.name

    def lookup_variable(self, ident: str) -> Optional[Variable]:
        v = super().lookup_variable(ident)
        if v is None:
            return self.params.get(ident)

    def compile(self, ctx: CompileContext):
        self.emit(Push(Register.baseptr))
        self.emit(Mov(Register.baseptr, Register.stackptr))
        yield from super().compile(ctx)
        self.emit(Mov(Register.stackptr, Register.baseptr))
        self.emit(Pop(Register.baseptr))
        self.emit(Ret())
