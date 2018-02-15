from typing import List

from compiler.objects import builder
from compiler.objects import base
from compiler.parser import lang


def parse_with_semantics(text: str, semantics: type=None) -> List[base.StatementObject]:
    """Parse a file with given semantics."""
    return lang.parse(text, semantics=semantics())


def parse_source(inp: str) -> List[base.StatementObject]:
    return parse_with_semantics(inp, builder.WewSemantics)


def compile_source(inp: str, debug: bool=False) -> base.Compiler:
    parsed = parse_source(inp)
    compiler = base.Compiler(debug)
    compiler.compile(parsed)
    return compiler
