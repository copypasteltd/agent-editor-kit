"""Pure tick-native linked editing, adapted from OpenFilm's timeline planner.

Source: openfilm/openfilm b138595d4c2d1fa5262b4a8a8c7cd98187c4b077,
packages/openfilm/studio/ui/src/lib/timeline-edit.ts.
Copyright (c) 2026 OpenFilm contributors, MIT. The complete permission notice
is distributed in this package's OPENFILM_LICENSE.txt.

Whole clips retain their complete source clocks and automation. No millisecond
rounding, UI minimum shot length, browser, Node or media process is used here.
"""
from __future__ import annotations

import copy
from collections import Counter
import hashlib
import heapq
import json
from typing import Any

from .errors import AppError
from .utils import ID_RE

ENGINE = 'agent-tick-linked-edit-v1'
SOURCE = {
    'repository': 'openfilm/openfilm',
    'revision': 'b138595d4c2d1fa5262b4a8a8c7cd98187c4b077',
    'path': 'packages/openfilm/studio/ui/src/lib/timeline-edit.ts',
    'license': 'MIT',
    'adaptation': 'native-integer-ticks-whole-clip-follow-and-gap-planning',
}
ACTIONS = {'remove', 'close_gap', 'close_gaps', 'shift', 'link', 'unlink'}


def _error(code: str, message: str, path: str = 'edit') -> None:
    raise AppError(code, message, exit_code=2, path=path)


def _integer(value: Any, path: str, minimum: int | None = None) -> int:
    if type(value) is not int or (minimum is not None and value < minimum):
        _error('EDIT_REQUEST_INVALID', '编辑 tick 必须为范围内的整数，不能是布尔或浮点数', path)
    return value


def _identifier(value: Any, path: str) -> str:
    if not isinstance(value, str) or not ID_RE.fullmatch(value):
        _error('EDIT_REQUEST_INVALID', '编辑标识符无效', path)
    return value


def project_fingerprint(project: dict[str, Any]) -> str:
    raw = json.dumps(project, sort_keys=True, ensure_ascii=False, separators=(',', ':'), allow_nan=False).encode('utf-8')
    return 'sha256:' + hashlib.sha256(raw).hexdigest()


def validate_editing(sequence: dict[str, Any]) -> dict[str, Any]:
    value = sequence.get('editing')
    if value is None:
        value = {}
    if not isinstance(value, dict) or set(value) - {'main_track_id', 'sync', 'linkage', 'linked', 'magnetic'}:
        _error('EDIT_CONFIGURATION_INVALID', 'sequence.editing 只允许 main_track_id/sync/linkage/linked/magnetic', 'sequence.editing')
    for key in ('sync', 'linkage', 'linked', 'magnetic'):
        if key in value and type(value[key]) is not bool:
            _error('EDIT_CONFIGURATION_INVALID', 'editing 开关必须是布尔值', 'sequence.editing.' + key)
    tracks = sequence.get('tracks', [])
    main = value.get('main_track_id')
    if 'main_track_id' in value:
        if not isinstance(main, str) or not any(t.get('id') == main and t.get('kind') == 'video' for t in tracks):
            _error('EDIT_CONFIGURATION_INVALID', 'main_track_id 必须引用本序列 video 轨道', 'sequence.editing.main_track_id')
    else:
        pictures = [t for t in tracks if t.get('kind') == 'video']
        if pictures:
            main = min(pictures, key=lambda t: (t.get('order') if type(t.get('order')) is int else 0, str(t.get('id', ''))))['id']
    return {'main_track_id': main, 'sync': value.get('sync', value.get('magnetic', False)),
            'linkage': value.get('linkage', False), 'linked': value.get('linked', True),
            'magnetic': value.get('magnetic', False)}


