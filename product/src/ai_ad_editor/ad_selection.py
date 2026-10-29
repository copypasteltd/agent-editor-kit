"""Joint, auditable visual selection for editable advertising storyboards.

The controller consumes actual calibrated search responses. A match is sampled
visual evidence, not proof of a whole shot's meaning or advertising quality.
"""
from __future__ import annotations

import copy
import json
import math

from . import ad_storyboard as storyboard
from .errors import AppError
from .execution_control import checkpoint
from .project import asset_map


def fail(message, **details):
    raise AppError('AD_SELECTION_INVALID', message, exit_code=2, diagnostics=details or None)



def content_identity(asset):
    """Exact registered source bytes, never a perceptual-similarity claim."""
    value = asset.get('sha256')
    if (not isinstance(value, str) or not value.startswith('sha256:') or len(value) != 71
            or any(c not in '0123456789abcdef' for c in value[7:])):
        fail('内容去重需要有效的素材 SHA256，不能回退为素材 ID', asset_id=asset.get('id'))
    return value


def prepare(project, payload):
    """Validate the complete storyboard before spending a model forward."""
    if not isinstance(payload, dict) or set(payload) - {'brief', 'queries', 'unique_assets', 'unique_content'}:
        fail('选材输入只接受 brief、queries、unique_assets、unique_content')
    unique = payload.get('unique_assets', True)
    if type(unique) is not bool:
        fail('unique_assets 必须为布尔值')
    unique_content = payload.get('unique_content', unique)
    if type(unique_content) is not bool:
        fail('unique_content 必须为布尔值')
    brief, queries = payload.get('brief'), payload.get('queries')
    if not isinstance(brief, dict) or not isinstance(queries, list) or not 1 <= len(queries) <= 50:
        fail('需要 brief 和 1..50 项镜头查询')
    shots = brief.get('shots')
    if not isinstance(shots, list) or any(not isinstance(s, dict) for s in shots):
        fail('brief.shots 必须为镜头对象数组')
    by_shot = {s.get('id'): s for s in shots if isinstance(s.get('id'), str)}
    if len(by_shot) != len(shots):
        fail('镜头 ID 缺失或重复')
    ids = set()
    for query in queries:
        if (not isinstance(query, dict) or not {'id', 'text'} <= set(query)
                or set(query) - {'id', 'text', 'include', 'exclude'}):
            fail('查询只接受 id/text/include/exclude')
        sid = query['id']
        if not isinstance(sid, str) or sid not in by_shot or sid in ids:
            fail('查询 ID 必须唯一且对应现有镜头')
        if (not isinstance(query['text'], str) or not query['text'].strip()
                or len(query['text']) > 1024):
            fail('查询文本必须为 1..1024 字符')
        try:
            receipt_text = json.dumps(dict(query=query, caller=by_shot[sid].get('rationale', '')),
                                      ensure_ascii=False, allow_nan=False)
        except (TypeError, ValueError):
            fail('查询与选材依据必须可序列化为有限 JSON')
        if len(receipt_text) > 6500:
            fail('查询与原依据超出可移植镜头记录预算', shot_id=sid)
        if any(k in by_shot[sid] for k in ('asset_id', 'source_in_tick')):
            fail('查询镜头不能同时指定 asset_id/source_in_tick', shot_id=sid)
        ids.add(sid)
    # Use an internal, non-emitted image sentinel solely to run the existing
    # duration/variant/caption contract. No sentinel media is opened or saved.
    provisional = copy.deepcopy(project)
    sentinel = '_ad_selection_placeholder'
    existing = asset_map(project)
    while sentinel in existing:
        sentinel += '_'
    provisional['assets'].append(dict(id=sentinel, kind='image', sha256='sha256:' + '0' * 64,
                                     probe={'audio': {'codec': 'planning-only-sentinel'}}))
    draft = copy.deepcopy(brief)
    for shot in draft['shots']:
        if shot['id'] in ids:
            shot['asset_id'] = sentinel
    variants = draft.get('variants')
    if isinstance(variants, list):
        for variant in variants:
            if not isinstance(variant, dict):
                continue
            overrides = variant.get('overrides', {})
            if isinstance(overrides, dict):
                for sid, patch in overrides.items():
                    if sid in ids and isinstance(patch, dict) and set(patch) & {'asset_id', 'source_in_tick'}:
                        fail('查询镜头的变体不能覆盖素材或来源起点', shot_id=sid)
    planned = storyboard.plan_storyboard(provisional, draft)
    durations, audio, reserved = {sid: 0 for sid in ids}, set(), set()
    for sequence in planned['sequences']:
        for track in sequence['tracks']:
            for clip in track['clips']:
                tag = clip.get('ad_storyboard', {})
                if tag.get('role') == 'picture' and tag.get('shot_id') in ids:
                    sid = tag['shot_id']
                    durations[sid] = max(durations[sid], clip['duration_tick'])
                elif tag.get('role') == 'picture':
                    reserved.add(clip['asset_id'])
                if tag.get('role') == 'source_audio' and tag.get('shot_id') in ids:
                    audio.add(tag['shot_id'])
    if not all(durations.values()):
        fail('每项查询必须至少用于一个变体')
    return dict(brief=copy.deepcopy(brief), queries=copy.deepcopy(queries),
                unique_assets=unique, unique_content=unique_content, required_duration_ticks=durations,
                required_source_audio=sorted(audio), reserved_assets=sorted(reserved))


