"""Native local music preparation and explicit speech/music ducking."""
from __future__ import annotations

import math
import wave
from pathlib import Path
from typing import Any

import numpy as np

from .errors import AppError, argument_error
from .material_project import commit_asset, new_asset_id
from .media import ffmpeg_path, probe_media
from .policy import require_local_reference, resolve_local_path
from .project import asset_map
from .rights import active_records, load_ledger
from .utils import ensure_inside, now_iso, run_process, sha256_file

ENGINE = 'community-audio-ffmpeg-v1'
SAMPLE_RATE = 48000


def finite(value: float, field: str, minimum: float, maximum: float) -> float:
    if not math.isfinite(value) or not minimum <= value <= maximum:
        raise argument_error(f'{field} 必须在 {minimum}–{maximum} 之间', field)
    return value


def source_asset(root: Path, project: dict[str, Any], ident: str) -> tuple[dict[str, Any], Path, dict[str, Any]]:
    asset = asset_map(project).get(ident)
    if not asset or asset.get('kind') not in {'audio', 'video'}:
        raise argument_error('音频源必须引用已导入的 audio/video 资产', 'asset_id')
    path = resolve_local_path(root, asset['uri'], field='asset.uri')
    if not path.is_file() or 'sha256:' + sha256_file(path) != asset.get('sha256'):
        raise AppError('AUDIO_SOURCE_CHANGED', '音频源缺失或摘要与工程不符', exit_code=3, path=str(path))
    probe = probe_media(path)
    if not probe.get('audio', {}).get('codec') or float(probe.get('duration_seconds', 0)) <= 0:
        raise argument_error('源文件没有有效音轨或正时长', 'asset_id')
    return asset, path, probe


def output_path(root: Path, output: str | None, aid: str) -> Path:
    if output:
        require_local_reference(output, field='output')
    path = Path(output) if output else Path('assets/community-audio') / (aid + '.wav')
    path = ensure_inside(root / 'assets', path if path.is_absolute() else root / path)
    if path.suffix.casefold() != '.wav' or path.exists():
        raise argument_error('输出必须为尚不存在的工程 assets/ 内 WAV', 'output')
    return path


def pcm_stats(path: Path) -> dict[str, Any]:
    with wave.open(str(path), 'rb') as wav:
        assert wav.getsampwidth() == 2
        channels, rate, frames = wav.getnchannels(), wav.getframerate(), wav.getnframes()
        pcm = np.frombuffer(wav.readframes(frames), dtype='<i2').astype(np.float64) / 32768.
    if not pcm.size or not np.isfinite(pcm).all():
        raise AppError('AUDIO_OUTPUT_INVALID', '音频输出为空或无效', exit_code=6)
    rms = float(np.sqrt(np.mean(pcm * pcm)))
    peak = float(np.abs(pcm).max())
    return dict(sample_rate=rate, channels=channels, frames=frames, duration_seconds=frames / rate,
                rms=rms, rms_dbfs=20 * math.log10(max(rms, 1e-12)), peak=peak,
                peak_dbfs=20 * math.log10(max(peak, 1e-12)), clipped_samples=int(np.sum(np.abs(pcm) >= 32767 / 32768)))


