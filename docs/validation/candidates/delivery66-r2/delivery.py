"""Candidate: verified installations and recoverable single-Skill delivery."""
from __future__ import annotations

import ast
from contextlib import contextmanager
import hashlib
import json
from pathlib import Path
import re
import uuid

from .errors import AppError
from .project import _atomic_write_bytes, _native_byte_lock
from .utils import atomic_write_json, run_process

FORMAT = 'agent-editor-skill-delivery-v2'
SKILL = 'skills/agent-ffmpeg-local-editor/'
CONFIG = 'local/agent-ffmpeg/runtime.json'
MANIFEST = 'agent-ffmpeg-local-install-manifest.json'
MAX_FILE = 32 * 1024**2
MAX_TOTAL = 128 * 1024**2
MAX_FILES = 512
ROLES = frozenset(('source-tests', 'installed-tests', 'package-replay', 'skill-entry', 'native-music'))
IN_PROGRESS = frozenset((b'{"release":"delivery-switch-in-progress"}\n',
                         b'{"release":"delivery-recovery-in-progress"}\n'))
RESERVED = frozenset(('con', 'prn', 'aux', 'nul', *(f'com{i}' for i in range(1, 10)),
                      *(f'lpt{i}' for i in range(1, 10))))


def failure(code, message, **details):
    return AppError('DELIVERY_' + code, message, exit_code=6, **details)


def require(condition, code, message, **details):
    if not condition:
        raise failure(code, message, **details)


def text(value, field):
    require(isinstance(value, str) and 0 < len(value) <= 4096, 'RECORD_INVALID',
            '交付字段须为有限非空字符串', path=field)
    return value


def digest(value, field):
    require(isinstance(value, str) and re.fullmatch(r'[0-9a-f]{64}', value),
            'RECORD_INVALID', '交付摘要须为小写SHA-256', path=field)
    return value


def size(value, field, *, maximum=MAX_FILE):
    require(type(value) is int and 0 <= value <= maximum, 'RECORD_INVALID',
            '交付大小须为预算内的整数', path=field)
    return value


def object_value(value, field):
    require(isinstance(value, dict), 'RECORD_INVALID', '交付字段须为JSON对象', path=field)
    return value


def rows_value(value, field, *, minimum=1):
    require(isinstance(value, list) and minimum <= len(value) <= MAX_FILES,
            'RECORD_INVALID', '交付清单缺失或超出条目预算', path=field)
    return value


def sha(path):
    try:
        with path.open('rb') as handle:
            return hashlib.file_digest(handle, 'sha256').hexdigest()
    except OSError as exc:
        raise failure('FILE_INVALID', '交付文件无法读取', path=str(path), cause=str(exc)) from exc


def checked_path(root, relative):
    text(relative, 'relative_path')
    parts = relative.split('/')
    require('\\' not in relative and all(part and part not in {'.', '..'}
        and not part.endswith(('.', ' ')) and part.split('.', 1)[0].casefold() not in RESERVED
        and all(ord(char) >= 32 and char not in ':<>"|?*' for char in part) for part in parts),
        'PATH_INVALID', '交付路径含越界、设备名或Windows别名', path=relative)
    candidate = root
    for part in parts:
        candidate = candidate / part
        require(not candidate.is_symlink() and not getattr(candidate, 'is_junction', lambda: False)(),
                'PATH_INVALID', '交付路径拒绝链接', path=str(candidate))
    require(candidate.resolve().is_relative_to(root.resolve()), 'PATH_INVALID', '交付路径越出工作区')
    return candidate


def local_file(root, value):
    value = text(value, 'local_file')
    path = Path(value)
    if path.is_absolute():
        try:
            value = path.relative_to(root).as_posix()
        except ValueError as exc:
            raise failure('PATH_INVALID', '交付依赖须位于工作区', path=str(path)) from exc
    return checked_path(root, value)


def read_bytes(path, limit):
    try:
        require(path.is_file(), 'FILE_INVALID', '交付文件缺失或不是普通文件', path=str(path))
        with path.open('rb') as handle:
            data = handle.read(limit + 1)
        require(len(data) <= limit, 'FILE_INVALID', '交付文件超出读取预算', path=str(path))
        return data
    except OSError as exc:
        raise failure('FILE_INVALID', '交付文件无法读取', path=str(path), cause=str(exc)) from exc


