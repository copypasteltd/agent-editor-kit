"""Deterministic, editable ad variants and scoped revision plans.

The caller supplies the actual creative decisions and local assets. This module
does not invent claims, silently stretch speech, or infer footage semantics.
"""
from __future__ import annotations

import copy
from fractions import Fraction
import hashlib
import json
import re
from typing import Any

from .edit_planner import project_fingerprint
from .errors import AppError
from .project import asset_map, find_sequence
from .sequence_canvas import validate_canvas, validate_output_alignment
from .utils import ID_RE


ENGINE = 'agent-ad-storyboard-v1'
FORMAT = 'agent-ad-storyboard-plan-v1'
SHOT_FIELDS = {'id', 'asset_id', 'source_in_tick', 'weight', 'text', 'fit', 'voice',
               'include_source_audio', 'source_gain_db', 'rationale'}
PATCH_FIELDS = SHOT_FIELDS - {'id', 'weight', 'rationale'}


def fail(message, path=None, code='AD_STORYBOARD_INVALID'):
    raise AppError(code, message, exit_code=2, path=path)


def obj(value, allowed, path):
    if not isinstance(value, dict) or set(value) - allowed:
        fail('必须为仅含已知字段的对象', path)
    return value


def identifier(value, path):
    if not isinstance(value, str) or len(value) > 32 or not ID_RE.fullmatch(value):
        fail('ID 必须为 1..32 个合法字符', path)
    return value


def number(value, path, low, high):
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        fail('数值类型无效', path)
    try:
        result = Fraction(str(value))
    except (ValueError, ZeroDivisionError):
        fail('数值必须有限', path)
    if not low <= result <= high:
        fail(f'数值必须在 {low}..{high} 内', path)
    return result


def integer(value, path, minimum=0):
    if type(value) is not int or value < minimum:
        fail('必须为范围内的整数', path)
    return value


def text(value, path, limit=2000):
    if not isinstance(value, str) or len(value) > limit or '\x00' in value:
        fail('文本类型、长度或字符无效', path)
    return value


def digest(value):
    try:
        raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')
    except (TypeError, ValueError, UnicodeError):
        fail('计划必须是有限数值和有效 Unicode 组成的 JSON', 'input')
    return 'sha256:' + hashlib.sha256(raw).hexdigest()


def _id(campaign, variant, role, shot=''):
    return '_'.join(p for p in ('ad', campaign, variant, role, shot) if p)


def _asset(assets, asset_id, kinds, path):
    if not isinstance(asset_id, str) or asset_id not in assets or assets[asset_id]['kind'] not in kinds:
        fail('必须引用已导入且类型匹配的本地资产', path)
    return assets[asset_id]


def _span(asset, start, duration, path):
    integer(start, path + '.source_in_tick')
    end = start + duration
    if asset['kind'] != 'image':
        total = asset.get('probe', {}).get('duration_tick', 0)
        if type(total) is not int or total <= 0 or end > total:
            fail('素材长度不足；请明确改用其他片段或调整变体时长', path, 'AD_SOURCE_TOO_SHORT')
    return start, end


def _tag(clip, shot, role):
    clip['ad_storyboard'] = {'shot_id': shot, 'role': role}
    return clip


def _clip(clip_id, start, duration, source_in=0):
    return dict(id=clip_id, timeline_start_tick=start, duration_tick=duration,
                source_in_tick=source_in, source_out_tick=source_in + duration)


def _caption_style(raw, canvas, assets):
    obj(raw, {'font_asset_id', 'font_ratio', 'fontcolor', 'bordercolor', 'safe_margin_ratio'}, 'caption_style')
    font = raw.get('font_asset_id')
    _asset(assets, font, {'font'}, 'caption_style.font_asset_id')
    ratio = number(raw.get('font_ratio', .045), 'caption_style.font_ratio', .01, .12)
    margin = number(raw.get('safe_margin_ratio', .08), 'caption_style.safe_margin_ratio', .03, .3)
    for key in ('fontcolor', 'bordercolor'):
        if key in raw and (not isinstance(raw[key], str) or not re.fullmatch(r'#[0-9a-fA-F]{6}|[A-Za-z]+', raw[key])):
            fail('颜色必须为 #RRGGBB 或具名颜色', 'caption_style.' + key)
    size = max(8, round(canvas['height'] * ratio))
    return dict(font_asset_id=font, fontsize=size, fontcolor=raw.get('fontcolor', 'white'),
                bordercolor=raw.get('bordercolor', 'black'), borderw=max(1, round(size / 24)),
                x='(w-text_w)/2', y=f'h-text_h-{round(canvas["height"] * margin)}',
                max_width=round(canvas['width'] * (1 - 2 * margin)), expansion='none')


