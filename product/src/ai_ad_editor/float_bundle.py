"""Agent-readable native-clock Float32 frame bundles from registered media.

The bundle is an intermediate, not an encoded movie or the timeline renderer.
Original frame PTS/durations and source indexes remain exact signed int64.
"""
from __future__ import annotations
from datetime import datetime,timezone
from fractions import Fraction
from itertools import islice
import hashlib,json,os,shutil,tempfile
from pathlib import Path
import numpy as np
from .artifact_locks import artifact_entry,verification_scope
from .errors import AppError
from .float_color_signal import ColorSignal,convert_rgba
from .icc_profiles import ICCSourceSignal,ProfileTransform,parse_source_signal
from .float_geometry import resample_rgba
from .float_video_source import NativeRGBSource,cancelled
from .float_yuv import YUVSpec
from .float_yuv_source import NativeYUVSource
from .native_video_index import IndexContext,owned
from .policy import require_local_reference,resolve_local_path
from .reverse_video_clock import probe_frames
from .utils import sha256_file

PROTOCOL='agent-native-clock-float32-bundle-v1'
FILES={'pixels':'frames.rgba-f32le','clock':'clock.i64le'}
MAX_OUTPUT_BYTES=2*1024**3
MAX_METADATA_BYTES=128*1024
HEADROOM_BYTES=64*1024**2

def error(code,message,**details):return AppError('FLOAT_BUNDLE_'+code,message,exit_code=2,diagnostics=details or None)
def canonical(value):return json.dumps(value,ensure_ascii=False,sort_keys=True,separators=(',',':'),allow_nan=False).encode('utf8')
def digest(path):return 'sha256:'+sha256_file(Path(path))

def _owned(root,value):
    require_local_reference(str(value),field='surface.output')
    path=Path(value).expanduser();path=path if path.is_absolute() else root/path
    try:return owned(root,path)
    except AppError as caught:raise error('PATH','浮点产物路径必须位于工程内且不能包含目录联接或符号链接') from caught

def _geometry(value,width,height):
    if value is None:return None,width,height
    if not isinstance(value,dict) or set(value)!={'width','height','inverse'}:raise error('GEOMETRY','几何说明须包含width/height/inverse')
    w,h=value['width'],value['height']
    if any(type(v) is not int or not 1<=v<=16384 for v in (w,h)) or w*h>16777216:
        raise error('GEOMETRY','输出几何尺寸超过浮点表面预算')
    try:
        raw=np.asarray(value['inverse'])
        if raw.dtype.kind not in 'fiu' or raw.shape!=(2,3):raise ValueError('invalid matrix')
        m=raw.astype(np.float64)
        if not np.isfinite(m).all() or np.max(np.abs(m))>1e9 or m[0,0]*m[1,1]-m[0,1]*m[1,0]==0:raise ValueError('invalid matrix')
    except (ValueError,TypeError,OverflowError) as caught:raise error('GEOMETRY','逆矩阵须为有限、不退化的2×3数值') from caught
    return {'width':w,'height':h,'inverse':m.tolist()},w,h

