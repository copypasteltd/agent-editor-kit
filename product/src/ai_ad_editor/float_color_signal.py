"""Explicit RGB signal conversion on bounded straight Float32 surfaces.

The caller chooses a relative transfer interpretation; a video 'bt709' tag
alone cannot choose scene inverse-OETF versus a reference-display EOTF.
The optional LuminanceSignal adapter adds explicitly declared display-light
PQ/HLG/nit units. Legacy two-field relative signals retain their exact v1
semantics. Explicit whites add Bradford adaptation; ICC and HDR display
acceptance require separate handling.
Only an explicitly requested HDR output domain policy can clamp RGB.

Primary xy coordinates: ITU-R BT.709-6, BT.2020-2 and W3C CSS Color 4
(2026-10-20). sRGB uses its signed extension; other power curves use an
explicit signed mathematical extension. BT.709 uses the published rounded
OETF constants, including their small discontinuity, not a hidden 'gamma'.
"""
from __future__ import annotations
from dataclasses import dataclass
import numpy as np
from .errors import AppError

PROTOCOL='explicit-D65-relative-RGB-float32-v1'
PRIMARIES={'bt709':((.640,.330),(.300,.600),(.150,.060)),
           'display-p3':((.680,.320),(.265,.690),(.150,.060)),
           'bt2020':((.708,.292),(.170,.797),(.131,.046)),
           'prophoto-rgb':((.734699,.265301),(.159597,.840403),(.036598,.000105)),
           'aces-ap1':((.713,.293),(.165,.830),(.128,.044))}
TRANSFERS={'linear','srgb','bt709-oetf','gamma22','gamma24','prophoto-rgb'}
MAX_DIMENSION=16384
MAX_PIXELS=16777216
MAX_WORKING_BYTES=768*1024*1024
MAX_TILE_PIXELS=262144

def error(code,message):return AppError('FLOAT_COLOR_'+code,message,exit_code=2)

@dataclass(frozen=True)
class ColorSignal:
    primaries:str
    transfer:str

    def __post_init__(self):
        if not isinstance(self.primaries,str) or self.primaries not in PRIMARIES:
            raise error('SIGNAL','RGB基色须明确且属于支持的集合')
        if not isinstance(self.transfer,str) or self.transfer not in TRANSFERS:
            raise error('SIGNAL','须明确选择相对RGB传递解释；禁止由色彩标签猜测')

def _rgb_to_xyz(primaries,white_xy=None):
    from .float_chromatic import white_for_primaries,xyz_white
    coordinates=np.array(PRIMARIES[primaries],dtype=np.float64)
    x,y=coordinates[:,0],coordinates[:,1]
    columns=np.stack((x/y,np.ones(3),(1-x-y)/y))
    white=xyz_white(white_for_primaries(primaries) if white_xy is None else white_xy)
    scales=np.linalg.solve(columns,white)
    return columns*scales

def _to_linear(values,transfer):
    if transfer=='linear':return values
    absolute=np.abs(values);sign=np.sign(values)
    if transfer=='srgb':
        return np.where(absolute<=.04045,values/12.92,sign*((absolute+.055)/1.055)**2.4)
    if transfer=='bt709-oetf':
        return np.where(absolute<.081,values/4.5,sign*((absolute+.099)/1.099)**(1/.45))
    if transfer=='prophoto-rgb':
        return np.where(absolute<=1/32,values/16,sign*absolute**1.8)
    return sign*absolute**(2.2 if transfer=='gamma22' else 2.4)

def _from_linear(values,transfer):
    if transfer=='linear':return values
    absolute=np.abs(values);sign=np.sign(values)
    if transfer=='srgb':
        return np.where(absolute<=.0031308,values*12.92,sign*(1.055*absolute**(1/2.4)-.055))
    if transfer=='bt709-oetf':
        return np.where(absolute<.018,values*4.5,sign*(1.099*absolute**.45-.099))
    if transfer=='prophoto-rgb':
        return np.where(absolute<1/512,values*16,sign*absolute**(1/1.8))
    return sign*absolute**(1/(2.2 if transfer=='gamma22' else 2.4))

