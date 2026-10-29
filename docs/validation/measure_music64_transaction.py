"""Measure real metadata flushes, preserving the current recovery guarantees."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import traceback
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run', required=True)
    parser.add_argument('--records', type=int, default=8)
    args = parser.parse_args()
    assert args.run.isalnum() and 2 <= args.records <= 32 and sys.dont_write_bytecode
    proof = ROOT / ('docs/validation/evidence/music-generation-20261030-r1/transaction-latency-' + args.run)
    proof.mkdir()
    (proof / 'executed-runner.py').write_bytes(Path(__file__).read_bytes())
    work = ROOT / ('local/agent-ffmpeg/music64-transaction-latency-' + args.run)
    work.mkdir()
    sys.path.insert(0, str(ROOT / 'product/src'))
    from ai_ad_editor import VERSION, project
    assert VERSION == '0.1.64'
    package = ROOT / 'product/src/ai_ad_editor'
    pins = {p.name:sha(p) for p in [package / name for name in ('__init__.py', 'project.py', 'utils.py', 'errors.py')]}
    root, unused_project = project.create_project(work / 'project', name='Synthetic transaction flush measurement')
    for index in range(args.records):
        target = root / 'operations' / ('latency-fixture-' + str(index) + '.json')
        target.write_text(json.dumps(dict(purpose='synthetic metadata latency probe', index=index, text='x' * 4096)) + '\n',
                          encoding='utf-8', newline='\n')
    before = {p.relative_to(root).as_posix():sha(p) for p in project._transaction_metadata_files(root)}
    real_fsync = os.fsync
    flushes, phase = [], 'prepare'

    def measured_fsync(descriptor):
        began = time.monotonic()
        real_fsync(descriptor)
        flushes.append(dict(phase=phase, seconds=time.monotonic() - began, bytes=os.fstat(descriptor).st_size))

    report = dict(status='failed', cli_version=VERSION, actual_neural_inference=False,
        synthetic_metadata_fixture=True, fsync_disabled=False, product_code_changed=False,
        timing_target_accepted=False, full_431_group_accepted=False)
    try:
        with project.project_write_lock(root), patch('os.fsync', side_effect=measured_fsync):
            began = time.monotonic()
            journal = project.prepare_project_transaction(root, command='validation.measure-metadata-flush')
            prepare_elapsed = time.monotonic() - began
            # Actual corruption is confined to the disposable diagnostic project.
            (root / 'project.json').write_bytes(b'{interrupted')
            (root / 'rights-ledger.json').write_bytes(b'{incomplete')
            added = root / 'operations/added-after-snapshot.json'
            added.write_bytes(b'{"partial":true}')
            phase = 'recover'
            began = time.monotonic()
            recovery = project.recover_pending_transaction(root)
            recovery_elapsed = time.monotonic() - began
        after = {p.relative_to(root).as_posix():sha(p) for p in project._transaction_metadata_files(root)}
        assert before == after and not added.exists() and not project.transaction_journal_file(root).exists()
        assert all(sha(package / name) == value for name,value in pins.items())
        report.update(status='passed', metadata_files=len(before), metadata_bytes=sum((root / p).stat().st_size for p in before),
            prepare_seconds=prepare_elapsed, recover_seconds=recovery_elapsed,
            prepare_fsync_seconds=sum(v['seconds'] for v in flushes if v['phase'] == 'prepare'),
            prepare_fsync_calls=sum(v['phase'] == 'prepare' for v in flushes),
            recover_fsync_seconds=sum(v['seconds'] for v in flushes if v['phase'] == 'recover'),
            recover_fsync_calls=sum(v['phase'] == 'recover' for v in flushes),
            fsync_events=flushes, backup_transaction_version=journal['transaction_version'],
            recovery_status=recovery['status'], metadata_restored_exactly=True,
            metadata_before=before, metadata_after=after, implementation_sha256=pins,
            project=str(root), limitations='One native E-drive synthetic metadata workload under concurrent activity; no broad hardware or CLI performance guarantee.')
    except BaseException as exc:
        report.update(error=repr(exc), traceback=traceback.format_exc(), fsync_events=flushes)
    (proof / 'verification.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps({k:v for k,v in report.items() if k not in ('metadata_before','metadata_after','fsync_events')}), flush=True)
    return 0 if report['status'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
