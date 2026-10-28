"""Explicit HLG display black lift, ITU-R BT.2100-3 Table5 (original code).

Optional subclasses preserve the old zero-black signal/metadata contract.
Black luminance is an author declaration, not a monitor measurement.
"""
from dataclasses import dataclass
import math
from .float_hdr import LuminanceSignal,number,error

PROTOCOL='explicit-HLG-display-black-float32-v1'

def beta(signal):
    black=getattr(signal,'display_black_nits',0.)
    return math.sqrt(3*(black/signal.display_peak_nits)**(1/signal.system_gamma)) if black else 0.

def describe(signal):
    if signal.transfer!='hlg-bt2100':return None
    return dict(display_black_nits=getattr(signal,'display_black_nits',0.),black_lift_beta=beta(signal),
        explicitly_declared=hasattr(signal,'display_black_nits'),display_peak_nits=signal.display_peak_nits,
        system_gamma=signal.system_gamma,reference_white_nits=signal.reference_white_nits)

@dataclass(frozen=True)
class HLGBlackSignal(LuminanceSignal):
    display_black_nits:float=0.

    def __post_init__(self):
        super().__post_init__()
        if self.transfer!='hlg-bt2100':raise error('SIGNAL','display_black_nits只适用于HLG显示解释')
        number(self.display_black_nits,0,10,'display_black_nits')
        if not beta(self)<1:raise error('SIGNAL','HLG黑位提升beta必须小于1；否则输入量程退化/反向')

@dataclass(frozen=True)
class HLGBlackWhiteSignal(HLGBlackSignal):
    white_xy:tuple=(.3127,.329)

    def __post_init__(self):
        super().__post_init__()
        from .float_chromatic import validate_white,D65
        object.__setattr__(self,'white_xy',validate_white(self.white_xy))
        if self.white_xy!=D65:raise error('SIGNAL','BT.2100 HLG编码信号要求D65')
