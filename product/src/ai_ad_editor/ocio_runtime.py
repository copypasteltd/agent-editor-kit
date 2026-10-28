"""Pinned native OpenColorIO ACES display/view transforms, without GUI or LUT downloads."""
import hashlib,importlib.util,json,os,struct,sys,threading
from pathlib import Path
import numpy as np
from .errors import AppError

PROTOCOL='native-ocio-aces-display-float32-v1'
MANIFEST_SHA256='35de74936b689a955fbb953af369c680dcb91e69afb8897d3d59f6ed737d479b'
CONFIGS={
    'aces-1.3':'ocio://studio-config-v2.2.0_aces-v1.3_ocio-v2.4',
    'aces-2.0':'ocio://studio-config-v4.0.0_aces-v2.0_ocio-v2.5',
    'aces-2.1':'ocio://studio-config-v5.0.0_aces-v2.1_ocio-v2.6'}
_MODULE=None
_LOCK=threading.Lock()

def error(code,message):return AppError('OCIO_'+code,message,exit_code=2)
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def runtime_paths():
    root=Path(__file__).resolve().parent;manifest=root/'native_ocio_manifest.json'
    if not manifest.is_file() or sha(manifest)!=MANIFEST_SHA256:raise error('RUNTIME','固定OCIO清单摘要不匹配')
    try:m=json.loads(manifest.read_bytes())
    except (OSError,ValueError) as e:raise error('RUNTIME','缺少有效的固定原生OCIO清单') from e
    if m.get('format')!='agent-native-ocio-runtime-v1' or m.get('version')!='2.6.0' or m.get('target')!='cp313-win_amd64':raise error('RUNTIME','OCIO版本/原生目标不匹配')
    expected={'native_ocio/PyOpenColorIO.pyd','native_ocio/OpenColorIO_2_6.dll','native_ocio/LICENSE.txt','native_ocio/THIRD-PARTY.md'}
    if {r.get('path') for r in m.get('files',[])}!=expected or len(m['files'])!=4:raise error('RUNTIME','OCIO固定文件集合无效')
    paths=[Path(__file__).resolve(),manifest]
    for row in m['files']:
        p=root/row['path']
        if not p.is_file() or p.stat().st_size!=row['bytes'] or sha(p)!=row['sha256']:raise error('RUNTIME','OCIO二进制/许可实际字节与固定清单不同')
        paths.append(p)
    return paths

def native():
    global _MODULE
    if sys.platform!='win32' or sys.version_info[:2]!=(3,13) or struct.calcsize('P')!=8:raise error('PLATFORM','固定OCIO运行库要求原生Windows CPython3.13 x64')
    with _LOCK:
        if _MODULE is None:
            runtime_paths();folder=Path(__file__).resolve().parent/'native_ocio'
            name='ai_ad_editor.PyOpenColorIO'
            spec=importlib.util.spec_from_file_location(name,folder/'PyOpenColorIO.pyd')
            try:
                with os.add_dll_directory(str(folder)):
                    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
                if module.__version__!='2.6.0':raise error('RUNTIME','实际OCIO原生模块版本不匹配')
                _MODULE=module
            except (OSError,ImportError) as e:raise error('RUNTIME','不能加载固定原生OCIO；不使用全局模块或下载回退') from e
        return _MODULE

def config(key):
    if not isinstance(key,str) or key not in CONFIGS:raise error('CONFIG','必须明确选择固定aces-1.3/aces-2.0/aces-2.1；禁止latest/环境配置')
    try:
        c=native().Config.CreateFromBuiltinConfig(CONFIGS[key]);c.validate();return c
    except AppError:raise
    except Exception as exc:raise error('CONFIG','固定ACES配置不能建立或验证') from exc

def catalog(key=None):
    result=[]
    for name in ([key] if key is not None else CONFIGS):
        c=config(name)
        result.append(dict(id=name,uri=CONFIGS[name],serialized_sha256=hashlib.sha256(c.serialize().encode()).hexdigest(),
            colorspaces=[dict(name=s.getName(),encoding=s.getEncoding(),description=s.getDescription()) for s in c.getColorSpaces()],
            displays=[dict(name=d,views=[dict(name=v,colorspace=c.getDisplayViewColorSpaceName(d,v),view_transform=c.getDisplayViewTransformName(d,v)) for v in c.getViews(d)]) for d in c.getDisplays()]))
    return dict(protocol=PROTOCOL,version='2.6.0',configs=result,CPU=True,GPU=False,external_LUT_files=False,environment_configuration=False)