def normalize_request(sequence: dict[str, Any], request: Any) -> dict[str, Any]:
    if not isinstance(request, dict) or set(request) - {'action', 'clip_ids', 'track_id', 'at_tick', 'delta_tick', 'options', 'link_id'}:
        _error('EDIT_REQUEST_INVALID', '编辑请求必须为已知字段组成的对象')
    action = request.get('action')
    if not isinstance(action, str) or action not in ACTIONS:
        _error('EDIT_REQUEST_INVALID', '编辑 action 不支持', 'edit.action')
    raw_options = request.get('options', {})
    if not isinstance(raw_options, dict) or set(raw_options) - {'sync', 'linkage', 'linked', 'ripple'}:
        _error('EDIT_REQUEST_INVALID', 'options 只允许 sync/linkage/linked/ripple', 'edit.options')
    options = validate_editing(sequence)
    for key in ('sync', 'linkage', 'linked'):
        if key in raw_options:
            if type(raw_options[key]) is not bool:
                _error('EDIT_REQUEST_INVALID', 'options 开关必须为布尔值', 'edit.options.' + key)
            options[key] = raw_options[key]
    ripple = raw_options.get('ripple', False)
    if type(ripple) is not bool and ripple != 'main':
        _error('EDIT_REQUEST_INVALID', 'ripple 只允许 true/false 或 main', 'edit.options.ripple')
    options['ripple'] = ripple
    out: dict[str, Any] = {'action': action, 'options': options}
    allowed = {'action', 'options'}
    if action in {'remove', 'shift', 'link', 'unlink'}:
        allowed.add('clip_ids')
        ids = request.get('clip_ids')
        if not isinstance(ids, list) or not ids:
            _error('EDIT_REQUEST_INVALID', 'clip_ids 必须为非空数组', 'edit.clip_ids')
        ids = [_identifier(item, 'edit.clip_ids') for item in ids]
        if len(set(ids)) != len(ids):
            _error('EDIT_REQUEST_INVALID', 'clip_ids 不能重复', 'edit.clip_ids')
        out['clip_ids'] = ids
    if action in {'close_gap', 'close_gaps'}:
        allowed.add('track_id')
        track_id = request['track_id'] if 'track_id' in request else options['main_track_id']
        out['track_id'] = _identifier(track_id, 'edit.track_id')
    if action == 'close_gap':
        allowed.add('at_tick')
        out['at_tick'] = _integer(request.get('at_tick'), 'edit.at_tick', 0)
    if action == 'shift':
        allowed.add('delta_tick')
        out['delta_tick'] = _integer(request.get('delta_tick'), 'edit.delta_tick')
    if action == 'link':
        allowed.add('link_id')
        if 'link_id' in request:
            out['link_id'] = _identifier(request['link_id'], 'edit.link_id')
    if set(request) - allowed:
        _error('EDIT_REQUEST_INVALID', '该 action 不接受这些字段: ' + ','.join(sorted(set(request) - allowed)))
    return out


def _start(clip):
    return clip['timeline_start_tick']


def _end(clip):
    return _start(clip) + clip['duration_tick']


def _overlap(a, b):
    return _start(a) < _end(b) and _end(a) > _start(b)


def _merge(spans):
    out = []
    for a, b in sorted(spans):
        if b <= a:
            continue
        if out and a <= out[-1][1]:
            out[-1] = (out[-1][0], max(b, out[-1][1]))
        else:
            out.append((a, b))
    return out


def _host(main, clip):
    for item in main['clips']:
        if _start(item) <= _start(clip) < _end(item):
            return item['id']
    last = max(main['clips'], key=lambda c: (_end(c), c['id']), default=None)
    return last['id'] if last is not None and _start(clip) >= _end(last) else None


def _rides(main, clip):
    if _host(main, clip) is None:
        return False
    cuts = {_start(c) for c in main['clips']} | {_end(c) for c in main['clips']}
    return sum(_start(clip) < cut < _end(clip) for cut in cuts) <= 1


def _content(clip):
    out = copy.deepcopy({key: value for key, value in clip.items() if key not in {'timeline_start_tick', 'link_id'}})
    if isinstance(out.get('subtitle'), dict):
        out['subtitle'].pop('asset_time_offset_tick', None)
        if not out['subtitle']:
            out.pop('subtitle')
    return out


