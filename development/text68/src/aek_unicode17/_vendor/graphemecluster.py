# Adapted from uniseg 0.10.1, Copyright (c) 2013-2024 Masaaki Shibata.
# MIT; see ../LICENSE_UNISEG.txt. AEK changes: relative imports and pinned Unicode 17.
"""Unicode grapheme cluster boundaries.

`UAX #29: Unicode Text Segmentation (Unicode 17.0.0)
<https://www.unicode.org/reports/tr29/tr29-47.html>`_
"""

from typing import Iterator, Optional

from .breaking import (Breakable, Breakables, Run, TailorFunction, boundaries,
                             break_units)
from .db import get_handle, get_value
from .derived import InCB, indic_conjunct_break
from .emoji import extended_pictographic
from .unicodeproperty import EnumProperty, PropertyFunction, character_property

__all__ = [
    'GraphemeClusterBreak',
    'GCB',
    'grapheme_cluster_break',
    'grapheme_cluster_breakables',
    'grapheme_cluster_boundaries',
    'grapheme_clusters',
]


class GraphemeClusterBreak(EnumProperty):
    """Grapheme_Cluster_Break property values in UAX #29."""

    __propname__ = 'Grapheme_Cluster_Break'

    OTHER = 'Other'
    """Grapheme_Cluster_Break property value Other"""

    CR = 'CR'
    """Grapheme_Cluster_Break property value CR"""

    LF = 'LF'
    """Grapheme_Cluster_Break property value LF"""

    CONTROL = 'Control'
    """Grapheme_Cluster_Break property value Control"""

    EXTEND = 'Extend'
    """Grapheme_Cluster_Break property value Extend"""

    ZWJ = 'ZWJ'
    """Grapheme_Cluster_Break property value ZWJ"""

    REGIONAL_INDICATOR = 'Regional_Indicator'
    """Grapheme_Cluster_Break property value Regional_Indicator"""

    PREPEND = 'Prepend'
    """Grapheme_Cluster_Break property value Prepend"""

    PACINGMARK = 'SpacingMark'
    """Grapheme_Cluster_Break property value SpacingMark"""

    L = 'L'
    """Grapheme_Cluster_Break property value L"""

    V = 'V'
    """Grapheme_Cluster_Break property value V"""

    T = 'T'
    """Grapheme_Cluster_Break property value T"""

    LV = 'LV'
    """Grapheme_Cluster_Break property value LV"""

    LVT = 'LVT'
    """Grapheme_Cluster_Break property value LVT"""


# type alias for `GraphemeClusterBreak`
GCB = GraphemeClusterBreak


_H_GCB = get_handle('Grapheme_Cluster_Break')


@character_property
def grapheme_cluster_break(c: str, /) -> GraphemeClusterBreak:
    R"""Return the Grapheme_Cluster_Break value assigned to the code point `c`.

    `c` must be a single Unicode character (code point).

    >>> grapheme_cluster_break('a')
    GraphemeClusterBreak.OTHER
    >>> grapheme_cluster_break('\r')
    GraphemeClusterBreak.CR
    >>> print(grapheme_cluster_break('\n'))
    LF
    """
    return GraphemeClusterBreak(get_value(_H_GCB, ord(c)) or 'Other')


def _ep(c: Optional[str], /) -> Optional[bool]:
    """(internal) Same as `extended_pictographic` but also accepts `None` as an
    argument, which returns `None` in that case."""
    return False if c is None else extended_pictographic(c)


