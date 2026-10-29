"""Check actual CLI55 delivery gates; optionally pin the verified unified Skill.

Pinning does not activate runtime.json or register discovery. Run native runtime
activation and the registered-entry case separately after a successful pin.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT/'docs/validation/evidence/process-budget-20261029-r1'


def load(path):
    return json.loads(path.read_bytes())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-run', default='r3')
    parser.add_argument('--installed-run', default='r1')
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--run', help='Unique receipt identity, required for --apply')
    args = parser.parse_args()
    for value in (args.source_run, args.installed_run, args.run):
        if value is not None and not value.replace('-', '').isalnum():
            parser.error('Receipt identities must be alphanumeric with optional hyphens')
    if args.apply and not args.run:
        parser.error('--apply requires a unique --run receipt identity')
    gates = {
        'installation': BASE/'installation-candidate-r1/verification.json',
        'candidate': BASE/'skill-candidate-r1/verification.json',
        'source_case': BASE/('case-'+args.source_run)/'verification.json',
        'installed_case': BASE/('installed-case-'+args.installed_run)/'verification.json',
    }
    for group in ('deadline', 'selection', 'semantic'):
        gates['source_'+group] = BASE/(group+'-r1')/'verification.json'
        gates['installed_'+group] = BASE/('installed-'+group+'-r1')/'verification.json'
    missing = [name for name, path in gates.items() if not path.is_file()]
    if missing:
        print(json.dumps(dict(status='pending', ready=False, missing=missing,
                              mutated=False, activated=False), ensure_ascii=False))
        return 2
    reports = {name: load(path) for name, path in gates.items()}
    rejected = [name for name, report in reports.items()
                if report.get('status') != ('installed-and-byte-verified' if name == 'installation' else 'passed')]
    if rejected:
        print(json.dumps(dict(status='rejected', ready=False, failed_gates=rejected,
                              mutated=False, activated=False), ensure_ascii=False))
        return 2
    installation = reports['installation']
    assert installation['status'] == 'installed-and-byte-verified'
    assert installation['cli_version'] == '0.1.55'
    source = ROOT/'product/src/ai_ad_editor'
    installed = Path(installation['installed'])/'site/ai_ad_editor'
    pins = {p.name: sha(p) for p in source.glob('*.py')}
    assert len(pins) == 281
    assert pins == {p.name: sha(p) for p in installed.glob('*.py')}
    for group, count in [('deadline', 15), ('selection', 45), ('semantic', 104)]:
        for prefix in ('source_', 'installed_'):
            report = reports[prefix+group]
            assert report['status'] == 'passed' and report['tests'] == count
            assert report['frozen_equal']
            assert all(report[key] == 0 for key in ('failures', 'errors', 'skipped'))
            assert report['source_files'] == pins
            assert all(sha(ROOT/'product/tests'/name) == digest
                       for name, digest in report['test_files'].items())
            if prefix == 'installed_':
                assert report['source_fallback'] is False and report['isolated'] and report['no_site']
                assert Path(report['installed']).resolve() == installed.parent.parent.resolve()
    for name in ('source_case', 'installed_case'):
        report = reports[name]
        assert report['status'] == 'passed'
        assert report.get('source_cli', report.get('cli_version')) == '0.1.55'
        for flag in ('actual_GPU_semantic_search', 'full_project_replay_equal',
                     'project_unchanged_by_selection', 'frozen_equal', 'non_silent_finite_PCM'):
            assert report[flag] is True, (name, flag)
        assert report['renders'] == 4
        assert set(report['variants']) == {'wide', 'vertical'}
        for variant in report['variants'].values():
            assert variant['replay_equal'] and variant['finite_non_silent_PCM']
        if name == 'installed_case':
            assert report['source_fallback'] is False
            assert Path(report['installed']).resolve() == installed.parent.parent.resolve()
    namespace = ROOT/'agent-ffmpeg-local-install-manifest.json'
    manifest = load(namespace)
    candidate = reports['candidate']
    assert candidate['status'] == 'passed' and candidate['actual_PowerShell_entry']
    assert candidate['cli_version'] == '0.1.55' and candidate['files'] == 93
    assert sha(namespace) == candidate['namespace_sha256']
    assert sha(ROOT/'local/agent-ffmpeg/runtime.json') == candidate['live_runtime_sha256']
    assert manifest['cli_version'] == '0.1.53' and len(manifest['files']) == 92
    folder = ROOT/'skills/agent-ffmpeg-local-editor'
    stage = ROOT/'local/agent-ffmpeg/ad-selection-skill-stage-r2/skills/agent-ffmpeg-local-editor'
    staged = {p.relative_to(stage).as_posix(): sha(p) for p in stage.rglob('*') if p.is_file()}
    assert staged == candidate['candidate_files'] and len(staged) == 93
    for row in manifest['files']:
        assert sha(ROOT/row['path']) == row['sha256']
    assert sum(Path(name).name == 'SKILL.md' for name in staged) == 1
    assert len(list((stage/'references/modules').glob('*/module.md'))) == 17
    if not args.apply:
        print(json.dumps(dict(status='ready', ready=True, mutated=False, activated=False,
                              public_entries=1, modules=17, files=93)))
        return 0
    out = BASE/('skill-pin-'+args.run)
    out.mkdir(exist_ok=False)
    (out/'executed-runner.py').write_bytes(Path(__file__).read_bytes())
    old_namespace = namespace.read_bytes()
    (out/'previous-namespace.json').write_bytes(old_namespace)
    old = {name: (folder/name).read_bytes() if (folder/name).exists() else None for name in staged}
    for name, content in old.items():
        if content is not None:
            backup = out/'previous-skill'/name
            backup.parent.mkdir(parents=True, exist_ok=True)
            backup.write_bytes(content)
    temporary = namespace.with_name(namespace.name+'.cli55-pin.tmp')
    assert not temporary.exists()
    try:
        for name in staged:
            target = folder/name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes((stage/name).read_bytes())
        manifest.update(release='v0.1.0-alpha.4-local.53', cli_version='0.1.55',
                        manifest_sha256=installation['manifest_sha256'])
        manifest['skills'][0]['skill_md_sha256'] = sha(folder/'SKILL.md')
        manifest['files'] = [dict(path=p.relative_to(ROOT).as_posix(), bytes=p.stat().st_size,
                                  sha256=sha(p)) for p in sorted(folder.rglob('*')) if p.is_file()]
        assert len(manifest['files']) == 93
        temporary.write_text(json.dumps(manifest, ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')
        os.replace(temporary, namespace)
    except BaseException:
        for name, content in old.items():
            target = folder/name
            if content is None:
                target.unlink(missing_ok=True)
            else:
                target.write_bytes(content)
        namespace.write_bytes(old_namespace)
        temporary.unlink(missing_ok=True)
        raise
    report = dict(status='pinned-not-activated', cli_version='0.1.55', public_entries=1,
                  modules=17, skill_files=93, activated=False, source_fallback=False,
                  namespace_manifest_sha256=sha(namespace),
                  gates={name: dict(path=path.relative_to(ROOT).as_posix(), sha256=sha(path))
                         for name, path in gates.items()})
    (out/'verification.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')
    print(json.dumps(report, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
