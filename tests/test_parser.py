import pytest
import tatsu

from wewv2_compiler.parser import language


def test_var_declaration():
    decl = "var a: (u2, *u4, [s2], *[s4]) -> *(s2);"
    ast = tatsu.parse(language, decl)
    assert ast[0][0]["name"] == "a"


def test_fn_declaration():
    decl = """fn b(a:[[*s4]@3]@5, b:u2) -> u4 > {
        return 0;
    };"""
    ast = tatsu.parse(language, decl)
    assert ast[0][0]["name"] == "b"
