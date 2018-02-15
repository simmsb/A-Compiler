from compiler.backend.rustvm import compile_and_allocate
from compiler.objects.errors import CompileException

from pytest import raises
from tests.helpers import emptyfn, for_feature


def compile(inp):
    # when testing we want debug mode to be on
    return compile_and_allocate(inp, debug=True)


@for_feature(globals="Global variables")
def test_var_declaration_global():
    """Test variable declaration inside a global scope."""
    decl = "var a := 4;"
    compile(decl)


@for_feature(variables="Local variables")
def test_var_declaration_func():
    """Test variable declaration inside a function scope/."""
    decl = emptyfn("var a := 4;")
    compile(decl)


@for_feature(variables="Variables")
def test_var_multiple_same():
    """Test that multiple declarations of a variable with the same type is valid."""
    decl = ("var a:u4;"
            "var a:u4;")
    compile(decl)


@for_feature(variables="Variables")
def test_var_multiple_different():
    """Test that multiple declarations of a variable with different types is invalid."""
    decl = ("var a:u4;"
            "var a:s1")
    with raises(CompileException):
        compile(decl)


@for_feature(math="Maths")
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
        compile(emptyfn(i + ";"))


@for_feature(math="Maths")
def test_incompatible_types_to_binary_add_op():
    """Test incorrect types to binary add operation."""
    tests = (
        "1::*u4 + 1::*u4",
    )

    for i in tests:
        with raises(CompileException):
            compile(emptyfn(i + ";"))


@for_feature(math="Maths")
def test_types_to_binary_mul_op():
    """Test types to binary multiply operation."""
    tests = (
        "1 * 1",
        "1 / 1"
    )

    for i in tests:
        compile(emptyfn(i + ";"))


@for_feature(math="Maths")
def test_incompatible_types_to_mul_op():
    """Test incorrect types to binary multiply operation."""
    tests = (
        "1 * 1::*u4",
        "1::*u4 * 1::*u4"
    )

    for i in tests:
        with raises(CompileException):
            compile(emptyfn(i + ";"))


@for_feature(bitwise="Bitwise")
def test_types_to_binary_shift_op():
    """Test types to binary shift operation."""
    tests = (
        "1 << 1",
        "1 >> 1"
    )

    for i in tests:
        compile(emptyfn(i + ";"))


@for_feature(bitwise="Bitwise")
def test_incompatible_types_to_shift_op():
    """Test incorrect types to binary shift operation."""
    tests = (
        "1 << 1::*u4",
        "1::*u4 >> 1::*u4"
    )

    for i in tests:
        with raises(CompileException):
            compile(emptyfn(i + ";"))


@for_feature(comparison="Relational")
def test_types_to_binary_relation_op():
    """Test types to binary relation operation."""
    tests = (
        "1 < 1",
        "1::*u1 < 1::*u1"
    )

    for i in tests:
        compile(emptyfn(i + ";"))


@for_feature(comparison="Relational")
def test_incompatible_types_to_relation_op():
    """Test incorrect types to binary relation operation."""
    tests = (
        "1 < 1::*u4",
        "1::*u4 > 1"
    )

    for i in tests:
        with raises(CompileException):
            compile(emptyfn(i + ";"))


@for_feature(bitwise="Bitwise")
def test_types_to_binary_bitwise_op():
    """Test types to binary bitwise operation."""
    tests = (
        "1 | 1",
    )

    for i in tests:
        compile(emptyfn(i + ";"))


@for_feature(bitwise="Bitwise")
def test_incompatible_types_to_bitwise_op():
    """Test incorrect types to binary bitwise operation."""
    tests = (
        "1 | 1::*u4",
        "1::*u4 | 1::*u4"
    )

    for i in tests:
        with raises(CompileException):
            compile(emptyfn(i + ";"))


@for_feature(ss_ops="Short-circuiting")
def test_types_to_binary_comparison_op():
    """Test types to binary comparison operation."""
    tests = (
        "1 || 1",
        "1 || 1::*u1",
        "1::*u1 || 1"
    )

    for i in tests:
        compile(emptyfn(i + ";"))


