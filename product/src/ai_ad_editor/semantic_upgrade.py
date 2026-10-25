"""Explicit runtime relocation for byte-identical semantic implementations.

Preserve old records. Fork adapters, indexes and profiles under new identities;
never convert changed implementations into a claim of compatible embeddings.
"""
from __future__ import annotations

from contextlib import ExitStack
import copy
import hashlib
from pathlib import Path
import shutil

from . import semantic
from .artifact_locks import artifact_entry, verification_scope, verification_summary
from .errors import AppError, argument_error
from .execution_control import ExecutionInterrupted, checkpoint, operation_budget
from .job_workspaces import managed_workspace
from .project import asset_map, create_snapshot, load_project, save_project
from .rights import add_record, load_ledger, record_for, save_ledger
from .semantic_contract import adapter_fingerprint, fingerprint, implementation_files, local_file, verify_adapter
from .semantic_decision import load_profile
from .semantic_sampling import owned
from .utils import assert_id, atomic_write_json, new_id, now_iso
from .validator import validate_project

FORMAT = 'agent-semantic-runtime-upgrade-v1'
MAX_COPY_BYTES = 512 * 1024**2


def add_parser(actions, leaf):
    parser = leaf(actions.add_parser('upgrade-semantic', help='逐字节核验相同实现，将旧语义工程显式派生到当前安装'))
    parser.add_argument('--project', required=True)
    parser.add_argument('--adapter-id', required=True)
    parser.add_argument('--new-adapter-id', required=True)
    parser.add_argument('--id-prefix', required=True)
    parser.add_argument('--index-id', action='append', help='可重复；默认迁移该适配器的全部索引及其校准')
    parser.add_argument('--timeout-seconds', type=float, default=600)
    parser.add_argument('--cancel-file')


def fail(message, *, path=None, code='SEMANTIC_UPGRADE_INVALID'):
    raise AppError(code, message, exit_code=6, path=path)


def _rights(ledger, ident, checksum):
    record = record_for(ledger, ident)
    if not record or record.get('sha256') != checksum:
        fail('原语义记录与有效权利摘要不匹配', path=ident)
    return record


def _target_adapter(old, ident, ledger):
    if old.get('sha256') != adapter_fingerprint(old):
        fail('原适配器指纹已改变')
    original_rights = _rights(ledger, old['rights_ref'], old['sha256'])
    entries = old.get('artifacts')
    if not isinstance(entries, list) or not all(isinstance(row, dict) for row in entries):
        fail('原适配器缺少文件清单')
    previous = [row for row in entries if row.get('role') == 'implementation']
    current = [artifact_entry(path, 'implementation') for path in implementation_files()]
    by_name = {Path(row.get('path', '')).name: row for row in previous}
    if len(previous) != len(by_name) or set(by_name) != {Path(row['path']).name for row in current}:
        fail('语义实现文件集改变，必须重新登记/构建索引', code='SEMANTIC_UPGRADE_REBUILD_REQUIRED')
    if len({str(Path(row['path']).parent) for row in previous}) != 1:
        fail('原实现文件不属于同一安装目录')
    for observed in current:
        pinned = by_name[Path(observed['path']).name]
        if any(pinned.get(key) != observed[key] for key in ('bytes', 'sha256')):
            fail('语义实现字节已改变，拒绝复用旧向量', path=Path(observed['path']).name,
                 code='SEMANTIC_UPGRADE_REBUILD_REQUIRED')
    target = copy.deepcopy(old)
    target.update(adapter_id=ident, rights_ref='semantic_adapter_'+ident, registered_at=now_iso())
    target['artifacts'] = [copy.deepcopy(row) for row in entries if row.get('role') != 'implementation'] + current
    # The native worker imports NumPy/Pillow from the current application's
    # site directory. Their exact pinned bytes must move with that directory,
    # while separately installed Python/Torch/model dependencies stay external.
    old_site = Path(previous[0]['path']).parent.parent
    new_site = Path(current[0]['path']).parent.parent
    relocated = {}
    for row in target.get('runtime_artifacts', []):
        source = Path(row['path'])
        if source.is_relative_to(old_site) and old_site != new_site:
            destination = new_site/source.relative_to(old_site)
            try:
                observed = artifact_entry(local_file(destination), 'runtime')
            except ExecutionInterrupted:
                raise
            except (AppError, OSError):
                fail('当前安装缺少原生依赖副本：'+str(destination), code='SEMANTIC_UPGRADE_DEPENDENCY_CHANGED')
            if any(observed[key] != row.get(key) for key in ('bytes', 'sha256')):
                fail('当前安装的原生依赖字节已改变', path=str(destination), code='SEMANTIC_UPGRADE_DEPENDENCY_CHANGED')
            relocated[row['path']] = observed
    target['runtime_artifacts'] = [copy.deepcopy(relocated.get(row['path'], row)) for row in target['runtime_artifacts']]
    target['artifacts'] = [copy.deepcopy(relocated.get(row['path'], row)) if row['role'] == 'runtime' else row
                           for row in target['artifacts']]
    target['runtime_modules'] = {name: relocated[path]['path'] if path in relocated else path
                                 for name, path in target['runtime_modules'].items()}
    target['sha256'] = adapter_fingerprint(target)
    checked = verify_adapter(target)
    if not checked['ok']:
        fail('模型、Python、原生依赖或证据不符合原 pin：'+checked['message'],
             code='SEMANTIC_UPGRADE_DEPENDENCY_CHANGED')
    target['runtime_upgrade'] = dict(format=FORMAT, from_adapter_id=old['adapter_id'],
        from_adapter_sha256=old['sha256'], implementation_files=len(current),
        implementation_bytes_identical=True, external_dependency_bytes_identical=True,
        relocated_bundled_runtime_files=len(relocated),
        old_installation_required=False, new_model_forwards=0)
    return target, original_rights


