"""Native video clocks, aligned original PCM and portable interpolation recipes."""
import copy,json,math,re
from fractions import Fraction
from .local_interpolation import ENGINE,PROTOCOL,error
from .interpolation_clock import selected_clock,subdivision,duration_seconds,validate_clock,clock_digest
from .lipsync_plan import digest

def normalize_options(*,cut_after_frame=None,scene_cut_threshold=.35):
    cuts=[] if cut_after_frame is None else cut_after_frame
    if not isinstance(cuts,list) or any(type(v)is not int or v<0 for v in cuts) or len(cuts)>14999 or len(set(cuts))!=len(cuts):raise error('CUTS','cut-after-frame须为不重复的选区相对帧索引')
    if scene_cut_threshold is not None and (type(scene_cut_threshold)not in (int,float) or not math.isfinite(scene_cut_threshold) or not 0<scene_cut_threshold<=1):raise error('CUT_THRESHOLD','切镜阈值须为0..1正数，或明确禁用')
    return dict(cut_after_frame=sorted(cuts),scene_cut_threshold=scene_cut_threshold)

def reference(root,asset):
    if not asset or asset.get('kind')!='video':raise error('ASSET','神经补帧须使用已登记的视频资产')
    from .lipsync_plan import reference as source_reference
    return source_reference(root,asset,'source')

def audio_plan(source,clock):
    streams=[s for s in source['probe']['streams'] if s.get('codec_type')=='audio']
    if not streams:return None
    stream=streams[0]
    try:
        rate=int(stream['sample_rate']);channels=int(stream['channels'])
        if not 8000<=rate<=96000 or not 1<=channels<=8:raise ValueError('audio format')
        origin=int(stream['start_pts'])*Fraction(stream['time_base']);extent=int(stream['duration_ts'])*Fraction(stream['time_base'])
        if extent<=0:raise ValueError('known audio duration required')
        total=round(extent*rate);base=validate_clock(clock);start=clock['pts'][0]*base;duration=duration_seconds(clock);end=start+duration
        output=round(duration*rate)
        first=min(total,max(0,round((start-origin)*rate)));last=min(total,max(0,round((end-origin)*rate)))
        lead=min(output,max(0,round((origin-start)*rate)));samples=last-first;tail=output-lead-samples
        if samples<0 or tail<0 or output<1:raise ValueError('audio boundary cannot fit rounded video clock')
        return dict(stream_index=stream['index'],sample_rate=rate,channels=channels,start_sample=first,end_sample=last,samples=samples,
            leading_zero_samples=lead,trailing_zero_samples=tail,output_samples=output,preserve=True,boundary='nearest-original-sample',
            original_origin=str(origin),rounding_error_seconds=str(Fraction(output,rate)-duration))
    except (ValueError,TypeError,KeyError,ZeroDivisionError,OverflowError) as exc:raise error('AUDIO_CLOCK','原音轨须具有可验证的起点、时长与采样时钟，未猜测或截断未知样本',cause=str(exc)) from exc

def configuration(source,clock,*,settings,start_frame=0,end_frame=None,factor=2,storage_budget_mib=2048,**options):
    try:selected=selected_clock(clock,start_frame,end_frame);output=subdivision(selected,factor);duration=duration_seconds(selected)
    except (ValueError,TypeError,ZeroDivisionError,OverflowError) as exc:raise error('CLOCK','原生帧时钟或选区无效',cause=str(exc)) from exc
    if not 0<duration<=600:raise error('DURATION','每次选择须为0..600秒')
    opts=normalize_options(**options);n=len(selected['pts'])
    if any(v>=n-1 for v in opts['cut_after_frame']):raise error('CUT_RANGE','cut-after-frame须指向选区内相邻两帧之间')
    width=source['probe']['video']['width'];height=source['probe']['video']['height']
    if not 32<=width<=4096 or not 32<=height<=4096:raise error('RASTER','输入画幅须为32..4096像素')
    audio=audio_plan(source,selected)
    if type(storage_budget_mib)is not int or not 16<=storage_budget_mib<=2048:raise error('STORAGE','存储预算须为16..2048MiB')
    maximum=width*height*5*n*factor+(audio['output_samples']*audio['channels']*4 if audio else 0)+1024**2
    work=maximum*2+(audio['output_samples']*audio['channels']*8 if audio else 0)+len(output['pts'])*100+4*1024**2
    if maximum>2*1024**3 or work>storage_budget_mib*1024**2:raise error('STORAGE','保守无损存储估算超过显式预算，请缩短选区或预缩放',estimated_bytes=work)
    arrays=width*height*4*18+16*1024**2
    if arrays>settings['state_budget_bytes']:raise error('ARRAY_BUDGET','画幅超过512MiB受管CPU数组预算',estimated_bytes=arrays)
    return dict(engine=ENGINE,protocol=PROTOCOL,network='disabled',source_clock=copy.deepcopy(clock),selected_clock=selected,output_clock=output,
        range=dict(start_frame=start_frame,end_frame=start_frame+n),video=dict(width=width,height=height,source_frames=n,frames=n*factor,factor=factor,duration_seconds=float(duration)),
        audio=audio,options=opts,storage_budget_bytes=storage_budget_mib*1024**2,estimated_workspace_bytes=work,estimated_output_bound_bytes=maximum,estimated_owned_array_bytes=arrays)

