import os

import tatsu

_lang = os.path.join(os.path.dirname(__file__), "lang.ebnf")

with open(_lang) as f:
    language = f.read()

lang = tatsu.compile(language)
