"""Audit current delivery pins, preserved gap closures and historical README rows."""
from pathlib import Path
import argparse
import hashlib
import json
import re
import subprocess
from urllib.parse import unquote
import zipfile

from audit_job_recovery_installation_20261025 import ROOT, EVIDENCE, sha, write

GIT = 'C:/Users/carzy/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/git/cmd/git.exe'


def previous(name):
    result = subprocess.run([GIT, '--no-optional-locks', '-c', 'core.fsmonitor=false', '-c', 'gc.auto=0',
        '-c', 'maintenance.auto=false', 'show', 'HEAD:' + name], cwd=ROOT, capture_output=True, timeout=60)
    return result.stdout.decode('utf8') if result.returncode == 0 else ''


def ids(text, prefix):
    return sorted(re.findall(r'^\| (' + prefix + r'\d\d)(?: / [^|]+)? \|', text, flags=re.M))


def closures(text):
    return {row.split('|')[1].strip(): row.split('|')[5].strip()
            for row in text.splitlines() if re.match(r'^\| G\d\d \|', row)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    out = args.output.resolve()
    assert out.is_relative_to(EVIDENCE)
    out.mkdir(exist_ok=False)
    (out / 'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    names = ['README.md', 'README.en.md', 'README.zh-TW.md', 'docs/README.md',
        'docs/product/JOB_RECOVERY.md', 'docs/product/GOAL_GAPS_20261025.md',
        'docs/product/IMPLEMENTATION_PLAN_20261025.md', 'docs/product/FOUR_STEM_SEPARATION.md',
        'docs/product/COMMUNITY_LOCAL_DELIVERY.md', 'docs/product/CASES.md',
        'docs/validation/任务中断恢复实测_2026-10-25.md']
    names += ['docs/product/' + prefix + '.' + suffix for prefix in ('CAPABILITIES', 'SKILLS')
              for suffix in ('md', 'en.md', 'zh-TW.md')]
    readmes = {}
    for name in names[:3]:
        text = (ROOT / name).read_text('utf8')
        before = previous(name)
        history = lambda value: [line for line in value.splitlines()
            if re.match(r'^\| R(?:0[1-9]|[1-4][0-9]|5[0-3]) \|', line)]
        assert len(history(before)) == 53 and history(before) == history(text), name
        for prefix, count in (('F', 50), ('S', 19), ('K', 17), ('R', 58)):
            assert ids(text, prefix) == [prefix + str(i).zfill(2) for i in range(1, count + 1)], (name, prefix)
        assert 'CLI 0.1.7' in text and 'unified-skill-r6.zip' in text
        readmes[name] = dict(F=50, S=19, K=17, R=58, historical_R01_R53_verbatim=True, sha256=sha(ROOT / name))
    gap = (ROOT / 'docs/product/GOAL_GAPS_20261025.md').read_text('utf8')
    prior = previous('docs/product/GOAL_GAPS_20261025.md')
    assert len(closures(gap)) == 38 and closures(prior) == closures(gap)
    links, baseline_missing, missing = 0, [], []
    for name in names:
        text, old = (ROOT / name).read_text('utf8'), previous(name)
        for target in re.findall(r'!?\[[^\]]*\]\(([^\n)]+)\)', text):
            target = target.strip('<>')
            if re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*:', target) or target.startswith('#'):
                continue
            plain = unquote(target.partition('#')[0])
            links += 1
            if not (ROOT / name).parent.joinpath(plain).exists():
                (baseline_missing if '(' + target + ')' in old else missing).append(dict(file=name, target=target))
    assert not missing, missing
    manifest = json.loads((ROOT / 'agent-ffmpeg-local-install-manifest.json').read_bytes())
    runtime = json.loads((ROOT / 'local/agent-ffmpeg/runtime.json').read_bytes())
    assert manifest['cli_version'] == '0.1.7' and manifest['release'] == runtime['release'] == 'v0.1.0-alpha.4-local.5'
    assert manifest['manifest_sha256'] == runtime['manifest_sha256'] and len(manifest['files']) == 62
    assert manifest['skill_count'] == 1 and manifest['module_count'] == 17
    for row in manifest['files']:
        path = ROOT / row['path']
        assert path.stat().st_size == row['bytes'] and sha(path) == 'sha256:' + row['sha256'], row['path']
    installed = Path(runtime['installed_directory'])
    assert sha(installed / 'run.py').removeprefix('sha256:') == runtime['launcher_sha256'].removeprefix('sha256:')
    source_records = json.loads((EVIDENCE / 'installation/source-python-files.json').read_bytes())
    for row in source_records:
        assert sha(ROOT / 'product/src' / row['path']) == row['sha256'] == sha(installed / 'site' / row['path'])
    kits = {}
    for version in ('0.1.6', '0.1.7'):
        package = json.loads((ROOT / ('docs/skills/community-unified-skill-package-' + version + '.json')).read_bytes())
        path = ROOT / package['archive']
        assert sha(path) == 'sha256:' + package['sha256'] and path.stat().st_size == package['bytes']
        kits[version] = dict(files=package['files'], bytes=package['bytes'], sha256=sha(path))
    kit = ROOT / 'docs/skills/agent-editor-kit-community-unified-skill-r6.zip'
    with zipfile.ZipFile(kit) as archive:
        inventory = json.loads(archive.read('KIT-FILES.json'))
        for row in inventory['files']:
            data = archive.read(row['path'])
            assert hashlib.sha256(data).hexdigest() == row['sha256'] and len(data) == row['bytes']
            if row['path'].startswith('skills/'):
                assert (ROOT / row['path']).read_bytes() == data
    for folder in ('faults-r1', 'demo-r1', 'installation', 'kit-r1'):
        assert json.loads((EVIDENCE / folder / 'verification.json').read_bytes())['status'] == 'passed'
    for folder in ('development-r1', 'installed-r1', 'skill-r1'):
        record = json.loads((EVIDENCE / folder / 'verification.json').read_bytes())
        assert record['quality_all_controlled_passed'] and not record['full_G17_closed']
        assert (EVIDENCE / folder / 'executed-generator.py').read_bytes() == (ROOT / 'scripts/verify_four_stems_20261025.py').read_bytes()
    old_cache = ROOT / 'local/agent-ffmpeg/four-stems-20261025-r1/installed-r1/中文 四轨工程/cache/four-stem-separation/hdemucs-fql2zn03'
    assert old_cache.is_dir()
    for project in ('installed-r1', 'skill-r1'):
        base = ROOT / 'local/agent-ffmpeg/job-recovery-20261025-r1' / project / '中文 四轨工程/cache/managed-jobs'
        assert not list(base.iterdir()), str(base)
    result = dict(status='passed', readmes=readmes, goal_groups=38, all_closure_conditions_preserved=True,
        local_markdown_targets_checked=links, new_missing_local_targets=missing,
        inherited_missing_local_targets=baseline_missing, source_python_files=len(source_records),
        source_installed_bytes_equal=True, registered_skill_files=62, registered_skills=1, internal_modules=17,
        kits=kits, legacy_forced_stop_evidence_preserved=True, completed_new_workspaces_empty=True,
        full_goal_complete=False, new_model_forwards=0, new_renders=0, browser_ui=False,
        generator_sha256=sha(Path(__file__)))
    write(out / 'verification.json', result)
    print(json.dumps(result, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
