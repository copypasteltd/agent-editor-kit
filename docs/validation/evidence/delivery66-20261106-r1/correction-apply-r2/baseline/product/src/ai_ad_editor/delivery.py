"""Verified native installations and recoverable single-Skill activation."""
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

FORMAT = 'agent-editor-skill-delivery-v1'
SKILL = 'skills/agent-ffmpeg-local-editor/'
CONFIG = 'local/agent-ffmpeg/runtime.json'
MANIFEST = 'agent-ffmpeg-local-install-manifest.json'
MAX_FILE = 32 * 1024**2
MAX_TOTAL = 128 * 1024**2


def failure(code, message, **details):
    return AppError('DELIVERY_' + code, message, exit_code=6, **details)


def sha(path):
    with path.open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()


def checked_path(root, relative):
    if not isinstance(relative, str) or not relative or '\\' in relative:
        raise failure('PATH_INVALID', '交付路径须为明确的本地相对路径')
    parts = relative.split('/')
    if any(not part or part in {'.', '..'} or ':' in part or '\0' in part
           or part.endswith(('.', ' ')) for part in parts):
        raise failure('PATH_INVALID', '交付路径含别名或越界部分', path=relative)
    candidate = root
    for part in parts:
        candidate = candidate / part
        if candidate.is_symlink() or getattr(candidate, 'is_junction', lambda: False)():
            raise failure('PATH_INVALID', '交付写入和备份路径拒绝链接', path=str(candidate))
    if not candidate.resolve().is_relative_to(root.resolve()):
        raise failure('PATH_INVALID', '交付路径越出工作区', path=relative)
    return candidate


def local_file(root, value):
    path = Path(value)
    if path.is_absolute():
        try:
            value = path.relative_to(root).as_posix()
        except ValueError as exc:
            raise failure('PATH_INVALID', '交付依赖必须位于工作区', path=str(path)) from exc
    return checked_path(root, value)


def read_json(path, limit=2 * 1024**2):
    if not path.is_file() or path.stat().st_size > limit:
        raise failure('FILE_INVALID', '交付记录缺失或超出大小预算', path=str(path))
    try:
        def unique(items):
            result = {}
            for key, value in items:
                if key in result:
                    raise ValueError('Duplicate JSON field: ' + key)
                result[key] = value
            return result
        value = json.loads(path.read_bytes(), object_pairs_hook=unique)
        if not isinstance(value, dict):
            raise ValueError('Object required')
        return value
    except (ValueError, UnicodeError) as exc:
        raise failure('FILE_INVALID', '交付记录须为无重复字段的JSON对象', path=str(path)) from exc


def target(root, relative):
    if relative not in {CONFIG, MANIFEST} and not relative.startswith(SKILL):
        raise failure('SCOPE_INVALID', '交付仅可修改统一Skill、注册清单和运行配置', path=relative)
    return checked_path(root, relative)


def inventory(root):
    manifest = read_json(target(root, MANIFEST))
    if manifest.get('skill_count') != 1 or manifest.get('module_count') != 17:
        raise failure('REGISTRATION_INVALID', '要求一个公开Skill及17内部模块')
    files = {}
    for row in manifest['files']:
        path = target(root, row['path'])
        if row['path'] in files or not row['path'].startswith(SKILL) or sha(path) != row['sha256']:
            raise failure('CURRENT_CHANGED', '当前Skill与正式清单不一致', path=str(path))
        files[row['path']] = row['sha256']
    for relative in (CONFIG, MANIFEST):
        files[relative] = sha(target(root, relative))
    actual = {p.relative_to(root).as_posix() for p in checked_path(root, SKILL.rstrip('/')).rglob('*') if p.is_file()}
    if actual != {p for p in files if p.startswith(SKILL)}:
        raise failure('CURRENT_CHANGED', '当前Skill存在未列入清单的文件')
    return files


