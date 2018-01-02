from compiler.objects import compile_source
from compiler.objects.base import CompileException
from pytest import raises


def emptyfn(body: str) -> str:
    return f"fn test() -> u1 {{{body}}}"


def test_var_declaration_global():
    decl = "var a := 4;"
    compile_source(decl)


def test_var_declaration_func():
    decl = emptyfn("var a := 4;")
    compile_source(decl)


def test_var_multiple_same():
    decl = ("var a:u4;"
            "var a:u4;")
    compile_source(decl)


def test_var_multiple_different():
    decl = ("var a:u4;"
            "var a:s1")
    with raises(CompileException):
        compile_source(decl)


def test_incompatible_types_to_add():
    decl = emptyfn("var a := 3;"
                   "var b : *u1;"
                   "a * b;")
    with raises(CompileException):
        compile_source(decl)

def test_var_ref():
    decl = ("var a := 3;"
            "fn test() -> u1 {"
            "    var b := a * 3;"
            "}")
    compile_source(decl)