def recipe(plan,source):
    result=dict(protocol=PROTOCOL,source_asset_id=source['asset_id'],source_sha256=source['sha256'],
        **{k:copy.deepcopy(plan[k]) for k in ('range','video','source_clock','selected_clock','output_clock','audio','options')})
    result['sha256']=digest(result);return result

def validate_recipe(value,*,asset,assets=None):
    try:
        required={'protocol','source_asset_id','source_sha256','range','video','source_clock','selected_clock','output_clock','audio','options','sha256'}
        if not isinstance(value,dict) or set(value)!=required or value['protocol']!=PROTOCOL or digest(value)!=value['sha256']:raise ValueError('recipe protocol/digest')
        ident=value['source_asset_id'];sha=value['source_sha256'];v=value['video'];r=value['range']
        if not isinstance(ident,str) or ident==asset['id'] or not isinstance(sha,str) or not re.fullmatch(r'sha256:[0-9a-f]{64}',sha):raise ValueError('source reference')
        if set(r)!={'start_frame','end_frame'}:raise ValueError('range fields')
        selected=selected_clock(value['source_clock'],r['start_frame'],r['end_frame'])
        expected=subdivision(selected,v['factor'])
        if selected!=value['selected_clock'] or expected!=value['output_clock'] or v['source_frames']!=len(selected['pts']) or v['frames']!=len(expected['pts']) or v['duration_seconds']!=float(duration_seconds(selected)):raise ValueError('native frame clock')
        if set(v)!={'width','height','source_frames','frames','factor','duration_seconds'} or any(type(v[k])is not int or not 32<=v[k]<=4096 for k in ('width','height')) or not 0<v['duration_seconds']<=600:raise ValueError('raster/duration')
        if value['options']!=normalize_options(**value['options']) or any(i>=v['source_frames']-1 for i in value['options']['cut_after_frame']):raise ValueError('cut options')
        if assets is not None:
            if ident not in assets or assets[ident]['kind']!='video' or assets[ident]['sha256']!=sha:raise ValueError('source asset/hash')
            source=assets[ident]
            expected_audio=audio_plan({'probe':source['probe']},selected)
            if value['audio']!=expected_audio:raise ValueError('original audio clock')
        if asset['kind']!='video' or any(asset['probe']['video'].get(k)!=v[k] for k in ('width','height')) or asset.get('source',{}).get('derived_from')!=[ident]:raise ValueError('asset/parents')
        stream=next(s for s in asset['probe']['streams'] if s.get('codec_type')=='video')
        if int(stream.get('nb_frames',0))!=v['frames'] or int(stream['duration_ts'])*Fraction(stream['time_base'])!=duration_seconds(expected):raise ValueError('generated native clock')
        audio=[s for s in asset['probe']['streams'] if s.get('codec_type')=='audio'];a=value['audio']
        if bool(audio)!=bool(a):raise ValueError('generated audio presence')
        if a and ((int(audio[0]['sample_rate']),int(audio[0]['channels']))!=(a['sample_rate'],a['channels']) or int(audio[0]['duration_ts'])*Fraction(audio[0]['time_base'])*a['sample_rate']!=a['output_samples']):raise ValueError('generated PCM clock')
    except (ValueError,KeyError,TypeError,OverflowError,StopIteration,ZeroDivisionError) as exc:raise error('RECIPE','补帧配方不完整、时钟或引用变化',cause=str(exc)) from exc
    return value

def rebind_recipe(value,*,mapping,asset,assets):
    validate_recipe(value,asset=asset,assets=assets);result=copy.deepcopy(value)
    result['source_asset_id']=mapping.get(result['source_asset_id'],result['source_asset_id']);result['sha256']=digest(result);return result
