from compiler.objects import compile_source, base
from compiler.backend.rustvm.register_allocate import allocate


def compile_and_allocate(inp: str, reg_count: int = 10) -> base.Compiler:
    compiled = compile_source(inp)
    for i in compiled.compiled_objects:
        allocate(reg_count, i.context.code)
    return compiled
