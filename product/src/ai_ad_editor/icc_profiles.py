"""Explicit project-local RGB ICC v2/v4 sources through pinned native LittleCMS.

Profiles and binaries stay read-locked for the transform lifetime. The CMM
converts directly to the declared linear working RGB profile in Float32;
there is no hidden Pillow/8-bit path or embedded-profile inference.
"""
import ctypes as C
from dataclasses import dataclass
import hashlib,json,math,re,sys
from pathlib import Path
import numpy as np
from .artifact_locks import _Verification
from .errors import AppError
from .float_color_signal import ColorSignal,PRIMARIES
from .float_chromatic import white_of
from .float_hdr import parse_signal
from .native_video_index import owned

PROTOCOL='explicit-native-icc-source-float32-v1'
INTENTS={'perceptual':0,'relative-colorimetric':1,'saturation':2,'absolute-colorimetric':3}
MAX_PROFILE_BYTES=16*1024**2
MAX_WORKING_BYTES=768*1024**2
MAX_TILE_PIXELS=262144
TYPE_RGB_FLT=(1<<22)|(4<<16)|(3<<3)|4

def error(code,message):return AppError('ICC_'+code,message,exit_code=2)
def sha(p):return 'sha256:'+hashlib.sha256(Path(p).read_bytes()).hexdigest()

@dataclass(frozen=True)
class ICCSourceSignal:
    icc_profile:str
    sha256:str
    intent:str
    black_point_compensation:bool=False
    reference_white_nits:float|None=None

    @property
    def transfer(self):return 'icc'

    def __post_init__(self):
        p=self.icc_profile
        if not isinstance(p,str) or not p or '\x00' in p or ':' in p or Path(p).is_absolute() or '..' in Path(p).parts or p.startswith(('\\','/')):
            raise error('PATH','ICC须为工程内相对路径，不能是网络/协议/父目录引用')
        if not isinstance(self.sha256,str) or not re.fullmatch('sha256:[0-9a-f]{64}',self.sha256):raise error('HASH','ICC源声明须锁定SHA-256')
        if not isinstance(self.intent,str) or self.intent not in INTENTS:raise error('INTENT','须明确ICC渲染意图')
        if type(self.black_point_compensation) is not bool:raise error('CONFIG','black_point_compensation须为布尔值')
        n=self.reference_white_nits
        if n is not None and (type(n) not in (float,int) or not .01<=n<=10000 or not math.isfinite(n)):
            raise error('LUMINANCE','ICC参考白亮度须为明确0.01..10000nit')

def parse_source_signal(value):
    if isinstance(value,dict) and 'icc_profile' in value:
        required={'icc_profile','sha256','intent'};allowed=required|{'black_point_compensation','reference_white_nits'}
        if not required<=set(value) or set(value)-allowed:raise error('CONFIG','ICC源信号字段不完整或混入RGB标签')
        return ICCSourceSignal(**value)
    return parse_signal(value)

def source_has_luminance(signal):
    from .float_hdr import has_luminance
    return has_luminance(signal) or isinstance(signal,ICCSourceSignal) and signal.reference_white_nits is not None

def profile_path(root,signal):
    p=owned(Path(root).resolve(),Path(root).resolve()/signal.icc_profile)
    if not p.is_file():raise error('MISSING','声明ICC文件不存在')
    if not 132<=p.stat().st_size<=MAX_PROFILE_BYTES:raise error('BUDGET','ICC文件须为132字节..16MiB')
    return p

def runtime_paths():
    root=Path(__file__).resolve().parent;manifest=root/'native_icc_manifest.json'
    m=json.loads(manifest.read_bytes());name=m.get('binary_filename','')
    if m.get('format')!='agent-native-icc-cmm-v1' or not re.fullmatch('avk_lcms_[0-9a-f]{16}\\.dll',name):raise error('RUNTIME','ICC本地运行清单无效')
    dll=root/name;license_file=root/'LITTLECMS_LICENSE.txt'
    if sha(dll)[7:]!=m['binary_sha256'] or sha(license_file)[7:]!=m['license_sha256']:raise error('RUNTIME','ICC原生二进制或许可字节变化')
    return [Path(__file__).resolve(),manifest,dll,license_file]

