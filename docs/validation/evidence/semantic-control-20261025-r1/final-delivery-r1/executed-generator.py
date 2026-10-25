"""Verify actual delivery, byte pins, interruption evidence and preserved scope."""
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
from urllib.parse import unquote
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'docs/validation/evidence/semantic-control-20261025-r1'
OUT = BASE / 'final-delivery-r1'
GIT = 'C:/Users/carzy/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/git/cmd/git.exe'


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def load(path):
    return json.loads(path.read_bytes())


def git(*args):
    return subprocess.check_output([GIT, '--no-optional-locks', '-c', 'core.fsmonitor=false',
        '-c', 'gc.auto=0', '-c', 'maintenance.auto=false', *args], cwd=ROOT, timeout=60)


def rows(text, prefix):
    return {m[1]: m[0] for m in re.finditer(r'^\| ('+prefix+r'\d{2})\s*\|.*$', text, re.M)}


def main():
    OUT.mkdir(exist_ok=False)
    (OUT / 'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    def save(name, value):
        (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')
    report = dict(status='running', started_at_utc=datetime.now(timezone.utc).isoformat(),
        native_windows=True, virtualization=False, browser_ui=False, new_inference_in_audit=0,
        new_renders_in_audit=0, human_quality_acceptance=False)
    save('verification.json', report)
    try:
        baseline = git('rev-parse', 'HEAD').decode().strip()
        runtime = load(ROOT / 'local/agent-ffmpeg/runtime.json')
        installation = load(BASE / 'installation-r1/verification.json')
        installed = Path(runtime['installed_directory'])
        assert runtime['release'] == 'v0.1.0-alpha.4-local.11'
        assert installed.resolve() == Path(installation['installed']).resolve()
        assert sha(Path(installation['archive'])) == installation['archive_sha256']
        assert load(installed / 'receipt.json')['manifest_sha256'] == runtime['manifest_sha256'] == installation['manifest_sha256']
        source = {p.name: sha(p) for p in (ROOT / 'product/src/ai_ad_editor').glob('*.py')}
        assert len(source) == 203 and source == {p.name: sha(p) for p in (installed / 'site/ai_ad_editor').glob('*.py')}
        manifest = load(ROOT / 'agent-ffmpeg-local-install-manifest.json')
        assert manifest['cli_version'] == '0.1.13' and manifest['skill_count'] == 1 and manifest['module_count'] == 17
        assert manifest['manifest_sha256'] == runtime['manifest_sha256']
        for row in manifest['files']:
            assert sha(ROOT / row['path']) == row['sha256'] and (ROOT / row['path']).stat().st_size == row['bytes']
        assert len(manifest['files']) == 65
        discovery = Path('C:/Users/carzy/.codex/skills/agent-ffmpeg-local-editor')
        assert discovery.resolve() == (ROOT / 'skills/agent-ffmpeg-local-editor').resolve()
        kit = load(ROOT / 'docs/skills/community-unified-skill-package-0.1.13.json')
        assert sha(ROOT / kit['archive']) == kit['sha256']
        with zipfile.ZipFile(ROOT / kit['archive']) as archive:
            inventory = json.loads(archive.read('KIT-FILES.json'))
            assert inventory['cli_version'] == '0.1.13'
            for row in inventory['files']:
                data = archive.read(row['path'])
                assert hashlib.sha256(data).hexdigest() == row['sha256'] and len(data) == row['bytes']
                if row['path'].startswith('skills/'):
                    assert data == (ROOT / row['path']).read_bytes()
        assert load(BASE / 'kit-r1/verification.json')['status'] == 'passed'
        calls, responses = [], {}
        for args in (['version'], ['doctor'], ['capabilities'], ['schema','show'], ['gpu','inspect'], ['model-pack','list']):
            name = '-'.join(args)
            command = ['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',str(discovery / 'scripts/run.ps1'),*args]
            result = subprocess.run(command,cwd=ROOT,capture_output=True,timeout=180,creationflags=subprocess.CREATE_NO_WINDOW)
            stdout, stderr = OUT / (name+'.stdout.json'), OUT / (name+'.stderr.txt')
            stdout.write_bytes(result.stdout); stderr.write_bytes(result.stderr)
            value = json.loads(result.stdout.decode('utf-8-sig')); responses[name] = value
            calls.append(dict(argv=command,exit_code=result.returncode,stdout_sha256=sha(stdout),stderr_sha256=sha(stderr)))
            save('calls.json',calls)
            assert result.returncode == 0 and value['ok']
        assert responses['version']['data']['cli_version'] == '0.1.13'
        capabilities = responses['capabilities']['data']['capabilities']
        assert capabilities == load(ROOT / 'docs/product/semantic-control-capabilities-cli-0.1.13.json')['data']['capabilities']
        counts = dict(Counter(v['status'] for v in capabilities.values()))
        assert len(capabilities) == 75 and counts == dict(implemented=20,implemented_with_limits=47,local_adapter_only=7,degraded=1)
        for name, count in (('development-r1',168),('installed-r1',168),('development-cli-r1',122),
                            ('bounded-development-r1',5),('bounded-installed-r1',5)):
            verification = load(BASE / 'tests' / name / 'verification.json')
            assert verification['status'] == 'passed' and verification['frozen_equal'] and verification['installed_frozen_equal']
            assert verification['result'] == dict(methods=count,skipped=0,failures=0,errors=0,success=True)
            assert load(BASE / 'tests' / name / 'product-files.json') == source
        faults = load(BASE / 'faults-r1/verification.json')
        assert faults['status'] == 'passed' and len(faults['cases']) == 5
        for fault in faults['cases']:
            case = BASE / 'faults-r1' / fault['case']
            assert sha(case / 'stdout.json') == fault['stdout_sha256']
            assert sha(case / 'stderr.txt') == fault['stderr_sha256']
            assert fault['error']['diagnostics']['partial_digest_discarded']
        for name in ('after-cuda','after-cpu','skill-cuda'):
            evidence = load(BASE / 'installed-r1' / name / 'verification.json')
            assert evidence['status'] == 'completed-with-explicit-quality-limits'
            assert evidence['all_80_decisions_and_ordered_hits_identical']
            assert evidence['original_source_and_external_paths_unavailable']
            errors = {r['id'] for r in evidence['quality']['queries'] if not (r['top1_correct'] if r['expected_asset_ids'] else r['rejected'])}
            assert errors == {'q14','hout00zh','hout08zh'}
        files = [ROOT / 'docs/product/GOAL_GAPS_20261025.md',ROOT / 'docs/product/IMPLEMENTATION_PLAN_20261025.md']
        previous = rows(git('show',baseline+':docs/product/GOAL_GAPS_20261025.md').decode('utf-8-sig'),'G')
        current = rows(files[0].read_text('utf-8-sig'),'G')
        assert len(previous) == len(current) == 38
        assert all(current[key].split('|')[5].strip() == line.split('|')[5].strip() for key,line in previous.items())
        for name in ('README.md','README.zh-TW.md','README.en.md'):
            path = ROOT / name; text = path.read_text('utf-8-sig')
            old = rows(git('show',baseline+':'+name).decode('utf-8-sig'),'R'); new = rows(text,'R')
            assert len(old) == 95 and len(new) == 101
            assert all(new[key] == line for key,line in old.items())
            for prefix,count in (('F',51),('S',20),('K',17)):
                assert len(rows(text,prefix)) == count
            files.append(path)
        files += [ROOT / 'docs/README.md',ROOT / 'docs/product/COMMUNITY_LOCAL_DELIVERY.md',
            ROOT / 'docs/product/SEMANTIC_JOB_RECOVERY.md',ROOT / 'docs/product/SEMANTIC_RETRIEVAL.md',
            ROOT / 'docs/product/CASES.md',ROOT / 'docs/validation/完整性校验超时取消实测_2026-10-25.md']
        files += [ROOT / ('docs/product/CAPABILITIES'+suffix+'.md') for suffix in ('','.zh-TW','.en')]
        links = 0
        for path in files:
            for match in re.finditer(r'!?\[[^\]]*\]\(([^)]+)\)',path.read_text('utf-8-sig')):
                target = match[1].strip().strip('<>')
                if re.match(r'^[a-z][a-z0-9+.-]*:',target,re.I) or target.startswith('#'):
                    continue
                assert (path.parent / unquote(target.split('#',1)[0])).exists(),(path,target)
                links += 1
        url = 'https://api.github.com/repos/copypasteltd/agent-editor-kit/releases?per_page=10'
        request = urllib.request.Request(url,headers={'User-Agent':'agent-editor-kit-delivery-audit','Accept':'application/vnd.github+json'})
        with urllib.request.urlopen(request,timeout=30) as remote:
            raw = remote.read(4*1024*1024+1); status = remote.status
        assert status == 200 and len(raw) <= 4*1024*1024
        (OUT / 'github-releases.raw.json').write_bytes(raw)
        latest = max((r for r in json.loads(raw) if not r['draft']),key=lambda r:r['published_at'])['tag_name']
        assert latest == 'v0.1.0-alpha.3'
        assert source == {p.name:sha(p) for p in (ROOT / 'product/src/ai_ad_editor').glob('*.py')}
        report.update(status='passed',finished_at_utc=datetime.now(timezone.utc).isoformat(),baseline_commit=baseline,
            installed=str(installed),cli_version='0.1.13',actual_read_only_cli_calls=len(calls),capability_count=75,
            capability_status_counts=counts,source_and_installed_files=203,skill_files=65,kit_sha256=kit['sha256'],
            original_goal_closure_conditions_preserved=38,historical_readme_rows_preserved_per_language=95,
            current_readme_rows_per_language=101,local_links_checked=links,public_release=latest,public_api_status=status,
            files=[dict(path=p.relative_to(ROOT).as_posix(),sha256=sha(p)) for p in files])
        save('verification.json',report)
        print(json.dumps({k:v for k,v in report.items() if k!='files'},ensure_ascii=False))
    except BaseException as exc:
        report.update(status='failed',error=repr(exc)); save('verification.json',report); raise


if __name__ == '__main__':
    main()
