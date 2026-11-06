# Adapted from uniseg 0.10.1, Copyright (c) 2013-2024 Masaaki Shibata.
# MIT; see ../LICENSE_UNISEG.txt. AEK changes: relative imports and pinned Unicode 17.
"""Breakable table and string tokenization."""

from collections.abc import Callable, Iterable, Iterator, Sequence
from copy import copy
from enum import Enum
from typing import Any, Generic, Literal, Optional, TypeVar, Union

__all__ = [
    'Breakable',
    'Breakables',
    'TailorFunction',
    'Run',
    'boundaries',
    'break_units',
]


class Breakable(Enum):
    DoNotBreak = 0
    Break = 1

    def __bool__(self) -> bool:
        return bool(self.value)


# type aliases for annotation
Breakables = Iterable[Literal[0, 1]]
SkipTable = Sequence[Literal[0, 1]]

TailorFunction = Callable[[str, Breakables], Breakables]
"""A function which returns tailored breakable talbes from a string and its
original braekable table."""


_T = TypeVar('_T')


class Run(Generic[_T]):
    """A utitlity class which helps treating break determination for a string."""
    __slots__ = [
        '_text', '_chars', '_attributes', '_skip_table', '_breakables',
        '_position', '_condition'
    ]

    def __init__(self, text: str, func: Callable[[str], _T] = lambda x: x, /):
        """Utitlity class which helps treating break determination for a string.

        `text`
            string to determine breakable information.
        `func`
            property function to get a specific value for each character
            (code point) of the string.
        """
        self._text = text
        self._chars = list(text)
        self._attributes = [func(c) for c in text]
        self._skip_table = [1 for __ in text]
        self._breakables = list[Optional[Breakable]](None for __ in text)
        self._position = 0
        self._condition = bool(text)

    def __bool__(self) -> bool:
        """Evaluate the instance itself represents if its context is valid.

        >>> bool(Run('a'))
        True
        >>> bool(Run(''))
        False
        >>> bool(Run('abc').is_leading('b'))
        True
        >>> bool(Run('abc').is_leading('b').is_leading('c'))
        True
        >>> bool(Run('abc').is_leading('x'))
        False
        >>> bool(Run('abc').is_leading('b').is_leading('c'))
        True
        >>> bool(Run('abc').is_leading('x').is_leading('c'))
        False
        """
        return self._condition

    @property
    def position(self) -> int:
        """Current index position.

        >>> run = Run('abc')
        >>> run.position
        0
        >>> __ = run.walk() ; run.position
        1
        """
        return self._position

    @property
    def text(self) -> str:
        """Initial string.

        >>> Run('abc').text
        'abc'
        """
        return self._text

    @property
    def chars(self) -> list[str]:
        return self._chars

    @property
    def curr(self) -> Optional[_T]:
        """Attribute value for the current position, or None if it is invalid.

        `run.curr` is equivalent for `run.value()`.

        >>> run = Run('abc', lambda x: x.upper())
        >>> run.curr
        'A'
        >>> __ = run.walk() ; run.curr
        'B'
        """
        return self.attr()

    @property
    def prev(self) -> Optional[_T]:
        """Attribute value for the previous position, or None if it is invalid.

        `run.prev` is equivalent for `run.value(-1)`.

        >>> run = Run('abc', lambda x: x.upper())
        >>> run.prev    # returns None
        >>> __ = run.walk() ; run.prev
        'A'
        """
        return self.attr(-1)

    @property
    def next(self) -> Optional[_T]:
        """Attribute value for the next position, or None if it is not valid.

        `run.next` is equivalent for `run.value(1)`.

        >>> run = Run('abc', lambda x: x.upper())
        >>> run.next
        'B'
        >>> __ = run.walk() ; run.next
        'C'
        """
        return self.attr(1)

    @property
    def cc(self) -> Optional[str]:
        """Current code point (a single Unicode str object) at the position.

        >>> run = Run('abc', lambda x: x.upper())
        >>> run.cc
        'a'
        >>> __ = run.walk() ; run.cc
        'b'
        """
        return self.char()

    @property
    def pc(self) -> Optional[str]:
        """Previous code point (a single Unicode str object) at the position.

        >>> run = Run('abc', lambda x: x.upper())
        >>> run.pc
        >>> __ = run.walk() ; run.pc
        'a'
        """
        return self.char(-1)

    @property
    def nc(self) -> Optional[str]:
        """Next code point (a single Unicode str object) at the position.

        >>> run = Run('abc', lambda x: x.upper())
        >>> run.nc
        'b'
        >>> __ = run.walk() ; run.nc
        'c'
        """
        return self.char(1)

    def char(self, offset: int = 0, /, noskip: bool = False) -> Optional[str]:
        i = self._calc_position(offset, noskip=noskip)
        if self._condition and 0 <= i < len(self._chars):
            return self._chars[i]
        else:
            return None

    def is_sot(self) -> bool:
        return self._position == 0

    def is_eot(self) -> bool:
        return self._position == len(self._text) - 1

    def set_char(self, ch: str, /) -> None:
        self._chars[self._position] = ch

    def set_attr(self, attr: _T, /) -> None:
        self._attributes[self._position] = attr

    def _calc_position(self, offset: int, /, noskip: bool = False) -> int:
        """(internal) Return the index for the result of walking `offset` steps
        from the current postion.

        If `noskip` is `True`, skipping values are ignored.

        >>> run = Run('abc')
        >>> run._calc_position(1)
        1
        >>> run.set_skip_table([1, 0, 1])
        >>> run._calc_position(1)
        2
        >>> run._calc_position(1, noskip=True)
        1
        >>> run._calc_position(3)
        4
        """
        i = self._position
        vec = offset // abs(offset) if offset else 0
        for __ in range(abs(offset)):
            i += vec
            while (
                0 <= i < len(self._text)
                and not noskip
                and self._skip_table[i] == 0
            ):
                i += vec
        return i

    def attr(self, offset: int = 0, /, noskip: bool = False) -> Optional[_T]:
        """Return attrubute value at current position + offset.

        >>> run = Run('abc', lambda x: x.upper())
        >>> run.attr(1)
        'B'
        >>> run.attr(2)
        'C'
        >>> run.walk()
        True
        >>> run.attr(-1)
        'A'
        >>> run.head()
        >>> run.set_skip_table([1, 0, 1])
        >>> run.attr(1)
        'C'
        >>> run.attr(1, noskip=True)
        'B'
        """
        i = self._calc_position(offset, noskip=noskip)
        if self._condition and 0 <= i < len(self._text):
            return self._attributes[i]
        else:
            return None

    def attributes(self) -> list[_T]:
        """Return a copy of the list of its properties.

        >>> run = Run('abc', lambda x: x.upper())
        >>> run.attributes()
        ['A', 'B', 'C']
        """
        return self._attributes[:]

    def breakables(self) -> list[Optional[Breakable]]:
        """Return a copy of the list of the breakable oppotunity values."""
        return self._breakables[:]

    def walk(self, offset: int = 1, /, noskip: bool = False) -> bool:
        """Move current position for `offset` steps.

        Certain values specified as "skip" is ignored unless `noskip` flag is
        set as `True`.  Return if it successfully moved.

        >>> run = Run('abcde')
        >>> run.walk()
        True
        >>> run.curr
        'b'
        >>> run.set_skip_table([1, 1, 0, 0, 1])
        >>> run.walk()
        True
        >>> run.curr
        'e'
        >>> run.walk()
        False
        """
        if self._condition:
            pos = self._calc_position(offset, noskip=noskip)
            condition = False
            if pos < 0:
                pos = 0
            elif len(self._text) <= pos:
                pos = len(self._text) - 1
            else:
                condition = True
            self._position = pos
            self._condition = condition
        return self._condition

    def head(self) -> None:
        self._position = 0
        self._condition = True

    def set_skip_table(self, iter_skip: Iterable[Any], /) -> None:
        """Set the skip table for the run.

        Skip table must be the sequence of 0 / 1, which lenght is the same as
        the run text. 1 for count, 0 for skip.
        """
        skip_table = [int(bool(x)) for x in iter_skip]
        if (len(skip_table) != len(self.text)):
            raise ValueError('Skip table must be the same length as the text')
        self._skip_table[:] = skip_table

    def is_continuing(
        self,
        attrinfo: Union[_T, tuple[_T, ...]],
        /,
        greedy: bool = False,
        backward: bool = False,
        noskip: bool = False,
    ) -> 'Run[_T]':
        """Test if values appears before / after the current position.

        Return shallow copy of the instance which position is at the result of
        the rounting.

        >>> run = Run('abc', lambda x: x.upper())
        >>> run.is_continuing('B').curr
        'B'
        >>> run.is_continuing('B').next
        'C'
        >>> run.is_continuing('X', greedy=True).curr
        'A'
        >>> run.is_continuing('X', greedy=True).next
        'B'
        >>> bool(run.is_continuing('B').is_continuing('C'))
        True
        >>> run.walk()
        True
        >>> run.is_continuing('B').curr is None
        True
        >>> run.is_continuing('A', backward=True).curr
        'A'
        >>> run.is_continuing('X', greedy=True, backward=True).curr
        'B'

        >>> run = Run('abbbccd', lambda x: x.upper())
        >>> run.is_continuing('B', greedy=True).curr
        'B'
        >>> run.set_skip_table([1, 1, 1, 1, 0, 0, 1])
        >>> run.is_continuing('B', greedy=True).next
        'D'
        >>> run.is_continuing('B', greedy=True).attr(1, noskip=True)
        'C'

        >>> run = Run('abbbccd', lambda x: x.upper())
        >>> run.walk(4)
        True
        >>> run.curr
        'C'
        >>> run.is_continuing('B', greedy=True, backward=True).prev
        'A'

        >>> run = Run('abcde')
        >>> run.is_continuing(('b', 'x')).curr
        'b'
        """
        attrs = attrinfo if isinstance(attrinfo, tuple) else (attrinfo,)
        run = copy(self)
        vec = -1 if backward else 1
        if greedy:
            while run.attr(vec, noskip=noskip) in attrs:
                if not run.walk(vec, noskip=noskip):
                    break
            condition = True
        else:
            condition = run.walk(vec, noskip=noskip) and run.curr in attrs
        run._condition = self._condition and condition
        return run

    def is_following(
        self,
        attrs: Union[_T, tuple[_T, ...]],
        /,
        greedy: bool = False,
        noskip: bool = False,
    ) -> 'Run[_T]':
        return self.is_continuing(attrs, greedy=greedy, backward=True, noskip=noskip)

    def is_leading(
        self,
        attrs: Union[_T, tuple[_T, ...]],
        /,
        greedy: bool = False,
        noskip: bool = False,
    ) -> 'Run[_T]':
        return self.is_continuing(attrs, greedy=greedy, noskip=noskip)

    def break_here(self) -> None:
        if self._text and self._breakables[self._position] is None:
            self._breakables[self._position] = Breakable.Break

    def do_not_break_here(self) -> None:
        if self._text and self._breakables[self._position] is None:
            self._breakables[self._position] = Breakable.DoNotBreak

    def does_break_here(self) -> bool:
        return bool(self._breakables[self._position])

    def set_default(self, breakable: Breakable) -> None:
        self._breakables[:] = [
            breakable if x is None else x for x in self._breakables
        ]

    def literal_breakables(
        self, default: Breakable = Breakable.Break
    ) -> Iterable[Literal[0, 1]]:
        return (default.value if x is None else x.value for x in self._breakables)