@for_feature(variables="Variables")
def test_var_ref_subscope():
    """Test that variables in enclosing scopes can be referenced correctly."""
    decl = ("fn test() -> u1 {"
            "    var a := 3;"
            "    {"
            "        var b := a * 2;"
            "    }"
            "}")
    compile(decl)


@for_feature(globals="Globals")
def test_var_ref_global():
    """Test that variables in enclosing scopes can be referenced correctly."""
    decl = ("var a := 3;"
            "fn test() -> u1 {"
            "    var b := a * 3;"
            "}")
    compile(decl)


@for_feature(variables="Variables")
def test_var_ref_fail():
    """Test that undeclared variables fail."""
    decl = emptyfn("a;")
    with raises(CompileException):
        compile(decl)


@for_feature(assignment="Assignment", variables="Variables")
def test_var_assn():
    """Test variable initialisation and assignment."""
    decl = emptyfn("var a := 3;"
                   "a = 4;")
    compile(decl)


@for_feature(assignment="Assignment", pointers="Pointers")
def test_ptr_assn():
    """Test pointer assignment."""
    decl = emptyfn("*(0::*u1) = 3;")
    compile(decl)


@for_feature(assignment="Assignment", variables="Variables")
def test_invalid_var_assn():
    """Test variable initialisation and invalid const assignment."""
    decl = emptyfn("var a:|u4| = 3;"
                   "a = 4;")
    with raises(CompileException):
        compile(decl)


@for_feature(functions="Functions")
def test_return_stmt():
    """Test that the return statement functions correctly."""
    decl = emptyfn("return 1;")
    compile(decl)


@for_feature(functions="Functions")
def test_incompatible_types_to_return():
    """Test that returning non-castable types is invalid."""
    decl = emptyfn("return 1::*u1;")
    with raises(CompileException):
        compile(decl)


@for_feature(assignment="Assignment")
def test_no_lvalue():
    """Test that expressions that have no lvalue are invalid in assignment and increment expressions."""
    decl = emptyfn("1 = 2;")
    with raises(CompileException):
        compile(decl)
    decl = emptyfn("1++;")
    with raises(CompileException):
        compile(decl)


@for_feature(functions="Functions")
def test_function_call():
    """Test that functions reference correctly and can be called, and that argument types work."""
    decl = ("fn a(b: u1, c: *u2) -> u2 {"
            "    return c[b];"
            "}"
            "fn main() -> u1 {"
            "    a(1, 2::*u2);"
            "}")
    compile(decl)


@for_feature(functions="Functions")
def test_function_call_fail_count():
    """Test that an incorrect number of arguments to functions are invalid."""
    decl = ("fn a(b: u1, c: *u2) -> u2 {"
            "    return c[b];"
            "}"
            "fn main() -> u1 {"
            "    a(1);"
            "}")
    with raises(CompileException):
        compile(decl)


@for_feature(functions="Functions")
def test_function_call_fail_type():
    """Test that an incorrect type of arguments to functions are invalid."""
    decl = ("fn a(b: u1, c: *u2) -> u2 {"
            "    return c[b];"
            "}"
            "fn main() -> u1 {"
            "    a(0::*u1, 1);"
            "}")
    with raises(CompileException):
        compile(decl)


@for_feature(pointers="Pointers")
def test_memory_reference_op():
    """Test the memory-location-of operator."""
    decl = emptyfn("var a: u1;"
                   "return &a;",
                   "*u1")
    compile(decl)


@for_feature(if_stmt="IF Statements")
def test_if_stmt():
    """Test the functionality of an if statement."""
    decl = emptyfn("var a := 1;"
                   "var b := 2;"
                   "if a < b {"
                   "    return a;"
                   "} elif a > b {"
                   "    return b;"
                   "} else {"
                   "    return (a + b) / 2;"
                   "}")
    compile(decl)


@for_feature(loop_stmt="While Loops")
def test_while_loop():
    """Test the functionality of a while loop."""
    decl = emptyfn("var a := 2;"
                   "while a {"
                   "    a = a * 2;"
                   "}")
    compile(decl)


@for_feature(variables="Variables", arrays="Arrays", number_literals="Numeric literals")
def test_array_init_num():
    """Test array initialisation."""
    decl = emptyfn("var a := {1, 2, 3};")
    compile(decl)