def generated_audio(root: Path, project: dict[str, Any], output: Path, aid: str,
                    parents: list[dict[str, Any]], command: str, plan: dict[str, Any],
                    placement: dict[str, Any]) -> dict[str, Any]:
    probe = probe_media(output)
    stats = pcm_stats(output)
    if stats['frames'] != plan['output_samples']:
        raise AppError('AUDIO_DURATION_MISMATCH', '音频输出样本数不符合请求', exit_code=6)
    digest = 'sha256:' + sha256_file(output)
    parent_refs = list(dict.fromkeys(p.get('rights_ref') or p['id'] for p in parents))
    rights_by_id = {r['asset_id']: r for r in active_records(load_ledger(root))}
    if any(ref not in rights_by_id for ref in parent_refs):
        raise AppError('RIGHTS_RECORD_MISSING', '音频源缺少权利记录', exit_code=7)
    records = [rights_by_id[ref] for ref in parent_refs]
    verified = all(r.get('verification_status') == 'verified' and r.get('takedown_status') == 'clear' for r in records)
    commercial = all('commercial_ad' in r.get('permitted_uses', []) or 'all' in r.get('permitted_uses', []) for r in records)
    evidence = ('assets/community-audio/' + aid + '-SOURCE.txt')
    asset = dict(id=aid, kind='audio', uri=output.relative_to(root).as_posix(), sha256=digest, probe=probe,
                 rights_ref=aid, source=dict(source_url='local://' + evidence, source_version=ENGINE,
                                            retrieved_at=now_iso(), original_name=output.name, derived_from=parent_refs))
    rights = dict(asset_id=aid, kind='audio', sha256=digest, source_url='local://' + evidence,
                  source_version=ENGINE, creator='local audio preparation', retrieved_at=now_iso(),
                  license_spdx='LicenseRef-Derived-Audio', license_url=evidence,
                  attribution='Prepared or mixed from ' + ', '.join(parent_refs) + '; edits and original credits in source evidence',
                  permitted_uses=['internal'] + (['commercial_ad'] if commercial else []),
                  restrictions=list(dict.fromkeys(s for r in records for s in r.get('restrictions', []))),
                  derived_from=parent_refs, evidence=evidence,
                  verification_status='verified' if verified else 'unverified', verified_by=ENGINE if verified else '',
                  takedown_status='clear', notes='Parent restrictions and attribution survive trimming, looping and mixing.')
    from .utils import atomic_write_text
    atomic_write_text(root / evidence, 'Derived audio\n' + str(plan) + '\n\nParent credits\n' +
                      '\n'.join(str({k: r.get(k) for k in ('asset_id', 'creator', 'license_spdx', 'attribution', 'license_url', 'evidence')}) for r in records))
    return {**commit_asset(root, project, asset, rights, command=command,
                            report=dict(engine=ENGINE, plan=plan, audio_stats=stats), **placement),
            'engine': ENGINE, 'plan': plan, 'audio_stats': stats}


def execute(root: Path, project: dict[str, Any], aid: str, output: Path, parents: list[dict[str, Any]],
            command: str, plan: dict[str, Any], argv: list[str], placement: dict[str, Any], dry_run: bool) -> dict[str, Any]:
    if dry_run:
        return dict(engine=ENGINE, asset_id=aid, output=str(output), plan=plan, command=argv, network='disabled')
    output.parent.mkdir(parents=True, exist_ok=True)
    created = False
    try:
        # -n prevents replacing any file created concurrently after planning.
        result = run_process(argv, timeout=min(3600., 120 + plan['duration_seconds'] * 12), cwd=root)
        if result.returncode:
            raise AppError('AUDIO_PROCESS_FAILED', '本地音频处理失败', exit_code=6, cause=result.stderr[-4000:])
        created = True
        return generated_audio(root, project, output, aid, parents, command, plan, placement)
    except BaseException:
        if created:
            output.unlink(missing_ok=True)
        raise


def prepare(root: Path, project: dict[str, Any], *, asset_id: str, output: str | None,
            duration: float, offset: float, loop: bool, gain_db: float, fade_in: float,
            fade_out: float, new_id: str | None, placement: dict[str, Any], dry_run: bool) -> dict[str, Any]:
    duration = finite(duration, 'duration_seconds', 1 / SAMPLE_RATE, 3600)
    offset = finite(offset, 'offset_seconds', 0, 3600 * 24)
    finite(gain_db, 'gain_db', -60, 12)
    finite(fade_in, 'fade_in_seconds', 0, duration)
    finite(fade_out, 'fade_out_seconds', 0, duration)
    source, path, probe = source_asset(root, project, asset_id)
    source_duration = float(probe['duration_seconds'])
    if offset >= source_duration or not loop and offset + duration > source_duration + 1 / SAMPLE_RATE:
        raise argument_error('源音频覆盖不足；需调整区间或显式 --loop', 'duration_seconds/offset_seconds')
    aid = new_asset_id(project, new_id, 'asset_music')
    target = output_path(root, output, aid)
    samples = round(duration * SAMPLE_RATE)
    actual_duration = samples / SAMPLE_RATE
    plan = dict(source_asset_id=asset_id, source_sha256=source['sha256'], duration_seconds=actual_duration,
                output_samples=samples, sample_rate=SAMPLE_RATE, channels=2, offset_seconds=offset,
                loop=loop, gain_db=gain_db, fade_in_seconds=fade_in, fade_out_seconds=fade_out,
                loop_is_not_seam_correction=True)
    filters = [f'atrim=start={offset:.9f}', 'asetpts=PTS-STARTPTS', 'aresample=48000',
               'aformat=sample_fmts=fltp:channel_layouts=stereo', f'atrim=end_sample={samples}', f'volume={gain_db:.9f}dB']
    if fade_in:
        filters.append(f'afade=t=in:st=0:d={fade_in:.9f}')
    if fade_out:
        filters.append(f'afade=t=out:st={max(0, actual_duration-fade_out):.9f}:d={fade_out:.9f}')
    argv = [ffmpeg_path(), '-hide_banner', '-v', 'error', '-nostdin', '-n']
    if loop:
        argv += ['-stream_loop', '-1']
    argv += ['-i', str(path), '-vn', '-af', ','.join(filters), '-ar', '48000', '-ac', '2', '-c:a', 'pcm_s16le', str(target)]
    return execute(root, project, aid, target, [source], 'music.prepare', plan, argv, placement, dry_run)