def _voice(spec, assets, start, duration, clip_id, shot):
    obj(spec, {'asset_id', 'source_in_tick', 'source_out_tick', 'gain_db'}, 'voice')
    asset = _asset(assets, spec.get('asset_id'), {'audio'}, 'voice.asset_id')
    source_in = integer(spec.get('source_in_tick', 0), 'voice.source_in_tick')
    source_out = integer(spec.get('source_out_tick', asset['probe'].get('duration_tick', 0)), 'voice.source_out_tick', 1)
    length = source_out - source_in
    if length <= 0 or length > duration:
        fail('完整声音必须放入镜头窗口；本命令不裁短或变速台词', 'voice', 'AD_VOICE_OUT_OF_WINDOW')
    _span(asset, source_in, length, 'voice')
    gain = float(number(spec.get('gain_db', 0), 'voice.gain_db', -96, 24))
    return _tag({**_clip(clip_id, start, length, source_in), 'asset_id': asset['id'], 'audio': {'gain_db': gain}}, shot, 'voice')


def _shot_parts(spec, assets, start, duration, campaign, variant, style):
    obj(spec, SHOT_FIELDS, 'shots[]')
    shot = identifier(spec.get('id'), 'shots[].id')
    asset = _asset(assets, spec.get('asset_id'), {'video', 'image'}, 'shots[].asset_id')
    source_in, source_out = _span(asset, spec.get('source_in_tick', 0), duration, 'shots[]')
    fit = spec.get('fit', 'fit')
    if fit not in ('fit', 'fill', 'stretch'):
        fail('fit 必须为 fit/fill/stretch', 'shots[].fit')
    include_audio = spec.get('include_source_audio', False)
    if type(include_audio) is not bool:
        fail('include_source_audio 必须为布尔值', 'shots[].include_source_audio')
    source_gain = float(number(spec.get('source_gain_db', 0), 'source_gain_db', -96, 24))
    picture = _tag({**_clip(_id(campaign, variant, 'picture', shot), start, duration, source_in),
                    'asset_id': asset['id'], 'crop': {'fit': fit}}, shot, 'picture')
    caption = None
    copy_text = text(spec.get('text', ''), 'shots[].text')
    if copy_text:
        caption = _tag({**_clip(_id(campaign, variant, 'caption', shot), start, duration),
                        'generator': {'type': 'text'}, 'subtitle': {'text': copy_text, 'style': copy.deepcopy(style)}}, shot, 'caption')
    voice = _voice(spec['voice'], assets, start, duration, _id(campaign, variant, 'voice', shot), shot) if spec.get('voice') is not None else None
    source_audio = None
    if include_audio:
        if not asset.get('probe', {}).get('audio', {}).get('codec'):
            fail('要求源音但素材没有已探测音轨', 'include_source_audio')
        source_audio = _tag({**_clip(_id(campaign, variant, 'source', shot), start, duration, source_in),
                             'asset_id': asset['id'], 'audio': {'gain_db': source_gain}}, shot, 'source_audio')
    return {'picture': picture, 'caption': caption, 'voice': voice, 'source_audio': source_audio}


def _track(track_id, kind, order):
    return dict(id=track_id, kind=kind, order=order, muted=False, locked=False, clips=[])


