"""Audit gap closure preservation, historical rows, local links and real receipts."""
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import re
import subprocess
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'docs/validation/evidence/goal-gaps-20261025-r8'
BASE = ROOT / 'docs/validation/evidence/ctc-activity-20261025-r1'
GIT = Path('C:/Users/carzy/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/git/cmd/git.exe')
BASELINE = '47386c538300c1c52e547aa39f42f974e20ba3b2'


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def load(path):
    return json.loads(path.read_bytes())


def git(*args):
    return subprocess.check_output([str(GIT), '--no-optional-locks', '-c', 'core.fsmonitor=false',
                                   '-c', 'gc.auto=0', '-c', 'maintenance.auto=false', *args], cwd=ROOT)


def groups(text):
    rows = [[part.strip() for part in line.strip('|').split('|')] for line in text.splitlines()
            if re.match(r'^\| G\d{2} \|', line)]
    assert len(rows) == 38 and all(len(row) == 6 for row in rows)
    assert [row[0] for row in rows] == [f'G{i:02d}' for i in range(1, 39)]
    return rows


def main():
    output = OUT / 'review.json'
    assert not output.exists()
    (OUT / 'executed-review.py').write_bytes(Path(__file__).read_bytes())
    report_name = 'docs/product/GOAL_GAPS_20261025.md'
    old = groups(git('show', BASELINE + ':' + report_name).decode('utf-8-sig'))
    new = groups((ROOT / report_name).read_text('utf-8-sig'))
    assert [(row[0], row[4]) for row in old] == [(row[0], row[4]) for row in new]
    roots = ['README.md', 'README.zh-TW.md', 'README.en.md']
    readmes = []
    for name in roots:
        before = git('show', BASELINE + ':' + name).decode('utf-8-sig')
        after = (ROOT / name).read_text('utf-8-sig')
        baseline_rows = [line for line in before.splitlines() if re.match(r'^\| R\d{2} \|', line)]
        assert len(baseline_rows) == 59
        assert all(line in after.splitlines() for line in baseline_rows)
        ids = re.findall(r'^\| (R\d{2}) \|', after, re.M)
        assert ids == [f'R{i:02d}' for i in range(1, 66)]
        for prefix, count in [('F', 50), ('S', 19), ('K', 17)]:
            found = set(re.findall(r'^\| (' + prefix + r'\d{2})(?: /[^|]*)? \|', after, re.M))
            assert found == {f'{prefix}{i:02d}' for i in range(1, count + 1)}, (name, prefix, len(found))
        readmes.append(dict(path=name, preserved_history_rows=59, current_verification_rows=65,
                            functional_ids=50, service_ids=19, internal_skill_ids=17, sha256=sha(ROOT / name)))
    runtime = load(ROOT / 'local/agent-ffmpeg/runtime.json')
    installed = Path(runtime['installed_directory'])
    assert runtime['release'] == 'v0.1.0-alpha.4-local.6'
    files = sorted((ROOT / 'product/src/ai_ad_editor').rglob('*.py'))
    assert len(files) == 195
    for path in files:
        assert path.read_bytes() == (installed / 'site' / path.relative_to(ROOT / 'product/src')).read_bytes()
    caps = load(ROOT / 'docs/product/ctc-activity-capabilities-cli-0.1.8.json')['data']['capabilities']
    assert len(caps) == 74
    assert Counter(value['status'] for value in caps.values()) == Counter(dict(
        implemented=20, implemented_with_limits=46, local_adapter_only=7, degraded=1))
    assert 'ctc-guided-activity-v3' in json.dumps(caps['forced_alignment'])
    inv = load(OUT / 'inventory.json')
    assert len(inv['calls']) == 6 and all(row['exit_code'] == 0 for row in inv['calls'])
    assert inv['public_release_check']['latest_published_tag'] == 'v0.1.0-alpha.3'
    for folder in ('development-v3-r1', 'installed-r1', 'cpu-v3-r1', 'skill-r1'):
        state = load(BASE / folder / 'state.json')
        assert state['frozen_equal'] and state['all_activity_gates_passed'] and not state['full_G15_closed']
    failed = load(BASE / 'installed-cli-regression-r1/verification.json')
    assert failed['exit_code'] == 1 and failed['methods'] == 122 and failed['frozen_equal']
    log = (BASE / 'installed-cli-regression-r1/tests.log').read_text('utf-8')
    assert len(re.findall(r'\.\.\. ok$', log, re.M)) == 121
    assert 'FAILED (failures=1)' in log and 'FAIL: test_runtime_storage_is_local_to_product' in log
    failed_test = BASE / 'installed-cli-regression-r1/failed-test_cli.py'
    expected = next(row['sha256'] for row in failed['frozen_before'] if row['path'].endswith('tests\\test_cli.py'))
    assert expected == 'sha256:' + sha(failed_test)
    for folder in ('installed-runtime-recheck-r1', 'source-runtime-recheck-r1'):
        result = load(BASE / folder / 'verification.json')
        assert result['methods'] == 1 and result['exit_code'] == 0 and result['terminal_ok'] and result['frozen_equal']
    protected = ROOT / 'docs/skills/agent-editor-kit-community-unified-skill-r6.zip'
    assert sha(protected) == 'b6668d060de7c61f13896449072419eec5d6254bce52edc926fa1bae3e4d7b45'
    kit_meta = load(ROOT / 'docs/skills/community-unified-skill-package-0.1.8.json')
    assert sha(ROOT / kit_meta['archive']) == kit_meta['sha256']
    assert load(BASE / 'kit-r1/verification.json')['kit_sha256'] == kit_meta['sha256']
    names = roots + ['docs/README.md', report_name, 'docs/product/IMPLEMENTATION_PLAN_20261025.md',
        'docs/product/CASES.md', 'docs/product/CTC_ACTIVITY_ALIGNMENT.md',
        'docs/product/COMMUNITY_LOCAL_DELIVERY.md', 'docs/validation/CTC声学边界实测_2026-10-25.md']
    for family in ('CAPABILITIES', 'SKILLS', 'COMMUNITY_MATERIALS'):
        names.extend(f'docs/product/{family}{suffix}.md' for suffix in ('', '.zh-TW', '.en'))
    names.extend(f'docs/skills/UNIFIED_SKILL{suffix}.md' for suffix in ('', '.zh-TW', '.en'))
    missing, links = [], []
    for name in names:
        path = ROOT / name
        for target in re.findall(r'!?\[[^\]]*\]\(([^\n)]+)\)', path.read_text('utf-8-sig')):
            target = target.strip().strip('<>')
            if re.match(r'^[a-z][a-z0-9+.-]*:', target, re.I) or target.startswith('#'):
                continue
            plain = unquote(target.split('#')[0])
            if not plain:
                continue
            resolved = (path.parent / plain).resolve()
            links.append(dict(page=name, target=target))
            if not resolved.exists():
                missing.append(links[-1])
    assert not missing, missing
    result = dict(status='passed', checked_at_utc=datetime.now(timezone.utc).isoformat(),
        baseline_commit=BASELINE, installed_cli='0.1.8', source_python_files=195,
        source_and_installed_equal=True, gap_groups=38, closed_complete_gap_groups=0,
        all_original_closure_conditions_verbatim=True, order_counts=dict(Counter(row[5] for row in new)),
        readmes=readmes, local_links_checked=len(links), missing_local_links=missing,
        historical_R01_R59_preserved=True, cli_full_suite_initial_passed=121, cli_full_suite_initial_failed=1,
        test_assumption_corrected=True, installed_and_source_targeted_recheck_each=1,
        full_cli_suite_repeated_after_test_change=False, previous_r6_kit_unchanged=True,
        public_release='v0.1.0-alpha.3', full_capcut_parity=False, human_listening=False,
        new_competitor_market_audit=False, native_windows=True, virtualization=False, browser_ui=False,
        goal_remains_active=True, generator_sha256=sha(Path(__file__)))
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps({key:result[key] for key in ('status', 'installed_cli', 'gap_groups', 'closed_complete_gap_groups',
          'all_original_closure_conditions_verbatim', 'local_links_checked', 'historical_R01_R59_preserved')}, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
