from typing import List

from wewcompiler.objects import builder
from wewcompiler.objects import base
from wewcompiler.parser import lang


def parse_with_semantics(text: str, semantics: type=None) -> List[base.StatementObject]:
    """Parse a file with given semantics."""
    return lang.parse(text, semantics=semantics())


def parse_source(inp: str) -> List[base.StatementObject]:
    return parse_with_semantics(inp, builder.WewSemantics)


def compile_source(inp: str) -> base.Compiler:
    parsed = parse_source(inp)
    compiler = base.Compiler()
    compiler.compile(parsed)
    return compiler
