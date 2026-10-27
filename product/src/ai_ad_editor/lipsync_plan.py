"""Finite native lip-sync clocks, explicit face boxes and portable edit recipes."""
import copy,json,math,re
from pathlib import Path
from .errors import argument_error
from .local_lipsync import ENGINE,PROTOCOL,boxes,error
from .media import probe_media
from .policy import resolve_local_path
from .utils import sha256_file,sha256_bytes


def digest(value):
    return 'sha256:'+sha256_bytes(json.dumps({k:v for k,v in value.items() if k!='sha256'},sort_keys=True,separators=(',',':'),allow_nan=False).encode())


def options(*,seed=0,mask_top=.45,feather_pixels=3):
    if type(seed)is not int or not 0<=seed<2**63:raise argument_error('seed须为0..2^63-1整数','seed')
    if any(type(v)not in (int,float) or not math.isfinite(v) for v in (mask_top,feather_pixels)) or not 0<=mask_top<=.8 or not 0<=feather_pixels<=32:
        raise argument_error('mask-top须为0..0.8，feather-pixels须为0..32','mask-top/feather-pixels')
    return dict(seed=seed,mask_top=mask_top,feather_pixels=feather_pixels)


def reference(root,asset,kind):
    if not asset or (asset.get('kind') not in {'image','video'} if kind=='source' else asset.get('kind') not in {'audio','video'}):
        raise error('ASSET','须选择已登记的本地图片/视频和音频资产',kind=kind)
    path=resolve_local_path(root,asset['uri'],field=kind+'-asset')
    if not path.is_file() or 'sha256:'+sha256_file(path)!=asset['sha256']:raise error('SOURCE_CHANGED','源资产文件与登记摘要不符')
    probe=probe_media(path)
    if kind=='source':
        video=probe['video'];stream=next((s for s in probe['streams'] if s['codec_type']=='video'),{})
        if not video.get('codec'):raise error('SOURCE_VIDEO','源资产没有可解码画面')
        if asset['kind']=='image':
            from PIL import Image
            with Image.open(path) as image:
                if image.mode not in {'RGB','RGBA','L','LA','P'} or image.info.get('icc_profile') or image.getexif().get(274,1)!=1 or getattr(image,'n_frames',1)!=1:
                    raise error('SOURCE_SIGNAL','图片须明确转换为无ICC、无旋转的单帧8bit SDR素材')
        if (stream.get('color_transfer') in {'smpte2084','arib-std-b67'} or stream.get('color_primaries') in {'bt2020','smpte431','smpte432'}
            or re.search(r'(?:p|rgba?|bgra?|gray)(?:9|10|12|14|16|32|48|64)(?:le|be)?$',str(video.get('pix_fmt','')))
            or int(stream.get('bits_per_raw_sample',0) or 0)>8
            or stream.get('sample_aspect_ratio','1:1') not in (None,'','0:1','1:1')
            or stream.get('field_order','progressive') not in (None,'','unknown','progressive')
            or any(float(row.get('rotation',0))!=0 for row in stream.get('side_data_list',[]))
            or float(stream.get('tags',{}).get('rotate',0))!=0):raise error('SOURCE_SIGNAL','口型模型仅接收方形像素、无旋转、逐行8bit SDR输入；请明确预处理HDR/高位深素材')
    else:
        stream=next((s for s in probe['streams'] if s['codec_type']=='audio'),{})
        if not stream or not 8000<=probe['audio']['sample_rate']<=96000 or not 1<=probe['audio']['channels']<=8:
            raise error('AUDIO_FORMAT','音频须为8..96kHz、1..8声道')
    return dict(asset_id=asset['id'],kind=asset['kind'],path=str(path),sha256=asset['sha256'],probe=probe,stream_index=stream['index'])


