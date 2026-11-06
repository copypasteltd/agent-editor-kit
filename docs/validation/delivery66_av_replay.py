"""Replay the accepted CLI66 neural master with a real, editable video track."""
import argparse
import array
import datetime as dt
from fractions import Fraction
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import sys

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import delivery66 as delivery
import delivery66_handoff as handoff

ROOT = delivery.ROOT
CODE_PHASE = handoff.BASE / 'av-replay-code-phase-r1/verification.json'
CONTRACTS = handoff.BASE / 'av-replay-contracts-r1/verification.json'
CODE = ('delivery66_av_replay.py', 'test_delivery66_av_replay.py',
        'continue_delivery66_handoff.py')


def check_code():
    phase = handoff.load(CODE_PHASE)
    handoff.require(phase['code_completed_before_functional_validation'] is True
                    and set(phase['files']) == set(CODE), 'Complete the whole replay batch first')
    for name, digest in phase['files'].items():
        handoff.require(handoff.sha(HERE / name) == digest, 'Replay batch changed: ' + name)
    for name, digest in phase['retained_inputs'].items():
        handoff.require(handoff.sha(handoff.local(ROOT / name)) == digest,
                        'Original accepted result or failure evidence changed: ' + name)
    return phase


def check_contracts():
    check_code()
    proof = handoff.load(CONTRACTS)
    handoff.require(proof['status'] == 'passed' and proof['tests'] == proof['discovered_tests'] == 8
                    and proof['failures'] == proof['errors'] == proof['skipped'] == 0
                    and proof['fixture_only'] is True
                    and proof['code_phase_sha256'] == handoff.sha(CODE_PHASE),
                    'The complete replay contract suite must pass')


def media_summary(probe, pcm):
    """Validate independent decoded content and exact video clock, including AAC padding."""
    streams = probe.get('streams', [])
    videos = [s for s in streams if s.get('codec_type') == 'video']
    audios = [s for s in streams if s.get('codec_type') == 'audio']
    if len(videos) != 1 or len(audios) != 1:
        raise ValueError('Exactly one real video and audio stream are required')
    video, audio = videos[0], audios[0]
    if ((video.get('width'), video.get('height')) != (320, 568)
            or int(video.get('nb_read_frames', 0)) != 300
            or Fraction(video['avg_frame_rate']) != 30
            or Fraction(video['time_base']) * int(video['duration_ts']) != 10):
        raise ValueError('The complete 300-frame 30fps video clock must be preserved')
    if (int(audio.get('channels', 0)) != 2 or int(audio.get('sample_rate', 0)) != 48000
            or Fraction(audio['time_base']) * int(audio['duration_ts']) != 10):
        raise ValueError('The complete 48kHz stereo audio clock must be preserved')
    if not pcm or len(pcm) > 4 * 1024**2 or len(pcm) % 8:
        raise ValueError('Invalid complete stereo Float32 payload')
    samples = array.array('f')
    samples.frombytes(pcm)
    if sys.byteorder != 'little':
        samples.byteswap()
    count = len(samples) // 2
    if not 480000 <= count <= 482048:
        raise ValueError('Missing audio or excessive AAC padding')
    if not all(math.isfinite(v) for v in samples):
        raise ValueError('Non-finite decoded audio')
    rms = math.sqrt(math.fsum(v * v for v in samples) / len(samples))
    peak = max(abs(v) for v in samples)
    if rms <= 0.0001 or peak > 2.0:
        raise ValueError('Silent or invalid decoded audio')
    return dict(video={k: video.get(k) for k in
                      ('width', 'height', 'avg_frame_rate', 'time_base', 'duration_ts', 'nb_read_frames')},
                audio=dict(sample_rate=48000, channels=2, decoded_samples_per_channel=count,
                           rms=rms, peak=peak, finite_non_silent=True,
                           complete_PCM_sha256=hashlib.sha256(pcm).hexdigest()))


