from compiler.backend.rustvm import compile_and_pack, assemble

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
    "fn main() {}"
)

(offsets, code), compiler = compile_and_pack(decl)

assembled = assemble.assemble_instructions(code)

print(assembled)

for i in code:
    print(i)
