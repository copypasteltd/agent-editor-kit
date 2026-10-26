"""Partition synchronized author windows before a discontinuous permutation."""
from __future__ import annotations

from bisect import bisect_left, bisect_right
from collections import defaultdict

from .clip_windows import slice_clip, validate_track_transitions
from .edit_planner import _error
from .bindings import native_clock_project


def split_sync(project, sequence, main, deltas, options, maximum):
    if not options['sync'] or not main:
        return []
    native = native_clock_project(project)
    rows = {c['id']: (t, c) for t in sequence['tracks'] for c in t['clips']}
    starts = [c['timeline_start_tick'] for c in main]
    ends = [c['timeline_start_tick']+c['duration_tick'] for c in main]
    cuts = sorted(set(starts+ends))
    main_ids = set(deltas)
    groups = defaultdict(list)
    for cid, (_, c) in rows.items():
        if options['linked'] and c.get('link_id'):
            groups[c['link_id']].append(cid)

    def region(at):
        i = bisect_right(starts, at)-1
        hosted = i >= 0 and (at < ends[i] or i == len(main)-1)
        return (deltas[main[i]['id']], main[i]['id']) if hosted else (0, None)

    def boundaries(c):
        a, b = c['timeline_start_tick'], c['timeline_start_tick']+c['duration_tick']
        return [a, *cuts[bisect_right(cuts, a):bisect_left(cuts, b)], b]

    cohorts, admitted = [], set()
    for cid, (track, c) in rows.items():
        if cid in main_ids or track.get('locked', False) or not track.get('sync_lock', True):
            continue
        link = c.get('link_id') if options['linked'] else None
        members = groups[link] if link else [cid]
        if any(m in main_ids for m in members) or cid in admitted:
            continue
        points = boundaries(c)
        signals = [region(at) for at in points[:-1]]
        # A rigid, fully hosted interval still uses the existing whole-clip path.
        if len(points) == 2 or (len({s[0] for s in signals}) == 1 and all(s[1] for s in signals)):
            continue
        admitted.update(members)
        cohorts.append((link, members))
    count = len(rows)
    for _, members in cohorts:
        count += sum(len(boundaries(rows[cid][1]))-2 for cid in members)
        if count > maximum:
            _error('EDIT_REORDER_RESOURCE_LIMIT', '自动同步拆分后超过 20000 个片段；没有缩减输入')
    if not cohorts:
        return []
    used = {obj['id'] for seq in project['sequences'] for obj in
            [seq, *seq['tracks'], *(c for t in seq['tracks'] for c in t['clips']),
             *seq.get('markers', []), *seq.get('source_transitions', [])] if 'id' in obj}
    used.update(a['id'] for a in project.get('assets', []))
    used.update(c['link_id'] for s in project['sequences'] for t in s['tracks'] for c in t['clips'] if c.get('link_id'))
    protected = {c['id'] for s in project['sequences'] for t in s['tracks'] for c in t['clips'] if c.get('tracking_binding')}
    protected.update(c['tracking_binding']['source_clip_id'] for s in project['sequences'] for t in s['tracks']
                     for c in t['clips'] if c.get('tracking_binding'))
    transition_refs = {cid for d in sequence.get('source_transitions', []) for cid in
                       [d['from_clip_id'], d['to_clip_id'], *(v for p in d.get('audio_pairs', []) for v in p.values())]}

    def fresh(stem):
        stem = stem[:100]
        name, serial = stem, 2
        while name in used:
            name, serial = f'{stem}_{serial}', serial+1
        used.add(name)
        return name

    reports = []
    for link, members in cohorts:
        for cid in members:
            track, _ = rows[cid]
            if track.get('locked', False):
                _error('EDIT_TRACK_LOCKED', '同步拆分涉及锁定的关联成员: '+cid)
            if cid in protected and not native:
                _error('EDIT_REORDER_SYNC_BINDING_UNSUPPORTED', '同步拆分涉及跟踪绑定源或目标: '+cid)
            if cid in transition_refs:
                _error('EDIT_REORDER_SYNC_TRANSITION_UNSUPPORTED', '同步拆分涉及真实源转场端点: '+cid)
        regions = sorted({bisect_right(cuts, at) for cid in members for at in boundaries(rows[cid][1])[:-1]})
        links = {r: (link if i == 0 else fresh(link+'_sync_'+str(i))) for i, r in enumerate(regions)} if link else {}
        for cid in members:
            track, c = rows[cid]
            points = boundaries(c)
            pieces, report = [], {'clip_id': cid, 'track_id': track['id'], 'original_link_id': link,
                'original_start_tick': c['timeline_start_tick'], 'original_duration_tick': c['duration_tick'], 'pieces': []}
            for i, (a, b) in enumerate(zip(points, points[1:])):
                pid = cid if i == 0 else fresh(cid+'_sync_'+str(i))
                piece = slice_clip(c, a-c['timeline_start_tick'], b-c['timeline_start_tick'], clip_id=pid,
                                   allow_tracking=native)
                if link:
                    piece['link_id'] = links[bisect_right(cuts, a)]
                delta, host = region(a)
                pieces.append(piece)
                report['pieces'].append({'clip_id': pid, 'original_range_tick': [a, b], 'host_clip_id': host,
                    'expected_delta_tick': delta, 'link_id': piece.get('link_id')})
            index = track['clips'].index(c)
            track['clips'][index:index+1] = pieces
            validate_track_transitions(track)
            reports.append(report)
    return reports
