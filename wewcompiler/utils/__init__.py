from typing import Iterable

def add_line_count(lines: Iterable[str], counter: Iterable[int]) -> Iterable[str]:
    return (f"{next(counter):>3}| {lv}" for lv in lines)

def add_line_once(line: str, counter: Iterable[int]) -> str:
    return f"{next(counter):>3}| {line}"

def strip_newlines(strs: Iterable[str]) -> Iterable[str]:
    return (i.rstrip("\n\r") for i in strs)