def maximum_assignment(rows, *, unique=True):
    """Rectangular Hungarian assignment, integer costs, deterministic ties.

    Missing edges are prohibited. This avoids a greedy first shot consuming
    the only valid candidate of a later shot. Scores quantize at 1e-8 cosine.
    """
    if not rows or any(not row for row in rows):
        fail('至少一个镜头没有满足来源范围和权利条件的候选')
    if not unique:
        return [min(row, key=lambda aid: (-row[aid], aid)) for row in rows]
    assets = sorted({aid for row in rows for aid in row})
    n, m = len(rows), len(assets)
    if m < n:
        fail('不同素材不足以覆盖全部镜头；可明确设置 unique_assets=false')
    absent = 10**15
    costs = [[-round(row[aid] * 10**8) if aid in row else absent for aid in assets] for row in rows]
    u, v, p, way = [0]*(n+1), [0]*(m+1), [0]*(m+1), [0]*(m+1)
    for i in range(1, n+1):
        checkpoint()
        p[0], j0 = i, 0
        minimum, used = [absent*2]*(m+1), [False]*(m+1)
        while True:
            checkpoint()
            used[j0], i0 = True, p[j0]
            delta, j1 = absent*2, 0
            for j in range(1, m+1):
                if not used[j]:
                    cost = costs[i0-1][j-1] - u[i0] - v[j]
                    if cost < minimum[j]:
                        minimum[j], way[j] = cost, j0
                    if minimum[j] < delta:
                        delta, j1 = minimum[j], j
            for j in range(m+1):
                if used[j]:
                    u[p[j]] += delta
                    v[j] -= delta
                else:
                    minimum[j] -= delta
            j0 = j1
            if not p[j0]:
                break
        while j0:
            j1 = way[j0]
            p[j0], j0 = p[j1], j1
    chosen = [None]*n
    for j in range(1, m+1):
        if p[j]:
            chosen[p[j]-1] = assets[j-1]
    if any(aid not in row for aid, row in zip(chosen, rows)):
        fail('候选存在冲突，无法为每个镜头分配不同素材')
    return chosen


