from typing import Optional

from dataclasses import dataclass

from wewcompiler.objects.types import Type


@dataclass
class DataReference:
    """Index to some named object, the exact location to be resolved later."""
    name: str


@dataclass
class Variable:
    """A reference to a variable, holds scope and location information."""

    name: str
    type: Type

    size: Optional[int] = None
    stack_offset: Optional[int] = None
    global_offset: Optional[DataReference] = None

    #: are we a function or something where dereferencing doesn't make sense
    lvalue_is_rvalue: Optional[bool] = False

    def __post_init__(self):
        if self.size is None:
            self.size = self.type.size

    def __str__(self):
        return f"Variable({self.name}, {self.type})"
