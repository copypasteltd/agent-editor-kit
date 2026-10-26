"""Native range, insert/overwrite and two-sided cut planning.

The planner changes a detached project only. Clip processing stays on its
complete authored clock; retained pieces use presentation windows, never
average source ratios or a regenerated curve. No media process runs here.
"""
from __future__ import annotations

import copy

from .clip_windows import slice_clip, validate_track_transitions, validate_window
from .edit_planner import (project_fingerprint, validate_editing, _Draft,
                           _host, _rides, _overlap)
from .errors import AppError
from .utils import ID_RE

ENGINE = 'agent-range-edit-v1'
ACTIONS = {'insert', 'overwrite', 'lift', 'extract', 'roll', 'slide', 'slip', 'extend_source'}


def fail(code, message, path='edit'):
    raise AppError(code, message, exit_code=2, path=path)


def integer(value, path, minimum=None):
    if type(value) is not int or (minimum is not None and value < minimum):
        fail('EDIT_RANGE_REQUEST_INVALID', '必须为范围内的整数 tick，不能是布尔或小数', path)
    return value


def identifier(value, path):
    if not isinstance(value, str) or not ID_RE.fullmatch(value):
        fail('EDIT_RANGE_REQUEST_INVALID', '标识符无效', path)
    return value


def start(clip):
    return clip['timeline_start_tick']


def end(clip):
    return start(clip) + clip['duration_tick']


