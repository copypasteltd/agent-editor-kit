"""Import bundled material and generated audio with portable rights evidence."""
from __future__ import annotations

import copy
import math
import shutil
from pathlib import Path
from typing import Any

from . import material_catalog
from .errors import AppError, argument_error
from .media import probe_media
from .project import TICKS_PER_SECOND, asset_map, create_snapshot, find_sequence, find_track, save_project
from .rights import add_record, load_ledger, save_ledger
from .utils import assert_id, atomic_write_json, atomic_write_text, ensure_inside, new_id, now_iso, sha256_file
from .validator import validate_project


def new_asset_id(project: dict[str, Any], requested: str | None, prefix: str) -> str:
    ident = requested or new_id(prefix)
    assert_id(ident, 'asset_id')
    if ident in asset_map(project):
        raise argument_error('资产 ID 已存在: ' + ident, 'asset_id')
    return ident


def append_audio(root: Path, project: dict[str, Any], asset: dict[str, Any], *, apply: bool,
                 sequence_id: str | None, track_id: str | None, start: float) -> dict[str, Any] | None:
    if not math.isfinite(start) or start < 0:
        raise argument_error('时间线起点必须为非负有限秒数', 'timeline_start_seconds')
    if not apply:
        return None
    if not track_id:
        raise argument_error('--apply 必须提供 --track-id', 'track_id')
    sequence = find_sequence(project, sequence_id)
    track = find_track(sequence, track_id, None)
    if track.get('kind') != 'audio' or track.get('locked') or track.get('muted'):
        raise argument_error('目标必须是未锁定、未静音的 audio 轨道', 'track_id')
    if asset['kind'] != 'audio':
        raise argument_error('只有音频素材可以应用到 audio 轨道', 'asset_id')
    tps = int(project.get('settings', {}).get('timebase', {}).get('ticks_per_second', TICKS_PER_SECOND))
    duration = max(1, round(float(asset['probe']['duration_seconds']) * tps))
    clip = dict(id=new_id('clip_community'), asset_id=asset['id'], enabled=True,
                timeline_start_tick=round(start * tps), source_in_tick=0, source_out_tick=duration,
                duration_tick=duration)
    track.setdefault('clips', []).append(clip)
    sequence['duration_tick'] = max([0, *(int(c.get('timeline_start_tick', 0)) + int(c.get('duration_tick', 0))
                                        for t in sequence.get('tracks', []) for c in t.get('clips', []))])
    return clip


def commit_asset(root: Path, project: dict[str, Any], asset: dict[str, Any], rights: dict[str, Any], *,
                 command: str, report: dict[str, Any], apply: bool = False, sequence_id: str | None = None,
                 track_id: str | None = None, start: float = 0.) -> dict[str, Any]:
    candidate = copy.deepcopy(project)
    snapshot = create_snapshot(root, project, label='before-' + command.replace('.', '-'))
    ledger = load_ledger(root)
    add_record(ledger, rights)
    candidate.setdefault('assets', []).append(asset)
    clip = append_audio(root, candidate, asset, apply=apply, sequence_id=sequence_id, track_id=track_id, start=start)
    validation = validate_project(root, candidate, rights_ledger=ledger, strict_rights=False)
    if not validation['ok']:
        raise AppError('COMMUNITY_ASSET_INVALID', '新增素材或时间线校验失败', exit_code=2,
                       cause=str(validation['errors']))
    operation_id = new_id('op')
    report_path = root / 'validation' / ('community_' + operation_id + '.json')
    change = dict(operation_id=operation_id, command=command, asset_id=asset['id'], at=now_iso(),
                  snapshot_id=snapshot['snapshot_id'], report=report_path.relative_to(root).as_posix())
    candidate.setdefault('provenance', {}).setdefault('change_log', []).append(change)
    atomic_write_json(report_path, dict(operation_id=operation_id, command=command, **report,
                                        asset=asset, rights=rights, generated_clip=clip, validation=validation))
    save_project(root, candidate)
    save_ledger(root, ledger)
    atomic_write_json(root / 'operations' / (operation_id + '.json'), {**change, 'status': 'succeeded'})
    return dict(asset=asset, rights=rights, generated_clip=clip, report=str(report_path),
                snapshot=snapshot, validation=validation, operation_id=operation_id, network='disabled')


