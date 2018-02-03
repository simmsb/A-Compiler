from compiler.backend.rustvm import compile_and_allocate

decl = (
    "fn ap(y: u8, z: u8, testfn: (u8, u8) -> u8) -> u8 {"
    "    return testfn(y * 2, z * 2);"
    "}"
    "fn mul(x: u8, y: u8) -> u8 {"
    "    return x * y;"
    "}"
    "fn test() -> u1 {"
    "    ap(1, 2, mul);"
    "}"
)

compiled = compile_and_allocate(decl)
for i in compiled.compiled_objects:
    print(i.identifier)
    print(i.pretty_print())