def convert_rgba(source,source_signal,target_signal,*,tile_pixels=65536,
                 max_working_bytes=MAX_WORKING_BYTES,cancel=None,hdr_range_policy='reject',hdr_input_range_policy='reject'):
    """Return owned straight RGBA Float32 with explicit signal metadata.

    Source inverse transfer -> explicit-white linear XYZ/adaptation -> target transfer.
    Identical signals use a byte-exact copy after validation. Finite RGB may be
    negative or above one. Relative white is 1; matching physical white/nits is
    a caller contract and is not inferred or managed here.
    """
    if not isinstance(source_signal,ColorSignal) or not isinstance(target_signal,ColorSignal):
        raise error('SIGNAL','输入与输出必须提供明确ColorSignal')
    from .float_hdr import HDR_TRANSFERS, has_luminance, to_linear, from_linear, domain
    absolute=has_luminance(source_signal) or has_luminance(target_signal)
    hdr=source_signal.transfer in HDR_TRANSFERS or target_signal.transfer in HDR_TRANSFERS
    if hdr and not (has_luminance(source_signal) and has_luminance(target_signal)):
        raise error('SIGNAL','PQ/HLG转换两端均须明确reference_white_nits；不能猜测相对RGB的亮度')
    if not isinstance(hdr_range_policy,str) or hdr_range_policy not in {'reject','clip'}:raise error('SIGNAL','HDR输出域策略须明确reject/clip')
    if not isinstance(hdr_input_range_policy,str) or hdr_input_range_policy not in {'reject','clip'}:raise error('SIGNAL','HDR输入域策略须明确reject/clip')
    if cancel is not None and not callable(cancel):raise error('ARGUMENT','取消回调无效')
    poll=cancel if cancel is not None else lambda:None;poll()
    if not isinstance(source,np.ndarray) or source.dtype!=np.dtype('float32') or source.ndim!=3 or source.shape[-1]!=4 or not source.flags.c_contiguous:
        raise error('SURFACE','输入必须是连续H×W×4 Float32表面')
    height,width=source.shape[:2];pixels=width*height
    if not 1<=min(width,height) or max(width,height)>MAX_DIMENSION or pixels>MAX_PIXELS:
        raise error('BUDGET','色彩表面尺寸超过预算')
    for value,limit in ((tile_pixels,MAX_TILE_PIXELS),(max_working_bytes,MAX_WORKING_BYTES)):
        if isinstance(value,bool) or not isinstance(value,(int,np.integer)) or not 1<=value<=limit:
            raise error('BUDGET','色彩分块或工作区预算无效')
    tile_pixels=int(tile_pixels);estimated=source.nbytes+pixels*16+min(tile_pixels,pixels)*(512 if absolute else 384)+4096
    if estimated>max_working_bytes:raise error('BUDGET','相对RGB转换超过工作区估算')
    source_rows=source.reshape(-1,4);output=np.empty_like(source_rows)
    from .float_chromatic import conversion,equivalent
    same=equivalent(source_signal,target_signal);matrix,chromatic=conversion(source_signal,target_signal)
    unit_scale=(source_signal.reference_white_nits/target_signal.reference_white_nits
                if has_luminance(source_signal) and has_luminance(target_signal) else 1.)
    hdr_clipped=0;hdr_input_clipped=0
    for start in range(0,pixels,tile_pixels):
        poll();value=source_rows[start:start+tile_pixels];out=output[start:start+len(value)]
        if not np.isfinite(value).all() or np.any(value[:,3]<0) or np.any(value[:,3]>1):
            raise error('SURFACE','RGB须有限且alpha须在0..1范围')
        incoming=None
        if source_signal.transfer in HDR_TRANSFERS:
            incoming=value[:,:3].astype(np.float64)
            incoming,clipped=domain(incoming,0,1,policy=hdr_input_range_policy,stage='输入PQ/HLG编码RGB')
            hdr_input_clipped+=clipped
        if same:
            out[:]=value
            if source_signal.transfer in HDR_TRANSFERS:out[:,:3]=incoming
            continue
        if incoming is None:incoming=value[:,:3].astype(np.float64)
        with np.errstate(over='ignore',invalid='ignore'):
            linear=to_linear(incoming,source_signal) if absolute else _to_linear(incoming,source_signal.transfer)
            # Explicit scalar column expressions avoid BLAS reduction choices
            # changing output rounding with the chosen tile length.
            transformed=np.empty_like(linear)
            for c in range(3):transformed[:,c]=linear[:,0]*matrix[c,0]+linear[:,1]*matrix[c,1]+linear[:,2]*matrix[c,2]
            if unit_scale!=1:transformed*=unit_scale
            if absolute:
                result,clipped=from_linear(transformed,target_signal,policy=hdr_range_policy);hdr_clipped+=clipped
            else:result=_from_linear(transformed,target_signal.transfer)
            out[:,:3]=result
        out[:,3]=value[:,3]
        if not np.isfinite(out).all():raise error('VALUES','转换结果超过Float32有限范围')
    poll()
    metadata={
        'protocol':PROTOCOL,'source_signal':{'primaries':source_signal.primaries,'transfer':source_signal.transfer},
        'target_signal':{'primaries':target_signal.primaries,'transfer':target_signal.transfer},
        'linear_gamut_matrix':matrix.tolist(),'white':'D65;relative-white=1;physical-white-matching-is-caller-contract',
        'alpha':'bit-exact-independent-straight-coverage','RGB_clipping':'none','gamut_mapping':'none',
        'negative_extension':'signed mathematical extension;not-HDR-acceptance',
        'bt709_interpretation':'published rounded camera OETF/inverse;not-BT1886-display-EOTF',
        'same_signal_byte_exact':same,'chromatic_adaptation':False,'absolute_nits_managed':False,
        'estimated_working_bytes':estimated,'estimated_bytes_are_peak_RSS':False,
        'HDR_accepted':False,'editor_integrated':False}
    if absolute:
        metadata.update(protocol='explicit-display-nits-PQ-HLG-float32-v1',
            source_signal=vars(source_signal),target_signal=vars(target_signal),
            linear_unit_scale=unit_scale,absolute_nits_managed=hdr or
                (has_luminance(source_signal) and has_luminance(target_signal)),
            relative_author_color_unit_inherited=not (has_luminance(source_signal) and has_luminance(target_signal)),
            white='D65; explicit declared reference_white_nits; display-linear working RGB',
            hdr_output_domain_policy=hdr_range_policy,hdr_output_components_clipped=hdr_clipped,
            hdr_input_domain_policy=hdr_input_range_policy,hdr_input_components_clipped=hdr_input_clipped,
            same_signal_byte_exact=same and hdr_input_clipped==0,
            RGB_clipping='explicit-HDR-input-or-output-domain-only' if hdr_clipped or hdr_input_clipped else 'none',
            HLG_black_level_nits=0,HLG_RGB_coupled_OOTF=True,
            negative_extension='legacy relative transfers only; standard PQ/HLG domains enforced')
        if any(hasattr(s,'display_black_nits') for s in (source_signal,target_signal)):
            from .float_hlg_black import describe
            metadata.pop('HLG_black_level_nits')
            metadata['HLG_black_level']={'protocol':'explicit-HLG-display-black-float32-v1',
                'source':describe(source_signal),'target':describe(target_signal),'black_luminance_inferred':False,
                'below_black_output_policy':hdr_range_policy}
    if chromatic['extended']:
        metadata.update(base_protocol=metadata['protocol'],protocol='explicit-white-Bradford-float32-v1',
            source_signal=vars(source_signal),target_signal=vars(target_signal),
            chromatic_adaptation=chromatic['chromatic_adaptation'],chromatic_transform=chromatic,
            white='explicit RGB reference white; Bradford on linear XYZ; no automatic physical illuminant estimation')
    return output.reshape(height,width,4),metadata