def interchange_features(project):
    """Native authoring semantics that external formats do not implement."""
    features = []
    if any('sequence_clip_id' in c for s in project['sequences'] for t in s['tracks'] for c in t['clips']):
        features.append('clip.sequence_clip_id')
    if any(isinstance(c.get('blend'), dict) and 'opacity_animation' in c['blend']
           for s in project['sequences'] for t in s['tracks'] for c in t['clips']):
        features.append('blend.opacity_animation')
    if any(c.get('presentation_window') is not None for s in project['sequences'] for t in s['tracks'] for c in t['clips']):
        features.append('clip.presentation_window')
    if any(s.get('source_transitions') for s in project['sequences']):
        features.append('sequence.source_transitions')
    if any(s.get('editing') is not None for s in project['sequences']):
        features.append('sequence.editing')
    if any(s.get('audio_routing') is not None for s in project['sequences']):
        features.append('sequence.audio_routing')
    if any('sync_lock' in t for s in project['sequences'] for t in s['tracks']):
        features.append('track.sync_lock')
    if any(c.get('link_id') is not None for s in project['sequences'] for t in s['tracks'] for c in t['clips']):
        features.append('clip.link_id')
    if any(c.get('subtitle', {}).get('asset_time_offset_tick', 0) for s in project['sequences'] for t in s['tracks'] for c in t['clips'] if isinstance(c.get('subtitle', {}), dict)):
        features.append('subtitle.asset_time_offset_tick')
    return features


