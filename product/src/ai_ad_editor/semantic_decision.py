"""Index-bound empirical rejection profiles; calibration is not a truth detector."""
from __future__ import annotations

import copy
import math
from pathlib import Path
import shutil

from .errors import AppError, argument_error
from .project import asset_map, create_snapshot, save_project
from .rights import active_records, add_record, load_ledger, save_ledger
from .semantic_contract import fingerprint, json_object, local_file
from .semantic_queries import QUERY_PROTOCOL, prepare, rank_clauses
from .semantic_sampling import owned, remaining
from .semantic_jobs import managed, current as current_job
from .utils import assert_id, atomic_write_json, new_id, now_iso, sha256_file

FORMAT = 'agent-semantic-acceptance-profile-v1'
DATASET_FORMAT = 'agent-semantic-calibration-set-v1'


def dataset(path, sources):
    value = json_object(path, max_bytes=1024**2)
    if set(value) != {'format', 'scope', 'queries'} or value['format'] != DATASET_FORMAT:
        raise argument_error('校准文件需要 format/scope/queries，不能夹带执行配置', 'input')
    if not isinstance(value['scope'], str) or not 1 <= len(value['scope'].strip()) <= 2048:
        raise argument_error('必须说明校准语料适用范围', 'scope')
    rows = value['queries']
    if not isinstance(rows, list) or not 32 <= len(rows) <= 128:
        raise argument_error('校准需要 32–128 项独立查询，正向/库外各至少 16 项', 'queries')
    ids, signatures, positives = set(), set(), 0
    for row in rows:
        if (not isinstance(row, dict) or not {'id', 'text', 'expected_asset_ids'} <= set(row)
                or set(row) - {'id', 'text', 'include', 'exclude', 'expected_asset_ids'}):
            raise argument_error('校准查询字段无效', 'queries')
        assert_id(row['id'], 'query_id')
        expected = row['expected_asset_ids']
        if (row['id'] in ids or not isinstance(expected, list) or len(expected) > len(sources)
                or any(not isinstance(v, str) or v not in sources for v in expected)
                or len(set(expected)) != len(expected)):
            raise argument_error('校准 ID/目标资产重复或不在当前索引内', 'queries')
        query = {k: v for k, v in row.items() if k != 'expected_asset_ids'}
        plans, _ = prepare([query])
        signature = fingerprint({key: [v.casefold() for v in plans[0][key]] for key in ('include', 'exclude')})
        if signature in signatures:
            raise argument_error('相同条件不能重复计入独立校准查询', 'queries')
        ids.add(row['id']); signatures.add(signature)
        positives += bool(expected)
    if positives < 16 or len(rows) - positives < 16:
        raise argument_error('正向和库外校准各需要至少 16 项', 'queries')
    return value


def fit(observations, *, false_accept_rate=.05, minimum_coverage=.75):
    """A predeclared order-statistic cutoff; never optimize on held-out results."""
    if (type(false_accept_rate) not in (int, float) or not math.isfinite(false_accept_rate)
            or not 0 <= false_accept_rate <= .25 or type(minimum_coverage) not in (int, float)
            or not math.isfinite(minimum_coverage) or not .5 <= minimum_coverage <= 1):
        raise argument_error('false-accept-rate 须为 0..0.25，minimum-coverage 须为 0.5..1', 'calibration')
    positives = [r for r in observations if r['expected_asset_ids']]
    negatives = [r for r in observations if not r['expected_asset_ids']]
    if len(positives) < 16 or len(negatives) < 16:
        raise argument_error('正向和库外校准各需要至少 16 项', 'calibration')
    # Exclusion-only rejections have score -1. The comparison at search is >.
    scores = sorted(r['score'] for r in negatives)
    if any(type(v) not in (int, float) or not math.isfinite(v) or not -1.00001 <= v <= 1.00001
           for v in [r['score'] for r in observations]):
        raise argument_error('校准分数必须是有限余弦值', 'calibration')
    permitted = math.floor(false_accept_rate * len(negatives))
    cutoff = scores[len(scores) - permitted - 1]
    accepted = lambda row: bool(row['top_asset_id'] is not None and row['score'] > cutoff)
    correct = sum(accepted(row) and row['top_asset_id'] in row['expected_asset_ids'] for row in positives)
    false = sum(accepted(row) for row in negatives)
    result = dict(algorithm='negative-order-statistic-strict-greater-v1', cutoff=cutoff,
        requested_false_accept_rate=false_accept_rate, requested_minimum_correct_coverage=minimum_coverage,
        positive_count=len(positives), negative_count=len(negatives), accepted_correct_positives=correct,
        correct_positive_coverage=correct / len(positives), false_accepted_negatives=false,
        observed_false_accept_rate=false / len(negatives),
        quality_gate_passed=correct / len(positives) >= minimum_coverage and false <= permitted,
        guarantee='empirical calibration only; no distribution-free, probability or universal no-match guarantee')
    return result


