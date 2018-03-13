from typing import Tuple, Dict, Any

import click

from compiler.objects import compile_source, base
from compiler.backend.rustvm.register_allocate import allocate
from compiler.backend.rustvm.assemble import process_code, assemble_instructions


def compile_and_allocate(inp: str, debug: bool=False, reg_count: int = 10) -> base.Compiler:
    compiler = compile_source(inp, debug)
    for i in compiler.compiled_objects:
        allocate(reg_count, i.code)
    return compiler

def compile_and_pack(inp: str, debug: bool=False, reg_count: int = 10) -> Tuple[Dict[str, int], Any]:
    compiler = compile_source(inp, debug)
    return process_code(compiler, reg_count), compiler


@click.command()
@click.argument("input", type=click.File('r'))
@click.argument("out", type=click.File('wb'))
def compile(input, out):
    (_, code), _ = compile_and_pack(input.read())
    out.write(assemble_instructions(code))


if __name__ == '__main__':
    compile()