def verify(root, descriptor):
    root = Path(root).resolve(strict=True)
    descriptor = local_file(root, str(descriptor))
    spec = read_json(descriptor)
    if spec.get('format') != FORMAT or not re.fullmatch(r'\d+\.\d+\.\d+', spec.get('cli_version', '')):
        raise failure('DESCRIPTOR_INVALID', '交付描述格式或版本无效')
    current = inventory(root)
    if spec.get('expected_current') != current:
        raise failure('CURRENT_CHANGED', '当前正式入口已变化，拒绝使用过期交付计划')
    rows, contents, total = spec.get('files'), {}, 0
    if not isinstance(rows, list) or not 4 <= len(rows) <= 512:
        raise failure('DESCRIPTOR_INVALID', '交付文件清单无效')
    for row in rows:
        if not isinstance(row, dict):
            raise failure('DESCRIPTOR_INVALID', '交付文件项无效')
        relative = row['path']
        destination = target(root, relative)
        if relative not in current and destination.exists():
            raise failure('CURRENT_CHANGED', '候选新增文件与已有内容冲突', path=str(destination))
        source = local_file(root, row['source'])
        if not source.is_relative_to(descriptor.parent) or relative in contents:
            raise failure('SCOPE_INVALID', '候选文件须属于描述所在目录且不得重复')
        size = source.stat().st_size
        total += size
        if (type(row['bytes']) is not int or size != row['bytes'] or size > MAX_FILE
                or total > MAX_TOTAL or sha(source) != row['sha256']):
            raise failure('CANDIDATE_CHANGED', '候选字节、大小或预算不符', path=str(source))
        contents[relative] = source.read_bytes()
        if hashlib.sha256(contents[relative]).hexdigest() != row['sha256']:
            raise failure('CANDIDATE_CHANGED', '候选读取时发生变化', path=str(source))
    if not current.keys() <= contents.keys() or len({p.casefold() for p in contents}) != len(contents):
        raise failure('SCOPE_INVALID', '升级不得遗漏原文件或使用大小写重复路径')
    config = json.loads(contents[CONFIG])
    manifest = json.loads(contents[MANIFEST])
    if (manifest.get('skill_count') != 1 or manifest.get('module_count') != 17
            or manifest.get('cli_version') != spec['cli_version']
            or manifest.get('release') != config.get('release') or config.get('release') != spec.get('release')
            or manifest.get('manifest_sha256') != config.get('manifest_sha256')
            or manifest.get('runtime_config') != CONFIG or config.get('native_only') is not True):
        raise failure('REGISTRATION_INVALID', '候选版本、配置或单一Skill注册不一致')
    expected = {row['path']: row['sha256'] for row in manifest['files']}
    skill_files = {name: hashlib.sha256(data).hexdigest() for name, data in contents.items() if name.startswith(SKILL)}
    if len(expected) != len(manifest['files']) or expected != skill_files:
        raise failure('REGISTRATION_INVALID', '候选Skill文件与注册清单不一致')
    installed = local_file(root, config['installed_directory'])
    launcher = installed / 'run.py'
    receipt = read_json(installed / 'receipt.json')
    if receipt.get('manifest_sha256') != config['manifest_sha256'] or sha(launcher) != config['launcher_sha256']:
        raise failure('INSTALLATION_CHANGED', '独立安装收据或启动器不符')
    tree = ast.parse((installed / 'site/ai_ad_editor/__init__.py').read_bytes())
    versions = [ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign)
                and any(isinstance(t, ast.Name) and t.id == 'VERSION' for t in n.targets)]
    if versions != [spec['cli_version']]:
        raise failure('INSTALLATION_CHANGED', '安装应用版本与交付计划不同')
    package_pins = spec.get('application_files')
    actual_names = {p.name for p in (installed / 'site/ai_ad_editor').glob('*.py')}
    if not isinstance(package_pins, dict) or actual_names != package_pins.keys():
        raise failure('INSTALLATION_CHANGED', '安装应用清单不完整')
    if any(sha(installed / 'site/ai_ad_editor' / name) != pin for name, pin in package_pins.items()):
        raise failure('INSTALLATION_CHANGED', '安装应用字节已变化')
    archive = spec.get('archive', {})
    archive_path = local_file(root, archive.get('path', ''))
    if not archive_path.is_file() or sha(archive_path) != archive.get('sha256'):
        raise failure('ARCHIVE_CHANGED', '原始离线包与候选交付摘要不一致')
    roles = {'source-tests', 'installed-tests', 'package-replay', 'skill-entry'}
    gates = spec.get('gates', {})
    if not isinstance(gates, dict) or gates.keys() != roles:
        raise failure('GATES_MISSING', '要求源码、安装、完整工程重放和候选Skill四类独立证据')
    if len({row['path'] for row in gates.values()}) != len(roles):
        raise failure('GATES_MISSING', '不同验收角色须有独立收据')
    for role, row in gates.items():
        proof = local_file(root, row['path'])
        if sha(proof) != row['sha256']:
            raise failure('GATE_CHANGED', '验收证据字节已变化', path=str(proof))
        report = read_json(proof, limit=8 * 1024**2)
        if report.get('status') != 'passed' or report.get('cli_version') != spec['cli_version']:
            raise failure('GATE_FAILED', '验收状态或版本不符', path=str(proof))
        if role.endswith('-tests') and (not report.get('frozen_equal')
                or not report.get('tests') or any(report.get(k) != 0 for k in ('failures', 'errors', 'skipped'))):
            raise failure('GATE_FAILED', '回归未完整通过或实现未冻结', path=str(proof))
        if role.endswith('-tests'):
            pins = report.get('file_hashes', {})
            expected_pins = {'product/src/ai_ad_editor/' + name: pin for name, pin in package_pins.items()}
            if any(pins.get(name) != pin for name, pin in expected_pins.items()):
                raise failure('GATE_FAILED', '回归对应的应用字节与交付候选不同', path=str(proof))
        if role == 'installed-tests' and report.get('source_fallback') is not False:
            raise failure('GATE_FAILED', '安装验证缺少禁止源码回落证明')
        if role == 'package-replay' and not all(report.get(k) is True for k in (
                'complete_master_WAV_equal', 'complete_generation_recipe_equal', 'complete_rendered_RGBA_PCM_equal')):
            raise failure('GATE_FAILED', '工程包缺少完整音画、原音频或配方一致证据')
        if role == 'skill-entry' and report.get('actual_PowerShell_entry') is not True:
            raise failure('GATE_FAILED', '候选Skill未实际执行')
    return spec, contents


