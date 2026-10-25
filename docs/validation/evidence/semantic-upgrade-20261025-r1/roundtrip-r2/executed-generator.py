"""Real native upgrade with an owned old installation made unavailable."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import time

from run_semantic_decisions_20261025 import metrics

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT/'docs/validation/evidence/semantic-upgrade-20261025-r1'
WORK = ROOT/'workspace/semantic-upgrade-20261025-installed-r2'
PREVIOUS = ROOT/'workspace/semantic-control-20261025-installed-r1'
INSTALLED = ROOT/'local/agent-ffmpeg/v0.1.0-alpha.4-local.13/final-r3/installed'
PYTHON = 'C:/Python313/python.exe'


def load(path):
    return json.loads(path.read_bytes())


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf8', newline='\n')


def prefix(directory):
    return [PYTHON, '-I', '-S', '-B', '-u', '-X', 'utf8', directory/'run.py']


def original_inventory(project):
    value = load(project/'project.json')
    return dict(project=value, ledger=load(project/'rights-ledger.json'),
        files={a['id']: dict(uri=a['uri'], sha256=sha(project/a['uri'])) for a in value['assets']})


def assert_preserved(root, before):
    current = load(root/'project.json'); ledger = load(root/'rights-ledger.json')
    assert before['project']['sequences'] == current['sequences']
    for group in ('adapters', 'indexes', 'calibrations'):
        assert all(row in current['extensions']['local_semantic'][group] for row in before['project']['extensions']['local_semantic'][group])
    assets = {a['id']: a for a in current['assets']}
    for asset in before['project']['assets']:
        assert assets[asset['id']] == asset and sha(root/asset['uri']) == before['files'][asset['id']]['sha256']
    assert all(row in ledger['records'] for row in before['ledger']['records'])


def compare(old, new):
    result = []
    for previous, current in zip(old['data']['results'], new['data']['results'], strict=True):
        assert previous['query'] == current['query'] and previous['decision'] == current['decision']
        assert [r['asset_id'] for r in previous['hits']] == [r['asset_id'] for r in current['hits']]
        error = max((abs(a['score']-b['score']) for a, b in zip(previous['hits'], current['hits'], strict=True)), default=0)
        assert error <= 1e-6
        result.append(dict(id=current['query']['id'], decision_and_order_identical=True, maximum_score_error=error))
    assert len(result) == 80
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase', required=True, choices=('setup', 'before', 'upgrade', 'after', 'roundtrip', 'skill'))
    parser.add_argument('--device', choices=('cpu', 'cuda'), default='cuda')
    args = parser.parse_args()
    phase = args.phase+('-'+args.device if args.phase in ('before', 'after', 'skill') else '')
    out = BASE/(phase+'-r2'); out.mkdir(parents=True, exist_ok=False)
    (out/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    code = {p.name: sha(p) for p in (INSTALLED/'site/ai_ad_editor').glob('*.py')}
    assert len(code) == 206 and code == {p.name: sha(p) for p in (ROOT/'product/src/ai_ad_editor').glob('*.py')}
    calls = []
    report = dict(status='running', phase=args.phase, device=args.device, started_at_utc=datetime.now(timezone.utc).isoformat(),
        cli_version='0.1.15', native_windows=True, virtualization=False, browser_ui=False, new_renders=0,
        human_semantic_acceptance=False, independent_agent_benchmark=False)
    save(out/'verification.json', report)
    def cli(name, arguments, *, installation=INSTALLED, skill=False, ok=True, envelope=True):
        start = time.monotonic()
        command = (['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
            'C:/Users/carzy/.codex/skills/agent-ffmpeg-local-editor/scripts/run.ps1'] if skill else prefix(installation))
        command += list(arguments); command = list(map(str, command))
        process = subprocess.run(command, cwd=ROOT, capture_output=True, timeout=1200, creationflags=subprocess.CREATE_NO_WINDOW)
        stdout, stderr = out/(name+'.stdout.json'), out/(name+'.stderr.txt')
        stdout.write_bytes(process.stdout); stderr.write_bytes(process.stderr)
        value = json.loads(process.stdout.decode('utf-8-sig'))
        calls.append(dict(id=name, argv=command, exit_code=process.returncode, elapsed_seconds=time.monotonic()-start,
            stdout_sha256=sha(stdout), stderr_sha256=sha(stderr)))
        save(out/'calls.json', calls)
        assert bool(process.returncode == 0 and (value.get('ok') if envelope else True)) == ok, value
        print(json.dumps(dict(id=name, code=process.returncode, elapsed_seconds=calls[-1]['elapsed_seconds'])), flush=True)
        return value
    try:
        project, isolated = WORK/'project', WORK/'isolated-native/installed'
        if args.phase == 'setup':
            WORK.mkdir(parents=True, exist_ok=False)
            for name in ('queries.json', 'labels.json'):
                (WORK/name).write_bytes((PREVIOUS/name).read_bytes())
            assert len(load(WORK/'queries.json')['queries']) == 80
            source_zip = PREVIOUS/'second.aevpkg.zip'
            original_hash = sha(source_zip)
            cli('import', ['convert', 'import', '--input', source_zip, '--output', project])
            baseline = original_inventory(project)
            save(WORK/'original-inventory.json', baseline)
            # Install the same verified bundle into an owned, disposable old
            # location. Never rename the user's previous shared installations.
            installation = load(BASE/'installation-r3/verification.json')
            bundle = ROOT/'local/agent-ffmpeg/v0.1.0-alpha.4-local.13/unpacked-r3'
            command = [PYTHON, '-I', '-B', '-u', '-X', 'utf8', bundle/'install.py', '--bundle', bundle,
                '--target', isolated, '--manifest-sha256', installation['manifest_sha256'], '--timeout-seconds', '600']
            process = subprocess.run(list(map(str, command)), cwd=ROOT, capture_output=True, timeout=900, creationflags=subprocess.CREATE_NO_WINDOW)
            (out/'isolated-install.stdout.json').write_bytes(process.stdout); (out/'isolated-install.stderr.txt').write_bytes(process.stderr)
            assert process.returncode == 0 and load(out/'isolated-install.stdout.json')['ok']
            assert code == {p.name: sha(p) for p in (isolated/'site/ai_ad_editor').glob('*.py')}
            first = cli('first-relocation', ['project', 'upgrade-semantic', '--project', project, '--adapter-id', 'siglip2',
                '--new-adapter-id', 'isolated15', '--id-prefix', 'source15'], installation=isolated)
            assert first['data']['model_forward_calls'] == 0
            assert_preserved(project, baseline)
            save(WORK/'first-upgrade.json', first['data'])
            assert sha(source_zip) == original_hash
            report.update(first_upgrade_zero_forwards=True, source_package_unchanged=True,
                old_19_implementation_files_identical=first['data']['adapter']['runtime_upgrade']['implementation_files'] == 19,
                source_package_sha256=original_hash, queries_sha256=sha(WORK/'queries.json'), labels_sha256=sha(WORK/'labels.json'))
        elif args.phase in ('before', 'after', 'skill'):
            first = load(WORK/'first-upgrade.json')
            target = first if args.phase == 'before' else load(WORK/'current-upgrade.json')
            current = project if args.phase != 'skill' else WORK/'restored'
            if args.phase == 'skill':
                runtime = load(ROOT/'local/agent-ffmpeg/runtime.json')
                assert runtime['release'] == 'v0.1.0-alpha.4-local.13'
                assert Path(runtime['installed_directory']).resolve() == INSTALLED.resolve()
            index_id = target['index_mappings'][0]['target']
            reg = load(current/'project.json')['extensions']['local_semantic']
            calibration = next(row['calibration_id'] for row in reg['calibrations'] if row['index_id'] == index_id and row['device'] == args.device)
            before = original_inventory(current)
            response = cli('query80', ['semantic', 'search', '--project', current, '--queries-file', WORK/'queries.json',
                '--index-id', index_id, '--calibration-id', calibration, '--kind', 'image', '--device', args.device, '--limit', '3'],
                installation=isolated if args.phase == 'before' else INSTALLED, skill=args.phase == 'skill')
            quality = metrics(response, load(WORK/'labels.json'))
            errors = {row['id'] for row in quality['queries'] if not (row['top1_correct'] if row['expected_asset_ids'] else row['rejected'])}
            assert errors == {'q14', 'hout00zh', 'hout08zh'}, errors
            prior = (load(ROOT/('docs/validation/evidence/semantic-control-20261025-r1/installed-r1/after-'+args.device+'/actual-decisions.json'))
                if args.phase == 'before' else load(BASE/('before-'+args.device+'-r2/query80.stdout.json')))
            comparisons = compare(prior, response)
            save(out/'comparison.json', comparisons)
            assert before == original_inventory(current)
            report.update(query_count=80, quality=quality, known_error_ids=sorted(errors), query_payload_unchanged=True,
                project_rights_and_assets_unchanged=True, decisions_and_order_identical=True,
                maximum_score_error=max(row['maximum_score_error'] for row in comparisons), inference=response['data']['inference'],
                old_isolated_installation_unavailable=not isolated.exists() if args.phase != 'before' else False)
        elif args.phase == 'upgrade':
            for device in ('cpu', 'cuda'):
                assert load(BASE/('before-'+device+'-r2/verification.json'))['status'] == 'passed-with-known-quality-errors'
            before = original_inventory(project); save(WORK/'before-current-inventory.json', before)
            offline = WORK/'isolated-installation-offline'
            assert isolated.resolve().is_relative_to(WORK.resolve()) and offline.resolve().is_relative_to(WORK.resolve())
            assert isolated.is_dir() and not offline.exists()
            # All owned installation CLI/worker calls above completed before
            # the finite rename; no shared installation or GPU process is moved.
            isolated.rename(offline)
            assert not isolated.exists()
            first = load(WORK/'first-upgrade.json')
            rejection = cli('old-index-rejected', ['semantic', 'search', '--project', project,
                '--index-id', first['index_mappings'][0]['target'], '--query', 'a cat', '--device', 'cuda', '--dry-run'], ok=False)
            assert rejection['errors'][0]['code'] == 'SEMANTIC_ADAPTER_INTEGRITY_FAILED'
            arguments = ['project', 'upgrade-semantic', '--project', project, '--adapter-id', 'isolated15',
                '--new-adapter-id', 'active15', '--id-prefix', 'current15']
            dry = cli('upgrade-dry', [*arguments, '--dry-run'])
            assert before == original_inventory(project)
            response = cli('upgrade', [*arguments, '--idempotency-key', 'upgrade-current-15'])
            assert response['data']['model_forward_calls'] == dry['data']['model_forward_calls'] == 0
            assert response['data']['adapter']['runtime_upgrade']['implementation_files'] == 19
            assert_preserved(project, before)
            unchanged = original_inventory(project)
            replay = cli('upgrade-replay', [*arguments, '--idempotency-key', 'upgrade-current-15'])
            assert replay['data']['operation_id'] == response['data']['operation_id'] and unchanged == original_inventory(project)
            save(WORK/'current-upgrade.json', response['data'])
            report.update(old_isolated_installation_unavailable=True, old_index_refusal_preserved=True,
                dry_run_unchanged=True, original_records_and_assets_preserved=True, new_model_forwards=0,
                index_count=len(response['data']['index_mappings']), profile_count=len(response['data']['calibration_mappings']),
                idempotent_replay_unchanged=True, original_19_implementation_sha_equal=True)
        elif args.phase == 'roundtrip':
            for device in ('cpu', 'cuda'):
                assert load(BASE/('after-'+device+'-r2/verification.json'))['status'] == 'passed-with-known-quality-errors'
            before = original_inventory(project)
            archive = WORK/'upgraded.aevpkg.zip'
            cli('export', ['convert', 'export', '--project', project, '--target-format', 'package', '--output', archive])
            cli('import', ['convert', 'import', '--input', archive, '--output', WORK/'restored'])
            assert before == original_inventory(WORK/'restored')
            offline = WORK/'project-offline'
            assert project.resolve().is_relative_to(WORK.resolve()) and offline.resolve().is_relative_to(WORK.resolve()) and not offline.exists()
            project.rename(offline)
            cli('validate', ['validate', '--project', WORK/'restored'])
            report.update(all_asset_bytes_and_semantic_metadata_identical=True, original_project_unavailable=True,
                package_sha256=sha(archive), package_bytes=archive.stat().st_size, new_model_forwards=0)
        assert code == {p.name: sha(p) for p in (INSTALLED/'site/ai_ad_editor').glob('*.py')}
        report.update(status='passed-with-known-quality-errors' if args.phase in ('before', 'after', 'skill') else 'passed',
            calls=len(calls), product_files=206, installed_and_source_equal=True, finished_at_utc=datetime.now(timezone.utc).isoformat())
        save(out/'verification.json', report)
        print(json.dumps({key: value for key, value in report.items() if key not in ('quality', 'inference')}, ensure_ascii=False))
    except BaseException as exc:
        report.update(status='failed', error=repr(exc)); save(out/'verification.json', report); raise


if __name__ == '__main__':
    main()
