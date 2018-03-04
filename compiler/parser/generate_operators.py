from typing import Tuple

bin_ops = (
    ("boolean",  ("or", "and"),          ">"),
    ("bitwise",  ("|", "^", "&"),        "<"),
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

        if assoc == "<":
            result.append(
                f"{name} = left:{next_op}_pre rest:{{{name}_rep}}+ ;"
            )

            result.append(
                f"{name}_rep = op:({op_list}) right:{next_op}_pre ;"
            )
        else:
            result.append(
                f"{name} = left:{next_op}_pre op:({op_list}) ~ right:{name}_pre ;"
            )

        result.append("\n")

    return "\n".join(result)

print(generate(bin_ops))
