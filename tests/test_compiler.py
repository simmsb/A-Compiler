from compiler.objects import compile_source
from compiler.objects.base import CompileException
from pytest import raises
from tests.helpers import emptyfn


def test_var_declaration_global():
    """Test variable declaration inside a global scope."""
    decl = "var a := 4;"
    compile_source(decl)


def test_var_declaration_func():
    """Test variable declaration inside a function scope/."""
    decl = emptyfn("var a := 4;")
    compile_source(decl)


def test_var_multiple_same():
    """Test that multiple declarations of a variable with the same type is valid."""
    decl = ("var a:u4;"
            "var a:u4;")
    compile_source(decl)


def test_var_multiple_different():
    """Test that multiple declarations of a variable with different types is invalid."""
    decl = ("var a:u4;"
            "var a:s1")
    with raises(CompileException):
        compile_source(decl)


# TODO: more binary operation type tests

def test_incompatible_types_to_multiply():
    """Test that multiplying a integer by a pointer is invalid."""
    decl = emptyfn("var a := 3;"
                   "var b : *u1;"
                   "a * b;")
    with raises(CompileException):
        compile_source(decl)


def test_var_ref_subscope():
    """Test that variables in enclosing scopes can be referenced correctly."""
    decl = ("fn test() -> u1 {"
            "    var a := 3;"
            "    {"
            "        var b := a * 2;"
            "    }"
            "}")
    compile_source(decl)


def test_var_ref_global():
    """Test that variables in enclosing scopes can be referenced correctly."""
    decl = ("var a := 3;"
            "fn test() -> u1 {"
            "    var b := a * 3;"
            "}")
    compile_source(decl)


def test_var_ref_fail():
    """Test that undeclared variables fail."""
    decl = emptyfn("a;")
    with raises(CompileException):
        compile_source(decl)


def test_var_assn():
    """Test variable initialisation and assignment."""
    decl = emptyfn("var a := 3;"
                   "a = 4;")
    compile_source(decl)


def test_return_stmt():
    """Test that the return statement functions correctly."""
    decl = emptyfn("return 1;")
    compile_source(decl)


def test_incompatible_types_to_return():
    """Test that returning non-castable types is invalid."""
    decl = emptyfn("return 1::*u1;")
    with raises(CompileException):
        compile_source(decl)


def test_no_lvalue():
    """Test that expressions that have no lvalue are invalid in assignment and increment expressions."""
    decl = emptyfn("1 = 2;")
    with raises(CompileException):
        compile_source(decl)
    decl = emptyfn("1++;")
    with raises(CompileException):
        compile_source(decl)


def test_function_call():
    """Test that functions reference correctly and can be called, and that argument types work."""
    decl = ("fn a(b: u1, c: *u2) -> u2 {"
            "    return c[b];"
            "}"
            "fn main() -> u1 {"
            "    a(1, 2::*u2);"
            "}")
    compile_source(decl)


def test_function_call_fail_count():
    """Test that an incorrect number of arguments to functions are invalid."""
    decl = ("fn a(b: u1, c: *u2) -> u2 {"
            "    return c[b];"
            "}"
            "fn main() -> u1 {"
            "    a(1);"
            "}")
    with raises(CompileException):
        compile_source(decl)


def test_function_call_fail_type():
    """Test that an incorrect type of arguments to functions are invalid."""
    decl = ("fn a(b: u1, c: *u2) -> u2 {"
            "    return c[b];"
            "}"
            "fn main() -> u1 {"
            "    a(0::*u1, 1);"
            "}")
    with raises(CompileException):
        compile_source(decl)