def load_profile(root, project, calibration_id, manifest, *, kind):
    from . import semantic
    try:
        matches = [r for r in semantic.registry(project).get('calibrations', [])
                   if r.get('calibration_id') == calibration_id]
        if len(matches) != 1:
            raise ValueError('Missing or duplicate calibration ID')
        record = matches[0]
        if record['sha256'] != fingerprint({k: v for k, v in record.items() if k != 'sha256'}):
            raise ValueError('Calibration registration changed')
        assets = asset_map(project)
        asset = assets[record['asset_id']]
        path = local_file(asset['uri'], root=root)
        if not path.is_relative_to(owned(root, root/'assets/semantic-calibration')):
            raise ValueError('Profile outside owned calibration directory')
        if 'sha256:' + sha256_file(path) != record['profile_sha256'] or asset['sha256'] != record['profile_sha256']:
            raise ValueError('Profile asset bytes/binding changed')
        profile = json_object(path, max_bytes=2*1024**2)
        if (profile['format'] != FORMAT or profile['query_protocol'] != QUERY_PROTOCOL
                or profile['calibration_id'] != calibration_id or profile['kind'] != kind
                or profile['index_fingerprint'] != manifest['fingerprint']
                or profile['adapter_sha256'] != manifest['adapter_sha256']
                or not profile['fit']['quality_gate_passed']
                or profile['fingerprint'] != fingerprint({k: v for k, v in profile.items() if k != 'fingerprint'})):
            raise ValueError('Profile scope/index/model/query protocol changed')
        cutoff = profile['fit']['cutoff']
        if type(cutoff) not in (int, float) or not math.isfinite(cutoff) or not -1.00001 <= cutoff <= 1.00001:
            raise ValueError('Invalid calibrated cutoff')
        source_asset = assets[record['dataset_asset_id']]
        source = local_file(source_asset['uri'], root=root)
        if (source != path.with_name('dataset.json') or source_asset['sha256'] != profile['dataset_sha256']
                or 'sha256:' + sha256_file(source) != profile['dataset_sha256']):
            raise ValueError('Calibration dataset bytes/binding changed')
        rights = {r['asset_id']: r for r in active_records(load_ledger(root))}
        for generated in (asset, source_asset):
            if rights.get(generated['rights_ref'], {}).get('sha256') != generated['sha256']:
                raise ValueError('Calibration rights binding missing')
        return profile
    except (KeyError, TypeError, ValueError, OSError, AttributeError) as exc:
        raise AppError('SEMANTIC_CALIBRATION_INVALID', '校准档案无效、过期或适用范围不符',
                       exit_code=6, cause=str(exc)) from exc