def import_material(root: Path, project: dict[str, Any], ident: str, *, asset_id: str | None = None,
                    dry_run: bool = False, **placement: Any) -> dict[str, Any]:
    checked = material_catalog.verify(ident)
    row, col = checked['record'], checked['collection']
    aid = new_asset_id(project, asset_id, 'asset_material')
    directory = ensure_inside(root, root / 'assets/community' / aid)
    source = Path(checked['file'])
    destination = directory / source.name
    if directory.exists():
        raise argument_error('素材目标目录已存在', str(directory))
    kind = 'font' if row['kind'] == 'font' else 'audio'
    probe = probe_media(source)
    notice = (directory / 'NOTICE.txt').relative_to(root).as_posix()
    evidence = (directory / 'SOURCE.txt').relative_to(root).as_posix()
    asset = dict(id=aid, kind=kind, uri=destination.relative_to(root).as_posix(),
                 sha256='sha256:' + row['sha256'], probe=probe, rights_ref=aid,
                 source=dict(source_url='local://' + evidence, source_version=material_catalog.CATALOG_VERSION,
                             original_name=source.name, retrieved_at=now_iso(), community_material_id=ident))
    rights = dict(asset_id=aid, kind=kind, sha256=asset['sha256'], source_url='local://' + evidence,
                  source_version=material_catalog.CATALOG_VERSION, retrieved_at=now_iso(), creator=col['creator'],
                  license_spdx=col['license']['spdx'], license_url=notice,
                  attribution=f"{row['name']} by {col['creator']}; {col['license']['spdx']}; source and full credit in {notice}",
                  permitted_uses=['internal', 'commercial_ad'], permitted_channels=[],
                  restrictions=col['license']['obligations'], evidence=evidence,
                  verification_status='verified', verified_by='bundled-community-catalog-sha256',
                  takedown_status='clear', notes='License evidence covers the source asset; project context and downstream attribution remain required.')
    if dry_run:
        candidate = copy.deepcopy(project)
        append_audio(root, candidate, asset, **placement)
        return dict(asset=asset, rights=rights, resource_id=ident, verified=True, network='disabled')
    directory.mkdir(parents=True, exist_ok=False)
    try:
        shutil.copyfile(source, destination)
        shutil.copyfile(checked['notice'], directory / 'NOTICE.txt')
        # Inert, human-readable attribution evidence is copied into the project.
        # Runtime project/ledger references themselves remain local.
        original = material_catalog.DATA / col['evidence_path']
        atomic_write_text(directory / 'SOURCE.txt',
                          f"Resource: {ident}\nTitle: {row['name']}\nCreator: {col['creator']}\n"
                          f"Source page: {col['source_url']}\nArchive: {col['archive_name']}\n"
                          f"Archive SHA-256: {col['archive_sha256']}\nOriginal member: {row['original']['member']}\n"
                          f"Original SHA-256: {row['original']['sha256']}\nBundled SHA-256: {row['sha256']}\n"
                          f"Transformation: {row['transformation']}\nLicense: {col['license']['spdx']}\n"
                          f"License URL: {col['license']['url']}\nFull attribution: {col['license']['attribution']}\n\n"
                          + original.read_text('utf-8-sig'))
        assert sha256_file(destination) == row['sha256']
        return commit_asset(root, project, asset, rights, command='materials.ingest',
                            report=dict(resource_id=ident, source_sha256=row['sha256'],
                                        source_archive_sha256=col['archive_sha256'], evidence=evidence,
                                        transformation=row['transformation']), **placement)
    except BaseException:
        # Only files created by this operation can be removed; preserve a failed
        # directory for diagnosis if unexpected content appeared in it.
        for name in (source.name, 'NOTICE.txt', 'SOURCE.txt'):
            path = directory / name
            if path.is_file():
                path.unlink()
        if directory.is_dir() and not any(directory.iterdir()):
            directory.rmdir()
        raise