@contextmanager
def lock(root):
    path = checked_path(root, 'local/agent-ffmpeg/delivery.lock')
    with _native_byte_lock(path, timeout=5, error_code='DELIVERY_BUSY', message='另一个交付操作尚未结束'):
        yield


def pending(root):
    return checked_path(root, 'local/agent-ffmpeg/delivery-journal.json')


def _restore(root, journal, *, require_current):
    rows = journal.get('files')
    if (journal.get('format') != FORMAT or not isinstance(rows, list) or not rows
            or not re.fullmatch(r'[0-9a-f]{32}', journal.get('delivery_id', ''))):
        raise failure('JOURNAL_INVALID', '交付恢复日志无效')
    prepared, seen = [], set()
    total = 0
    for index, row in enumerate(rows):
        relative = row['path']
        destination = target(root, relative)
        if relative.casefold() in seen:
            raise failure('JOURNAL_INVALID', '交付恢复条目重复')
        seen.add(relative.casefold())
        if require_current and (not destination.is_file() or sha(destination) != row['next_sha256']):
            raise failure('CURRENT_CHANGED', '升级后文件已有其他修改，拒绝覆盖', path=str(destination))
        data = None
        if row['existed'] is True:
            backup = checked_path(root, 'local/agent-ffmpeg/deliveries/' + journal['delivery_id'] + f'/{index:04d}.bin')
            size = backup.stat().st_size
            total += size
            if size > MAX_FILE or total > MAX_TOTAL or sha(backup) != row['previous_sha256']:
                raise failure('BACKUP_CHANGED', '完整交付备份核验失败，未开始恢复', path=str(backup))
            data = backup.read_bytes()
            if hashlib.sha256(data).hexdigest() != row['previous_sha256']:
                raise failure('BACKUP_CHANGED', '交付备份读取时发生变化')
        elif row['existed'] is not False:
            raise failure('JOURNAL_INVALID', '交付恢复条目缺少原存在状态')
        elif destination.exists() and sha(destination) != row['next_sha256']:
            raise failure('CURRENT_CHANGED', '新增路径存在其他内容，拒绝删除', path=str(destination))
        prepared.append((relative, destination, data))
    if CONFIG not in seen or MANIFEST not in seen:
        raise failure('JOURNAL_INVALID', '交付恢复缺少配置及注册清单')
    # Keep discovery fail-closed until every Skill and registration file is restored.
    _atomic_write_bytes(target(root, CONFIG), b'{"release":"delivery-recovery-in-progress"}\n')
    for relative, path, data in sorted(prepared, key=lambda row: row[0] == CONFIG):
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
        journal = read_json(path)
        if journal.get('status') == 'rolled-back':
            return dict(status='clean', recovered=False, previous_delivery_id=journal['delivery_id'])
        if journal.get('status') == 'committed' and not rollback:
            return dict(status='committed', recovered=False, delivery_id=journal['delivery_id'])
        if journal.get('status') not in {'prepared', 'committed'}:
            raise failure('JOURNAL_INVALID', '未知交付事务状态')
        if dry_run:
            return dict(status='planned', recovered=False, action='rollback' if rollback else 'recover')
        return _restore(root, journal, require_current=journal['status'] == 'committed')