def decode_json(data, name):
    try:
        def unique(items):
            result = {}
            for key, value in items:
                if key in result:
                    raise ValueError('Duplicate field: ' + key)
                result[key] = value
            return result
        value = json.loads(data, object_pairs_hook=unique,
                           parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))
        return object_value(value, str(name))
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise failure('FILE_INVALID', '交付记录须为有限、无重复字段的JSON对象', path=str(name)) from exc


def read_json(path, limit=2 * 1024**2):
    return decode_json(read_bytes(path, limit), path)


def pinned_file(root, row, field, *, limit=MAX_FILE):
    row = object_value(row, field)
    path = local_file(root, row.get('path'))
    expected_size = size(row.get('bytes'), field + '.bytes', maximum=limit)
    pin = digest(row.get('sha256'), field + '.sha256')
    data = read_bytes(path, limit)
    require(len(data) == expected_size and hashlib.sha256(data).hexdigest() == pin,
            'CANDIDATE_CHANGED', '交付文件大小或摘要不符', path=str(path))
    return path, data


def target(root, relative):
    text(relative, 'target')
    require(relative in {CONFIG, MANIFEST} or relative.startswith(SKILL), 'SCOPE_INVALID',
            '交付仅可修改统一Skill、注册清单和运行配置', path=relative)
    return checked_path(root, relative)


def inventory(root):
    manifest = read_json(target(root, MANIFEST))
    require(type(manifest.get('skill_count')) is int and manifest['skill_count'] == 1
        and type(manifest.get('module_count')) is int and manifest['module_count'] == 17,
        'REGISTRATION_INVALID', '要求一个公开Skill及17内部模块')
    files, seen, total = {}, set(), 0
    for row in rows_value(manifest.get('files'), 'current.files'):
        row = object_value(row, 'current.file')
        name = text(row.get('path'), 'current.file.path')
        path = target(root, name)
        pin = digest(row.get('sha256'), 'current.file.sha256')
        try:
            total += size(path.stat().st_size, 'current.file.bytes')
        except OSError as exc:
            raise failure('FILE_INVALID', '当前正式文件无法读取', path=name, cause=str(exc)) from exc
        require(total <= MAX_TOTAL, 'CURRENT_CHANGED', '当前正式文件超出完整备份预算')
        require(name.startswith(SKILL) and name.casefold() not in seen and sha(path) == pin,
                'CURRENT_CHANGED', '当前Skill与正式清单不一致', path=name)
        seen.add(name.casefold())
        files[name] = pin
    actual = set()
    for path in checked_path(root, SKILL.rstrip('/')).rglob('*'):
        checked_path(root, path.relative_to(root).as_posix())
        if path.is_file():
            actual.add(path.relative_to(root).as_posix())
    require(actual == set(files), 'CURRENT_CHANGED', '当前Skill有未列入清单的文件')
    for name in (CONFIG, MANIFEST):
        files[name] = sha(target(root, name))
    return files


