"""Read-only bounded random access from verified local Float32 intermediates.

The original registered asset is revalidated on open and clean close. A frame
copy owns its pixels; callers cannot retain an mmap view after this source
closes. This provider neither decodes files nor installs a default renderer.
"""
from fractions import Fraction
import hashlib,json
from pathlib import Path
import numpy as np
from .errors import AppError
from .float_bundle import FILES,canonical,inspect_bundle
from .float_color_signal import ColorSignal
from .float_timeline import TimedSurfaceSource
from .policy import resolve_local_path
from .utils import sha256_file

PROTOCOL='verified-float32-bundle-frame-source-v1'

def error(code,message):return AppError('FLOAT_BUNDLE_SOURCE_'+code,message,exit_code=2)
def digest(path):return 'sha256:'+sha256_file(path)
def stamp(path):
    v=path.stat();return (v.st_size,v.st_mtime_ns,v.st_ctime_ns)

class BundleSurfaceSource(TimedSurfaceSource):
    def __init__(self,root,value,asset,*,demux_origin=None,cancel=None):
        self.closed=True;self.pixels=None;self.clock=None
        if cancel is not None and not callable(cancel):raise error('ARGUMENT','取消回调无效')
        self.poll=cancel if cancel is not None else lambda:None;self.poll()
        self.root=Path(root).resolve();receipt=inspect_bundle(self.root,value);self.manifest_path=Path(receipt['manifest'])
        self.directory=self.manifest_path.parent;manifest=json.loads(self.manifest_path.read_bytes());self.manifest_sha=receipt['manifest_sha256']
        recipe=manifest.get('recipe',{})
        if manifest.get('recipe_sha256')!='sha256:'+hashlib.sha256(canonical(recipe)).hexdigest():raise error('RECIPE','浮点源配方SHA不一致')
        if (asset.get('kind') not in ('video','image') or asset.get('id')!=manifest.get('source_asset_id') or asset.get('sha256')!=manifest.get('source_sha256')
            or recipe.get('source_sha256')!=asset.get('sha256') or recipe.get('asset_id')!=asset.get('id')):raise error('ASSET','浮点包与已登记原始资产不一致')
        if recipe.get('geometry') is not None or manifest.get('geometry_boundary') is not None:raise error('GEOMETRY','宿主只接收未预变换的源表面，防止重复应用作者变换')
        from .float_hdr import parse_signal
        try:signal=parse_signal(recipe['working_signal'])
        except (KeyError,TypeError) as caught:raise error('SIGNAL','浮点包缺少明确工作RGB信号') from caught
        recorded=(manifest.get('source_reader') or {}).get('format_info',{}).get('start_time')
        try:recorded=Fraction(recorded) if recorded not in (None,'N/A','') else None
        except (ValueError,TypeError,ZeroDivisionError) as caught:raise error('CLOCK','浮点包容器起点无效') from caught
        if demux_origin is None:
            if recorded is None:raise error('CLOCK','容器起点未知，调用者须显式提供，不按帧率推测')
            origin=recorded
        else:
            try:origin=Fraction(demux_origin)
            except (ValueError,TypeError,ZeroDivisionError) as caught:raise error('CLOCK','显式容器起点无效') from caught
            if recorded is not None and origin!=recorded:raise error('CLOCK','显式容器起点与原始解复用记录不一致')
        self.original=resolve_local_path(self.root,asset.get('uri',''),field='float-bundle-source.asset')
        if not self.original.is_file() or digest(self.original)!=asset['sha256']:raise error('INPUT_CHANGED','登记原片字节已变化')
        self.original_sha=asset['sha256'];self.bound_paths=[self.original,self.manifest_path,*[self.directory/FILES[k] for k in ('pixels','clock')]]
        self.stamps={str(p):stamp(p) for p in self.bound_paths};self.poll()
        n,h,w=(manifest[k] for k in ('frames','height','width'))
        try:
            self.clock=np.memmap(self.directory/FILES['clock'],mode='r',dtype='<i8',shape=(n,3))
            self.pixels=np.memmap(self.directory/FILES['pixels'],mode='r',dtype='<f4',shape=(n,h,w,4))
            super().__init__(self.clock[:,1].tolist(),self.clock[:,2].tolist(),manifest['native_time_base'],origin,self._fetch,
                signal=signal,source_sha256=self.original_sha,verify=self._verify_inputs,still=asset['kind']=='image',source_frame_start=manifest['selected_source_frame_start'])
            self.closed=False;self.metadata={'protocol':PROTOCOL,'bundle_manifest_sha256':self.manifest_sha,'original_source_sha256':self.original_sha,
                'original_inputs_revalidated':True,'demux_origin':str(origin),'origin_from_caller':recorded is None,'mapped_pixel_bytes':self.pixels.nbytes,
                'frame_copies_owned':True,'pretransformed_sources_accepted':False,'default_renderer_integrated':False,'network':False}
        except BaseException:
            self._release();raise

    def _check(self):
        self.poll()
        if self.closed:raise error('CLOSED','浮点帧源已关闭')
        try:
            if any(stamp(p)!=self.stamps[str(p)] for p in self.bound_paths):raise error('INPUT_CHANGED','帧源生命周期内源或派生产物属性变化')
        except OSError as caught:raise error('INPUT_CHANGED','浮点帧源文件不可读') from caught

    def _fetch(self,index):
        self._check();result=np.array(self.pixels[index],dtype=np.float32,order='C',copy=True);self._check();return result

    def _verify_inputs(self):
        self._check();receipt=inspect_bundle(self.root,self.directory)
        if receipt['manifest_sha256']!=self.manifest_sha or digest(self.original)!=self.original_sha:raise error('INPUT_CHANGED','原片或浮点清单字节变化')
        self._check()

    def _release(self):
        for name in ('pixels','clock'):
            value=getattr(self,name,None)
            if value is not None:value._mmap.close();setattr(self,name,None)
        self.closed=True

    def close(self,*,verify=True):
        if self.closed:return
        try:
            if verify:self.verify()
        finally:self._release()

    def __enter__(self):self._check();return self
    def __exit__(self,kind,value,traceback):self.close(verify=kind is None)
