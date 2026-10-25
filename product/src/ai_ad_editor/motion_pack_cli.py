"""CLI for bounded local motion recipes and atomic project applications."""
from __future__ import annotations

import json
import os
from pathlib import Path

from . import motion_pack as packs
from .artifact_locks import artifact_entry, verification_scope, verification_summary
from .errors import AppError
from .execution_control import checkpoint, operation_budget
from .policy import resolve_local_path
from .project import create_snapshot, find_sequence, load_project, save_project
from .utils import new_id, now_iso
from .validator import validate_project


def add_parser(actions, leaf):
    parser = actions.add_parser('pack', help='创建、捕获和跨工程应用版本化参数运镜包')
    sub = parser.add_subparsers(dest='pack_action', required=True)
    for action in ('list', 'inspect', 'create', 'capture', 'apply'):
        child = leaf(sub.add_parser(action))
        child.add_argument('--timeout-seconds', type=float, default=120)
        child.add_argument('--cancel-file')
        if action in ('inspect', 'apply'):
            source = child.add_mutually_exclusive_group(required=True)
            source.add_argument('--input', help='本地运镜包 JSON')
            source.add_argument('--name', choices=packs.BUILTIN_NAMES, help='内置包稳定 ID')
        if action == 'create':
            child.add_argument('--name', required=True, choices=packs.BUILTIN_NAMES)
        if action in ('create', 'capture'):
            child.add_argument('--output', required=True, help='新的本地 JSON 路径，不覆盖已有文件')
        if action in ('capture', 'apply'):
            child.add_argument('--project', required=True)
            child.add_argument('--sequence-id')
            child.add_argument('--track-id')
            child.add_argument('--clip-id', required=True)
        if action == 'capture':
            child.add_argument('--id', required=True, dest='pack_id')
            child.add_argument('--title', required=True)
            child.add_argument('--version', default='1.0.0', dest='pack_version')
            child.add_argument('--creator', required=True)
            child.add_argument('--license', required=True, dest='pack_license')
            child.add_argument('--property', action='append', dest='properties', choices=tuple(packs.ALIASES))
        if action == 'apply':
            child.add_argument('--param', action='append', default=[], help='NAME=有限数字；可多次指定，不能重复')
            child.add_argument('--start-tick', type=int, default=0)
            child.add_argument('--end-tick', type=int)
            child.add_argument('--replace', action='store_true', help='显式替换包涉及的整条已有属性轨')


def _load(root, argument):
    path = resolve_local_path(root, argument, field='input')
    if not path.is_file():
        packs.fail('运镜包输入不存在或不是普通文件', str(path))
    if path.stat().st_size > packs.MAX_BYTES:
        packs.fail('运镜包超过 1MiB', str(path), 'MOTION_PACK_TOO_LARGE')
    entry = artifact_entry(path, 'motion-pack')
    return packs.decode_pack(path.read_bytes()), entry


def _write_new(path, pack):
    # Link a fully flushed sibling into a new name atomically. A concurrent
    # creator wins without being overwritten; our temporary sibling is owned.
    raw = json.dumps(pack, ensure_ascii=False, indent=2, allow_nan=False).encode('utf-8') + b'\n'
    if len(raw) > packs.MAX_BYTES:
        packs.fail('格式化后的包超过 1MiB', code='MOTION_PACK_TOO_LARGE')
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name('.' + path.name + '.' + new_id('motion') + '.tmp')
    try:
        with temporary.open('xb') as stream:
            stream.write(raw); stream.flush(); os.fsync(stream.fileno())
        checkpoint(force=True)
        try:
            os.link(temporary, path)
        except FileExistsError as exc:
            raise AppError('OUTPUT_EXISTS', '输出已存在；请使用新路径', exit_code=2, path=str(path)) from exc
        except OSError as exc:
            raise AppError('MOTION_PACK_OUTPUT_FAILED', '无法原子发布新运镜包', exit_code=2, path=str(path), cause=str(exc)) from exc
    finally:
        temporary.unlink(missing_ok=True)


def _target(project, args):
    sequence = find_sequence(project, args.sequence_id)
    found = [(track, clip) for track in sequence['tracks']
             if not args.track_id or track['id'] == args.track_id
             for clip in track['clips'] if clip['id'] == args.clip_id]
    if len(found) != 1:
        packs.fail('必须找到唯一的目标片段；必要时指定轨道', 'clip_id', 'MOTION_PACK_TARGET_INVALID')
    track, clip = found[0]
    if track['kind'] not in ('video', 'image'):
        packs.fail('本版运镜包应用于视觉轨道', 'track_id', 'MOTION_PACK_TARGET_INVALID')
    return sequence, track, clip