def _gate(root, role, row, version, pins, skill_pins):
    row = object_value(row, 'gates.' + role)
    path = local_file(root, row.get('path'))
    data = read_bytes(path, 8 * 1024**2)
    require(hashlib.sha256(data).hexdigest() == digest(row.get('sha256'), role + '.sha256'),
            'GATE_CHANGED', '验收证据字节已变化', path=str(path))
    report = decode_json(data, path)
    require(report.get('status') == 'passed' and report.get('cli_version') == version,
            'GATE_FAILED', '验收状态或版本不符', path=str(path))
    if role.endswith('-tests'):
        count = report.get('tests')
        require(report.get('frozen_equal') is True and type(count) is int and count > 0
            and report.get('discovered_tests') == count
            and all(type(report.get(k)) is int and report[k] == 0 for k in ('failures', 'errors', 'skipped')),
            'GATE_FAILED', '回归未完整通过或实现未冻结', path=str(path))
        source_pins = object_value(report.get('file_hashes'), role + '.file_hashes')
        require(all(source_pins.get('product/src/ai_ad_editor/' + name) == pin for name, pin in pins.items()),
                'GATE_FAILED', '回归与候选应用字节不同', path=str(path))
    else:
        require(report.get('application_files') == pins, 'GATE_FAILED', '实测与候选应用字节不同', path=str(path))
    if role in {'installed-tests', 'skill-entry', 'native-music'}:
        require(report.get('source_fallback') is False, 'GATE_FAILED', '缺少禁止源码回落证明')
    if role == 'package-replay':
        require(all(report.get(k) is True for k in ('complete_master_WAV_equal',
            'complete_generation_recipe_equal', 'complete_rendered_RGBA_PCM_equal')),
            'GATE_FAILED', '工程包缺少完整音画、原音频或配方一致证据')
    if role in {'skill-entry', 'native-music'}:
        require(report.get('actual_PowerShell_entry') is True and report.get('skill_files') == skill_pins,
                'GATE_FAILED', '实际入口与候选Skill字节不一致')
    if role == 'native-music':
        require(all(report.get(k) is True for k in ('actual_CUDA_music', 'complete_PCM_verified',
            'project_placement_verified', 'owned_process_cleanup_verified')),
            'GATE_FAILED', '缺少当前候选实际CUDA配乐、完整音频、入轨或清理证据')
        _, master = pinned_file(root, report.get('master_audio'), 'native-music.master_audio')
        require(master[:4] == b'RIFF' and master[8:12] == b'WAVE' and len(master) > 44,
                'GATE_FAILED', '实际配乐母音频不是有效WAV容器')
        pinned_file(root, report.get('request_file'), 'native-music.request_file', limit=2 * 1024**2)
        pinned_file(root, report.get('project_manifest'), 'native-music.project_manifest', limit=2 * 1024**2)
        generation = object_value(report.get('actual_generation'), 'native-music.actual_generation')
        worker = object_value(generation.get('worker'), 'native-music.worker')
        model = object_value(worker.get('model'), 'native-music.model')
        forwards = object_value(model.get('forwards'), 'native-music.forwards')
        devices = object_value(model.get('forward_output_devices'), 'native-music.forward_output_devices')
        cleanup = object_value(generation.get('cleanup'), 'native-music.cleanup')
        require(model.get('neural_backend') == 'cuda' and set(forwards) == {'text', 'language_model', 'diffusion', 'vae'}
            and all(type(n) is int and n > 0 for n in forwards.values())
            and all(devices.get(name) == ['cuda:0'] for name in forwards)
            and generation.get('complete_PCM_roundtrip_verified') is True
            and isinstance(report.get('independent_PCM_sha256'), str)
            and report['independent_PCM_sha256'] == worker.get('output_PCM_sha256')
            and cleanup.get('worker_exited') is True and cleanup.get('owner_job_closed') is True,
            'GATE_FAILED', '实际配乐的前向设备、完整音频或清理记录不完整')
    return str(path).casefold()


