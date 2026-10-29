"""Replay actual generated music as editable assets and complete encoded AV."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'docs/validation/evidence/music-generation-20261030-r1'
PYTHON = 'C:/Python313/python.exe'


def load(path):
    return json.loads(path.read_bytes())


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--case-run', required=True)
    parser.add_argument('--run', required=True)
    args = parser.parse_args()
    assert all(v.replace('-', '').isalnum() for v in (args.run, args.case_run)) and sys.dont_write_bytecode
    case_path = BASE / ('actual-' + args.case_run) / 'verification.json'
    case = load(case_path)
    assert case['status'] == 'passed' and case['cli_version'] == '0.1.64'
    assert case['complete_PCM_roundtrip_verified']
    assert all(sha(ROOT / path) == value for path, value in case['source_hashes'].items())
    out = BASE / ('package-' + args.run)
    out.mkdir()
    (out / 'executed-runner.py').write_bytes(Path(__file__).read_bytes())
    work = ROOT / 'local/agent-ffmpeg' / ('music-generation64-package-' + args.run)
    work.mkdir()
    project = Path(case['artifacts']['project'])
    entry = case.get('entrypoint') or [PYTHON, '-E', '-B', '-u', '-X', 'utf8', project.parent / 'source_entry.py']
    calls = []

    def command(name, argv, cli=False):
        started = time.monotonic()
        result = subprocess.run(list(map(str, argv)), cwd=ROOT, capture_output=True, timeout=900,
                                creationflags=subprocess.CREATE_NO_WINDOW)
        (out / (name + '.stdout')).write_bytes(result.stdout)
        (out / (name + '.stderr')).write_bytes(result.stderr)
        calls.append(dict(name=name, argv=list(map(str, argv)), exit_code=result.returncode,
                          elapsed_seconds=time.monotonic() - started))
        save(out / 'calls.json', calls)
        assert result.returncode == 0, (name, result.stdout[-2000:], result.stderr[-2000:])
        print(json.dumps(dict(name=name, status='passed')), flush=True)
        if cli:
            value = json.loads(result.stdout)
            assert value['ok'] and value['provenance']['cli_version'] == '0.1.64'
            return value['data']
        return result.stdout

    def cli(name, *argv):
        return command(name, [*entry, *argv], True)

    try:
        sys.path.insert(0, str(ROOT / 'product/src'))
        from ai_ad_editor.runtime import configure_local_runtime
        from ai_ad_editor.media import ffmpeg_path
        configure_local_runtime()
        ffmpeg = ffmpeg_path()
        audio = Path(case['artifacts']['wav'])
        command('decode-master', [ffmpeg, '-nostdin', '-v', 'error', '-n', '-i', audio,
                '-map', '0:a:0', '-c:a', 'pcm_f32le', '-f', 'f32le', work / 'master.f32'])
        raw = (work / 'master.f32').read_bytes()
        assert 'sha256:' + hashlib.sha256(raw).hexdigest() == case['actual_generation']['worker']['output_PCM_sha256']
        signal = np.frombuffer(raw, dtype='<f4').reshape(-1, 2)
        samples = case['actual_generation']['worker']['samples']
        assert len(signal) == samples and np.isfinite(signal).all()
        image = Image.new('RGB', (960, 480), '#101925')
        draw = ImageDraw.Draw(image)
        draw.text((28, 20), 'ACTUAL NATIVE CUDA MUSIC / ACE-Step 1.5 Turbo / internal review', fill='white')
        draw.text((28, 50), f'{samples} stereo samples | 48 kHz Float32 | {samples / 48000:g} seconds', fill='#aac5d6')
        maximum = max(1., float(np.abs(signal).max()))
        for channel in (0, 1):
            center = 172 + channel * 165
            for x in range(900):
                section = signal[x * samples // 900:(x + 1) * samples // 900, channel]
                lo, hi = float(section.min()) / maximum, float(section.max()) / maximum
                draw.line((30 + x, center - hi * 58, 30 + x, center - lo * 58), fill=['#61d2ca', '#80b8fb'][channel])
            draw.text((30, center + 66), ['LEFT / measured PCM', 'RIGHT / measured PCM'][channel], fill='#a6bed0')
        draw.text((28, 450), 'No padding, looping, resampling or normalization. Musical/lyric quality and output rights await review.', fill='#b8c5d1')
        image.save(work / 'actual.png')
        notice = work / 'SOURCE.txt'
        notice.write_text('Diagnostic visual authored from measured PCM by this harness; visual source CC0-1.0. '
                          'The neural audio remains unverified/internal and is not licensed or approved for public distribution. '
                          'This card is not a GUI screenshot or a recording of a human performance.\n', encoding='utf-8')
        cli('ingest-diagnostic', 'media', 'ingest', '--project', project, '--input', work / 'actual.png',
            '--asset-id', 'music_diagnostic', '--license-spdx', 'CC0-1.0', '--verification-status', 'verified',
            '--creator', 'Agent Editor Kit diagnostic visualization', '--evidence', notice)
        span = case['clip']['duration_tick']
        changes = work / 'timeline.json'
        save(changes, dict(operations=[dict(op='update_sequence', patch=dict(canvas=dict(width=320, height=180))),
            dict(op='append_clip', id='diagnostic_clip', track_id='track_video_1', asset_id='music_diagnostic',
                 source_in_tick=0, source_out_tick=span, duration_tick=span, timeline_start_tick=0)]))
        cli('timeline', 'timeline', 'compose', '--project', project, '--input', changes)
        original = project / 'renders/neural-music.mp4'
        cli('render-original', 'render', '--project', project, '--output', original)
        package = work / 'editable-neural-music.zip'
        cli('export', 'convert', 'export', '--project', project, '--target-format', 'package', '--output', package)
        replay = work / 'replay'
        cli('import', 'convert', 'import', '--input', package, '--output', replay)
        imported = next(asset for asset in load(replay / 'project.json')['assets'] if asset['id'] == case['asset']['id'])
        assert imported['source']['music_generation'] == case['asset']['source']['music_generation']
        assert sha(replay / imported['uri']) == sha(audio)
        reproduced = replay / 'renders/neural-music.mp4'
        cli('render-replay', 'render', '--project', replay, '--output', reproduced)
        decoded = {}
        for label, movie in [('original', original), ('replay', reproduced)]:
            for kind, options in [('RGBA', ['-an', '-pix_fmt', 'rgba', '-f', 'rawvideo']),
                                  ('PCM', ['-vn', '-c:a', 'pcm_f32le', '-f', 'f32le'])]:
                target = work / (label + '.' + kind.lower())
                command(label + '-' + kind, [ffmpeg, '-nostdin', '-v', 'error', '-n', '-i', movie, *options, target])
                decoded[label + '_' + kind] = dict(bytes=target.stat().st_size, sha256=sha(target))
        assert decoded['original_RGBA'] == decoded['replay_RGBA'] and decoded['original_RGBA']['bytes'] > 0
        assert decoded['original_PCM'] == decoded['replay_PCM'] and decoded['original_PCM']['bytes'] > 0
        assert all(sha(ROOT / path) == value for path, value in case['source_hashes'].items())
        report = dict(status='passed', cli_version='0.1.64', actual_case_sha256=sha(case_path),
            entrypoint=list(map(str, entry)), installed=case.get('installed'), source_fallback=case.get('source_fallback'),
            actual_PowerShell_entry=case.get('actual_PowerShell_entry', False),
            source_frozen_equal=True, complete_master_WAV_equal=True, complete_generation_recipe_equal=True,
            complete_rendered_RGBA_PCM_equal=True, decoded=decoded,
            original_model_forwards=case['actual_generation']['worker']['model']['forwards'], new_model_forwards=0,
            generated_audio_rights='unverified/internal', media_published=False,
            human_listening=False, natural_quality_accepted=False,
            AAC_movie_is_not_lossless_master=True,
            artifacts=dict(movie=str(original), replay_movie=str(reproduced), wav=str(audio),
                           png=str(work / 'actual.png'), package=str(package), replay=str(replay)))
        save(out / 'verification.json', report)
        print(json.dumps({k:v for k,v in report.items() if k != 'artifacts'}), flush=True)
    except BaseException as exc:
        save(out / 'verification.json', dict(status='failed', cli_version='0.1.64', error=repr(exc), calls=calls))
        raise


if __name__ == '__main__':
    main()