def mix(root: Path, project: dict[str, Any], *, voice_asset_id: str, music_asset_id: str,
        output: str | None, duration: float | None, voice_gain_db: float, music_gain_db: float,
        duck: bool, threshold: float, ratio: float, attack: float, release: float,
        loop_music: bool, new_id: str | None, placement: dict[str, Any], dry_run: bool) -> dict[str, Any]:
    voice, voice_path, voice_probe = source_asset(root, project, voice_asset_id)
    music, music_path, music_probe = source_asset(root, project, music_asset_id)
    voice_duration = float(voice_probe['duration_seconds'])
    duration = voice_duration if duration is None else finite(duration, 'duration_seconds', voice_duration, 3600)
    finite(voice_gain_db, 'voice_gain_db', -60, 12)
    finite(music_gain_db, 'music_gain_db', -60, 12)
    finite(threshold, 'duck_threshold', 0.00097563, 1)
    finite(ratio, 'duck_ratio', 1, 20)
    finite(attack, 'duck_attack_ms', 0.01, 2000)
    finite(release, 'duck_release_ms', 0.01, 9000)
    if not loop_music and float(music_probe['duration_seconds']) + 1 / SAMPLE_RATE < duration:
        raise argument_error('配乐覆盖不足；先 prepare 或显式 --loop-music', 'music_asset_id')
    aid = new_asset_id(project, new_id, 'asset_mix')
    target = output_path(root, output, aid)
    samples = round(duration * SAMPLE_RATE)
    plan = dict(voice_asset_id=voice_asset_id, music_asset_id=music_asset_id,
                source_sha256=[voice['sha256'], music['sha256']], duration_seconds=samples / SAMPLE_RATE,
                output_samples=samples, sample_rate=SAMPLE_RATE, channels=2,
                voice_gain_db=voice_gain_db, music_gain_db=music_gain_db, loop_music=loop_music,
                ducking=dict(enabled=duck, threshold=threshold, ratio=ratio, attack_ms=attack, release_ms=release),
                limiter=dict(limit=0.95, automatic_makeup=False, latency_compensated=True),
                voice_truncated=False, original_stems_preserved=True)
    voice_chain = f'[0:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,volume={voice_gain_db}dB,apad,atrim=end_sample={samples},asetpts=PTS-STARTPTS'
    music_chain = f'[1:a]aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo,volume={music_gain_db}dB,atrim=end_sample={samples},asetpts=PTS-STARTPTS[bed]'
    filters = [voice_chain + (',asplit=2[voice][key]' if duck else '[voice]'), music_chain]
    if duck:
        filters.append(f'[bed][key]sidechaincompress=threshold={threshold}:ratio={ratio}:attack={attack}:release={release}:makeup=1[ducked]')
    filters.append(f'[voice][{"ducked" if duck else "bed"}]amix=inputs=2:normalize=0:duration=longest:dropout_transition=0,alimiter=limit=0.95:level=0:latency=1,atrim=end_sample={samples}[out]')
    argv = [ffmpeg_path(), '-hide_banner', '-v', 'error', '-nostdin', '-n', '-i', str(voice_path)]
    if loop_music:
        argv += ['-stream_loop', '-1']
    argv += ['-i', str(music_path), '-filter_complex', ';'.join(filters), '-map', '[out]',
             '-ar', '48000', '-ac', '2', '-c:a', 'pcm_s16le', str(target)]
    return execute(root, project, aid, target, [voice, music], 'music.mix', plan, argv, placement, dry_run)
