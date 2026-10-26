"""Editable complete-author temporal wrappers and native ripple following."""
from __future__ import annotations

import copy

from .clip_windows import slice_clip, validate_track_transitions
from .edit_planner import (_error, _identifier, _plan_changes, _rides, _host,
                           project_fingerprint, validate_editing)
from .range_edits import RangeDraft, start, end
from .retime_transform import Transform
from .sequence_canvas import sequence_canvas
from .blend_automation import retimed_blend

ENGINE = 'agent-complete-output-retime-v1'
MAX_CLIPS = 20000
FADES = {None, '', 'fade', 'fade_in', 'fade_out'}


def normalize(sequence, request):
    allowed = {'action','clip_ids','transform','options','sync_content'}
    if not isinstance(request, dict) or set(request)-allowed or request.get('action') != 'retime':
        _error('EDIT_RETIME_REQUEST_INVALID', 'retime 只接受 action/clip_ids/transform/options/sync_content')
    ids = request.get('clip_ids')
    if not isinstance(ids, list) or not ids:
        _error('EDIT_RETIME_REQUEST_INVALID', 'clip_ids 必须非空')
    ids = [_identifier(cid, 'edit.clip_ids') for cid in ids]
    if len(set(ids)) != len(ids):
        _error('EDIT_RETIME_REQUEST_INVALID', 'clip_ids 不能重复')
    supplied = request.get('options', {})
    if not isinstance(supplied, dict) or set(supplied)-{'linked','sync','linkage'}:
        _error('EDIT_RETIME_REQUEST_INVALID', 'options 只允许 linked/sync/linkage')
    opts = validate_editing(sequence)
    for key, value in supplied.items():
        if type(value) is not bool:
            _error('EDIT_RETIME_REQUEST_INVALID', 'options 必须为严格布尔值')
        opts[key] = value
    policy = request.get('sync_content', 'ripple')
    if not isinstance(policy, str) or policy not in ('ripple','retime'):
        _error('EDIT_RETIME_REQUEST_INVALID', 'sync_content 必须为 ripple/retime')
    return {'action':'retime','clip_ids':ids,'transform':copy.deepcopy(request.get('transform')),
            'options':opts,'sync_content':policy}


def _guard(draft, track, clip):
    draft.unlocked([clip['id']])
    draft.guard_cut(clip)
    if track['kind'] not in ('video','audio','subtitle') and not (draft.native_tracking and track['kind']=='overlay'):
        _error('EDIT_RETIME_TRACK_UNSUPPORTED', 'retime 需要可渲染的 video/audio/subtitle 轨道')
    if any(isinstance(clip.get(key), dict) and clip[key].get('type') not in FADES
           for key in ('transition_in','transition_out')):
        independent=False
        if draft.native_tracking and track['kind'] in ('video','overlay','subtitle'):
            from .float_transition_plan import compile_track
            plan=compile_track(track,draft.project['settings']['timebase']['ticks_per_second'])
            independent=not any(clip['id'] in (p['from'],p['to']) for p in plan['pairs'])
        if not independent:
            _error('EDIT_RETIME_TRANSITION_UNSUPPORTED', '完整输出变速需先移除跨片段转场或选择其完整上级组')


def _wrap(draft, track, clip, host, transform, *, cid, first, last, shared=None):
    """Complete the original clip before sharing the host's output clock."""
    _guard(draft, track, clip)
    if shared:
        sid, inner_id = shared['sequence_id'], shared['clips'][clip['id']]
        blend = None  # Child returns its original scalar alpha and blend slot.
    else:
        original = copy.deepcopy(clip)
        blend = retimed_blend(original, host, transform, draft.project['settings'])
        original.pop('blend', None)
        original.pop('link_id', None)
        inner_id = draft.fresh(cid+'_author')
        inner = slice_clip(original, 0, original['duration_tick'], clip_id=inner_id,allow_tracking=draft.native_tracking)
        sid = draft.fresh(cid+'_author_sequence')
        child_track = draft.fresh(cid+'_author_track')
        child = {'id':sid,'name':'Original authored '+clip['id'],
                 'duration_tick':max(end(host),end(clip),1),
                 'canvas':sequence_canvas(draft.project, draft.sequence),
                 'tracks':[{'id':child_track,'kind':track['kind'],'order':0,'clips':[inner]}], 'markers':[]}
        draft.project['sequences'].append(child)
    parent = {'id':cid,'sequence_id':sid,'timeline_start_tick':start(host),
              'duration_tick':transform.output,'source_in_tick':start(host),'source_out_tick':end(host),
              **copy.deepcopy(transform.value)}
    for key in ('link_id','rights_dependencies'):
        if key in clip:
            parent[key] = copy.deepcopy(clip[key])
    if shared:
        parent.update(sequence_clip_id=inner_id,link_id=shared['link_id'])
    if blend is not None:
        parent['blend'] = blend
    audio = clip.get('audio', {})
    role = {k:copy.deepcopy(v) for k,v in audio.items() if k in ('role','ducking','duck_under_voice')}
    if role:
        parent['audio'] = role
    a, b = transform.interval(first-start(host), last-start(host))
    if a != 0 or b != transform.output:
        parent = slice_clip(parent, a, b, start=start(host)+a)
    draft.origin[cid] = clip['id']
    draft.changed.add(cid)
    return parent, {'original_clip_id':clip['id'],'clip_id':cid,'sequence_id':sid,'author_clip_id':inner_id,
                    'original_range_tick':[first,last], 'output_range_tick':[start(parent),end(parent)],
                    'host_original_range_tick':[start(host),end(host)],'source_author_preserved':True,
                    'external_blend_retained':copy.deepcopy(blend)}


