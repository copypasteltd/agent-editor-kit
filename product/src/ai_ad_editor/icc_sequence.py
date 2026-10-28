"""Editable timeline -> individually profile-embedded RGBA16 PNGs and raw PCM.

Device RGB is delivered as device RGB, never incorrectly tagged as YUV BT709.
"""
import json,math,shutil,tempfile
from fractions import Fraction
from pathlib import Path
from . import icc_profiles as icc,icc_output,png_icc,float_audio_graph
from .artifact_locks import artifact_entry,verification_scope
from .float_bundle import _owned,canonical,digest
from .float_standard_render import FloatRenderContext,configuration
from .float_stream import _EncoderPipe
from .float_hdr import map_display,LuminanceSignal
from .media import ffmpeg_path
from .native_audio_clock import cancel
from .policy import resolve_local_path
from .render import output_settings
from .sequence_canvas import sequence_canvas

PROTOCOL='agent-icc-png16-timeline-sequence-v1'
MAX_BYTES=8*1024**3

def inspect(root,value,*,cancel_file=None):
    """Verify declared derived bytes, not original-source provenance or rights."""
    import hashlib
    import numpy as np
    directory=_owned(Path(root).resolve(),value);marker=Path(cancel_file) if cancel_file else None;poll=lambda:cancel(marker)
    manifest_path=_owned(Path(root).resolve(),directory/'sequence.json')
    if not manifest_path.is_file() or manifest_path.stat().st_size>16*1024**2:raise icc.error('MANIFEST','ICC序列清单缺少或超预算')
    with verification_scope():
        artifact_entry(manifest_path,'icc-sequence-inspect-manifest');m=json.loads(manifest_path.read_bytes());r=m.get('recipe',{})
        if m.get('protocol')!=PROTOCOL or m.get('recipe_sha256')!='sha256:'+hashlib.sha256(canonical(r)).hexdigest():raise icc.error('MANIFEST','ICC序列协议或配方摘要不一致')
        start,stop=r.get('start_frame'),r.get('stop_frame_exclusive');w,h=r.get('width'),r.get('height')
        if any(type(x) is not int for x in (start,stop,w,h)) or not 0<=start<stop<=1000000000 or stop-start>1000000 or min(w,h)<1 or max(w,h)>16384 or w*h>16777216:
            raise icc.error('BUDGET','ICC序列核验帧范围/尺寸超预算')
        expected_names=[f'frame-{i:09d}.png' for i in range(start,stop)]+['output.icc','audio.f32le']
        files=m.get('files')
        if not isinstance(files,list) or len(files)!=len(expected_names) or [v.get('name') for v in files]!=expected_names or m.get('frames')!=stop-start:
            raise icc.error('MANIFEST','ICC序列文件目录不完整或重复')
        if {p.name for p in directory.iterdir()}!={*expected_names,'sequence.json'}:raise icc.error('MANIFEST','ICC序列存在未登记文件')
        total=0
        for row in files:
            poll();path=_owned(Path(root).resolve(),directory/row['name']);locked=artifact_entry(path,'icc-sequence-inspect-file')
            n=row.get('bytes')
            if type(n) is not int or not 0<=n<=MAX_BYTES or n!=path.stat().st_size or locked['sha256']!=row.get('sha256'):raise icc.error('CORRUPT','ICC序列实际字节/摘要不符')
            total+=n
        if total>MAX_BYTES:raise icc.error('BUDGET','ICC序列核验总字节超预算')
        if files[-2]['bytes']>icc.MAX_PROFILE_BYTES:raise icc.error('BUDGET','交付ICC超16MiB预算')
        profile=(directory/'output.icc').read_bytes();icc.header(profile)
        if 'sha256:'+hashlib.sha256(profile).hexdigest()!=r['profile']['sha256']:raise icc.error('CORRUPT','交付ICC与配方不一致')
        combined=hashlib.sha256()
        for name in expected_names[:-2]:
            result=png_icc.inspect(directory/name,profile,w,h,cancel=poll);combined.update(bytes.fromhex(result['RGBA16BE_sha256'][7:]))
        a0,a1=r.get('audio_start_sample'),r.get('audio_end_sample_exclusive')
        if type(a0) is not int or type(a1) is not int or not 0<=a0<=a1 or (a1-a0)*8!=files[-1]['bytes']:raise icc.error('AUDIO_CLOCK','交付音频采样边界/长度不一致')
        scalars=0
        with (directory/'audio.f32le').open('rb') as stream:
            while block:=stream.read(65536):
                poll();v=np.frombuffer(block,dtype='<f4')
                if not np.isfinite(v).all():raise icc.error('AUDIO_VALUES','交付PCM存在非有限值')
                scalars+=len(v)
        return {'status':'verified','frames':stop-start,'all_png_pixels_and_CRC_verified':True,'embedded_profiles_exact':True,
            'ordered_pixel_hashes_sha256':'sha256:'+combined.hexdigest(),'audio_sample_frames':a1-a0,'audio_scalars':scalars,
            'manifest_sha256':digest(manifest_path),'original_inputs_revalidated':False,'rights_or_artistic_acceptance':False}