def header(data):
    if not 132<=len(data)<=MAX_PROFILE_BYTES or int.from_bytes(data[:4],'big')!=len(data) or data[36:40]!=b'acsp':raise error('HEADER','ICC大小或acsp标识无效')
    if data[8] not in (2,4):raise error('VERSION','当前明确支持ICC v2/v4')
    if data[16:20]!=b'RGB ' or data[20:24] not in (b'XYZ ',b'Lab '):raise error('SPACE','ICC源须为RGB，PCS须为XYZ或Lab')
    if data[12:16] not in (b'scnr',b'mntr',b'prtr',b'spac'):raise error('CLASS','不接受device-link/abstract/named-color等非RGB源配置')
    count=int.from_bytes(data[128:132],'big');end=132+12*count
    if count>4096 or end>len(data):raise error('TAGS','ICC标签目录超出预算/文件')
    tags=[]
    for start in range(132,end,12):
        name=data[start:start+4].decode('ascii','replace');offset=int.from_bytes(data[start+4:start+8],'big');size=int.from_bytes(data[start+8:start+12],'big')
        if size<8 or offset<end or offset+size>len(data):raise error('TAGS','ICC标签指向文件之外或覆盖目录')
        tags.append(name)
    return dict(version_major=data[8],device_class=data[12:16].decode('ascii'),color_space='RGB',PCS=data[20:24].decode('ascii').strip(),tags=tags)

class xyY(C.Structure):_fields_=[('x',C.c_double),('y',C.c_double),('Y',C.c_double)]
class Primaries(C.Structure):_fields_=[('Red',xyY),('Green',xyY),('Blue',xyY)]
CALLBACK=C.CFUNCTYPE(None,C.c_void_p,C.c_uint32,C.c_char_p)

def api(path):
    if sys.platform!='win32' or C.sizeof(C.c_void_p)!=8:raise error('PLATFORM','固定ICC运行包要求原生Windows x64')
    a=C.CDLL(str(path),winmode=0x1100)
    def bind(name,restype,args):
        f=getattr(a,name);f.restype=restype;f.argtypes=args
    p=C.c_void_p;u=C.c_uint32;i=C.c_int;d=C.c_double
    for name,result,args in [('cmsGetEncodedCMMversion',i,[]),('cmsCreateContext',p,[p,p]),('cmsDeleteContext',None,[p]),
        ('cmsSetLogErrorHandlerTHR',None,[p,CALLBACK]),('cmsOpenProfileFromMemTHR',p,[p,p,u]),('cmsCloseProfile',i,[p]),
        ('cmsBuildGamma',p,[p,d]),('cmsFreeToneCurve',None,[p]),
        ('cmsCreateRGBProfileTHR',p,[p,C.POINTER(xyY),C.POINTER(Primaries),C.POINTER(p)]),
        ('cmsCreateTransformTHR',p,[p,p,u,p,u,u,u]),('cmsDoTransform',None,[p,p,p,u]),('cmsDeleteTransform',None,[p]),
        ('cmsIsMatrixShaper',i,[p]),('cmsIsIntentSupported',i,[p,u,u]),
        ('cmsGetProfileInfoASCII',u,[p,u,C.c_char_p,C.c_char_p,C.c_char_p,u]),
        ('cmsSaveProfileToMem',i,[p,p,C.POINTER(u)])]:bind(name,result,args)
    if a.cmsGetEncodedCMMversion()!=2190:raise error('RUNTIME','ICC引擎版本与锁定构建不同')
    return a

