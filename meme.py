import tatsu

from wewv2_compiler.objects import BaseObject
from wewv2_compiler.parser import language

decl = """fn b(a:[[*s4]@3]@5, b:u2) -> u4 > {
var a := 4;
a = 5 * (4 +
    (4 / 3));
return f(a);
};"""

ast = tatsu.parse(language, decl)[0][0]
print(BaseObject(ast).highlight_lines)

obj = ast.body[1][0]
print(BaseObject(obj).highlight_lines)
obj = ast.body[1][0].right
print(BaseObject(obj).highlight_lines)
obj = ast.body[1][0].right.right
print(BaseObject(obj).highlight_lines)
obj = ast.body[1][0].right.left
print(BaseObject(obj).highlight_lines)
