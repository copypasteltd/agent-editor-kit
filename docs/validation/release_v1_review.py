"""Activate the verified pair, audit source/docs and materialize a scoped commit."""
from pathlib import Path
import json
import os
import re
import shutil
import sys
from urllib.parse import unquote

sys.path.insert(0, str(Path(__file__).resolve().parent))
import release_v1 as r


def activate():
    proof = r.load(r.EVIDENCE / 'local-r1/verification.json')
    assert proof['status'] == 'passed'
    source = r.WORK / 'source'
    manifest = r.load(source / 'agent-ffmpeg-local-install-manifest.json')
    backup = r.WORK / 'formal-before'
    backup.mkdir()
    names = [row['path'] for row in r.load(r.WORK / 'before.json')['formal_skill_inventory']['files']]
    names += ['agent-ffmpeg-local-install-manifest.json', 'local/agent-ffmpeg/runtime.json']
    for name in names:
        path = backup / name
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(r.ROOT / name, path)
    try:
        for row in manifest['files']:
            assert r.sha(source / row['path']) == row['sha256']
            target = r.ROOT / row['path']
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source / row['path'], target)
        shutil.copyfile(source / 'agent-ffmpeg-local-install-manifest.json', r.ROOT / 'agent-ffmpeg-local-install-manifest.json')
        config = r.load(backup / 'local/agent-ffmpeg/runtime.json')
        installed = Path(proof['installed'])
        config.update(release=r.TAG, installed_directory=str(installed), manifest_sha256=manifest['manifest_sha256'],
                      launcher_sha256=r.sha(installed / 'run.py'))
        r.save(r.ROOT / 'local/agent-ffmpeg/runtime.json', config)
        out = r.EVIDENCE / 'formal-r1'
        entry = Path('C:/Users/carzy/.codex/skills/agent-ffmpeg-local-editor/scripts/run.ps1')
        assert entry.parent.parent.resolve() == (r.ROOT / r.SKILL).resolve()
        prefix = ['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', entry]
        version = r.call(out, 'actual-discovery-version', [*prefix, 'version'], json_result=True)
        assert version['provenance']['cli_version'] == r.VERSION
        r.call(out, 'actual-discovery-capabilities', [*prefix, 'capabilities'], json_result=True)
        r.call(out, 'actual-discovery-gpu', [*prefix, 'gpu', 'inspect'], json_result=True)
        r.save(out / 'verification.json', dict(status='passed', distribution_version=r.TAG, cli_version=r.VERSION,
            skill_revision=r.REVISION, skill_count=1, modules=17, files=len(manifest['files']),
            actual_global_discovery=True, registration_target_unchanged=True, source_fallback=False,
            existing_model_config_preserved=True, rollback_backup=str(backup),
            paused_candidates_resumed=False, candidate_validation_must_rebase_formal_guard=True))
    except BaseException:
        # Restore only this transaction's files. The added reference is harmless
        # but remove it if it did not exist in the backed-up inventory.
        for row in manifest['files']:
            if row['path'] not in names:
                (r.ROOT / row['path']).unlink(missing_ok=True)
        for name in names:
            shutil.copyfile(backup / name, r.ROOT / name)
        raise


