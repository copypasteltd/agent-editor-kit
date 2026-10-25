"""Audit the real installed editable-ad delivery without new inference/renders."""
import argparse
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
BASE = ROOT/'docs/validation/evidence/ad-storyboard-20261025-r1'
GIT = 'C:/Users/carzy/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/git/cmd/git.exe'


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def load(path):
    return json.loads(path.read_bytes())


def git(*args):
    return subprocess.check_output([GIT, '--no-optional-locks', '-c', 'core.fsmonitor=false',
        '-c', 'gc.auto=0', '-c', 'maintenance.auto=false', *args], cwd=ROOT, timeout=120)


def rows(text, prefix):
    return {m[1]: m[0] for m in re.finditer(r'^\| ('+prefix+r'\d{2,3})\s*\|.*$', text, re.M)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', required=True)
    args = parser.parse_args()
    assert re.fullmatch(r'r[1-9][0-9]*', args.run)
    out = BASE/('final-delivery-'+args.run); out.mkdir(exist_ok=False)
    (out/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    def save(name, value):
        (out/name).write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf8', newline='\n')
    report = dict(status='running', started_at_utc=datetime.now(timezone.utc).isoformat(), native_windows=True,
        virtualization=False, browser_ui=False, new_model_forwards_in_audit=0, new_renders_in_audit=0,
        human_playback=False, human_listening=False, natural_ad_quality_acceptance=False,
        independent_agent_benchmark=False)
    save('verification.json', report)
    try:
        baseline = git('rev-parse', 'HEAD').decode().strip()
        assert baseline == 'bcd479d3ddfe2362e8cf71dc0b54f2b35afe792f'
        assert git('branch', '--show-current').decode().strip() == 'main'
        assert git('remote', 'get-url', 'origin').decode().strip() == 'git@github.com:copypasteltd/agent-editor-kit.git'
        runtime = load(ROOT/'local/agent-ffmpeg/runtime.json')
        installation = load(BASE/'installation-r2/verification.json')
        installed = Path(runtime['installed_directory'])
        assert runtime['release'] == 'v0.1.0-alpha.4-local.12'
        assert installed.resolve() == Path(installation['installed']).resolve()
        assert sha(Path(installation['archive'])) == installation['archive_sha256']
        assert Path(installation['archive']).stat().st_size == installation['archive_bytes'] == 302674843
        assert load(installed/'receipt.json')['manifest_sha256'] == runtime['manifest_sha256'] == installation['manifest_sha256']
        source = {p.name: sha(p) for p in (ROOT/'product/src/ai_ad_editor').glob('*.py')}
        assert len(source) == 205 and source == {p.name: sha(p) for p in (installed/'site/ai_ad_editor').glob('*.py')}
        manifest = load(ROOT/'agent-ffmpeg-local-install-manifest.json')
        assert manifest['cli_version'] == '0.1.14' and manifest['skill_count'] == 1 and manifest['module_count'] == 17
        assert manifest['manifest_sha256'] == runtime['manifest_sha256'] and len(manifest['files']) == 66
        for row in manifest['files']:
            assert sha(ROOT/row['path']) == row['sha256'] and (ROOT/row['path']).stat().st_size == row['bytes']
        discovery = Path('C:/Users/carzy/.codex/skills/agent-ffmpeg-local-editor')
        assert discovery.resolve() == (ROOT/'skills/agent-ffmpeg-local-editor').resolve()
        kit = load(ROOT/'docs/skills/community-unified-skill-package-0.1.14.json')
        assert sha(ROOT/kit['archive']) == kit['sha256'] and kit['files'] == 88
        with zipfile.ZipFile(ROOT/kit['archive']) as archive:
            inventory = json.loads(archive.read('KIT-FILES.json'))
            assert inventory['cli_version'] == '0.1.14' and inventory['skill_count'] == 1 and inventory['module_count'] == 17
            assert len(archive.namelist()) == len(set(archive.namelist())) == 88
            for row in inventory['files']:
                data = archive.read(row['path'])
                assert len(data) == row['bytes'] and hashlib.sha256(data).hexdigest() == row['sha256']
                if row['path'].startswith('skills/'):
                    assert data == (ROOT/row['path']).read_bytes()
        kit_proof = load(BASE/'kit-r2/verification.json')
        assert kit_proof['status'] == 'passed' and kit_proof['skill_files'] == 66 and kit_proof['process_calls'] == 8
        assert kit_proof['kit_sha256'] == kit['sha256'] and not kit_proof['real_discovery_changed']
        assert load(BASE/'kit-r1/failure.json')['status'] == 'failed'
        upgrade_error = load(BASE/'kit-r1/semantic-dry-run.stdout.txt')
        assert upgrade_error['errors'][0]['code'] == 'SEMANTIC_ADAPTER_INTEGRITY_FAILED'
        validation = subprocess.run([str(Path('C:/Python313/python.exe')), '-E', '-B', '-u', '-X', 'utf8',
            'C:/Users/carzy/.codex/skills/.system/skill-creator/scripts/quick_validate.py', str(discovery)],
            cwd=ROOT, capture_output=True, timeout=60, creationflags=subprocess.CREATE_NO_WINDOW)
        (out/'skill-validation.stdout.txt').write_bytes(validation.stdout)
        (out/'skill-validation.stderr.txt').write_bytes(validation.stderr)
        assert validation.returncode == 0 and b'Skill is valid!' in validation.stdout
        calls, responses = [], {}
        for parameters in (['version'], ['doctor'], ['capabilities'], ['schema', 'show'], ['gpu', 'inspect'], ['model-pack', 'list']):
            name = '-'.join(parameters)
            command = ['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(discovery/'scripts/run.ps1'), *parameters]
            result = subprocess.run(command, cwd=ROOT, capture_output=True, timeout=180, creationflags=subprocess.CREATE_NO_WINDOW)
            stdout, stderr = out/(name+'.stdout.json'), out/(name+'.stderr.txt')
            stdout.write_bytes(result.stdout); stderr.write_bytes(result.stderr)
            calls.append(dict(argv=command, exit_code=result.returncode, stdout_sha256=sha(stdout), stderr_sha256=sha(stderr)))
            save('calls.json', calls)
            value = json.loads(result.stdout.decode('utf-8-sig')); responses[name] = value
            assert result.returncode == 0 and value['ok']
            print(json.dumps(dict(id=name, status='passed')), flush=True)
        assert responses['version']['data']['cli_version'] == '0.1.14'
        capabilities = responses['capabilities']['data']['capabilities']
        assert capabilities == load(ROOT/'docs/product/ad-storyboard-capabilities-cli-0.1.14.json')['data']['capabilities']
        counts = dict(Counter(value['status'] for value in capabilities.values()))
        assert len(capabilities) == 75 and counts == dict(implemented=20, implemented_with_limits=47, local_adapter_only=7, degraded=1)
        for name, count in (('development-r4', 226), ('installed-r2', 55), ('installed-cli-r2', 122)):
            proof = load(BASE/'tests'/name/'verification.json')
            assert proof['status'] == 'passed' and proof['frozen_equal']
            assert proof['result'] == dict(methods=count, skipped=0, failures=0, errors=0, success=True)
            assert load(BASE/'tests'/name/'product-files.json') == source
            if name.startswith('installed'):
                assert proof['installed_frozen_equal']
        for phase in ('setup-finalize-r1', 'render-continue-r1', 'revision-r1', 'roundtrip-r1', 'skill-r1', 'media-r1'):
            assert load(BASE/phase/'verification.json')['status'] == 'passed'
        voice = load(BASE/'setup-finalize-r1/verification.json')
        assert voice['recorded_actual_voice_generations'] == 3 and voice['recorded_model_initializations'] == 1
        assert voice['reviewed_original_text_preserved'] and voice['translation_worker_calls'] == 0
        assert voice['devices']['voice']['selected'] == 'cuda'
        for row in voice['verified_prior_calls']:
            assert sha(ROOT/row['path']) == row['sha256']
        assert load(BASE/'render-continue-r1/verification.json')['variant_frames'] == dict(vertical12=360, wide9=270, square9=270)
        for phase in ('revision-r1', 'skill-r1'):
            proof = load(BASE/phase/'verification.json')
            for field in ('unselected_sequences_identical', 'first_180_decoded_frames_identical', 'last_90_frames_changed', 'decoded_pcm_identical', 'original_assets_preserved'):
                assert proof[field], (phase, field)
        package = ROOT/'workspace/ad-storyboard-20261025-installed-r1/campaign.aevpkg.zip'
        roundtrip = load(BASE/'roundtrip-r1/verification.json')
        assert roundtrip['original_project_unavailable'] and roundtrip['rgb_frames_identical'] and roundtrip['pcm_identical']
        assert roundtrip['editable_variants'] == 3 and sha(package) == roundtrip['package_sha256']
        assert not (package.parent/'project').exists()
        for phase in ('setup-r1', 'setup-continue-r1', 'render-r1'):
            assert load(BASE/phase/'verification.json')['status'] == 'failed'
        media = load(ROOT/'docs/assets/ad-storyboard-20261025-r1/media-manifest.json')
        assert media == load(BASE/'media-r1/verification.json') and not media['public_audio']
        for row in media['files']:
            assert sha(ROOT/row['path']) == row['sha256'] and (ROOT/row['path']).stat().st_size == row['bytes']
        board = load(BASE/'media-board-r1/verification.json')
        assert sha(ROOT/board['output']) == board['sha256']
        inspection = load(BASE/'still-inspection-r1/verification.json')
        assert inspection['static_inspection_only'] and not inspection['continuous_human_playback']
        for row in inspection['files']:
            assert sha(ROOT/row['path']) == row['sha256']
        files = [ROOT/'docs/product/GOAL_GAPS_20261025.md', ROOT/'docs/product/IMPLEMENTATION_PLAN_20261025.md']
        old = rows(git('show', baseline+':docs/product/GOAL_GAPS_20261025.md').decode('utf-8-sig'), 'G')
        current = rows(files[0].read_text('utf-8-sig'), 'G')
        assert len(old) == len(current) == 38
        assert all(current[key].split('|')[5].strip() == value.split('|')[5].strip() for key, value in old.items())
        for name in ('README.md', 'README.zh-TW.md', 'README.en.md'):
            path = ROOT/name; text = path.read_text('utf-8-sig')
            old = rows(git('show', baseline+':'+name).decode('utf-8-sig'), 'R'); current = rows(text, 'R')
            assert len(old) == 101 and len(current) == 109
            assert all(current[key] == value for key, value in old.items())
            for prefix, count in (('F', 52), ('S', 20), ('K', 17)):
                assert len(rows(text, prefix)) == count
            files.append(path)
        files += [ROOT/'docs/README.md', ROOT/'docs/product/COMMUNITY_LOCAL_DELIVERY.md', ROOT/'docs/product/AD_STORYBOARD.md',
            ROOT/'docs/product/CASES.md', ROOT/'docs/product/SUBTITLE_DUBBING.md', ROOT/'docs/validation/可编辑广告分镜与返工实测_2026-10-25.md']
        files += [ROOT/('docs/product/'+name+suffix+'.md') for name in ('CAPABILITIES', 'SKILLS') for suffix in ('', '.zh-TW', '.en')]
        links = 0
        for path in files:
            text = path.read_text('utf-8-sig')
            if path.name.startswith('CAPABILITIES'):
                blocks = re.findall(r'^### `([^`]+)`\s*\n+```json\n(.*?)\n```', text, re.M|re.S)
                assert dict((key, json.loads(value)) for key, value in blocks) == capabilities
                assert len(rows(text, 'F')) == 52 and len(rows(text, 'S')) == 20
            if path.name.startswith('SKILLS'):
                assert len(rows(text, 'K')) == 17
            for match in re.finditer(r'!?\[[^\]]*\]\(([^)]+)\)', text):
                target = match[1].strip().strip('<>')
                if re.match(r'^[a-z][a-z0-9+.-]*:', target, re.I) or target.startswith('#'):
                    continue
                assert (path.parent/unquote(target.split('#', 1)[0])).exists(), (path, target)
                links += 1
        request = urllib.request.Request('https://api.github.com/repos/copypasteltd/agent-editor-kit/releases?per_page=10',
            headers={'User-Agent': 'agent-editor-kit-delivery-audit', 'Accept': 'application/vnd.github+json'})
        with urllib.request.urlopen(request, timeout=30) as remote:
            raw, status = remote.read(4*1024*1024+1), remote.status
        assert status == 200 and len(raw) <= 4*1024*1024
        (out/'github-releases.raw.json').write_bytes(raw)
        latest = max((r for r in json.loads(raw) if not r['draft']), key=lambda r: r['published_at'])['tag_name']
        assert latest == 'v0.1.0-alpha.3'
        assert source == {p.name: sha(p) for p in (ROOT/'product/src/ai_ad_editor').glob('*.py')}
        report.update(status='passed', finished_at_utc=datetime.now(timezone.utc).isoformat(), baseline_commit=baseline,
            cli_version='0.1.14', installed=str(installed), actual_read_only_cli_calls=len(calls), source_and_installed_files=205,
            skill_files=66, kit_files=88, kit_sha256=kit['sha256'], capability_count=75, capability_status_counts=counts,
            original_goal_closure_conditions_preserved=38, historical_readme_rows_preserved_per_language=101,
            current_readme_rows_per_language=109, local_links_checked=links, public_release=latest, public_api_status=status,
            actual_case_phases_verified=6, preserved_failed_phases=3,
            files=[dict(path=p.relative_to(ROOT).as_posix(), sha256=sha(p)) for p in files])
        save('verification.json', report)
        print(json.dumps({k: v for k, v in report.items() if k != 'files'}, ensure_ascii=False))
    except BaseException as exc:
        report.update(status='failed', error=repr(exc)); save('verification.json', report); raise


if __name__ == '__main__':
    main()
