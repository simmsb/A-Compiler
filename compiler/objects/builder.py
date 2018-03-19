# pylint: disable=no-self-use
import sys

from compiler.objects.base import FunctionDecl, Scope
from compiler.objects.literals import (ArrayLiteral, Identifier,
                                       IntegerLiteral, StringLiteral,
                                       char_literal)
from compiler.objects.operations import (AssignOp, BinAddOp, BinMulOp,
                                         BinRelOp, BinShiftOp, BitwiseOp,
                                         BoolCompOp, unary_postfix,
                                         unary_prefix, BinaryExpression)
from compiler.objects.statements import (IFStmt, LoopStmt, ReturnStmt,
                                         VariableDecl)
from compiler.objects.types import Array, Function, Int, Pointer, Type, Void

from tatsu.ast import AST


sys.setrecursionlimit(10000)  # this goes deep


def resolve_left_assoc(builder_fun: BinaryExpression, ast):
    # we end up with an ast looking like:
    # {'left': expr, 'rest': [{'op': ..., 'right': expr}, ...]}
    #
    # go from left right, add the result of the last expression as the 'left' of the current

    assert isinstance(ast, AST)
    assert ast.rest is not None

    operations = iter(ast.rest)

    node = ast.left

    for i in operations:
        node = builder_fun(i.op, node, i.right)

    return node


class WewSemantics(object):
    def start(self, ast):
        return ast

    def base_type(self, ast):
        return Int(ast.t, ast=ast)

    def void_type(self, ast):
        return Void(ast=ast)

    def ptr_type(self, ast):
        return Pointer(ast.t, ast=ast)

    def const_type(self, typ):
        assert isinstance(typ.t, Type)

        typ.t.const = True
        return typ.t

    def array_type(self, ast):
        return Array(ast.t, ast.s, ast=ast)

    def fun_type(self, ast):
        return Function(ast.r, ast.t, ast=ast)

    def type(self, ast):
        return ast

    def statement(self, ast):
        if isinstance(ast, list):
            return ast[0]
        return ast

    def scope(self, ast):
        return Scope(ast)

    def if_stmt(self, ast):
        # we build elif's recursively from the right
        node = ast.f
        for i in reversed(ast.elf):
            i["f"] = node
            node = IFStmt(i)
        if ast.elf:
            del ast["f"]
            ast["f"] = node
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

    def boolean(self, ast):
        return BoolCompOp(ast)

    def bitwise(self, ast):
        return resolve_left_assoc(BitwiseOp, ast)

    def equality(self, ast):
        return resolve_left_assoc(BinRelOp, ast)

    def relation(self, ast):
        return resolve_left_assoc(BinRelOp, ast)

    def bitshift(self, ast):
        return resolve_left_assoc(BinShiftOp, ast)

    def additive(self, ast):
        return resolve_left_assoc(BinAddOp, ast)

    def multiply(self, ast):
        return resolve_left_assoc(BinMulOp, ast)

    def prefix(self, ast):
        # negation operator applied to an integer literal makes it negative and signed
        if isinstance(ast.right, IntegerLiteral) and ast.op == "-":
            ast.right.lit = -ast.right.lit
            ast.right._type.sign = True
            return ast.right
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