@managed('semantic-calibrate')
def calibrate(root, project, *, index_id, calibration_id, input_path, kind=None,
              false_accept_rate=.05, minimum_coverage=.75, device='auto', device_index=0,
              batch_size=8, timeout=600, cancel_file=None, dry_run=False):
    from . import semantic
    assert_id(calibration_id, 'calibration_id')
    if any(r.get('calibration_id') == calibration_id for r in semantic.registry(project).get('calibrations', [])):
        raise AppError('SEMANTIC_CALIBRATION_EXISTS', '校准 ID 已存在，请使用新的 ID', exit_code=2)
    deadline, marker = semantic._config(timeout, cancel_file, root, batch_size=batch_size, device_index=device_index)
    manifest, vectors, adapter = semantic.read_index(root, project, index_id)
    if kind not in (None, 'image', 'video'):
        raise argument_error('校准 kind 无效', 'kind')
    source = local_file(input_path, root=root)
    original_hash = 'sha256:' + sha256_file(source)
    allowed = {r['asset_id'] for r in manifest['rows'] if not kind or r['kind'] == kind}
    truth = dataset(source, allowed)
    queries = [{k: v for k, v in row.items() if k != 'expected_asset_ids'} for row in truth['queries']]
    plans, inputs = prepare(queries)
    # Validate numeric controls before any inference or derivative directory.
    fit([dict(expected_asset_ids=['x'] if i < 16 else [], score=0., top_asset_id='x') for i in range(32)],
        false_accept_rate=false_accept_rate, minimum_coverage=minimum_coverage)
    key = fingerprint(calibration_id).removeprefix('sha256:')[:24]
    destination = owned(root, root/'assets/semantic-calibration'/key)
    if destination.exists():
        raise AppError('SEMANTIC_CALIBRATION_EXISTS', '校准产物目录已存在，原内容保留', exit_code=2)
    if dry_run:
        return dict(index_id=index_id, calibration_id=calibration_id, queries=len(queries),
                    clauses=len(inputs), model_forward_calls=0, destination=str(destination))
    job = semantic._job(root)
    features, inference = semantic.embed(root, adapter, inputs, 'text', job=job, device=device,
        device_index=device_index, batch_size=batch_size, deadline=deadline, marker=marker)
    observations = []
    for row, plan in zip(truth['queries'], plans):
        hit = rank_clauses(vectors, features, manifest['rows'], plan, limit=1, kind=kind)
        observations.append(dict(id=row['id'], expected_asset_ids=row['expected_asset_ids'],
            top_asset_id=hit[0]['asset_id'] if hit else None,
            score=hit[0]['decision_score'] if hit else -1., clauses=plan))
    result = fit(observations, false_accept_rate=false_accept_rate, minimum_coverage=minimum_coverage)
    atomic_write_json(job/'calibration-fit.json', dict(fit=result, observations=observations, inference=inference))
    if not result['quality_gate_passed']:
        raise AppError('SEMANTIC_CALIBRATION_QUALITY_FAILED', '当前模型/素材库无法满足声明的校准覆盖门槛',
                       exit_code=6, diagnostics=dict(fit=result, evidence=str(job/'calibration-fit.json')))
    if original_hash != 'sha256:' + sha256_file(source):
        raise AppError('SEMANTIC_INPUT_CHANGED', '校准输入在执行期间改变', exit_code=6)
    ready = job/'ready'; ready.mkdir(exist_ok=False)
    try:
        shutil.copyfile(source, ready/'dataset.json')
        if 'sha256:' + sha256_file(ready/'dataset.json') != original_hash:
            raise AppError('SEMANTIC_INPUT_CHANGED', '校准输入在复制时改变', exit_code=6)
        profile = dict(format=FORMAT, calibration_id=calibration_id, index_id=index_id,
            index_fingerprint=manifest['fingerprint'], adapter_sha256=adapter['sha256'],
            query_protocol=QUERY_PROTOCOL, kind=kind, created_at=now_iso(), scope=truth['scope'],
            dataset_sha256=original_hash, device=inference['response']['device'],
            device_index=inference['response']['device_index'], fit=result,
            observations=observations, inference=inference, network='disabled')
        profile['fingerprint'] = fingerprint(profile)
        atomic_write_json(ready/'profile.json', profile)
        remaining(deadline, marker)
        current_job().publish_tree(ready, destination)
        assets, generated = asset_map(project), []
        for suffix, filename in (('profile', 'profile.json'), ('dataset', 'dataset.json')):
            path = destination/filename
            aid = 'scal_' + key + '_' + suffix
            if aid in assets:
                raise AppError('SEMANTIC_ASSET_EXISTS', '校准资产 ID 已存在', exit_code=2)
            generated.append(dict(id=aid, kind='generated', uri=path.relative_to(root).as_posix(),
                sha256='sha256:'+sha256_file(path), probe={}, rights_ref=aid,
                source=dict(semantic_calibration=calibration_id, source_url='local://semantic-calibration/'+calibration_id,
                            retrieved_at=now_iso())))
        record = dict(calibration_id=calibration_id, index_id=index_id, asset_id=generated[0]['id'],
            dataset_asset_id=generated[1]['id'], profile_sha256=generated[0]['sha256'],
            kind=kind, device=profile['device'], device_index=profile['device_index'], created_at=now_iso())
        record['sha256'] = fingerprint(record)
        ledger = load_ledger(root)
        for asset in generated:
            add_record(ledger, dict(asset_id=asset['rights_ref'], kind='semantic-calibration-evidence',
                sha256=asset['sha256'], source_url='local://semantic-calibration/'+calibration_id,
                source_version=FORMAT, retrieved_at=now_iso(), creator='Local calibration author',
                license_spdx='LicenseRef-Source-And-Model-Dependencies', license_url='', attribution='',
                permitted_uses=['internal'], permitted_channels=[], restrictions=[],
                derived_from=[semantic.item(project, 'indexes', index_id)['asset_id'], adapter['rights_ref']],
                evidence=generated[0]['uri'], verification_status='verified',
                verified_by='local-calibration-source-model-hash', takedown_status='clear',
                notes='Verified derivation; empirical cutoff does not verify semantics or grant source rights.'))
        candidate = copy.deepcopy(project); candidate.setdefault('assets', []).extend(generated)
        candidate['extensions']['local_semantic'].setdefault('calibrations', []).append(record)
        from .validator import validate_project
        validation = validate_project(root, candidate, rights_ledger=ledger, strict_rights=False)
        if not validation['ok']:
            raise AppError('SEMANTIC_PROJECT_INVALID', '校准登记后的工程校验失败', exit_code=2, diagnostics=validation)
        snapshot = create_snapshot(root, project, label='before-semantic-calibration')
        operation_id = new_id('op')
        candidate.setdefault('provenance', {}).setdefault('change_log', []).append(dict(
            command='semantic.calibrate', operation_id=operation_id, calibration_id=calibration_id,
            at=now_iso(), snapshot_id=snapshot['snapshot_id']))
        save_project(root, candidate); save_ledger(root, ledger)
        atomic_write_json(root/'operations'/f'{operation_id}.json', dict(command='semantic.calibrate',
            operation_id=operation_id, status='succeeded', calibration_id=calibration_id, job=str(job)))
        return dict(calibration=record, profile=profile, validation=validation, snapshot=snapshot,
                    operation_id=operation_id, network='disabled')
    except BaseException as exc:
        if isinstance(exc, OSError):
            raise AppError('SEMANTIC_CALIBRATION_IO_FAILED', '校准发布失败，事务与受管任务按身份核验恢复',
                           exit_code=6, cause=str(exc)) from exc
        raise
