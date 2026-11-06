"""Unicode 17 property enums. All values come from bundled tables."""
from .unicodeproperty import EnumProperty, character_property
from .db import get_value
class Category(EnumProperty):
    LU = 'Lu'
    LL = 'Ll'
    LT = 'Lt'
    LM = 'Lm'
    LO = 'Lo'
    MN = 'Mn'
    MC = 'Mc'
    ME = 'Me'
    ND = 'Nd'
    NL = 'Nl'
    NO = 'No'
    PC = 'Pc'
    PD = 'Pd'
    PS = 'Ps'
    PE = 'Pe'
    PI = 'Pi'
    PF = 'Pf'
    PO = 'Po'
    SM = 'Sm'
    SC = 'Sc'
    SK = 'Sk'
    SO = 'So'
    ZS = 'Zs'
    ZL = 'Zl'
    ZP = 'Zp'
    CC = 'Cc'
    CF = 'Cf'
    CS = 'Cs'
    CO = 'Co'
    CN = 'Cn'
GC = Category
class EastAsianWidth(EnumProperty):
    A = 'A'
    F = 'F'
    H = 'H'
    N = 'N'
    NA = 'Na'
    W = 'W'
EA = EastAsianWidth
@character_property
def category(c, /):
    return GC(get_value('General_Category', ord(c)))
@character_property
def east_asian_width(c, /):
    return EA(get_value('East_Asian_Width', ord(c)))