def _frames(total, weights):
    if total < len(weights):
        fail('变体帧数不足以给每个镜头分配一帧', 'variants.duration_seconds')
    remaining = total - len(weights)
    exact = [remaining * weight / sum(weights) for weight in weights]
    counts = [1 + item.numerator // item.denominator for item in exact]
    order = sorted(range(len(weights)), key=lambda i: (-(exact[i] % 1), i))
    for i in order[:total - sum(counts)]:
        counts[i] += 1
    return counts


def _finish(project, kind, request, sequences, warnings):
    ids = set()
    for sequence in sequences:
        for track in sequence['tracks']:
            for clip in track['clips']:
                if clip.get('asset_id'):
                    ids.add(clip['asset_id'])
                font = clip.get('subtitle', {}).get('style', {}).get('font_asset_id')
                if font:
                    ids.add(font)
        ids.add(sequence['ad_storyboard']['caption_style']['font_asset_id'])
    assets = asset_map(project)
    plan = dict(format=FORMAT, engine=ENGINE, kind=kind, project_id=project['project']['id'],
                base_project_sha256=project_fingerprint(project), request=copy.deepcopy(request),
                asset_pins=[{'asset_id': aid, 'sha256': assets[aid]['sha256']} for aid in sorted(ids)],
                sequences=sequences, warnings=warnings)
    plan['plan_sha256'] = digest(plan)
    return plan


def plan_storyboard(project: dict, brief: Any) -> dict:
    obj(brief, {'id', 'product', 'audience', 'cta', 'shots', 'variants', 'caption_style', 'music'}, 'brief')
    campaign = identifier(brief.get('id'), 'brief.id')
    for field in ('product', 'audience', 'cta'):
        if not text(brief.get(field), 'brief.' + field).strip():
            fail('需要明确产品、受众和 CTA；不会自动编造商品承诺', 'brief.' + field)
    shots, variants = brief.get('shots'), brief.get('variants')
    if not isinstance(shots, list) or not 1 <= len(shots) <= 50 or not isinstance(variants, list) or not 1 <= len(variants) <= 30:
        fail('需要 1..50 个镜头与 1..30 个变体', 'brief')
    shot_map = {}
    for item in shots:
        obj(item, SHOT_FIELDS, 'shots[]')
        key = identifier(item.get('id'), 'shots[].id')
        if key in shot_map:
            fail('镜头 ID 重复', 'shots[].id')
        number(item.get('weight', 1), 'shots[].weight', Fraction(1, 10000), 10000)
        if 'rationale' in item:
            text(item['rationale'], 'shots[].rationale', limit=8192)
        shot_map[key] = copy.deepcopy(item)
    assets, sequences, warnings = asset_map(project), [], []
    tps = project['settings']['timebase']['ticks_per_second']
    fps_value = project['settings']['timebase']['display_fps']
    fps = Fraction(fps_value['num'], fps_value['den'])
    seen = set()
    for variant in variants:
        obj(variant, {'id', 'name', 'canvas', 'duration_seconds', 'shot_ids', 'overrides'}, 'variants[]')
        vid = identifier(variant.get('id'), 'variants[].id')
        if vid in seen:
            fail('变体 ID 重复', 'variants[].id')
        seen.add(vid)
        canvas = variant.get('canvas')
        validate_canvas(canvas, path='variants[].canvas')
        if canvas is None:
            fail('变体必须明确 canvas', 'variants[].canvas')
        validate_output_alignment(canvas, 'yuv420p')
        style = _caption_style(brief.get('caption_style'), canvas, assets)
        seconds = number(variant.get('duration_seconds'), 'variants[].duration_seconds', 3, 180)
        total_frames = round(seconds * fps)
        end_tick = round(total_frames * tps / fps)
        if Fraction(total_frames, 1) / fps != seconds:
            warnings.append(dict(code='AD_DURATION_FRAME_ALIGNED', variant_id=vid, requested_seconds=float(seconds),
                                 actual_seconds=float(Fraction(total_frames, 1) / fps), frames=total_frames))
        selected = variant.get('shot_ids', list(shot_map))
        if not isinstance(selected, list) or not selected or any(not isinstance(s, str) for s in selected) or len(selected) != len(set(selected)) or any(s not in shot_map for s in selected):
            fail('shot_ids 必须为不重复的已有镜头 ID', 'variants[].shot_ids')
        overrides = variant.get('overrides', {})
        if not isinstance(overrides, dict) or set(overrides) - set(selected):
            fail('overrides 只能修改当前变体的已选镜头', 'variants[].overrides')
        resolved = []
        for shot in selected:
            patch = obj(overrides.get(shot, {}), PATCH_FIELDS, 'variants[].overrides.' + shot)
            resolved.append({**shot_map[shot], **copy.deepcopy(patch)})
        frames = _frames(total_frames, [number(s.get('weight', 1), 'weight', Fraction(1, 10000), 10000) for s in resolved])
        sequence_id = _id(campaign, vid, 'sequence')
        if any(s['id'] == sequence_id for s in project['sequences']):
            fail('变体序列已存在；请使用局部返工或另一个 campaign ID', 'variants[].id', 'AD_VARIANT_EXISTS')
        role_kinds = [('picture', 'video', 0), ('caption', 'subtitle', 0), ('voice', 'audio', 0), ('source_audio', 'audio', 1), ('music', 'audio', 2)]
        tracks = {role: _track(_id(campaign, vid, role), kind, order) for role, kind, order in role_kinds}
        sequence = dict(id=sequence_id, name=text(variant.get('name', vid), 'variants[].name'),
                        duration_tick=end_tick, canvas=copy.deepcopy(canvas), tracks=list(tracks.values()), markers=[])
        cursor = 0
        for spec, count in zip(resolved, frames):
            start, end = round(cursor * tps / fps), round((cursor + count) * tps / fps)
            parts = _shot_parts(spec, assets, start, end - start, campaign, vid, style)
            for role, clip in parts.items():
                if clip is not None:
                    tracks[role]['clips'].append(clip)
            sequence['markers'].append(dict(id=_id(campaign, vid, 'marker', spec['id']), at_tick=start, label=spec['id']))
            cursor += count
        if brief.get('music') is not None:
            music = obj(brief['music'], {'asset_id', 'source_in_tick', 'gain_db'}, 'music')
            asset = _asset(assets, music.get('asset_id'), {'audio'}, 'music.asset_id')
            source_in, _ = _span(asset, music.get('source_in_tick', 0), end_tick, 'music')
            gain = float(number(music.get('gain_db', -24), 'music.gain_db', -96, 24))
            tracks['music']['clips'].append(_tag({**_clip(_id(campaign, vid, 'bed'), 0, end_tick, source_in),
                'asset_id': asset['id'], 'audio': {'gain_db': gain}}, '', 'music'))
        sequence['ad_storyboard'] = dict(engine=ENGINE, campaign_id=campaign, variant_id=vid, product=brief['product'],
            audience=brief['audience'], cta=brief['cta'], frames=total_frames, fps=copy.deepcopy(fps_value),
            caption_style=style, shots={s['id']: s for s in resolved}, tracks={role: track['id'] for role, track in tracks.items()})
        sequences.append(sequence)
    return _finish(project, 'create', brief, sequences, warnings)


def plan_revision(project: dict, request: Any) -> dict:
    obj(request, {'campaign_id', 'variant_ids', 'shots'}, 'revision')
    campaign = identifier(request.get('campaign_id'), 'revision.campaign_id')
    variants, changes = request.get('variant_ids'), request.get('shots')
    if not isinstance(variants, list) or not variants or any(not isinstance(v, str) for v in variants) or len(variants) != len(set(variants)):
        fail('返工必须明确不重复的目标 variant_ids', 'revision.variant_ids')
    if not isinstance(changes, list) or not changes:
        fail('返工需要非空 shots', 'revision.shots')
    patches = {}
    for change in changes:
        obj(change, PATCH_FIELDS | {'id'}, 'revision.shots[]')
        sid = identifier(change.get('id'), 'revision.shots[].id')
        if sid in patches or len(change) == 1:
            fail('返工镜头重复或没有修改字段', 'revision.shots[].id')
        patches[sid] = change
    assets, sequences = asset_map(project), []
    for vid in variants:
        identifier(vid, 'revision.variant_ids[]')
        sequence = copy.deepcopy(find_sequence(project, _id(campaign, vid, 'sequence')))
        meta = sequence.get('ad_storyboard', {})
        if meta.get('engine') != ENGINE or meta.get('campaign_id') != campaign or meta.get('variant_id') != vid:
            fail('目标不是可核对的本程序广告分镜', 'revision.variant_ids')
        by_track = {track['id']: track for track in sequence['tracks']}
        for sid, patch in patches.items():
            if sid not in meta['shots']:
                fail('目标变体不包含该镜头', sid)
            spec = {**meta['shots'][sid], **copy.deepcopy(patch)}
            picture_track = by_track.get(meta['tracks']['picture'])
            if picture_track is None:
                fail('分镜视频轨已缺失', sid, 'AD_TARGET_CHANGED')
            pictures = [c for c in picture_track['clips'] if c.get('ad_storyboard') == {'shot_id': sid, 'role': 'picture'}]
            if len(pictures) != 1:
                fail('分镜视频已拆分/移除；需要显式重新规划', sid, 'AD_TARGET_CHANGED')
            picture = pictures[0]
            # Respect manually slipped/replaced picture content unless requested.
            for field in ('asset_id', 'source_in_tick'):
                if field not in patch:
                    spec[field] = picture[field]
            if 'fit' not in patch:
                spec['fit'] = picture.get('crop', {}).get('fit', 'fit')
            affected = {'picture'} if set(patch) & {'asset_id', 'source_in_tick', 'fit'} else set()
            if 'text' in patch:
                affected.add('caption')
            if 'voice' in patch:
                affected.add('voice')
            if set(patch) & {'asset_id', 'source_in_tick', 'include_source_audio', 'source_gain_db'}:
                affected.add('source_audio')
            generate = copy.deepcopy(spec)
            if 'voice' not in affected:
                generate['voice'] = None
            if 'source_audio' not in affected:
                generate['include_source_audio'] = False
            parts = _shot_parts(generate, assets, picture['timeline_start_tick'], picture['duration_tick'], campaign, vid, meta['caption_style'])
            for role in affected:
                track = by_track.get(meta['tracks'][role])
                if track is None or track.get('locked'):
                    fail('目标轨道已缺失或锁定', role, 'AD_TARGET_LOCKED')
                found = [c for c in track['clips'] if c.get('ad_storyboard') == {'shot_id': sid, 'role': role}]
                if len(found) > 1:
                    fail('返工目标已拆分或重复；拒绝批量覆盖', sid, 'AD_TARGET_CHANGED')
                replacement = parts[role]
                if not found:
                    if replacement is not None:
                        track['clips'].append(replacement)
                    continue
                original = found[0]
                if replacement is None:
                    track['clips'].remove(original)
                elif role == 'picture':
                    if set(patch) & {'asset_id', 'source_in_tick'}:
                        for field in ('asset_id', 'source_in_tick', 'source_out_tick'):
                            original[field] = replacement[field]
                    if 'fit' in patch:
                        original.setdefault('crop', {})['fit'] = replacement['crop']['fit']
                elif role == 'caption':
                    original['subtitle']['text'] = replacement['subtitle']['text']
                else:
                    # Preserve manual effect, envelope and keyframe additions.
                    original.update({k: v for k, v in replacement.items() if k != 'audio'})
                    original.setdefault('audio', {}).update(replacement.get('audio', {}))
            meta['shots'][sid] = spec
        sequences.append(sequence)
    return _finish(project, 'revise', request, sequences, [])


def apply_plan(project: dict, plan: Any) -> dict:
    if not isinstance(plan, dict) or plan.get('format') != FORMAT or plan.get('engine') != ENGINE:
        fail('不是本版本广告分镜计划', 'input')
    expected = plan.get('plan_sha256')
    if expected != digest({k: v for k, v in plan.items() if k != 'plan_sha256'}):
        fail('计划摘要不一致；请重新规划', 'plan_sha256', 'AD_PLAN_CHANGED')
    if plan.get('project_id') != project['project']['id'] or plan.get('base_project_sha256') != project_fingerprint(project):
        fail('工程已偏离计划；请根据当前工程重新规划', 'base_project_sha256', 'AD_PROJECT_CHANGED')
    if plan.get('kind') == 'create':
        rebuilt = plan_storyboard(project, plan.get('request'))
    elif plan.get('kind') == 'revise':
        rebuilt = plan_revision(project, plan.get('request'))
    else:
        fail('计划种类无效', 'kind')
    if rebuilt != plan:
        fail('计划与实际输入重算结果不一致', 'input', 'AD_PLAN_CHANGED')
    candidate = copy.deepcopy(project)
    for sequence in rebuilt['sequences']:
        if plan['kind'] == 'create':
            candidate['sequences'].append(copy.deepcopy(sequence))
        else:
            old = find_sequence(candidate, sequence['id'])
            candidate['sequences'][candidate['sequences'].index(old)] = copy.deepcopy(sequence)
    return candidate
