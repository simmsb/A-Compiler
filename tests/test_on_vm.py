import subprocess
import pytest

from wewcompiler.backend.rustvm import compile_and_pack, assemble_instructions


def run_code_on_vm(location: int, value: int, size: int, program: str, binary_location: str):

    (_, code), _ = compile_and_pack(program)
    compiled = assemble_instructions(code)

    proc = subprocess.run(
        [binary_location, "-", "test", "-d", str(location), "-s", str(size), "-v", str(value)],
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
def test_one():
    return """
    fn main() {
        var x := 1000::*u8;
        *x = 4;
    }
    """


@expect(500, 123, 8)
def test_two():
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
def test_three():
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
def test_four():
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
def test_five():
    return """
    fn main() {
        {dest} = x();
    }

    fn x() -> u4 {
        return 3 * 4;
    }
    """

@expect(1000, 4, 8)
def test_six():
    return """
    var arr: [u8] = {1, 2, 3, 4};

    fn main() {
        {dest} = arr[3];
    }
    """


@expect(1000, 6, 8)
def test_seven():
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
def test_eight():
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
def test_nine():
    return """
    fn main() {
        var x: u8;
        *&x = 1234;

        {dest} = x;
    }
    """


@expect(1000, 1235, 8)
def test_ten():
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
def test_eleven():
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
def test_arithmetic():
    return """
    fn main() {
        {dest} = 1000 - 100 * (4 / 2) + 10 - 5 + 1 << 3;
    }
    """

@expect(5000, 1, 8)
def test_comparison_ops_le_t():
    return """
    fn main() {
        {dest} = 1 < 2;
    }
    """

@expect(5000, 0, 8)
def test_comparison_ops_le_f():
    return """
    fn main() {
        {dest} = 2 < 1;
    }
    """

@expect(5000, 1, 8)
def test_comparison_ops_eq_t():
    return """
    fn main() {
        {dest} = 1 == 1;
    }
    """

@expect(5000, 0, 8)
def test_comparison_ops_eq_f():
    return """
    fn main() {
        {dest} = 1 == 2;
    }
    """

@expect(5000, 1, 8)
def test_bool_op_or_first():
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
def test_bool_op_or_second():
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
def test_bool_op_and_first():
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
def test_bool_op_and_second():
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
def test_function_pointers():
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
def test_string():
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
def test_multidimension_arr():
    return """
    fn main() {
        var arr: [[u8]] = {{1, 2}, {123, 4}};
        {dest} = arr[1][0];
    }
    """

@expect(5000, 12, 4)
def test_call_fuzz():
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
def test_ptr_arr():
    return """
    fn main() {
        var x: **u8 = {{1, 2}, {3, 4}};
        {dest} = x[1][0];
    }
    """


@expect(5000, 50, 8)
def test_force_spills_to_happen():
    x = "1"
    for _ in range(49):
        x = f"(1 + {x})"
    return """
    fn main() {
        {dest} = {x};
    }
    """.replace('{x}', x)
