from compiler.objects import builder
from compiler.objects import base
from compiler.parser import lang

def parse_with_semantics(text: str, semantics: object=None):
    """Parse a file with given semantics."""
    return lang.parse(text, semantics=semantics())

def parse_source(inp: str):
    return parse_with_semantics(inp, builder.WewSemantics)

def compile_source(inp: str):
    parsed = parse_source(inp)
    compiler = base.Compiler()
    compiler.compile(parsed)
    return compiler
    