def resolve(project, prepared, search):
    """Bind calibrated, hash-checked candidates to exact storyboard windows."""
    if (not isinstance(search, dict) or search.get('task') != 'text'
            or search.get('query_mode') != 'clauses' or not search.get('calibration_id')
            or search.get('network') != 'disabled'):
        fail('自动选材需要 clauses 文本查询及匹配设备的校准档案')
    queries = prepared['queries']
    results = search.get('results')
    if not isinstance(results, list) or len(results) != len(queries):
        fail('检索返回的查询数量不匹配')
    assets, rows, candidates, rejected = asset_map(project), [], [], []
    unique_content = prepared['unique_content']
    reserved_content = {content_identity(assets[aid]) for aid in prepared['reserved_assets']} if unique_content else set()
    for query, result in zip(queries, results):
        checkpoint()
        if result.get('query') != query or result.get('calibration_id') != search['calibration_id']:
            fail('检索结果偏离原查询或校准档案')
        if result.get('decision') != 'calibrated_match':
            fail('镜头没有经过校准接受的候选', shot_id=query['id'], decision=result.get('decision'))
        hits = result.get('hits')
        if not isinstance(hits, list) or not 1 <= len(hits) <= 20:
            fail('检索候选数量无效')
        valid = {}
        for hit in hits:
            if not isinstance(hit, dict):
                fail('候选必须为对象')
            aid = hit.get('asset_id')
            asset = assets.get(aid) if isinstance(aid, str) else None
            if (asset is None or asset.get('kind') not in ('image', 'video')
                    or hit.get('source_sha256') != asset.get('sha256')):
                fail('候选来源已偏离当前素材摘要', asset_id=aid)
            score = hit.get('decision_score')
            if type(score) not in (int, float) or not math.isfinite(score) or not -1 <= score <= 1:
                fail('候选相似度必须为 -1..1 的有限数值')
            reference = hit.get('editable_reference', {})
            start = reference.get('source_in_tick')
            if (reference.get('asset_id') != aid or type(start) is not int or start < 0
                    or reference.get('point_sample_only') is not True):
                fail('候选必须具有真实点采样的可编辑来源引用')
            identity = content_identity(asset) if unique_content else None
            reason = None
            if hit.get('rights_verification_status') != 'verified':
                reason = 'rights_not_verified'
            if prepared['unique_assets'] and aid in prepared['reserved_assets']:
                reason = 'reserved_by_explicit_shot'
            elif unique_content and identity in reserved_content:
                reason = 'reserved_content_by_explicit_shot'
            if (query['id'] in prepared['required_source_audio']
                    and not asset.get('probe', {}).get('audio', {}).get('codec')):
                reason = 'source_audio_missing'
            duration = asset.get('probe', {}).get('duration_tick', 0)
            if asset['kind'] == 'video' and (type(duration) is not int
                    or start + prepared['required_duration_ticks'][query['id']] > duration):
                reason = 'source_too_short'
            if reason:
                rejected.append(dict(shot_id=query['id'], asset_id=aid, reason=reason))
                continue
            # Several samples may refer to one asset; keep the best usable
            # sample, then its earliest source tick on an exact score tie.
            old = valid.get(aid)
            if old is None or (-score, start) < (-old['decision_score'], old['editable_reference']['source_in_tick']):
                valid[aid] = copy.deepcopy(hit)
        candidates.append(valid)
        rows.append({aid: hit['decision_score'] for aid, hit in valid.items()})
    if unique_content:
        # One column per exact source hash. For each shot retain the highest
        # scoring usable alias; stable asset-ID then sample-clock tie breaks.
        representatives, grouped_rows = [], []
        for valid in candidates:
            by_content = {}
            for aid, hit in valid.items():
                key = content_identity(assets[aid])
                old_aid = by_content.get(key)
                rank = lambda name: (-valid[name]['decision_score'], name,
                                     valid[name]['editable_reference']['source_in_tick'])
                if old_aid is None or rank(aid) < rank(old_aid):
                    by_content[key] = aid
            representatives.append(by_content)
            grouped_rows.append({key:valid[aid]['decision_score'] for key,aid in by_content.items()})
        groups = maximum_assignment(grouped_rows, unique=True)
        chosen = [aliases[key] for aliases,key in zip(representatives, groups)]
    else:
        chosen = maximum_assignment(rows, unique=prepared['unique_assets'])
    brief, receipts = copy.deepcopy(prepared['brief']), []
    shots = {s['id']: s for s in brief['shots']}
    for query, valid, aid in zip(queries, candidates, chosen):
        hit = valid[aid]
        receipt = dict(shot_id=query['id'], query=copy.deepcopy(query), index_id=search['index_id'],
            calibration_id=search['calibration_id'], asset_id=aid, source_sha256=hit['source_sha256'],
            source_in_tick=hit['editable_reference']['source_in_tick'], decision_score=hit['decision_score'],
            required_duration_tick=prepared['required_duration_ticks'][query['id']],
            preview_asset_id=hit.get('preview_asset_id'), semantic_truth_verified=False,
            uniqueness_group=hit['source_sha256'] if unique_content else aid,
            scope='calibrated_sampled_visual_similarity_not_whole_shot_semantics')
        shot = shots[query['id']]
        shot.update(asset_id=aid, source_in_tick=receipt['source_in_tick'])
        # Preserve both caller rationale and a portable machine-readable
        # selection receipt inside the existing editable storyboard contract.
        shot['rationale'] = json.dumps(dict(caller=shot.get('rationale', ''), selection=receipt),
                                       ensure_ascii=False, separators=(',', ':'), allow_nan=False)
        receipts.append(receipt)
    plan = storyboard.plan_storyboard(project, brief)
    return plan, dict(selected=receipts, rejected=rejected, unique_assets=prepared['unique_assets'],
        unique_content=unique_content, content_identity='exact_source_sha256_not_perceptual_similarity',
        assignment='global_maximum_quantized_1e-8_cosine', semantic_truth_verified=False,
        whole_shot_content_requires_review=True, rights_checked_for_publication=False)
