"""Project-aware neural music, explicit adapters and editable generation recipes."""
import copy
import json
import math
from pathlib import Path

from .artifact_locks import verification_scope
from .errors import argument_error
from .job_workspaces import managed_workspace
from .local_music_generation import ENGINE, PROTOCOL, error, prepare_adapter, prepare_request, validate_recipe, verify_adapter
from .model_registry import load_model_registry, save_model_registry, adapter_for
from .native_audio_clock import cancel
from .policy import resolve_local_path
from .project import load_project, asset_map, find_sequence, find_track, create_snapshot, save_project
from .rights import load_ledger, save_ledger, active_records, add_record
from .utils import assert_id, atomic_write_json, now_iso, new_id


def add_parser(actions, leaf):
    group = actions.add_parser('generator-adapter', help='登记离线原生ACE-Step1.5模型与核心代码')
    registrations = group.add_subparsers(dest='adapter_action', required=True)
    for action in ('register', 'list', 'inspect'):
        parser = leaf(registrations.add_parser(action))
        parser.add_argument('--project', required=True)
        if action != 'list':
            parser.add_argument('--adapter-id', required=True)
        if action == 'register':
            for field in ('model-path', 'runtime-root', 'executable', 'evidence'):
                parser.add_argument('--' + field, required=True)
            parser.add_argument('--threads', type=int, default=4)
            parser.add_argument('--creator', default='unknown')
            parser.add_argument('--license-spdx', default='LicenseRef-UNVERIFIED')
            parser.add_argument('--license-url', default='')
            parser.add_argument('--permitted-use', action='append', default=['internal'])
            parser.add_argument('--verification-status', choices=['unverified', 'verified', 'restricted'], default='unverified')
    parser = leaf(actions.add_parser('inspect-generation', help='校验神经音乐提示、歌词、时钟和生成参数'))
    parser.add_argument('--input', required=True)
    parser = leaf(actions.add_parser('generate', help='实际原生CUDA神经音乐；独立Float32音频与可编辑请求'))
    parser.add_argument('--project', required=True)
    parser.add_argument('--adapter-id', required=True)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--input', help='agent-neural-music-v1本地JSON')
    source.add_argument('--recipe-asset-id', help='使用已有资产中保持不变的请求重新生成')
    parser.add_argument('--new-asset-id', required=True)
    parser.add_argument('--storage-budget-mib', type=int, default=2048)
    parser.add_argument('--timeout-seconds', type=float, default=1800.,
                        help='工作进程与输出核验的总秒数；不含登记及命令预检')
    parser.add_argument('--cancel-file')
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--sequence-id')
    parser.add_argument('--track-id')
    parser.add_argument('--timeline-start-seconds', type=float, default=0.)


def read_request(path, root):
    file = resolve_local_path(root, path, field='input')
    if not file.is_file() or file.stat().st_size > 128 * 1024:
        raise argument_error('要求至多128KiB的本地UTF-8音乐请求JSON')
    try:
        return prepare_request(json.loads(file.read_text(encoding='utf-8-sig')))
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise argument_error('音乐请求JSON不可读取') from exc


def inspect_command(args):
    from .cli import _envelope
    value = read_request(args.input, Path.cwd())
    return _envelope('music.inspect-generation', args, data=dict(engine=ENGINE, request=value,
        sample_rate=48000, channels=2, samples=round(value['duration_seconds'] * 48000), model_inference_executed=False))


