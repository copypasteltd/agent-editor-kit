"""Reproduce recovery integrity defects using disposable native E-drive projects."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import traceback

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'docs/validation/evidence/music-loading-20261030-r1'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run', required=True)
    args = parser.parse_args()
    assert args.run.isalnum() and sys.dont_write_bytecode
    proof = BASE / ('recovery-integrity-' + args.run)
    proof.mkdir()
    (proof / 'executed-runner.py').write_bytes(Path(__file__).read_bytes())
    work = ROOT / ('local/agent-ffmpeg/music65-recovery-integrity-' + args.run)
    work.mkdir()
    sys.path.insert(0, str(ROOT / 'product/src'))
    from ai_ad_editor import VERSION, project
    from ai_ad_editor.errors import AppError
    assert VERSION == '0.1.65'
    package = ROOT / 'product/src/ai_ad_editor'
    pins = {p.relative_to(ROOT).as_posix(): sha(p) for p in package.glob('*.py')}
    assert len(pins) == 288
    report = dict(status='failed', cli_version=VERSION,
        kind='reproduction-not-recovery-acceptance', synthetic_disposable_projects=True,
        product_code_changed=False, neural_inference=False, fsync_disabled=False,
        full_product_goal_closed=False, cases=[])
    try:
        root, _ = project.create_project(work / 'same-size-corruption', name='Disposable corrupted backup')
        before = {p.relative_to(root).as_posix(): sha(p) for p in project._transaction_metadata_files(root)}
        with project.project_write_lock(root):
            journal = project.prepare_project_transaction(root, command='validation.corrupted-backup')
            item = next(row for row in journal['files'] if row['path'] == 'project.json')
            backup = root / item['backup']
            original = backup.read_bytes()
            damaged = bytes([original[0] ^ 1]) + original[1:]
            assert len(damaged) == item['size'] and hashlib.sha256(damaged).hexdigest() != item['sha256']
            backup.write_bytes(damaged)
            recovery = project.recover_pending_transaction(root)
        after = {p.relative_to(root).as_posix(): sha(p) for p in project._transaction_metadata_files(root)}
        assert recovery['status'] == 'recovered' and (root / 'project.json').read_bytes() == damaged
        assert before['project.json'] != after['project.json']
        assert not project.transaction_journal_file(root).exists()
        report['cases'].append(dict(case='same-size-corrupted-backup', reproduced=True,
            recovery_report=recovery, journal_sha256=item['sha256'], corrupted_sha256=sha(root / 'project.json'),
            size_unchanged=True, corrupted_bytes_restored=True, journal_deleted=True,
            expected_future_behavior='Reject the size/SHA mismatch before writing any destination; retain journal and backups.'))

        root, _ = project.create_project(work / 'late-missing-backup', name='Disposable late missing backup')
        baseline = {p.relative_to(root).as_posix(): sha(p) for p in project._transaction_metadata_files(root)}
        with project.project_write_lock(root):
            journal = project.prepare_project_transaction(root, command='validation.late-missing-backup')
            assert len(journal['files']) >= 3
            for index, item in enumerate(journal['files']):
                (root / item['path']).write_bytes(('interrupted synthetic bytes ' + str(index)).encode())
            missing = journal['files'][-1]
            (root / missing['backup']).unlink()
            before = {row['path']: sha(root / row['path']) for row in journal['files']}
            try:
                project.recover_pending_transaction(root)
            except AppError as error:
                assert error.code == 'PROJECT_TRANSACTION_BACKUP_MISSING'
                code = error.code
            else:
                raise AssertionError('Missing backup was unexpectedly accepted')
        after = {row['path']: sha(root / row['path']) for row in journal['files']}
        changed = [name for name in before if before[name] != after[name]]
        assert changed and missing['path'] not in changed
        assert all(after[name] == baseline[name] for name in changed)
        assert project.transaction_journal_file(root).is_file()
        report['cases'].append(dict(case='late-missing-backup', reproduced=True, error_code=code,
            missing_destination=missing['path'], earlier_destinations_changed_before_error=changed,
            before=before, after=after, baseline=baseline, journal_retained=True,
            expected_future_behavior='Preflight all entries and payloads before writing any destination.'))
        assert all(sha(ROOT / name) == pin for name, pin in pins.items())
        report.update(status='reproduced', source_frozen_equal=True, file_hashes=pins,
            recovery_correctness_accepted=False, scope='G33 project metadata crash recovery',
            limitations='Two disposable corrupted-backup cases. No user project, model generation, recovery repair, or performance claim.')
    except BaseException as error:
        report.update(error=repr(error), traceback=traceback.format_exc())
    (proof / 'verification.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps({k:v for k,v in report.items() if k != 'file_hashes'}), flush=True)
    return 0 if report['status'] == 'reproduced' else 1


if __name__ == '__main__':
    raise SystemExit(main())
