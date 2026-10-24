"""Native process-tree lifetime, durable publication and recovery invariants."""
from __future__ import annotations

import contextlib
import ctypes
from ctypes import wintypes
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

import ai_ad_editor
from ai_ad_editor.cli import main
from ai_ad_editor.errors import AppError
from ai_ad_editor.job_workspaces import Workspace, managed_workspace, recover_workspaces
from ai_ad_editor.project import project_transaction, load_project, save_project, prepare_project_transaction
from ai_ad_editor.runtime import configure_local_runtime
from ai_ad_editor.utils import atomic_write_json, run_process, sha256_file


def invoke(*args):
    stream = io.StringIO()
    with contextlib.redirect_stdout(stream):
        code = main(list(map(str, args)))
    return code, json.loads(stream.getvalue())


def wait_file(path, timeout=15):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if path.is_file():
            try:
                return json.loads(path.read_bytes())
            except (ValueError, OSError):
                pass
        time.sleep(.02)
    raise AssertionError('Owned process did not create its handshake: ' + str(path))


def process_is_alive(pid):
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.OpenProcess.argtypes, kernel.OpenProcess.restype = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD], wintypes.HANDLE
    kernel.WaitForSingleObject.argtypes, kernel.WaitForSingleObject.restype = [wintypes.HANDLE, wintypes.DWORD], wintypes.DWORD
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel.OpenProcess(0x00100000, False, pid)
    if not handle:
        return False
    try:
        return kernel.WaitForSingleObject(handle, 0) == 258
    finally:
        kernel.CloseHandle(handle)


@unittest.skipUnless(os.name == 'nt', 'Windows native lifetime contracts')
class NativeProcessTreeTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=configure_local_runtime()['temp'])
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.child_script = self.root / 'child.py'
        self.child_script.write_text('''import json,os,subprocess,sys,time
from pathlib import Path
child=subprocess.Popen([sys.executable,'-E','-B','-c','import time;time.sleep(45)'])
Path(sys.argv[1]).write_text(json.dumps(dict(child=os.getpid(),grandchild=child.pid)))
if sys.argv[2]=='normal':
 print('normal-exit',flush=True)
else: time.sleep(45)
''', encoding='utf8')
        self.handshake = self.root / 'pids.json'

    def tree_command(self, mode='wait'):
        return [sys.executable, '-E', '-B', '-u', str(self.child_script), str(self.handshake), mode]

    def assert_tree_exited(self, pids):
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and any(process_is_alive(pid) for pid in pids.values()):
            time.sleep(.02)
        self.assertFalse(any(process_is_alive(pid) for pid in pids.values()), pids)

    def test_normal_child_exit_reaps_descendants_holding_pipes(self):
        started = time.monotonic()
        result = run_process(self.tree_command('normal'), timeout=10)
        self.assertEqual(result.returncode, 0)
        self.assertIn('normal-exit', result.stdout)
        self.assertLess(time.monotonic() - started, 10)
        self.assert_tree_exited(wait_file(self.handshake))

    def test_timeout_ends_both_child_and_grandchild(self):
        with self.assertRaises(AppError) as error:
            run_process(self.tree_command(), timeout=1)
        self.assertEqual(error.exception.code, 'PROCESS_TIMEOUT')
        self.assert_tree_exited(wait_file(self.handshake))

    def test_cancel_ends_both_child_and_grandchild(self):
        marker = self.root / 'cancel'
        def cancel():
            wait_file(self.handshake)
            marker.write_bytes(b'cancel')
        thread = threading.Thread(target=cancel)
        thread.start()
        try:
            with self.assertRaises(AppError) as error:
                run_process(self.tree_command(), timeout=10, cancel_file=marker)
            self.assertEqual(error.exception.code, 'CANCELLED')
        finally:
            thread.join(timeout=10)
        self.assert_tree_exited(wait_file(self.handshake))

    def test_hard_owner_exit_ends_its_tree_without_taskkill(self):
        package = str(Path(ai_ad_editor.__file__).resolve().parent.parent)
        owner_script = self.root / 'owner.py'
        owner_script.write_text('import sys\nsys.path.insert(0,sys.argv[1])\nfrom ai_ad_editor.utils import run_process\nrun_process(sys.argv[2:],timeout=40)\n', encoding='utf8')
        owner = subprocess.Popen([sys.executable, '-E', '-B', str(owner_script), package, *self.tree_command()],
            stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=subprocess.CREATE_NO_WINDOW)
        try:
            pids = wait_file(self.handshake)
            self.assertTrue(all(process_is_alive(pid) for pid in pids.values()))
            owner.kill()  # Only this fixture's owner; no /T, PID enumeration or unrelated process stop.
            owner.communicate(timeout=10)
            self.assert_tree_exited(pids)
        finally:
            if owner.poll() is None:
                owner.kill()
                owner.communicate(timeout=10)

    def test_assignment_failure_never_executes_application_code(self):
        marker = self.root / 'executed'
        command = [sys.executable, '-E', '-B', '-c', 'from pathlib import Path;import sys;Path(sys.argv[1]).write_text("bad")', str(marker)]
        with patch('ai_ad_editor.native_process_job.NativeProcessJob.attach_and_resume', side_effect=OSError('injected assignment failure')):
            with self.assertRaises(AppError) as error:
                run_process(command, timeout=10)
        self.assertEqual(error.exception.code, 'PROCESS_START_FAILED')
        self.assertFalse(marker.exists())


class WorkspaceRecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=configure_local_runtime()['temp'])
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / '中文 工程'
        self.assertEqual(invoke('project', 'init', self.root)[0], 0)

    def publication(self):
        workspace = Workspace(self.root, 'four-stem-separation')
        self.addCleanup(workspace.lease.close)
        stage = workspace.path / 'stage.wav'
        stage.write_bytes(b'owned publication fixture')
        destination = self.root / 'assets/derived/owned.wav'
        workspace.publish(stage, destination)
        return workspace, destination

    def test_live_lease_is_preserved_and_dry_run_does_not_write(self):
        workspace, destination = self.publication()
        # Windows byte locks intentionally deny reads of the held lease byte.
        contents = lambda: {p.relative_to(self.root).as_posix(): p.read_bytes()
            for p in self.root.rglob('*') if p.is_file() and p.name != 'owner.lock'}
        before = contents()
        result = recover_workspaces(self.root, dry_run=True)
        self.assertEqual(result['jobs'][0]['status'], 'active_or_locked_preserved')
        self.assertEqual(before, contents())
        self.assertEqual((workspace.path / 'owner.lock').stat().st_size, 1)
        self.assertTrue(destination.exists())

    def test_stale_publication_is_planned_then_removed_and_repeat_is_clean(self):
        workspace, destination = self.publication()
        workspace.lease.close()
        planned = invoke('project', 'recover', '--project', self.root, '--cleanup-jobs', '--dry-run')
        self.assertEqual(planned[0], 0, planned)
        self.assertEqual(planned[1]['data']['job_recovery']['jobs'][0]['status'], 'cleanup_planned')
        self.assertTrue(destination.exists())
        result = invoke('project', 'recover', '--project', self.root, '--cleanup-jobs')
        self.assertEqual(result[0], 0, result)
        self.assertEqual(result[1]['data']['job_recovery']['cleaned'], 1)
        self.assertFalse(destination.exists())
        self.assertFalse(workspace.path.exists())
        self.assertEqual(recover_workspaces(self.root)['jobs'], [])

    def test_transaction_retains_lease_until_metadata_commits(self):
        with project_transaction(self.root, command='test.commit'):
            with managed_workspace(self.root, 'four-stem-separation') as workspace:
                stage = workspace.path / 'ready.wav'
                stage.write_bytes(b'committed media')
                destination = self.root / 'assets/derived/commit.wav'
                workspace.publish(stage, destination)
            self.assertTrue(workspace.path.is_dir())
            self.assertEqual(recover_workspaces(self.root)['jobs'][0]['status'], 'active_or_locked_preserved')
            _, project = load_project(self.root)
            project['assets'].append(dict(id='committed', kind='audio', uri='assets/derived/commit.wav', sha256='sha256:' + sha256_file(destination)))
            save_project(self.root, project)
        self.assertFalse(workspace.path.exists())
        self.assertEqual(destination.read_bytes(), b'committed media')

    def test_metadata_rollback_removes_only_owned_publications(self):
        original = (self.root / 'project.json').read_bytes()
        source = self.root / 'assets/source.wav'
        source.write_bytes(b'preserve source')
        with self.assertRaisesRegex(RuntimeError, 'rollback'):
            with project_transaction(self.root, command='test.rollback'):
                with managed_workspace(self.root, 'four-stem-separation') as workspace:
                    stage = workspace.path / 'pending.wav'
                    stage.write_bytes(b'pending')
                    destination = self.root / 'assets/derived/pending.wav'
                    workspace.publish(stage, destination)
                    (self.root / 'project.json').write_bytes(b'incomplete json')
                    raise RuntimeError('rollback')
        self.assertEqual((self.root / 'project.json').read_bytes(), original)
        self.assertFalse(workspace.path.exists())
        self.assertFalse(destination.exists())
        self.assertEqual(source.read_bytes(), b'preserve source')

    def test_changed_output_is_preserved(self):
        workspace, destination = self.publication()
        workspace.lease.close()
        destination.write_bytes(b'new user edit')
        result = recover_workspaces(self.root)
        self.assertEqual(result['jobs'][0]['status'], 'changed_output_preserved')
        self.assertEqual(destination.read_bytes(), b'new user edit')
        self.assertTrue(workspace.path.exists())

    def test_replaced_output_with_identical_bytes_is_preserved(self):
        workspace, destination = self.publication()
        workspace.lease.close()
        replacement = destination.with_suffix('.replacement')
        replacement.write_bytes(destination.read_bytes())
        os.replace(replacement, destination)
        result = recover_workspaces(self.root)
        self.assertEqual(result['jobs'][0]['status'], 'changed_output_preserved')
        self.assertTrue(destination.exists())

    def test_referenced_output_survives_cleanup(self):
        workspace, destination = self.publication()
        workspace.lease.close()
        _, project = load_project(self.root)
        project['assets'].append(dict(id='retained', kind='audio', uri='assets/derived/owned.wav'))
        save_project(self.root, project)
        result = recover_workspaces(self.root)
        self.assertEqual(result['cleaned'], 1)
        self.assertTrue(destination.exists())
        self.assertFalse(workspace.path.exists())

    def test_publication_does_not_replace_a_competing_file(self):
        workspace = Workspace(self.root, 'four-stem-separation')
        self.addCleanup(workspace.lease.close)
        stage = workspace.path / 'new.wav'
        stage.write_bytes(b'new')
        target = self.root / 'assets/derived/existing.wav'
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b'existing')
        with self.assertRaises(FileExistsError):
            workspace.publish(stage, target)
        self.assertEqual(target.read_bytes(), b'existing')

    def test_forged_paths_and_unknown_directories_are_preserved(self):
        workspace, destination = self.publication()
        workspace.lease.close()
        source = self.root / 'assets/source.wav'
        source.write_bytes(b'protected original')
        record = json.loads((workspace.path / 'job.json').read_bytes())
        record['outputs'][0]['path'] = 'assets/derived/../source.wav'
        atomic_write_json(workspace.path / 'job.json', record)
        unknown = self.root / 'cache/managed-jobs/unowned'
        unknown.mkdir()
        (unknown / 'keep').write_bytes(b'unknown')
        result = recover_workspaces(self.root)
        self.assertEqual(result['cleaned'], 0)
        self.assertTrue(all(row['status'] == 'unverified_or_blocked_preserved' for row in result['jobs']))
        self.assertEqual(source.read_bytes(), b'protected original')
        self.assertTrue(destination.exists())

    @unittest.skipUnless(os.name == 'nt', 'Native directory junction contract')
    def test_junction_inside_job_cannot_reach_external_files(self):
        workspace = Workspace(self.root, 'four-stem-separation')
        self.addCleanup(workspace.lease.close)
        workspace.lease.close()
        outside = Path(self.temp.name) / 'external'
        outside.mkdir()
        (outside / 'keep').write_bytes(b'external')
        junction = workspace.path / 'junction'
        result = subprocess.run(['cmd.exe', '/c', 'mklink', '/J', str(junction), str(outside)], capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        try:
            result = recover_workspaces(self.root)
            self.assertEqual(result['cleaned'], 0)
            self.assertEqual((outside / 'keep').read_bytes(), b'external')
        finally:
            self.assertTrue(junction.absolute().is_relative_to(self.root.absolute()))
            junction.rmdir()  # Remove only the verified owned junction, never its target.

    def test_unmanaged_historical_cache_is_preserved(self):
        legacy = self.root / 'cache/four-stem-separation/hdemucs-legacy'
        legacy.mkdir(parents=True)
        (legacy / 'input.f32').write_bytes(b'legacy evidence')
        result = recover_workspaces(self.root)
        self.assertEqual(result['legacy_unmanaged'], 'preserved')
        self.assertEqual((legacy / 'input.f32').read_bytes(), b'legacy evidence')

    def test_recover_restores_missing_or_corrupt_project_before_cache_cleanup(self):
        original = (self.root / 'project.json').read_bytes()
        for corruption in ('missing', 'invalid-json'):
            workspace, destination = self.publication()
            workspace.lease.close()
            prepare_project_transaction(self.root, command='test.interrupted-metadata')
            if corruption == 'missing':
                (self.root / 'project.json').unlink()
            else:
                (self.root / 'project.json').write_bytes(b'{incomplete')
            code, response = invoke('project', 'recover', '--project', self.root, '--cleanup-jobs')
            self.assertEqual(code, 0, response)
            self.assertTrue(response['data']['recovery']['recovered'])
            self.assertEqual((self.root / 'project.json').read_bytes(), original)
            self.assertEqual(response['data']['job_recovery']['cleaned'], 1)
            self.assertFalse(destination.exists())


if __name__ == '__main__':
    unittest.main()
