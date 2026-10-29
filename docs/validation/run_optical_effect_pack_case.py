"""Exercise the eight editable optical templates using the installed CLI63.

Source and formal Skill remain frozen. Outputs are original project studies,
not natural-footage quality or an independent clean-machine acceptance claim.
"""
import argparse
import copy
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import time
import wave

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]
PACK = ROOT / 'docs/content/effect-packs/optical-v1'
DELIVERY = ROOT / 'docs/validation/evidence/job-enumeration-20261029-r1'


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def load(p):
    return json.loads(p.read_bytes())


def save(p, value):
    p.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')


def original_study(path):
    image = Image.new('RGB', (480, 270))
    pixels = image.load()
    for y in range(270):
        for x in range(480):
            r = math.exp(-(((x - 370) / 150) ** 2 + ((y - 65) / 150) ** 2))
            b = math.exp(-(((x - 85) / 160) ** 2 + ((y - 210) / 180) ** 2))
            pixels[x, y] = (int(9 + 38 * r + 6 * b), int(16 + 21 * r + 16 * b), int(28 + 7 * r + 42 * b))
    d = ImageDraw.Draw(image)
    d.ellipse((95, 223, 389, 253), fill='#0a101d')
    d.rounded_rectangle((196, 80, 284, 227), radius=20, fill='#c9d7df', outline='#f1f5fa', width=2)
    d.rectangle((212, 62, 268, 89), fill='#ccaf6b', outline='#f8e8b0', width=2)
    d.rectangle((218, 52, 262, 63), fill='#151f2e', outline='#e4d3a0')
    d.rounded_rectangle((204, 91, 213, 210), radius=4, fill='#f8fbff')
    d.rounded_rectangle((218, 119, 271, 177), radius=3, fill='#14243b', outline='#e9ca86')
    d.line((230, 132, 259, 132), fill='#f2deb2', width=2)
    d.line((230, 145, 259, 145), fill='#f2deb2', width=2)
    d.line((236, 158, 253, 158), fill='#f2deb2', width=2)
    for x, color in [(65, '#df9b55'), (99, '#c7566a'), (133, '#71b8d4'), (340, '#ffffff'), (374, '#f2ddb0')]:
        d.ellipse((x, 195, x + 14, 209), fill=color)
    for x, y in [(350, 54), (113, 73), (324, 152)]:
        d.line((x - 8, y, x + 8, y), fill='#f7f8ff', width=2)
        d.line((x, y - 8, x, y + 8), fill='#f7f8ff', width=2)
    image.save(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', required=True)
    args = parser.parse_args()
    assert args.run.replace('-', '').isalnum()
    install = load(DELIVERY / 'installation-candidate-r1/verification.json')
    assert install['status'] == 'installed-and-byte-verified' and install['cli_version'] == '0.1.63'
    installed = Path(install['installed'])
    code = ROOT / 'product/src/ai_ad_editor'
    source_pins = {p.name: sha(p) for p in code.glob('*.py')}
    assert len(source_pins) == 283
    assert source_pins == {p.name: sha(p) for p in (installed / 'site/ai_ad_editor').glob('*.py')}
    guard = install['registered_skill_file_hashes']
    assert all(sha(Path(p)) == h for p, h in guard.items())
    catalog = load(PACK / 'catalog.json')
    assert catalog['template_count'] == 8 and all(sha(PACK / r['template']) == r['sha256'] for r in catalog['items'])
    home = ROOT / 'local/agent-ffmpeg' / ('optical-pack63-' + args.run)
    out = ROOT / 'docs/validation/evidence' / ('optical-pack-20261029-' + args.run)
    public = ROOT / 'docs/assets' / ('optical-pack-20261029-' + args.run)
    for p in (home, out, public):
        p.mkdir(parents=True, exist_ok=False)
    (out / 'executed-runner.py').write_bytes(Path(__file__).read_bytes())
    original_study(public / 'source.png')
    # Quiet original diagnostic tones; not a music-generation quality sample.
    with wave.open(str(public / 'source.wav'), 'wb') as stream:
        stream.setparams((2, 2, 48000, 0, 'NONE', 'not compressed'))
        for start in range(0, 192000, 4096):
            data = bytearray()
            for i in range(start, min(start + 4096, 192000)):
                fade = min(1, i / 2400, (191999 - i) / 2400)
                a = int(1400 * fade * (math.sin(2 * math.pi * 220 * i / 48000) + .25 * math.sin(2 * math.pi * 330 * i / 48000)))
                data.extend(struct.pack('<hh', a, a))
            stream.writeframesraw(data)
    (public / 'SOURCE.txt').write_text('Original geometric product study and two-tone diagnostic audio authored by agent editor kit, 2026-10-29. CC0-1.0 for these two media files. No external photography, trademark, model weights or music recording. Templates remain MIT. No natural quality or listening approval claim.\n', encoding='utf-8')
    calls = []
    def run(name, argv, cli=False, binary=False, expected=0):
        t = time.monotonic()
        result = subprocess.run(list(map(str, argv)), cwd=ROOT, capture_output=True, timeout=1800,
                                creationflags=subprocess.CREATE_NO_WINDOW)
        (out / (name + '.stderr')).write_bytes(result.stderr)
        if not binary:
            (out / (name + '.stdout')).write_bytes(result.stdout)
        calls.append(dict(name=name, exit_code=result.returncode, elapsed_seconds=time.monotonic() - t,
                          stdout_bytes=len(result.stdout), stdout_sha256=hashlib.sha256(result.stdout).hexdigest()))
        save(out / 'calls.json', calls)
        print(json.dumps(calls[-1]), flush=True)
        assert result.returncode == expected, (name, result.stdout[-1400:], result.stderr[-2000:])
        if cli and result.returncode == 0:
            value = json.loads(result.stdout)
            assert value['ok'] and value['provenance']['cli_version'] == '0.1.63'
            return value['data']
        return result.stdout
    def cli(name, *argv):
        return run(name, [sys.executable, '-E', '-B', '-u', '-X', 'utf8', installed / 'run.py', *argv], cli=True)
    ffmpeg = shutil.which('ffmpeg')
    assert ffmpeg
    def raw(name, path, kind):
        options = ['-map', '0:v:0', '-an', '-pix_fmt', 'rgba', '-f', 'rawvideo'] if kind == 'rgba' else ['-map', '0:a:0', '-vn', '-c:a', 'pcm_s16le', '-f', 's16le']
        return run(name, [ffmpeg, '-nostdin', '-v', 'error', '-i', path, *options, 'pipe:1'], binary=True)
    base = home / 'base'
    cli('init', 'project', 'init', base)
    for asset, filename in [('study', 'source.png'), ('tone', 'source.wav')]:
        cli('ingest-' + asset, 'media', 'ingest', '--project', base, '--input', public / filename,
            '--asset-id', asset, '--license-spdx', 'CC0-1.0', '--verification-status', 'verified',
            '--creator', 'agent editor kit original geometric study', '--evidence', public / 'SOURCE.txt')
    base_json = load(base / 'project.json')
    settings = base_json['settings']
    settings['canvas'].update(width=480, height=270, background='#0a101d')
    settings['timebase'] = dict(ticks_per_second=90000, display_fps=dict(num=12, den=1))
    settings['color'] = dict(primaries='bt709', transfer='iec61966-2-1', matrix='bt709', range='limited')
    settings['pixel_pipeline'] = dict(engine='float32-native-v1', working_signal=dict(primaries='bt709', transfer='linear'),
                                      output_signal=dict(primaries='bt709', transfer='srgb'), range_policy='clip',
                                      sources=dict(study=dict(source_signal=dict(primaries='bt709', transfer='srgb'),
                                                              demux_origin='0', display_geometry='square-unrotated')))
    seq = base_json['sequences'][0]
    seq['duration_tick'] = 360000
    for track in seq['tracks']:
        if track['kind'] not in ('video', 'audio'):
            continue
        track['clips'] = [dict(id='hero' if track['kind'] == 'video' else 'sound',
                               asset_id='study' if track['kind'] == 'video' else 'tone',
                               timeline_start_tick=0, duration_tick=360000,
                               source_in_tick=0, source_out_tick=360000)]
    save(base / 'project.json', base_json)
    cli('base-validate', 'validate', '--project', base)
    baseline = base / 'renders/baseline.mkv'
    render_options = ['--container', 'mkv', '--video-codec', 'libx264', '--crf', '0',
                      '--pixel-format', 'yuv444p', '--audio-codec', 'pcm_s16le',
                      '--hardware-encode', 'off', '--projection-acceleration', 'require', '--projection-device', '0.0']
    cli('baseline-render', 'render', '--project', base, '--output', baseline, *render_options)
    base_rgba = raw('baseline-rgba', baseline, 'rgba')
    base_pcm = raw('baseline-pcm', baseline, 'pcm')
    assert len(base_rgba) == 480 * 270 * 4 * 48 and len(base_pcm) == 192000 * 4
    results, thumbs = [], [Image.open(public / 'source.png').convert('RGB').resize((240, 135))]
    for item in catalog['items']:
        code_id = item['id']
        project = home / code_id
        shutil.copytree(base, project, ignore=shutil.ignore_patterns('renders', 'previews', '.locks'))
        values = dict(clip_id='hero', middle_tick=180000, end_tick=360000)
        variables = home / (code_id + '-variables.json')
        save(variables, values)
        template = PACK / item['template']
        before = (project / 'project.json').read_bytes()
        cli(code_id + '-dry-run', 'template', 'apply', '--project', project, '--input', template,
            '--variables', variables, '--dry-run')
        assert before == (project / 'project.json').read_bytes()
        applied = cli(code_id + '-apply', 'template', 'apply', '--project', project, '--input', template,
                      '--variables', variables)
        assert applied['template_snapshot']['id'] == item['template_id']
        authored = load(project / 'project.json')
        target = next(c for t in authored['sequences'][0]['tracks'] for c in t['clips'] if c['id'] == 'hero')
        assert len(target['effects']) == 2 and any(e['keyframes'] for e in target['effects'])
        cli(code_id + '-validate', 'validate', '--project', project)
        movie = project / 'renders/effect.mkv'
        render = cli(code_id + '-render', 'render', '--project', project, '--output', movie, *render_options)
        actual = raw(code_id + '-rgba', movie, 'rgba')
        pcm = raw(code_id + '-pcm', movie, 'pcm')
        assert len(actual) == len(base_rgba) and pcm == base_pcm
        frame_size = 480 * 270 * 4
        assert actual != base_rgba and actual[:frame_size] != actual[24 * frame_size:25 * frame_size]
        package = public / (code_id + '.aevpkg.zip')
        cli(code_id + '-export', 'convert', 'export', '--project', project, '--output', package, '--target-format', 'package')
        replay = home / (code_id + '-replay')
        cli(code_id + '-import', 'convert', 'import', '--input', package, '--output', replay)
        again = replay / 'renders/replay.mkv'
        cli(code_id + '-replay-render', 'render', '--project', replay, '--output', again, *render_options)
        assert raw(code_id + '-replay-rgba', again, 'rgba') == actual
        assert raw(code_id + '-replay-pcm', again, 'pcm') == pcm
        preview = public / (code_id + '.mp4')
        run(code_id + '-mp4', [ffmpeg, '-nostdin', '-v', 'error', '-i', movie, '-c:v', 'libx264', '-crf', '18',
                              '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '128k', '-movflags', '+faststart', preview])
        gif = public / (code_id + '.gif')
        run(code_id + '-gif', [ffmpeg, '-nostdin', '-v', 'error', '-i', preview, '-an', '-vf',
                              'fps=8,scale=360:-1:flags=lanczos,split[a][b];[a]palettegen[p];[b][p]paletteuse', gif])
        frame = Image.frombytes('RGBA', (480, 270), actual[24 * frame_size:25 * frame_size]).convert('RGB')
        frame.save(public / (code_id + '.png'))
        thumbs.append(frame.resize((240, 135)))
        result = dict(id=code_id, template_sha256=sha(template), frames=48, duration_seconds=4, fps=12,
                      full_RGBA_bytes=len(actual), full_RGBA_sha256=hashlib.sha256(actual).hexdigest(),
                      full_PCM_bytes=len(pcm), full_PCM_sha256=hashlib.sha256(pcm).hexdigest(),
                      changed_from_original=True, animation_observed=True, full_project_package_RGBA_PCM_equal=True,
                      dry_run_author_bytes_unchanged=True, clip_and_keys_editable=True,
                      actual_render_delivery=render.get('delivery'),
                      public_files={p.name: dict(bytes=p.stat().st_size, sha256=sha(p)) for p in
                                    (preview, gif, package, public / (code_id + '.png'))})
        results.append(result)
        save(out / 'results.json', results)
    assert len({r['full_RGBA_sha256'] for r in results}) == 8
    contact = Image.new('RGB', (720, 465), '#0a101d')
    draw = ImageDraw.Draw(contact)
    for i, frame in enumerate(thumbs):
        x, y = i % 3 * 240, i // 3 * 155
        contact.paste(frame, (x, y))
        draw.text((x + 8, y + 138), 'ORIGINAL' if i == 0 else catalog['items'][i - 1]['id'] + ' ' + catalog['items'][i - 1]['name_en'], fill='white')
    contact.save(public / 'contact.png')
    assert all(sha(Path(p)) == h for p, h in guard.items())
    assert source_pins == {p.name: sha(p) for p in code.glob('*.py')}
    assert source_pins == {p.name: sha(p) for p in (installed / 'site/ai_ad_editor').glob('*.py')}
    report = dict(status='passed', checked_at_utc=datetime.now(timezone.utc).isoformat(), cli_version='0.1.63',
                  installed=str(installed), source_fallback=False, actual_template_apply=8, actual_templates=len(results),
                  original_study_only=True, actual_package_replays=8, full_RGBA_PCM_equal=True,
                  natural_footage_quality_accepted=False, human_listening_accepted=False,
                  new_core_features=0, new_neural_forwards=0, full_goal_closed=False,
                  source_and_installed_frozen=True, formal_files_unchanged=95,
                  public=str(public.relative_to(ROOT)), catalog_sha256=sha(PACK / 'catalog.json'), cases=results,
                  media_sources={p.name: sha(p) for p in (public / 'source.png', public / 'source.wav', public / 'SOURCE.txt')})
    save(out / 'verification.json', report)
    print(json.dumps({k: v for k, v in report.items() if k != 'cases'}, ensure_ascii=False), flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
