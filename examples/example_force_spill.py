from pprint import pprint

from compiler.backend.rustvm import compile_and_allocate

src = (
"""
fn fibonacci_rec(to: u8) -> u8 {
    if to < 1 {
        return 1;
    }
    return fibonacci_rec(to - 1) + fibonacci_rec(to - 2);
}

fn fibonacci_iter(to : u8) -> u8 {
    var a := 0/u8;
    var b := 1/u8;
    var tmp: u8;
    while to {
        tmp = a;
        a = b;
        b = tmp + a;
        to--;
    }
    return b;
}
""")

src = (
"""
fn derefme(to: *u8) -> u8 {
    if -1 < 2 {
        return (1 * (2 * (3 * (4 * (5 * (6 * (7 * (8 * (1 * (2 * (3 * 4)))))))))));
    } elif -1/u8 < 3 {
        return 4;
    } else {
        return 5;
    }
    return to[4];
}
"""
)

comp = compile_and_allocate(src)

for i in comp.compiled_objects:
    print(i.pretty_print())
    print("\n\n\n\n")