def configuration(source,audio,*,face_boxes,settings,audio_start_seconds=0,audio_end_seconds=None,
                  source_start_seconds=0,source_end_seconds=None,source_mode='once',storage_budget_mib=2048,**parameters):
    opts=options(**parameters)
    def span(start,end,duration,label):
        end=duration if end is None else end
        if any(type(v)not in (int,float) or not math.isfinite(v) for v in (start,end,duration)) or not 0<=start<end<=duration+.000001:
            raise error('RANGE','源范围须有限并位于实际素材内',kind=label)
        return start,min(end,duration)
    ap=audio['probe']['audio'];rate=ap['sample_rate'];channels=ap['channels']
    audio_duration=ap['duration_seconds'] or audio['probe']['duration_seconds']
    a,b=span(audio_start_seconds,audio_end_seconds,audio_duration,'audio')
    first,last=round(a*rate),round(b*rate);samples=last-first
    if samples<=0:raise error('AUDIO_EMPTY','所选音频不足一个样本')
    frames=(samples*25+rate-1)//rate
    if not 1<=frames<=15000:raise error('DURATION','每次口型同步须在600秒内')
    target_samples=(frames*rate+24)//25
    width=source['probe']['video']['width'];height=source['probe']['video']['height']
    if not 32<=width<=4096 or not 32<=height<=4096:raise error('RASTER','输入画幅须为32..4096像素')
    if source_mode not in {'once','hold','loop'}:raise error('SOURCE_MODE','source-mode须为once/hold/loop')
    if source['kind']=='image':
        if source_start_seconds!=0 or source_end_seconds is not None or source_mode!='once':
            raise error('IMAGE_RANGE','单张图片会明确重复到输出时长，不接收视频源范围或循环模式')
        start,end=0,None
    else:
        duration=source['probe']['video']['duration_seconds'] or source['probe']['duration_seconds']
        start,end=span(source_start_seconds,source_end_seconds,duration,'video')
        if source_mode=='once' and end-start+.000001<frames/25:raise error('SOURCE_TOO_SHORT','视频源不足，须缩短音频或明确选择hold/loop')
        if source_mode=='loop' and (start!=0 or source_end_seconds is not None):raise error('LOOP_RANGE','loop当前明确循环完整源视频；子区间请先生成独立素材')
    boxes(face_boxes,width,height,frames)
    if type(storage_budget_mib)is not int or not 16<=storage_budget_mib<=2048:raise error('STORAGE','storage-budget-mib须为16..2048')
    maximum_output=width*height*5*frames+target_samples*channels*4+1024**2
    work_estimate=maximum_output*2+target_samples*channels*8+frames*640*4+4*1024**2
    if maximum_output>2*1024**3 or work_estimate>storage_budget_mib*1024**2:
        raise error('STORAGE','保守无损工作空间估算超过显式预算；请缩短范围或预缩放',estimated_bytes=work_estimate)
    array_estimate=(settings['batch_size']+8)*width*height*16+frames*50*5*384*2//25+32*1024**2
    if array_estimate>settings['state_budget_bytes']:raise error('ARRAY_BUDGET','画幅、时长和批次超过512MiB受管数组预算',estimated_bytes=array_estimate)
    return dict(engine=ENGINE,protocol=PROTOCOL,network='disabled',video=dict(width=width,height=height,frames=frames,fps='25',duration_seconds=frames/25),
        range=dict(start_seconds=start,end_seconds=end,source_mode=source_mode),audio=dict(start_sample=first,end_sample=last,samples=samples,
        sample_rate=rate,channels=channels,padded_samples=target_samples-samples,output_samples=target_samples,preserve=True,
        padding_seconds=(target_samples-samples)/rate),boxes=copy.deepcopy(face_boxes),options=opts,
        storage_budget_bytes=storage_budget_mib*1024**2,estimated_workspace_bytes=work_estimate,estimated_array_bytes=array_estimate)


def recipe(plan,source,audio):
    value=dict(protocol=PROTOCOL,source_asset_id=source['asset_id'],audio_asset_id=audio['asset_id'],
        source_sha256=source['sha256'],audio_sha256=audio['sha256'],source_kind=source['kind'],
        video=copy.deepcopy(plan['video']),range=copy.deepcopy(plan['range']),audio=copy.deepcopy(plan['audio']),
        boxes=copy.deepcopy(plan['boxes']),options=copy.deepcopy(plan['options']))
    return {**value,'sha256':digest(value)}


