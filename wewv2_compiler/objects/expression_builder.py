"""
DEAD CODE
"""

from typing import Iterable, Union

from irObject import (Binary, Immediate, IRObject, Pop, Push, Register,
                      RegisterEnum, Resize, pullsize)


class FUUUUUUUCK(type):
    def __new__(mcs, name, bases, dict_):
        def fn(op):
            def ref(self, other: Union['Operator', int]):
                if isinstance(other, int):
                    other = OpImmediate(other, self.size)
                return Operation(op, self, other)
            return ref
        for k, v in (("add", "+"),
                     ("sub", "-"),
                     ("mul", "*"),
                     ("floordiv", "/")):
            f = fn(v)
            dict_[f"__{k}__"] = dict_[f"__r{k}__"] = f
        return super().__new__(mcs, name, bases, dict_)


class Operator(metaclass=FUUUUUUUCK):
    pass


class Operation(Operator):
    def __init__(self, op: str, left: Union[Operator, int],
                 right: Union['Operation', 'Register', int]):
        self.op = op
        self.left = left
        self.right = right
        self.size = max(pullsize(left), pullsize(right))

    def __str__(self):
        return f"({self.left} {self.op} {self.right})"

    def __repr__(self):
        return f"({self.op} {repr(self.left)} {repr(self.right)})"

    def emit(self) -> Iterable[IRObject]:
        yield from self.left.emit()
        yield from self.right.emit()
        yield Pop(OpRegister.acc1(self.right.size))  # right first
        yield Pop(OpRegister.acc2(self.left.size))
        yield Binary(OpRegister.acc1(self.right.size),
                     OpRegister.acc2(self.left.size), self.op)


class OpImmediate(Immediate, Operator):
    def emit(self):
        yield Push(self)


class OpRegister(Register, Operator):
    def emit(self):
        yield Push(self.reg)