class ProfileTransform:
    def __init__(self,root,signal,working=None,*,cancel=None):
        if not isinstance(signal,ICCSourceSignal):raise error('CONFIG','须明确ICC源信号')
        if working is not None and (not isinstance(working,ColorSignal) or working.transfer!='linear'):raise error('WORKING','ICC来源仅接入明确线性RGB工作域')
        self.signal=signal;self.working=working;self.poll=cancel or (lambda:None);self.guard=_Verification()
        self.context=None;self.input=None;self.output=None;self.transform=None;self.closed=False;self.errors=[]
        self.metadata=dict(protocol=PROTOCOL,CPU=True,GPU=False,implicit_8bit_boundary=False,embedded_profile_inferred=False,closed=False)
        try:
            self.poll();path=profile_path(root,signal);paths=runtime_paths()
            self.artifacts={str(p):self.guard.entry(p,'native-icc-profile' if p==path else 'native-icc-runtime') for p in [path,*paths]}
            if runtime_paths()!=paths:raise error('RUNTIME','ICC运行清单在持锁前发生变化')
            if self.artifacts[str(path)]['sha256']!=signal.sha256:raise error('CHANGED','ICC实际字节与作者锁定SHA不同')
            data=path.read_bytes();h=header(data);self.buffer=C.create_string_buffer(data)
            self.a=api(paths[2]);self.context=self.a.cmsCreateContext(None,None)
            if not self.context:raise error('RUNTIME','无法建立ICC独立上下文')
            def record(context,code,message):
                if len(self.errors)<8:self.errors.append(dict(code=int(code),message=(message or b'')[:1024].decode('utf8','replace')))
            self.callback=CALLBACK(record);self.a.cmsSetLogErrorHandlerTHR(self.context,self.callback)
            self.input=self.a.cmsOpenProfileFromMemTHR(self.context,self.buffer,len(data))
            if not self.input:raise error('PROFILE','LittleCMS拒绝ICC配置文件')
            description=C.create_string_buffer(1024);self.a.cmsGetProfileInfoASCII(self.input,0,b'en',b'US',description,len(description))
            self.metadata.update(source_profile=vars(signal),header=h,description=description.value.decode('utf8','replace'),
                matrix_shaper=bool(self.a.cmsIsMatrixShaper(self.input)),CMM_encoded_version=2190,artifacts=self.artifacts)
            if working is not None:
                if not self.a.cmsIsIntentSupported(self.input,INTENTS[signal.intent],0):raise error('INTENT','该ICC源未声明支持所选输入意图')
                primaries=Primaries(*(xyY(x,y,1) for x,y in PRIMARIES[working.primaries]));wx,wy=white_of(working);white=xyY(wx,wy,1)
                curve=self.a.cmsBuildGamma(self.context,1.)
                if not curve:raise error('RUNTIME','无法建立线性工作曲线')
                try:self.output=self.a.cmsCreateRGBProfileTHR(self.context,C.byref(white),C.byref(primaries),(C.c_void_p*3)(curve,curve,curve))
                finally:self.a.cmsFreeToneCurve(curve)
                if not self.output:raise error('WORKING','LittleCMS拒绝目标线性RGB工作配置')
                flags=0x0040|0x0100|(0x2000 if signal.black_point_compensation else 0)
                self.transform=self.a.cmsCreateTransformTHR(self.context,self.input,TYPE_RGB_FLT,self.output,TYPE_RGB_FLT,INTENTS[signal.intent],flags)
                if not self.transform or self.errors:raise error('TRANSFORM','LittleCMS无法建立所选转换')
                dst_nits=getattr(working,'reference_white_nits',None)
                self.unit_scale=signal.reference_white_nits/dst_nits if signal.reference_white_nits is not None and dst_nits is not None else 1.
                self.metadata.update(working_signal=vars(working),linear_unit_scale=self.unit_scale,rendering_intent=signal.intent,
                    black_point_compensation=signal.black_point_compensation,flags=flags,negative_output_clipped=False,alpha='bit-exact-independent-straight-coverage')
            self.verify()
        except BaseException:self.close(verify=False);raise

    def verify(self):
        self.poll()
        if self.closed:raise error('CLOSED','ICC转换已关闭')
        for path,row in self.artifacts.items():
            self.poll()
            if sha(path)!=row['sha256']:raise error('CHANGED','ICC配置或实现字节在任务中变化')

    def convert(self,source,*,tile_pixels=65536,max_working_bytes=MAX_WORKING_BYTES):
        self.verify()
        if not self.transform:raise error('CONFIG','只读检查上下文不能转换像素')
        if not isinstance(source,np.ndarray) or source.dtype!=np.dtype('float32') or source.ndim!=3 or source.shape[-1]!=4 or not source.flags.c_contiguous:raise error('SURFACE','ICC要求连续HxWx4 Float32表面')
        h,w=source.shape[:2];pixels=h*w
        if not 1<=min(h,w) or max(h,w)>16384 or pixels>16777216:raise error('BUDGET','ICC表面超出尺寸预算')
        if type(tile_pixels) is not int or not 1<=tile_pixels<=MAX_TILE_PIXELS or type(max_working_bytes) is not int or not 1<=max_working_bytes<=MAX_WORKING_BYTES:raise error('BUDGET','ICC分块/工作区预算无效')
        estimated=source.nbytes*2+min(tile_pixels,pixels)*64+4096
        if estimated>max_working_bytes:raise error('BUDGET','ICC工作区估算超出预算')
        rows=source.reshape(-1,4);output=np.empty_like(rows)
        for start in range(0,pixels,tile_pixels):
            self.poll();v=rows[start:start+tile_pixels];o=output[start:start+len(v)]
            if not np.isfinite(v).all() or np.any(v<0) or np.any(v>1):raise error('INPUT_RANGE','ICC编码源RGB及alpha须在0..1；不会隐式截断')
            incoming=np.ascontiguousarray(v[:,:3]);converted=np.empty_like(incoming)
            self.a.cmsDoTransform(self.transform,incoming.ctypes.data,converted.ctypes.data,len(v))
            if self.errors:raise error('TRANSFORM','LittleCMS执行转换时报告错误')
            o[:,:3]=converted if self.unit_scale==1 else converted.astype(np.float64)*self.unit_scale
            o[:,3]=v[:,3]
            if not np.isfinite(o).all():raise error('VALUES','ICC结果超出有限Float32范围')
        self.verify();receipt=dict(self.metadata,estimated_working_bytes=estimated,estimate_is_peak_RSS=False,converted_pixels=pixels)
        return output.reshape(h,w,4),receipt

    def close(self,*,verify=True):
        if self.closed:return
        try:
            if verify:self.verify()
        finally:
            if self.transform:self.a.cmsDeleteTransform(self.transform);self.transform=None
            if self.output:self.a.cmsCloseProfile(self.output);self.output=None
            if self.input:self.a.cmsCloseProfile(self.input);self.input=None
            if self.context:self.a.cmsDeleteContext(self.context);self.context=None
            self.guard.close();self.closed=True;self.metadata['closed']=True;self.metadata['native_handles_closed']=True
    def __enter__(self):return self
    def __exit__(self,*args):self.close(verify=args[0] is None)

def inspect_profile(root,relative):
    if not isinstance(relative,str):raise error('PATH','须明确工程内ICC路径')
    provisional=ICCSourceSignal(relative,'sha256:'+'0'*64,'relative-colorimetric')
    path=profile_path(root,provisional)
    signal=ICCSourceSignal(relative,sha(path),'relative-colorimetric')
    with ProfileTransform(root,signal) as transform:result=dict(transform.metadata)
    result.update(native_handles_closed=True,read_only=True)
    return result
