"""Local source-raster to timeline-canvas tracking bindings.

Observations are immutable source-clock evidence. Canvas keyframes are a
rebuildable projection, compiled again for the current project/output canvas.
No model is executed while validating or rendering a saved binding.
"""
from __future__ import annotations

import bisect
import copy
import math
import re
from fractions import Fraction
from pathlib import Path
from typing import Any

from .animation import keyframe_value
from .errors import AppError
from .sequence_canvas import sequence_canvas

BINDING_VERSION = 'timeline-canvas-v1'
MAX_BINDING_FRAMES = 20_000
MAX_SOURCE_FRAGMENTS = 128


def source_references(binding: dict) -> list[dict]:
    """Native edit lineage; an explicit empty route is a retained hidden binding."""
    if 'source_fragments' in binding:return binding['source_fragments']
    return [dict(track_id=binding.get('source_track_id'),clip_id=binding['source_clip_id'])]


def find_sources(sequence: dict, binding: dict) -> list[tuple[dict, dict]]:
    result = []
    for reference in source_references(binding):
        result.append(find_source(sequence, {**binding, 'source_track_id':reference['track_id'],
            'source_clip_id':reference['clip_id']}, allow_window=True))
    spans = sorted((c['timeline_start_tick'], c['timeline_start_tick']+c['duration_tick']) for _, c in result)
    if any(a[1] > b[0] for a, b in zip(spans, spans[1:])):
        raise invalid('同一绑定的源片段窗口不能重叠；须先明确唯一的源覆盖')
    return result


def invalid(message: str, field: str = 'tracking_binding') -> AppError:
    return AppError('TRACK_BIND_GEOMETRY_INVALID', message, exit_code=2, path=field)


