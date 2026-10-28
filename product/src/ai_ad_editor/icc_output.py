"""Pinned native RGB ICC output and real LittleCMS soft-proof transforms.

Linear working RGB is never relabelled as an arbitrary device RGB space.
These transforms own independent contexts, profile handles and read locks.
"""
import ctypes as C
from dataclasses import dataclass
from pathlib import Path
import numpy as np
from . import icc_profiles as icc
from .float_color_signal import ColorSignal

PROTOCOL='explicit-native-icc-output-float32-v1'
PROOF_PROTOCOL='explicit-native-icc-softproof-float32-v1'

@dataclass(frozen=True)
class ICCOutputSignal(icc.ICCSourceSignal):
    pass

def parse_output_profile(value):
    if not isinstance(value,dict) or 'icc_profile' not in value:raise icc.error('OUTPUT','须明确完整ICC输出配置')
    signal=icc.parse_source_signal(value)
    return ICCOutputSignal(**vars(signal))

def proof_configuration(value):
    if not isinstance(value,dict) or set(value)!={'profile','simulation_intent'}:raise icc.error('PROOF','软打样须明确profile与simulation_intent')
    signal=parse_output_profile(value['profile']);intent=value['simulation_intent']
    if not isinstance(intent,str) or intent not in icc.INTENTS:raise icc.error('INTENT','软打样模拟意图无效')
    if signal.reference_white_nits is not None:raise icc.error('PROOF','软打样是相对PCS模拟；物理亮度须在显示映射单独声明，不能写入proof profile')
    return signal,intent

def linear_profile(a,context,working):
    if not isinstance(working,ColorSignal) or working.transfer!='linear':raise icc.error('WORKING','ICC输出/软打样要求明确线性RGB工作信号')
    prim=icc.Primaries(*(icc.xyY(x,y,1) for x,y in icc.PRIMARIES[working.primaries]))
    white=icc.xyY(*icc.white_of(working),1);curve=a.cmsBuildGamma(context,1.)
    if not curve:raise icc.error('RUNTIME','无法建立线性ICC工作曲线')
    try:profile=a.cmsCreateRGBProfileTHR(context,C.byref(white),C.byref(prim),(C.c_void_p*3)(curve,curve,curve))
    finally:a.cmsFreeToneCurve(curve)
    if not profile:raise icc.error('WORKING','无法建立原生线性ICC工作配置')
    return profile

def blocks(source,tile_pixels,max_working_bytes):
    if not isinstance(source,np.ndarray) or source.dtype!=np.dtype('float32') or source.ndim!=3 or source.shape[-1]!=4 or not source.flags.c_contiguous:
        raise icc.error('SURFACE','ICC输出要求连续HxWx4 Float32表面')
    h,w=source.shape[:2];pixels=h*w
    if not 1<=min(h,w) or max(h,w)>16384 or pixels>16777216:raise icc.error('BUDGET','ICC输出表面超出尺寸预算')
    if type(tile_pixels) is not int or not 1<=tile_pixels<=icc.MAX_TILE_PIXELS or type(max_working_bytes) is not int or not 1<=max_working_bytes<=icc.MAX_WORKING_BYTES:
        raise icc.error('BUDGET','ICC输出分块/工作区预算无效')
    estimated=source.nbytes*2+min(tile_pixels,pixels)*80+4096
    if estimated>max_working_bytes:raise icc.error('BUDGET','ICC输出工作区估算超出预算')
    return source.reshape(-1,4),estimated