def _fork_rights(ledger, original, ident, checksum, evidence, dependencies):
    record = copy.deepcopy(original)
    for key in ('record_id', 'record_version', 'recorded_at', 'active'):
        record.pop(key, None)
    record.update(asset_id=ident, sha256=checksum, evidence=evidence, retrieved_at=now_iso(),
        derived_from=list(dict.fromkeys([original['asset_id'], *dependencies])),
        notes=str(original.get('notes', ''))+' Explicit byte-identical semantic runtime relocation; original record retained.')
    add_record(ledger, record)


def _ident(prefix, role, original):
    return prefix+'_'+role+'_'+fingerprint(original).removeprefix('sha256:')[:20]


def _fork_asset(original, ident, uri, checksum, mapping):
    result = copy.deepcopy(original)
    result.update(id=ident, rights_ref=ident, uri=uri, sha256=checksum)
    result.setdefault('source', {})['runtime_upgrade'] = mapping
    return result


def _copy(source, destination, checksum):
    digest = hashlib.sha256()
    destination.parent.mkdir(parents=True, exist_ok=True)
    with source.open('rb') as reader, destination.open('xb') as writer:
        while chunk := reader.read(1024**2):
            checkpoint()
            digest.update(chunk); writer.write(chunk)
    checkpoint(force=True)
    if 'sha256:'+digest.hexdigest() != checksum:
        fail('复制期间原语义产物发生变化', path=str(source))


