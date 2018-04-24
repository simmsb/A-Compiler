import os

_lang = os.path.join(os.path.dirname(__file__), "lang.ebnf")

with open(_lang) as f:
    language = f.read()

try:
    from wewcompiler.parser.lang import WewParser
    lang = WewParser()
except ImportError:
    import tatsu
    lang = tatsu.compile(language)