def prepare(root,project,asset_id,output,*,source_signal,target_signal,pixel_family='rgb',yuv_spec=None,
            scan=None,alpha_association='straight',start_frame=0,stop_frame=None,geometry=None,max_output_bytes=MAX_OUTPUT_BYTES,
            hdr_range_policy='reject',hdr_input_range_policy='reject'):
    root=Path(root).resolve()
    if not isinstance(source_signal,(ColorSignal,ICCSourceSignal)) or not isinstance(target_signal,ColorSignal):raise error('SIGNAL','输入和工作RGB信号须明确')
    from .float_hdr import HDR_TRANSFERS,has_luminance
    hdr=getattr(source_signal,'transfer',None) in HDR_TRANSFERS or target_signal.transfer in HDR_TRANSFERS
    if hdr and not (has_luminance(source_signal) and has_luminance(target_signal)):raise error('SIGNAL','HDR中间包两端须明确reference_white_nits')
    if any(type(v) is not str or v not in ('reject','clip') for v in (hdr_range_policy,hdr_input_range_policy)):
        raise error('SIGNAL','HDR输入/输出域策略须为reject或明确clip')
    if not hdr and (hdr_range_policy!='reject' or hdr_input_range_policy!='reject'):raise error('SIGNAL','HDR域策略不应用于非HDR来源/目标')
    if isinstance(source_signal,ICCSourceSignal):
        with ProfileTransform(root,source_signal,target_signal):pass
    if pixel_family not in ('rgb','yuv'):raise error('FORMAT','原生像素族须明确为rgb或yuv')
    if alpha_association not in ('straight','premultiplied'):raise error('ALPHA','源透明度表示须明确')
    if pixel_family=='yuv' and (not isinstance(yuv_spec,YUVSpec) or scan!='progressive'):
        raise error('COLOR','YCbCr必须提供明确矩阵、量程、位置及逐行声明')
    if pixel_family=='rgb' and (yuv_spec is not None or scan is not None):raise error('COLOR','RGB源不能附带YCbCr采样参数')
    if type(start_frame) is not int or start_frame<0 or (stop_frame is not None and (type(stop_frame) is not int or stop_frame<=start_frame)):
        raise error('RANGE','帧选区须为非空、从零起算的半开区间')
    if type(max_output_bytes) is not int or not 1<=max_output_bytes<=MAX_OUTPUT_BYTES:raise error('BUDGET','产物预算须在1字节至2GiB范围')
    asset=next((a for a in project.get('assets',[]) if a.get('id')==asset_id),None)
    if asset is None or asset.get('kind') not in ('video','image'):raise error('ASSET','须选择已登记的本地视频或图片资产')
    source=resolve_local_path(root,asset.get('uri',''),field='surface.asset')
    if not source.is_file() or digest(source)!=asset.get('sha256'):raise error('INPUT_CHANGED','源字节与工程登记SHA不一致')
    destination=_owned(root,output)
    if destination==root or destination.exists():raise error('OUTPUT_EXISTS','浮点输出目录必须是工程内尚不存在的新目录')
    probe=asset.get('probe',{});width,height=int(probe.get('width',0)),int(probe.get('height',0))
    geometry,width,height=_geometry(geometry,width,height)
    recipe={'protocol':PROTOCOL,'asset_id':asset_id,'source':str(source),'source_sha256':asset['sha256'],
        'source_signal':vars(source_signal),
        'working_signal':vars(target_signal),
        'pixel_family':pixel_family,'YCbCr':None if yuv_spec is None else {'matrix':yuv_spec.matrix,'range':yuv_spec.range,'chroma_location':yuv_spec.chroma_location},
        'scan':scan,'alpha_association':alpha_association,'start_frame':start_frame,'stop_frame_exclusive':stop_frame,
        'geometry':geometry,'max_output_bytes':max_output_bytes}
    if hdr:recipe.update(hdr_range_policy=hdr_range_policy,hdr_input_range_policy=hdr_input_range_policy)
    return {'status':'planned','recipe':recipe,'recipe_sha256':'sha256:'+hashlib.sha256(canonical(recipe)).hexdigest(),
        'output':str(destination),'native_decode_started':False,'frames_and_dimensions_authoritative_only_after_native_index':True,
        'encoded_movie':False,'timeline_renderer_integrated':False,'HDR_accepted':hdr}

