"""Record installed, read-only facts and audit an additive full-goal review."""
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
OUT = ROOT / 'docs/validation/evidence/goal-gaps-20261025-r11'
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
    return json.loads(path.read_text('utf-8-sig'))


def save(name, value):
    with (OUT / name).open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write('\n')


def groups(content):
    rows = []
    for line in content.splitlines():
        if re.match(r'^\| G\d{2} \|', line):
            cells = [cell.strip() for cell in line.strip('|').split('|')]
            assert len(cells) == 6, line
            rows.append(dict(zip(('id', 'module', 'current', 'gap', 'closure', 'order'), cells)))
    assert [row['id'] for row in rows] == [f'G{i:02d}' for i in range(1, 39)]
    return rows


def inventory():
    OUT.mkdir(parents=True, exist_ok=False)
    (OUT / 'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    (OUT / 'logs').mkdir()
    before = git('rev-parse', 'HEAD').decode().strip()
    source_worktree_status = git('status', '--porcelain', '--', 'product/src/ai_ad_editor').decode('utf-8')
    skill = Path('C:/Users/carzy/.codex/skills/agent-ffmpeg-local-editor/scripts/run.ps1')
    calls, responses = [], {}
    for argv in (['version'], ['doctor'], ['capabilities'], ['schema', 'show'],
                 ['gpu', 'inspect'], ['model-pack', 'list']):
        name = '-'.join(argv)
        command = ['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(skill), *argv]
        started = time.perf_counter()
        result = subprocess.run(command, cwd=ROOT, capture_output=True, timeout=60)
        stdout = OUT / 'logs' / (name + '.stdout.json')
        stderr = OUT / 'logs' / (name + '.stderr.txt')
        stdout.write_bytes(result.stdout)
        stderr.write_bytes(result.stderr)
        data = json.loads(result.stdout.decode('utf-8-sig'))
        assert result.returncode == 0 and data['ok'] and data['status'] == 'succeeded', data
        responses[name] = data
        calls.append(dict(name=name, argv=command, exit_code=result.returncode, ok=data['ok'],
            status=data['status'], elapsed_seconds=time.perf_counter()-started,
            stdout_sha256=digest(stdout), stderr_sha256=digest(stderr)))
    runtime = load(ROOT / 'local/agent-ffmpeg/runtime.json')
    assert runtime['release'] == 'v0.1.0-alpha.4-local.7'
    assert responses['version']['data']['cli_version'] == '0.1.9'
    entries = responses['capabilities']['data']['capabilities']
    statuses = dict(Counter(value['status'] for value in entries.values()))
    assert len(entries) == 75 and statuses == dict(implemented=20, implemented_with_limits=47,
        local_adapter_only=7, degraded=1)
    installed = Path(runtime['installed_directory']) / 'site/ai_ad_editor'
    paths = [path.relative_to(ROOT).as_posix() for path in sorted((ROOT / 'product/src/ai_ad_editor').glob('*.py'))]
    comparisons = []
    for name in paths:
        source = ROOT / name
        packaged = installed / source.relative_to(ROOT / 'product/src/ai_ad_editor')
        assert digest(source) == digest(packaged), name
        comparisons.append(dict(path=name, source_and_installed_sha256=digest(source)))
    assert len(comparisons) == 197
    save('installed-source-comparison.json', comparisons)
    kit = load(ROOT / 'docs/skills/community-unified-skill-package-0.1.9.json')
    assert kit['skill_count'] == 1 and kit['module_count'] == 17
    assert digest(ROOT / kit['archive']) == kit['sha256']
    api = 'https://api.github.com/repos/copypasteltd/agent-editor-kit/releases?per_page=10'
    public = dict(url=api, http_status=None, releases=None, error=None)
    try:
        request = urllib.request.Request(api, headers={'User-Agent': 'agent-editor-kit-assessment',
            'Accept': 'application/vnd.github+json'})
        with urllib.request.urlopen(request, timeout=30) as remote:
            raw = remote.read(4*1024*1024+1)
            public['http_status'] = remote.status
        assert len(raw) <= 4*1024*1024
        (OUT / 'github-releases.raw.json').write_bytes(raw)
        public['response_sha256'] = hashlib.sha256(raw).hexdigest()
        public['releases'] = [{key: row[key] for key in ('tag_name', 'draft', 'prerelease',
            'published_at', 'html_url')} for row in json.loads(raw)]
        published = [row for row in public['releases'] if not row['draft']]
        public['latest_published_tag'] = max(published, key=lambda row: row['published_at'])['tag_name']
    except (OSError, ValueError) as exc:
        public['error'] = str(exc)
        public['http_status'] = getattr(exc, 'code', None)
    assert git('rev-parse', 'HEAD').decode().strip() == before
    rows = groups((ROOT / REPORT).read_text('utf-8-sig'))
    record = dict(status='passed-read-only-installed-review', checked_at_utc=datetime.now(timezone.utc).isoformat(),
        baseline_commit=before, source_worktree_status=source_worktree_status, runtime=runtime, installed_cli='0.1.9', calls=calls,
        capability_count=len(entries), capability_status_counts=statuses, product_python_files=197,
        source_and_installed_equal=True, registered_skill='agent-ffmpeg-local-editor', internal_modules=17,
        kit_sha256=kit['sha256'], gap_groups=38, closed_complete_gap_groups=0,
        order_counts=dict(Counter(row['order'] for row in rows)), public_release_check=public,
        new_model_forwards=0, new_renders=0, historical_regression_rerun=False,
        human_listening=False, new_competitor_market_audit=False, overall_completion_percentage=None,
        native_windows=True, virtualization=False, browser_ui=False, goal_remains_active=True,
        generator_sha256=digest(Path(__file__)))
    save('inventory.json', record)
    print(json.dumps({key: record[key] for key in ('installed_cli', 'capability_count',
        'capability_status_counts', 'product_python_files', 'gap_groups', 'closed_complete_gap_groups')}, ensure_ascii=False))
    print(json.dumps(public, ensure_ascii=False))


def audit():
    with (OUT / 'executed-documentation-auditor.py').open('xb') as stream:
        stream.write(Path(__file__).read_bytes())
    record = load(OUT / 'inventory.json')
    assert git('rev-parse', 'HEAD').decode().strip() == record['baseline_commit']
    baseline = groups(git('show', 'HEAD:' + REPORT).decode('utf-8-sig'))
    current = groups((ROOT / REPORT).read_text('utf-8-sig'))
    assert [(row['id'], row['closure']) for row in baseline] == [(row['id'], row['closure']) for row in current]
    for name in READMES:
        old = git('show', 'HEAD:' + name).decode('utf-8-sig')
        new = (ROOT / name).read_text('utf-8-sig')
        old_rows = re.findall(r'^\| R\d{2} \|.*$', old, re.M)
        new_rows = re.findall(r'^\| R\d{2} \|.*$', new, re.M)
        assert len(old_rows) == 72 and len(new_rows) == 73 and new_rows[:72] == old_rows, name
        for prefix, count in (('F', 51), ('S', 20), ('K', 17), ('R', 73)):
            ids = re.findall(r'^\| (' + prefix + r'\d{2})(?=\s|\|)', new, re.M)
            assert len(ids) == len(set(ids)) == count, (name, prefix, ids)
        assert 'goal-gaps-20261025-r11/inventory.json' in new
    paths = [ROOT / name for name in (*READMES, REPORT, 'docs/README.md',
        'docs/product/IMPLEMENTATION_PLAN_20261025.md', 'docs/product/SUBTITLE_DUBBING.md', 'docs/product/COMMUNITY_LOCAL_DELIVERY.md', 'docs/product/COMMUNITY_VOICES.md', 'docs/product/JOB_RECOVERY.md', 'docs/product/CASES.md', 'docs/product/CAPABILITIES.md', 'docs/product/CAPABILITIES.zh-TW.md', 'docs/product/CAPABILITIES.en.md', 'docs/product/SKILLS.md', 'docs/product/SKILLS.zh-TW.md', 'docs/product/SKILLS.en.md', 'docs/validation/字幕翻译配音联合流程实测_2026-10-25.md')]
    checked = 0
    for path in paths:
        content = re.sub(r'```.*?```', '', path.read_text('utf-8-sig'), flags=re.S)
        for target in re.findall(r'!?\[[^\]\n]*\]\(([^)\n]+)\)', content):
            target = target.strip().strip('<>')
            if re.match(r'^(?:https?://|mailto:|app:|codex:|#)', target):
                continue
            local = unquote(target.split('#', 1)[0])
            candidate = (path.parent / local).resolve()
            assert not local or candidate.exists() or candidate == OUT / 'documentation-audit.json', (path, target)
            checked += bool(local)
    save('documentation-audit.json', dict(status='passed', checked_at_utc=datetime.now(timezone.utc).isoformat(),
        baseline_commit=record['baseline_commit'], all_original_G01_G38_closure_conditions_verbatim=True,
        historical_R01_R72_verbatim_in_three_readmes=True, numbered_rows=dict(F=51, S=20, K=17, R=73),
        local_links_checked=checked, missing_local_links=[], new_product_features=0,
        scope='documentation audit only; batch product/model/render work has separate receipts',
        initial_documentation_audit_failed=False,
        new_renders=0, new_model_forwards=0, human_listening=False, full_capcut_parity=False,
        files=[dict(path=path.relative_to(ROOT).as_posix(), sha256=digest(path)) for path in paths],
        generator_sha256=digest(Path(__file__))))
    assert (OUT / 'documentation-audit.json').is_file()
    print(json.dumps(dict(status='passed', local_links_checked=checked,
        preserved_closure_conditions=38, preserved_historical_rows_per_readme=72)))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--audit-docs', action='store_true')
    args = parser.parse_args()
    audit() if args.audit_docs else inventory()
