"""Original16s score, real synthesis, editable package and full AV replay on independent installed59."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys
import wave

import numpy as np
from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT/'docs/validation/evidence/music-score-20261029-r1'


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def load(path):
    return json.loads(path.read_bytes())


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')


def original_score():
    tracks = []
    lead = []
    motif = [62, 69, 65, 64, 62, 65, 69, 72]
    for i in range(32):
        lead.append(dict(id=f'n{i:02d}', start_beat=i, duration_beats=.85,
                         pitch=motif[i%8]+(0 if i<16 else 12), velocity=.65 if i%4 else .8))
    tracks.append(dict(id='lead', instrument='pluck', gain_db=-12, pan=-.2, notes=lead))
    chords = [[50, 53, 57], [46, 50, 53], [48, 53, 57], [48, 52, 55]]
    pad = [dict(id=f'chord{c}_{i}', start_beat=c*8, duration_beats=7.8, pitch=p, velocity=.55)
           for c, chord in enumerate(chords) for i, p in enumerate(chord)]
    tracks.append(dict(id='harmony', instrument='pad', gain_db=-22, pan=.2, notes=pad))
    tracks.append(dict(id='bass', instrument='sine', gain_db=-16, pan=0,
        notes=[dict(id=f'b{i}', start_beat=i*4, duration_beats=3.8, pitch=[38, 34, 41, 36][i//2], velocity=.7) for i in range(8)]))
    tracks.append(dict(id='kick', instrument='kick', gain_db=-20, pan=0,
        notes=[dict(id=f'k{i}', start_beat=i*2, duration_beats=.45, pitch=36, velocity=.8) for i in range(16)]))
    tracks.append(dict(id='hat', instrument='hihat', gain_db=-28, pan=.35,
        notes=[dict(id=f'h{i}', start_beat=i+.5, duration_beats=.18, pitch=72, velocity=.65) for i in range(32)]))
    return dict(format='agent-music-score-v1', tempo_bpm=120, duration_beats=32,
                seed=20261029, master_gain_db=-3, limiter='none', tracks=tracks)


def draw_scope(path, pcm, score):
    image = Image.new('RGB', (960, 480), '#101925')
    draw = ImageDraw.Draw(image)
    draw.text((28, 16), 'ORIGINAL EDITABLE SCORE / CPU analytical synthesis / no neural model', fill='white')
    draw.text((28, 37), '16 seconds | 48 kHz stereo | 5 editable instrument tracks', fill='#92b7c7')
    for x in range(900):
        lo, hi = x*len(pcm)//900, (x+1)*len(pcm)//900
        peak = float(np.max(np.abs(pcm[lo:hi].astype(np.int32)), initial=0))/32768
        draw.line((30+x, 150-peak*85, 30+x, 150+peak*85), fill='#6bd7d0')
    colors = ['#5cc8ff', '#a8b0ff', '#ffa869', '#f07f91', '#c2dc83']
    for row, track in enumerate(score['tracks']):
        y = 256+row*36
        draw.text((30, y), track['id']+' / '+track['instrument'], fill=colors[row])
        for note in track['notes']:
            x = 220+note['start_beat']/32*710
            width = max(2, note['duration_beats']/32*710)
            draw.rectangle((x, y+3, x+width, y+19), fill=colors[row])
    for bar in range(9):
        x = 220+bar/8*710
        draw.line((x, 240, x, 449), fill='#344558', width=1)
    draw.text((30, 457), 'Waveform above is measured from actual generated PCM. Listening acceptance pending.', fill='#a1b0c4')
    image.save(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', required=True)
    parser.add_argument('--installed', type=Path, required=True)
    args = parser.parse_args()
    assert args.run.replace('-', '').isalnum() and sys.dont_write_bytecode
    gate = load(BASE/'contracts-r3/verification.json')
    assert gate['status'] == 'passed' and gate['tests'] == 19 and gate['frozen_equal']
    assert all(sha(ROOT/n) == v for n, v in gate['file_hashes'].items())
    out = BASE/('installed59-score-case-'+args.run); out.mkdir(exist_ok=False)
    (out/'executed-runner.py').write_bytes(Path(__file__).read_bytes())
    work = ROOT/'local/agent-ffmpeg'/('installed59-score-case-'+args.run); work.mkdir(exist_ok=False)
    namespace, runtime = ROOT/'agent-ffmpeg-local-install-manifest.json', ROOT/'local/agent-ffmpeg/runtime.json'
    guard = {str(p):sha(p) for p in [namespace, runtime]}
    registered = load(namespace)
    guard.update({str(ROOT/row['path']):row['sha256'] for row in registered['files']})
    installed=args.installed.resolve()
    assert installed.is_relative_to((ROOT/'local/agent-ffmpeg/v0.1.0-alpha.4-local.57').resolve())
    entry=installed/'run.py';assert entry.is_file()
    package=installed/'site/ai_ad_editor'
    source_pins={p.name:sha(p) for p in (ROOT/'product/src/ai_ad_editor').glob('*.py')}
    assert len(source_pins)==282 and source_pins=={p.name:sha(p) for p in package.glob('*.py')}
    acceptance=load(BASE/('installed59-score-'+args.run)/'verification.json')
    assert acceptance['status']=='passed' and acceptance['tests']==19
    assert acceptance['source_fallback'] is False and Path(acceptance['installed']).resolve()==installed
    calls = []

    def run(name, argv, cli=False):
        argv = list(map(str, argv))
        result = subprocess.run(argv, cwd=ROOT, capture_output=True, timeout=1800,
                                creationflags=subprocess.CREATE_NO_WINDOW)
        (out/(name+'.stdout')).write_bytes(result.stdout)
        (out/(name+'.stderr')).write_bytes(result.stderr)
        calls.append(dict(name=name, argv=argv, exit_code=result.returncode))
        save(out/'calls.json', calls)
        print(json.dumps(dict(name=name, exit_code=result.returncode)), flush=True)
        assert result.returncode == 0, (name, result.stderr[-1000:], result.stdout[-1500:])
        if cli:
            value = json.loads(result.stdout)
            assert value['ok'] and value['provenance']['cli_version'] == '0.1.59'
            return value['data']

    def cli(name, *argv):
        return run(name, [sys.executable, '-I', '-S', '-B', '-u', '-X', 'utf8', entry, *argv], True)

    ffmpeg = shutil.which('ffmpeg'); assert ffmpeg
    project, replay = work/'project', work/'replay'
    try:
        cli('version', 'version'); cli('init', 'project', 'init', project)
        request = work/'original-score.json'; save(request, original_score())
        inspected = cli('inspect', 'music', 'inspect-score', '--input', request)
        assert inspected['frames'] == 768000
        before = [(project/n).read_bytes() for n in ['project.json', 'rights-ledger.json']]
        cli('dry-run', 'music', 'compose', '--project', project, '--input', request, '--new-asset-id', 'score_demo', '--stems', '--dry-run')
        assert before == [(project/n).read_bytes() for n in ['project.json', 'rights-ledger.json']]
        result = cli('compose', 'music', 'compose', '--project', project, '--input', request,
                     '--new-asset-id', 'score_demo', '--stems', '--apply', '--track-id', 'track_audio_1')
        assert result['rights']['verification_status'] == 'unverified'
        original = project/result['asset']['uri']
        with wave.open(str(original), 'rb') as wav:
            assert (wav.getframerate(), wav.getnchannels(), wav.getnframes(), wav.getsampwidth()) == (48000, 2, 768000, 2)
            original_pcm = wav.readframes(wav.getnframes())
        assert len(original_pcm) == 3072000 and hashlib.sha256(original_pcm).hexdigest() == result['audio_stats']['PCM_sha256']
        assert len(result['audio_stats']['stems']) == 5
        for stem in result['audio_stats']['stems'].values():
            path = original.parent/stem['file']
            assert 'sha256:'+sha(path) == stem['sha256']
            with wave.open(str(path), 'rb') as wav:assert wav.getnframes() == 768000
        effects = {}
        for preset in ['whoosh', 'riser', 'impact', 'chime']:
            effect = cli('effect-'+preset, 'music', 'effect', '--project', project, '--preset', preset,
                         '--duration-seconds', '2', '--new-asset-id', preset)
            assert effect['audio_stats']['frames'] == 96000 and effect['audio_stats']['nonzero_samples'] > 0
            effects[preset] = dict(path=str(project/effect['asset']['uri']), sha256=effect['asset']['sha256'])
        assert len({v['sha256'] for v in effects.values()}) == 4
        scope = work/'actual.png'
        draw_scope(scope, np.frombuffer(original_pcm, dtype='<i2').reshape(-1, 2), original_score())
        notice = work/'SOURCE.txt'
        notice.write_text('Original score, analytical audio and diagnostic graphic authored by this harness; fixture media CC0-1.0. No copied recordings, sampled sound bank, model weights or human voice. The synthesizer source is MIT. Source score/output rights remain unverified by default in the product; this fixture is explicitly credited here.\n', encoding='utf-8')
        cli('ingest-scope', 'media', 'ingest', '--project', project, '--input', scope, '--asset-id', 'scope',
            '--license-spdx', 'CC0-1.0', '--verification-status', 'verified', '--creator', 'Agent Editor Kit original fixture', '--evidence', notice)
        changes = work/'timeline.json'
        save(changes, dict(operations=[dict(op='update_sequence', patch=dict(canvas=dict(width=320, height=180))),
            dict(op='append_clip', id='scope_clip', track_id='track_video_1', asset_id='scope',
                 source_in_tick=0, source_out_tick=1440000, duration_tick=1440000, timeline_start_tick=0)]))
        cli('timeline', 'timeline', 'compose', '--project', project, '--input', changes)
        # The audition is internal; generating a score never auto-verifies its rights.
        movie = project/'renders/score.mp4'
        cli('render', 'render', '--project', project, '--output', movie)
        package = work/'editable-score.zip'
        cli('export', 'convert', 'export', '--project', project, '--output', package, '--target-format', 'package')
        cli('import', 'convert', 'import', '--input', package, '--output', replay)
        canonical = replay/'assets/music-scores/score_demo/score.json'
        assert canonical.read_bytes() == (original.parent/'score.json').read_bytes()
        cli('recompose', 'music', 'compose', '--project', replay, '--input', canonical, '--new-asset-id', 'recomposed')
        with wave.open(str(replay/'assets/music-scores/recomposed/master.wav'), 'rb') as wav:
            assert wav.readframes(wav.getnframes()) == original_pcm
        replay_movie = replay/'renders/score.mp4'
        cli('replay', 'render', '--project', replay, '--output', replay_movie)
        decoded = {}
        for label, movie_path in [('original', movie), ('replay', replay_movie)]:
            for kind, options in [('rgba', ['-an', '-pix_fmt', 'rgba', '-f', 'rawvideo']),
                                  ('pcm', ['-vn', '-acodec', 'pcm_f32le', '-f', 'f32le'])]:
                target = work/(label+'.'+kind)
                run(label+'-'+kind, [ffmpeg, '-nostdin', '-v', 'error', '-n', '-i', movie_path, *options, target])
                decoded[label+'_'+kind] = dict(bytes=target.stat().st_size, sha256=sha(target))
        assert decoded['original_rgba'] == decoded['replay_rgba'] and decoded['original_rgba']['bytes'] == 110592000
        assert decoded['original_pcm'] == decoded['replay_pcm'] and decoded['original_pcm']['bytes'] == 6144000
        run('gif', [ffmpeg, '-nostdin', '-v', 'error', '-n', '-i', movie, '-vf', 'fps=4,scale=480:-1', '-an', work/'actual.gif'])
        assert all(sha(ROOT/n) == v for n, v in gate['file_hashes'].items())
        assert all(sha(Path(n)) == v for n, v in guard.items())
        source_case=load(BASE/'actual-case-r1/verification.json')
        assert source_case['audio']['PCM_sha256']==result['audio_stats']['PCM_sha256']
        assert source_case['decoded']==decoded
        assert source_pins=={p.name:sha(p) for p in package.glob('*.py')}
        report = dict(complete_source_installed_PCM_equal=True, complete_source_installed_AV_equal=True, status='passed', cli_version='0.1.59', source_only=False, source_fallback=False, installed=str(installed), neural_model=False,
            actual_model_forwards=0, device='cpu', audio=result['audio_stats'], effects=effects,
            complete_original_PCM_bytes=len(original_pcm), complete_recomposition_PCM_equal=True,
            complete_rendered_AV_replay_equal=True, decoded=decoded, source_frozen_equal=True,
            registered_skill_unchanged=True, registered_skill_cli=registered['cli_version'],
            inspected_and_dry_run_readonly=True, original_score_and_fixture_media='CC0-1.0',
            product_rights_remain_unverified_by_default=True, human_listening=False,
            neural_music_accepted=False, full_product_goal_closed=False,
            artifacts=dict(wav=str(original), movie=str(movie), png=str(scope), gif=str(work/'actual.gif'),
                           editable_package=str(package), score=str(request), source=str(notice)))
        save(out/'verification.json', report)
        print(json.dumps(dict(status='passed', cli_version='0.1.59', complete_PCM_recomposition=True, complete_AV_replay=True)), flush=True)
    except BaseException as error:
        save(out/'verification.json', dict(status='failed', error=repr(error), source_only=False, source_fallback=False, installed=str(installed), cli_version='0.1.59'))
        raise


if __name__ == '__main__':
    main()
