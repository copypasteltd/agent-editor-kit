"""Render every optical template on the user's existing N002 preview source."""
import copy
import hashlib
import html
import json
from pathlib import Path
import shutil
import subprocess
import sys

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'docs/validation/evidence/job-enumeration-20261029-r1'
PACK = ROOT / 'docs/content/effect-packs/optical-v1'


def load(p):
    return json.loads(p.read_bytes())


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def save(p, value):
    p.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')


def main():
    installed = Path(load(BASE / 'installation-candidate-r1/verification.json')['installed'])
    source = ROOT / 'docs/assets/looks-n002-20261024-r1/source.png'
    original = Path('E:/dev/sandbox/视频拆解/新片俄式艺术重制_v4_2026-10-23/output/imagegen/raw/N002.png')
    expected = 'babaa64ce3434a23133c41a1d2b4fad384a5e6707546b527508d4731ba83ab4b'
    assert sha(source) == sha(original) == expected
    catalog = load(PACK / 'catalog.json')
    assert len(catalog['items']) == 8
    namespace = ROOT / 'agent-ffmpeg-local-install-manifest.json'
    runtime = ROOT / 'local/agent-ffmpeg/runtime.json'
    formal = load(namespace)
    protected = {namespace: sha(namespace), runtime: sha(runtime)}
    protected.update({ROOT / r['path']: r['sha256'] for r in formal['files']})
    code = ROOT / 'product/src/ai_ad_editor'
    source_pins = {p.name: sha(p) for p in code.glob('*.py')}
    assert len(source_pins) == 283 and source_pins == {p.name: sha(p) for p in (installed / 'site/ai_ad_editor').glob('*.py')}
    home = ROOT / 'local/agent-ffmpeg/optical-n002-r1'
    out = ROOT / 'docs/validation/evidence/optical-n002-20261029-r1'
    public = ROOT / 'docs/assets/optical-n002-20261029-r1'
    for p in (home, out, public):
        p.mkdir()
    (out / 'executed-runner.py').write_bytes(Path(__file__).read_bytes())
    image = Image.open(source).convert('RGB')
    assert image.size == (1672, 940)
    image.resize((480, 270), Image.Resampling.LANCZOS).save(public / 'source.png')
    rights = ('# N002 optical previews\n\nThe user supplied N002.png and requested filter examples in the README and Skill guides. '
              'This records demonstration use; no broader ownership or license grant is inferred. '
              'LicenseRef-User-Supplied-Preview; neither the original nor derivatives are CC0 or covered wholesale by MIT. '
              'The MIT optical template parameters have separate rights.\n\n'
              f'Original SHA256: {expected}; 1672x940 RGB with no embedded profile. '
              'For these previews the image is Lanczos-resized to480x270, explicitly interpreted as sRGB, '
              'processed in linear BT.709 and returned to sRGB. All templates use the same480x270 source, '
              'original author clock of90000ticks/s and frame24 of12fps (2seconds); no automatic scene/light detection. '
              'These are actual still previews, not new video footage or natural-quality approval.\n')
    (public / 'SOURCE.md').write_text(rights, encoding='utf-8', newline='\n')
    calls = []
    def cli(name, *args):
        argv = [sys.executable, '-I', '-S', '-B', '-u', '-X', 'utf8', str(installed / 'run.py'), *map(str, args)]
        result = subprocess.run(argv, cwd=ROOT, capture_output=True, timeout=300,
                                creationflags=subprocess.CREATE_NO_WINDOW)
        (out / (name + '.stdout')).write_bytes(result.stdout)
        (out / (name + '.stderr')).write_bytes(result.stderr)
        calls.append(dict(name=name, exit_code=result.returncode, stdout_sha256=hashlib.sha256(result.stdout).hexdigest()))
        save(out / 'calls.json', calls)
        print(json.dumps(calls[-1]), flush=True)
        assert result.returncode == 0, (name, result.stdout[-1500:], result.stderr[-2000:])
        value = json.loads(result.stdout)
        assert value['ok'] and value['provenance']['cli_version'] == '0.1.63'
        return value['data']
    base = home / 'base'
    cli('init', 'project', 'init', base)
    cli('ingest', 'media', 'ingest', '--project', base, '--input', public / 'source.png', '--asset-id', 'n002',
        '--license-spdx', 'LicenseRef-User-Supplied-Preview', '--verification-status', 'unverified',
        '--creator', 'User-supplied N002 demonstration source', '--evidence', public / 'SOURCE.md')
    project = load(base / 'project.json')
    settings = project['settings']
    settings['canvas'].update(width=480, height=270, background='#000000')
    settings['timebase'] = dict(ticks_per_second=90000, display_fps=dict(num=12, den=1))
    settings['color'] = dict(primaries='bt709', transfer='iec61966-2-1', matrix='bt709', range='limited')
    settings['pixel_pipeline'] = dict(engine='float32-native-v1',
        working_signal=dict(primaries='bt709', transfer='linear'),
        output_signal=dict(primaries='bt709', transfer='srgb'), range_policy='clip',
        sources=dict(n002=dict(source_signal=dict(primaries='bt709', transfer='srgb'),
                               demux_origin='0', display_geometry='square-unrotated')))
    seq = project['sequences'][0]
    seq['duration_tick'] = 360000
    for track in seq['tracks']:
        track['clips'] = [dict(id='hero', asset_id='n002', timeline_start_tick=0, duration_tick=360000,
                               source_in_tick=0, source_out_tick=360000)] if track['kind'] == 'video' else []
    save(base / 'project.json', project)
    cli('base-validate', 'validate', '--project', base)
    baseline = cli('baseline', 'preview', 'frame', '--project', base, '--frame', 24, '--height', 270)
    # Preview returns actual paths; inspect the existing contract rather than guess filenames.
    save(out / 'baseline-result.json', baseline)
    candidate_paths = [Path(v) for v in baseline.values() if isinstance(v, str) and v.lower().endswith('.png')]
    assert len(candidate_paths) == 1, baseline
    baseline_path = candidate_paths[0]
    if not baseline_path.is_absolute():
        baseline_path = base / baseline_path
    assert baseline_path.is_file()
    shutil.copyfile(baseline_path, public / 'baseline.png')
    original_pixels = Image.open(baseline_path).convert('RGB').tobytes()
    results = []
    variables = home / 'variables.json'
    save(variables, dict(clip_id='hero', middle_tick=180000, end_tick=360000))
    for item in catalog['items']:
        ident = item['id']
        template = PACK / item['template']
        assert sha(template) == item['sha256']
        target = home / ident
        shutil.copytree(base, target, ignore=shutil.ignore_patterns('previews', 'cache', '.locks'))
        before = (target / 'project.json').read_bytes()
        cli(ident + '-dry-run', 'template', 'apply', '--project', target, '--input', template, '--variables', variables, '--dry-run')
        assert (target / 'project.json').read_bytes() == before
        cli(ident + '-apply', 'template', 'apply', '--project', target, '--input', template, '--variables', variables)
        cli(ident + '-validate', 'validate', '--project', target)
        result = cli(ident + '-preview', 'preview', 'frame', '--project', target, '--frame', 24, '--height', 270)
        candidate_paths = [Path(v) for v in result.values() if isinstance(v, str) and v.lower().endswith('.png')]
        assert len(candidate_paths) == 1, result
        actual = candidate_paths[0]
        if not actual.is_absolute():
            actual = target / actual
        decoded = Image.open(actual).convert('RGB')
        assert decoded.size == (480, 270) and decoded.tobytes() != original_pixels
        output = public / (ident + '.png')
        shutil.copyfile(actual, output)
        results.append(dict(id=ident, template_id=item['template_id'], template_sha256=sha(template),
                            output=output.relative_to(ROOT).as_posix(), PNG_sha256=sha(output),
                            RGB_sha256=hashlib.sha256(decoded.tobytes()).hexdigest(), frame=24, seconds=2,
                            size=[480, 270], dry_run_preserved_project=True, different_from_baseline=True))
    assert len({r['RGB_sha256'] for r in results}) == 8
    contact = Image.new('RGB', (1440, 882), '#0c1420')
    draw = ImageDraw.Draw(contact)
    labels = [('ORIGINAL N002 (same pipeline)', public / 'baseline.png')]
    labels += [(r['id'] + ' ' + item['name_en'], public / (r['id'] + '.png')) for r, item in zip(results, catalog['items'])]
    for i, (label, p) in enumerate(labels):
        x, y = (i % 3) * 480, (i // 3) * 294
        contact.paste(Image.open(p).convert('RGB'), (x, y))
        draw.text((x + 10, y + 274), label, fill='#ffffff')
    contact.save(public / 'contact.png')
    assert all(sha(p) == h for p, h in protected.items())
    assert source_pins == {p.name: sha(p) for p in code.glob('*.py')}
    report = dict(status='passed', cli_version='0.1.63', installed=str(installed), source_fallback=False,
                  original_N002_sha256=expected, resized_source_sha256=sha(public / 'source.png'),
                  templates=results, all8_distinct=True, all8_different_from_baseline=True,
                  complete_frame_RGB_bytes=480 * 270 * 3, explicit_sRGB_interpretation=True,
                  source_and_formal_files_unchanged=True, formal_cli_at_execution=formal['cli_version'],
                  image_rights='LicenseRef-User-Supplied-Preview', image_rights_verification='unverified',
                  new_video_footage=False, human_quality_accepted=False, model_forwards=0,
                  full_goal_closed=False)
    save(out / 'verification.json', report)
    print(json.dumps(dict(status='passed', templates=8, native_still_previews=True)), flush=True)


if __name__ == '__main__':
    main()
