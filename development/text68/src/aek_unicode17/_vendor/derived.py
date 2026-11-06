"""Unicode 17 Indic_Conjunct_Break, backed by pinned UCD data."""
from .db import get_value
from .unicodeproperty import EnumProperty, character_property

class IndicConjunctBreak(EnumProperty):
    NONE = 'None'
    LINKER = 'Linker'
    CONSONANT = 'Consonant'
    EXTEND = 'Extend'

InCB = IndicConjunctBreak

@character_property
def indic_conjunct_break(c, /):
    return InCB(get_value('InCB', ord(c)))