@for_feature(variables="Variables", arrays="Arrays", string_literals="String literals")
def test_array_init_str():
    """Test array initialisation."""
    decl = emptyfn("var a := {\"string\", \"morestring\", \"lessstring\"};")
    compile(decl)


@for_feature(variables="Variables", arrays="Arrays")
def test_array_decl():
    """Tests array declaration."""
    decl = emptyfn("var a: [u1];")  # this should error, no size information
    with raises(CompileException):
        compile(decl)

    decl = emptyfn("var a: [u1@5];")
    compile(decl)

    decl = emptyfn("var a: [u1@-4]")
    with raises(CompileException):
        compile(decl)


@for_feature(variables="Variables", arrays="Arrays")
def test_array_vars_first():
    """Test array initialisation where a variable is the inspected type."""
    decl = emptyfn("var b := 1;"
                   "var a := {b, 2, 3};")
    compile(decl)


@for_feature(variables="Variables", arrays="Arrays")
def test_array_vars_second():
    """Test array initialisation where a variable isn't the inspected type."""
    decl = emptyfn("var b := 2;"
                   "var a := {1, b, 3};")
    compile(decl)


@for_feature(variables="Variables", arrays="Arrays")
def test_array_init_invalid():
    """Test array initialisation with conflicting types."""
    decl = emptyfn("var a := {1, 2::*u2};")
    with raises(CompileException):
        compile(decl)


@for_feature(variables="Variables", arrays="Arrays")
def test_array_init_expr():
    """Test that expressions in an array initialisation are valid."""
    decl = emptyfn("var b := 4;"
                   "var a := {b, b * 2};")
    compile(decl)


@for_feature(arrays="Arrays", number_literals="Numeric literals")
def test_array_lit_num():
    """Test array literals with numbers."""
    decl = emptyfn("{1, 2, 3};")
    compile(decl)


@for_feature(variables="Variables", arrays="Arrays", string_literals="String literals")
def test_array_lit_str():
    """Test array literals with strings."""
    decl = emptyfn("{\"string\", \"morestring\", \"lessstring\"};")
    compile(decl)


@for_feature(arrays="Arrays")
def test_array_lit_no_const():
    """Test that non-constant expressions are illegal in array lits."""
    decl = emptyfn("var a := 3;"
                   "{a, a * 2};")
    with raises(CompileException):
        compile(decl)


@for_feature(variables="Variables")
def test_var_decl():
    """Test various variable declarations."""
    decl = emptyfn("var a: u1;")
    compile(decl)

    decl = emptyfn("var a: u1 = 3;")
    compile(decl)

    decl = emptyfn("var a: [u1] = {1, 2, 3};")
    compile(decl)

    decl = emptyfn("var a: [u1@4] = {1, 2, 3, 4};")
    compile(decl)

    # we dont have string literal -> string array yet.
    # TODO: string lit -> string arr
    decl = emptyfn("var a: [*u1] = \"test\";")
    with raises(CompileException):
        compile(decl)

    decl = emptyfn("var a: [*u1] = {1, 2};")
    with raises(CompileException):
        compile(decl)

    decl = emptyfn("var a: [u1@4] = {1, 2, 3};")
    with raises(CompileException):
        compile(decl)

    decl = emptyfn("var a: [u1] = 3;")
    with raises(CompileException):
        compile(decl)


@for_feature(number_literals="Numeric literals")
def test_numeric_literals():
    decl = emptyfn("var a := 1;")
    compile(decl)
    decl = emptyfn("var a := 1/u1;")
    compile(decl)
    decl = emptyfn("var a := 1/s1;")
    compile(decl)
    decl = emptyfn("var a := 1/u8;")
    compile(decl)


@for_feature(pointers="Pointers", functions="Functions")
def test_dereference_operation():
    """Test pointer dereference operations."""
    decl = ("fn deref(ptr: *u4, offset: u2) -> u4 {"
            "    return *(ptr + offset);"
            "}")
    compile(decl)
    decl = ("fn deref(ptr: *u4, offset: u2) -> u4 {"
            "    return ptr[offset];"
            "}")
    compile(decl)
