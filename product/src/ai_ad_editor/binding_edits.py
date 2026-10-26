"""Detached native tracking lineage repair, without sampling or model inference.

Source observations stay on the asset clock. Only retained clip references and
the original ROI/rotation reference output tick change during an edit.
"""
import copy

from .bindings import (find_sources, native_clock_project, source_references,
                       validate_binding, MAX_SOURCE_FRAGMENTS)
from .errors import AppError

PROTOCOL = 'native-tracking-edit-lineage-v1'


def replan(project, sequence, original, origins, *, source_changes=(), containerized_sources=()):
    if not native_clock_project(project):return []
    before = {c['id']:(t,c) for t in original['tracks'] for c in t['clips']}
    after = {c['id']:(t,c) for t in sequence['tracks'] for c in t['clips']}
    descendants = {}
    author_shifts = {}
    for change in source_changes:
        cid=change['clip_id']
        author_shifts[cid]=author_shifts.get(cid,0)+change.get('head_tick',0)
    for cid, pair in after.items():
        descendants.setdefault(origins.get(cid,cid),[]).append(pair)
    changed = []
    for track in sequence['tracks']:
        for target in track['clips']:
            binding = target.get('tracking_binding')
            if not binding:continue
            previous = before.get(origins.get(target['id'],target['id']))
            old_target = previous[1] if previous else target
            old_binding = old_target.get('tracking_binding') or binding
            refs = source_references(binding)
            affected = old_target != target or any(
                r['clip_id'] in before and (len(descendants.get(r['clip_id'],[]))!=1 or
                    descendants[r['clip_id']][0] != before[r['clip_id']]) for r in refs)
            if not affected:continue
            updated = copy.deepcopy(binding)
            route = []
            for reference in refs:
                cid = reference['clip_id']
                pairs = descendants.get(cid,[]) if cid in before else [after[cid]] if cid in after else []
                for source_track, source in pairs:
                    if source['id'] in containerized_sources:
                        # The matching target interval lives in the same shared
                        # author graph. Outside retained pieces still use only
                        # direct sources on the parent clock.
                        continue
                    if source.get('sequence_id') or source.get('asset_id') != binding['asset_id']:
                        raise AppError('EDIT_BINDING_SOURCE_CHANGED','编辑替换了跟踪源的媒体身份，需重新跟踪或明确解除绑定',exit_code=2)
                    retained=dict(track_id=source_track['id'],clip_id=source['id'],
                        **({'author_offset_tick':reference['author_offset_tick']} if 'author_offset_tick' in reference else {}))
                    offset=reference.get('author_offset_tick',0)+author_shifts.get(source['id'],0)
                    if offset:retained['author_offset_tick']=offset
                    route.append(retained)
            route.sort(key=lambda r:(after[r['clip_id']][1]['timeline_start_tick'],r['track_id'],r['clip_id']))
            if len(route)>MAX_SOURCE_FRAGMENTS:
                raise AppError('EDIT_BINDING_FRAGMENT_BUDGET','一次绑定超过128个保留源分片',exit_code=2)
            updated['source_fragments'] = route
            if route:
                updated['source_track_id'],updated['source_clip_id'] = route[0]['track_id'],route[0]['clip_id']
            if 'reference_output_tick' not in updated and source_references(old_binding):
                old_sources = find_sources(original,old_binding)
                origin = old_target['timeline_start_tick']-int((old_target.get('presentation_window') or {}).get('offset_tick',0))
                origin += int((old_target.get('_source_handle') or {}).get('head_tick',0))
                _, source = min(old_sources,key=lambda pair: (max(pair[1]['timeline_start_tick']-origin,
                    origin-(pair[1]['timeline_start_tick']+pair[1]['duration_tick']),0),pair[1]['timeline_start_tick'],pair[1]['id']))
                window = source.get('presentation_window') or {}
                elapsed = origin-source['timeline_start_tick']+int(window.get('offset_tick',0))
                updated['reference_output_tick'] = max(0,min(int(window.get('authored_duration_tick',source['duration_tick'])),elapsed))
            edits=[copy.deepcopy(c) for c in source_changes if c['clip_id'] in {r['clip_id'] for r in refs}]
            if updated != binding or edits:
                if track.get('locked'):
                    raise AppError('EDIT_BOUND_REFERENCE_LOCKED','编辑需要更新锁定轨道上的跟踪引用',exit_code=2)
                target['tracking_binding'] = updated
                changed.append(dict(clip_id=target['id'],before=copy.deepcopy(binding),after=copy.deepcopy(updated),
                    inactive=not route,protocol=PROTOCOL,source_edits=edits))
    # Validate the complete result, including routes of unchanged dependants.
    for track in sequence['tracks']:
        for target in track['clips']:
            if target.get('tracking_binding'):validate_binding(project,sequence,track,target)
    return changed
