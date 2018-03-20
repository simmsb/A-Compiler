from compiler.backend.rustvm import compile_and_pack, assemble

src = """
fn main() {
    var x: [u8@4] = {1, 2, 3, 4, 5};
}
"""

(offset, code), compiler = compile_and_pack(src)

assembled = assemble.assemble_instructions(code)
