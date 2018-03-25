from typing import Tuple, Dict, Any

import click
import pprint

from wewcompiler.objects import compile_source, base
from wewcompiler.backend.rustvm.register_allocate import allocate
from wewcompiler.backend.rustvm.assemble import process_code, assemble_instructions, group_fns_toplevel


def compile_and_allocate(inp: str, debug: bool=False, reg_count: int = 10) -> base.Compiler:
    compiler = compile_source(inp, debug)
    for i in compiler.compiled_objects:
        allocate(reg_count, i.code)
    return compiler

def compile_and_pack(inp: str, debug: bool=False, reg_count: int = 10) -> Tuple[Dict[str, int], Any]:
    compiler = compile_source(inp, debug)
    return process_code(compiler, reg_count), compiler


def get_stats(compiler: base.Compiler, instructions: bytearray):
    f, s = group_fns_toplevel(compiler.compiled_objects)

    num_funs = len(f)
    num_globals = len(s)
    num_instructions = len(instructions)

    return [
        f"Function count: {num_funs}",
        f"Global count: {num_globals}",
        f"Binary length: {num_instructions}"
    ]


@click.command()
@click.argument("input", type=click.File('r'))
@click.argument("out", type=click.File('wb'))
@click.option("--reg-count", default=10, help="Number of registers to compile for.")
@click.option("--show-stats", is_flag=True, default=True)
@click.option("--debug-compiler", is_flag=True)
@click.option("--print-ir", is_flag=True)
@click.option("--print-hwin", is_flag=True)
@click.option("--print-offsets", is_flag=True)
@click.option("--no-include-std", is_flag=True)
def compile(input, out, reg_count, show_stats, debug_compiler,
            print_ir, print_hwin, print_offsets, no_include_std):

    input = input.read()

    if not no_include_std:
        import os
        stdlib_path = os.path.join(os.path.dirname(__file__), "stdlib.wew")

        with open(stdlib_path) as f:
            stdlib = f.read()

        input += stdlib  # Good solution lol

    (offsets, code), compiler = compile_and_pack(input, debug=debug_compiler, reg_count=reg_count)

    if print_ir:
        print("\n\n".join("{}\n{}".format(i.identifier, i.pretty_print())
                          for i in compiler.compiled_objects))

    if print_hwin:
        print("\n".join(map(str, code)))

    if print_offsets:
        pprint.pprint(offsets)

    compiled = assemble_instructions(code)

    if show_stats:
        print("Stats: \n  ", end="")
        print("\n  ".join(get_stats(compiler, compiled)))

    out.write(compiled)


if __name__ == '__main__':
    compile()