class _Draft:
    def __init__(self, project, sequence, request, *, compute_anchors=True):
        self.project = project
        self.sequence = sequence
        self.request = request
        self.original_tracks = copy.deepcopy(sequence['tracks'])
        self.before = {c['id']: (t, c) for t in self.original_tracks for c in t['clips']}
        self.original_order = [t['id'] for t in sequence['tracks']]
        self.main_id = request['options']['main_track_id']
        self.main = next((copy.deepcopy(t) for t in sequence['tracks'] if t['id'] == self.main_id), None)
        self.anchored = ({c['id'] for t in sequence['tracks'] if t['id'] != self.main_id for c in t['clips']
                         if self.main is None or not _rides(self.main, c)} if compute_anchors else set())
        self.short = 0
        self.shifts = []
        self.settle_needed = False
        self.new_tracks = []
        self.rebound = []
        self.retimed_subtitles = []
        self.selected = []
        self.used = {obj['id'] for seq in project['sequences'] for obj in [seq, *seq['tracks'],
                     *(c for t in seq['tracks'] for c in t['clips'])]}
        self.used.update(a['id'] for a in project.get('assets', []))
        self.used.update(m['id'] for s in project['sequences'] for m in s.get('markers', []) if 'id' in m)

    def track(self, track_id):
        result = next((t for t in self.sequence['tracks'] if t['id'] == track_id), None)
        if result is None:
            _error('EDIT_TRACK_NOT_FOUND', '找不到轨道: ' + str(track_id), 'edit.track_id')
        return result

    def unlocked(self, ids):
        for clip_id in ids:
            if clip_id not in self.before:
                _error('EDIT_CLIP_NOT_FOUND', '找不到片段: ' + clip_id, 'edit.clip_ids')
            if self.before[clip_id][0].get('locked', False):
                _error('EDIT_TRACK_LOCKED', '关联选择涉及锁定轨道: ' + self.before[clip_id][0]['id'], 'edit.clip_ids')

    def expand(self, ids):
        links = {self.before[c][1].get('link_id') for c in ids if c in self.before} - {None}
        return list(dict.fromkeys([*ids, *(cid for cid, (_, c) in self.before.items() if c.get('link_id') in links)]))

    def follow(self, own):
        own = {t for t in own if not self.track(t).get('locked', False)}
        opts = self.request['options']
        if opts['sync']:
            reached = {t['id'] for t in self.sequence['tracks'] if not t.get('locked', False)
                       and (t['id'] in own or t.get('sync_lock', True))}
            return reached, reached
        if opts['linkage'] and self.main_id in own:
            return {t['id'] for t in self.sequence['tracks'] if not t.get('locked', False)}, own
        return own, own

    def ripple(self, point, amount, reached, bound):
        rows = [t for t in self.sequence['tracks'] if t['id'] in reached and not t.get('locked', False)]
        if amount < 0:
            room = None
            for track in rows:
                if track['id'] not in bound:
                    continue
                later = [_start(c) for c in track['clips'] if _start(c) >= point]
                if later:
                    floor = max([0, *(_end(c) for c in track['clips'] if _start(c) < point)])
                    available = max(0, min(later) - floor)
                    room = available if room is None else min(room, available)
            if room is not None and -amount > room:
                self.short += -amount - room
                amount = -room
        if amount == 0:
            return
        if reached != bound:
            self.settle_needed = True
        changed = []
        for track in rows:
            for clip in track['clips']:
                if _start(clip) >= point and (track['id'] in bound or clip['id'] not in self.anchored):
                    clip['timeline_start_tick'] += amount
                    if _start(clip) < 0:
                        _error('EDIT_NEGATIVE_TIME', '联动会把片段移至负时间: ' + clip['id'])
                    changed.append(clip['id'])
        self.shifts.append({'point_tick': point, 'delta_tick': amount, 'track_ids': sorted(reached), 'clip_ids': changed})

    def close(self, by_track):
        opts = self.request['options']
        if opts['sync']:
            reached, bound = self.follow(by_track)
            groups = [(sum(by_track.values(), []), reached, bound)]
        elif opts['linkage'] and self.main_id in by_track:
            reached, bound = self.follow([self.main_id])
            groups = [(by_track[self.main_id], reached, bound)]
        else:
            groups = [(spans, {tid}, {tid}) for tid, spans in by_track.items()]
        for spans, reached, bound in groups:
            for a, b in reversed(_merge(spans)):
                self.ripple(b, a - b, reached, bound)

    @staticmethod
    def processing(track):
        return {'kind': track['kind'], 'muted': bool(track.get('muted', False)), 'audio': track.get('audio', {})}

    def fresh(self, base):
        stem = base[:80]
        value = stem
        index = 2
        while value in self.used:
            value = f'{stem}_{index}'
            index += 1
        self.used.add(value)
        return value

    def relocate(self, source, clip):
        if source['kind'] == 'audio' and (source.get('audio', {}).get('effects') or source.get('audio', {}).get('duck_under_voice')):
            _error('EDIT_AUDIO_BUS_RELOCATION_UNSUPPORTED', '自动换轨会改变有轨道效果或闪避处理的音频总线，请先明确安排轨道')
        routing = self.sequence.get('audio_routing')
        rows = routing.get('tracks', []) if isinstance(routing, dict) else []
        def route_signature(track):
            return {k: v for row in rows if row['track_id'] == track['id'] for k, v in row.items() if k != 'track_id'}
        route = route_signature(source)
        named_detectors = set()
        if routing is not None:
            # A new lane cannot replace one nonlinear processor or one named
            # track detector with two independent states. Shared bus FX remain
            # safe: cloned linear sends still meet at that single bus.
            tone = {'denoise', 'noise_reduction', 'compressor', 'equalizer', 'eq', 'highpass', 'lowpass',
                    'dialogue_enhance', 'voice_enhance', 'pitch_semitones', 'reverb', 'loudnorm'}
            detectors = [row.get('sidechain', {}) for row in rows+list(routing.get('buses', []))+[routing.get('master', {})]]
            named_detectors = {d['track_id'] for d in detectors if 'track_id' in d}
            if route.get('sidechain') is not None or any(source.get('audio', {}).get(k) for k in tone) or any(d.get('track_id') == source['id'] for d in detectors):
                _error('EDIT_AUDIO_BUS_RELOCATION_UNSUPPORTED', '自动换轨不能拆分命名检测源、轨道侧链或音色处理状态；请先明确安排轨道')
        candidates = [t for t in self.sequence['tracks'] if t is not source and t['id'] != self.main_id
                      and not t.get('locked', False) and self.processing(t) == self.processing(source)
                      and route_signature(t) == route
                      and t['id'] not in named_detectors
                      and not any(_overlap(clip, c) for c in t['clips'])]
        candidates.sort(key=lambda t: (abs(t['order'] - source['order']), -t['order'], t['id']))
        if candidates:
            target = candidates[0]
        else:
            target = copy.deepcopy(source)
            target.update(id=self.fresh('edit_lane_' + source['id']),
                          order=max([t['order'] for t in self.sequence['tracks']], default=-1) + 1,
                          clips=[], locked=False)
            self.sequence['tracks'].append(target)
            if route:
                routing.setdefault('tracks', []).append({'track_id': target['id'], **copy.deepcopy(route)})
            self.new_tracks.append(target['id'])
        target['clips'].append(clip)

    def settle(self):
        def moved(clip, track):
            old_track, old_clip = self.before[clip['id']]
            return old_track['id'] != track['id'] or _start(old_clip) != _start(clip)
        for track in list(self.sequence['tracks']):
            if track['id'] == self.main_id or track.get('locked', False):
                continue
            kept = []
            for clip in sorted(list(track['clips']), key=lambda c: (_start(c), c['id'])):
                hits = [c for c in kept if _overlap(c, clip)]
                if not hits or (not moved(clip, track) and not any(moved(c, track) for c in hits)):
                    kept.append(clip)
                    continue
                go = [clip] if moved(clip, track) or any(not moved(c, track) for c in hits) else hits
                for item in go:
                    if not moved(item, track):
                        _error('EDIT_PREEXISTING_OVERLAP', '原轨道存在重叠，请先明确整理重叠区间: ' + track['id'])
                    track['clips'].remove(item)
                    if item in kept:
                        kept.remove(item)
                    self.relocate(track, item)
                if clip not in go:
                    kept.append(clip)

    def repair_bindings(self):
        from .bindings import native_clock_project
        if native_clock_project(self.project):
            from .binding_edits import replan
            changes=replan(self.project,self.sequence,{**self.sequence,'tracks':self.original_tracks},
                {cid:cid for cid in self.before})
            self.rebound.extend(c['clip_id'] for c in changes)
            return
        now = {c['id']: t['id'] for t in self.sequence['tracks'] for c in t['clips']}
        for seq in self.project['sequences']:
            for track in seq['tracks']:
                for clip in track['clips']:
                    binding = clip.get('tracking_binding')
                    if not isinstance(binding, dict) or binding.get('source_clip_id') not in self.before:
                        continue
                    source_id = binding['source_clip_id']
                    if source_id not in now:
                        _error('EDIT_BINDING_SOURCE_REMOVED', '删除后仍有跟踪绑定引用该源片段: ' + source_id)
                    if now[source_id] != binding.get('source_track_id'):
                        if track.get('locked', False):
                            _error('EDIT_BOUND_REFERENCE_LOCKED', '源轨道变化需要更新锁定轨道上的绑定: ' + clip['id'])
                        binding['source_track_id'] = now[source_id]
                        self.rebound.append(clip['id'])

    def retime_subtitles(self):
        assets = {a['id']: a for a in self.project.get('assets', [])}
        for track in self.sequence['tracks']:
            for clip in track['clips']:
                old = self.before[clip['id']][1]
                delta = _start(clip) - _start(old)
                subtitle = clip.get('subtitle', {})
                external = assets.get(clip.get('asset_id'), {}).get('kind') == 'subtitle' or bool(subtitle.get('asset_uri'))
                if delta and external and not clip.get('presentation_window') and subtitle.get('asset_time_base', 'sequence') == 'sequence':
                    clip.setdefault('subtitle', {})['asset_time_offset_tick'] = subtitle.get('asset_time_offset_tick', 0) - delta
                    self.retimed_subtitles.append(clip['id'])


