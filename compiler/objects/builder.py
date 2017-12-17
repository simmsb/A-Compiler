# pylint: disable=no-self-use
from compiler.objects.base import Scope
from compiler.objects.literals import (ArrayLiteral, Identifier,
                                       IntegerLiteral, StringLiteral,
                                       char_literal)
from compiler.objects.operations import BinAddOp, unary_postfix, unary_prefix
from compiler.objects.statements import FunctionDecl, ReturnStmt, VariableDecl
from compiler.objects.types import Array, Function, Int, Pointer


class WewSemantics(object):
    def start(self, ast):
        return ast

    def base_type(self, ast):
        return Int(ast.base_type)

    def ptr_type(self, ast):
        return Pointer(ast.t)

    def const_type(self, typ):
        typ.const = True
        return typ

    def array_type(self, ast):
        return Array(ast.t, ast.s)

    def fun_type(self, ast):
        return Function(ast.r, ast.t)

    def type(self, ast):
        return ast

    def statement(self, ast):
        return ast

    def scope(self, ast):
        return Scope(ast)

    def if_stmt(self, ast):
        return ast

    def loop_stmt(self, ast):
        return ast

    def return_stmt(self, ast):
        return ReturnStmt(ast)

    def expression_stmt(self, ast):
        return ast

    def expr(self, ast):
        return ast

    def fun_decl(self, ast):
        return FunctionDecl(ast)

    def var_decl(self, ast):
        return VariableDecl(ast)

    def optional_def(self, ast):
        return ast

    def decl(self, ast):
        return ast

    def assign_expr(self, ast):
        return ast

    def logical(self, ast):
        return ast

    def bitwise(self, ast):
        return ast

    def boolean(self, ast):
        return ast

    def comparison(self, ast):
        return ast

    def equality(self, ast):
        return ast

    def relation(self, ast):
        return ast

    def shift(self, ast):
        return ast

    def bitshift(self, ast):
        return ast

    def binop(self, ast):
        return ast

    def additive(self, ast):
        return BinAddOp(ast)

    def multiplicative(self, ast):
        return ast

    def multiply(self, ast):
        return ast

    def unop(self, ast):
        return ast

    def prefix(self, ast):
        return unary_prefix(ast)

    def postfix(self, ast):
        return unary_postfix(ast)

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
        return int(ast.int)

    def str(self, ast):
        return StringLiteral(ast)

    def chr(self, ast):
        return char_literal(ast)

    def identifier(self, ast):
        return Identifier(ast)