def verify(root, descriptor):
    root = Path(root).resolve(strict=True)
    descriptor = local_file(root, str(descriptor))
    spec = read_json(descriptor)
    version = text(spec.get('cli_version'), 'cli_version')
    release = text(spec.get('release'), 'release')
    require(spec.get('format') == FORMAT and re.fullmatch(r'\d+\.\d+\.\d+', version),
            'DESCRIPTOR_INVALID', '交付描述格式或版本无效')
    current = inventory(root)
    require(spec.get('expected_current') == current, 'CURRENT_CHANGED', '当前正式入口已变化')
    contents, total = {}, 0
    for row in rows_value(spec.get('files'), 'files', minimum=4):
        row = object_value(row, 'file')
        name = text(row.get('path'), 'file.path')
        destination = target(root, name)
        require(name in current or not destination.exists(), 'CURRENT_CHANGED', '候选新增文件与已有内容冲突')
        source = local_file(root, row.get('source'))
        require(source.is_relative_to(descriptor.parent) and name not in contents,
                'SCOPE_INVALID', '候选文件须属于描述目录且不得重复')
        _, data = pinned_file(root, dict(path=str(source), bytes=row.get('bytes'), sha256=row.get('sha256')), 'file')
        total += len(data)
        require(total <= MAX_TOTAL, 'CANDIDATE_CHANGED', '候选总大小超出预算')
        contents[name] = data
    require(current.keys() <= contents.keys() and len({p.casefold() for p in contents}) == len(contents),
            'SCOPE_INVALID', '升级不得遗漏原文件或使用大小写重复路径')
    config, manifest = decode_json(contents[CONFIG], CONFIG), decode_json(contents[MANIFEST], MANIFEST)
    require(type(manifest.get('skill_count')) is int and manifest['skill_count'] == 1
        and type(manifest.get('module_count')) is int and manifest['module_count'] == 17
        and manifest.get('cli_version') == version and manifest.get('release') == config.get('release') == release
        and manifest.get('manifest_sha256') == config.get('manifest_sha256')
        and manifest.get('runtime_config') == CONFIG and config.get('native_only') is True,
        'REGISTRATION_INVALID', '候选版本、配置或单一Skill注册不一致')
    expected, seen = {}, set()
    for row in rows_value(manifest.get('files'), 'manifest.files'):
        row = object_value(row, 'manifest.file')
        name = text(row.get('path'), 'manifest.file.path')
        target(root, name)
        require(name.startswith(SKILL) and name.casefold() not in seen, 'REGISTRATION_INVALID', '候选注册条目重复或越界')
        seen.add(name.casefold())
        expected[name] = digest(row.get('sha256'), 'manifest.file.sha256')
        require(name in contents and size(row.get('bytes'), 'manifest.file.bytes') == len(contents[name]),
                'REGISTRATION_INVALID', '候选注册条目大小不一致')
    skill_pins = {name: hashlib.sha256(data).hexdigest() for name, data in contents.items() if name.startswith(SKILL)}
    require(expected == skill_pins, 'REGISTRATION_INVALID', '候选Skill与注册清单不同')
    installed = local_file(root, config.get('installed_directory'))
    launcher = local_file(root, str(installed / 'run.py'))
    receipt = read_json(local_file(root, str(installed / 'receipt.json')))
    require(receipt.get('manifest_sha256') == config.get('manifest_sha256')
        and sha(launcher) == digest(config.get('launcher_sha256'), 'launcher_sha256'),
        'INSTALLATION_CHANGED', '独立安装收据或启动器不符')
    package = local_file(root, str(installed / 'site/ai_ad_editor'))
    try:
        tree = ast.parse(read_bytes(package / '__init__.py', MAX_FILE))
        versions = [ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign)
            and any(isinstance(t, ast.Name) and t.id == 'VERSION' for t in n.targets)]
    except (ValueError, SyntaxError, TypeError, RecursionError) as exc:
        raise failure('INSTALLATION_CHANGED', '安装应用版本文件无法解释') from exc
    require(versions == [version], 'INSTALLATION_CHANGED', '安装应用版本与交付计划不同')
    pins = object_value(spec.get('application_files'), 'application_files')
    require({p.name for p in package.glob('*.py')} == pins.keys(), 'INSTALLATION_CHANGED', '安装应用清单不完整')
    for name, pin in pins.items():
        require(sha(local_file(root, str(package / name))) == digest(pin, 'application.' + name),
                'INSTALLATION_CHANGED', '安装应用字节已变化', path=name)
    archive = object_value(spec.get('archive'), 'archive')
    require(sha(local_file(root, archive.get('path'))) == digest(archive.get('sha256'), 'archive.sha256'),
            'ARCHIVE_CHANGED', '离线包摘要不一致')
    gates = object_value(spec.get('gates'), 'gates')
    require(gates.keys() == ROLES, 'GATES_MISSING', '要求源码、安装、工程包、Skill及实际CUDA配乐五类独立证据')
    gate_paths = [_gate(root, role, row, version, pins, skill_pins) for role, row in gates.items()]
    require(len(set(gate_paths)) == len(ROLES), 'GATES_MISSING', '验收角色不得复用同一收据')
    return spec, contents


@contextmanager
def lock(root):
    path = checked_path(root, 'local/agent-ffmpeg/delivery.lock')
    with _native_byte_lock(path, timeout=5, error_code='DELIVERY_BUSY', message='另一个交付操作尚未结束'):
        yield