def adapter_command(args):
    from .cli import _envelope, _operation
    with verification_scope():
        root, project = load_project(args.project)
        registry = load_model_registry(root)
        if args.adapter_action == 'list':
            return _envelope('music.generator-adapter.list', args, data=dict(adapters=[a for a in registry['adapters'] if a.get('engine') == ENGINE]))
        existing = adapter_for(registry, args.adapter_id)
        if args.adapter_action == 'inspect':
            if not existing or existing.get('engine') != ENGINE:
                raise error('ADAPTER_MISSING', '找不到神经音乐适配器')
            return _envelope('music.generator-adapter.inspect', args, data=dict(adapter=existing, verification=verify_adapter(existing)))
        if existing:
            raise error('ADAPTER_EXISTS', '适配器ID已存在，须使用新ID')
        adapter, rights = prepare_adapter(root, adapter_id=args.adapter_id, model_path=args.model_path,
            runtime_root=args.runtime_root, executable=args.executable, evidence=args.evidence,
            creator=args.creator, license_spdx=args.license_spdx, license_url=args.license_url,
            permitted_uses=args.permitted_use, verification_status=args.verification_status, threads=args.threads)
        if args.dry_run:
            return _envelope('music.generator-adapter.register', args, status='planned', data=dict(adapter=adapter, rights=rights))
        snapshot = create_snapshot(root, copy.deepcopy(project), label='before-music-adapter-register')
        operation = new_id('op')
        ledger = load_ledger(root)
        registry['adapters'].append(adapter)
        add_record(ledger, rights)
        save_model_registry(root, registry)
        save_ledger(root, ledger)
        project['provenance'].setdefault('local_adapters', []).append(dict(adapter_id=args.adapter_id,
            kind='music-generation', engine=ENGINE, model_sha256=adapter['model_sha256'], registered_at=adapter['registered_at']))
        project['provenance']['change_log'].append(dict(command='music.generator-adapter.register', operation_id=operation, at=now_iso()))
        save_project(root, project)
        _operation(root, operation, dict(command='music.generator-adapter.register', status='succeeded', snapshot_id=snapshot['snapshot_id'], created_at=now_iso()))
        return _envelope('music.generator-adapter.register', args, data=dict(adapter=adapter, rights=rights), operation_id=operation)


