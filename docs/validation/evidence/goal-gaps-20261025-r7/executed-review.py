"""Record a read-only goal assessment; do not turn unintegrated drafts into delivery."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'docs/validation/evidence/goal-gaps-20261025-r7'
GIT = Path('C:/Users/carzy/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/git/cmd/git.exe')
REPORT = 'docs/product/GOAL_GAPS_20261025.md'
READMES = ['README.md', 'README.zh-TW.md', 'README.en.md']


def git(*args):
    return subprocess.check_output([str(GIT), '--no-optional-locks', '-c', 'core.fsmonitor=false',
                                    '-c', 'gc.auto=0', '-c', 'maintenance.auto=false', *args], cwd=ROOT)


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def load(path):
    return json.loads(path.read_text('utf-8-sig'))


def save(name, value):
    target = OUT / name
    assert not target.exists(), target
    target.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')


def groups(text):
    rows = []
    for line in text.splitlines():
        if re.match(r'^\| G\d{2} \|', line):
            cells = [cell.strip() for cell in line.strip('|').split('|')]
            assert len(cells) == 6, line
            rows.append(dict(zip(('id', 'module', 'current', 'gap', 'closure', 'order'), cells)))
    assert [row['id'] for row in rows] == [f'G{i:02d}' for i in range(1, 39)]
    return rows


def prepare():
    inventory = load(OUT / 'inventory.json')
    assert len(inventory['calls']) == 6
    assert all(call['exit_code'] == 0 and call['status'] == 'succeeded' for call in inventory['calls'])
    assert inventory['version']['cli_version'] == '0.1.7'
    assert inventory['statuses'] == dict(implemented=20, implemented_with_limits=46, local_adapter_only=7, degraded=1)
    installed = Path(inventory['runtime']['installed_directory'])
    assert installed.is_relative_to(ROOT)
    python_paths = [name for name in git('ls-files', '-z', 'product/src/ai_ad_editor').decode('utf-8').split('\0')
                    if name.endswith('.py')]
    comparisons = []
    for name in python_paths:
        source = ROOT / name
        counterpart = installed / 'site' / source.relative_to(ROOT / 'product/src')
        expected = hashlib.sha256(git('show', 'HEAD:' + name)).hexdigest()
        actual = digest(source)
        packaged = digest(counterpart)
        assert expected == actual == packaged, name
        comparisons.append(dict(path=name, sha256=actual, committed_source_and_installed_equal=True))
    assert len(comparisons) == 194
    baseline_report = git('show', 'HEAD:' + REPORT).decode('utf-8-sig')
    baseline = dict(commit=git('rev-parse', 'HEAD').decode().strip(), groups=groups(baseline_report), readmes={})
    for name in READMES:
        old = git('show', 'HEAD:' + name).decode('utf-8-sig')
        lines = [line for line in old.splitlines() if re.match(r'^\| R\d{2} \|', line)]
        assert len(lines) == 58
        baseline['readmes'][name] = lines
    save('baseline.json', baseline)
    save('installed-source-comparison.json', comparisons)
    candidates = []
    for name in ('product/src/ai_ad_editor/ctc_activity.py', 'docs/specs/CTC声学活动边界契约_20261025.md'):
        path = ROOT / name
        candidates.append(dict(path=name, sha256=digest(path), installed=False, integrated=False,
                               new_tests_or_model_results=None, counts_as_delivered=False))
    assert not (installed / 'site/ai_ad_editor/ctc_activity.py').exists()
    for name in ('cli.py', 'ctc_cli.py', 'ctc_worker.py', 'local_ctc.py'):
        content = (installed / 'site/ai_ad_editor' / name).read_text('utf-8-sig')
        assert 'ctc_activity' not in content and 'boundary-mode' not in content
    ctc_path = ROOT / 'docs/validation/evidence/ctc-real-en-20261018-b/word-boundary-quality.json'
    ctc = load(ctc_path)
    assert not ctc['passed'] and ctc['observed_max_error_seconds'] > ctc['predeclared_max_error_seconds']
    qwen_path = ROOT / 'docs/validation/evidence/implementation-20261025-r1/native-aligner-research/quality.json'
    qwen = load(qwen_path)
    qwen_cases = qwen['results'][0]['cases']
    assert all(not case['passed'] for case in qwen_cases)
    semantic_path = ROOT / 'docs/validation/evidence/semantic-20261025-r1/development-r1/queries/quality.json'
    semantic = load(semantic_path)
    failures = [row for row in semantic['queries'] if row['group'] != 'positive']
    kit = load(ROOT / 'docs/skills/community-unified-skill-package-0.1.7.json')
    assert digest(ROOT / kit['archive']) == kit['sha256']
    assert kit['skill_count'] == 1 and kit['module_count'] == 17
    record = dict(checked_at_utc=datetime.now(timezone.utc).isoformat(), scope='goal assessment and documentation only',
        installed_release=inventory['runtime']['release'], installed_cli='0.1.7', inventory_sha256=digest(OUT / 'inventory.json'),
        capability_count=inventory['capability_count'], declarations=inventory['statuses'],
        tracked_product_python_files_compared=len(comparisons), all_committed_source_and_installed_equal=True,
        development_candidates=candidates, kit_sha256=kit['sha256'], skill_count=1, modules=17,
        baseline_commit=baseline['commit'], gap_groups=38, closed_gap_groups=0,
        order_counts=dict(Counter(row['order'] for row in baseline['groups'])),
        historical_quality_evidence=dict(
            ctc=dict(path=ctc_path.relative_to(ROOT).as_posix(), sha256=digest(ctc_path),
                     maximum_error_ms=ctc['observed_max_error_seconds'] * 1000,
                     unchanged_gate_ms=ctc['predeclared_max_error_seconds'] * 1000, passed=False,
                     reference='authored trimmed word blocks, not independent phonetic truth'),
            qwen=dict(path=qwen_path.relative_to(ROOT).as_posix(), sha256=digest(qwen_path),
                      cases=[dict(fixture=case['fixture'], max_error_ms=case['max_error_ms'], passed=case['passed'])
                             for case in qwen_cases]),
            semantic=dict(path=semantic_path.relative_to(ROOT).as_posix(), sha256=digest(semantic_path),
                          non_positive_queries=failures)),
        public_release_api=inventory['github_release_api'], public_releases=inventory['public_releases'],
        new_product_features=0, new_model_forwards=0, new_renders=0, human_listening=False,
        full_historical_regression_rerun=False, virtualization=False, browser_ui=False,
        generator_sha256=digest(Path(__file__)))
    save('review.json', record)
    (OUT / 'executed-review.py').write_bytes(Path(__file__).read_bytes())
    print(json.dumps({key:record[key] for key in ('installed_cli', 'gap_groups', 'closed_gap_groups',
                                                'tracked_product_python_files_compared', 'order_counts')}, ensure_ascii=False))


def audit():
    baseline = load(OUT / 'baseline.json')
    current = groups((ROOT / REPORT).read_text('utf-8-sig'))
    assert [(r['id'], r['closure']) for r in current] == [(r['id'], r['closure']) for r in baseline['groups']]
    for name in READMES:
        content = (ROOT / name).read_text('utf-8-sig')
        old = [line for line in content.splitlines() if re.match(r'^\| R(?:0[1-9]|[1-4]\d|5[0-8]) \|', line)]
        assert old == baseline['readmes'][name], name
        for prefix, total in [('F', 50), ('S', 19), ('K', 17), ('R', 59)]:
            found = re.findall(r'^\| (' + prefix + r'\d{2})(?=\s|\|)', content, re.M)
            assert len(found) == total and len(set(found)) == total, (name, prefix, found)
        assert 'goal-gaps-20261025-r7/inventory.json' in content
        assert 'goal-gaps-20261025-r7/review.json' in content
    checked_links = 0
    paths = [ROOT / name for name in READMES + [REPORT, 'docs/README.md', 'docs/product/IMPLEMENTATION_PLAN_20261025.md']]
    for path in paths:
        content = re.sub(r'```.*?```', '', path.read_text('utf-8-sig'), flags=re.S)
        for target in re.findall(r'!?\[[^\]\n]*\]\(([^)\n]+)\)', content):
            target = target.strip().strip('<>')
            if re.match(r'^(?:https?://|mailto:|app:|codex:|#)', target):
                continue
            target = unquote(target.split('#', 1)[0])
            if not target:
                continue
            candidate = (path.parent / target).resolve()
            assert candidate.exists(), (str(path.relative_to(ROOT)), target)
            checked_links += 1
    record = dict(status='passed', checked_at_utc=datetime.now(timezone.utc).isoformat(),
                  all_38_original_closure_conditions_preserved=True,
                  original_R01_R58_rows_verbatim_preserved_in_three_readmes=True,
                  numbered_rows_per_readme=dict(F=50, S=19, K=17, R=59),
                  checked_local_link_targets=checked_links, scope='documentation audit; no media or model regression',
                  files=[dict(path=p.relative_to(ROOT).as_posix(), sha256=digest(p)) for p in paths],
                  generator_sha256=digest(Path(__file__)))
    save('documentation-audit.json', record)
    print(json.dumps({key:record[key] for key in ('status', 'checked_local_link_targets', 'numbered_rows_per_readme')}, ensure_ascii=False))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--audit-docs', action='store_true')
    args = parser.parse_args()
    audit() if args.audit_docs else prepare()
