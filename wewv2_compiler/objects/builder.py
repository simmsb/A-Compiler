from wewv2_compiler.objects.declarations import FunctionDeclare
from wewv2_compiler.objects.literals import (Identifier, IntegerLiteral,
                                             StringLiteral, char_literal)
from wewv2_compiler.objects.operations import unary_postfix, unary_prefix

Class WewSemantics(object):
    def start(self, ast):  # noqa
        return ast

    def base_type(self, ast):  # noqa
        return ast

    def ptr_type(self, ast):  # noqa
        return ast

    def const_type(self, typ):  # noqa
        typ.const = True

    def array_type(self, ast):  # noqa
        return ast

    def fun_type(self, ast):  # noqa
        return ast

    def type(self, ast):  # noqa
        return ast

    def statement(self, ast):  # noqa
        return ast

    def scope(self, ast):  # noqa
        return ast

    def if_stmt(self, ast):  # noqa
        return ast

    def loop_stmt(self, ast):  # noqa
        return ast

    def return_stmt(self, ast):  # noqa
        return ast

    def expression_stmt(self, ast):  # noqa
        return ast

    def expr(self, ast):  # noqa
        return ast

    def fun_decl(self, ast):  # noqa
        return ast

    def var_decl(self, ast):  # noqa
        return ast

    def optional_def(self, ast):  # noqa
        return ast

    def decl(self, ast):  # noqa
        return ast

    def assign_expr(self, ast):  # noqa
        return ast

    def logical(self, ast):  # noqa
        return ast

    def bitwise(self, ast):  # noqa
        return ast

    def boolean(self, ast):  # noqa
        return ast

    def comparison(self, ast):  # noqa
        return ast

    def equality(self, ast):  # noqa
        return ast

    def relation(self, ast):  # noqa
        return ast

    def shift(self, ast):  # noqa
        return ast

    def bitshift(self, ast):  # noqa
        return ast

    def binop(self, ast):  # noqa
        return ast

    def additive(self, ast):  # noqa
        return ast

    def multiplicative(self, ast):  # noqa
        return ast

    def multiply(self, ast):  # noqa
        return ast

    def unop(self, ast):  # noqa
        return ast

    def prefix(self, ast):
        return unary_prefix(ast)

    def postfix(self, ast):
        return unary_postfix(ast)

    def postop(self, ast):  # noqa
        return ast

    def singular(self, ast):  # noqa
        return ast

    def subexpr(self, ast):  # noqa
        return ast

    def literal(self, ast):  # noqa
        return ast

    def arr_lit(self, ast):  # noqa
        return ast

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