def normalize(sequence, request):
    if not isinstance(request, dict) or not isinstance(request.get('action'), str) or request['action'] not in ACTIONS:
        fail('EDIT_RANGE_REQUEST_INVALID', '范围编辑 action 无效')
    action = request['action']
    fields = {'action', 'options'} | {
        'insert': {'at_tick', 'duration_tick', 'items'},
        'overwrite': {'at_tick', 'duration_tick', 'items'},
        'lift': {'at_tick', 'duration_tick', 'track_ids'},
        'extract': {'at_tick', 'duration_tick', 'track_ids'},
        'roll': {'left_clip_id', 'right_clip_id', 'delta_tick', 'handle_policy'},
        'slide': {'clip_id', 'delta_tick', 'handle_policy'},
        'slip': {'clip_id', 'delta_source_tick'},
        'extend_source': {'clip_id', 'head_tick', 'tail_tick'},
    }[action]
    if set(request) - fields:
        fail('EDIT_RANGE_REQUEST_INVALID', '该 action 包含未知字段；未静默忽略')
    supplied = request.get('options', {})
    if not isinstance(supplied, dict) or set(supplied) - {'sync', 'linkage', 'linked'}:
        fail('EDIT_RANGE_REQUEST_INVALID', 'options 只允许 sync/linkage/linked', 'edit.options')
    options = validate_editing(sequence)
    if action in {'slip', 'extend_source'}:
        options.update(sync=False, linkage=False)
    for key, value in supplied.items():
        if type(value) is not bool:
            fail('EDIT_RANGE_REQUEST_INVALID', '编辑开关必须为布尔值', 'edit.options.' + key)
        options[key] = value
    if action in {'slip', 'extend_source'} and (options['sync'] or options['linkage']):
        fail('EDIT_RANGE_REQUEST_INVALID', '源编辑只使用 linked；sync/linkage 不能设为 true')
    result = {'action': action, 'options': options}
    if action in {'roll', 'slide'}:
        policy = request.get('handle_policy', 'retained')
        if not isinstance(policy, str) or policy not in {'retained', 'source'}:
            fail('EDIT_RANGE_REQUEST_INVALID', 'handle_policy 必须为 retained 或 source')
        result['handle_policy'] = policy
    if action in {'insert', 'overwrite', 'lift', 'extract'}:
        result['at_tick'] = integer(request.get('at_tick'), 'edit.at_tick', 0)
    if action in {'lift', 'extract'}:
        ids = request.get('track_ids')
        if not isinstance(ids, list) or not ids or len(ids) != len(set(map(str, ids))):
            fail('EDIT_RANGE_REQUEST_INVALID', 'track_ids 必须是非空、无重复的轨道数组')
        result['track_ids'] = [identifier(i, 'edit.track_ids') for i in ids]
        result['duration_tick'] = integer(request.get('duration_tick'), 'edit.duration_tick', 1)
        if result['at_tick'] + result['duration_tick'] > sequence['duration_tick']:
            fail('EDIT_RANGE_OUTSIDE_SEQUENCE', '移除范围超出序列结尾')
    elif action in {'insert', 'overwrite'}:
        items = request.get('items')
        if not isinstance(items, list) or not items or len(items) > 256:
            fail('EDIT_RANGE_REQUEST_INVALID', 'items 必须包含 1..256 个轨道/片段对象')
        result['items'] = copy.deepcopy(items)
        extent = 0
        for item in result['items']:
            if not isinstance(item, dict) or set(item) != {'track_id', 'clip'} or not isinstance(item['clip'], dict):
                fail('EDIT_RANGE_REQUEST_INVALID', '每个 item 只允许 track_id 与完整 clip')
            identifier(item['track_id'], 'edit.items.track_id')
            clip = item['clip']
            identifier(clip.get('id'), 'edit.items.clip.id')
            if clip.get('link_id') is not None:
                identifier(clip['link_id'], 'edit.items.clip.link_id')
            integer(clip.get('timeline_start_tick'), 'edit.items.clip.timeline_start_tick', 0)
            integer(clip.get('duration_tick'), 'edit.items.clip.duration_tick', 1)
            integer(clip.get('source_in_tick'), 'edit.items.clip.source_in_tick', 0)
            integer(clip.get('source_out_tick'), 'edit.items.clip.source_out_tick', 1)
            validate_window(clip)
            extent = max(extent, end(clip))
        result['duration_tick'] = integer(request.get('duration_tick', extent), 'edit.duration_tick', 1)
        if result['duration_tick'] < extent:
            fail('EDIT_RANGE_REQUEST_INVALID', '编辑范围不能短于 incoming clips 的完整相对范围')
    elif action == 'roll':
        result['left_clip_id'] = identifier(request.get('left_clip_id'), 'edit.left_clip_id')
        result['right_clip_id'] = identifier(request.get('right_clip_id'), 'edit.right_clip_id')
        result['delta_tick'] = integer(request.get('delta_tick'), 'edit.delta_tick')
    elif action == 'slide':
        result['clip_id'] = identifier(request.get('clip_id'), 'edit.clip_id')
        result['delta_tick'] = integer(request.get('delta_tick'), 'edit.delta_tick')
    elif action in {'slip', 'extend_source'}:
        result['clip_id'] = identifier(request.get('clip_id'), 'edit.clip_id')
        keys = ('delta_source_tick',) if action == 'slip' else ('head_tick', 'tail_tick')
        for key in keys:
            value = request.get(key) if action == 'slip' else request.get(key, 0)
            value = integer(value, 'edit.'+key, 0 if action == 'extend_source' else None)
            if abs(value) > 2**53-1:
                fail('EDIT_RANGE_REQUEST_INVALID', '源编辑 tick 超过可精确编译的整数时钟范围')
            result[key] = value
    return result