def prerequisites(args):
    check_contracts()
    freeze = handoff.load(delivery.BASE / ('freeze-' + args.freeze_run) / 'verification.json')
    delivery.unchanged(freeze)
    for mode in ('source-all', 'installed-all'):
        proof = handoff.load(delivery.BASE / (mode + '-' + args.tests_run) / 'verification.json')
        handoff.require(proof['status'] == 'passed' and proof['tests'] == proof['discovered_tests'] == 4124
                        and proof['failures'] == proof['errors'] == proof['skipped'] == 0
                        and proof['file_hashes'] == freeze['file_hashes'] and proof['frozen_equal']
                        and proof['original_assertions_preserved'], 'Original complete regression required')
        if mode == 'installed-all':
            handoff.require(proof['source_fallback'] is False, 'Installed fallback is forbidden')
    candidate = handoff.load(delivery.BASE / ('candidate-' + args.candidate_run) / 'verification.json')
    installed = handoff.local(candidate['installed'])
    application = {p.name: handoff.sha(p) for p in (installed / 'site/ai_ad_editor').glob('*.py')}
    handoff.require(candidate['status'] == 'installed-and-byte-verified'
                    and candidate['cli_version'] == delivery.VERSION and len(application) == 289
                    and application == candidate['application_files']
                    and application == {p.name: handoff.sha(p) for p in delivery.SOURCE.glob('*.py')}
                    and handoff.sha(candidate['archive']) == candidate['archive_sha256'],
                    'The original byte-verified application is required')
    staged = handoff.load(delivery.BASE / ('skill-entry-' + args.stage_run) / 'verification.json')
    handoff.require(staged['status'] == 'passed' and staged['application_files'] == application,
                    'Accepted candidate Skill required')
    handoff.require(all(handoff.sha(handoff.local(Path(staged['home']) / name)) == digest
                        for name, digest in staged['skill_files'].items()), 'Candidate Skill changed')
    music_path = delivery.BASE / ('native-music-' + args.music_run) / 'verification.json'
    music = handoff.load(music_path)
    for key in ('actual_CUDA_music', 'complete_PCM_verified', 'project_placement_verified',
                'owned_process_cleanup_verified'):
        handoff.require(music.get(key) is True, 'Accepted actual music required: ' + key)
    handoff.require(music['status'] == 'passed' and music['application_files'] == application
                    and music['skill_files'] == staged['skill_files'] and music['source_fallback'] is False,
                    'Music belongs to another candidate')
    model = music['actual_generation']['worker']['model']
    handoff.require(model['neural_backend'] == 'cuda' and model['CPU_fallback'] is False
                    and set(model['forwards']) == {'text', 'language_model', 'diffusion', 'vae'}
                    and all(type(v) is int and v > 0 for v in model['forwards'].values())
                    and all(model['forward_output_devices'][k] == ['cuda:0'] for k in model['forwards']),
                    'Four actual CUDA components are required')
    source = handoff.local(music['artifacts']['project'])
    master = handoff.local(music['master_audio']['path'])
    handoff.require(handoff.sha(source / 'project.json') == music['project_manifest']['sha256']
                    and handoff.sha(master) == music['master_audio']['sha256']
                    and master.is_relative_to(source), 'The original accepted music changed')
    project = handoff.load(source / 'project.json')
    asset = next(a for a in project['assets'] if a['id'] == music['asset']['id'])
    handoff.require(asset['source']['music_generation'] == music['asset']['source']['music_generation']
                    and handoff.sha(source / asset['uri']) == music['master_audio']['sha256']
                    and music['actual_generation']['worker']['samples'] == 480000
                    and project['settings']['timebase'] ==
                    dict(ticks_per_second=90000, display_fps=dict(num=30, den=1)),
                    'Preserve the actual ten-second master, recipe and native clock')
    return freeze, candidate, music, music_path, source


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name, default in [('run', 'r2'), ('freeze-run', 'r6'), ('tests-run', 'r6'),
                          ('candidate-run', 'r1'), ('stage-run', 'r1'), ('music-run', 'r1')]:
        parser.add_argument('--' + name, default=default)
    args = parser.parse_args()
    handoff.require(os.name == 'nt' and sys.dont_write_bytecode and sys.prefix == sys.base_prefix,
                    'Use an existing native Windows interpreter')
    handoff.require(all(v.isalnum() for v in vars(args).values()), 'Invalid run identifier')
    freeze, candidate, music, music_path, source = prerequisites(args)
    out = delivery.BASE / ('package-replay-' + args.run)
    work = delivery.LOCAL / ('package-' + args.run)
    handoff.require(not out.exists() and not work.exists(), 'Preserve all earlier replay attempts')
    out.mkdir()
    work.mkdir()
    (out / 'executed-runner.py').write_bytes(Path(__file__).read_bytes())
    installed = Path(candidate['installed'])
    prefix = [sys.executable, '-I', '-S', '-B', '-u', '-X', 'utf8', installed / 'run.py']
    source_pins = {p.relative_to(source).as_posix(): handoff.sha(p)
                   for p in source.rglob('*') if p.is_file()}
    try:
        sys.path.insert(0, str(installed / 'site'))
        import ai_ad_editor
        from ai_ad_editor.media import ffmpeg_path, ffprobe_path
        from ai_ad_editor.runtime import configure_local_runtime
        handoff.require(Path(ai_ad_editor.__file__).resolve() == installed / 'site/ai_ad_editor/__init__.py',
                        'Load the actual installed application')
        configure_local_runtime()
        ffmpeg, ffprobe = ffmpeg_path(), ffprobe_path()
        original = work / 'original'
        shutil.copytree(source, original)
        project = handoff.load(original / 'project.json')
        project['settings']['canvas'].update(width=320, height=568)
        handoff.save(original / 'project.json', project)
        diagnostic = work / 'procedural-video.mp4'
        handoff.execute(out, 'make-diagnostic-video', [ffmpeg, '-nostdin', '-v', 'error',
            '-f', 'lavfi', '-i', 'testsrc2=size=320x568:rate=30:duration=10', '-an',
            '-c:v', 'libx264', '-threads', '2', '-pix_fmt', 'yuv420p', diagnostic])
        video = handoff.execute(out, 'ingest-diagnostic-video', [*prefix, 'media', 'ingest',
            '--project', original, '--input', diagnostic], cli=True)['data']['asset']
        changes = work / 'video-track.json'
        track = next(t for t in project['sequences'][0]['tracks'] if t['kind'] == 'video' and not t['locked'])
        handoff.save(changes, dict(operations=[dict(op='append_clip', id='replay_diagnostic_video',
            asset_id=video['id'], track_id=track['id'], timeline_start_tick=0,
            duration_tick=900000, source_in_tick=0, source_out_tick=900000)]))
        handoff.execute(out, 'compose-diagnostic-video', [*prefix, 'timeline', 'compose',
            '--project', original, '--input', changes], cli=True)
        handoff.execute(out, 'validate-authored-project', [*prefix, 'validate', '--project', original], cli=True)
        archive, restored = work / 'music.aevpkg.zip', work / 'restored'
        handoff.execute(out, 'export', [*prefix, 'convert', 'export', '--project', original,
            '--target-format', 'package', '--output', archive], cli=True)
        handoff.execute(out, 'import', [*prefix, 'convert', 'import', '--input', archive,
            '--output', restored], cli=True)
        decoded, measurements = {}, {}
        for label, project_root in [('original', original), ('restored', restored)]:
            saved = handoff.load(project_root / 'project.json')
            asset = next(a for a in saved['assets'] if a['id'] == music['asset']['id'])
            handoff.require(handoff.sha(project_root / asset['uri']) == music['master_audio']['sha256']
                            and asset['source']['music_generation'] == music['asset']['source']['music_generation'],
                            'Master WAV or complete generation recipe changed')
            movie = project_root / 'renders/music.mp4'
            handoff.execute(out, label + '-render', [*prefix, 'render', '--project', project_root,
                '--output', movie], cli=True)
            for kind, options in [('RGBA', ['-map', '0:v:0', '-an', '-pix_fmt', 'rgba']),
                                  ('PCM', ['-map', '0:a:0', '-vn', '-c:a', 'pcm_f32le'])]:
                raw = handoff.execute(out, label + '-' + kind, [ffmpeg, '-nostdin', '-v', 'error',
                    '-i', movie, *options, '-f', 'hash', '-hash', 'sha256', 'pipe:1'])
                digest = raw.decode().strip()
                handoff.require(len(digest) == 71 and digest.startswith('SHA256=')
                                and all(c in '0123456789abcdef' for c in digest[7:].lower()), 'Invalid full decoded digest')
                decoded[label + '_' + kind] = digest
            raw_probe = handoff.execute(out, label + '-probe', [ffprobe, '-v', 'error', '-count_frames',
                '-show_streams', '-show_format', '-of', 'json', movie])
            pcm = handoff.execute(out, label + '-PCM-samples', [ffmpeg, '-nostdin', '-v', 'error',
                '-i', movie, '-map', '0:a:0', '-vn', '-c:a', 'pcm_f32le', '-f', 'f32le', 'pipe:1'])
            measured = media_summary(json.loads(raw_probe), pcm)
            handoff.require(measured['audio']['complete_PCM_sha256'] ==
                            decoded[label + '_PCM'].split('=', 1)[1], 'Independent complete PCM differs')
            measurements[label] = measured
        handoff.require(decoded['original_RGBA'] == decoded['restored_RGBA']
                        and decoded['original_PCM'] == decoded['restored_PCM']
                        and measurements['original'] == measurements['restored'],
                        'Complete rendered media or clock differs after migration')
        delivery.unchanged(freeze)
        handoff.require(source_pins == {p.relative_to(source).as_posix(): handoff.sha(p)
                                       for p in source.rglob('*') if p.is_file()},
                        'Replay mutated the accepted generation project')
        check_code()
        handoff.save(out / 'verification.json', dict(status='passed', cli_version=delivery.VERSION,
            application_files=candidate['application_files'], complete_master_WAV_equal=True,
            complete_generation_recipe_equal=True, complete_rendered_RGBA_PCM_equal=True,
            decoded=decoded, measurements=measurements, generation_cli=delivery.VERSION,
            generation_reference=dict(path=str(music_path), sha256=handoff.sha(music_path)),
            new_model_forwards=0, human_listening=False, natural_quality_accepted=False,
            media_published=False, preview_canvas=[320, 568], project_package=str(archive),
            source_fallback=False,
            diagnostic_video=dict(kind='procedural FFmpeg testsrc2', duration_seconds=10, frames=300,
                created_for_validation=True, natural_video=False, sha256=handoff.sha(diagnostic)),
            source_generation_project_unchanged=True, original_audio_only_rejection_preserved=True,
            original_product_code_unchanged=True, replay_code_phase_sha256=handoff.sha(CODE_PHASE),
            observed_at_utc=dt.datetime.now(dt.timezone.utc).isoformat()))
    except BaseException as exc:
        handoff.save(out / 'verification.json', dict(status='failed', cli_version=delivery.VERSION,
            error=repr(exc), original_product_code_unchanged=True, formal_activation=False))
        raise


if __name__ == '__main__':
    main()
