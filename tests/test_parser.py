import pytest
import tatsu

from wewv2_compiler.parser import lang


def test_var_declaration():
    decl = "var a : (u2, *u4, [s2], *[s4]) -> *(s2)"
    lang.parse(decl)


def test_fn_declaration():
    decl = """fn b(a:[[*s4@3]@5], b:u2) -> u4 {
        return 1
    }"""
    lang.parse(decl)


def test_multiple_advanced():
    decl = """fn b(a:|[[|*s4|@3]@5]|, b:u2) -> |u4| {
        var a: [u4@4] = {1, 2, 3, 4}
        a = 5 * (4 + (4 / 3))
        if a < b {print(wew, lad)}
        x++; ~~ we need a semicolon here
        n = *(0:::*u2)
        n[1+2]--
        return f(a)
    }"""
    lang.parse(decl)