def activate(root, descriptor, *, dry_run=False):
    root = Path(root).resolve(strict=True)
    with lock(root):
        path = pending(root)
        if path.is_file() and read_json(path).get('status') == 'prepared':
            raise failure('RECOVERY_REQUIRED', '先完成上次中断的交付恢复')
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
            existed = destination.is_file()
            old = destination.read_bytes() if existed else None
            if old is not None:
                _atomic_write_bytes(base / f'{index:04d}.bin', old)
            rows.append(dict(path=name, existed=existed,
                previous_sha256=hashlib.sha256(old).hexdigest() if existed else None,
                next_sha256=hashlib.sha256(data).hexdigest()))
        journal = dict(format=FORMAT, status='prepared', delivery_id=identity,
                       cli_version=spec['cli_version'], release=spec['release'], files=rows)
        atomic_write_json(path, journal)
        try:
            _atomic_write_bytes(target(root, CONFIG), b'{"release":"delivery-switch-in-progress"}\n')
            for name, data in sorted(contents.items(), key=lambda row: row[0] == CONFIG):
                _atomic_write_bytes(target(root, name), data)
            for row in rows:
                if sha(target(root, row['path'])) != row['next_sha256']:
                    raise failure('PUBLICATION_CHANGED', '切换后的字节不符')
            result = run_process(['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass',
                '-File', str(target(root, SKILL + 'scripts/run.ps1')), 'version'], timeout=90)
            version = json.loads(result.stdout)
            if result.returncode or not version.get('ok') or version.get('data', {}).get('cli_version') != spec['cli_version']:
                raise failure('ENTRY_FAILED', '正式Skill切换后实际版本入口未通过')
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
    if args.action == 'inspect':
        spec, files = verify(Path(args.workspace).resolve(strict=True), args.descriptor)
        result = dict(status='verified', cli_version=spec['cli_version'], files=len(files), formal_activation=False)
    elif args.action == 'activate':
        result = activate(args.workspace, args.descriptor, dry_run=args.dry_run)
    else:
        result = recover(args.workspace, rollback=args.action == 'rollback', dry_run=args.dry_run)
    return _envelope('delivery.' + args.action, args, data=result,
                     status='planned' if args.dry_run else 'succeeded')
