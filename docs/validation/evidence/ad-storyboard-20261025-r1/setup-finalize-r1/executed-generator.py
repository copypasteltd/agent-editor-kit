"""Execute actual installed/Skill ad production, revision and package roundtrip."""
import argparse
import copy
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'docs/validation/evidence/ad-storyboard-20261025-r1'
PUBLIC = ROOT / 'docs/assets/ad-storyboard-20261025-r1'
PYTHON = 'C:/Python313/python.exe'
INSTALLED = ROOT / 'local/agent-ffmpeg/v0.1.0-alpha.4-local.12/final-r2/installed'


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def load(path):
    return json.loads(path.read_bytes())


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase', choices=('setup', 'setup-continue', 'setup-finalize', 'render', 'revision', 'roundtrip', 'skill'), required=True)
    parser.add_argument('--run', required=True)
    args = parser.parse_args(); assert args.run.replace('-', '').isalnum()
    out = BASE / (args.phase + '-' + args.run); out.mkdir(parents=True, exist_ok=False)
    (out / 'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    work = ROOT / 'workspace/ad-storyboard-20261025-installed-r1'
    project = work / 'project'
    environment = dict(os.environ)
    runtime = load(ROOT / 'local/agent-ffmpeg/runtime.json')
    environment.update(AEK_COMMUNITY_DEVICE_CONFIG=runtime['community_config'],
        AI_AD_EDITOR_RUNTIME_DIR=str(ROOT / 'product/.runtime'), PYTHONDONTWRITEBYTECODE='1',
        TEMP=str(ROOT / 'product/.runtime/temp'), TMP=str(ROOT / 'product/.runtime/temp'))
    prefix = [PYTHON, '-I', '-S', '-B', '-u', '-X', 'utf8', str(INSTALLED / 'run.py')]
    calls = []
    before = {p.name: sha(p) for p in (ROOT / 'product/src/ai_ad_editor').glob('*.py')}
    assert len(before) == 205 and before == {p.name: sha(p) for p in (INSTALLED / 'site/ai_ad_editor').glob('*.py')}
    report = dict(status='running', phase=args.phase, cli_version='0.1.14', native_windows=True,
                  virtualization=False, browser_ui=False, human_listening=False, natural_quality_acceptance=False,
                  started_at_utc=datetime.now(timezone.utc).isoformat())
    save(out / 'verification.json', report)

    def run(name, command, cli=False, expected=None, timeout=900):
        started = time.perf_counter()
        result = subprocess.run([str(x) for x in command], cwd=ROOT, env=environment, capture_output=True,
                                timeout=timeout, creationflags=subprocess.CREATE_NO_WINDOW)
        stdout, stderr = out / (name + '.stdout'), out / (name + '.stderr')
        stdout.write_bytes(result.stdout); stderr.write_bytes(result.stderr)
        entry = dict(name=name, argv=list(map(str, command)), exit_code=result.returncode,
                     elapsed_seconds=time.perf_counter()-started, stdout_sha256=sha(stdout), stderr_sha256=sha(stderr))
        calls.append(entry); save(out / 'calls.json', calls)
        print(json.dumps({k: entry[k] for k in ('name', 'exit_code', 'elapsed_seconds')}), flush=True)
        if cli:
            value = json.loads(result.stdout)
            if expected:
                assert not value['ok'] and value['errors'][0]['code'] == expected, value
            else:
                assert result.returncode == 0 and value['ok'], value
            return value['data'] if not expected else value
        assert result.returncode == 0, result.stderr.decode('utf8', 'replace')[-2000:]
        return result.stdout

    def cli(name, *argv, expected=None):
        return run(name, prefix + list(argv), cli=True, expected=expected)

    def fingerprint(name, path):
        raw = run(name + '-frames', ['ffmpeg', '-v', 'error', '-i', path, '-map', '0:v:0',
            '-pix_fmt', 'rgb24', '-f', 'framemd5', '-'])
        frames = [line.rsplit(b',', 1)[-1].strip().decode() for line in raw.splitlines() if line and not line.startswith(b'#')]
        pcm = run(name + '-pcm', ['ffmpeg', '-v', 'error', '-i', path, '-map', '0:a:0', '-ar', '48000', '-ac', '2', '-f', 'f32le', '-'])
        # Keep the audio itself local; evidence retains its exact digest/count.
        (out / (name + '-pcm.stdout')).unlink()
        calls[-1]['stdout_retained'] = False; save(out / 'calls.json', calls)
        value = dict(frames=frames, frame_count=len(frames), pcm_bytes=len(pcm), pcm_sha256=hashlib.sha256(pcm).hexdigest())
        save(out / (name + '-decoded.json'), value)
        return value

    def render(name, root, sequence, target, gpu=False):
        arguments = ['render', '--project', root, '--sequence-id', sequence['id'], '--output', target,
                     '--container', 'mkv', '--audio-codec', 'pcm_f32le', '--crf', '0', '--pixel-format', 'yuv420p',
                     '--hardware-encode', 'require' if gpu else 'off']
        if gpu:
            arguments += ['--hardware-encoder', 'nvenc']
        cli(name, *arguments)
        probe = json.loads(run(name + '-probe', ['ffprobe', '-v', 'error', '-show_streams', '-of', 'json', target]))
        video = next(s for s in probe['streams'] if s['codec_type'] == 'video')
        assert (video['width'], video['height']) == (sequence['canvas']['width'], sequence['canvas']['height'])
        decoded = fingerprint(name, target)
        assert decoded['frame_count'] == sequence['ad_storyboard']['frames']
        return decoded

    try:
        if args.phase in ('setup', 'setup-continue'):
            if args.phase == 'setup':
                work.mkdir(parents=True, exist_ok=False); PUBLIC.mkdir(parents=True, exist_ok=False)
                cli('init', 'project', 'init', project, '--name', 'Agent editor kit / reviewed product ad')
                cli('font', 'materials', 'ingest', '--project', project, '--id', 'noto-sans-sc-variable', '--asset-id', 'ad_font')
                music = cli('music-list', 'materials', 'list', '--kind', 'music', '--limit', '44')['records'][0]
                cli('music', 'materials', 'ingest', '--project', project, '--id', music['id'], '--asset-id', 'ad_music')
                font_path = INSTALLED / 'site/ai_ad_editor/material_data/fonts/noto-sans-sc-variable.ttf'
                font = ImageFont.truetype(str(font_path), 34)
                small = ImageFont.truetype(str(font_path), 17)
                source = PUBLIC / 'source'; source.mkdir()
                notice = source / 'SOURCE.txt'
                notice.write_text('Programmatically authored vector product-ad cards and motion, CC0-1.0.\n'
                    'Creator: agent editor kit contributors. Not a GUI screenshot or natural video quality benchmark.\n'
                    'Noto Sans SC font remains under its separately included SIL OFL license.\n', encoding='utf8')
                local_notice = project / 'assets/ad-source-license.txt'; shutil.copyfile(notice, local_notice)
                for index, (title, subtitle, color) in enumerate([
                    ('KEEP YOUR ORIGINALS', 'Original inputs stay intact', '#314a79'),
                    ('EDIT EACH SHOT', 'Picture  /  Captions  /  Sound', '#196d6a'),
                    ('DELIVER THREE FORMATS', 'Vertical  /  Wide  /  Square', '#705037'),
                    ('START A LOCAL EDIT', 'Open source. Editable. Local.', '#375b4a')]):
                    image = Image.new('RGB', (640, 360), '#111a29'); draw = ImageDraw.Draw(image)
                    draw.rounded_rectangle((26, 24, 614, 336), radius=22, fill=color)
                    draw.text((50, 48), 'agent editor kit', font=small, fill='#c6dedf')
                    draw.text((50, 110), title, font=font, fill='white')
                    draw.text((50, 170), subtitle, font=small, fill='white')
                    for row, width in enumerate((415, 330, 460)):
                        draw.rounded_rectangle((50, 225 + row * 24, 50 + width, 239 + row * 24), radius=4, fill='#b6d6d1')
                    card = source / ('card-' + str(index) + '.png'); image.save(card)
                    video = source / ('shot-' + str(index) + '.mp4')
                    run('source-' + str(index), ['ffmpeg', '-v', 'error', '-i', card, '-vf',
                        "zoompan=z='min(zoom+0.0002,1.04)':x='iw/2-iw/zoom/2':y='ih/2-ih/zoom/2':d=135:s=640x360:fps=30",
                        '-frames:v', '135', '-c:v', 'libx264', '-crf', '16', '-pix_fmt', 'yuv420p', video])
                    cli('ingest-' + str(index), 'media', 'ingest', '--project', project, '--input', video,
                        '--asset-id', 'ad_picture_' + str(index), '--source-url', 'local://assets/ad-source-license.txt',
                        '--license-spdx', 'CC0-1.0', '--license-url', 'local://assets/ad-source-license.txt',
                        '--evidence', 'local://assets/ad-source-license.txt', '--creator', 'agent editor kit contributors',
                        '--verification-status', 'verified', '--permitted-use', 'commercial_ad')
            lines = ['保留原始素材。', '自由修改每个镜头。', '现在开始本地剪辑。']
            srt = work / 'reviewed.srt'
            srt.write_text('\n\n'.join(f'{i+1}\n00:00:{i*4:02d},000 --> 00:00:{i*4+3:02d},500\n{line}' for i, line in enumerate(lines)) + '\n', encoding='utf8')
            dub = cli('gpu-voice-batch', 'dub', 'subtitles', '--project', project, '--input', srt,
                '--from', 'zh-Hans', '--to', 'zh-Hans', '--voice', 'zf_001', '--device', 'cuda', '--fit', 'reject')
            voice_report = load(Path(dub['report']))
            cues = voice_report['cues']; assert len(cues) == 3 and dub['total_generations'] == 3
            brief = dict(id='aek_demo', product='agent editor kit', audience='需要可编辑本地广告工程的视频创作者',
                cta='现在开始本地剪辑', caption_style={'font_asset_id': 'ad_font', 'font_ratio': .06},
                music={'asset_id': 'ad_music', 'gain_db': -27},
                shots=[dict(id=sid, asset_id='ad_picture_' + str(i), text=lines[i], fit='fit', weight=1,
                            voice={'asset_id': cues[i]['final_asset_id']}, rationale=reason)
                       for i, (sid, reason) in enumerate([('hook', '明确保留原始素材'), ('proof', '展示逐镜头可编辑结构'), ('cta', '明确本地开始剪辑的行动')])],
                variants=[dict(id=vid, canvas=canvas, duration_seconds=seconds) for vid, canvas, seconds in [
                    ('vertical12', {'width': 360, 'height': 640}, 12),
                    ('wide9', {'width': 640, 'height': 360}, 9),
                    ('square9', {'width': 360, 'height': 360}, 9)]])
            save(work / 'brief.json', brief); save(PUBLIC / 'reviewed-brief.json', brief)
            before_project = (project / 'project.json').read_bytes()
            plan = project / 'validation/storyboard.json'
            cli('storyboard-dry', 'ad', 'storyboard', '--project', project, '--input', work / 'brief.json', '--output', plan, '--dry-run')
            assert not plan.exists() and (project / 'project.json').read_bytes() == before_project
            cli('storyboard', 'ad', 'storyboard', '--project', project, '--input', work / 'brief.json', '--output', plan)
            assert (project / 'project.json').read_bytes() == before_project
            cli('build', 'ad', 'build', '--project', project, '--input', plan, '--idempotency-key', 'initial-ad')
            built = (project / 'project.json').read_bytes()
            cli('build-replay', 'ad', 'build', '--project', project, '--input', plan, '--idempotency-key', 'initial-ad')
            assert (project / 'project.json').read_bytes() == built
            cli('stale-plan', 'ad', 'build', '--project', project, '--input', plan, expected='AD_PROJECT_CHANGED')
            assert (project / 'project.json').read_bytes() == built
            save(work / 'state.json', dict(voice_report=dub['report'], devices=dub['devices'], brief=str(work / 'brief.json'),
                music_id=next(a['source']['community_material_id'] for a in load(project / 'project.json')['assets'] if a['id']=='ad_music'),
                original_assets={a['id']: a['sha256'] for a in load(project / 'project.json')['assets']}))
            report.update(variants=3, voice_generations=3, model_initializations=dub['model_initializations'], devices=dub['devices'],
                          stale_plan_rejected=True, idempotent_replay_preserved=True, dry_run_preserved=True)
        elif args.phase == 'setup-finalize':
            # Verify the completed native calls from the interrupted recorder;
            # do not rerun or relabel its successful model output or failed receipt.
            prior = BASE / 'setup-continue-r1'
            raw = load(prior / 'gpu-voice-batch.stdout')
            assert raw['ok'] and raw['provenance']['cli_version'] == '0.1.14'
            dub = raw['data']; assert dub['total_generations'] == 3 and dub['model_initializations'] == 1
            assert set(dub['devices']) == {'voice'} and dub['devices']['voice']['selected'] == 'cuda'
            voice_report = load(Path(dub['report']))
            assert voice_report['text_mode'] == 'preserve-original' and voice_report['translation_attempts'] == []
            assert all(cue['source_text'] == cue['translation'] for cue in voice_report['cues'])
            for name in ('storyboard-dry', 'storyboard', 'build', 'build-replay'):
                assert load(prior / (name + '.stdout'))['ok']
            assert load(prior / 'stale-plan.stdout')['errors'][0]['code'] == 'AD_PROJECT_CHANGED'
            current = load(project / 'project.json')
            assert len([s for s in current['sequences'] if s.get('ad_storyboard')]) == 3
            for asset in current['assets']:
                assert 'sha256:' + sha(project / asset['uri']) == asset['sha256']
            cli('validate-actual-project', 'validate', '--project', project)
            save(work / 'state.json', dict(voice_report=dub['report'], devices=dub['devices'], brief=str(work / 'brief.json'),
                music_id=next(a['source']['community_material_id'] for a in current['assets'] if a['id']=='ad_music'),
                original_assets={a['id']: a['sha256'] for a in current['assets']}))
            report.update(variants=3, recorded_actual_voice_generations=3, recorded_model_initializations=1,
                devices=dub['devices'], reviewed_original_text_preserved=True, translation_worker_calls=0,
                recording_failure_preserved='setup-continue-r1/verification.json',
                verified_prior_calls=[dict(path=p.relative_to(ROOT).as_posix(),sha256=sha(p)) for p in prior.glob('*.stdout')])
        elif args.phase == 'render':
            sequences = [s for s in load(project / 'project.json')['sequences'] if s.get('ad_storyboard')]
            results = {}
            for sequence in sequences:
                vid = sequence['ad_storyboard']['variant_id']; target = project / 'renders' / (vid + '.mkv')
                results[vid] = render(vid, project, sequence, target)
            wide = next(s for s in sequences if s['ad_storyboard']['variant_id'] == 'wide9')
            gpu = render('wide9-nvenc', project, wide, project / 'renders/wide9-nvenc.mkv', gpu=True)
            save(work / 'decoded-before.json', results)
            report.update(variant_frames={k: v['frame_count'] for k, v in results.items()}, nvenc_frame_count=gpu['frame_count'])
        elif args.phase in ('revision', 'skill'):
            if args.phase == 'skill':
                prefix = ['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
                          'C:/Users/carzy/.codex/skills/agent-ffmpeg-local-editor/scripts/run.ps1']
                version = cli('skill-version', 'version'); assert version['cli_version'] == '0.1.14'
                project = work / 'skill-restored'
                cli('skill-import', 'convert', 'import', '--input', work / 'campaign.aevpkg.zip', '--output', project)
            before_project = load(project / 'project.json')
            request = dict(campaign_id='aek_demo', variant_ids=['wide9'], shots=[dict(id='cta', asset_id='ad_picture_3',
                text='现在开始本地剪辑。\n' + ('开源 · 可编辑' if args.phase == 'skill' else 'agent editor kit'))])
            request_path = project / ('revision-' + args.phase + '.json'); save(request_path, request)
            plan = project / 'validation' / ('revision-' + args.phase + '.json')
            cli('revise', 'ad', 'revise', '--project', project, '--input', request_path, '--output', plan)
            cli('revise-build', 'ad', 'build', '--project', project, '--input', plan)
            current = load(project / 'project.json')
            for old, new in zip(before_project['sequences'], current['sequences']):
                if old.get('ad_storyboard', {}).get('variant_id') != 'wide9':
                    assert old == new
            sequence = next(s for s in current['sequences'] if s.get('ad_storyboard', {}).get('variant_id') == 'wide9')
            target = project / 'renders' / ('wide9-' + args.phase + '.mkv')
            decoded = render('revised-wide9', project, sequence, target)
            previous = load(work / 'decoded-before.json')['wide9'] if args.phase == 'revision' else load(work / 'decoded-revised.json')
            assert decoded['frames'][:180] == previous['frames'][:180]
            assert decoded['frames'][180:] != previous['frames'][180:]
            assert decoded['pcm_sha256'] == previous['pcm_sha256'] and decoded['pcm_bytes'] == previous['pcm_bytes']
            if args.phase == 'revision':
                save(work / 'decoded-revised.json', decoded)
            state = load(work / 'state.json')
            assert {a['id']: a['sha256'] for a in current['assets']} == state['original_assets']
            report.update(unselected_sequences_identical=True, first_180_decoded_frames_identical=True,
                          last_90_frames_changed=True, decoded_pcm_identical=True, original_assets_preserved=True)
        elif args.phase == 'roundtrip':
            package = work / 'campaign.aevpkg.zip'; restored = work / 'restored'
            cli('export', 'convert', 'export', '--project', project, '--target-format', 'package', '--output', package)
            cli('import', 'convert', 'import', '--input', package, '--output', restored)
            # Make every original project URI unavailable before the new render.
            offline = work / 'original-project-offline'; project.rename(offline)
            sequence = next(s for s in load(restored / 'project.json')['sequences'] if s.get('ad_storyboard', {}).get('variant_id') == 'wide9')
            decoded = render('restored-wide9', restored, sequence, restored / 'renders/wide9-restored.mkv')
            assert decoded == load(work / 'decoded-revised.json')
            cli('validate-restored', 'validate', '--project', restored)
            report.update(original_project_unavailable=True, rgb_frames_identical=True, pcm_identical=True,
                          package_sha256=sha(package), package_bytes=package.stat().st_size, editable_variants=3)
        assert before == {p.name: sha(p) for p in (ROOT / 'product/src/ai_ad_editor').glob('*.py')}
        assert before == {p.name: sha(p) for p in (INSTALLED / 'site/ai_ad_editor').glob('*.py')}
        report.update(status='passed', calls=len(calls), source_files=205, source_and_installed_equal=True,
                      finished_at_utc=datetime.now(timezone.utc).isoformat())
        save(out / 'verification.json', report)
        print(json.dumps(report, ensure_ascii=False), flush=True)
    except BaseException as exc:
        report.update(status='failed', error=repr(exc)); save(out / 'verification.json', report); raise


if __name__ == '__main__':
    main()