def _implementation_artifacts():
    directory=Path(__file__).resolve().parent
    paths={name:directory/(name+'.py') for name in ('float_bundle','float_color_signal','float_hdr','float_hlg_black','float_chromatic','float_geometry','icc_profiles')}
    paths['numpy_init']=Path(np.__file__).resolve()
    # These files are the numerical boundary's entry module and native code.
    # This is not advertised as an exhaustive NumPy package inventory.
    for index,p in enumerate(sorted((Path(np.__file__).parent/'_core').glob('*multiarray_umath*.pyd'))):paths['numpy_native_'+str(index)]=p.resolve()
    for index,p in enumerate(sorted((Path(np.__file__).parent.parent/'numpy.libs').glob('*.dll'))):paths['numpy_dll_'+str(index)]=p.resolve()
    with verification_scope():return {name:artifact_entry(p,'float-bundle-implementation') for name,p in paths.items()}

def _verify(artifacts,marker):
    for name,row in artifacts.items():
        cancelled(marker)
        if digest(row['path'])!=row['sha256']:raise error('INPUT_CHANGED','浮点实现或数值依赖字节变化',artifact=name)

def export_bundle(root,plan,*,cancel_file=None,progress=None):
    root=Path(root).resolve();recipe=plan['recipe'];marker=Path(cancel_file) if cancel_file is not None else None;cancelled(marker)
    if plan.get('recipe_sha256')!='sha256:'+hashlib.sha256(canonical(recipe)).hexdigest():raise error('RECIPE','浮点配方摘要不一致')
    destination=_owned(root,plan['output'])
    if destination.exists():raise error('OUTPUT_EXISTS','浮点输出已存在，禁止覆盖')
    source=resolve_local_path(root,recipe['source'],field='surface.source')
    if digest(source)!=recipe['source_sha256']:raise error('INPUT_CHANGED','执行前源字节变化')
    context=IndexContext(root,persist=False,cancel_file=marker)
    pts,durations,stream,format_info,index=context.acquire(source,recipe['source_sha256'],probe_frames)
    stop=recipe['stop_frame_exclusive'] if recipe['stop_frame_exclusive'] is not None else len(pts);start=recipe['start_frame']
    if not 0<=start<stop<=len(pts):raise error('RANGE','选择帧区间超出原生索引',source_frames=len(pts))
    geometry,width,height=_geometry(recipe['geometry'],int(stream['width']),int(stream['height']))
    if not 1<=width<=16384 or not 1<=height<=16384 or width*height>16777216:raise error('BUDGET','原生表面尺寸超出预算')
    count=stop-start;pixel_bytes=count*width*height*16;clock_bytes=count*24;required=pixel_bytes+clock_bytes+MAX_METADATA_BYTES
    if required>recipe['max_output_bytes']:raise error('BUDGET','浮点帧选区超过产物字节预算',required_bytes=required,budget_bytes=recipe['max_output_bytes'])
    if shutil.disk_usage(root).free<required+HEADROOM_BYTES:raise error('DISK','浮点产物加64MiB余量超过可用磁盘')
    from .float_hdr import parse_signal
    implementations=_implementation_artifacts();source_signal=parse_source_signal(recipe['source_signal']);target_signal=parse_signal(recipe['working_signal'])
    kwargs={'root':root,'source':source,'source_sha256':recipe['source_sha256'],'alpha_association':recipe['alpha_association'],
        'stop_frame':stop,'cancel_file':marker,'index_context':context}
    reader=(NativeRGBSource(**kwargs) if recipe['pixel_family']=='rgb' else
        NativeYUVSource(**kwargs,spec=YUVSpec(**recipe['YCbCr']),scan=recipe['scan']))
    # Parent creation begins only after native index, budgets and input checks.
    destination.parent.mkdir(parents=True,exist_ok=True);_owned(root,destination.parent)
    temporary=Path(tempfile.mkdtemp(prefix='.float-bundle-',dir=destination.parent));_owned(root,temporary)
    committed=False;colour_metadata=None;geometry_metadata=None;icc_transform=None
    try:
        if isinstance(source_signal,ICCSourceSignal):icc_transform=ProfileTransform(root,source_signal,target_signal,cancel=lambda:cancelled(marker))
        with (temporary/FILES['pixels']).open('xb') as pixels,(temporary/FILES['clock']).open('xb') as clock:
            with reader:
                for frame in reader:
                    if frame.index<start:continue
                    cancelled(marker)
                    value,colour_metadata=(icc_transform.convert(frame.rgba) if icc_transform else
                        convert_rgba(frame.rgba,source_signal,target_signal,cancel=lambda:cancelled(marker),
                            hdr_range_policy=recipe.get('hdr_range_policy','reject'),hdr_input_range_policy=recipe.get('hdr_input_range_policy','reject')))
                    if geometry is not None:
                        value,geometry_metadata=resample_rgba(value,(width,height),geometry['inverse'],cancel=lambda:cancelled(marker))
                    pixels.write(value.astype('<f4',copy=False).tobytes());clock.write(np.array([frame.index,frame.pts,frame.duration],dtype='<i8').tobytes())
                    if progress is not None:progress(frame.index-start+1,count)
            pixels.flush();os.fsync(pixels.fileno());clock.flush();os.fsync(clock.fileno())
        if (temporary/FILES['pixels']).stat().st_size!=pixel_bytes or (temporary/FILES['clock']).stat().st_size!=clock_bytes:
            raise error('TRUNCATED','浮点产物未覆盖声明的全部选择帧')
        _verify(implementations,marker);reader.verify()
        if icc_transform:
            icc_transform.close();colour_metadata.update(closed=True,native_handles_closed=True)
        manifest={'protocol':PROTOCOL,'created_at_utc':datetime.now(timezone.utc).isoformat(),'recipe':recipe,
            'recipe_sha256':plan['recipe_sha256'],'source_asset_id':recipe['asset_id'],'source_sha256':recipe['source_sha256'],
            'frames':count,'width':width,'height':height,'pixel_format':'interleaved-straight-RGBA-f32le',
            'native_time_base':str(Fraction(stream['time_base'])),'clock_columns':['source_frame_index','original_pts','original_duration'],
            'selected_source_frame_start':start,'selected_source_frame_end_exclusive':stop,'source_frame_count':len(pts),
            'all_source_frames_exported':start==0 and stop==len(pts),'all_selected_frames_exported':True,
            'files':{key:{'name':name,'bytes':(temporary/name).stat().st_size,'sha256':digest(temporary/name)} for key,name in FILES.items()},
            'source_reader':reader.metadata,'source_reader_process':{'exit_code':reader.pipe.process.poll(),
                'owned_threads_terminated':all(not thread.is_alive() for thread in reader.pipe.threads)},
            'colour_boundary':colour_metadata,'geometry_boundary':geometry_metadata,
            'implementation_artifacts':implementations,'numpy_version':np.__version__,'numpy_whole_package_inventory':False,
            'working_white':('native ICC rendering intent to explicit linear working RGB; physical illuminant not inferred' if icc_transform else
                'explicit RGB reference white; Bradford in linear XYZ; physical illuminant not inferred'
                if colour_metadata.get('chromatic_transform',{}).get('extended')
                else 'relative D65;physical white matching must be supplied by caller'),
            'alpha':'independent-straight;not-a-transfer-component','encoded_movie':False,'audio_exported':False,
            'timeline_renderer_integrated':False,'HDR_accepted':plan['HDR_accepted'],'native_windows':True,'network':False,
            'budget':{'required_bytes_estimate':required,'limit_bytes':recipe['max_output_bytes'],'peak_RSS_accepted':False}}
        payload=json.dumps(manifest,ensure_ascii=False,indent=2,allow_nan=False).encode('utf8')+b'\n'
        if len(payload)>MAX_METADATA_BYTES:raise error('BUDGET','浮点清单超过128KiB预算')
        (temporary/'bundle.json').write_bytes(payload);cancelled(marker);_owned(root,destination)
        if destination.exists():raise error('OUTPUT_EXISTS','提交时浮点输出目录已存在')
        temporary.rename(destination);committed=True
        return {'status':'succeeded','output':str(destination),'manifest':str(destination/'bundle.json'),
            'manifest_sha256':digest(destination/'bundle.json'),'frames':count,'width':width,'height':height,
            'native_time_base':manifest['native_time_base'],'recipe_sha256':plan['recipe_sha256'],
            'all_source_frames_exported':manifest['all_source_frames_exported'],'encoded_movie':False,
            'timeline_renderer_integrated':False,'HDR_accepted':plan['HDR_accepted']}
    except OSError as caught:
        raise error('IO','浮点包本地读写失败；保留源文件并清理未提交产物',cause=str(caught)) from caught
    finally:
        if icc_transform:icc_transform.close(verify=False)
        reader.close()
        if not committed and temporary.exists():
            _owned(root,temporary);shutil.rmtree(temporary)

