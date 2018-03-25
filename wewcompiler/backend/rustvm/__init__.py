import re
import pprint
from itertools import count
from typing import Tuple, Dict, Any, Iterable

import click
import colorama
from termcolor import colored

from tatsu.exceptions import FailedParse

from wewcompiler.objects import base, parse_source, compile_source
from wewcompiler.utils import add_line_count, strip_newlines
from wewcompiler.backend.rustvm.assemble import process_code, assemble_instructions, group_fns_toplevel


def compile_and_pack(inp: str, debug: bool = False, reg_count: int = 10) -> Tuple[Dict[str, int], Any]:
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

    colorama.init(autoreset=True)

    input = input.read()

    try:
        parsed = parse_source(input)
    except FailedParse as e:
        print("Failed to parse input: ")

        info = e.buf.line_info(e.pos)
        line = info.line + 1
        col = info.col + 1

        text = info.text.rstrip()

        arrow_pos = re.sub(r"[^\t]", " ", text)[:info.col]

        text = text.expandtabs()

        above_lines = strip_newlines(e.buf.get_lines(max(line - 5, 0), line - 2))
        error_line = e.buf.get_line(line - 1).rstrip("\n\r")
        below_lines = strip_newlines(e.buf.get_lines(line, line + 5))

        # get line error is on, cut 5 lines above and 5 lines below
        # highlight error line, grey colour surrounding lines

        line_counter = count(max(line - 4, 1))

        line = colored(str(line), 'green')
        col = colored(str(col), 'green')
        print(f"Line {line}, Column: {col}: ")
        if above_lines:
            print(colorama.Style.DIM + "\n".join(add_line_count(above_lines, line_counter)))
        print(colorama.Style.BRIGHT + f"{next(line_counter):>3}| {error_line}\n     {arrow_pos}^")
        if below_lines:
            print(colorama.Style.DIM + "\n".join(add_line_count(below_lines, line_counter)))

        exit(1)

    if not no_include_std:
        import os
        stdlib_path = os.path.join(os.path.dirname(__file__), "stdlib.wew")

        with open(stdlib_path) as f:
            stdlib = f.read()

        parsed.extend(parse_source(stdlib))

    compiler = base.Compiler(debug_compiler)

    compiler.compile(parsed)

    offsets, code = process_code(compiler, reg_count)

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
