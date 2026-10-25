"""Capture a read-only installed assessment; audit additive documentation changes."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import time
from urllib.parse import unquote
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'docs/validation/evidence/goal-gaps-20261025-r13'
GIT = 'C:/Users/carzy/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/git/cmd/git.exe'
REPORT = 'docs/product/GOAL_GAPS_20261025.md'
READMES = ('README.md', 'README.zh-TW.md', 'README.en.md')


def git(*args):
    return subprocess.check_output([GIT, '--no-optional-locks', '-c', 'core.fsmonitor=false',
        '-c', 'gc.auto=0', '-c', 'maintenance.auto=false', *args], cwd=ROOT, timeout=60)


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def load(path):
    return json.loads(path.read_bytes())


def save(name, value):
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n',
        encoding='utf-8', newline='\n')


def numbered(text, prefix):
    return {m[1]: m[0] for m in re.finditer(r'^\| (' + prefix + r'\d{2})\s*\|.*$', text, re.M)}


def inventory():
    OUT.mkdir(parents=True, exist_ok=False)
    (OUT / 'logs').mkdir()
    (OUT / 'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    baseline = git('rev-parse', 'HEAD').decode().strip()
    report = dict(status='running', baseline_commit=baseline,
        started_at_utc=datetime.now(timezone.utc).isoformat(),
        native_windows=True, virtualization=False, browser_ui=False,
        new_model_forwards=0, new_renders=0, human_listening=False,
        historical_regression_rerun=False, new_competitor_market_audit=False,
        overall_completion_percentage=None)
    save('inventory.json', report)
    try:
        runtime = load(ROOT / 'local/agent-ffmpeg/runtime.json')
        manifest = load(ROOT / 'agent-ffmpeg-local-install-manifest.json')
        installed = Path(runtime['installed_directory'])
        assert runtime['release'] == 'v0.1.0-alpha.4-local.10'
        assert manifest['cli_version'] == '0.1.12'
        assert manifest['skill_count'] == 1 and manifest['module_count'] == 17
        assert load(installed / 'receipt.json')['manifest_sha256'] == runtime['manifest_sha256'] == manifest['manifest_sha256']
        canonical = ROOT / 'skills/agent-ffmpeg-local-editor'
        discovery = Path('C:/Users/carzy/.codex/skills/agent-ffmpeg-local-editor')
        assert discovery.resolve() == canonical.resolve()
        for row in manifest['files']:
            path = ROOT / row['path']
            assert path.stat().st_size == row['bytes'] and digest(path) == row['sha256']
        assert len(manifest['files']) == 65
        kit = load(ROOT / 'docs/skills/community-unified-skill-package-0.1.12.json')
        assert digest(ROOT / kit['archive']) == kit['sha256']
        assert (ROOT / kit['archive']).stat().st_size == kit['bytes']
        source = ROOT / 'product/src/ai_ad_editor'
        package = installed / 'site/ai_ad_editor'
        source_hashes = {path.name: digest(path) for path in sorted(source.glob('*.py'))}
        installed_hashes = {path.name: digest(path) for path in sorted(package.glob('*.py'))}
        assert len(source_hashes) == 202 and source_hashes == installed_hashes
        save('installed-source-comparison.json', dict(source=source_hashes, installed=installed_hashes, equal=True))
        calls, responses = [], {}
        for args in (['version'], ['doctor'], ['capabilities'], ['schema', 'show'], ['gpu', 'inspect'], ['model-pack', 'list']):
            name = '-'.join(args)
            command = ['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
                str(discovery / 'scripts/run.ps1'), *args]
            started = time.perf_counter()
            result = subprocess.run(command, cwd=ROOT, capture_output=True, timeout=90,
                creationflags=subprocess.CREATE_NO_WINDOW)
            stdout, stderr = OUT / 'logs' / (name + '.stdout.json'), OUT / 'logs' / (name + '.stderr.txt')
            stdout.write_bytes(result.stdout)
            stderr.write_bytes(result.stderr)
            value = json.loads(result.stdout.decode('utf-8-sig'))
            calls.append(dict(name=name, argv=command, exit_code=result.returncode,
                ok=value.get('ok'), status=value.get('status'), elapsed_seconds=time.perf_counter()-started,
                stdout_sha256=digest(stdout), stderr_sha256=digest(stderr)))
            save('calls.json', calls)
            assert result.returncode == 0 and value['ok'] and value['status'] == 'succeeded', value
            responses[name] = value
        assert responses['version']['data']['cli_version'] == '0.1.12'
        entries = responses['capabilities']['data']['capabilities']
        counts = dict(Counter(row['status'] for row in entries.values()))
        assert len(entries) == 75 and counts == dict(implemented=20, implemented_with_limits=47, local_adapter_only=7, degraded=1)
        assert entries == load(ROOT / 'docs/product/semantic-recovery-capabilities-cli-0.1.12.json')['data']['capabilities']
        public = dict(url='https://api.github.com/repos/copypasteltd/agent-editor-kit/releases?per_page=10',
            http_status=None, error=None)
        try:
            request = urllib.request.Request(public['url'], headers={'User-Agent': 'agent-editor-kit-assessment',
                'Accept': 'application/vnd.github+json'})
            with urllib.request.urlopen(request, timeout=30) as remote:
                raw = remote.read(4*1024*1024+1)
                public['http_status'] = remote.status
            assert len(raw) <= 4*1024*1024
            (OUT / 'github-releases.raw.json').write_bytes(raw)
            public['response_sha256'] = hashlib.sha256(raw).hexdigest()
            public['releases'] = [{key: row[key] for key in ('tag_name', 'draft', 'prerelease', 'published_at', 'html_url')}
                for row in json.loads(raw)]
            published = [row for row in public['releases'] if not row['draft']]
            public['latest_published_tag'] = max(published, key=lambda row: row['published_at'])['tag_name']
        except (OSError, ValueError) as exc:
            public['http_status'] = getattr(exc, 'code', None)
            public['error'] = str(exc)
        timeout_receipt = ROOT / 'docs/validation/evidence/semantic-recovery-20261025-r1/faults-r1/search-timeout/verification.json'
        timeout = load(timeout_receipt)
        report['known_timeout_failure'] = dict(receipt=timeout_receipt.relative_to(ROOT).as_posix(),
            sha256=digest(timeout_receipt), elapsed_seconds=timeout['fault_process']['elapsed_seconds'],
            actual_timeout_error=timeout['actual_timeout'], timing_acceptance=False, new_execution=False)
        current = numbered((ROOT / REPORT).read_text('utf-8-sig'), 'G')
        assert len(current) == 38
        assert source_hashes == {p.name: digest(p) for p in source.glob('*.py')}
        assert source_hashes == {p.name: digest(p) for p in package.glob('*.py')}
        assert git('rev-parse', 'HEAD').decode().strip() == baseline
        report.update(status='passed-read-only-installed-review', checked_at_utc=datetime.now(timezone.utc).isoformat(),
            runtime=runtime, installed_cli='0.1.12', calls=calls, capability_count=len(entries),
            capability_status_counts=counts, product_python_files=202, source_and_installed_equal=True,
            registered_skill='agent-ffmpeg-local-editor', internal_modules=17, skill_pinned_files=65,
            kit_sha256=kit['sha256'], public_release_check=public, gap_groups=38,
            fully_closed_groups=0, generator_sha256=digest(Path(__file__)))
        save('inventory.json', report)
        print(json.dumps({key: report[key] for key in ('status', 'installed_cli', 'capability_status_counts', 'source_and_installed_equal', 'gap_groups')}))
        print(json.dumps(public, ensure_ascii=False))
    except BaseException as exc:
        report.update(status='failed', error=repr(exc))
        save('inventory.json', report)
        raise


def audit():
    record = load(OUT / 'inventory.json')
    assert record['status'] == 'passed-read-only-installed-review'
    assert git('rev-parse', 'HEAD').decode().strip() == record['baseline_commit']
    assert not (OUT / 'documentation-audit.json').exists()
    save('documentation-audit.json', dict(status='running', started_at_utc=datetime.now(timezone.utc).isoformat()))
    (OUT / 'executed-documentation-auditor.py').write_bytes(Path(__file__).read_bytes())
    before = numbered(git('show', record['baseline_commit'] + ':' + REPORT).decode('utf-8-sig'), 'G')
    after = numbered((ROOT / REPORT).read_text('utf-8-sig'), 'G')
    assert len(before) == len(after) == 38
    assert all(after[key].split('|')[5].strip() == row.split('|')[5].strip() for key, row in before.items())
    docs = [ROOT / REPORT, ROOT / 'docs/product/IMPLEMENTATION_PLAN_20261025.md']
    for name in READMES:
        text = (ROOT / name).read_text('utf-8-sig')
        historical = numbered(git('show', record['baseline_commit'] + ':' + name).decode('utf-8-sig'), 'R')
        rows = numbered(text, 'R')
        assert len(historical) == 94 and len(rows) == 95
        assert all(rows[key] == row for key, row in historical.items())
        for prefix, expected in (('F', 51), ('S', 20), ('K', 17)):
            assert len(numbered(text, prefix)) == expected
        docs.append(ROOT / name)
    links = 0
    for path in docs:
        for match in re.finditer(r'!?\[[^\]]*\]\(([^)]+)\)', path.read_text('utf-8-sig')):
            target = match[1].strip().strip('<>')
            if re.match(r'^[a-z][a-z0-9+.-]*:', target, re.I) or target.startswith('#'):
                continue
            target = unquote(target.split('#', 1)[0])
            assert (path.parent / target).exists(), (path, target)
            links += 1
    for call in record['calls']:
        assert digest(OUT / 'logs' / (call['name'] + '.stdout.json')) == call['stdout_sha256']
        assert digest(OUT / 'logs' / (call['name'] + '.stderr.txt')) == call['stderr_sha256']
    result = dict(status='passed', checked_at_utc=datetime.now(timezone.utc).isoformat(),
        original_goal_closure_conditions_preserved=38, historical_readme_rows_preserved_per_language=94,
        current_readme_rows_per_language=95, functional_rows=51, service_rows=20, internal_skill_rows=17,
        local_links_checked=links, actual_read_only_cli_calls=6, new_model_forwards=0, new_renders=0,
        human_listening=False, files=[dict(path=p.relative_to(ROOT).as_posix(), sha256=digest(p)) for p in docs])
    save('documentation-audit.json', result)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=('inventory', 'audit'))
    args = parser.parse_args()
    (inventory if args.mode == 'inventory' else audit)()
