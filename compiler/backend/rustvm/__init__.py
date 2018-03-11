from typing import Tuple, Dict, Any

from compiler.objects import compile_source, base
from compiler.backend.rustvm.register_allocate import allocate
from compiler.backend.rustvm.assemble import process_code


def compile_and_allocate(inp: str, debug: bool=False, reg_count: int = 10) -> base.Compiler:
    compiler = compile_source(inp, debug)
    for i in compiler.compiled_objects:
        allocate(reg_count, i.code)
    return compiler

def compile_and_pack(inp: str, debug: bool=False, reg_count: int = 10) -> Tuple[Dict[str, int], Any]:
    compiler = compile_source(inp, debug)
    return process_code(compiler, reg_count), compiler