def generate_command(args):
    from .cli import _envelope, _operation, _progress, _recompute_sequence_duration
    from .validator import validate_project
    with verification_scope():
        root, project = load_project(args.project)
        assets = asset_map(project)
        assert_id(args.new_asset_id, 'new-asset-id')
        if not math.isfinite(args.timeout_seconds) or not 0 < args.timeout_seconds <= 7200:
            raise argument_error('timeout-seconds须为0..7200正秒数')
        if type(args.storage_budget_mib) is not int or not 64 <= args.storage_budget_mib <= 8192:
            raise argument_error('storage-budget-mib须为64..8192整数')
        if not math.isfinite(args.timeline_start_seconds) or args.timeline_start_seconds < 0 or bool(args.apply) != bool(args.track_id):
            raise argument_error('须明确--apply及独立音轨；时间线起点须为非负有限值')
        marker = resolve_local_path(root, args.cancel_file, field='cancel-file') if args.cancel_file else None
        cancel(marker)
        previous = None
        if args.recipe_asset_id:
            parent = assets.get(args.recipe_asset_id)
            if not parent or not (previous := parent.get('source', {}).get('music_generation')):
                raise error('RECIPE_MISSING', '指定资产没有神经音乐配方')
            validate_recipe(previous, asset=parent)
            generation = previous['request']
        else:
            generation = read_request(args.input, root)
        adapter = adapter_for(load_model_registry(root), args.adapter_id)
        if not adapter or adapter.get('engine') != ENGINE or not verify_adapter(adapter)['ok']:
            raise error('ADAPTER_UNAVAILABLE', '要求显式登记且完整字节匹配的ACE-Step1.5适配器')
        if previous and (previous['model_sha256'] != adapter['model_sha256'] or previous['runtime_sha256'] != adapter['runtime_sha256']):
            raise error('RECIPE_MODEL', '配方重跑须使用相同模型和运行时代码字节')
        ledger = load_ledger(root)
        rights = {r['asset_id']:r for r in active_records(ledger)}
        if args.new_asset_id in assets or args.new_asset_id in rights:
            raise error('OUTPUT_EXISTS', '输出资产ID已存在，须使用新ID')
        parent_rights = rights.get(adapter['rights_ref'])
        if not parent_rights or parent_rights['sha256'] != adapter['sha256']:
            raise error('RIGHTS_MISSING', '模型缺少摘要匹配的来源与权利记录')
        sequence = find_sequence(project, args.sequence_id)
        track = find_track(sequence, args.track_id) if args.apply else None
        tps = project['settings']['timebase']['ticks_per_second']
        start = round(args.timeline_start_seconds * tps)
        span = round(generation['duration_seconds'] * tps)
        if track and (track.get('locked') or track['kind'] != 'audio'):
            raise argument_error('音乐生成须选择未锁定的独立音频轨道')
        if track and track.get('overlap_policy', 'reject') != 'allow' and any(max(start, c['timeline_start_tick']) < min(start + span, c['timeline_start_tick'] + c['duration_tick']) for c in track['clips']):
            raise argument_error('神经音乐入轨区间与已有片段重叠')
        output = root / 'assets/derived' / (args.new_asset_id + '.wav')
        if output.exists():
            raise error('OUTPUT_EXISTS', '输出文件已存在，不能覆盖')
        warnings = [dict(code='MUSIC_GENERATION_REVIEW_REQUIRED', message='须试听风格、结构、歌词/发音和音量；提示遵循与输出权利须另行审核。种子不保证跨设备逐字节重现。')]
        if args.dry_run:
            return _envelope('music.generate', args, status='planned', warnings=warnings, data=dict(engine=ENGINE,
                request=generation, adapter_id=args.adapter_id, output=str(output), model_inference_executed=False,
                sample_rate=48000, channels=2, samples=round(generation['duration_seconds'] * 48000), apply=args.apply))
        snapshot = create_snapshot(root, copy.deepcopy(project), label='before-neural-music')
        operation = new_id('op')
        report_path = root / 'validation' / ('music_generation_' + operation + '.json')
        try:
            with managed_workspace(root, 'music-generation') as job:
                from .music_generation_pipeline import execute
                def progress(phase, done, total):
                    _progress(args, operation, 'progress', 'music.generate', min(95, round(90 * done / total)), phase)
                _progress(args, operation, 'started', 'music.generate', 0, '执行原生CUDA神经音乐生成')
                staged, result = execute(root, job, adapter, generation, storage_budget_bytes=args.storage_budget_mib * 1024**2,
                    timeout=args.timeout_seconds, cancel_file=marker, operation_id=operation, progress=progress)
                cancel(marker)
                job.publish(staged, output)
                generated = dict(id=args.new_asset_id, kind='audio', uri=output.relative_to(root).as_posix(),
                    sha256=result['sha256'], rights_ref=args.new_asset_id, probe=result['probe'],
                    source=dict(source_url='local://music-generation/' + operation, retrieved_at=now_iso(),
                                original_name=output.name, music_generation=result['recipe']))
                project['assets'].append(generated)
                record = dict(asset_id=args.new_asset_id, kind='audio', sha256=result['sha256'],
                    source_url=generated['source']['source_url'], source_version=PROTOCOL, retrieved_at=now_iso(),
                    creator='local-neural-music', license_spdx='LicenseRef-UNVERIFIED', license_url='', attribution='',
                    permitted_uses=['internal'], permitted_channels=[], restrictions=[], derived_from=[adapter['rights_ref']],
                    evidence='', verification_status='unverified', verified_by='', takedown_status='clear',
                    notes='Prompt/lyrics/model/runtime/output rights and listening quality require separate review.')
                add_record(ledger, record)
                save_ledger(root, ledger)
                clip = None
                if track:
                    clip = dict(id=new_id('clip_music'), asset_id=args.new_asset_id, timeline_start_tick=start,
                                duration_tick=span, source_in_tick=0, source_out_tick=span)
                    track['clips'].append(clip)
                    _recompute_sequence_duration(sequence)
                validation = validate_project(root, project)
                if not validation['ok']:
                    raise error('PROJECT_INVALID', '神经音乐入库后工程校验失败，事务回滚', validation=validation)
                report = dict(protocol=PROTOCOL, operation_id=operation, asset=generated, rights=record,
                              generation=result, clip=clip, snapshot_id=snapshot['snapshot_id'], validation=validation)
                atomic_write_json(report_path, report)
                project['provenance']['change_log'].append(dict(command='music.generate', operation_id=operation,
                    asset_id=args.new_asset_id, report=str(report_path), at=now_iso()))
                cancel(marker)
                save_project(root, project)
                _operation(root, operation, dict(command='music.generate', status='succeeded', report=str(report_path), created_at=now_iso()))
                _progress(args, operation, 'completed', 'music.generate', 100, '实际CUDA音乐及完整PCM入轨已核验')
                return _envelope('music.generate', args, data=report, warnings=warnings, operation_id=operation)
        except BaseException:
            report_path.unlink(missing_ok=True)
            raise
