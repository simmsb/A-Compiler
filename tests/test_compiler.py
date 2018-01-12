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


def test_types_to_binary_add_op():
    """Test types to binary add operation."""
    tests = (
        "1 + 1",
        "1 - 1",
        "1 + 1::*u4",
        "1::u2 + 1::u8",
        "1::u2 + 1::s8",
        "1::*u4 + 1",
        "1::*u4 - 1::*u4"
    )

    for i in tests:
        compile_source(emptyfn(i + ";"))


def test_incompatible_types_to_binary_add_op():
    """Test incorrect types to binary add operation."""
    tests = (
        "1::*u4 + 1::*u4",
    )

    for i in tests:
        with raises(CompileException):
            compile_source(emptyfn(i + ";"))


def test_types_to_binary_mul_op():
    """Test types to binary multiply operation."""
    tests = (
        "1 * 1",
        "1 / 1"
    )

    for i in tests:
        compile_source(emptyfn(i + ";"))

def test_incompatible_types_to_mul_op():
    """Test incorrect types to binary multiply operation."""
    tests = (
        "1 * 1::*u4",
        "1::*u4 * 1::*u4"
    )

    for i in tests:
        with raises(CompileException):
            compile_source(emptyfn(i + ";"))


def test_types_to_binary_shift_op():
    """Test types to binary shift operation."""
    tests = (
        "1 << 1",
        "1 >> 1"
    )

    for i in tests:
        compile_source(emptyfn(i + ";"))


def test_incompatible_types_to_shift_op():
    """Test incorrect types to binary shift operation."""
    tests = (
        "1 << 1::*u4",
        "1::*u4 >> 1::*u4"
    )

    for i in tests:
        with raises(CompileException):
            compile_source(emptyfn(i + ";"))


def test_types_to_binary_relation_op():
    """Test types to binary relation operation."""
    tests = (
        "1 < 1",
        "1::*u1 < 1::*u1"
    )

    for i in tests:
        compile_source(emptyfn(i + ";"))


def test_incompatible_types_to_relation_op():
    """Test incorrect types to binary relation operation."""
    tests = (
        "1 < 1::*u4",
        "1::*u4 > 1"
    )

    for i in tests:
        with raises(CompileException):
            compile_source(emptyfn(i + ";"))


def test_types_to_binary_bitwise_op():
    """Test types to binary bitwise operation."""
    tests = (
        "1 | 1",
    )

    for i in tests:
        compile_source(emptyfn(i + ";"))


def test_incompatible_types_to_bitwise_op():
    """Test incorrect types to binary bitwise operation."""
    tests = (
        "1 | 1::*u4",
        "1::*u4 | 1::*u4"
    )

    for i in tests:
        with raises(CompileException):
            compile_source(emptyfn(i + ";"))


def test_types_to_binary_comparison_op():
    """Test types to binary comparison operation."""
    tests = (
        "1 || 1",
        "1 || 1::*u1",
        "1::*u1 || 1"
    )

    for i in tests:
        compile_source(emptyfn(i + ";"))


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


def test_invalid_var_assn():
    """Test variable initialisation and invalid const assignment."""
    decl = emptyfn("var a:|u4| = 3;"
                   "a = 4;")
    with raises(CompileException):
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


def test_memory_reference_op():
    """Test the memory-location-of operator."""
    decl = emptyfn("var a: u1;"
                   "return &a;",
                   "*u1")
    compile_source(decl)


def test_if_stmt():
    """Test the functionality of an if statement."""
    decl = emptyfn("var a := 1;"
                   "var b := 2;"
                   "if a < b {"
                   "    return a;"
                   "} else {"
                   "    return b;"
                   "}")
    compile_source(decl)


def test_while_loop():
    """Test the functionality of a while loop."""
    decl = emptyfn("var a := 2;"
                   "while a {"
                   "    a = a * 2;"
                   "}")
    compile_source(decl)

    
def test_array_init():
    """Tests array initialisation."""
    decl = emptyfn("var a := {1, 2, 3};")
    compile_source(decl)