def _one(project, sequence_id, cid, query, *, main_selection):
    draft = RangeDraft(project, sequence_id, None, temporal_options=query['options'])
    draft.binding_retime = draft.native_tracking
    track, host = draft.before[cid]
    _guard(draft, track, host)
    is_main = track['id'] == query['options']['main_track_id']
    transform = Transform(query['transform'], host['duration_tick'], draft.project['settings'])
    delta = transform.output-host['duration_tick']
    linked = {cid}
    if query['options']['linked'] and host.get('link_id'):
        linked.update(k for k,(_,c) in draft.before.items() if c.get('link_id')==host['link_id'])
    draft.unlocked(linked)
    # Other selected main shots get their own host clock, processed right-to-left.
    body = {cid}
    for other, (lane, clip) in draft.before.items():
        if other==cid or other in main_selection or end(clip)<=start(host) or start(clip)>=end(host):
            continue
        rider = is_main and query['options']['linkage'] and draft.main and _rides(draft.main, clip) and _host(draft.main, clip)==cid
        synced = (is_main and query['options']['sync'] and query['sync_content']=='retime'
                  and not lane.get('locked') and lane.get('sync_lock',True))
        if other in linked or rider or synced:
            body.add(other)
    if not is_main:
        body = linked
        if any(draft.before[k][0]['id']==query['options']['main_track_id'] for k in body):
            _error('EDIT_RETIME_MIXED_SELECTION', '副轨变速不能隐式改写关联主轨；请显式选择主轨宿主')
    closure = None
    if draft.native_tracking:
        from .tracking_retime import context
        body, closure = context(draft, body, host)
        if not is_main and any(draft.before[k][0]['id']==query['options']['main_track_id'] for k in body):
            _error('EDIT_RETIME_MIXED_SELECTION', '跟踪依赖包含主轨；请显式选择主轨宿主')
    for other in body:
        lane, clip = draft.before[other]
        if end(clip)<=start(host) or start(clip)>=end(host):
            _error('EDIT_RETIME_LINK_RANGE_UNSUPPORTED', '独立副轨关联组必须与宿主相交；不猜测外部落点')
        _guard(draft, lane, clip)
    count = sum(len(t['clips']) for s in project['sequences'] for t in s['tracks'])
    projected = count+sum(1+int(start(draft.before[k][1])<start(host))+
                          int(end(draft.before[k][1])>end(host)) for k in body)
    if closure is not None:
        projected = count+len(closure)+sum(int(start(draft.before[k][1])<start(host))+
            int(end(draft.before[k][1])>end(host)) for k in body)
    if projected>MAX_CLIPS:
        _error('EDIT_RETIME_RESOURCE_LIMIT', '预计作者子序列/前后保留片段超过 20000；未降低精度或丢片段')
    reports, original_rows = [], {}
    shared = None
    if closure is not None:
        from .tracking_retime import create
        shared = create(draft, closure, body, host)
        draft.containerized_sources = set()
    for other in sorted(body, key=lambda k:(draft.before[k][0]['order'],start(draft.before[k][1]),k)):
        lane, clip = draft.before[other]
        original_rows[other] = (lane, clip)
        # Temporarily remove retimed members so the unrelated ripple cannot
        # trim them or turn the newly authored main into a retained old window.
        target = draft.track(lane['id'])
        target['clips'] = [c for c in target['clips'] if c['id']!=other]
    if is_main and delta:
        a = end(host) if delta>0 else end(host)+delta
        b = a+abs(delta)
        selected = draft.range_selection({track['id']},a,b,True)-body
        draft.rewrite_range(selected,a,b,'insert' if delta>0 else 'extract')
    for other, (lane,clip) in original_rows.items():
        first, last = max(start(host),start(clip)), min(end(host),end(clip))
        parts = []
        if start(clip)<first:
            parts.append(draft.piece(clip,0,first-start(clip)))
        body_id = other if not parts else draft.fresh(other+'_retimed')
        wrapped, report = _wrap(draft,lane,clip,host,transform,cid=body_id,first=first,last=last,shared=shared)
        if shared:
            draft.containerized_sources.add(body_id)
        parts.append(wrapped);reports.append(report)
        if last<end(clip):
            tail = draft.piece(clip,last-start(clip),clip['duration_tick'],
                               at=last+delta,
                               cid=draft.fresh(other+'_after'))
            parts.append(tail)
        draft.track(lane['id'])['clips'].extend(parts)
    draft.settle();draft.references()
    if is_main:
        draft.sequence['duration_tick'] = max(1,draft.old_duration+delta)
    draft.sequence['duration_tick'] = max([draft.sequence['duration_tick'],1,
        *(end(c) for t in draft.sequence['tracks'] for c in t['clips'])])
    if any(marker.get('at_tick', 0) > draft.sequence['duration_tick']
           for marker in draft.sequence.get('markers', [])):
        _error('EDIT_RETIME_ABSOLUTE_POINT_OUTSIDE', '变速缩短后有绝对标记越界；请先明确处理标记，不自动删除')
    for lane in draft.sequence['tracks']:
        validate_track_transitions(lane)
    from .magnetic_mode import validate
    validate(draft.sequence)
    return draft.project, {'host_clip_id':cid,'track_id':track['id'],'is_main':is_main,
        'clock':transform.report(),'delta_tick':delta,'retimed_members':reports,
        'shared_author_context':copy.deepcopy(shared['report']) if shared else None,
        'tracking_binding_changes':copy.deepcopy(draft.binding_changes),
        'new_tracks':draft.new_tracks,'changes':_plan_changes(draft.original,draft.sequence)}