class OutputProfileTransform(icc.ProfileTransform):
    def __init__(self,root,signal,working,*,cancel=None):
        if not isinstance(signal,ICCOutputSignal):raise icc.error('OUTPUT','须明确ICCOutputSignal而非来源信号')
        if not isinstance(working,ColorSignal) or working.transfer!='linear':raise icc.error('WORKING','ICC输出要求明确线性RGB')
        super().__init__(root,signal,None,cancel=cancel)
        try:
            p=Path(__file__).resolve();self.artifacts[str(p)]=self.guard.entry(p,'native-icc-output-runtime')
            self.output,self.input=self.input,None;self.working=working
            if not self.a.cmsIsIntentSupported(self.output,icc.INTENTS[signal.intent],1):raise icc.error('INTENT','该ICC配置未声明所选输出意图；不回退其他表')
            self.input=linear_profile(self.a,self.context,working)
            flags=0x0040|0x0100|(0x2000 if signal.black_point_compensation else 0)
            self.transform=self.a.cmsCreateTransformTHR(self.context,self.input,icc.TYPE_RGB_FLT,self.output,icc.TYPE_RGB_FLT,icc.INTENTS[signal.intent],flags)
            if not self.transform or self.errors:raise icc.error('TRANSFORM','无法建立原生ICC输出转换')
            src_nits=getattr(working,'reference_white_nits',None)
            if (src_nits is None)!=(signal.reference_white_nits is None):raise icc.error('LUMINANCE','ICC输出两端须同时明确参考白nits或均使用相对单位')
            self.unit_scale=src_nits/signal.reference_white_nits if src_nits is not None else 1.
            self.metadata.pop('source_profile');self.metadata.update(protocol=PROTOCOL,output_profile=vars(signal),working_signal=vars(working),
                linear_input_unit_scale=self.unit_scale,rendering_intent=signal.intent,black_point_compensation=signal.black_point_compensation,
                output_direction=1,flags=flags,alpha='bit-exact-independent-straight-coverage',native_profile_mapping_not_overridden=True)
            self.verify()
        except BaseException:self.close(verify=False);raise

    def convert(self,source,*,tile_pixels=65536,max_working_bytes=icc.MAX_WORKING_BYTES,range_policy='reject'):
        self.verify()
        if not isinstance(range_policy,str) or range_policy not in ('reject','clip'):raise icc.error('RANGE','ICC输出须明确reject/clip')
        rows,estimated=blocks(source,tile_pixels,max_working_bytes);output=np.empty_like(rows);clipped=negative=superwhite=0
        for start in range(0,len(rows),tile_pixels):
            self.poll();v=rows[start:start+tile_pixels];o=output[start:start+len(v)]
            if not np.isfinite(v).all() or np.any(v[:,3]<0) or np.any(v[:,3]>1):raise icc.error('INPUT_RANGE','线性ICC输入须有限，alpha须在0..1')
            negative+=int(np.count_nonzero(v[:,:3]<0));superwhite+=int(np.count_nonzero(v[:,:3]>1))
            incoming=np.ascontiguousarray(v[:,:3] if self.unit_scale==1 else (v[:,:3].astype(np.float64)*self.unit_scale).astype(np.float32))
            if not np.isfinite(incoming).all():raise icc.error('VALUES','ICC输入亮度缩放溢出Float32')
            converted=np.empty_like(incoming);self.a.cmsDoTransform(self.transform,incoming.ctypes.data,converted.ctypes.data,len(v))
            if self.errors or not np.isfinite(converted).all():raise icc.error('TRANSFORM','原生ICC输出失败或非有限')
            outside=(converted<0)|(converted>1);n=int(np.count_nonzero(outside));clipped+=n
            if n and range_policy=='reject':raise icc.error('OUTPUT_RANGE','ICC设备RGB超出0..1；须明确选择clip')
            o[:,:3]=np.clip(converted,0,1) if n else converted;o[:,3]=v[:,3]
        self.verify();receipt=dict(self.metadata,estimated_working_bytes=estimated,estimate_is_peak_RSS=False,converted_pixels=len(rows),
            output_range_policy=range_policy,encoded_output_components_clipped=clipped,negative_working_components=negative,superwhite_working_components=superwhite)
        return output.reshape(source.shape),receipt

