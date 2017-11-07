from base import CompileContext, Scope
from irObject import IRObject


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
        self.params = ast.params
        self.type = ast.r

    @property
    def identifier(self):
        return self.name

    def lookup_variable(self, ident):
        v = super().lookup_variable(ident)
        if v is None:
            return self.params.get(ident)

    def compile(self, ctx: CompileContext):
        yield IRObject("push", "rpb")
        # stk being the stack pointer and rpb being the base pointer
        yield IRObject("mov", "rpb", "stk")
        yield from super().compile(ctx)
        yield IRObject("ret", sum(i.size for i in self.params))
