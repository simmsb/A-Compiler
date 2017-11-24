from typing import Union

from irObject import Binary, IRObject, Pop, Push, Register


class FUUUUUUUCK(type):
    def __new__(cls, name, bases, dict_):
        def fn(op):
            def ref(self, other: Union['Operator', int]):
                return Operation(op, self, other)
            return ref
        for k, v in (("add", "+"),
                     ("sub", "-"),
                     ("mul", "*"),
                     ("floordiv", "/")):
            f = fn(v)
            dict_[f"__{k}__"] = f
            dict_[f"__r{k}__"] = lambda a, b, f=f: f(b, a)
        return super().__new__(cls, name, bases, dict_)


class Operator(metaclass=FUUUUUUUCK):
    pass


class Operation(Operator):
    def __init__(self, op: str, left: Union[Operator, int],
                 right: Union['Operation', 'Register', int]):
        self.op = op
        self.left = left
        self.right = right

    def __str__(self):
        return f"({self.left} {self.op} {self.right})"

    def __repr__(self):
        return f"({self.op} {repr(self.left)} {repr(self.right)})"

    def emit(self):
        yield from self.left
        yield from self.right
        yield Pop(Register.acc1)
        yield Pop(Register.acc2)
        yield Binary(Register.acc1, Register.acc2, self.op)


class OpRegister(Operator):
    def __init__(self, reg: Register):
        self.reg = reg

    def __str__(self):
        return f"%{self.reg}"

    __repr__ = __str__

    def emit(self):
        yield Push(self.reg)


stackptr = OpRegister(Register.stackptr)
baseptr = OpRegister(Register.baseptr)
acc1 = OpRegister(Register.acc1)
acc2 = OpRegister(Register.acc2)