class RangeDraft:
    def __init__(self, project, sequence_id, request, *, temporal_options=None):
        self.project = copy.deepcopy(project)
        self.sequence = next((s for s in self.project['sequences'] if s['id'] == sequence_id), None)
        if self.sequence is None:
            fail('EDIT_SEQUENCE_NOT_FOUND', '找不到编辑序列')
        self.original = copy.deepcopy(self.sequence)
        self.request = (normalize(self.sequence, request) if temporal_options is None else
                        {'action':'retime','options':copy.deepcopy(temporal_options)})
        self.options = self.request['options']
        self.before = {c['id']: (t, c) for t in self.original['tracks'] for c in t['clips']}
        self.tracks = {t['id']: t for t in self.sequence['tracks']}
        self.assets = {a['id']: a for a in self.project.get('assets', [])}
        self.origin = {cid: cid for cid in self.before}
        self.used = {a['id'] for a in self.project.get('assets', [])}
        self.used.update(o['id'] for s in self.project['sequences'] for o in
                         [s, *s['tracks'], *(c for t in s['tracks'] for c in t['clips']),
                          *s.get('markers', []), *s.get('source_transitions', [])] if 'id' in o)
        old_links = {c.get('link_id') for s in self.project['sequences'] for t in s['tracks'] for c in t['clips']} - {None}
        self.incoming_ids = set()
        self.intentional_overlaps = set()
        items = self.request.get('items', [])
        for item in items:
            clip = item['clip']
            if clip['id'] in self.used:
                fail('EDIT_RANGE_ID_CONFLICT', 'incoming clip ID 已经存在: ' + clip['id'])
            if clip.get('link_id') in old_links:
                fail('EDIT_RANGE_LINK_CONFLICT', 'incoming link_id 不能隐式并入已有组')
            self.used.add(clip['id'])
            self.incoming_ids.add(clip['id'])
        for item in items:
            clip = item['clip']
            for other in items:
                if other is item or other['track_id'] != item['track_id'] or not _overlap(clip, other['clip']):
                    continue
                track = self.tracks.get(item['track_id'])
                if track is not None and track.get('overlap_policy') != 'allow':
                    fail('EDIT_RANGE_INCOMING_OVERLAP', '同轨 incoming clips 重叠，须明确声明 overlap_policy=allow')
                self.intentional_overlaps.add(frozenset((clip['id'], other['clip']['id'])))
        self.main = next((t for t in self.original['tracks'] if t['id'] == self.options['main_track_id']), None)
        self.changed = set()
        self.selected = set()
        self.retimed = set()
        self.rebound = set()
        self.new_tracks = []
        self.removed_transitions = []
        self.cut_pairs = []
        self.source_changes = []
        self.old_duration = self.sequence['duration_tick']
        from .bindings import native_clock_project, source_references
        self.native_tracking = native_clock_project(self.project)
        self.binding_changes = []
        self.protected = {c['id'] for s in self.project['sequences'] for t in s['tracks'] for c in t['clips'] if c.get('tracking_binding')}
        self.protected.update(r['clip_id'] for s in self.project['sequences']
            for t in s['tracks'] for c in t['clips'] if c.get('tracking_binding') for r in source_references(c['tracking_binding']))
        self.transition_refs = {cid for d in self.original.get('source_transitions', []) for cid in
                                [d['from_clip_id'], d['to_clip_id'],
                                 *(v for pair in d.get('audio_pairs', []) for v in pair.values())]}

    def track(self, tid):
        if tid not in self.tracks:
            fail('EDIT_TRACK_NOT_FOUND', '找不到轨道: ' + tid)
        return self.tracks[tid]

    def unlocked(self, ids):
        for cid in ids:
            if cid not in self.before:
                fail('EDIT_CLIP_NOT_FOUND', '找不到片段: ' + cid)
            if self.before[cid][0].get('locked', False):
                fail('EDIT_TRACK_LOCKED', '范围编辑涉及锁定的关联轨道: ' + self.before[cid][0]['id'])

    def linked(self, ids):
        result = set(ids)
        self.unlocked(result)
        if self.options['linked']:
            links = {self.before[cid][1].get('link_id') for cid in result} - {None}
            result.update(cid for cid, (_, c) in self.before.items() if c.get('link_id') in links)
        self.unlocked(result)
        return result

    def fresh(self, base):
        stem, number = base[:72], 2
        value = stem
        while value in self.used:
            value = stem + '_' + str(number)
            number += 1
        self.used.add(value)
        return value

    def guard_cut(self, clip):
        if clip['id'] in self.protected and (not self.native_tracking or self.request['action']=='retime'):
            fail('EDIT_RANGE_BINDING_UNSUPPORTED', '裁切涉及跟踪绑定源或目标；需先解除绑定或编辑完整容器')
        if clip['id'] in self.transition_refs:
            fail('EDIT_RANGE_TRANSITION_UNSUPPORTED', '剪口涉及真实源转场端点；需先移除声明或编辑完整容器')

    def piece(self, clip, first, last, *, at=None, cid=None):
        self.guard_cut(clip)
        result = slice_clip(clip, first, last, start=at, clip_id=cid,allow_tracking=self.native_tracking)
        self.origin[result['id']] = self.origin.get(clip['id'], clip['id'])
        self.changed.add(result['id'])
        return result

    def move(self, clip, delta):
        if delta == 0:
            return clip
        result = copy.deepcopy(clip)
        result['timeline_start_tick'] += delta
        if start(result) < 0:
            fail('EDIT_NEGATIVE_TIME', '移位不能到负时间')
        subtitle = result.get('subtitle', {})
        external = self.assets.get(result.get('asset_id'), {}).get('kind') == 'subtitle' or bool(subtitle.get('asset_uri'))
        if external and not result.get('presentation_window') and subtitle.get('asset_time_base', 'sequence') == 'sequence':
            result.setdefault('subtitle', {})['asset_time_offset_tick'] = subtitle.get('asset_time_offset_tick', 0) - delta
            self.retimed.add(result['id'])
        self.changed.add(result['id'])
        return result

    def resize(self, clip, offset_delta, duration, at):
        self.guard_cut(clip)
        if duration <= 0 or at < 0:
            fail('EDIT_RANGE_EMPTY_SIDE', '剪口两侧必须保留非空片段与非负落点')
        validate_window(clip,allow_tracking=self.native_tracking)
        result = copy.deepcopy(clip)
        window = result.setdefault('presentation_window', {
            'version': 1, 'authored_start_tick': start(clip),
            'authored_duration_tick': clip['duration_tick'], 'offset_tick': 0})
        offset = window['offset_tick'] + offset_delta
        if offset < 0 or offset + duration > window['authored_duration_tick']:
            if clip['id'] in self.protected and not self.native_tracking:
                fail('EDIT_RANGE_BINDING_SOURCE_EXTENSION_UNSUPPORTED','带绑定的真实源外扩需要重新规划观测基准；保留句柄内的窗口调整可用')
            if self.request.get('handle_policy') != 'source' and self.request['action'] != 'extend_source':
                fail('EDIT_RANGE_HANDLE_SHORTFALL', '原作者输出没有足够保留句柄；可显式选择 handle_policy=source 使用真实源范围')
            from .source_edits import expand_author
            head = max(0, -offset)
            tail = max(0, offset+duration-window['authored_duration_tick'])
            result, change = expand_author(self.project, result, head, tail)
            self.source_changes.append(change)
            window = result['presentation_window']
            offset += head
        window['offset_tick'] = offset
        result['duration_tick'], result['timeline_start_tick'] = duration, at
        validate_window(result,allow_tracking=self.native_tracking)
        self.changed.add(result['id'])
        return result

    def slip(self):
        from .source_edits import slip
        selected = self.linked({self.request['clip_id']})
        replacements = {}
        delta = self.request['delta_source_tick']
        for cid in sorted(selected):
            if delta and cid in self.protected and not self.native_tracking:
                fail('EDIT_RANGE_BINDING_UNSUPPORTED', 'slip 会使跟踪源或目标的既有观察失效；请先重新规划绑定')
            replacements[cid], change = slip(self.project, self.before[cid][1], delta)
            if delta:
                self.changed.add(cid)
                self.source_changes.append(change)
        self.selected.update(selected)
        self.replace(replacements)

    def extend_source(self):
        selected = self.linked({self.request['clip_id']})
        head, tail = self.request['head_tick'], self.request['tail_tick']
        replacements = {}
        if head or tail:
            for cid in sorted(selected):
                clip = self.before[cid][1]
                replacements[cid] = self.resize(clip, -head, clip['duration_tick']+head+tail, start(clip)-head)
        self.selected.update(selected)
        self.replace(replacements)

    def range_selection(self, own, a, b, ripple):
        for tid in own:
            if self.track(tid).get('locked', False):
                fail('EDIT_TRACK_LOCKED', '目标轨道已锁定: ' + tid)
        reached = set(own)
        if self.options['sync'] and ripple:
            reached.update(t['id'] for t in self.original['tracks'] if not t.get('locked', False) and t.get('sync_lock', True))
        affected = lambda c: end(c) > a if ripple else start(c) < b and end(c) > a
        selected = {cid for cid, (t, c) in self.before.items() if t['id'] in reached and affected(c)}
        while True:
            expanded = self.linked(selected)
            if self.options['linkage'] and self.main:
                hosts = {cid for cid in expanded if self.before[cid][0]['id'] == self.main['id']}
                expanded.update(cid for cid, (t, c) in self.before.items() if not t.get('locked', False)
                                and t['id'] != self.main['id'] and _rides(self.main, c) and _host(self.main, c) in hosts)
            if expanded == selected:
                break
            selected = expanded
        self.selected.update(selected)
        return selected

    def rewrite_range(self, selected, a, b, action):
        delta = b - a
        for track in self.sequence['tracks']:
            rows = []
            for clip in track['clips']:
                cid, first, last = clip['id'], start(clip), end(clip)
                if cid not in selected or last <= a:
                    rows.append(clip)
                    continue
                if action == 'insert':
                    if first >= a:
                        rows.append(self.move(clip, delta))
                    else:
                        rows.extend([self.piece(clip, 0, a-first),
                                     self.piece(clip, a-first, clip['duration_tick'], at=b, cid=self.fresh(cid+'_after'))])
                elif first >= b:
                    rows.append(self.move(clip, -delta) if action == 'extract' else clip)
                else:
                    self.changed.add(cid)
                    if first < a:
                        rows.append(self.piece(clip, 0, a-first))
                    if last > b:
                        rows.append(self.piece(clip, b-first, clip['duration_tick'],
                                               at=a if action == 'extract' else b,
                                               cid=self.fresh(cid+'_after') if first < a else cid))
            track['clips'] = rows

    def insert_items(self):
        items = self.request['items']
        for item in items:
            clip = item['clip']
            result = slice_clip(clip, 0, clip['duration_tick'], start=self.request['at_tick']+start(clip),allow_tracking=self.native_tracking)
            self.track(item['track_id'])['clips'].append(result)
            self.changed.add(result['id'])

    def pairs(self, left, right):
        self.unlocked([left, right])
        lt, lc = self.before[left]
        rt, rc = self.before[right]
        if lt['id'] != rt['id'] or end(lc) != start(rc):
            fail('EDIT_RANGE_CUT_INVALID', 'roll 需要同轨精确相邻的两个片段')
        lefts, rights = self.linked({left}), self.linked({right})
        if self.options['sync']:
            cut = end(lc)
            for track in self.original['tracks']:
                if track.get('locked', False) or not track.get('sync_lock', True):
                    continue
                ls = [c['id'] for c in track['clips'] if end(c) == cut]
                rs = [c['id'] for c in track['clips'] if start(c) == cut]
                if len(ls) == len(rs) == 1:
                    lefts.update(ls); rights.update(rs)
        lefts, rights = self.linked(lefts), self.linked(rights)
        if lefts & rights:
            cut = end(lc)
            lefts = {cid for cid in lefts if end(self.before[cid][1]) == cut}
            rights = {cid for cid in rights if start(self.before[cid][1]) == cut}
        rows = []
        for tid in sorted({self.before[cid][0]['id'] for cid in lefts | rights}):
            ls = [cid for cid in lefts if self.before[cid][0]['id'] == tid]
            rs = [cid for cid in rights if self.before[cid][0]['id'] == tid]
            if len(ls) != 1 or len(rs) != 1 or ls[0] == rs[0] or end(self.before[ls[0]][1]) != start(self.before[rs[0]][1]):
                fail('EDIT_RANGE_LINK_GEOMETRY', '关联剪口须在每个参与轨道有唯一连续左右对；可显式 linked=false 单独编辑')
            rows.append((ls[0], rs[0]))
        self.unlocked(lefts | rights)
        self.selected.update(lefts | rights)
        return rows

    def replace(self, replacements):
        for track in self.sequence['tracks']:
            track['clips'] = [replacements.get(c['id'], c) for c in track['clips']]

    def roll(self):
        q, replacements = self.request, {}
        pairs = self.pairs(q['left_clip_id'], q['right_clip_id'])
        delta = q['delta_tick']
        if delta:
            for left, right in pairs:
                lc, rc = self.before[left][1], self.before[right][1]
                replacements[left] = self.resize(lc, 0, lc['duration_tick']+delta, start(lc))
                replacements[right] = self.resize(rc, delta, rc['duration_tick']-delta, start(rc)+delta)
        self.cut_pairs = [{'left_clip_id': l, 'right_clip_id': r} for l, r in pairs]
        self.replace(replacements)

    def slide(self):
        q, replacements = self.request, {}
        cid = q['clip_id']
        mids = self.linked({cid})
        root_mid = self.before[cid][1]
        if self.options['sync']:
            for track in self.original['tracks']:
                if track.get('locked', False) or not track.get('sync_lock', True):
                    continue
                matches = [c['id'] for c in track['clips'] if start(c) == start(root_mid) and end(c) == end(root_mid)]
                if len(matches) == 1:
                    mids.update(matches)
        self.unlocked(mids)
        triples = []
        for mid in sorted(mids):
            track, clip = self.before[mid]
            ls = [c['id'] for c in track['clips'] if end(c) == start(clip) and c['id'] != mid]
            rs = [c['id'] for c in track['clips'] if start(c) == end(clip) and c['id'] != mid]
            if len(ls) != 1 or len(rs) != 1:
                fail('EDIT_RANGE_CUT_INVALID', 'slide 每个关联成员需要唯一的连续左右邻居')
            triples.append((ls[0], mid, rs[0]))
        touched = {c for triple in triples for c in triple}
        if len(touched) != 3*len(triples):
            fail('EDIT_RANGE_LINK_GEOMETRY', 'slide 的关联三元组不能共享片段')
        if self.linked(touched) != touched:
            fail('EDIT_RANGE_LINK_GEOMETRY', 'slide 邻居关联组不完整；须完整选择或显式 linked=false')
        delta = q['delta_tick']
        for left, mid, right in triples:
            lc, mc, rc = self.before[left][1], self.before[mid][1], self.before[right][1]
            if delta:
                replacements[left] = self.resize(lc, 0, lc['duration_tick']+delta, start(lc))
                replacements[mid] = self.move(mc, delta)
                replacements[right] = self.resize(rc, delta, rc['duration_tick']-delta, start(rc)+delta)
        if delta and self.options['linkage'] and self.main:
            hosts = {mid for mid in mids if self.before[mid][0]['id'] == self.main['id']}
            riders = {cid for cid, (t, c) in self.before.items() if cid not in touched and not t.get('locked', False)
                      and t['id'] != self.main['id'] and _rides(self.main, c) and _host(self.main, c) in hosts}
            riders = self.linked(riders)
            if riders & touched:
                fail('EDIT_RANGE_LINK_GEOMETRY', 'slide 骑乘关联组与剪口成员冲突')
            for rider in riders:
                replacements[rider] = self.move(self.before[rider][1], delta)
            touched.update(riders)
        self.selected.update(touched)
        self.cut_pairs = [{'left_clip_id': l, 'clip_id': m, 'right_clip_id': r} for l, m, r in triples]
        self.replace(replacements)

    def settle(self):
        # Same lane policy as whole-clip editing, with origin IDs for cut pieces.
        lanes = _Draft(self.project, self.sequence, {'options': self.options})
        lanes.used = self.used
        for track in list(self.sequence['tracks']):
            if track.get('locked', False):
                continue
            kept = []
            for clip in sorted(list(track['clips']), key=lambda c: (start(c), c['id'])):
                hits = [c for c in kept if _overlap(c, clip)]
                original = self.origin.get(clip['id'])
                def old_overlap(other):
                    old = self.origin.get(other['id'])
                    return frozenset((clip['id'], other['id'])) in self.intentional_overlaps or (
                        original != old and original in self.before and old in self.before
                        and _overlap(self.before[original][1], self.before[old][1]))
                introduced = [other for other in hits if not old_overlap(other)]
                if not introduced:
                    kept.append(clip)
                    continue
                if track['id'] == self.options['main_track_id']:
                    fail('EDIT_MAIN_TRACK_COLLISION', '范围编辑不能在主轨留下新重叠')
                moving = [clip] if clip['id'] in self.changed else [c for c in introduced if c['id'] in self.changed]
                if not moving:
                    fail('EDIT_RANGE_COLLISION', '没有可保持处理语义的冲突解决方案')
                for item in moving:
                    track['clips'].remove(item)
                    if item in kept:
                        kept.remove(item)
                    lanes.relocate(track, item)
                if clip not in moving:
                    kept.append(clip)
        self.tracks = {t['id']: t for t in self.sequence['tracks']}
        self.new_tracks = lanes.new_tracks

    def references(self):
        now = {c['id']: (t, c) for t in self.sequence['tracks'] for c in t['clips']}
        declarations = []
        for declaration in self.sequence.get('source_transitions', []):
            ids = {declaration['from_clip_id'], declaration['to_clip_id'],
                   *(v for pair in declaration.get('audio_pairs', []) for v in pair.values())}
            surviving = ids & now.keys()
            if not surviving:
                self.removed_transitions.append(declaration['id'])
            elif surviving != ids:
                fail('EDIT_RANGE_TRANSITION_UNSUPPORTED', '移除仅部分真实源转场端点；需先移除声明或编辑完整容器')
            else:
                lt, lc = now[declaration['from_clip_id']]
                rt, rc = now[declaration['to_clip_id']]
                if lt['id'] != rt['id'] or end(lc) != start(rc):
                    fail('EDIT_RANGE_TRANSITION_UNSUPPORTED', '编辑会拆开既有真实源转场剪口；需先移除声明或编辑完整容器')
                for pair in declaration.get('audio_pairs', []):
                    at, ac = now[pair['from_clip_id']]
                    bt, bc = now[pair['to_clip_id']]
                    if at['id'] != bt['id'] or end(ac) != start(bc) or end(ac) != end(lc):
                        fail('EDIT_RANGE_TRANSITION_UNSUPPORTED', '编辑会拆开真实源转场的关联音频剪口')
                declarations.append(declaration)
        if 'source_transitions' in self.sequence:
            self.sequence['source_transitions'] = declarations
        if self.native_tracking:
            from .binding_edits import replan
            self.binding_changes = replan(self.project,self.sequence,self.original,self.origin,source_changes=self.source_changes)
            self.rebound.update(c['clip_id'] for c in self.binding_changes)
        for s in ([] if self.native_tracking else self.project['sequences']):
            for track in s['tracks']:
                for clip in track['clips']:
                    binding = clip.get('tracking_binding')
                    if not binding or binding.get('source_clip_id') not in self.before:
                        continue
                    source = now.get(binding['source_clip_id'])
                    if source is None:
                        fail('EDIT_BINDING_SOURCE_REMOVED', '移除后仍有绑定引用该源片段')
                    if source[0]['id'] != binding.get('source_track_id'):
                        if track.get('locked', False):
                            fail('EDIT_BOUND_REFERENCE_LOCKED', '换轨需要更新锁定轨道上的绑定')
                        binding['source_track_id'] = source[0]['id']
                        self.rebound.add(clip['id'])
        for track in self.sequence['tracks']:
            validate_track_transitions(track)
        for track in self.original['tracks']:
            if track.get('locked', False) and self.track(track['id']) != track:
                fail('EDIT_LOCK_INVARIANT_FAILED', '范围编辑不能改变锁定轨道')

    def run(self):
        q, action = self.request, self.request['action']
        if action in {'roll', 'slide', 'slip', 'extend_source'}:
            getattr(self, action)()
        else:
            a, b = q['at_tick'], q['at_tick']+q['duration_tick']
            own = {i['track_id'] for i in q['items']} if 'items' in q else set(q['track_ids'])
            selected = self.range_selection(own, a, b, action in {'insert', 'extract'})
            self.rewrite_range(selected, a, b, action)
            if 'items' in q:
                self.insert_items()
            if action == 'insert':
                self.sequence['duration_tick'] = max(self.old_duration, a)+q['duration_tick']
            elif action == 'overwrite':
                self.sequence['duration_tick'] = max(self.old_duration, b)
            elif action == 'extract':
                self.sequence['duration_tick'] = max(1, self.old_duration-q['duration_tick'])
        self.settle()
        self.references()
        if self.source_changes and self.sequence.get('source_transitions'):
            from .source_transitions import analyze
            analyze(self.project, self.sequence)
        self.sequence['duration_tick'] = max([self.sequence['duration_tick'], 1,
            *(end(c) for t in self.sequence['tracks'] for c in t['clips'])])
        old = {c['id']: (t['id'], c) for t in self.original['tracks'] for c in t['clips']}
        new = {c['id']: (t['id'], c) for t in self.sequence['tracks'] for c in t['clips']}
        changes = [{'clip_id': cid,
                    'before': {'track_id': old[cid][0], 'clip': old[cid][1]} if cid in old else None,
                    'after': {'track_id': new[cid][0], 'clip': new[cid][1]} if cid in new else None}
                   for cid in sorted(old.keys() | new.keys()) if old.get(cid) != new.get(cid)]
        return self.project, {
            'engine': ENGINE, 'base_project_sha256': None, 'sequence_id': self.sequence['id'],
            'request': q, 'main_track_id': self.options['main_track_id'],
            'selected_clip_ids': sorted(self.selected), 'incoming_clip_ids': [i['clip']['id'] for i in q.get('items', [])],
            'changes': changes, 'short_tick': 0, 'new_track_ids': self.new_tracks,
            'new_tracks': [copy.deepcopy(t) for t in self.sequence['tracks'] if t['id'] in self.new_tracks],
            'rebound_clip_ids': sorted(self.rebound),
            'tracking_binding_changes':self.binding_changes,
            'retimed_subtitle_ids': sorted(self.retimed), 'removed_transition_ids': self.removed_transitions,
            'cut_pairs': self.cut_pairs, 'source_changes': self.source_changes,
            'warnings': [{'code': 'SOURCE_EDIT_NESTED_CURVE_RENORMALIZED',
                          'message': '外扩保留嵌套曲线的原生时长归一化；旧主体采样时钟可能变化，请检查前后计划与成片',
                          'clip_id': change['clip_id']}
                         for change in self.source_changes if change.get('native_nested_curve_renormalized')],
            'before_duration_tick': self.old_duration, 'after_duration_tick': self.sequence['duration_tick'],
            'limits': ['markers-remain-absolute', 'roll-and-slide-default-to-retained-authored-handles',
                       'source-handles-require-finite-recorded-local-input-bounds',
                       'source-extension-reauthors-edge-processing-and-native-retiming',
                       'native-tracking-replans-retained-fragments; legacy-tracking-and-real-transition-endpoint-cuts-reject',
                       'clip-processing-before-cut-track-and-root-processing-after-edit',
                       'existing-native-window-render-budgets-still-apply'],
        }


def build_range_plan(project, sequence_id, request):
    candidate, plan = RangeDraft(project, sequence_id, request).run()
    plan['base_project_sha256'] = project_fingerprint(project)
    return candidate, plan
