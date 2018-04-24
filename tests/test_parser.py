from wewcompiler import objects
from wewcompiler.objects import parse_source

from pytest import raises
from tatsu.exceptions import FailedParse
from tests.helpers import emptyfn, for_feature


@for_feature(variables="Variables")
def test_var_declaration():
    """Test variable declarations."""
    decl = "var a : (u2, *u4, *[s2], *[s4]) -> *(s2)"
    parse_source(decl)


@for_feature(functions="Functions")
def test_fn_declaration():
    """Test function definitions."""
    decl = """fn b(a: *[[*s4@3]@5], b:u2) -> u4 {
        return 1;
    }"""
    parse_source(decl)


@for_feature(fuzz="General Fuzzing")
def test_multiple_advanced():
    """Test by parser fuzzing."""
    decl = """fn b(a: *|[[|*s4|@3]@5]|, b:u2) -> |u4| {
        var a: [u4@4] = {1, 2, 3, 4};
        a = 5 * (4 + (4 / 3));
        if a < b {print(wew, lad);}
        x++; // we need a semicolon here
        n = *(0:::*u2);
        n[1+2]--;
        return f(a);
    }"""
    parse_source(decl)


@for_feature(functions="Functions")
def test_function_decl():
    """Test function declarations and check the type of the parsed fn."""
    decl = "fn func(a: u1, b: *u2, ...) -> u4 {};"
    body, = parse_source(decl)

    assert isinstance(body, objects.base.FunctionDecl)

    assert body._type == objects.types.Function(
        objects.types.Int('u4'),
        (objects.types.Int('u1'),
         objects.types.Pointer(
             objects.types.Int('u2'))),
        True,
        True)


@for_feature(functions="Functions")
def test_return_parse():
    """Test that the return statement is parsed correctly."""
    decl = emptyfn("return 1;")
    fn, = parse_source(decl)

    rtn_stmt = fn.body[0]

    assert isinstance(rtn_stmt, objects.statements.ReturnStmt)


@for_feature(if_stmt="IF Statements")
def test_if_stmt():
    """Test the if statement."""
    decl = emptyfn("if a != b {"
                   "    print(\"test\");"
                   "}")
    parse_source(decl)


def test_fn_in_fn():
    """Test function declarations being impossible inside a function body."""
    decl = emptyfn(emptyfn(""))
    with raises(FailedParse):
        parse_source(decl)