def prepare(root,project,sequence_id,output,profile,*,start_frame=0,stop_frame=None,range_policy='reject',max_output_bytes=MAX_BYTES):
    root=Path(root).resolve();destination=_owned(root,output)
    if destination==root or destination.exists():raise icc.error('OUTPUT_EXISTS','ICC序列目标须是工程内不存在的新目录')
    sequence=next((s for s in project['sequences'] if s['id']==sequence_id),None)
    if sequence is None:raise icc.error('SEQUENCE','目标序列不存在')
    if type(max_output_bytes) is not int or not 1<=max_output_bytes<=MAX_BYTES:raise icc.error('BUDGET','ICC序列产物预算须为1字节至8GiB')
    if range_policy not in ('reject','clip'):raise icc.error('RANGE','ICC输出须明确reject/clip')
    cfg=configuration(project['settings']['pixel_pipeline'],project['settings'],output_settings(project['settings']))
    signal=cfg['working']
    if 'display_mapping' in cfg['mappings']:signal=LuminanceSignal('bt709','linear',cfg['mappings']['display_mapping']['target_peak_nits'])
    target=icc_output.parse_output_profile(profile)
    with icc_output.OutputProfileTransform(root,target,signal):pass
    fps_config=project['settings']['timebase']['display_fps'];fps=Fraction(fps_config['num'],fps_config['den'])
    ticks=project['settings']['timebase']['ticks_per_second'];duration=Fraction(sequence['duration_tick'],ticks)
    count=math.ceil(duration*fps);stop=count if stop_frame is None else stop_frame
    if type(start_frame) is not int or type(stop) is not int or not 0<=start_frame<stop<=count or stop-start_frame>1000000:
        raise icc.error('RANGE','ICC序列须使用有效的半开CFR帧区间')
    canvas=sequence_canvas(project,sequence);w,h=canvas['width'],canvas['height']
    if max(w,h)>16384 or w*h>16777216:raise icc.error('BUDGET','ICC序列表面超过预算')
    # First audio sample on/after the selected CFR boundaries; last boundary
    # is clamped to the authored duration, not extended to a rounded-up frame.
    a0=math.ceil(Fraction(start_frame,1)/fps*48000)
    a1=math.ceil(min(Fraction(stop,1)/fps,duration)*48000)
    size=icc.profile_path(root,target).stat().st_size
    estimate=(stop-start_frame)*png_icc.estimate(w,h,size)+(a1-a0)*8+size+(stop-start_frame)*1536+1024**2
    if estimate>max_output_bytes:raise icc.error('BUDGET','ICC序列保守产物估算超过预算')
    recipe={'protocol':PROTOCOL,'project_sha256':float_audio_graph.project_digest(project),'sequence_id':sequence_id,
        'profile':vars(target),'linear_signal':vars(signal),'start_frame':start_frame,'stop_frame_exclusive':stop,
        'fps':str(fps),'width':w,'height':h,'audio_start_sample':a0,'audio_end_sample_exclusive':a1,
        'range_policy':range_policy,'max_output_bytes':max_output_bytes,'estimated_output_bytes':estimate,
        'softproof_applied_to_device_output':False,'display_mapping_applied':'display_mapping' in cfg['mappings']}
    return {'status':'planned','recipe':recipe,'recipe_sha256':'sha256:'+__import__('hashlib').sha256(canonical(recipe)).hexdigest(),
        'output':str(destination),'native_decode_started':False,'audio_format':'stereo interleaved Float32LE, 48000Hz',
        'encoded_movie':False,'timeline_renderer_integrated':True}

