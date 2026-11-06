"""Unicode 17 Extended_Pictographic, backed by pinned UCD data."""
from .db import get_value
from .unicodeproperty import character_property

@character_property
def extended_pictographic(c, /):
    return get_value('Extended_Pictographic', ord(c)) == 'Yes'
