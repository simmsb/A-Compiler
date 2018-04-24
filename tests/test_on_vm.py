import subprocess
import pytest

from wewcompiler.backend.rustvm import compile_and_pack, assemble_instructions
from tests.helpers import for_feature


def run_code_on_vm(location: int, value: int, size: int, program: str, binary_location: str):

    (_, code), _ = compile_and_pack(program)
    compiled = assemble_instructions(code)

    proc = subprocess.run(
        [binary_location, "-", "test", "-d",
            str(location), "-s", str(size), "-v", str(value)],
        input=compiled,
        stdout=subprocess.PIPE
    )

    if proc.returncode != 0:
        raise Exception(f"Test failed: {proc.stdout}")


def expect(location: int, value: int, size: int = 2):
    """Wrapper for testing some source on the VM.

    The substring '{dest}' in the source is replaced with the string '*({location}::*u{size})'
    Where {location} is the provided memory location and {size} is the size to read.

    For example:
    @expect(1000, 1234, 8)
    def test_mytest():
        return \"\"\"
        fn main() {
            {dest} = 1234
        \"\"\"
    """
    def wrapper(func):
        def more_wrappers(binloc):
            program = func().replace("{dest}", f"*({location}::*u{size})")
            run_code_on_vm(location, value, size, program, binloc)
        return pytest.mark.usefixtures("binloc")(more_wrappers)
    return wrapper


@expect(1000, 4, 8)
@for_feature(assignment="Assignment")
def test_ptr_assign():
    """A simple pointer dereference assignment."""
    return """
    fn main() {
        var x := 1000::*u8;
        *x = 4;
    }
    """


@expect(500, 123, 8)
@for_feature(if_stmt="IF Statements")
def test_if_stmt():
    """Always falsey if statement."""
    return """
    fn main() {
        if 0 {
            {dest} = 100;
        } else {
            {dest} = 123;
        }
    }
    """


@expect(1000 + 8 * 10, 10, 8)
@for_feature(variables="Local Variables",
             pointers="Pointers",
             increment_ops="Increment op")
def test_loop_ptr_write():
    """Writing to an array in a loop."""
    return """
    fn main() {
        var x : u2 = 0;
        var mem := 1000::*u8;

        while x++ < 10 {
            *(mem + x) = x;
        }
    }
    """


@expect(5000, 12, 8)
@for_feature(arrays="Arrays", loop="While loops")
def test_function_pt_write():
    """Writing to an array passed to a function."""
    return """
    fn test(arr: *u8, len: u8) {
        var i : u8 = 0;
        while i++ < len {
            arr[i] = multwo(arr[i]);
        }
    }

    fn multwo(x: u8) -> u8 {
        return x * 2;
    }

    fn main() {
        var arr: [u8] = {0, 1, 2, 3, 4, 5, 6};

        test(arr, 7);

        {dest} = arr[6];
    }
    """


@expect(1000, 12, 4)
@for_feature(math="Maths")
def test_fn_return():
    """Check function return values."""
    return """
    fn main() {
        {dest} = x();
    }

    fn x() -> u4 {
        return 3 * 4;
    }
    """


@expect(1000, 4, 8)
@for_feature(arrays="Arrays")
def test_arr():
    """Array indexing."""
    return """
    var arr: [u8] = {1, 2, 3, 4};

    fn main() {
        {dest} = arr[3];
    }
    """


@expect(1000, 6, 8)
@for_feature(functions="Functions")
def test_fn_param_return():
    """Check function returns and parameters."""
    return """
    fn main() {
        var x := myfn(2);
        {dest} = x;
    }

    fn myfn(x: u1) -> u8 {
        return 6;
    }
    """


@expect(1000, 9, 8)
@for_feature(pointers="Pointers", functions="Functions")
def test_ptr_passing_setting():
    """Check passing pointers to functions to be written to."""
    return """
    fn main() {
        var x: u8 = 4;
        write_pls(9, &x);

        {dest} = x;
    }

    fn write_pls(a: u2, aptr: *u8) {
        {dest} = a;
        {dest} = aptr;

        *aptr = a;
    }
    """