def _finite(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise invalid('绑定中的数字必须有限且不能是布尔值')
    return float(value)


def find_source(sequence: dict, binding: dict, *, allow_window: bool = False) -> tuple[dict, dict]:
    for track in sequence.get('tracks', []):
        if track.get('id') == binding['source_track_id']:
            for clip in track.get('clips', []):
                if clip.get('id') == binding['source_clip_id']:
                    if clip.get('presentation_window') is not None and not allow_window:
                        raise invalid('跟踪绑定源暂不支持输出窗口时钟；请绑定完整作者片段')
                    if track.get('kind') not in {'video', 'overlay'} or clip.get('sequence_id') or clip.get('asset_id') != binding['asset_id']:
                        raise invalid('绑定源必须是匹配 asset_id 的直接视频片段')
                    return track, clip
    raise invalid('找不到绑定引用的源轨道/片段')


def native_clock_project(project: dict) -> bool:
    settings=project.get('settings',{})
    value=settings.get('pixel_pipeline') if isinstance(settings,dict) else None
    return isinstance(value,dict) and value.get('engine') == 'float32-native-v1'


def validate_binding(project: dict, sequence: dict, track: dict, clip: dict, *, native_clock: bool | None = None) -> None:
    native_clock = native_clock_project(project) if native_clock is None else native_clock
    b = clip.get('tracking_binding')
    if b is None:
        return
    required = {'version','source_track_id','source_clip_id','asset_id','source_sha256','range','observations','offset','scale_mode','scale_multiplier','rotation_mode','base'}
    extra = {'source_fragments','reference_output_tick'} if native_clock else set()
    if not isinstance(b, dict) or not required <= set(b) or set(b)-required-extra or b.get('version') != BINDING_VERSION:
        raise invalid('绑定字段或版本无效')
    if track.get('kind') == 'audio' or clip.get('sequence_id'):
        raise invalid('绑定目标必须是直接视觉片段')
    if not all(isinstance(b[k], str) and b[k] for k in ('source_track_id','source_clip_id','asset_id')) or b['source_clip_id'] == clip.get('id'):
        raise invalid('绑定源引用无效或源与目标相同')
    if 'source_fragments' in b:
        refs = b['source_fragments']
        if not isinstance(refs,list) or len(refs)>MAX_SOURCE_FRAGMENTS or any(
            not isinstance(r,dict) or set(r)!={'track_id','clip_id'} or any(not isinstance(v,str) or not v for v in r.values())
            for r in refs):
            raise invalid('原生源分片须为0..128个明确轨道/片段引用')
        if len({(r['track_id'],r['clip_id']) for r in refs})!=len(refs) or any(r['clip_id']==clip.get('id') for r in refs):
            raise invalid('原生源分片重复或引用目标自身')
        if refs and (b['source_track_id'],b['source_clip_id'])!=(refs[0]['track_id'],refs[0]['clip_id']):
            raise invalid('主源引用须与第一项源分片一致')
    if 'reference_output_tick' in b and (type(b['reference_output_tick']) is not int or not 0<=b['reference_output_tick']<=2**53-1):
        raise invalid('绑定基准输出tick须为可精确表示的非负整数')
    sources = find_sources(sequence,b) if native_clock else [find_source(sequence,b)]
    assets = {a.get('id'):a for a in project.get('assets', [])}
    asset = assets.get(b['asset_id'], {})
    if asset.get('kind') != 'video' or not isinstance(b['source_sha256'], str) or not re.fullmatch(r'sha256:[0-9a-f]{64}', b['source_sha256']) or b['source_sha256'] != asset.get('sha256'):
        raise invalid('绑定证据与源视频资产摘要不匹配')
    video = asset.get('probe', {}).get('video', {})
    if not all(isinstance(video.get(k), (int,float)) and _finite(video[k]) > 0 for k in ('width','height')):
        raise invalid('绑定需要已探测的视频尺寸')
    stream = next((s for s in asset.get('probe',{}).get('streams',[]) if s.get('codec_type')=='video'),{})
    try:
        rotations = [float(stream.get('tags',{}).get('rotate',0)),*[float(s.get('rotation',0)) for s in stream.get('side_data_list',[])]]
        if any(r%360 for r in rotations) or stream.get('sample_aspect_ratio','1:1') not in {'1:1','0:1','N/A',None} or not native_clock and abs(float(stream.get('start_time') or 0)) > .001:
            raise ValueError('raster/PTS')
        if not native_clock and stream.get('avg_frame_rate') and stream.get('r_frame_rate') and Fraction(stream['avg_frame_rate']) != Fraction(stream['r_frame_rate']):
            raise ValueError('variable frame rate')
    except (TypeError,ValueError,ZeroDivisionError):
        raise invalid('绑定当前需要零旋转/起始 PTS、方形像素和一致的名义/平均帧率')
    if not isinstance(b['range'], dict) or set(b['range']) != {'start_seconds','end_seconds'}:
        raise invalid('绑定需要明确源时间范围')
    begin, end = (_finite(b['range'][k]) for k in ('start_seconds','end_seconds'))
    if not 0 <= begin < end:
        raise invalid('绑定源时间范围无效')
    if not isinstance(b['observations'], list) or not 1 <= len(b['observations']) <= 4000:
        raise invalid('绑定需要 1..4000 个实际观测')
    previous = -1.0
    for observation in b['observations']:
        if not isinstance(observation, dict) or set(observation) != {'at_seconds','x','y','width','height','confidence'}:
            raise invalid('绑定观测字段无效')
        at, x, y, w, h, confidence = (_finite(observation[k]) for k in ('at_seconds','x','y','width','height','confidence'))
        if not begin-1e-6 <= at <= end+1e-6 or at <= previous or not 0 <= x <= 1 or not 0 <= y <= 1 or not 0 < w <= 1 or not 0 < h <= 1 or not 0 <= confidence <= 1:
            raise invalid('绑定观测时钟、框或置信度无效')
        previous = at
    if not isinstance(b['offset'], dict) or set(b['offset']) != {'x','y'} or any(abs(_finite(v)) > 1 for v in b['offset'].values()):
        raise invalid('绑定画布偏移必须位于 -1..1')
    if b['scale_mode'] not in {'none','roi'} or b['rotation_mode'] not in {'none','source'} or not 0 < _finite(b['scale_multiplier']) <= 20:
        raise invalid('绑定缩放或旋转设置无效')
    if not isinstance(b['base'], dict) or set(b['base']) != {'scale','rotation','opacity','opacity_keyframes'}:
        raise invalid('绑定目标基准无效')
    base = b['base']
    if not 0 < _finite(base['scale']) <= 20 or not 0 <= _finite(base['opacity']) <= 1 or abs(_finite(base['rotation'])) > 3600 or not isinstance(base['opacity_keyframes'], list):
        raise invalid('绑定目标基准范围无效')
    previous = -1
    for p in base['opacity_keyframes']:
        if not isinstance(p, dict) or set(p)-{'at_tick','value','interpolation','control_points'} or not {'at_tick','value'} <= set(p) or type(p['at_tick']) is not int or p['at_tick'] < previous or not 0 <= _finite(p['value']) <= 1 or p.get('interpolation','linear') not in {'linear','hold','ease_in','ease_out','ease_in_out','bezier'}:
            raise invalid('绑定基准透明度关键帧无效')
        previous = p['at_tick']
        if p.get('interpolation') == 'bezier' and (not isinstance(p.get('control_points'), list) or len(p['control_points']) not in {2,4} or any(not math.isfinite(_finite(v)) for v in p['control_points'])):
            raise invalid('绑定基准透明度 Bezier 控制点无效')
    # Geometry-changing effects need their own inverse mappings, not a guessed
    # affine approximation. Colour/blur effects do not change the point map.
    for effect in (effect for _, source in sources for effect in source.get('effects', [])):
        name = str(effect.get('type','') if isinstance(effect, dict) else effect).lower()
        if name in {'lenscorrection','lens_correction','perspective','v360','transpose'}:
            raise invalid('源效果尚无坐标逆映射: '+name)


def make_binding(project: dict, sequence: dict, source_track: dict, source_clip: dict, target_track: dict, target_clip: dict, tracking: dict, *, offset_x: float, offset_y: float, scale_mode: str, scale_multiplier: float, rotation_mode: str) -> dict:
    transform = target_clip.get('transform') or {}
    old = target_clip.get('tracking_binding')
    base = copy.deepcopy(old['base']) if isinstance(old, dict) and old.get('version') == BINDING_VERSION else {
        'scale':float(transform.get('scale',1)), 'rotation':float(transform.get('rotation',0)), 'opacity':float(transform.get('opacity',1)),
        'opacity_keyframes':copy.deepcopy(next((t.get('keyframes',[]) for t in target_clip.get('keyframes',[]) if t.get('property') in {'transform.opacity','opacity'}),[])),
    }
    frames = [{k:f[k] for k in ('at_seconds','x','y','width','height','confidence')} for f in tracking['frames']]
    range_value = tracking['range']
    binding = {'version':BINDING_VERSION, 'source_track_id':source_track['id'], 'source_clip_id':source_clip['id'], 'asset_id':source_clip['asset_id'], 'source_sha256':tracking['source_sha256'], 'range':{'start_seconds':range_value['start_seconds'],'end_seconds':range_value['end_seconds']}, 'observations':frames, 'offset':{'x':offset_x,'y':offset_y}, 'scale_mode':scale_mode, 'scale_multiplier':scale_multiplier, 'rotation_mode':rotation_mode, 'base':base}
    validate_binding(project,sequence,target_track,{**target_clip,'tracking_binding':binding})
    return binding


def _transform(clip: dict, at: float) -> dict[str, float]:
    transform = clip.get('transform') or {}
    result = {}
    for key, default in (('scale',1),('rotation',0),('opacity',1)):
        result[key] = keyframe_value(clip,('transform.'+key,key),float(transform.get(key,default)),at)
    for group in ('position','anchor'):
        raw = transform.get(group) or {}
        for axis in ('x','y'):
            result[group+'_'+axis] = keyframe_value(clip,(f'transform.{group}.{axis}',f'{group}.{axis}',f'{group}_{axis}'),float(raw.get(axis,transform.get(group+'_'+axis,.5))),at)
    return result


def _crop(clip: dict, tick: float, sw: int, sh: int) -> tuple[float,float,float,float,str]:
    crop = clip.get('crop') or {}
    if not crop:
        return 0,0,sw,sh,'fit'
    normalized = crop.get('unit','pixels') in {'normalized','relative'}
    merged = {**clip,'keyframes':[*clip.get('keyframes',[]),*[{**t,'property':t['property'] if t['property'].startswith('crop.') else 'crop.'+t['property']} for t in crop.get('keyframes',[])]]}
    animated = {t['property'] for t in merged['keyframes'] if str(t.get('property','')).startswith('crop.')}
    values = []
    for names, default, dimension in ((('x',),0,sw),(('y',),0,sh),(('width','w'),1 if normalized else sw,sw),(('height','h'),1 if normalized else sh,sh)):
        raw = float(next((crop[n] for n in names if n in crop),default))
        value = keyframe_value(merged,tuple('crop.'+n for n in names),raw,tick)
        values.append(value*dimension if normalized else value)
    x,y,w,h = values
    dynamic_size = bool(animated & {'crop.width','crop.w','crop.height','crop.h'})
    if dynamic_size:
        w,h = min(sw,max(2,w)),min(sh,max(2,h))
        x,y = min(sw-w,max(0,x)),min(sh-h,max(0,y))
    else:
        # Static native crop dimensions are rounded once; animated x/y are
        # evaluated per frame. exact=1 avoids hidden chroma-grid rounding.
        w = round(float(crop.get('width',crop.get('w',1 if normalized else sw)))*(sw if normalized else 1))
        h = round(float(crop.get('height',crop.get('h',1 if normalized else sh)))*(sh if normalized else 1))
        base_x = min(sw-2,max(0,round(float(crop.get('x',0))*(sw if normalized else 1))))
        base_y = min(sh-2,max(0,round(float(crop.get('y',0))*(sh if normalized else 1))))
        w,h = max(2,min(w,sw if 'crop.x' in animated else sw-base_x)),max(2,min(h,sh if 'crop.y' in animated else sh-base_y))
        x = min(sw-w,max(0,math.trunc(x))) if 'crop.x' in animated else base_x
        y = min(sh-h,max(0,math.trunc(y))) if 'crop.y' in animated else base_y
    return x,y,w,h,str(crop.get('fit',crop.get('mode','fit')))


def project_point(clip: dict, point: dict, *, at_tick: float, crop_tick: float, source_width: int, source_height: int, width: int, height: int) -> dict:
    x,y,cw,ch,fit = _crop(clip,crop_tick,source_width,source_height)
    sx,sy = width/cw,height/ch
    if fit != 'stretch':
        sx = sy = max(sx,sy) if fit == 'fill' else min(sx,sy)
    px = (point['x']*source_width-x)*sx+(width-cw*sx)/2
    py = (point['y']*source_height-y)*sy+(height-ch*sy)/2
    transform = _transform(clip,at_tick)
    if not math.isfinite(transform['scale']) or transform['scale'] <= 0:
        raise invalid('绑定源缩放必须为正数；镜像请使用 hflip/vflip')
    angle = math.radians(transform['rotation'])
    dx = (px-transform['anchor_x']*width)*transform['scale']
    dy = (py-transform['anchor_y']*height)*transform['scale']
    result = {'x':(transform['position_x']*width+dx*math.cos(angle)-dy*math.sin(angle))/width, 'y':(transform['position_y']*height+dx*math.sin(angle)+dy*math.cos(angle))/height,
            'roi_width_pixels':point['width']*source_width*sx*abs(transform['scale']), 'rotation':transform['rotation'], 'opacity':max(0,min(1,transform['opacity'])),
            'inside_crop':x <= point['x']*source_width < x+cw and y <= point['y']*source_height < y+ch}
    for effect in clip.get('effects',[]):
        name = str(effect.get('type','') if isinstance(effect,dict) else effect).lower()
        if name in {'hflip','flip','horizontal_flip'}:
            result['x'] = 1-result['x']; result['rotation'] = 180-result['rotation']
        elif name in {'vflip','vertical_flip'}:
            result['y'] = 1-result['y']; result['rotation'] = -result['rotation']
    return result


def _simplify(points: list[dict], tolerance: float = 1e-8) -> list[dict]:
    if len(points) <= 2:
        return points
    if points[0]['interpolation'] == 'hold':
        return [points[0],*[p for previous,p in zip(points,points[1:]) if p['value'] != previous['value']]]
    retained = {0,len(points)-1}
    stack = [(0,len(points)-1)]
    while stack:
        a,b = stack.pop()
        first,last = points[a],points[b]
        worst,index = tolerance,None
        for i in range(a+1,b):
            fraction = (points[i]['at_tick']-first['at_tick'])/max(1,last['at_tick']-first['at_tick'])
            error = abs(points[i]['value']-(first['value']+(last['value']-first['value'])*fraction))
            if error > worst:
                worst,index = error,i
        if index is not None:
            retained.add(index)
            stack.extend(((a,index),(index,b)))
    return [points[i] for i in sorted(retained)]


def compile_binding(project: dict, sequence: dict, track: dict, target: dict) -> dict:
    validate_binding(project,sequence,track,target)
    b = target['tracking_binding']
    source_track,source = find_source(sequence,b)
    asset = next(a for a in project['assets'] if a['id']==b['asset_id'])
    video = asset['probe']['video']
    settings = project['settings']; tps = settings['timebase']['ticks_per_second']
    fps_value = settings['timebase']['display_fps']; fps = Fraction(fps_value['num'],fps_value['den'])
    canvas = sequence_canvas(project, sequence)
    width,height = (canvas[k] for k in ('width','height'))
    start,duration = target['timeline_start_tick'],target['duration_tick']
    first = math.ceil(Fraction(start,tps)*fps)
    last = math.ceil(Fraction(start+duration,tps)*fps)
    if last-first+2 > MAX_BINDING_FRAMES:
        raise AppError('TRACK_BIND_FRAME_BUDGET', '绑定帧数超过 20000，请拆分序列或缩短片段', exit_code=2)
    ticks = sorted({0,duration,*[max(0,min(duration,round(Fraction(i*tps,1)/fps)-start)) for i in range(first,last)]})
    observations = b['observations']; times = [f['at_seconds'] for f in observations]
    # Reuse the renderer's exact integral/inverse for its supported speed curves.
    from .render import _speed_curve_segments, _reverse_speed_curve_segments, _speed_curve_source_seconds_at_elapsed, speed_curve_duration_seconds
    source_span = source['source_out_tick']-source['source_in_tick']
    segments = _speed_curve_segments(source,source_span,tps)
    if source.get('reverse'):
        segments = _reverse_speed_curve_segments(segments)
    content_duration = speed_curve_duration_seconds(source,source_span,tps) or source_span/tps/float(source.get('speed',1))
    try:
        source_fps = float(Fraction(str(video.get('fps') or '0')))
    except (ValueError,ZeroDivisionError):
        source_fps = 0
    if not 0 < source_fps <= 240:
        raise invalid('源视频需要已知且不超过 240 的帧率')
    frame_seconds = 1/source_fps
    first_source = math.ceil(source['source_in_tick']/tps*source_fps-1e-8)/source_fps
    last_source = (math.ceil(source['source_out_tick']/tps*source_fps-1e-8)-1)/source_fps
    values = {p:[] for p in ('position.x','position.y','opacity')}
    if b['scale_mode']=='roi': values['scale']=[]
    if b['rotation_mode']=='source': values['rotation']=[]
    first_width = first_rotation = None
    missing = hidden = 0
    opacity_clip = {'keyframes':[{'property':'opacity','keyframes':b['base']['opacity_keyframes']}]}
    # Match the renderer's CFR loop filter: start counts consumed frames,
    # so start=4 repeats input index 3. Non-grid holds use the same rounded
    # frame count as rendering, including the one-frame minimum.
    display_frame = float(1/fps)
    first_clock = math.ceil(source['timeline_start_tick']/tps/display_frame-1e-8)*display_frame
    clock_offset = first_clock-source['timeline_start_tick']/tps
    freeze = source.get('freeze') or {}
    requested_freeze_at = max(0,min(content_duration,float(freeze.get('at_tick',round(content_duration*tps)))/tps))
    requested_freeze_duration = max(0,float(freeze.get('duration_tick',0))/tps)
    freeze_frame = max(0,math.ceil(requested_freeze_at/display_frame-1e-8))
    freeze_start = clock_offset+max(1,freeze_frame)*display_frame
    held_elapsed = clock_offset+max(0,freeze_frame-1)*display_frame
    freeze_duration = max(1,round(requested_freeze_duration/display_frame))*display_frame if requested_freeze_duration > 0 else 0
    for tick in ticks:
        local_tick = start+tick-source['timeline_start_tick']
        elapsed = local_tick/tps
        content_elapsed = elapsed
        if freeze_duration > 0 and elapsed >= freeze_start:
            content_elapsed = held_elapsed if elapsed < freeze_start+freeze_duration else elapsed-freeze_duration
        distance = _speed_curve_source_seconds_at_elapsed(segments,max(0,content_elapsed)) if segments else max(0,content_elapsed)*float(source.get('speed',1))
        # The video chain resamples its remapped timestamps to the display
        # grid with round=up. Choose the last available source frame, matching
        # that framesync policy instead of moving a label between held frames.
        distance = math.floor(distance*source_fps+1e-7)/source_fps
        source_at = max(first_source,min(last_source,last_source-distance if source.get('reverse') else first_source+distance))
        right = bisect.bisect_right(times,source_at)
        left_ob = observations[max(0,right-1)]; right_ob = observations[min(right,len(observations)-1)]
        fraction = max(0,min(1,(source_at-left_ob['at_seconds'])/max(1e-9,right_ob['at_seconds']-left_ob['at_seconds'])))
        point = {k:left_ob[k]+(right_ob[k]-left_ob[k])*fraction for k in ('x','y','width','height')}
        mapped = project_point(source,point,at_tick=local_tick,crop_tick=max(0,content_elapsed*tps),source_width=int(video['width']),source_height=int(video['height']),width=width,height=height)
        first_width = mapped['roi_width_pixels'] if first_width is None else first_width
        first_rotation = mapped['rotation'] if first_rotation is None else first_rotation
        active = 0 <= local_tick < source['duration_tick'] and b['range']['start_seconds']-1e-6 <= source_at < b['range']['end_seconds']+1e-6 and mapped['inside_crop'] and not source_track.get('muted',False)
        hidden += not active
        missing += source_at < times[0]-1e-6 or source_at > times[-1]+frame_seconds+1e-6
        fields = {'position.x':mapped['x']+b['offset']['x'],'position.y':mapped['y']+b['offset']['y'], 'opacity':max(0,min(1,keyframe_value(opacity_clip,('opacity',),b['base']['opacity'],tick)*mapped['opacity'])) if active else 0}
        if 'scale' in values:
            fields['scale'] = max(.01,min(20,b['base']['scale']*b['scale_multiplier']*mapped['roi_width_pixels']/max(1e-9,first_width)))
        if 'rotation' in values:
            fields['rotation'] = b['base']['rotation']+mapped['rotation']-first_rotation
        for prop,value in fields.items():
            values[prop].append({'at_tick':tick,'value':round(value,9),'interpolation':'hold' if prop=='opacity' else 'linear'})
    keyframes = [{'property':'transform.'+prop,'keyframes':_simplify(points)} for prop,points in values.items()]
    warnings = ['tracking_observations_interpolated_in_source_clock','binding_is_sampled_at_project_display_fps','source_masks_and_occlusion_visibility_require_review']
    if missing: warnings.append('tracking_edges_held_outside_observed_clock')
    return {'coordinate_space':BINDING_VERSION,'source_clip_id':source['id'],'source_track_id':source_track['id'],'canvas':{'width':width,'height':height},'sampled_frames':len(ticks),'hidden_frames':hidden,'keyframes':keyframes,'warnings':warnings}


def apply_compiled_binding(target: dict, plan: dict) -> None:
    names = {t['property'] for t in plan['keyframes']}
    aliases = {n.removeprefix('transform.') for n in names}
    aliases |= {n.replace('.','_') for n in aliases}
    target['keyframes'] = [t for t in target.get('keyframes',[]) if t.get('property') not in names|aliases]+copy.deepcopy(plan['keyframes'])


def compile_project_bindings(project: dict) -> dict:
    result = copy.deepcopy(project)
    for sequence in result.get('sequences',[]):
        completed,visiting = set(),set()
        def resolve(track: dict, clip: dict) -> None:
            if not clip.get('tracking_binding') or clip['id'] in completed: return
            if clip['id'] in visiting: raise invalid('绑定引用形成循环')
            validate_binding(result,sequence,track,clip)
            visiting.add(clip['id'])
            source_track,source = find_source(sequence,clip['tracking_binding'])
            resolve(source_track,source)
            source['_tracking_binding_source'] = True
            plan = compile_binding(result,sequence,track,clip)
            clip['_tracking_binding_plan'] = {k:v for k,v in plan.items() if k != 'keyframes'}
            apply_compiled_binding(clip,plan)
            visiting.remove(clip['id']); completed.add(clip['id'])
        for track in sequence.get('tracks',[]):
            for clip in track.get('clips',[]): resolve(track,clip)
    return result


def validate_project_bindings(project: dict, root: Path | None = None) -> list[dict]:
    errors = []
    checked_assets = set()
    for si,sequence in enumerate(project.get('sequences',[])):
        links = {}
        for ti,track in enumerate(sequence.get('tracks',[])):
            for ci,clip in enumerate(track.get('clips',[])):
                if clip.get('tracking_binding') is None: continue
                path = f'sequences[{si}].tracks[{ti}].clips[{ci}].tracking_binding'
                try:
                    validate_binding(project,sequence,track,clip)
                    if root is not None and clip['tracking_binding']['asset_id'] not in checked_assets:
                        from .policy import resolve_local_path
                        from .utils import sha256_file
                        asset = next(a for a in project['assets'] if a['id']==clip['tracking_binding']['asset_id'])
                        file = resolve_local_path(root,asset['uri'],field='tracking_binding.source')
                        if not file.is_file() or 'sha256:'+sha256_file(file) != clip['tracking_binding']['source_sha256']:
                            raise invalid('绑定源文件与观测摘要不匹配')
                        checked_assets.add(asset['id'])
                    links[clip['id']] = [r['clip_id'] for r in source_references(clip['tracking_binding'])]
                except (AppError,ValueError,TypeError,KeyError,OSError) as exc:
                    errors.append({'code':'TRACK_BIND_GEOMETRY_INVALID','message':str(exc),'path':path})
        done = set()
        def visit(current, chain):
            if current in chain or len(chain)>=16:
                raise invalid('绑定源引用存在循环或超过16层')
            if current in done or current not in links:return
            for reference in links[current]:visit(reference, chain|{current})
            done.add(current)
        try:
            for origin in links:visit(origin,set())
        except AppError as exc:
            errors.append({'code':'TRACK_BIND_CYCLE','message':str(exc),'path':f'sequences[{si}]'})
    return errors


def bake_interchange_bindings(project: dict) -> tuple[dict,list[str]]:
    bound = [c['id'] for s in project.get('sequences',[]) for t in s.get('tracks',[]) for c in t.get('clips',[]) if c.get('tracking_binding')]
    if not bound: return project,[]
    if native_clock_project(project):
        raise AppError('TRACK_BIND_NATIVE_BAKE_REQUIRED', '原生PTS绑定须保留为可编辑工程包；当前中间格式尚未按原生帧时钟烘焙', exit_code=2)
    result = compile_project_bindings(project)
    for sequence in result['sequences']:
        for track in sequence['tracks']:
            for clip in track['clips']:
                clip.pop('tracking_binding',None)
                clip.pop('_tracking_binding_source',None)
                clip.pop('_tracking_binding_plan',None)
    return result,bound
