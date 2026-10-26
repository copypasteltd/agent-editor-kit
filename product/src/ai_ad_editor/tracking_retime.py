"""Shared author/dependency context for native tracking output retiming."""
import copy

from .bindings import source_references, validate_binding
from .edit_planner import _error
from .range_edits import start, end
from .sequence_canvas import sequence_canvas
from .sequence_selection import PROTOCOL


def context(draft, body, host):
    """Close tracking edges in both directions, and explicitly enabled links."""
    edges = []
    for cid, (_, clip) in draft.before.items():
        if clip.get('tracking_binding'):
            edges.extend(({cid, r['clip_id']} for r in source_references(clip['tracking_binding'])))
    if not any(edge & body for edge in edges) and not any('sequence_clip_id' in draft.before[k][1] for k in body):
        return body, None
    if draft.options['linked']:
        links = {}
        for cid, (_, clip) in draft.before.items():
            if clip.get('link_id'):
                links.setdefault(clip['link_id'], set()).add(cid)
        edges.extend(links.values())
    closure = set(body)
    while True:
        expanded = closure | set().union(*(edge for edge in edges if edge & closure))
        if expanded == closure:
            break
        closure = expanded
    active = {cid for cid in closure if end(draft.before[cid][1]) > start(host)
              and start(draft.before[cid][1]) < end(host)}
    for cid in active - body:
        lane, _ = draft.before[cid]
        if lane.get('sync_lock') is False:
            _error('EDIT_RETIME_BINDING_SYNC_LOCK', '跟踪依赖轨道关闭了同步；请显式处理其共享作者时钟')
    draft.unlocked(active)
    return active, closure


def create(draft, closure, body, host):
    """Clone full author clips, never just their retimed display intervals."""
    sid = draft.fresh(host['id'] + '_shared_author')
    tids = {t['id']: draft.fresh(t['id'] + '_shared_author') for t in draft.original['tracks']
            if any(c['id'] in closure for c in t['clips'])}
    cids = {cid: draft.fresh(cid + '_shared_author') for cid in sorted(closure)}
    links = {}
    tracks = []
    for lane in draft.original['tracks']:
        if lane['id'] not in tids:
            continue
        # Track effects, buses and external blend slots remain on the parent.
        track = {k: copy.deepcopy(lane[k]) for k in ('kind', 'order', 'muted', 'overlap_policy') if k in lane}
        track.update(id=tids[lane['id']], clips=[])
        for clip in lane['clips']:
            if clip['id'] not in closure:
                continue
            inner = copy.deepcopy(clip)
            inner['id'] = cids[clip['id']]
            if inner.get('link_id'):
                old = inner['link_id']
                if old not in links:
                    links[old] = draft.fresh(old + '_author_link')
                inner['link_id'] = links[old]
            binding = inner.get('tracking_binding')
            if binding:
                binding['source_track_id'] = tids.get(binding['source_track_id'], binding['source_track_id'])
                binding['source_clip_id'] = cids.get(binding['source_clip_id'], binding['source_clip_id'])
                for reference in binding.get('source_fragments', []):
                    reference['track_id'] = tids[reference['track_id']]
                    reference['clip_id'] = cids[reference['clip_id']]
            track['clips'].append(inner)
        tracks.append(track)
    child = dict(id=sid, name='Shared authored tracking ' + host['id'],
        duration_tick=max(draft.original['duration_tick'], end(host), 1),
        canvas=sequence_canvas(draft.project, draft.sequence), tracks=tracks, markers=[])
    draft.project['sequences'].append(child)
    for track in tracks:
        for clip in track['clips']:
            if clip.get('tracking_binding'):
                validate_binding(draft.project, child, track, clip)
    # Parent outputs become an explicit editable linked cohort. Breaking that
    # link later separates complete authored outputs, not the inner binding.
    link = draft.fresh(host['id'] + '_shared_output_link')
    return dict(sequence_id=sid, clips=cids, link_id=link,
        report=dict(protocol=PROTOCOL, sequence_id=sid, context_clip_ids=sorted(closure),
            retimed_clip_ids=sorted(body), readonly_context_clip_ids=sorted(closure-body),
            selected_author_clip_ids=cids, parent_link_id=link,
            source_observations_preserved=True, external_layer_order_preserved=True,
            display_keyframes_baked=False, model_inference=False))