def upgrade(root, project, *, adapter_id, new_adapter_id, prefix, index_ids=None, dry_run=False):
    assert_id(adapter_id, 'adapter_id'); assert_id(new_adapter_id, 'new_adapter_id'); assert_id(prefix, 'id_prefix')
    if len(prefix) > 32 or len(new_adapter_id) > 64:
        raise argument_error('id-prefix 最长 32，new-adapter-id 最长 64 字符', 'id_prefix')
    registered = semantic.registry(project)
    registered_index_ids = {row.get('index_id') for row in registered.get('indexes', [])}
    if any(row.get('index_id') not in registered_index_ids for row in registered.get('calibrations', [])):
        fail('存在孤立校准，必须先明确修复其索引关系')
    if any(row.get('adapter_id') == new_adapter_id for row in registered.get('adapters', [])):
        fail('目标适配器 ID 已存在，原内容保留', code='SEMANTIC_UPGRADE_TARGET_EXISTS')
    ledger = load_ledger(root)
    original = semantic.item(project, 'adapters', adapter_id)
    target, model_rights = _target_adapter(original, new_adapter_id, ledger)
    indexes = [row for row in registered.get('indexes', []) if row.get('adapter_id') == adapter_id]
    if index_ids is not None:
        if (not isinstance(index_ids, list) or len(index_ids) != len(set(index_ids))
                or any(ident not in {row['index_id'] for row in indexes} for ident in index_ids)):
            fail('索引选择重复、不存在或不属于原适配器')
        indexes = [row for row in indexes if row['index_id'] in index_ids]
    if len(indexes) > 32 or len({row.get('index_id') for row in indexes}) != len(indexes):
        fail('索引重复或超出单次 32 项预算')
    selected = {row['index_id'] for row in indexes}
    profiles = [row for row in registered.get('calibrations', []) if row.get('index_id') in selected]
    if len(profiles) > 64 or len({row.get('calibration_id') for row in profiles}) != len(profiles):
        fail('校准重复或超出单次 64 项预算')
    assets = asset_map(project)
    index_plans, profile_plans, copy_bytes, rows = [], [], 0, 0
    for record in indexes:
        manifest, _, _ = semantic.read_index_payload(root, project, record['index_id'])
        name = _ident(prefix, 'i', record['index_id'])
        key = fingerprint(name).removeprefix('sha256:')[:24]
        destination = owned(root, root/'assets/semantic'/key)
        if destination.exists() or any(row.get('index_id') == name for row in registered.get('indexes', [])):
            fail('派生索引已存在，原内容保留', code='SEMANTIC_UPGRADE_TARGET_EXISTS')
        identifiers = [record['asset_id'], record['vector_asset_id'], *record['frame_asset_ids']]
        for ident in identifiers:
            _rights(ledger, assets[ident]['rights_ref'], assets[ident]['sha256'])
            if ident != record['asset_id']:
                copy_bytes += local_file(assets[ident]['uri'], root=root).stat().st_size
        rows += len(manifest['rows'])
        index_plans.append(dict(record=record, manifest=manifest, id=name, key=key, destination=destination))
    for record in profiles:
        previous = next(row for row in index_plans if row['record']['index_id'] == record['index_id'])
        for ident in (record['asset_id'], record['dataset_asset_id']):
            asset = assets[ident]
            observed = artifact_entry(local_file(asset['uri'], root=root), 'semantic-upgrade-input')
            if observed['sha256'] != asset['sha256']:
                fail('原校准文件字节已改变', path=ident)
        profile = load_profile(root, project, record['calibration_id'], previous['manifest'], kind=record['kind'])
        name = _ident(prefix, 'c', record['calibration_id'])
        key = fingerprint(name).removeprefix('sha256:')[:24]
        destination = owned(root, root/'assets/semantic-calibration'/key)
        if destination.exists() or any(row.get('calibration_id') == name for row in registered.get('calibrations', [])):
            fail('派生校准已存在，原内容保留', code='SEMANTIC_UPGRADE_TARGET_EXISTS')
        copy_bytes += local_file(assets[record['dataset_asset_id']]['uri'], root=root).stat().st_size
        profile_plans.append(dict(record=record, profile=profile, id=name, key=key, destination=destination, index=previous))
    if rows > 4096 or copy_bytes > MAX_COPY_BYTES:
        fail('单次派生最多 4096 预览/512MiB；请明确分批选择 index-id')
    free = shutil.disk_usage(root).free
    if free < 256*1024**2 + copy_bytes*2:
        fail('磁盘不足以保留原数据并原子派生新数据', code='SEMANTIC_UPGRADE_DISK_BUDGET')
    job_root = owned(root, root/'cache/managed-jobs')
    occupied = sum(1 for _ in job_root.iterdir()) if job_root.exists() else 0
    if occupied + len(index_plans) + len(profile_plans) > 256:
        fail('受管任务预算不足；先预览并明确清理可回收任务', code='SEMANTIC_UPGRADE_JOB_BUDGET')
    summary = dict(format=FORMAT, source_adapter_id=adapter_id, adapter=target,
        implementation_bytes_identical=True, index_mappings=[dict(source=row['record']['index_id'], target=row['id']) for row in index_plans],
        calibration_mappings=[dict(source=row['record']['calibration_id'], target=row['id']) for row in profile_plans],
        copied_payload_bytes=copy_bytes, preview_rows=rows, model_forward_calls=0, network='disabled',
        original_records_preserved=True, cutoff_and_observations_preserved=True)
    checkpoint(force=True)
    if dry_run:
        return summary
    candidate = copy.deepcopy(project); candidate_registry = candidate['extensions']['local_semantic']
    candidate_registry['adapters'].append(target)
    _fork_rights(ledger, model_rights, target['rights_ref'], target['sha256'], model_rights.get('evidence'), [])
    generated = []

    def register_asset(original_asset, ident, path, checksum, dependency):
        if ident in assets or any(row['id'] == ident for row in generated):
            fail('派生资产 ID 已存在', code='SEMANTIC_UPGRADE_TARGET_EXISTS', path=ident)
        relative = path.relative_to(root).as_posix()
        generated.append(_fork_asset(original_asset, ident, relative, checksum,
            dict(format=FORMAT, source_asset_id=original_asset['id'], adapter_id=new_adapter_id)))
        _fork_rights(ledger, _rights(ledger, original_asset['rights_ref'], original_asset['sha256']),
            ident, checksum, relative, dependency)

    jobs = []
    with ExitStack() as stack:
        def new_job(kind):
            job = stack.enter_context(managed_workspace(root, kind))
            job.hold_for_review('Explicit semantic runtime upgrade; old records retained, no model forwards.')
            jobs.append(dict(job_id=job.path.name, kind=job.record['kind'], path=str(job.path)))
            return job
        for plan in index_plans:
            index_job = new_job('semantic-index')
            old, manifest = plan['record'], copy.deepcopy(plan['manifest'])
            stage = index_job.path/('ready-'+plan['key']); stage.mkdir()
            destination = plan['destination']; generated_frames = []
            for i, row in enumerate(manifest['rows']):
                original_frame = assets[row['preview_asset_id']]
                ident = 'sup_'+plan['key']+'_f'+str(i)
                relative = Path('frames')/(str(i).zfill(6)+'.png')
                _copy(local_file(original_frame['uri'], root=root), stage/relative, row['preview_sha256'])
                row.update(preview_asset_id=ident, preview_uri=(destination/relative).relative_to(root).as_posix())
                register_asset(original_frame, ident, destination/relative, row['preview_sha256'], [target['rights_ref']])
                generated_frames.append(ident)
            original_vector = assets[old['vector_asset_id']]
            _copy(local_file(original_vector['uri'], root=root), stage/'vectors.f32', manifest['vectors']['sha256'])
            manifest.update(index_id=plan['id'], adapter_id=new_adapter_id, adapter_sha256=target['sha256'], created_at=now_iso(),
                runtime_upgrade=dict(format=FORMAT, original_index_id=old['index_id'], original_fingerprint=plan['manifest']['fingerprint'],
                    original_adapter_sha256=original['sha256'], original_inference_retained=True, new_model_forwards=0))
            manifest['vectors']['uri'] = (destination/'vectors.f32').relative_to(root).as_posix()
            manifest['fingerprint'] = fingerprint({key: value for key, value in manifest.items() if key != 'fingerprint'})
            atomic_write_json(stage/'index.json', manifest)
            index_job.publish_tree(stage, destination)
            index_id, vector_id = 'sup_'+plan['key']+'_index', 'sup_'+plan['key']+'_vectors'
            checksum = artifact_entry(destination/'index.json', 'semantic-index')['sha256']
            register_asset(assets[old['asset_id']], index_id, destination/'index.json', checksum, [target['rights_ref']])
            register_asset(original_vector, vector_id, destination/'vectors.f32', manifest['vectors']['sha256'], [target['rights_ref']])
            record = copy.deepcopy(old)
            record.update(index_id=plan['id'], adapter_id=new_adapter_id, adapter_sha256=target['sha256'], asset_id=index_id,
                vector_asset_id=vector_id, frame_asset_ids=generated_frames, manifest_sha256=checksum, created_at=now_iso())
            record['sha256'] = fingerprint({key: value for key, value in record.items() if key != 'sha256'})
            candidate_registry['indexes'].append(record); plan['new_manifest'] = manifest; plan['new_record'] = record
        for plan in profile_plans:
            calibration_job = new_job('semantic-calibrate')
            old, profile = plan['record'], copy.deepcopy(plan['profile'])
            stage = calibration_job.path/('ready-'+plan['key']); stage.mkdir()
            destination = plan['destination']
            original_dataset = assets[old['dataset_asset_id']]
            _copy(local_file(original_dataset['uri'], root=root), stage/'dataset.json', profile['dataset_sha256'])
            profile.update(calibration_id=plan['id'], index_id=plan['index']['id'], index_fingerprint=plan['index']['new_manifest']['fingerprint'],
                adapter_sha256=target['sha256'], created_at=now_iso(), runtime_upgrade=dict(format=FORMAT,
                    original_calibration_id=old['calibration_id'], original_fingerprint=plan['profile']['fingerprint'],
                    new_model_forwards=0, cutoff_and_observations_preserved=True))
            profile['fingerprint'] = fingerprint({key: value for key, value in profile.items() if key != 'fingerprint'})
            atomic_write_json(stage/'profile.json', profile)
            calibration_job.publish_tree(stage, destination)
            profile_id, dataset_id = 'sup_'+plan['key']+'_profile', 'sup_'+plan['key']+'_dataset'
            checksum = artifact_entry(destination/'profile.json', 'semantic-calibration')['sha256']
            register_asset(assets[old['asset_id']], profile_id, destination/'profile.json', checksum,
                [plan['index']['new_record']['asset_id'], target['rights_ref']])
            register_asset(original_dataset, dataset_id, destination/'dataset.json', profile['dataset_sha256'],
                [plan['index']['new_record']['asset_id'], target['rights_ref']])
            record = copy.deepcopy(old)
            record.update(calibration_id=plan['id'], index_id=plan['index']['id'], asset_id=profile_id, dataset_asset_id=dataset_id,
                profile_sha256=checksum, created_at=now_iso())
            record['sha256'] = fingerprint({key: value for key, value in record.items() if key != 'sha256'})
            candidate_registry.setdefault('calibrations', []).append(record)
        candidate.setdefault('assets', []).extend(generated)
        validation = validate_project(root, candidate, rights_ledger=ledger, strict_rights=False)
        if not validation['ok']:
            raise AppError('SEMANTIC_UPGRADE_PROJECT_INVALID', '升级后的候选工程校验失败', exit_code=2, diagnostics=validation)
        for plan in index_plans:
            semantic.read_index_payload(root, candidate, plan['id'])
        # Profile verification needs the candidate ledger. Save within the outer
        # project transaction, then check before its commit; failures roll back.
        snapshot = create_snapshot(root, project, label='before-semantic-runtime-upgrade')
        operation_id = new_id('op')
        candidate.setdefault('provenance', {}).setdefault('change_log', []).append(dict(command='project.upgrade-semantic',
            at=now_iso(), operation_id=operation_id, snapshot_id=snapshot['snapshot_id'],
            source_adapter_id=adapter_id, target_adapter_id=new_adapter_id,
            index_mappings=summary['index_mappings'], calibration_mappings=summary['calibration_mappings']))
        checkpoint(force=True)
        save_project(root, candidate); save_ledger(root, ledger)
        for plan in profile_plans:
            load_profile(root, candidate, plan['id'], plan['index']['new_manifest'], kind=plan['record']['kind'])
        atomic_write_json(root/'operations'/f'{operation_id}.json', dict(command='project.upgrade-semantic',
            operation_id=operation_id, status='succeeded', source_adapter_id=adapter_id, target_adapter_id=new_adapter_id,
            index_mappings=summary['index_mappings'], calibration_mappings=summary['calibration_mappings'], jobs=jobs))
        checkpoint(force=True)
    return {**summary, 'snapshot': snapshot, 'operation_id': operation_id, 'managed_workspaces': jobs, 'validation': validation}


def command(args, envelope):
    root, project = load_project(args.project)
    with verification_scope(), operation_budget(args.timeout_seconds, args.cancel_file, root=root):
        result = upgrade(root, project, adapter_id=args.adapter_id, new_adapter_id=args.new_adapter_id,
            prefix=args.id_prefix, index_ids=args.index_id, dry_run=args.dry_run)
        result['verification_scope'] = verification_summary()
    return envelope('project.upgrade-semantic', args, data=result, status='planned' if args.dry_run else 'succeeded',
        operation_id=result.get('operation_id'))