def grapheme_cluster_breakables(
    s: str,
    /,
    *,
    property: PropertyFunction[GraphemeClusterBreak] = grapheme_cluster_break
) -> Breakables:
    R"""Iterate grapheme cluster breaking opportunities for every
    position of `s`.

    1 for "break" and 0 for "do not break".  The length of iteration
    will be the same as ``len(s)``.

    >>> list(grapheme_cluster_breakables('ABC'))
    [1, 1, 1]
    >>> list(grapheme_cluster_breakables('g̈')) # (== '\u0067\u0308')
    [1, 0]
    >>> list(grapheme_cluster_breakables(''))
    []
    """
    if not s:
        return iter([])

    run = Run(s, indic_conjunct_break)
    while run.walk():
        if (
            run.is_following(
                (InCB.EXTEND, InCB.LINKER), greedy=True
            ).prev == InCB.CONSONANT
            and run.is_following(InCB.EXTEND, greedy=True).prev != InCB.CONSONANT
            and run.curr == InCB.CONSONANT
        ):
            run.do_not_break_here()
    incb_breakables = run.breakables()

    run = Run(s, property)
    while run.walk():
        # GB3
        if run.prev == GCB.CR and run.curr == GCB.LF:
            run.do_not_break_here()
        # GB4, GB5
        elif (
            run.prev in (GCB.CONTROL, GCB.CR, GCB.LF)
            or run.curr in (GCB.CONTROL, GCB.CR, GCB.LF)
        ):
            run.break_here()
        # GB6, GB7, GB8
        elif (
            (run.prev == GCB.L and run.curr in (GCB.L, GCB.V, GCB.LV, GCB.LVT))
            or (run.prev in (GCB.LV, GCB.V) and run.curr in (GCB.V, GCB.T))
            or (run.prev in (GCB.LVT, GCB.T) and run.curr == GCB.T)
        ):
            run.do_not_break_here()
        elif run.curr in (GCB.EXTEND, GCB.ZWJ):
            run.do_not_break_here()
        # GB9a, GB9b
        elif run.curr == GCB.PACINGMARK or run.prev == GCB.PREPEND:
            run.do_not_break_here()
        # GB9c
        elif incb_breakables[run.position] is Breakable.DoNotBreak:
            run.do_not_break_here()
        # GB11
        elif (
            _ep(run.is_following(GCB.ZWJ).is_following(GCB.EXTEND, greedy=True).pc)
            and _ep(run.cc)
        ):
            run.do_not_break_here()
    # GB12, GB13
    run.head()
    while 1:
        while run.curr != GCB.REGIONAL_INDICATOR:
            if not run.walk():
                break
        if not run.walk():
            break
        while run.prev == run.curr == GCB.REGIONAL_INDICATOR:
            run.do_not_break_here()
            if not run.walk():
                break
            if not run.walk():
                break
    run.set_default(Breakable.Break)
    return run.literal_breakables()


def grapheme_cluster_boundaries(
    s: str,
    /,
    *,
    property: PropertyFunction[GraphemeClusterBreak] = grapheme_cluster_break,
    tailor: Optional[TailorFunction] = None,
) -> Iterator[int]:
    R"""Iterate indices of the grapheme cluster boundaries of `s`.

    This function yields from 0 to the end of the string (== len(s)).

    >>> list(grapheme_cluster_boundaries('ABC'))
    [0, 1, 2, 3]
    >>> list(grapheme_cluster_boundaries('g̈')) # (== '\u0067\u0308')
    [0, 2]
    >>> list(grapheme_cluster_boundaries(''))
    []
    """
    breakables = grapheme_cluster_breakables(s, property=property)
    if tailor is not None:
        breakables = tailor(s, breakables)
    return boundaries(breakables)


def grapheme_clusters(
    s: str,
    /,
    *,
    property: PropertyFunction[GraphemeClusterBreak] = grapheme_cluster_break,
    tailor: Optional[TailorFunction] = None,
) -> Iterator[str]:
    R"""Iterate every grapheme cluster token of `s`.

    Grapheme clusters (both legacy and extended):

    >>> list(grapheme_clusters('g̈')) # (== '\u0067\u0308')
    ['g̈']
    >>> list(grapheme_clusters('각')) # (== '\uac01')
    ['각']
    >>> list(grapheme_clusters('각')) # (== '\u1100\u1161\u11a8')
    ['각']

    Extended grapheme clusters:

    >>> list(grapheme_clusters('நி')) # (== '\u0ba8\u0bbf')
    ['நி']
    >>> list(grapheme_clusters('षि')) # (== '\u0937\u093f')
    ['षि']

    Empty string leads the result of empty sequence:

    >>> list(grapheme_clusters(''))
    []

    You can customize the default breaking behavior by modifying breakable
    table so as to fit the specific locale in `tailor` function.  It receives
    `s` and its default breaking sequence (iterator) as its arguments and
    returns the sequence of customized breaking opportunities:

    >>> def tailor_gcb_breakables(s, breakables) -> Breakables:
    ...     for i, breakable in enumerate(breakables):
    ...         # don't break between 'c' and 'h'
    ...         if s.endswith('c', 0, i) and s.startswith('h', i):
    ...             yield 0
    ...         else:
    ...             yield breakable
    ...
    >>> list(grapheme_clusters('Czech'))
    ['C', 'z', 'e', 'c', 'h']
    >>> list(grapheme_clusters('Czech', tailor=tailor_gcb_breakables))
    ['C', 'z', 'e', 'ch']
    """
    breakables = grapheme_cluster_breakables(s, property=property)
    if tailor is not None:
        breakables = tailor(s, breakables)
    return break_units(s, breakables)


if __name__ == '__main__':
    import doctest
    doctest.testmod()