def build_retime_plan(project, sequence_id, request):
    sequence = next((s for s in project['sequences'] if s['id']==sequence_id),None)
    if sequence is None:
        _error('EDIT_SEQUENCE_NOT_FOUND','找不到编辑序列')
    query = normalize(sequence,request)
    rows = {c['id']:(t,c) for t in sequence['tracks'] for c in t['clips']}
    if any(cid not in rows for cid in query['clip_ids']):
        _error('EDIT_CLIP_NOT_FOUND','找不到 retime 片段')
    ids = set(query['clip_ids'])
    main_id = query['options']['main_track_id']
    is_main = {rows[cid][0]['id']==main_id for cid in ids}
    if len(is_main)>1:
        _error('EDIT_RETIME_MIXED_SELECTION','retime 不能混合选择主副轨；关联素材由规划器扩展')
    main = is_main=={True}
    if main and query['options']['linked']:
        links = {rows[k][1].get('link_id') for k in ids}-{None}
        ids.update(k for k,(t,c) in rows.items() if t['id']==main_id and c.get('link_id') in links)
    elif not main and len(ids)>1:
        # Each independent side selection owns its own complete output clock.
        # Shared members are handled once; inconsistent overlap is not guessed.
        links = [rows[k][1].get('link_id') for k in ids]
        if query['options']['linked'] and len([v for v in links if v])!=len(set(v for v in links if v)):
            _error('EDIT_RETIME_DUPLICATE_GROUP','同一副轨关联组只选一个宿主')
    candidate = project
    steps = []
    for cid in sorted(ids,key=lambda k:(start(rows[k][1]),k),reverse=True):
        candidate,step = _one(candidate,sequence_id,cid,query,main_selection=ids if main else set())
        steps.append(step)
    target = next(s for s in candidate['sequences'] if s['id']==sequence_id)
    return candidate, {'engine':ENGINE,'base_project_sha256':project_fingerprint(project),
        'sequence_id':sequence_id,'request':query,'expanded_clip_ids':sorted(ids),
        'before_duration_tick':sequence['duration_tick'],'after_duration_tick':target['duration_tick'],
        'short_tick':0,
        'steps':steps,'changes':_plan_changes(sequence,target),
        'created_sequences':[copy.deepcopy(s) for s in candidate['sequences'] if s['id'] not in {q['id'] for q in project['sequences']}],
        'warnings':[],'limits':['relative-complete-visible-output-not-absolute-source-speed',
            'markers-and-root-automation-retain-absolute-clock','continuous-author-blend-parameters-at-display-CFR',
            'existing-tracking-transition-and-nonlinear-lane-boundaries-retained']}