def boundaries(breakables: Breakables, /) -> Iterator[int]:
    """Iterate boundary indices of the breakabe table, `breakables`.

    The boundaries start from 0 to the end of the sequence (==
    len(breakables)).

    >>> list(boundaries([1, 1, 1]))
    [0, 1, 2, 3]
    >>> list(boundaries([1, 0, 1]))
    [0, 2, 3]
    >>> list(boundaries([0, 1, 0]))
    [1, 3]

    It yields empty when the given sequece is empty.

    >>> list(boundaries([]))
    []
    """
    i = None
    for i, breakable in enumerate(breakables):
        if breakable:
            yield i
    if i is not None:
        yield i+1


def break_units(s: str, breakables: Breakables, /) -> Iterator[str]:
    """Iterate every tokens of `s` basing on breakable table, `breakables`.

    >>> list(break_units('ABC', [1, 1, 1])) == ['A', 'B', 'C']
    True
    >>> list(break_units('ABC', [1, 0, 1])) == ['AB', 'C']
    True
    >>> list(break_units('ABC', [1, 0, 0])) == ['ABC']
    True

    The length of `s` must be equal to that of `breakables`.
    """
    i = 0
    for j, bk in enumerate(breakables):
        if bk:
            if j:
                yield s[i:j]
            i = j
    if s:
        yield s[i:]


if __name__ == '__main__':
    import doctest
    doctest.testmod()
