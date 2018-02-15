from compiler.backend.rustvm import compile_and_allocate

decl = "\n".join((
    "var a : u8 = 1;",
    "var b : [s4] = {1, 2, 3, 4};",
    "var c : [[s4]] = {{1, 2, 3}, {4, 5, 6}};  ~~ This doesn't function correctly yet",
    "var d : u8;"
))

compiled = compile_and_allocate(decl)
for i in compiled.compiled_objects:
    print(i.identifier)
    print(i.pretty_print())
