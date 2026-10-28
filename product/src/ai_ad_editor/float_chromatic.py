"""Explicit RGB reference whites and Bradford adaptation in linear XYZ.

Original implementation. Native D65 behavior is retained; built-in D50/D60
chromaticities follow CSS Color 4 and the Academy's ACEScg specification.
This is an explicit colorimetric transform, not ICC parsing or an ACES DRT.
"""
from dataclasses import dataclass
import math
import numpy as np

from .errors import AppError
from .float_color_signal import ColorSignal, PRIMARIES
from .float_hdr import LuminanceSignal

PROTOCOL='explicit-white-Bradford-float32-v1'
D65=(.3127,.329)
D50=(.3457,.3585)
D60=(.32168,.33767)
DEFAULT_WHITES={'prophoto-rgb':D50,'aces-ap1':D60}
BRADFORD=np.array([[.8951,.2664,-.1614],[-.7502,1.7135,.0367],[.0389,-.0685,1.0296]],np.float64)


def error(code,message):return AppError('FLOAT_CHROMATIC_'+code,message,exit_code=2)


def validate_white(value):
    if not isinstance(value,(list,tuple)) or len(value)!=2:
        raise error('WHITE','white_xy须为两个有限CIE1931色度数值')
    if any(type(v) not in (int,float) or not .0001<=v<=.9998 or not math.isfinite(v) for v in value):
        raise error('WHITE','白点xy须为有限数值且在0.0001..0.9998之间')
    x,y=map(float,value)
    if x+y>=.9999:raise error('WHITE','白点必须具有正的XYZ三刺激分量')
    return x,y


def white_for_primaries(primaries):return DEFAULT_WHITES.get(primaries,D65)


def white_of(signal):
    return validate_white(signal.white_xy) if hasattr(signal,'white_xy') else white_for_primaries(signal.primaries)


def xyz_white(white):
    x,y=validate_white(white)
    return np.array([x/y,1.,(1-x-y)/y],np.float64)


def validate_RGB_white(primaries,white):
    coordinates=np.array(PRIMARIES[primaries],np.float64);x,y=coordinates[:,0],coordinates[:,1]
    columns=np.stack((x/y,np.ones(3),(1-x-y)/y))
    scales=np.linalg.solve(columns,xyz_white(white))
    if not np.isfinite(scales).all() or np.min(scales)<=1e-8:
        raise error('WHITE_GAMUT','声明白点须位于RGB基色三角形内部')
    cones=BRADFORD@xyz_white(white)
    if np.min(cones)<=1e-8:raise error('CONE','声明白点无法进行支持的正锥响应Bradford适应')


@dataclass(frozen=True)
class WhitePointSignal(ColorSignal):
    white_xy:tuple

    def __post_init__(self):
        super().__post_init__()
        object.__setattr__(self,'white_xy',validate_white(self.white_xy))
        validate_RGB_white(self.primaries,self.white_xy)


@dataclass(frozen=True)
class WhitePointLuminanceSignal(LuminanceSignal):
    white_xy:tuple=D65

    def __post_init__(self):
        super().__post_init__()
        object.__setattr__(self,'white_xy',validate_white(self.white_xy))
        validate_RGB_white(self.primaries,self.white_xy)
        if self.transfer in {'pq-st2084','hlg-bt2100'} and self.white_xy!=D65:
            raise error('HDR_WHITE','BT.2100 PQ/HLG编码端要求D65；须先在明确线性工作域转换')


def bradford_matrix(source_white,target_white):
    source_white=validate_white(source_white);target_white=validate_white(target_white)
    if source_white==target_white:return np.eye(3,dtype=np.float64)
    a,b=BRADFORD@xyz_white(source_white),BRADFORD@xyz_white(target_white)
    if np.min(a)<=1e-8 or np.min(b)<=1e-8:raise error('CONE','Bradford要求正的白点锥响应')
    return np.linalg.solve(BRADFORD,np.diag(b/a)@BRADFORD)


def conversion(source,target):
    from .float_color_signal import _rgb_to_xyz
    a,b=white_of(source),white_of(target)
    adaptation=bradford_matrix(a,b)
    if source.primaries==target.primaries and a==b:matrix=np.eye(3,dtype=np.float64)
    else:
        incoming=_rgb_to_xyz(source.primaries,a)
        matrix=np.linalg.solve(_rgb_to_xyz(target.primaries,b),adaptation@incoming if a!=b else incoming)
    extended=any(hasattr(v,'white_xy') or v.primaries in DEFAULT_WHITES for v in (source,target))
    return matrix,dict(extended=extended,source_white_xy=list(a),target_white_xy=list(b),
        method='Bradford' if a!=b else 'identity',XYZ_adaptation_matrix=adaptation.tolist(),
        chromatic_adaptation=a!=b,reference_white_Y=1.,ICC_profile_parsed=False,ACES_output_transform=False)


def equivalent(source,target):
    if source==target:return True
    if source.primaries!=target.primaries or source.transfer!=target.transfer or white_of(source)!=white_of(target):return False
    return {k:v for k,v in vars(source).items() if k!='white_xy'}=={k:v for k,v in vars(target).items() if k!='white_xy'}