def pending(root):
    return checked_path(root, 'local/agent-ffmpeg/delivery-journal.json')


def _journal(value):
    value = object_value(value, 'journal')
    identity = text(value.get('delivery_id'), 'delivery_id')
    require(value.get('format') == FORMAT and re.fullmatch(r'[0-9a-f]{32}', identity)
        and value.get('status') in {'prepared', 'committed', 'rolled-back'}, 'JOURNAL_INVALID', '交付恢复日志身份或状态无效')
    rows_value(value.get('files'), 'journal.files')
    return value


def _prepare_restore(root, journal, *, require_current):
    _journal(journal)
    prepared, seen, total = [], set(), 0
    for index, row in enumerate(journal['files']):
        row = object_value(row, 'journal.file')
        name = text(row.get('path'), 'journal.file.path')
        destination = target(root, name)
        require(name.casefold() not in seen and type(row.get('existed')) is bool,
                'JOURNAL_INVALID', '交付恢复条目重复或缺少原存在状态')
        seen.add(name.casefold())
        next_pin = digest(row.get('next_sha256'), 'journal.file.next_sha256')
        data = None
        if row['existed']:
            pin = digest(row.get('previous_sha256'), 'journal.file.previous_sha256')
            backup = checked_path(root, 'local/agent-ffmpeg/deliveries/' + journal['delivery_id'] + f'/{index:04d}.bin')
            data = read_bytes(backup, MAX_FILE)
            total += len(data)
            require(total <= MAX_TOTAL and len(data) == size(row.get('previous_bytes'), 'journal.file.previous_bytes')
                and hashlib.sha256(data).hexdigest() == pin, 'BACKUP_CHANGED', '完整交付备份核验失败，未开始恢复')
        else:
            require(row.get('previous_sha256') is None and row.get('previous_bytes') is None,
                    'JOURNAL_INVALID', '新增条目不得声明原始备份')
        if require_current:
            require(destination.is_file() and sha(destination) == next_pin,
                    'CURRENT_CHANGED', '升级后文件已有其他修改，拒绝覆盖', path=name)
        elif destination.exists():
            current = read_bytes(destination, MAX_FILE)
            allowed = {next_pin}
            if data is not None:
                allowed.add(hashlib.sha256(data).hexdigest())
            require(hashlib.sha256(current).hexdigest() in allowed or name == CONFIG and current in IN_PROGRESS,
                    'CURRENT_CHANGED', '中断后文件存在非交付修改，拒绝覆盖', path=name)
        prepared.append((name, destination, data))
    require({CONFIG, MANIFEST} <= seen and all(data is not None for name, _, data in prepared
            if name in {CONFIG, MANIFEST}), 'JOURNAL_INVALID', '恢复缺少原配置及注册清单')
    return prepared


def _restore(root, journal, *, require_current):
    prepared = _prepare_restore(root, journal, require_current=require_current)
    _atomic_write_bytes(target(root, CONFIG), b'{"release":"delivery-recovery-in-progress"}\n')
    for name, path, data in sorted(prepared, key=lambda row: row[0] == CONFIG):
        if data is None:
            path.unlink(missing_ok=True)
        else:
            _atomic_write_bytes(path, data)
    journal['status'] = 'rolled-back'
    atomic_write_json(pending(root), journal)
    return dict(status='rolled-back', delivery_id=journal['delivery_id'], restored=len(prepared),
                backups_preserved=True, source_fallback=False)


def recover(root, *, rollback=False, dry_run=False):
    root = Path(root).resolve(strict=True)
    with lock(root):
        path = pending(root)
        if not path.is_file():
            return dict(status='clean', recovered=False)
        journal = _journal(read_json(path))
        if journal['status'] == 'rolled-back':
            return dict(status='clean', recovered=False, previous_delivery_id=journal['delivery_id'])
        if journal['status'] == 'committed' and not rollback:
            return dict(status='committed', recovered=False, delivery_id=journal['delivery_id'])
        if dry_run:
            _prepare_restore(root, journal, require_current=journal['status'] == 'committed')
            return dict(status='planned', recovered=False, action='rollback' if rollback else 'recover')
        return _restore(root, journal, require_current=journal['status'] == 'committed')


