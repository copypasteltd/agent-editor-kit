"""Explicit D65 linear BT.709 gamut reduction at constant OKLab L/hue.

OKLab matrices: Bjorn Ottosson, https://bottosson.github.io/posts/oklab/
(2021-01-25 coefficients, public domain/MIT). Original bounded ray search.
This is chroma boundary reduction, not ACES, CSS local-MINDE or a soft knee.
"""
import numpy as np

from .errors import AppError

PROTOCOL = 'oklab-constant-lightness-hue-bt709-v1'
ITERATIONS = 24
WHITE_LIGHTNESS_EPS = 1e-7  # Rounded published matrices do not give exactly neutral white.
RGB_LMS = np.array([[.4122214708,.5363325363,.0514459929],
                    [.2119034982,.6806995451,.1073969566],
                    [.0883024619,.2817188376,.6299787005]], np.float64)
LMS_LAB = np.array([[.2104542553,.7936177850,-.0040720468],
                    [1.9779984951,-2.4285922050,.4505937099],
                    [.0259040371,.7827717662,-.8086757660]], np.float64)
LAB_LMS = np.linalg.inv(LMS_LAB)
LMS_RGB = np.linalg.inv(RGB_LMS)


def reduce_chroma(rgb, *, cancel=None):
    """One <=65536-pixel Float64 tile; already in-gamut pixels bit-exact.

    Preserve OKLab L and atan2(b,a) when 0<L<1-1e-7. At/beyond the lightness
    endpoints use black/white explicitly. Not constant CIE Y luminance.
    The search selects the in-gamut side; no output component clamp.
    """
    if (not isinstance(rgb,np.ndarray) or rgb.dtype!=np.float64 or rgb.ndim!=2 or
            rgb.shape[1]!=3 or not 0<len(rgb)<=65536 or not np.isfinite(rgb).all()):
        raise AppError('FLOAT_GAMUT_INPUT','色域映射须为有限Float64 RGB有界分块',exit_code=2)
    poll=cancel or (lambda:None);poll()
    out=rgb.copy()
    outside=np.any((rgb<0)|(rgb>1),axis=1)
    stats=dict(gamut_pixels_mapped=int(outside.sum()),gamut_lightness_to_black_pixels=0,
               gamut_lightness_to_white_pixels=0,gamut_chroma_reduced_pixels=0)
    if not np.any(outside):return out,stats
    lab=np.cbrt(rgb[outside]@RGB_LMS.T)@LMS_LAB.T
    black=lab[:,0]<=0;white=lab[:,0]>=1-WHITE_LIGHTNESS_EPS;active=~(black|white)
    result=np.zeros_like(lab);result[white]=1
    stats['gamut_lightness_to_black_pixels']=int(black.sum())
    stats['gamut_lightness_to_white_pixels']=int(white.sum())
    stats['gamut_chroma_reduced_pixels']=int(active.sum())
    if np.any(active):
        chosen=lab[active];lo=np.zeros(len(chosen));hi=np.ones(len(chosen))
        # The neutral endpoint is inside the RGB cube. Keep the last verified
        # candidate, including very dark/light values, instead of clamping.
        neutral=np.zeros_like(chosen);neutral[:,0]=chosen[:,0]
        best=((neutral@LAB_LMS.T)**3)@LMS_RGB.T
        for _ in range(ITERATIONS):
            poll();mid=(lo+hi)*.5
            trial=chosen.copy();trial[:,1:]*=mid[:,None]
            candidate=((trial@LAB_LMS.T)**3)@LMS_RGB.T
            inside=np.all((candidate>=0)&(candidate<=1),axis=1)
            best[inside]=candidate[inside];lo=np.where(inside,mid,lo);hi=np.where(inside,hi,mid)
        result[active]=best
    out[outside]=result;poll()
    if not np.isfinite(out).all() or np.any((out<0)|(out>1)):
        raise AppError('FLOAT_GAMUT_DOMAIN','色域映射不能产生有限单位RGB域结果',exit_code=2)
    return out,stats