@expect(1000, 1234, 8)
@for_feature(pointers="Pointers")
def test_reference_dereference():
    """Check that dereferencing a pointer gained from using the
    reference to operator on a variable preserves the lvalue.
    """
    return """
    fn main() {
        var x: u8;
        *&x = 1234;

        {dest} = x;
    }
    """


@expect(1000, 1235, 8)
@for_feature(functions="Functions")
def test_fn_return_val():
    """Check return value from functions."""
    return """
    fn retme(x: u8) -> u8 {
        return x;
    }

    fn main() {
        var y := 1234;

        y = retme(1235);

        {dest} = y;
    }
    """


@expect(1000, 9 * 123, 8)
@for_feature(math="Maths", functions="Functions")
def test_function_params():
    """Check multi-parameter functions returning a result."""
    return """
    fn multwo(x: u8, y: u8) -> u8 {
        return x * y;
    }

    fn main() {
        var x := multwo(9, 123);

        {dest} = x;
    }
    """


@expect(5000, 1000 - 100 * (4 // 2) + 10 - 5 + 1 << 3, 8)
@for_feature(maths="Maths")
def test_arithmetic():
    """Check a chain of complex math operations."""
    return """
    fn main() {
        {dest} = 1000 - 100 * (4 / 2) + 10 - 5 + 1 << 3;
    }
    """


@expect(5000, 1, 8)
@for_feature(comparison="Relational Operators")
def test_comparison_ops_le_t():
    """Check the less than operator for a truthy result."""
    return """
    fn main() {
        {dest} = 1 < 2;
    }
    """


@expect(5000, 0, 8)
@for_feature(comparison="Relational Operators")
def test_comparison_ops_le_f():
    """Check the less than operator for a falsey result."""
    return """
    fn main() {
        {dest} = 2 < 1;
    }
    """


@expect(5000, 1, 8)
@for_feature(comparison="Relational Operators")
def test_comparison_ops_eq_t():
    """Check the equal-to operator for a truthy result."""
    return """
    fn main() {
        {dest} = 1 == 1;
    }
    """


@expect(5000, 0, 8)
@for_feature(comparison="Relational Operators")
def test_comparison_ops_eq_f():
    """Check the equal-to operator for a falsey result."""
    return """
    fn main() {
        {dest} = 1 == 2;
    }
    """


@expect(5000, 1, 8)
@for_feature(comparison="Boolean Operators")
def test_bool_op_or_first():
    """Check the boolean or op with a truthy left operand."""
    return """
    fn write() -> u1 {
        {dest} = 0;
        return 1;
    }

    fn main() {
        {dest} = 1;
        1 or write();
    }
    """


@expect(5000, 1, 8)
@for_feature(comparison="Boolean Operators")
def test_bool_op_or_second():
    """Check the boolean or op with a truthy right operand."""
    return """
    fn write() -> u1 {
        {dest} = 1;
        return 1;
    }

    fn main() {
        {dest} = 0;
        0 or write();
    }
    """


@expect(5000, 1, 8)
@for_feature(comparison="Boolean Operators")
def test_bool_op_and_first():
    """Check the boolean and op with truthy left and right operands."""
    return """
    fn write() -> u1 {
        {dest} = 1;
        return 1;
    }

    fn main() {
        {dest} = 0;
        1 and write();
    }
    """


@expect(5000, 1, 8)
@for_feature(comparison="Boolean Operators")
def test_bool_op_and_second():
    """Check the boolean and op with falsey left operand."""
    return """
    fn write() -> u1 {
        {dest} = 0;
        return 1;
    }

    fn main() {
        {dest} = 1;
        0 and write();
    }
    """


@expect(5000, 10, 8)
@for_feature(pointers="Pointers", functions="Functions")
def test_function_pointers():
    """Check passing function pointers around."""
    return """
    fn run_fun(fun: (u8) -> u8, arg: u8) -> u8 {
        return fun(arg);
    }

    fn mul_two(x: u8) -> u8 {
        return x * 2;
    }

    fn main() {
        {dest} = run_fun(mul_two, 5);
    }
    """


@expect(5000, ord('a'), 1)
@for_feature(strings="String Literals")
def test_string():
    """Check string literals working."""
    return """
    fn last_char(str: *u1) -> u1 {
        while *str { str++; }
        return *(str - 1);
    }

    fn main() {
        var string := "test, a";
        {dest} = last_char(string);
    }
    """


@expect(5000, 123, 8)
@for_feature(arrays="Arrays")
def test_multidimension_arr():
    """Check multidimensional array creation."""
    return """
    fn main() {
        var arr: [[u8]] = {{1, 2}, {123, 4}};
        {dest} = arr[1][0];
    }
    """


@expect(5000, 12, 4)
@for_feature(functions="Functions")
def test_call_fuzz():
    """Fuzz some functions."""
    return """
    fn main() {
        {dest} = takes_args(fuzz(), fuzz(), fuzz());
    }

    fn takes_args(a: u8, b: u1, c: u4) -> u4 {
         write_value(&b, 10);
         return a + b + c;
    }

    fn write_value(ptr: *u1, val: u1) {
        *ptr = val;
    }

    fn fuzz() -> u2 {
        return 1;
    }
    """


@expect(5000, 3, 8)
@for_feature(arrays="Arrays")
def test_ptr_arr():
    """Check arrays as pointers initialisation."""
    return """
    fn main() {
        var x: |*|*u8|| = {{1, 2}, {3, 4}};
        {dest} = x[1][0];
    }
    """


@expect(5000, 50, 8)
@for_feature(register_allocation="Register Allocation")
def test_force_spills_to_happen_large_expression():
    """Create a complex expression to force the register allocator
    to spill registers.
    """
    x = "1"
    for _ in range(49):
        x = f"(1 + {x})"
    return """
    fn main() {
        {dest} = {x};
    }
    """.replace('{x}', x)


@expect(5000, sum(range(50)), 8)
@for_feature(register_allocation="Register Allocation")
def test_force_spills_to_happen_many_args():
    """Create a complex expression to force the register allocator
    to spill registers.
    """
    arg_names = [f"a_{i}" for i in range(50)]
    args = ", ".join(f"{i}: u8" for i in arg_names)
    argsum = "+".join(arg_names)
    params = ", ".join(map(str, range(50)))

    return """
    fn test({args}) -> u8 {
        return {argsum};
    }

    fn main() {
        {dest} = test({params});
    }
    """.replace("{args}", args).replace("{argsum}", argsum).replace("{params}", params)


@expect(5000, 5, 8)
@for_feature(vararys="Variable Arguments")
def test_varargs():
    """Check vararg functions."""
    return """
    fn main() {
        {dest} = test_va(5::u8);
    }

    fn test_va(...) -> u8 {
        return *(var_args::*u8 - 1);
    }
    """


@expect(5000, 5, 8)
@for_feature(if_stmt="If Statements")
def test_if_stmt_true():
    """Check if statements with a truthy condition."""
    return """
    fn main() {
        var x := 1;
        if x {
            {dest} = 5;
        } else {
            {dest} = 0;
        }
    }
    """


@expect(5000, 5, 8)
@for_feature(if_stmt="If Statements")
def test_if_stmt_false():
    """Check if statements with a falsey condition."""
    return """
    fn main() {
        var x := 0;
        if x {
            {dest} = 0;
        } else {
            {dest} = 5;
        }
    }
    """


@expect(5000, 5, 8)
@for_feature(if_stmt="If Statements")
def test_if_stmt_single_branch_true():
    """Check if statements with no else, truthy condition."""
    return """
    fn main() {
        {dest} = 0;
        if 1 {
            {dest} = 5;
        }
    }
    """


@expect(5000, 5, 8)
@for_feature(if_stmt="If Statements")
def test_if_stmt_single_branch_false():
    """Check if statements with no else, falsey condition."""
    return """
    fn main() {
        {dest} = 5;
        if 0 {
            {dest} = 0;
        }
    }
    """


@expect(5000, 1 + 2 + 3, 8)
@for_feature(varargs="Variable Arguments")
def test_varargs_complex():
    """Complex vararg fuzzing tests."""
    return """
    fn main() {
        {dest} = test_va(0, 1, 1::u8, 2::u2, 3::u4);
    }

    fn test_va(no_: u1, pe_: u8, ...) -> u8 {
        var a: *u8;
        var b: *u2;
        var c: *u4;

        var ptr := var_args::*u1;

        ptr = ptr - sizeof<u8>;
        a = ptr;

        ptr = ptr - sizeof<u2>;
        b = ptr;

        ptr = ptr - sizeof<u4>;
        c = ptr;

        return *a + *b + *c;
    }
    """


@expect(5000, 8, 8)
@for_feature(incr_op="Increment Operator")
def test_princrement():
    """Check the preincrement operator."""
    return """
    fn main() {
        var x := 0::*u8;
        ++x;
        {dest} = x::u8;
    }
    """


@expect(5000, 123 + 234, 8)
@for_feature(globals="Global Variables")
def test_globals():
    """Check global variable arrays and scoped variables."""
    return """
    var global: [u8] = {1, 2, 234};
    mod test {
        var global2 : u8 = 123;
    }

    fn main () {
        {dest} = (test.global2 + global[2]);
    }
    """


@expect(5000, 999_999_999_999_999_999, 8)
@for_feature(integer_lit="Integer literals")
def test_big_number():
    """Check that large literals work properly."""
    return """
    fn main() {
        {dest} = 999999999999999999;
    }
    """


@expect(5000, 1, 8)
@for_feature(unary_op="Unary abs")
def test_pos_of_neg():
    """Check functionality of unary abs operator."""
    return """
    fn main() {
        var a := -1;
        {dest} = +a;
    }
    """


@expect(5000, 1, 8)
@for_feature(unary_op="Unary abs")
def test_pos_of_pos():
    """Check functionality of unary abs operator."""
    return """
    fn main() {
        var a : s8 = 1;
        {dest} = +a;
    }
    """


@expect(5000, 1, 8)
@for_feature(unary_op="Unary negate")
def test_negate_of_neg():
    """Check functionality of unary neg operator."""
    return """
    fn main() {
        var a := -1;
        {dest} = -a;
    }
    """


@expect(5000, 1, 8)
@for_feature(unary_op="Logical invert")
def test_linv():
    """Check functionality of unary logical invert operator."""
    return """
    fn main() {
        var a := 0;
        {dest} = !a;
    }
    """


@expect(5000, 1, 1)
@for_feature(unary_op="Bitwise invert")
def test_binv():
    """Check functionality of unary bitwise invert operator."""
    return """
    fn main() {
        var a : u1 = 254;
        {dest} = ~a;
    }
    """


def math_test_gen(name: str, left: int, right: int, op: str, force_result: int = None):
    result = force_result if force_result is not None else eval(f"({left}) {op} ({right})")

    @expect(5000, result, 1)
    @for_feature(binop="Binary Operator")
    def wrapper():
        return """
        fn main() {
            {dest} = ({left}) {op} ({right});
        }
        """.replace("{left}", str(left)).replace("{op}", op).replace("{right}", str(right))

    wrapper.__name__ = f"test_op_{name}"
    wrapper.__doc__ = f"Test the binary operator '{op}'."
    return wrapper


test_op_imod = math_test_gen("imod", -3, 2, "%", force_result=255)


test_op_mod = math_test_gen("mod", 3, 2, "%")


test_op_idiv = math_test_gen("idiv", -4, 2, "/", force_result=254)


test_op_shr = math_test_gen("shr", 4, 1, ">>")


test_op_sar = math_test_gen("sar", -4, 1, ">>", force_result=254)


test_op_shl = math_test_gen("shl", 1, 1, "<<")