def command(args, envelope, operation):
    action = args.pack_action
    root, project = load_project(args.project) if getattr(args, 'project', None) else (Path.cwd(), None)
    with operation_budget(args.timeout_seconds, args.cancel_file, root=root), verification_scope():
        if action == 'list':
            return envelope('motion.pack.list', args, data=dict(engine=packs.ENGINE, format=packs.FORMAT,
                format_version=packs.VERSION, network='disabled', count=len(packs.BUILTIN_NAMES), packs=packs.catalog()))
        validation = None
        if project is not None:
            validation = validate_project(root, project, strict_rights=False)
            if not validation['ok']:
                raise AppError('PROJECT_INVALID', '运镜操作前工程无效', exit_code=2, diagnostics=validation)
            sequence, track, clip = _target(project, args)
        entry = None
        if action == 'capture':
            pack = packs.capture_pack(clip, pack_id=args.pack_id, name=args.title, creator=args.creator,
                license=args.pack_license, version=args.pack_version, properties=args.properties)
        elif getattr(args, 'input', None):
            pack, entry = _load(root, args.input)
        else:
            pack = packs.builtin(args.name)
        data = dict(pack=pack, content_sha256=packs.digest(pack), input=entry,
                    verification=verification_summary(), engine=packs.ENGINE)
        if action == 'inspect':
            return envelope('motion.pack.inspect', args, data=data)
        if action in ('create', 'capture'):
            output = resolve_local_path(root, args.output, field='output')
            if output.exists():
                raise AppError('OUTPUT_EXISTS', '输出已存在；请使用新路径', exit_code=2, path=str(output))
            data['output'] = str(output)
            if action == 'capture':
                data.update(sequence_id=sequence['id'], track_id=track['id'], clip_id=clip['id'], validation=validation)
            if args.dry_run:
                return envelope('motion.pack.' + action, args, status='planned', data=data)
            _write_new(output, pack)
            return envelope('motion.pack.' + action, args, data=data)
        if track.get('locked'):
            packs.fail('不能修改锁定轨道', 'track_id', 'EDIT_TRACK_LOCKED')
        if any(c.get('tracking_binding', {}).get('source_clip_id') == clip['id']
               for s in project['sequences'] for t in s['tracks'] for c in t['clips']):
            packs.fail('目标被跟踪绑定引用，不能静默改变轨迹', code='MOTION_PACK_TRACKING_CONFLICT')
        parameters = {}
        for value in args.param:
            name, separator, raw = value.partition('=')
            if not separator or name in parameters:
                packs.fail('参数必须为唯一的 NAME=数字', 'param')
            try:
                parsed = json.loads(raw)
            except ValueError:
                packs.fail('参数必须为 JSON 有限数字', 'param')
            parameters[name] = packs.number(parsed, 'param.' + name)
        updated, receipt, warnings = packs.compile_pack(pack, clip, parameters=parameters,
            start_tick=args.start_tick, end_tick=args.end_tick, replace=args.replace)
        # All compilation occurs on a detached value. The dispatcher owns the
        # project lock, idempotency and metadata transaction around this commit.
        import copy
        candidate = copy.deepcopy(project)
        target_sequence, target_track, target_clip = _target(candidate, args)
        target_clip.clear(); target_clip.update(updated)
        candidate_validation = validate_project(root, candidate, strict_rights=False)
        if not candidate_validation['ok']:
            raise AppError('PROJECT_INVALID', '运镜包会生成无效工程', exit_code=2, diagnostics=candidate_validation)
        receipt['input_sha256'] = entry['sha256'] if entry else None
        data.update(sequence_id=target_sequence['id'], track_id=target_track['id'], clip_id=target_clip['id'],
                    motion=receipt, clip=target_clip, validation=candidate_validation)
        checkpoint(force=True)
        if args.dry_run:
            return envelope('motion.pack.apply', args, status='planned', data=data, warnings=warnings)
        snapshot = create_snapshot(root, project, label='before-motion-pack-apply')
        operation_id = new_id('op')
        record = dict(operation_id=operation_id, command='motion.pack.apply', status='succeeded',
            created_at=now_iso(), sequence_id=target_sequence['id'], track_id=target_track['id'],
            clip_id=target_clip['id'], motion=receipt, before_snapshot_id=snapshot['snapshot_id'])
        candidate.setdefault('provenance', {}).setdefault('change_log', []).append(record.copy())
        checkpoint(force=True)
        save_project(root, candidate)
        operation(root, operation_id, record)
        checkpoint(force=True)
        return envelope('motion.pack.apply', args, data={**data, 'before_snapshot':snapshot},
                        warnings=warnings, operation_id=operation_id)