def inspect_bundle(root,value):
    root=Path(root).resolve();directory=_owned(root,value);metadata=_owned(root,directory/'bundle.json')
    if not metadata.is_file() or metadata.stat().st_size>MAX_METADATA_BYTES or {p.name for p in islice(directory.iterdir(),4)}!={'bundle.json',*FILES.values()}:
        raise error('INVALID','浮点包必须只包含有界清单、像素和原生帧时钟')
    try:manifest=json.loads(metadata.read_bytes())
    except (ValueError,UnicodeDecodeError) as caught:raise error('INVALID','浮点清单JSON无效') from caught
    if manifest.get('protocol')!=PROTOCOL or manifest.get('pixel_format')!='interleaved-straight-RGBA-f32le':raise error('INVALID','浮点协议或像素布局不受支持')
    n,w,h=(manifest.get(name) for name in ('frames','width','height'))
    if any(type(v) is not int or v<1 for v in (n,w,h)) or n>1000000 or max(w,h)>16384 or w*h>16777216:
        raise error('INVALID','浮点包帧数或表面尺寸超过边界')
    sizes={'pixels':n*w*h*16,'clock':n*24}
    if sum(sizes.values())>MAX_OUTPUT_BYTES:raise error('INVALID','浮点包超过2GiB字节边界')
    for key,name in FILES.items():
        path=_owned(root,directory/name);row=manifest.get('files',{}).get(key,{})
        if row.get('name')!=name or row.get('bytes')!=sizes[key] or not path.is_file() or path.stat().st_size!=sizes[key] or digest(path)!=row.get('sha256'):
            raise error('CORRUPT','浮点像素或原生帧时钟字节变化',file=name)
    try:
        time_base=Fraction(manifest['native_time_base']);start=manifest['selected_source_frame_start'];stop=manifest['selected_source_frame_end_exclusive']
        if time_base<=0 or type(start) is not int or type(stop) is not int or start<0 or stop-start!=n:raise ValueError('invalid selected range')
        clock=np.fromfile(directory/FILES['clock'],dtype='<i8').reshape(n,3)
        if (not np.array_equal(clock[:,0],np.arange(start,stop)) or np.any(clock[:,2]<0) or np.any(clock[1:,1]<=clock[:-1,1])):raise ValueError('invalid original clock')
    except (ValueError,KeyError,TypeError,ZeroDivisionError) as caught:raise error('INVALID','浮点帧时钟元数据无效') from caught
    return {'status':'verified','manifest':str(metadata),'manifest_sha256':digest(metadata),'frames':n,'width':w,'height':h,
        'native_time_base':str(time_base),'first_original_pts':int(clock[0,1]),'last_original_pts':int(clock[-1,1]),
        'pixel_bytes':sizes['pixels'],'clock_bytes':sizes['clock'],'source_asset_id':manifest.get('source_asset_id'),
        'source_sha256':manifest.get('source_sha256'),'derived_bytes_verified':True,'original_inputs_revalidated':False,
        'encoded_movie':False,'timeline_renderer_integrated':False,'HDR_accepted':False}
