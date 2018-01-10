# pylint: disable=no-self-use
from compiler.objects.base import FunctionDecl, Scope
from compiler.objects.literals import (ArrayLiteral, Identifier,
                                       IntegerLiteral, StringLiteral,
                                       char_literal)
from compiler.objects.operations import (AssignOp, BinAddOp, BinMulOp,
                                         BinRelOp, BinShiftOp, BitwiseOp,
                                         BoolCompOp, unary_postfix,
                                         unary_prefix)
from compiler.objects.statements import (IFStmt, LoopStmt, ReturnStmt,
                                         VariableDecl)
from compiler.objects.types import Array, Function, Int, Pointer, Type


class WewSemantics(object):
    def start(self, ast):
        return ast

    def base_type(self, ast):
        return Int(ast)

    def ptr_type(self, ast):
        return Pointer(ast.t)

    def const_type(self, typ):
        assert isinstance(typ.t, Type)

        typ.t.const = True
        return typ.t

    def array_type(self, ast):
        return Array(ast.t, ast.s)

    def fun_type(self, ast):
        return Function(ast.r, ast.t)

    def type(self, ast):
        return ast

    def statement(self, ast):
        if isinstance(ast, list):
            return ast[0]
        return ast

    def scope(self, ast):
        return Scope(ast)

    def if_stmt(self, ast):
        return IFStmt(ast)

    def loop_stmt(self, ast):
        return LoopStmt(ast)

    def return_stmt(self, ast):
        return ReturnStmt(ast)

    def expr(self, ast):
        return ast

    def fun_decl(self, ast):
        return FunctionDecl(ast)

    def var_decl(self, ast):
        return VariableDecl(ast)

    def optional_def(self, ast):
        return ast

    def decl(self, ast):
        # 'decl ;' results in [<decl>, ';']
        # but 'decl' results in <decl>
        if isinstance(ast, list):
            return ast[0]
        return ast

    def assign_expr(self, ast):
        return AssignOp(ast)

    def logical(self, ast):
        return ast

    def bitwise(self, ast):
        return BitwiseOp(ast)

    def boolean(self, ast):
        return BoolCompOp(ast)

    def comparison(self, ast):
        return ast

    def equality(self, ast):
        return BinRelOp(ast)

    def relation(self, ast):
        return BinRelOp(ast)

    def shift(self, ast):
        return ast

    def bitshift(self, ast):
        return BinShiftOp(ast)

    def binop(self, ast):
        return ast

    def additive(self, ast):
        return BinAddOp(ast)

    def multiplicative(self, ast):
        return ast

    def multiply(self, ast):
        return BinMulOp(ast)

    def unop(self, ast):
        return ast

    def prefix(self, ast):
        return unary_prefix(ast)

    def postfixexpr(self, ast):
        return ast

    def postfix(self, ast):
        # since we cant have left recursion we cant parse postfix operations recursively
        # instead we parse a list of expressions on the right hand side
        # then we unfold this by generating ast nodes from left to right
        final = ast.left
        for i in ast.exprs:
            i["left"] = final
            final = unary_postfix(i)
        return final

    def postop(self, ast):
        return ast

    def singular(self, ast):
        return ast

    def subexpr(self, ast):
        return ast

    def literal(self, ast):
        return ast

    def arr_lit(self, ast):
        return ArrayLiteral(ast)

    def int_lit(self, ast):
        return IntegerLiteral(ast)

    def int(self, ast):
        return int(ast)

    def str(self, ast):
        return StringLiteral(ast)

    def chr(self, ast):
        return char_literal(ast)

    def identifier(self, ast):
        return Identifier(ast)
