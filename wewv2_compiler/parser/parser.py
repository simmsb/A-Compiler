#!/usr/bin/env python
# -*- coding: utf-8 -*-

# CAVEAT UTILITOR
#
# This file was automatically generated by TatSu.
#
#    https://pypi.python.org/pypi/tatsu/
#
# Any changes you make to it will be overwritten the next time
# the file is generated.


from __future__ import print_function, division, absolute_import, unicode_literals

import sys

from tatsu.buffering import Buffer
from tatsu.parsing import Parser
from tatsu.parsing import tatsumasu
from tatsu.util import re, generic_main  # noqa


KEYWORDS = {}  # type: ignore


class WewBuffer(Buffer):
    def __init__(
        self,
        text,
        whitespace=None,
        nameguard=None,
        comments_re='{~(\\n|.)*~}',
        eol_comments_re='\\/\\/.*?$',
        ignorecase=None,
        namechars='',
        **kwargs
    ):
        super(WewBuffer, self).__init__(
            text,
            whitespace=whitespace,
            nameguard=nameguard,
            comments_re=comments_re,
            eol_comments_re=eol_comments_re,
            ignorecase=ignorecase,
            namechars=namechars,
            **kwargs
        )


class WewParser(Parser):
    def __init__(
        self,
        whitespace=None,
        nameguard=None,
        comments_re='{~(\\n|.)*~}',
        eol_comments_re='\\/\\/.*?$',
        ignorecase=None,
        left_recursion=True,
        parseinfo=True,
        keywords=None,
        namechars='',
        buffer_class=WewBuffer,
        **kwargs
    ):
        if keywords is None:
            keywords = KEYWORDS
        super(WewParser, self).__init__(
            whitespace=whitespace,
            nameguard=nameguard,
            comments_re=comments_re,
            eol_comments_re=eol_comments_re,
            ignorecase=ignorecase,
            left_recursion=left_recursion,
            parseinfo=parseinfo,
            keywords=keywords,
            namechars=namechars,
            buffer_class=buffer_class,
            **kwargs
        )

    @tatsumasu()
    def _start_(self):  # noqa

        def block0():
            self._statement_()
        self._positive_closure(block0)
        self._check_eof()

    @tatsumasu()
    def _base_type_(self):  # noqa
        with self._choice():
            with self._option():
                self._token('u2')
            with self._option():
                self._token('u4')
            with self._option():
                self._token('s2')
            with self._option():
                self._token('s4')
            self._error('no available options')

    @tatsumasu()
    def _ptr_type_(self):  # noqa
        self._token('*')
        self._type_()
        self.name_last_node('t')
        self.ast._define(
            ['t'],
            []
        )

    @tatsumasu()
    def _array_type_(self):  # noqa
        self._token('[')
        self._type_()
        self.name_last_node('t')
        self._token(']')
        with self._optional():
            self._token('@')
            self._int_()
            self.name_last_node('s')
        self.ast._define(
            ['s', 't'],
            []
        )

    @tatsumasu()
    def _fun_type_(self):  # noqa
        self._token('(')

        def sep1():
            self._token(',')

        def block1():
            self._type_()
        self._gather(block1, sep1)
        self.name_last_node('t')
        self._token(')')
        self._token('->')
        self._type_()
        self.name_last_node('r')
        self.ast._define(
            ['r', 't'],
            []
        )

    @tatsumasu()
    def _type_(self):  # noqa
        with self._choice():
            with self._option():
                self._base_type_()
            with self._option():
                self._ptr_type_()
            with self._option():
                self._array_type_()
            with self._option():
                self._fun_type_()
            with self._option():
                self._token('(')
                self._type_()
                self._token(')')
            self._error('no available options')

    @tatsumasu()
    def _statement_(self):  # noqa
        with self._choice():
            with self._option():
                self._scope_()
            with self._option():
                self._if_stmt_()
            with self._option():
                self._loop_stmt_()
            with self._option():
                self._return_stmt_()
            with self._option():
                self._expression_stmt_()
            self._error('no available options')

    @tatsumasu()
    def _scope_(self):  # noqa
        self._token('{')

        def block1():
            self._statement_()
        self._positive_closure(block1)
        self.name_last_node('body')
        self._token('}')
        self.ast._define(
            ['body'],
            []
        )

    @tatsumasu()
    def _if_stmt_(self):  # noqa
        self._token('if')
        self._cut()
        self._token('(')
        self._expr_()
        self.name_last_node('e')
        self._token(')')
        self._scope_()
        self.name_last_node('t')
        with self._optional():
            self._token('else')
            self._scope_()
            self.name_last_node('f')
        self.ast._define(
            ['e', 'f', 't'],
            []
        )

    @tatsumasu()
    def _loop_stmt_(self):  # noqa
        self._token('while')
        self._cut()
        self._token('(')
        self._expr_()
        self.name_last_node('e')
        self._token(')')
        self._token('{')

        def block2():
            self._statement_()
        self._positive_closure(block2)
        self.name_last_node('body')
        self._token('}')
        self.ast._define(
            ['body', 'e'],
            []
        )

    @tatsumasu()
    def _return_stmt_(self):  # noqa
        self._token('return')
        self._cut()
        self._expr_()
        self.name_last_node('e')
        self._token(';')
        self.ast._define(
            ['e'],
            []
        )

    @tatsumasu()
    def _expression_stmt_(self):  # noqa
        self._expr_()
        self._token(';')

    @tatsumasu()
    def _expr_(self):  # noqa
        with self._choice():
            with self._option():
                self._decl_()
            with self._option():
                self._assign_expr_()
            with self._option():
                self._logical_()
            self._error('no available options')

    @tatsumasu()
    def _fun_decl_(self):  # noqa
        self._token('fn')
        self._cut()
        self._identifier_()
        self.name_last_node('name')
        self._token('(')

        def sep2():
            self._token(',')

        def block2():
            self._identifier_()
            self.name_last_node('n')
            self._token(':')
            self._type_()
            self.name_last_node('t')
        self._gather(block2, sep2)
        self.name_last_node('args')
        self._token(')')
        self._token('->')
        self._type_()
        self.name_last_node('r')
        self._token('>')
        self._token('{')

        def block7():
            self._statement_()
        self._positive_closure(block7)
        self.name_last_node('body')
        self._token('}')
        self.ast._define(
            ['args', 'body', 'n', 'name', 'r', 't'],
            []
        )

    @tatsumasu()
    def _var_decl_(self):  # noqa
        self._token('var')
        self._cut()
        self._identifier_()
        self.name_last_node('name')
        self._optional_def_()
        self.name_last_node('init')
        self.ast._define(
            ['init', 'name'],
            []
        )

    @tatsumasu()
    def _optional_def_(self):  # noqa
        with self._choice():
            with self._option():
                self._token(':')
                self._type_()
                self.name_last_node('typ')
                with self._optional():
                    self._token('=')
                    self._expr_()
                    self.name_last_node('val')
            with self._option():
                self._token(':=')
                self._cut()
                self._expr_()
                self.name_last_node('val')
                self._constant('infer')
                self.name_last_node('typ')
            self._error('no available options')
        self.ast._define(
            ['typ', 'val'],
            []
        )

    @tatsumasu()
    def _decl_(self):  # noqa
        with self._choice():
            with self._option():
                self._fun_decl_()
            with self._option():
                self._var_decl_()
            self._error('no available options')

    @tatsumasu()
    def _assign_expr_(self):  # noqa
        self._logical_()
        self.name_last_node('left')
        self._token('=')
        self.name_last_node('op')
        self._expr_()
        self.name_last_node('right')
        self.ast._define(
            ['left', 'op', 'right'],
            []
        )

    @tatsumasu()
    def _logical_(self):  # noqa
        with self._choice():
            with self._option():
                self._bitwise_()
            with self._option():
                self._boolean_()
            with self._option():
                self._comparison_()
            self._error('no available options')

    @tatsumasu()
    def _bitwise_(self):  # noqa
        with self._choice():
            with self._option():
                self._comparison_()
                self.name_last_node('left')
                self._token('|')
                self.name_last_node('op')
                self._logical_()
                self.name_last_node('right')
            with self._option():
                self._comparison_()
                self.name_last_node('left')
                self._token('^')
                self.name_last_node('op')
                self._logical_()
                self.name_last_node('right')
            with self._option():
                self._comparison_()
                self.name_last_node('left')
                self._token('&')
                self.name_last_node('op')
                self._logical_()
                self.name_last_node('right')
            self._error('no available options')
        self.ast._define(
            ['left', 'op', 'right'],
            []
        )

    @tatsumasu()
    def _boolean_(self):  # noqa
        with self._choice():
            with self._option():
                self._comparison_()
                self.name_last_node('left')
                self._token('||')
                self.name_last_node('op')
                self._logical_()
                self.name_last_node('right')
            with self._option():
                self._comparison_()
                self.name_last_node('left')
                self._token('&&')
                self.name_last_node('op')
                self._logical_()
                self.name_last_node('right')
            self._error('no available options')
        self.ast._define(
            ['left', 'op', 'right'],
            []
        )

    @tatsumasu()
    def _comparison_(self):  # noqa
        with self._choice():
            with self._option():
                self._equality_()
            with self._option():
                self._relation_()
            with self._option():
                self._shift_()
            self._error('no available options')

    @tatsumasu()
    def _equality_(self):  # noqa
        with self._choice():
            with self._option():
                self._shift_()
                self.name_last_node('left')
                self._token('!=')
                self.name_last_node('op')
                self._comparison_()
                self.name_last_node('right')
            with self._option():
                self._shift_()
                self.name_last_node('left')
                self._token('==')
                self.name_last_node('op')
                self._comparison_()
                self.name_last_node('right')
            self._error('no available options')
        self.ast._define(
            ['left', 'op', 'right'],
            []
        )

    @tatsumasu()
    def _relation_(self):  # noqa
        with self._choice():
            with self._option():
                self._shift_()
                self.name_last_node('left')
                self._token('=<')
                self.name_last_node('op')
                self._comparison_()
                self.name_last_node('right')
            with self._option():
                self._shift_()
                self.name_last_node('left')
                self._token('=>')
                self.name_last_node('op')
                self._comparison_()
                self.name_last_node('right')
            with self._option():
                self._shift_()
                self.name_last_node('left')
                self._token('<')
                self.name_last_node('op')
                self._comparison_()
                self.name_last_node('right')
            with self._option():
                self._shift_()
                self.name_last_node('left')
                self._token('>')
                self.name_last_node('op')
                self._comparison_()
                self.name_last_node('right')
            self._error('no available options')
        self.ast._define(
            ['left', 'op', 'right'],
            []
        )

    @tatsumasu()
    def _shift_(self):  # noqa
        with self._choice():
            with self._option():
                self._bitshift_()
            with self._option():
                self._binop_()
            self._error('no available options')

    @tatsumasu()
    def _bitshift_(self):  # noqa
        with self._choice():
            with self._option():
                self._binop_()
                self.name_last_node('left')
                self._token('>>')
                self.name_last_node('op')
                self._shift_()
                self.name_last_node('right')
            with self._option():
                self._binop_()
                self.name_last_node('left')
                self._token('<<')
                self.name_last_node('op')
                self._shift_()
                self.name_last_node('right')
            self._error('no available options')
        self.ast._define(
            ['left', 'op', 'right'],
            []
        )

    @tatsumasu()
    def _binop_(self):  # noqa
        with self._choice():
            with self._option():
                self._additive_()
            with self._option():
                self._multiplicative_()
            self._error('no available options')

    @tatsumasu()
    def _additive_(self):  # noqa
        with self._choice():
            with self._option():
                self._multiplicative_()
                self.name_last_node('left')
                self._token('+')
                self.name_last_node('op')
                self._binop_()
                self.name_last_node('right')
            with self._option():
                self._multiplicative_()
                self.name_last_node('left')
                self._token('-')
                self.name_last_node('op')
                self._binop_()
                self.name_last_node('right')
            self._error('no available options')
        self.ast._define(
            ['left', 'op', 'right'],
            []
        )

    @tatsumasu()
    def _multiplicative_(self):  # noqa
        with self._choice():
            with self._option():
                self._multiply_()
            with self._option():
                self._unop_()
            self._error('no available options')

    @tatsumasu()
    def _multiply_(self):  # noqa
        with self._choice():
            with self._option():
                self._unop_()
                self.name_last_node('left')
                self._token('*')
                self.name_last_node('op')
                self._multiplicative_()
                self.name_last_node('right')
            with self._option():
                self._unop_()
                self.name_last_node('left')
                self._token('/')
                self.name_last_node('op')
                self._multiplicative_()
                self.name_last_node('right')
            self._error('no available options')
        self.ast._define(
            ['left', 'op', 'right'],
            []
        )

    @tatsumasu()
    def _unop_(self):  # noqa
        with self._choice():
            with self._option():
                self._prefix_()
            with self._option():
                self._postfix_()
            self._error('no available options')

    @tatsumasu()
    def _prefix_(self):  # noqa
        with self._choice():
            with self._option():
                self._token('*')
                self.name_last_node('op')
                self._unop_()
                self.name_last_node('right')
            with self._option():
                self._token('--')
                self.name_last_node('op')
                self._unop_()
                self.name_last_node('right')
            with self._option():
                self._token('++')
                self.name_last_node('op')
                self._unop_()
                self.name_last_node('right')
            with self._option():
                self._token('~')
                self.name_last_node('op')
                self._unop_()
                self.name_last_node('right')
            with self._option():
                self._token('!')
                self.name_last_node('op')
                self._unop_()
                self.name_last_node('right')
            with self._option():
                self._token('-')
                self.name_last_node('op')
                self._unop_()
                self.name_last_node('right')
            with self._option():
                self._token('+')
                self.name_last_node('op')
                self._unop_()
                self.name_last_node('right')
            self._error('no available options')
        self.ast._define(
            ['op', 'right'],
            []
        )

    @tatsumasu()
    def _postfix_(self):  # noqa
        with self._choice():
            with self._option():
                self._postop_()
            with self._option():
                self._singular_()
            self._error('no available options')

    @tatsumasu()
    def _postop_(self):  # noqa
        with self._choice():
            with self._option():
                self._postfix_()
                self.name_last_node('left')
                self._token('(')

                def sep2():
                    self._token(',')

                def block2():
                    self._expr_()
                self._gather(block2, sep2)
                self.name_last_node('args')
                self._token(')')
                self._constant('f')
                self.name_last_node('type')
            with self._option():
                self._postfix_()
                self.name_last_node('left')
                self._token('[')
                self._cut()
                self._expr_()
                self.name_last_node('args')
                self._token(']')
                self._constant('b')
                self.name_last_node('type')
            with self._option():
                self._postfix_()
                self.name_last_node('left')
                self._token('++')
                self.name_last_node('op')
                self._constant('d')
                self.name_last_node('type')
            with self._option():
                self._postfix_()
                self.name_last_node('left')
                self._token('--')
                self.name_last_node('op')
                self._constant('d')
                self.name_last_node('type')
            self._error('no available options')
        self.ast._define(
            ['args', 'left', 'op', 'type'],
            []
        )

    @tatsumasu()
    def _singular_(self):  # noqa
        with self._choice():
            with self._option():
                self._literal_()
            with self._option():
                self._identifier_()
            with self._option():
                self._subexpr_()
            self._error('no available options')

    @tatsumasu()
    def _subexpr_(self):  # noqa
        self._token('(')
        self._expr_()
        self.name_last_node('@')
        self._token(')')

    @tatsumasu()
    def _literal_(self):  # noqa
        with self._choice():
            with self._option():
                self._int_()
                self.name_last_node('val')
                self._constant('int')
                self.name_last_node('type')
            with self._option():
                self._str_()
                self.name_last_node('val')
                self._constant('str')
                self.name_last_node('type')
            with self._option():
                self._chr_()
                self.name_last_node('val')
                self._constant('chr')
                self.name_last_node('type')
            self._error('no available options')
        self.ast._define(
            ['type', 'val'],
            []
        )

    @tatsumasu()
    def _int_(self):  # noqa
        self._pattern(r'\d+')

    @tatsumasu()
    def _str_(self):  # noqa
        self._pattern(r'".+"')

    @tatsumasu()
    def _chr_(self):  # noqa
        self._pattern(r"'.'")

    @tatsumasu()
    def _identifier_(self):  # noqa
        self._pattern(r'[A-Za-z]\w*')


class WewSemantics(object):
    def start(self, ast):  # noqa
        return ast

    def base_type(self, ast):  # noqa
        return ast

    def ptr_type(self, ast):  # noqa
        return ast

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

    def prefix(self, ast):  # noqa
        return ast

    def postfix(self, ast):  # noqa
        return ast

    def postop(self, ast):  # noqa
        return ast

    def singular(self, ast):  # noqa
        return ast

    def subexpr(self, ast):  # noqa
        return ast

    def literal(self, ast):  # noqa
        return ast

    def int(self, ast):  # noqa
        return ast

    def str(self, ast):  # noqa
        return ast

    def chr(self, ast):  # noqa
        return ast

    def identifier(self, ast):  # noqa
        return ast


def main(filename, start='start', **kwargs):
    if not filename or filename == '-':
        text = sys.stdin.read()
    else:
        with open(filename) as f:
            text = f.read()
    parser = WewParser()
    return parser.parse(text, start=start, filename=filename, **kwargs)


if __name__ == '__main__':
    import json
    from tatsu.util import asjson

    ast = generic_main(main, WewParser, name='Wew')
    print('AST:')
    print(ast)
    print()
    print('JSON:')
    print(json.dumps(asjson(ast), indent=2))
    print()