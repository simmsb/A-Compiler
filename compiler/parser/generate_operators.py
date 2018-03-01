from typing import Tuple

bin_ops = (
    ("logical",  ("|", "^", "&"),        ">"),
    ("boolean",  ("or", "and"),          ">"),
    ("equality", ("!=", "=="),           "<"),
    ("relation", ("<=", ">=", "<", ">"), "<"),
    ("bitshift", (">>", "<<"),           "<"),
    ("additive", ("+", "-"),             "<"),
    ("multiply", ("*", "/"),             "<")
)

def generate(op_table: Tuple[str, Tuple[str, ...]]):
    result = []

    next_values = [x for x, *_ in op_table[1:]] + ["unop"]

    for (name, ops, assoc), next_op in zip(op_table, next_values):
        result.append(
            f"{name}_pre = {name} | {next_op}_pre ;"
        )

        op_list = " | ".join(f"'{x}'" for x in ops)

        result.append(
            f"{name} = ({op_list}){assoc}{{{next_op}_pre}}+ ;"
        )

    return "\n".join(result)

print(generate(bin_ops))
