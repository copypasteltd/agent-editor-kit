"""Exercise actual installed refusals, cancellation and calibration quality failure."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'docs/validation/evidence/semantic-decision-20261025-r1'


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', required=True)
    parser.add_argument('--installed', type=Path, required=True)
    parser.add_argument('--project', type=Path, required=True)
    args = parser.parse_args()
    assert args.run.replace('-', '').isalnum()
    project = args.project.resolve(strict=True)
    installed = args.installed.resolve(strict=True)
    assert project.is_relative_to(ROOT / 'workspace')
    output = BASE / ('controls-' + args.run)
    output.mkdir(exist_ok=False)
    (output / 'executed-generator.py').write_bytes(Path(__file__).read_bytes())

    def save(name, data):
        (output / name).write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n',
                                 encoding='utf-8', newline='\n')

    prefix = ['C:/Python313/python.exe', '-I', '-S', '-B', '-u', '-X', 'utf8', str(installed / 'run.py')]
    paths = [project / 'project.json', project / 'rights-ledger.json']
    paths.extend(sorted((project / 'assets/semantic-calibration').rglob('*.json')))
    before = {str(path): sha(path) for path in paths}
    source_before = {p.name: sha(p) for p in (installed / 'site/ai_ad_editor').glob('*.py')}
    calls = []

    def cli(name, arguments, error=None, planned=False):
        jobs_before = set((project / 'cache/semantic-jobs').glob('job_*'))
        command = [*prefix, *map(str, arguments)]
        result = subprocess.run(command, cwd=ROOT, capture_output=True, timeout=900,
                                creationflags=subprocess.CREATE_NO_WINDOW)
        stdout, stderr = output / (name + '.stdout.json'), output / (name + '.stderr.txt')
        stdout.write_bytes(result.stdout)
        stderr.write_bytes(result.stderr)
        value = json.loads(result.stdout.decode('utf-8-sig'))
        created = set((project / 'cache/semantic-jobs').glob('job_*')) - jobs_before
        workers = []
        for job in sorted(created):
            for path in sorted(job.rglob('response.json')):
                response = json.loads(path.read_bytes())
                workers.append(dict(path=str(path), sha256=sha(path), device=response.get('device'),
                    status=response.get('status'), model_forward_calls=response.get('model_forward_calls')))
        calls.append(dict(id=name, argv=command, exit_code=result.returncode, expected_error=error,
            actual_errors=value.get('errors'), status=value.get('status'), workers=workers,
            stdout_sha256=sha(stdout), stderr_sha256=sha(stderr)))
        save('calls.json', calls)
        if error:
            assert result.returncode != 0 and not value['ok'] and value['errors'][0]['code'] == error, value
        else:
            assert result.returncode == 0 and value['ok'], value
            assert value['status'] == ('planned' if planned else 'succeeded'), value
        assert before == {str(path): sha(path) for path in paths}, name
        print(json.dumps(dict(id=name, exit_code=result.returncode, expected_error=error,
                              workers=len(workers))), flush=True)
        return value

    query = ['semantic', 'search', '--project', project, '--index-id', 'images-v1',
             '--query', 'a cat', '--kind', 'image', '--calibration-id', 'accept-cuda']
    report = dict(status='running', started_at_utc=datetime.now(timezone.utc).isoformat(),
                  installed=True, native_windows=True, virtualization=False,
                  deliberate_wrong_labels_are_fault_injection_not_quality_measurement=True)
    try:
        cli('profile-list', ['semantic', 'calibration-list', '--project', project])
        planned = cli('dry-run', [*query, '--device', 'cuda', '--dry-run'], planned=True)
        assert planned['data']['calibration_verified'] and planned['data']['model_forward_calls'] == 0
        cli('raw-profile-refusal', [*query, '--query-mode', 'raw'], error='ARGUMENT_INVALID')
        ambiguous = [*query]
        ambiguous[ambiguous.index('a cat')] = 'not only a cat'
        cli('ambiguous-scope-refusal', ambiguous, error='SEMANTIC_QUERY_SCOPE_REQUIRES_REVIEW')
        wrong_kind = [*query]
        wrong_kind[wrong_kind.index('image')] = 'video'
        cli('kind-refusal', wrong_kind, error='SEMANTIC_CALIBRATION_INVALID')
        marker = output / 'cancel.marker'
        marker.write_text('explicit pre-cancel control', encoding='utf-8')
        cli('pre-cancel', [*query, '--cancel-file', marker], error='CANCELLED')
        automatic = cli('auto-profile', [*query, '--device', 'auto'])
        assert automatic['data']['inference']['response']['device'] == 'cuda'
        assert automatic['data']['results'][0]['decision'] == 'calibrated_match'
        cli('device-refusal', [*query, '--device', 'cpu'], error='SEMANTIC_CALIBRATION_DEVICE_MISMATCH')
        truth = json.loads((BASE / 'frozen/calibration.json').read_bytes())
        truth['scope'] = 'Deliberate incorrect-positive-label fault injection; not a quality dataset.'
        for row in truth['queries']:
            if row['expected_asset_ids']:
                row['expected_asset_ids'] = ['asset_j3' if 'asset_j3' not in row['expected_asset_ids'] else 'asset_a7']
        source = output / 'deliberate-wrong-labels.json'
        source.write_text(json.dumps(truth, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
        failed = cli('quality-refusal', ['semantic', 'calibrate', '--project', project,
            '--index-id', 'images-v1', '--calibration-id', 'quality-failure-control',
            '--kind', 'image', '--input', source, '--device', 'cuda'],
            error='SEMANTIC_CALIBRATION_QUALITY_FAILED')
        assert 'quality-failure-control' not in (project / 'project.json').read_text('utf-8')
        assert source_before == {p.name: sha(p) for p in (installed / 'site/ai_ad_editor').glob('*.py')}
        report.update(status='passed', calls=len(calls), project_rights_and_existing_profiles_unchanged=True,
            no_failed_profile_registered=True, installed_bytes_unchanged=True, new_renders=0,
            observed_worker_model_forwards=sum(w['model_forward_calls'] or 0 for c in calls for w in c['workers']),
            finished_at_utc=datetime.now(timezone.utc).isoformat())
        save('verification.json', report)
        print(json.dumps(report), flush=True)
    except BaseException as exc:
        report.update(status='failed', error=repr(exc), calls=len(calls))
        save('verification.json', report)
        raise


if __name__ == '__main__':
    main()
