from typing import Optional

from dataclasses import dataclass

from compiler.objects.types import Type
from compiler.objects.astnode import BaseObject
from compiler.objects.ir_object import DataReference


@dataclass
class Variable:
    """A reference to a variable, holds scope and location information."""

    name: str
    type: Type
    parent: Optional[BaseObject] = None

    stack_offset: Optional[int] = None
    global_offset: Optional[DataReference] = None

    @property
    def size(self) -> int:
        return self.type.size

    @property
    def identifier(self) -> str:
        return self.name

    def __str__(self):
        return f"Variable({self.name}, {self.type})"
