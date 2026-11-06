# Adapted from uniseg 0.10.1, Copyright (c) 2013-2024 Masaaki Shibata.
# MIT; see ../LICENSE_UNISEG.txt. AEK changes: relative imports and pinned Unicode 17.
from collections.abc import Callable
from enum import Enum
from functools import wraps
from typing import TypeVar

__all__ = [
    'EnumProperty',
    'PropertyFunction',
]


class EnumProperty(str, Enum):

    def __repr__(self) -> str:
        return f'{self.__class__.__name__}.{self.name}'

    def __str__(self) -> str:
        return self.name


_T = TypeVar('_T')

PropertyFunction = Callable[[str], _T]
"""A function which returns any property value for given Unicode code point."""


def character_property(f: PropertyFunction[_T]) -> PropertyFunction[_T]:
    """(decorator) Check if the given argument is a sigle unicode character, or
    raise TypeError otherwise."""
    @wraps(f)
    def wrapper(c: str, /) -> _T:
        if len(c) != 1:
            raise TypeError(
                f"{f.__name__}() argument 1 must be a unicode character, not str"
            )
        return f(c)
    return wrapper