def review(phase):
    before = r.load(r.WORK / 'before.json')
    assert all(r.sha(r.ROOT / name) == pin for name, pin in before.get('working_copy_python', {}).items())
    assert r.sha(r.ROOT / 'docs/product/GOAL_GAPS_20261025.md') == '36347a3c5599ec4e4850b13c6cd98f726847f4142f96863fadf6f26b4f27e755'
    history = r.load(r.ROOT / 'docs/history/readme-before-v1.0.0/numbered-rows.json')
    counts = {}
    missing = []
    post_publication = ('publication-r1/verification.json', 'public-download-r1/verification.json')
    for name in r.README_NAMES:
        actual = (r.ROOT / name).read_text(encoding='utf-8')
        archived = r.ROOT / 'docs/history/readme-before-v1.0.0' / (name + '.original.txt')
        assert r.sha(archived) == history[name]['sha256']
        assert len(history[name]['rows']) == 707
        assert re.findall(r'^\|\s*[FR]\d+\s*\|.*$', archived.read_text(encoding='utf-8'), flags=re.M) == history[name]['rows']
        counts[name] = dict(lines=len(actual.splitlines()), function_rows=len(re.findall(r'^\| F\d+\s*\|', actual, re.M)),
                           modules=len(re.findall(r'^\| K\d+\s*\|', actual, re.M)))
        assert counts[name]['function_rows'] >= 75 and counts[name]['modules'] == 17
        assert 'v1.0.0' in actual and 'r60' in actual and 'R618' in actual and 'R619' in actual and 'R620' in actual
        assert 'STABLE_MANIFEST_SHA256' not in actual
    checked = [r.ROOT / name for name in r.README_NAMES]
    checked += list((r.ROOT / 'docs/releases/v1.0.0').glob('*.md'))
    for path in checked:
        text = path.read_text(encoding='utf-8')
        for match in re.finditer(r'!?\[[^\]\n]*\]\(([^\s)]+)\)', text):
            target = match[1]
            if target.startswith(('#', 'http:', 'https:', 'mailto:')):
                continue
            plain = unquote(target.split('#', 1)[0])
            destination = path.parent / plain
            if not destination.exists():
                if phase == 'pre-publication' and any(plain.endswith(suffix) for suffix in post_publication):
                    continue
                missing.append(dict(document=path.relative_to(r.ROOT).as_posix(), target=target))
    r.save(r.WORK / ('link-review-' + phase + '.json'), dict(missing=missing, counts=counts))
    assert not missing, 'Broken public manual links; inspect link-review receipt'
    scope = list(r.README_NAMES) + ['agent-ffmpeg-local-install-manifest.json']
    manifest = r.load(r.ROOT / 'agent-ffmpeg-local-install-manifest.json')
    assert manifest['release'] == r.TAG and manifest['skill_count'] == 1 and manifest['module_count'] == 17
    scope += [row['path'] for row in manifest['files'] if not (r.ROOT / row['path']).exists()
              or r.sha(r.ROOT / row['path']) != {item['path']: item['sha256'] for item in before['formal_skill_inventory']['files']}.get(row['path'])]
    roots = ['docs/releases/v1.0.0', 'docs/history/readme-before-v1.0.0', 'docs/assets/release-v1-20261107']
    for folder in roots:
        scope += [p.relative_to(r.ROOT).as_posix() for p in (r.ROOT / folder).rglob('*') if p.is_file()]
    scope += [p.relative_to(r.ROOT).as_posix() for p in (r.ROOT / 'docs/validation').glob('release_v1*.py')]
    # Publish receipts, not large raw subprocess streams or machine-local configuration.
    scope += [p.relative_to(r.ROOT).as_posix() for p in r.EVIDENCE.glob('*/verification.json')]
    scope += ['docs/product/STABLE_V1_SCOPE.md']
    # Remove files whose Git clean object already matches HEAD (follow-up commit).
    ordered = sorted(set(scope))
    objects = r.git('hash-object', '--stdin-paths', data=('\n'.join(ordered) + '\n').encode('utf-8')).splitlines()
    existing = {}
    for start in range(0, len(ordered), 40):
        for record in r.git('ls-tree', '-r', '-z', 'HEAD', '--', *ordered[start:start + 40]).split(b'\0'):
            if record:
                header, name = record.split(b'\t', 1)
                existing[name.decode('utf-8')] = header.split()[2]
    changed = [name for name, clean in zip(ordered, objects) if existing.get(name) != clean]
    pins = {name: r.sha(r.ROOT / name) for name in changed}
    scanned = r.scan(r.ROOT / name for name in pins)
    r.scan(r.WORK / 'assets' / row['name'] for row in r.load(r.WORK / 'release-lock.json')['assets'])
    result = dict(status='passed', phase=phase, distribution_version=r.TAG, cli_version=r.VERSION,
        three_language_counts=counts, historical_rows_preserved_each=707,
        original_goal_unchanged=True, unaccepted_source_worktree_preserved=True,
        candidate_CLI67_committed=False, scope_files=len(pins), exact_secret_scan_files=scanned,
        current_manual_local_links_resolve=True, whole_goal_complete=False)
    r.save(r.EVIDENCE / ('review-' + phase) / 'verification.json', result)
    name = 'docs/validation/evidence/release-v1-20261107/review-' + phase + '/verification.json'
    pins[name] = r.sha(r.ROOT / name)
    r.save(r.WORK / ('scope-' + phase + '.json'), pins)
    (r.WORK / ('message-' + phase + '.txt')).write_text(
        ('release: publish first stable agent editor kit v1.0.0\n' if phase == 'pre-publication'
         else 'docs: record verified public stable downloads and native replay\n') +
        '\nRebuild the accepted CLI66 distribution, pair unified Skill r60, preserve '
        'experimental source and unrelated staging, organize complete trilingual manuals '
        'and retain all dated verification history.\n', encoding='utf-8')
    print(json.dumps(result, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    if sys.argv[1] == 'activate': activate()
    else: review(sys.argv[1])