def export(root,project,plan,*,cancel_file=None,progress=None):
    root=Path(root).resolve();recipe=plan['recipe'];marker=Path(cancel_file) if cancel_file else None
    poll=lambda:cancel(marker)
    if plan['recipe_sha256']!='sha256:'+__import__('hashlib').sha256(canonical(recipe)).hexdigest():raise icc.error('RECIPE','ICC序列配方摘要变化')
    if recipe['project_sha256']!=float_audio_graph.project_digest(project):raise icc.error('INPUT_CHANGED','ICC序列作者工程已改变')
    destination=_owned(root,plan['output']);poll()
    if destination.exists():raise icc.error('OUTPUT_EXISTS','ICC序列输出已存在')
    sequence=next(s for s in project['sequences'] if s['id']==recipe['sequence_id'])
    target=icc_output.parse_output_profile(recipe['profile']);signal=icc.parse_source_signal(recipe['linear_signal'])
    temporary=None;committed=False
    with verification_scope():
        # Freeze originals including audio-only dependencies for the entire
        # render/publication scope, rather than just the visual source handles.
        artifacts=[]
        for asset in project['assets']:
            p=resolve_local_path(root,asset['uri'],field='icc-sequence.asset')
            entry=artifact_entry(p,'icc-sequence-original')
            if entry['sha256']!=asset['sha256']:raise icc.error('INPUT_CHANGED','原始资产SHA与登记不符')
            artifacts.append(entry)
        for path in [icc.profile_path(root,target),*icc.runtime_paths()]:
            row=artifact_entry(path,'icc-sequence-output-profile-runtime')
            if path==icc.profile_path(root,target) and row['sha256']!=target.sha256:raise icc.error('INPUT_CHANGED','ICC输出配置与计划摘要不同')
            artifacts.append(row)
        for name in ('icc_sequence','icc_output','png_icc'):
            artifacts.append(artifact_entry(Path(__file__).with_name(name+'.py'),'icc-sequence-runtime'))
        from .float_preview import runtime_paths
        numerical=sorted(runtime_paths());empty_markers=[str(p) for p in numerical if p.stat().st_size==0]
        for path in numerical:
            if path.stat().st_size:artifacts.append(artifact_entry(path,'icc-sequence-numerical-runtime'))
        def verify():
            poll()
            if recipe['project_sha256']!=float_audio_graph.project_digest(project):raise icc.error('INPUT_CHANGED','作者工程在执行期间变化')
            for row in artifacts:
                if digest(row['path'])!=row['sha256']:raise icc.error('INPUT_CHANGED','ICC序列源/执行实现变化')
        destination.parent.mkdir(parents=True,exist_ok=True)
        if shutil.disk_usage(destination.parent).free<recipe['estimated_output_bytes']+64*1024**2:raise icc.error('BUDGET','ICC序列输出磁盘空间不足')
        try:
            with icc_output.OutputProfileTransform(root,target,signal,cancel=poll) as transform:
                profile=icc.profile_path(root,target).read_bytes()
                if 'sha256:'+__import__('hashlib').sha256(profile).hexdigest()!=target.sha256:raise icc.error('INPUT_CHANGED','ICC输出配置变化')
                temporary=Path(tempfile.mkdtemp(prefix='.icc-sequence-',dir=destination.parent));rows=[];clipped=0
                (temporary/'output.icc').write_bytes(profile)
                with FloatRenderContext(root,project,sequence,output_settings(project['settings']),cancel_file=marker) as renderer:
                    if renderer.timeline.frame_count<recipe['stop_frame_exclusive']:raise icc.error('RANGE','作者时间线帧数与计划不符')
                    for index in range(recipe['start_frame'],recipe['stop_frame_exclusive']):
                        poll();surface,_=renderer.timeline.render_frame(index)
                        if recipe['display_mapping_applied']:
                            surface,actual_signal,_=map_display(surface,renderer.config['working'],renderer.config['mappings']['display_mapping'],cancel=poll)
                            if vars(actual_signal)!=vars(signal):raise icc.error('SIGNAL','显示映射工作信号变化')
                        delivered,boundary=transform.convert(surface,range_policy=recipe['range_policy'])
                        name=f'frame-{index:09d}.png';p=temporary/name
                        png_icc.write(p,delivered,profile,max_bytes=png_icc.estimate(recipe['width'],recipe['height'],len(profile)),cancel=poll)
                        clipped+=boundary['encoded_output_components_clipped']
                        rows.append({'name':name,'bytes':p.stat().st_size,'sha256':digest(p),'timeline_frame':index,
                            'timeline_time_seconds':str(Fraction(index,1)/Fraction(recipe['fps']))})
                        if progress:progress(len(rows),recipe['stop_frame_exclusive']-recipe['start_frame'])
                    audio=float_audio_graph.prepare(root,project,sequence['id'],cancel_file=marker)
                    a0,a1=recipe['audio_start_sample'],recipe['audio_end_sample_exclusive'];audio_path=temporary/'audio.f32le'
                    if a1>a0:
                        graph=audio['filter_complex']+f';[aout]atrim=start_sample={a0}:end_sample={a1},asetpts=N/SR/TB[icc_audio]'
                        command=[ffmpeg_path(),'-nostdin','-v','error',*audio['inputs'],'-filter_complex',graph,'-map','[icc_audio]',
                            '-ar','48000','-ac','2','-c:a','pcm_f32le','-f','f32le',str(audio_path)]
                        pipe=_EncoderPipe(command,cwd=root,cancel_file=marker,timeout=3600)
                        try:pipe.finish()
                        finally:pipe.close()
                    else:audio_path.write_bytes(b'')
                    expected=(a1-a0)*8
                    if audio_path.stat().st_size!=expected:raise icc.error('AUDIO_CLOCK','实际PCM长度与作者选区采样时钟不符')
                    float_audio_graph.verify(root,audio,cancel_file=marker);renderer.finish_sources()
                    metadata=renderer.metadata
                transform.verify();verify()
                cmm=dict(transform.metadata)
            cmm.update(closed=True,native_handles_closed=True)
            files=[*rows,{'name':'output.icc','bytes':len(profile),'sha256':digest(temporary/'output.icc')},
                {'name':'audio.f32le','bytes':expected,'sha256':digest(audio_path)}]
            manifest={'protocol':PROTOCOL,'recipe':recipe,'recipe_sha256':plan['recipe_sha256'],'frames':len(rows),'files':files,
                'CMM':cmm,'timeline':metadata,'audio':{'sample_rate':48000,'channels':2,'format':'interleaved Float32LE',
                'sample_frames':a1-a0,'start_sample':a0,'end_sample_exclusive':a1,'authored_graph':audio},
                'encoded_output_components_clipped_all_frames':clipped,'implementation_artifacts':artifacts,
                'softproof_applied_to_device_output':False,'empty_numerical_package_markers':empty_markers,'network':False,'native_windows':True}
            payload=canonical(manifest)+b'\n'
            if len(payload)>16*1024**2 or sum(r['bytes'] for r in files)+len(payload)>recipe['max_output_bytes']:
                raise icc.error('BUDGET','ICC序列实际产物超过显式预算')
            (temporary/'sequence.json').write_bytes(payload);verify();_owned(root,destination)
            if destination.exists():raise icc.error('OUTPUT_EXISTS','发布时ICC序列目标已存在')
            temporary.rename(destination);committed=True
            return {'status':'succeeded','output':str(destination),'manifest':str(destination/'sequence.json'),
                'manifest_sha256':digest(destination/'sequence.json'),'frames':len(rows),'audio_sample_frames':a1-a0,
                'encoded_output_components_clipped_all_frames':clipped,'encoded_movie':False,'timeline_renderer_integrated':True}
        finally:
            if temporary is not None and not committed and temporary.exists():
                _owned(root,temporary);shutil.rmtree(temporary)