def activate(root, descriptor, *, dry_run=False):
    root = Path(root).resolve(strict=True)
    with lock(root):
        path = pending(root)
        if path.is_file():
            require(_journal(read_json(path))['status'] != 'prepared', 'RECOVERY_REQUIRED', '先完成上次中断的交付恢复')
        spec, contents = verify(root, descriptor)
        if dry_run:
            return dict(status='planned', cli_version=spec['cli_version'], release=spec['release'],
                        files=len(contents), formal_activation=False)
        identity = uuid.uuid4().hex
        base = checked_path(root, 'local/agent-ffmpeg/deliveries/' + identity)
        base.mkdir(parents=True)
        rows = []
        for index, (name, data) in enumerate(sorted(contents.items())):
            destination = target(root, name)
            existed = name in spec['expected_current']
            old = read_bytes(destination, MAX_FILE) if existed else None
            require((old is not None and hashlib.sha256(old).hexdigest() == spec['expected_current'][name])
                    or (not existed and not destination.exists()), 'CURRENT_CHANGED', '备份前正式文件发生变化', path=name)
            if old is not None:
                _atomic_write_bytes(base / f'{index:04d}.bin', old)
            rows.append(dict(path=name, existed=existed, previous_bytes=len(old) if existed else None,
                previous_sha256=hashlib.sha256(old).hexdigest() if existed else None,
                next_sha256=hashlib.sha256(data).hexdigest()))
        journal = dict(format=FORMAT, status='prepared', delivery_id=identity,
                       cli_version=spec['cli_version'], release=spec['release'], files=rows)
        atomic_write_json(path, journal)
        try:
            _atomic_write_bytes(target(root, CONFIG), b'{"release":"delivery-switch-in-progress"}\n')
            for name, data in sorted(contents.items(), key=lambda row: row[0] == CONFIG):
                _atomic_write_bytes(target(root, name), data)
            require(all(sha(target(root, row['path'])) == row['next_sha256'] for row in rows),
                    'PUBLICATION_CHANGED', '切换后文件摘要不符')
            result = run_process(['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass',
                '-File', str(target(root, SKILL + 'scripts/run.ps1')), 'version'], timeout=90)
            version = decode_json(result.stdout, 'PowerShell.version')
            require(result.returncode == 0 and version.get('ok') is True
                and isinstance(version.get('data'), dict) and version['data'].get('cli_version') == spec['cli_version'],
                'ENTRY_FAILED', '正式Skill切换后实际版本入口未通过')
            journal['status'] = 'committed'
            atomic_write_json(path, journal)
            atomic_write_json(base / 'committed.json', journal)
            return dict(status='activated', cli_version=spec['cli_version'], release=spec['release'],
                        delivery_id=identity, files=len(rows), actual_PowerShell_entry=True,
                        source_fallback=False, backups_preserved=True)
        except BaseException:
            _restore(root, journal, require_current=False)
            raise


def add_parser(subs, leaf):
    group = subs.add_parser('delivery', help='核验、切换、恢复和回滚唯一正式Skill')
    actions = group.add_subparsers(dest='action', required=True)
    for name in ('inspect', 'activate', 'recover', 'rollback'):
        parser = leaf(actions.add_parser(name))
        parser.add_argument('--workspace', required=True)
        if name in {'inspect', 'activate'}:
            parser.add_argument('--descriptor', required=True)


def command(args):
    from .cli import _envelope
    try:
        if args.action == 'inspect':
            spec, files = verify(Path(args.workspace).resolve(strict=True), args.descriptor)
            result = dict(status='verified', cli_version=spec['cli_version'], files=len(files), formal_activation=False)
        elif args.action == 'activate':
            result = activate(args.workspace, args.descriptor, dry_run=args.dry_run)
        else:
            result = recover(args.workspace, rollback=args.action == 'rollback', dry_run=args.dry_run)
    except OSError as exc:
        raise failure('IO_FAILED', '交付文件系统操作失败，保留恢复记录', cause=str(exc)) from exc
    return _envelope('delivery.' + args.action, args, data=result,
                     status='planned' if args.dry_run else 'succeeded')
