import subprocess
import pytest

from compiler.backend.rustvm import compile_and_pack, assemble_instructions


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
    def wrapper(func):
        def more_wrappers(binloc):
            program = func()
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
            *(500::*u8) = 100;
        } else {
            *(500::*u8) = 123;
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

        *(5000::*u8) = arr[6];
    }
    """


@expect(1000, 12, 4)
def test_five():
    return """
    fn main() {
        *(1000::*u4) = x();
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
        *(1000::*u8) = arr[3];
    }
    """


@expect(1000, 6, 8)
def test_seven():
    return """
    fn main() {
        var x := myfn(2);
        *(1000::*u8) = x;
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

        *(1000::*u8) = x;
    }

    fn write_pls(a: u2, aptr: *u8) {
        *(1020::*u2) = a;
        *(1024::*u8) = aptr;

        *aptr = a;
    }
    """


@expect(1000, 1234, 8)
def test_nine():
    return """
    fn main() {
        var x: u8;
        *&x = 1234;

        *(1000::*u8) = x;
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

        *(1000::*u8) = y;
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

        *(1000::*u8) = x;
    }
    """