def _gaps(track):
    end = 0
    out = []
    for clip in sorted(track['clips'], key=lambda c: (_start(c), c['id'])):
        if _start(clip) > end:
            out.append((end, _start(clip)))
        end = max(end, _end(clip))
    return out


def _plan_changes(before, after):
    old = {c['id']: (t['id'], c) for t in before['tracks'] for c in t['clips']}
    new = {c['id']: (t['id'], c) for t in after['tracks'] for c in t['clips']}
    changes = []
    for cid, (tid, clip) in old.items():
        current = new.get(cid)
        if current is None:
            changes.append({'clip_id': cid, 'before': {'track_id': tid, 'clip': clip}, 'after': None})
        elif tid != current[0] or clip != current[1]:
            changes.append({'clip_id': cid, 'before': {'track_id': tid, 'clip': clip},
                            'after': {'track_id': current[0], 'clip': current[1]}})
    changes.extend({'clip_id': cid, 'before': None, 'after': {'track_id': tid, 'clip': clip}}
                   for cid, (tid, clip) in new.items() if cid not in old)
    return changes


def build_edit_plan(project: dict[str, Any], sequence_id: str, request: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return an isolated candidate plus a reviewable plan; never mutate input."""
    if isinstance(request, dict) and request.get('action') == 'retime':
        from .retime_edits import build_retime_plan
        return build_retime_plan(project, sequence_id, request)
    from .magnetic_mode import maybe_plan
    magnetic = maybe_plan(project, sequence_id, request)
    if magnetic is not None:
        return magnetic
    if isinstance(request, dict) and isinstance(request.get('action'), str):
        if request['action'] == 'reorder':
            from .magnetic_reorder import build_reorder_plan
            return build_reorder_plan(project, sequence_id, request)
        from .range_edits import ACTIONS as RANGE_ACTIONS, build_range_plan
        if request['action'] in RANGE_ACTIONS:
            return build_range_plan(project, sequence_id, request)
    candidate = copy.deepcopy(project)
    sequence = next((s for s in candidate['sequences'] if s['id'] == sequence_id), None)
    if sequence is None:
        _error('EDIT_SEQUENCE_NOT_FOUND', '找不到编辑序列: ' + sequence_id, 'sequence_id')
    original = copy.deepcopy(sequence)
    normalized = normalize_request(sequence, request)
    draft = _Draft(candidate, sequence, normalized)
    action = normalized['action']
    options = normalized['options']
    selected = normalized.get('clip_ids', [])
    draft.unlocked(selected)
    if action not in {'link', 'unlink'} and options['linked']:
        selected = draft.expand(selected)
        draft.unlocked(selected)
    if action == 'link':
        selected = draft.expand(selected)
        draft.unlocked(selected)
        if len(selected) < 2:
            _error('EDIT_LINK_SELECTION_TOO_SMALL', '建立关联至少需要两个片段', 'edit.clip_ids')
        used = {c.get('link_id') for _, c in draft.before.values()} - {None}
        link = normalized.get('link_id') or next((draft.before[c][1]['link_id'] for c in selected if draft.before[c][1].get('link_id')), None)
        if link is None:
            base = ('link_' + selected[0])[:80]
            link, index = base, 2
            while link in used:
                link = f'{base}_{index}'
                index += 1
        if any(c.get('link_id') == link and cid not in selected for cid, (_, c) in draft.before.items()):
            _error('EDIT_LINK_ID_CONFLICT', 'link_id 已由未选择片段使用', 'edit.link_id')
        for track in sequence['tracks']:
            for clip in track['clips']:
                if clip['id'] in selected:
                    clip['link_id'] = link
    elif action == 'unlink':
        gone = set(selected)
        for link in {draft.before[c][1].get('link_id') for c in selected} - {None}:
            left = [cid for cid, (_, c) in draft.before.items() if c.get('link_id') == link and cid not in gone]
            if len(left) == 1:
                gone.add(left[0])
        selected = list(dict.fromkeys([*selected, *sorted(gone)]))
        draft.unlocked(selected)
        for track in sequence['tracks']:
            for clip in track['clips']:
                if clip['id'] in gone:
                    clip.pop('link_id', None)
    elif action == 'remove':
        if options['linkage'] and not options['sync'] and draft.main and not draft.main.get('locked', False):
            while True:
                gone = {cid for cid in selected if draft.before[cid][0]['id'] == draft.main_id}
                riders = [cid for cid, (t, c) in draft.before.items() if t['id'] != draft.main_id and not t.get('locked', False)
                          and _rides(draft.main, c) and _host(draft.main, c) in gone]
                expanded = list(dict.fromkeys([*selected, *riders]))
                if options['linked']:
                    expanded = draft.expand(expanded)
                draft.unlocked(expanded)
                if set(expanded) == set(selected):
                    break
                selected = expanded
        spans = {}
        for track in sequence['tracks']:
            removed = [c for c in track['clips'] if c['id'] in selected]
            track['clips'] = [c for c in track['clips'] if c['id'] not in selected]
            if removed and options['ripple'] and (options['ripple'] is True or track['id'] == draft.main_id):
                spans[track['id']] = [(_start(c), _end(c)) for c in removed]
        if spans:
            draft.close(spans)
    elif action in {'close_gap', 'close_gaps'}:
        track = draft.track(normalized['track_id'])
        if track.get('locked', False):
            _error('EDIT_TRACK_LOCKED', '锁定轨道不能闭合空隙', 'edit.track_id')
        spans = _gaps(track)
        if action == 'close_gap':
            at = normalized['at_tick']
            spans = [(a, b) for a, b in spans if a <= at < b]
            if not spans:
                _error('EDIT_GAP_NOT_FOUND', '指定 tick 不位于可闭合空隙内', 'edit.at_tick')
        draft.close({track['id']: spans})
    elif action == 'shift':
        if options['linkage'] and not options['sync'] and draft.main:
            hosts = {cid for cid in selected if draft.before[cid][0]['id'] == draft.main_id}
            selected = list(dict.fromkeys([*selected, *(cid for cid, (t, c) in draft.before.items()
                if t['id'] != draft.main_id and not t.get('locked', False) and _rides(draft.main, c) and _host(draft.main, c) in hosts)]))
            if options['linked']:
                selected = draft.expand(selected)
            draft.unlocked(selected)
        delta = normalized['delta_tick']
        for track in sequence['tracks']:
            for clip in track['clips']:
                if clip['id'] in selected:
                    clip['timeline_start_tick'] += delta
                    if _start(clip) < 0:
                        _error('EDIT_NEGATIVE_TIME', '移位不能到负时间', 'edit.delta_tick')
        draft.settle_needed = delta != 0
    draft.selected = selected
    if draft.settle_needed:
        draft.settle()
    main = next((t for t in sequence['tracks'] if t['id'] == draft.main_id), None)
    if main is not None:
        ordered = sorted(main['clips'], key=lambda c: (_start(c), c['id']))
        active, counts = [], Counter()
        for clip in ordered:
            while active and active[0][0] <= _start(clip):
                _, old_delta, _ = heapq.heappop(active)
                counts[old_delta] -= 1
                if not counts[old_delta]:
                    del counts[old_delta]
            delta = _start(clip) - _start(draft.before[clip['id']][1])
            if counts and (len(counts) != 1 or delta not in counts):
                _error('EDIT_MAIN_TRACK_COLLISION', '主轨整片段移位发生碰撞；本命令不会隐式覆盖或裁切片段')
            heapq.heappush(active, (_end(clip), delta, clip['id']))
            counts[delta] += 1
    draft.repair_bindings()
    draft.retime_subtitles()
    # A locked track and every surviving clip's media/animation payload stay
    # equivalent as JSON values, apart from binding references and cue offsets.
    after_clips = {c['id']: c for t in sequence['tracks'] for c in t['clips']}
    for track in draft.original_tracks:
        if track.get('locked', False) and draft.track(track['id']) != track:
            _error('EDIT_LOCK_INVARIANT_FAILED', '编辑不能改变锁定轨道')
    for cid, (_, old_clip) in draft.before.items():
        if cid in after_clips and cid not in draft.rebound and _content(old_clip) != _content(after_clips[cid]):
            _error('EDIT_CONTENT_INVARIANT_FAILED', '整片段编辑不能重写源时钟或动画')
    changes = _plan_changes(original, sequence)
    if changes and action not in {'link', 'unlink'}:
        sequence['duration_tick'] = max([1, *(_end(c) for t in sequence['tracks'] for c in t['clips'])])
    plan = {'engine': ENGINE, 'source': SOURCE, 'base_project_sha256': project_fingerprint(project),
            'sequence_id': sequence_id, 'request': normalized, 'selected_clip_ids': selected,
            'main_track_id': draft.main_id, 'anchored_clip_ids': sorted(draft.anchored),
            'short_tick': draft.short, 'shifts': draft.shifts, 'changes': changes,
            'new_track_ids': draft.new_tracks, 'rebound_clip_ids': draft.rebound,
            'retimed_subtitle_ids': draft.retimed_subtitles,
            'new_tracks': [copy.deepcopy(t) for t in sequence['tracks'] if t['id'] in draft.new_tracks],
            'before_duration_tick': original['duration_tick'], 'after_duration_tick': sequence['duration_tick'],
            'limits': ['whole-clip-edits-no-source-trim-or-insert-overwrite',
                       'markers-remain-at-absolute-sequence-ticks',
                       'new-collision-lanes-above-existing-order-and-preserve-track-processing',
                       'sync-conflicts-report-short-tick-never-fall-back-to-one-track']}
    return candidate, plan