def configuration(value):
    fields={'config','display','view','exposure_stops','input_interpretation'}
    if not isinstance(value,dict) or set(value)!=fields or value.get('input_interpretation')!='scene-linear-ACEScg':raise error('CONFIG','须完整声明config/display/view/exposure_stops及scene-linear-ACEScg输入解释')
    if not isinstance(value['config'],str) or value['config'] not in CONFIGS or not all(isinstance(value[k],str) and 1<=len(value[k])<=256 for k in ('display','view')):raise error('CONFIG','OCIO配置/显示/视图名称无效')
    e=value['exposure_stops']
    if isinstance(e,bool) or not isinstance(e,(int,float)) or not np.isfinite(e) or not -16<=e<=16:raise error('CONFIG','ACES场景曝光须为有限-16..16 stops')
    return {**value,'exposure_stops':float(e)}

class DisplayTransform:
    def __init__(self,value):
        self.value=configuration(value);self.closed=False;c=config(self.value['config']);o=native()
        if self.value['display'] not in list(c.getDisplays()) or self.value['view'] not in list(c.getViews(self.value['display'])):raise error('VIEW','固定配置中不存在明确选择的display/view')
        try:
            transform=o.DisplayViewTransform(src='ACEScg',display=self.value['display'],view=self.value['view'])
            self.processor=c.getProcessor(transform);self.cpu=self.processor.getDefaultCPUProcessor()
        except Exception as e:raise error('PROCESSOR','原生OCIO不能建立所选ACES显示变换') from e
        self.metadata=dict(protocol=PROTOCOL,version='2.6.0',selection=self.value,config_uri=CONFIGS[self.value['config']],
            config_sha256=hashlib.sha256(c.serialize().encode()).hexdigest(),processor_cache_id=self.processor.getCacheID(),
            CPU=True,GPU=False,source_space='ACEScg',input_is_scene_relative=True,automatic_camera_IDT=False,
            frames=0,pixels=0,alpha='bit-exact',integer_intermediate=False,external_LUT_files=False,environment_configuration=False)

    def apply(self,source,*,cancel=None,tile_pixels=65536,max_working_bytes=768*1024**2):
        if self.closed:raise error('CLOSED','ACES变换已经关闭')
        if not isinstance(source,np.ndarray) or source.dtype!=np.float32 or source.ndim!=3 or source.shape[-1]!=4 or not source.flags.c_contiguous:raise error('SURFACE','ACES输入须为连续HxWx4 Float32')
        h,w=source.shape[:2];count=h*w
        if not 1<=min(h,w) or max(h,w)>16384 or count>16777216 or type(tile_pixels) is not int or not 1<=tile_pixels<=262144:raise error('BUDGET','ACES表面/分块超过预算')
        estimate=source.nbytes*2+min(count,tile_pixels)*80+4096
        if type(max_working_bytes) is not int or not 1<=max_working_bytes<=768*1024**2 or estimate>max_working_bytes:raise error('BUDGET','ACES工作区估算超限；非总RSS')
        poll=cancel if cancel is not None else lambda:None;poll();output=np.empty_like(source);src=source.reshape(-1,4);dst=output.reshape(-1,4)
        for start in range(0,count,tile_pixels):
            poll();a=src[start:start+tile_pixels]
            if not np.isfinite(a).all() or np.any((a[:,3]<0)|(a[:,3]>1)):raise error('SURFACE','ACES输入RGB须有限，alpha须0..1')
            block=a.copy();block[:,:3]=(block[:,:3].astype(np.float64)*2**self.value['exposure_stops']).astype(np.float32)
            if not np.isfinite(block).all():raise error('VALUES','ACES曝光超过Float32范围')
            try:self.cpu.applyRGBA(block)
            except Exception as e:raise error('VALUES','原生ACES处理失败；不回退简单曲线') from e
            block[:,3]=a[:,3]
            if not np.isfinite(block).all():raise error('VALUES','原生ACES输出非有限值')
            dst[start:start+len(a)]=block
        poll();self.metadata['frames']+=1;self.metadata['pixels']+=count
        return output,dict(self.metadata,estimated_working_bytes=estimate,estimate_is_peak_RSS=False)

    def close(self):self.cpu=None;self.processor=None;self.closed=True
    def __enter__(self):return self
    def __exit__(self,*args):self.close()