def validate_recipe(value,*,asset,assets=None):
    try:
        expected={'protocol','source_asset_id','audio_asset_id','source_sha256','audio_sha256','source_kind','video','range','audio','boxes','options','sha256'}
        if not isinstance(value,dict) or set(value)!=expected or value['protocol']!=PROTOCOL or digest(value)!=value['sha256']:raise ValueError('recipe protocol/digest')
        v=value['video'];a=value['audio'];r=value['range']
        if set(v)!={'width','height','frames','fps','duration_seconds'} or any(type(v[k])is not int or v[k]<1 for k in ('width','height','frames')) or v['frames']>15000 or max(v['width'],v['height'])>4096 or v['fps']!='25' or v['duration_seconds']!=v['frames']/25:raise ValueError('video clock')
        boxes(value['boxes'],v['width'],v['height'],v['frames'])
        if value['options']!=options(**value['options']) or set(r)!={'start_seconds','end_seconds','source_mode'} or r['source_mode'] not in {'once','hold','loop'}:raise ValueError('recipe options')
        if type(r['start_seconds'])not in (int,float) or not math.isfinite(r['start_seconds']) or r['start_seconds']<0 or r['end_seconds'] is not None and (type(r['end_seconds'])not in (int,float) or not math.isfinite(r['end_seconds']) or r['end_seconds']<=r['start_seconds']):raise ValueError('source range')
        required={'start_sample','end_sample','samples','sample_rate','channels','padded_samples','output_samples','preserve','padding_seconds'}
        if set(a)!=required or any(type(a[k])is not int for k in required-{'preserve','padding_seconds'}) or not 0<=a['start_sample']<a['end_sample'] or a['samples']!=a['end_sample']-a['start_sample'] or not 8000<=a['sample_rate']<=96000 or not 1<=a['channels']<=8 or not a['preserve']:raise ValueError('audio samples')
        if v['frames']!=(a['samples']*25+a['sample_rate']-1)//a['sample_rate'] or a['output_samples']!=(v['frames']*a['sample_rate']+24)//25 or a['padded_samples']!=a['output_samples']-a['samples'] or a['padding_seconds']!=a['padded_samples']/a['sample_rate']:raise ValueError('audio clock')
        if value['source_kind'] not in {'image','video'}:raise ValueError('source kind')
        for role in ('source','audio'):
            ident=value[role+'_asset_id'];source_digest=value[role+'_sha256']
            if ident==asset['id'] or not isinstance(ident,str) or not isinstance(source_digest,str) or not re.fullmatch(r'sha256:[0-9a-f]{64}',source_digest):raise ValueError('source reference')
            if assets is not None and (ident not in assets or assets[ident]['sha256']!=source_digest or (assets[ident]['kind']!=value['source_kind'] if role=='source' else assets[ident]['kind'] not in {'audio','video'})):raise ValueError('source asset/hash')
        probe=asset.get('probe',{}).get('video',{})
        if asset['kind']!='video' or any(probe.get(k)!=v[k] for k in ('width','height')):raise ValueError('generated asset dimensions')
        from fractions import Fraction
        stream=next(s for s in asset['probe']['streams'] if s.get('codec_type')=='video')
        audio_stream=next(s for s in asset['probe']['streams'] if s.get('codec_type')=='audio')
        if int(stream.get('nb_frames',0))!=v['frames'] or Fraction(stream.get('avg_frame_rate','0'))!=25:raise ValueError('generated frame clock')
        if (int(audio_stream['sample_rate']),int(audio_stream['channels']))!=(a['sample_rate'],a['channels']) or round(int(audio_stream['duration_ts'])*Fraction(audio_stream['time_base'])*a['sample_rate'])!=a['output_samples']:raise ValueError('generated PCM clock')
        if asset.get('source',{}).get('derived_from')!=list(dict.fromkeys((value['source_asset_id'],value['audio_asset_id']))):raise ValueError('parent assets')
    except (ValueError,KeyError,TypeError,OverflowError,StopIteration,ZeroDivisionError) as exc:raise error('RECIPE','口型同步可编辑配方不完整或引用变化',cause=str(exc)) from exc
    return value


def rebind_recipe(value,*,mapping,asset,assets):
    validate_recipe(value,asset=asset,assets=assets)
    result=copy.deepcopy(value)
    for role in ('source','audio'):result[role+'_asset_id']=mapping.get(result[role+'_asset_id'],result[role+'_asset_id'])
    result['sha256']=digest(result);return result
