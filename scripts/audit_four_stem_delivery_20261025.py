"""Audit documented four-stem delivery without new model inference or rendering."""
from pathlib import Path
import hashlib
import json
import re
import subprocess
import urllib.parse
import zipfile
from audit_four_stem_installation_20261025 import ROOT, sha, save


def main():
    evidence = ROOT / 'docs/validation/evidence/four-stems-20261025-r1'
    output = evidence / 'delivery-audit-r2'
    output.mkdir(exist_ok=False)
    (output / 'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    git = 'C:/Users/carzy/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/git/cmd/git.exe'
    git_args = [git, '--no-optional-locks', '-c', 'core.fsmonitor=false', '-c', 'gc.auto=0', '-c', 'maintenance.auto=false']
    baseline = subprocess.check_output([*git_args, 'rev-parse', 'HEAD'], cwd=ROOT).decode().strip()
    readmes = []
    for name in ('README.md', 'README.zh-TW.md', 'README.en.md'):
        previous = subprocess.check_output([*git_args, 'show', 'HEAD:' + name], cwd=ROOT).decode('utf8')
        current = (ROOT / name).read_text('utf8')
        historic = lambda text: [line for line in text.splitlines()
            if re.match(r'^\| R(?:0[1-9]|[1-3][0-9]|4[0-8]) ', line)]
        assert historic(previous) == historic(current) and len(historic(current)) == 48
        ids = lambda prefix: re.findall(r'^\| (' + prefix + r'\d\d) ', current, re.M)
        assert ids('R') == ['R%02d' % n for n in range(1, 54)]
        assert sorted(ids('F')) == ['F%02d' % n for n in range(1, 51)]
        assert ids('S') == ['S%02d' % n for n in range(1, 20)]
        assert ids('K') == ['K%02d' % n for n in range(1, 18)]
        assert 'audio separate-stems' in current and 'r5 Skill kit' in current
        assert '1.71dB' in current and '0.419' in current
        readmes.append(dict(path=name, sha256=sha(ROOT / name), historical_rows_unchanged=48,
            verification_rows=53, feature_rows=50, service_rows=19, module_rows=17))
    gaps = (ROOT / 'docs/product/GOAL_GAPS_20261025.md').read_text('utf8')
    assert re.findall(r'^\| (G\d\d) ', gaps, re.M) == ['G%02d' % n for n in range(1, 39)]
    previous = subprocess.check_output([*git_args, 'show', 'HEAD:docs/product/GOAL_GAPS_20261025.md'], cwd=ROOT).decode('utf8')
    conditions = lambda text: {line.split('|')[1].strip(): line.split('|')[-3].strip()
        for line in text.splitlines() if re.match(r'^\| G\d\d ', line)}
    assert conditions(previous) == conditions(gaps)
    docs = [ROOT / r['path'] for r in readmes] + [ROOT / name for name in (
        'docs/README.md', 'docs/product/GOAL_GAPS_20261025.md', 'docs/product/COMMUNITY_LOCAL_DELIVERY.md',
        'docs/product/FOUR_STEM_SEPARATION.md', 'docs/product/CASES.md',
        'docs/validation/独立四轨音源分离实测_2026-10-25.md')]
    docs += [ROOT / ('docs/product/' + family + suffix + '.md')
        for family in ('CAPABILITIES', 'SKILLS') for suffix in ('', '.en', '.zh-TW')]
    local_links = 0
    for path in docs:
        for link in re.findall(r'!?\[[^\]\n]*\]\(([^\)\n]+)\)', path.read_text('utf8')):
            if re.match(r'^[a-z]+:', link) or link.startswith('#'):
                continue
            target = (path.parent / urllib.parse.unquote(link.split('#', 1)[0])).resolve()
            assert target.exists(), (path, link)
            local_links += 1
    pin = json.loads((ROOT / 'agent-ffmpeg-local-install-manifest.json').read_bytes())
    assert pin['cli_version'] == '0.1.6' and pin['skill_count'] == 1 and pin['module_count'] == 17
    for row in pin['files']:
        path = ROOT / row['path']
        assert sha(path) == 'sha256:' + row['sha256'] and path.stat().st_size == row['bytes']
    kit = ROOT / 'docs/skills/agent-editor-kit-community-unified-skill-r5.zip'
    with zipfile.ZipFile(kit) as archive:
        for row in pin['files']:
            assert archive.read(row['path']) == (ROOT / row['path']).read_bytes()
    required = ('installation', 'kit-r1', 'controls-r3', 'demo-r2')
    for name in required:
        assert json.loads((evidence / name / 'verification.json').read_bytes())['status'] == 'passed'
    demo = json.loads((evidence / 'demo-r2/verification.json').read_bytes())
    public = ROOT / 'docs/assets/four-stems-20261025-r1/demo-r2'
    assert set(p.name for p in public.iterdir()) == set(demo['public_files'])
    for name, row in demo['public_files'].items():
        assert sha(public / name) == row['sha256'] and (public / name).stat().st_size == row['bytes']
    assert demo['frames'] == 180 and demo['samples'] == 288000 and demo['float_mix_max_abs_error'] == 0
    assert demo['roundtrip_pcm_exact'] and not demo['human_listening']
    assert demo['gif']['frames'] == 60 and demo['gif']['duration_milliseconds'] == 6000
    for path in evidence.rglob('*'):
        assert path.suffix.lower() not in ('.wav', '.mp3', '.pt', '.pth', '.mkv', '.zip'), path
    result = dict(status='passed', baseline_commit=baseline, readmes=readmes,
        full_goal_gap_groups=38, original_close_conditions_unchanged=True,
        checked_documents=len(docs), existing_local_link_targets=local_links,
        pinned_skill_files=len(pin['files']), kit_bytes_match_live_skill=True,
        public_media_hashes_match=True, public_source_model_audio_redistributed=False,
        model_forwards=0, new_renders=0, historical_tests_rerun=False,
        all_goal_groups_still_open=True, generator_sha256=sha(Path(__file__)))
    save(output / 'verification.json', result)
    print(json.dumps(result, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