class SoftProofTransform(icc.ProfileTransform):
    def __init__(self,root,signal,working,simulation_intent,*,cancel=None):
        self.proof=None
        if not isinstance(signal,ICCOutputSignal) or signal.reference_white_nits is not None:raise icc.error('PROOF','软打样要求相对RGB ICC输出配置')
        if not isinstance(simulation_intent,str) or simulation_intent not in icc.INTENTS:raise icc.error('INTENT','须明确软打样模拟意图')
        if not isinstance(working,ColorSignal) or working.transfer!='linear':raise icc.error('WORKING','软打样要求明确线性RGB')
        super().__init__(root,signal,None,cancel=cancel)
        try:
            p=Path(__file__).resolve();self.artifacts[str(p)]=self.guard.entry(p,'native-icc-proof-runtime')
            self.proof,self.input=self.input,None;self.working=working
            if not self.a.cmsIsIntentSupported(self.proof,icc.INTENTS[signal.intent],1) or not self.a.cmsIsIntentSupported(self.proof,1,0):
                raise icc.error('INTENT','软打样配置须支持所选输出意图及相对色度输入表')
            self.input=linear_profile(self.a,self.context,working);self.output=linear_profile(self.a,self.context,working)
            fn=self.a.cmsCreateProofingTransformTHR;fn.restype=C.c_void_p
            fn.argtypes=[C.c_void_p,C.c_void_p,C.c_uint32,C.c_void_p,C.c_uint32,C.c_void_p,C.c_uint32,C.c_uint32,C.c_uint32]
            flags=0x0040|0x0100|0x4000|(0x2000 if signal.black_point_compensation else 0)
            self.transform=fn(self.context,self.input,icc.TYPE_RGB_FLT,self.output,icc.TYPE_RGB_FLT,self.proof,icc.INTENTS[signal.intent],icc.INTENTS[simulation_intent],flags)
            if not self.transform or self.errors:raise icc.error('TRANSFORM','无法建立原生ICC软打样转换')
            self.metadata.pop('source_profile');self.metadata.update(protocol=PROOF_PROTOCOL,proof_profile=vars(signal),working_signal=vars(working),
                rendering_intent=signal.intent,simulation_intent=simulation_intent,flags=flags,SOFTPROOFING_flag=True,gamut_alarm_enabled=False,
                paper_luminance_inferred=False,alpha='bit-exact-independent-straight-coverage',output_remains_linear_working_RGB=True)
            self.verify()
        except BaseException:self.close(verify=False);raise

    def convert(self,source,*,tile_pixels=65536,max_working_bytes=icc.MAX_WORKING_BYTES):
        self.verify();rows,estimated=blocks(source,tile_pixels,max_working_bytes);output=np.empty_like(rows)
        for start in range(0,len(rows),tile_pixels):
            self.poll();v=rows[start:start+tile_pixels];o=output[start:start+len(v)]
            if not np.isfinite(v).all() or np.any(v[:,3]<0) or np.any(v[:,3]>1):raise icc.error('INPUT_RANGE','软打样输入须有限，alpha须在0..1')
            incoming=np.ascontiguousarray(v[:,:3]);converted=np.empty_like(incoming)
            self.a.cmsDoTransform(self.transform,incoming.ctypes.data,converted.ctypes.data,len(v))
            if self.errors or not np.isfinite(converted).all():raise icc.error('TRANSFORM','原生软打样失败或结果非有限')
            o[:,:3]=converted;o[:,3]=v[:,3]
        self.verify()
        return output.reshape(source.shape),dict(self.metadata,converted_pixels=len(rows),estimated_working_bytes=estimated,estimate_is_peak_RSS=False)

    def close(self,*,verify=True):
        if getattr(self,'closed',True):return
        try:
            if verify:self.verify()
        finally:
            if self.transform:self.a.cmsDeleteTransform(self.transform);self.transform=None
            if self.proof:self.a.cmsCloseProfile(self.proof);self.proof=None
            super().close(verify=False)
