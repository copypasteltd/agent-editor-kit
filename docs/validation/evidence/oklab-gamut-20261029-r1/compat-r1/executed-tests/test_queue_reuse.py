from __future__ import annotations

import contextlib
import copy
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from ai_ad_editor import queue_reuse as reuse
from ai_ad_editor import cli
from ai_ad_editor.errors import AppError
from ai_ad_editor.media import probe_media
from ai_ad_editor.project import create_project, save_project, ledger_file
from ai_ad_editor.utils import atomic_write_json, load_json, sha256_file


def invoke(*args):
    stream = io.StringIO()
    with contextlib.redirect_stdout(stream):
        code = cli.main(list(args))
    return code, json.loads(stream.getvalue())


class SnapshotFixture:
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='queue-reuse-snapshot-')
        self.addCleanup(self.temp.cleanup)
        self.root, self.project = create_project(Path(self.temp.name) / 'project')
        self.sequence = self.project['sequences'][0]
        self.source = self.root / 'assets/source.png'
        self.source.write_bytes(b'fixture-raw-source-a')
        self.project['assets'] = [{'id': 'a', 'uri': 'assets/source.png', 'kind': 'image',
                                   'sha256': 'sha256:declared-old', 'probe': {'format': 'png_pipe'}}]
        self.runtime_file = self.root / 'runtime.fixture'
        self.runtime_file.write_bytes(b'implementation-a')
        self.addCleanup(patch.stopall)
        patch.object(reuse, '_runtime_paths', return_value={self.runtime_file}).start()
        patch.object(reuse, '_probe_input_format', return_value='png_pipe').start()
        self.persist()
        self.session = reuse.ReuseSession(self.root)

    def persist(self):
        save_project(self.root, self.project)

    def snapshot(self, settings=None):
        return self.session.snapshot(self.project, self.sequence, settings or self.project['settings'])


class SnapshotTests(SnapshotFixture, unittest.TestCase):
    def test_deep_canonical_preserves_nested_differences_and_array_order(self):
        self.assertEqual(reuse.canonical({'a': {'y': 2, 'x': 1}}), reuse.canonical({'a': {'x': 1, 'y': 2}}))
        self.assertNotEqual(reuse.canonical({'a': {'x': 1}}), reuse.canonical({'a': {'x': 2}}))
        self.assertNotEqual(reuse.canonical([1, 2]), reuse.canonical([2, 1]))
        with self.assertRaisesRegex(AppError, '有限值'):
            reuse.canonical({'a': float('nan')})

    def test_only_known_output_bookkeeping_is_excluded_without_mutation(self):
        original = copy.deepcopy(self.project)
        before = self.snapshot()
        self.project['outputs'].append({'path': 'renders/previous.mp4'})
        self.project['provenance']['change_log'].append({'command': 'queue.run'})
        self.persist()
        self.assertEqual(before, self.snapshot())
        self.assertEqual(original['settings'], self.project['settings'])
        self.project['project']['name'] += '-authored-change'
        self.persist()
        self.assertNotEqual(before, self.snapshot())

    def test_normalized_defaults_and_output_labels_share_signature(self):
        from ai_ad_editor.render_queue import normalize_job
        args = type('Args', (), {'progress': 'none'})()
        first = normalize_job(self.root, {'job_id': 'a', 'label': 'first'})
        normal, _ = cli._render_settings_for_args(self.project, cli._queue_job_args(self.root, first, args))
        video = normal['output']['video']
        second = normalize_job(self.root, {'job_id': 'b', 'output': 'renders/different-name.mp4',
            'label': 'second', 'video_codec': video['codec'], 'crf': video['crf'], 'pixel_format': video['pixel_format']})
        explicit, _ = cli._render_settings_for_args(self.project, cli._queue_job_args(self.root, second, args))
        self.assertEqual(self.snapshot(normal), self.snapshot(explicit))
        explicit['acceleration'] = {'encode': 'off', 'decode': 'off'}
        explicit['sequence_sampling'] = {'method': 'bilinear'}
        self.assertEqual(self.snapshot(normal), self.snapshot(explicit))
        explicit['timebase']['display_fps'] = {'num': 24000, 'den': 1001}
        self.assertNotEqual(self.snapshot(normal), self.snapshot(explicit))

    def test_same_size_restored_mtime_source_change_invalidates(self):
        before, stamp = self.snapshot(), self.source.stat()
        self.source.write_bytes(b'fixture-raw-source-b')
        os.utime(self.source, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
        self.assertEqual(stamp.st_size, self.source.stat().st_size)
        self.assertNotEqual(before['signature'], self.snapshot()['signature'])

    def test_rights_ledger_bytes_invalidate(self):
        before = self.snapshot()
        ledger = ledger_file(self.root)
        ledger.write_bytes(ledger.read_bytes() + b' ')
        self.assertNotEqual(before['signature'], self.snapshot()['signature'])

    def test_font_and_mask_files_are_actual_dependencies(self):
        font = self.root / 'assets/font.ttf'
        mask = self.root / 'assets/mask.mkv'
        font.write_bytes(b'font-a')
        mask.write_bytes(b'mask-a')
        self.project['assets'].append({'id': 'mask', 'uri': 'assets/mask.mkv', 'kind': 'video', 'probe': {'format': 'matroska,webm'}})
        self.sequence['tracks'][0]['clips'] = [{'id': 'c', 'subtitle': {'text': 'caption', 'style': {'fontfile': 'assets/font.ttf'}}}]
        self.persist()
        first = self.snapshot()
        paths = {row['path'] for row in first['dependencies']}
        self.assertIn(str(font.resolve()), paths)
        self.assertIn(str(mask.resolve()), paths)
        font.write_bytes(b'font-b')
        self.assertNotEqual(first['signature'], self.snapshot()['signature'])

    def test_direct_and_registered_luts_bind_actual_bytes(self):
        lut = self.root / 'assets/look.cube'
        lut.write_bytes(b'lut-a')
        for effect in ({'type': 'lut3d', 'path': 'assets/look.cube'},
                       {'type': 'lut3d', 'parameters': {'lut_id': 'look'}}):
            with self.subTest(effect=effect):
                atomic_write_json(self.root / 'assets/lut-library.json', {'records': [{'id': 'look', 'uri': 'assets/look.cube'}]})
                self.sequence['tracks'][0]['clips'] = [{'id': 'c', 'effects': [effect]}]
                self.persist()
                first = self.snapshot()
                self.assertIn(str(lut.resolve()), {r['path'] for r in first['dependencies']})
                lut.write_bytes(lut.read_bytes() + b'b')
                self.assertNotEqual(first['signature'], self.snapshot()['signature'])

    def test_missing_actual_file_does_not_use_declared_hash(self):
        self.source.unlink()
        with self.assertRaises(AppError) as caught:
            self.snapshot()
        self.assertEqual(caught.exception.code, 'QUEUE_REUSE_INPUT_UNREADABLE')

    def test_empty_authored_source_is_still_rejected(self):
        self.source.write_bytes(b'')
        with self.assertRaises(AppError) as caught:
            self.snapshot()
        self.assertEqual(caught.exception.code, 'QUEUE_REUSE_INPUT_EMPTY')

    def test_declared_format_cannot_hide_actual_multifile_dependency(self):
        with patch.object(reuse, '_probe_input_format', return_value='hls'):
            with self.assertRaises(AppError) as caught:
                self.snapshot()
        self.assertEqual(caught.exception.code, 'QUEUE_REUSE_UNSUPPORTED')

    def test_runtime_change_stops_session_instead_of_silent_new_key(self):
        self.snapshot()
        self.runtime_file.write_bytes(b'implementation-b')
        with self.assertRaises(AppError) as caught:
            self.snapshot()
        self.assertEqual(caught.exception.code, 'QUEUE_REUSE_RUNTIME_CHANGED')

    def test_out_of_band_author_change_is_rejected(self):
        disk = load_json(self.root / 'project.json')
        disk['settings']['canvas']['width'] += 2
        atomic_write_json(self.root / 'project.json', disk)
        with self.assertRaises(AppError) as caught:
            self.snapshot()
        self.assertEqual(caught.exception.code, 'QUEUE_REUSE_AUTHOR_CHANGED')

    def test_untracked_dynamic_dependencies_are_explicitly_rejected(self):
        original = copy.deepcopy(self.project)
        cases = [
            ('hardware', lambda p: p['settings'].update(acceleration={'encode': 'prefer'})),
            ('stretch', lambda p: p['settings'].update(audio_stretch={'engine': 'external'})),
            ('fallback', lambda p: p['sequences'][0]['tracks'][0].update(clips=[{'subtitle': {'text': 'x'}}])),
            ('external-ass', lambda p: p['sequences'][0]['tracks'][0].update(clips=[{'subtitle': {'asset_uri': 'x.ass'}}])),
            ('binding', lambda p: p['sequences'][0]['tracks'][0].update(clips=[{'tracking_binding': {'report': 'x.json'}}])),
            ('grain', lambda p: p['sequences'][0]['tracks'][0].update(clips=[{'effects': ['film-grain']}])),
            ('playlist', lambda p: p['assets'][0]['probe'].update(format='hls')),
        ]
        for name, mutate in cases:
            with self.subTest(name=name):
                self.project = copy.deepcopy(original)
                self.sequence = self.project['sequences'][0]
                mutate(self.project)
                self.persist()
                with self.assertRaises(AppError) as caught:
                    self.snapshot()
                self.assertEqual(caught.exception.code, 'QUEUE_REUSE_UNSUPPORTED')


class CopyTests(SnapshotFixture, unittest.TestCase):
    """Real encoded input, fixture source manifest; no encoding claim for it."""
    @classmethod
    def setUpClass(cls):
        cls.media_temp = tempfile.TemporaryDirectory(prefix='queue-reuse-media-')
        cls.media = Path(cls.media_temp.name) / 'source.mp4'
        result = subprocess.run(['ffmpeg', '-hide_banner', '-loglevel', 'error', '-y',
            '-f', 'lavfi', '-i', 'testsrc2=s=160x96:r=8:d=1', '-f', 'lavfi', '-i',
            'sine=frequency=440:sample_rate=48000:d=1', '-shortest', '-c:v', 'libx264',
            '-pix_fmt', 'yuv420p', '-c:a', 'aac', str(cls.media)], capture_output=True)
        if result.returncode:
            raise RuntimeError(result.stderr.decode('utf-8', 'replace'))

    @classmethod
    def tearDownClass(cls):
        cls.media_temp.cleanup()

    def setUp(self):
        super().setUp()
        self.project['settings']['canvas'].update(width=160, height=96)
        self.project['settings']['timebase']['display_fps'] = {'num': 8, 'den': 1}
        self.sequence['duration_tick'] = 90000
        self.persist()
        self.leader = self.root / 'renders/leader.mp4'
        shutil.copyfile(self.media, self.leader)
        self.manifest = self.leader.with_suffix('.mp4.manifest.json')
        atomic_write_json(self.manifest, {'sha256': sha256_file(self.leader), 'operation_id': 'render-fixture',
            'output': str(self.leader), 'quality': {'ok': True}, 'command': ['fixture-command-never-claimed-executed']})
        self.result = {'operation_id': 'render-fixture', 'path': str(self.leader), 'manifest': str(self.manifest), 'warnings': []}
        self.before = self.snapshot()
        self.entry = self.session.capture(self.before, self.result, 'leader')
        self.target = self.root / 'renders/target.mp4'

    def clone(self, **kwargs):
        return self.session.clone(self.entry, self.before, self.project, self.sequence,
                                  self.project['settings'], self.target, **kwargs)

    def assert_no_partial(self):
        self.assertFalse(self.target.exists())
        self.assertFalse(self.target.with_suffix('.mp4.manifest.json').exists())
        self.assertFalse(list(self.target.parent.glob('.queue-reuse-*')))

    def test_copy_has_new_provenance_independent_quality_and_no_encode(self):
        result = self.clone()
        self.assertEqual(self.leader.read_bytes(), self.target.read_bytes())
        self.assertNotEqual(result['operation_id'], self.result['operation_id'])
        self.assertTrue(result['quality']['ok'])
        manifest = load_json(Path(result['manifest']))
        self.assertEqual(manifest['command'], [])
        self.assertFalse(manifest['reuse']['encoding_executed'])
        self.assertEqual(manifest['reuse']['source_operation_id'], 'render-fixture')
        self.assertEqual(manifest['output'], str(self.target))
        self.assertNotEqual(os.stat(self.leader).st_ino, os.stat(self.target).st_ino)

    def test_existing_target_is_preserved(self):
        self.target.write_bytes(b'existing-user-output')
        with self.assertRaises(AppError):
            self.clone()
        self.assertEqual(self.target.read_bytes(), b'existing-user-output')

    def test_source_and_manifest_corruption_reject_even_with_original_mtime(self):
        for path in (self.leader, self.manifest):
            with self.subTest(path=path):
                raw, stamp = path.read_bytes(), path.stat()
                path.write_bytes(bytes([raw[0] ^ 1]) + raw[1:])
                os.utime(path, ns=(stamp.st_atime_ns, stamp.st_mtime_ns))
                with self.assertRaises(AppError) as caught:
                    self.clone()
                self.assertEqual(caught.exception.code, 'QUEUE_REUSE_SOURCE_CHANGED')
                self.assert_no_partial()
                path.write_bytes(raw)

    def test_partial_chunk_copy_cancellation_cleans_only_target(self):
        marker = self.root / 'operations/copy.cancel'
        active, polls = False, 0
        original = reuse._cancel
        def progress(*args):
            nonlocal active
            active = True
        def cancel(value):
            nonlocal polls
            if active:
                polls += 1
                if polls == 3:
                    marker.write_text('cancel', encoding='utf-8')
            original(value)
        with patch.object(reuse, 'CHUNK_BYTES', 32), patch.object(reuse, '_cancel', side_effect=cancel):
            with self.assertRaises(AppError) as caught:
                self.clone(marker=marker, progress_callback=progress)
        self.assertEqual(caught.exception.code, 'CANCELLED')
        self.assertGreaterEqual(polls, 3)
        self.assert_no_partial()
        self.assertEqual(sha256_file(self.leader), self.entry['output']['sha256'])

    def test_rename_and_manifest_disk_failure_remove_owned_copy(self):
        for name in ('rename', 'atomic_write_json'):
            with self.subTest(name=name):
                target = reuse.os if name == 'rename' else reuse
                with patch.object(target, name, side_effect=OSError('fixture disk failure')):
                    with self.assertRaises(AppError) as caught:
                        self.clone()
                self.assertEqual(caught.exception.code, 'QUEUE_REUSE_COPY_FAILED')
                self.assert_no_partial()

    def test_input_change_during_independent_check_rejects_copy(self):
        original = reuse.check_output
        def change(*args, **kwargs):
            checked = original(*args, **kwargs)
            self.source.write_bytes(b'fixture-raw-source-b')
            return checked
        with patch.object(reuse, 'check_output', side_effect=change):
            with self.assertRaises(AppError) as caught:
                self.clone()
        self.assertEqual(caught.exception.code, 'QUEUE_REUSE_INPUT_CHANGED')
        self.assert_no_partial()

    def test_derived_cache_change_prevents_stale_copy(self):
        cache = self.root / 'cache/luts/fixture.cube'
        cache.parent.mkdir(parents=True)
        cache.write_bytes(b'original-derived-lut')
        entry = self.session.capture(self.before, self.result, 'leader')
        self.assertEqual(load_json(self.manifest)['reuse']['derived_files'], entry['derived_files'])
        self.assertEqual(entry['derived_files'][0]['sha256'], sha256_file(cache))
        cache.write_bytes(b'changed-derived-lut!')
        with self.assertRaises(AppError) as caught:
            self.session.clone(entry, self.before, self.project, self.sequence,
                               self.project['settings'], self.target)
        self.assertEqual(caught.exception.code, 'QUEUE_REUSE_DERIVED_CHANGED')
        self.assert_no_partial()

    def test_empty_derived_artifact_is_bound_and_later_changes_reject_reuse(self):
        empty = self.root / 'cache/native-audio-clock/continuous/audio.pcm'
        empty.parent.mkdir(parents=True)
        empty.write_bytes(b'')
        entry = self.session.capture(self.before, self.result, 'leader')
        self.assertEqual(entry['derived_files'], [{
            'path': str(empty.resolve()), 'sha256': reuse.hashlib.sha256(b'').hexdigest(), 'bytes': 0}])
        result = self.session.clone(entry, self.before, self.project, self.sequence,
                                    self.project['settings'], self.target)
        self.assertEqual(self.target.read_bytes(), self.leader.read_bytes())
        manifest = load_json(Path(result['manifest']))
        self.assertEqual(manifest['reuse']['source_derived_files'], entry['derived_files'])
        self.target.unlink()
        self.target.with_suffix('.mp4.manifest.json').unlink()
        empty.write_bytes(b'corrupted-from-empty')
        with self.assertRaises(AppError) as caught:
            self.session.clone(entry, self.before, self.project, self.sequence,
                               self.project['settings'], self.target)
        self.assertEqual(caught.exception.code, 'QUEUE_REUSE_DERIVED_CHANGED')
        self.assert_no_partial()

    def test_truncated_derived_artifact_is_rejected_as_changed(self):
        artifact = self.root / 'cache/native-audio-clock/discontinuous/audio.pcm'
        artifact.parent.mkdir(parents=True)
        artifact.write_bytes(b'original-derived-pcm')
        entry = self.session.capture(self.before, self.result, 'leader')
        artifact.write_bytes(b'')
        with self.assertRaises(AppError) as caught:
            self.session.clone(entry, self.before, self.project, self.sequence,
                               self.project['settings'], self.target)
        self.assertEqual(caught.exception.code, 'QUEUE_REUSE_DERIVED_CHANGED')
        self.assert_no_partial()

    def test_callback_failure_closes_handle_and_removes_temporary(self):
        def failed(*args):
            raise RuntimeError('fixture progress consumer failed')
        with self.assertRaisesRegex(RuntimeError, 'progress consumer'):
            self.clone(progress_callback=failed)
        self.assert_no_partial()


class QueueCliTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        CopyTests.setUpClass.__func__(cls)

    @classmethod
    def tearDownClass(cls):
        cls.media_temp.cleanup()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='queue-reuse-cli-')
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.base / 'project'
        self.assertEqual(invoke('project', 'init', str(self.root))[0], 0)
        code, media = invoke('media', 'ingest', '--project', str(self.root), '--input', str(self.media))
        self.assertEqual(code, 0, media)
        aid = media['data']['asset']['id']
        self.changes = self.base / 'changes.json'
        atomic_write_json(self.changes, {'operations': [
            {'op': 'append_clip', 'track_id': 'track_video_1', 'asset_id': aid, 'source_in_tick': 0, 'source_out_tick': 90000},
            {'op': 'append_clip', 'track_id': 'track_audio_1', 'asset_id': aid, 'source_in_tick': 0, 'source_out_tick': 90000},
        ]})
        code, changed = invoke('timeline', 'compose', '--project', str(self.root), '--input', str(self.changes))
        self.assertEqual(code, 0, changed)
        self.jobs = self.base / 'jobs.json'

    def enqueue(self, jobs):
        atomic_write_json(self.jobs, {'jobs': [{'job_id': str(i), 'profile': 'custom', 'width': 160, 'height': 96,
            'output': f'renders/job-{i}.mp4', **job} for i, job in enumerate(jobs)]})
        code, result = invoke('queue', 'enqueue', '--project', str(self.root), '--input', str(self.jobs))
        self.assertEqual(code, 0, result)

    def test_failed_leader_never_seeds_reuse_and_different_specs_encode(self):
        self.enqueue([{'video_codec': 'fixture_invalid_encoder'}, {}, {'crf': 18}, {'width': 256, 'height': 144}])
        with patch.object(cli, 'render_project', wraps=cli.render_project) as render:
            code, result = invoke('queue', 'run', '--project', str(self.root), '--reuse-identical', '--continue-on-error')
        self.assertEqual(code, 2, result)
        self.assertEqual(result['data']['summary']['succeeded'], 3)
        self.assertEqual(result['data']['summary']['failed'], 1)
        self.assertEqual(result['data']['reuse_summary']['encoded_successes'], 2)
        self.assertEqual(result['data']['reuse_summary']['reused_successes'], 1)
        # The invalid codec is rejected by settings normalization before FFmpeg.
        self.assertEqual(render.call_count, 2)
        first, second = self.root / 'renders/job-1.mp4', self.root / 'renders/job-2.mp4'
        self.assertEqual(first.read_bytes(), second.read_bytes())
        self.assertFalse((self.root / 'renders/job-0.mp4').exists())
        self.assertEqual(probe_media(self.root / 'renders/job-3.mp4')['video']['width'], 256)
        queue = load_json(self.root / 'operations/render-queue.json')
        self.assertEqual([j['status'] for j in queue['jobs']], ['failed', 'succeeded', 'succeeded', 'succeeded'])
        for row in result['data']['jobs'][1:]:
            operation = load_json(self.root / 'operations' / f"{row['operation_id']}.json")
            self.assertEqual(operation['reuse']['encoding_executed'], row['job_id'] != '2')

    def test_default_path_encodes_each_job_and_does_not_create_reuse_record(self):
        self.enqueue([{}, {}])
        with patch.object(cli, 'render_project', wraps=cli.render_project) as render:
            code, result = invoke('queue', 'run', '--project', str(self.root))
        self.assertEqual(code, 0, result)
        self.assertEqual(render.call_count, 2)
        self.assertNotIn('reuse_summary', result['data'])
        self.assertNotIn('reuse', load_json(self.root / 'renders/job-1.mp4.manifest.json'))

    def test_simulated_render_failure_does_not_seed_later_identical_jobs(self):
        self.enqueue([{}, {}, {}])
        real = cli.render_project
        calls = 0
        def fail_first(*args, **kwargs):
            nonlocal calls
            calls += 1
            if calls == 1:
                raise AppError('RENDER_FAILED', 'injected executor failure', exit_code=6)
            return real(*args, **kwargs)
        with patch.object(cli, 'render_project', side_effect=fail_first):
            code, result = invoke('queue', 'run', '--project', str(self.root), '--reuse-identical', '--continue-on-error')
        self.assertEqual(code, 2, result)
        self.assertEqual(calls, 2)
        self.assertEqual(result['data']['reuse_summary']['encoded_successes'], 1)
        self.assertEqual(result['data']['reuse_summary']['reused_successes'], 1)

    def test_current_invocation_only_never_reads_old_success_as_cache(self):
        self.enqueue([{}, {}])
        with patch.object(cli, 'render_project', wraps=cli.render_project) as render:
            for _ in range(2):
                code, result = invoke('queue', 'run', '--project', str(self.root), '--reuse-identical', '--max-jobs', '1')
                self.assertEqual(code, 0, result)
                self.assertEqual(result['data']['reuse_summary']['reused_successes'], 0)
        self.assertEqual(render.call_count, 2)

    def test_each_target_rechecks_publish_rights_before_reuse(self):
        self.enqueue([{}, {'publish': True}])
        with patch.object(cli, 'render_project', wraps=cli.render_project) as render:
            code, result = invoke('queue', 'run', '--project', str(self.root), '--reuse-identical', '--continue-on-error')
        self.assertEqual(code, 2, result)
        self.assertEqual(render.call_count, 1)
        self.assertEqual(result['data']['jobs'][1]['error']['code'], 'PROJECT_INVALID')
        self.assertFalse((self.root / 'renders/job-1.mp4').exists())

    def test_workers_conflict_and_existing_outputs_preserve_metadata(self):
        self.enqueue([{}, {}])
        queue_path = self.root / 'operations/render-queue.json'
        before = queue_path.read_bytes()
        code, result = invoke('queue', 'run', '--project', str(self.root), '--reuse-identical', '--workers', '2', '--continue-on-error')
        self.assertEqual(code, 2, result)
        self.assertEqual(queue_path.read_bytes(), before)
        existing = self.root / 'renders/job-0.mp4'
        existing.write_bytes(b'user-output')
        code, result = invoke('queue', 'run', '--project', str(self.root), '--reuse-identical')
        self.assertEqual(code, 2, result)
        self.assertEqual(result['data']['jobs'][0]['error']['code'], 'QUEUE_REUSE_TARGET_EXISTS')
        self.assertEqual(existing.read_bytes(), b'user-output')

    def test_dry_run_has_no_hashing_render_or_metadata_mutation(self):
        self.enqueue([{}, {}])
        before = (self.root / 'operations/render-queue.json').read_bytes()
        with patch.object(reuse, '_runtime_paths', side_effect=AssertionError('dry-run must not hash')):
            code, result = invoke('queue', 'run', '--project', str(self.root), '--reuse-identical', '--dry-run')
        self.assertEqual(code, 0, result)
        self.assertEqual(result['status'], 'planned')
        self.assertTrue(result['data']['reuse_identical'])
        self.assertEqual(before, (self.root / 'operations/render-queue.json').read_bytes())

    def test_copy_cancellation_has_no_output_metadata_or_partial_artifact(self):
        self.enqueue([{}, {}])
        real = reuse.ReuseSession.clone
        def cancelled(session, *args, **kwargs):
            marker = kwargs['marker']
            def signal(*event):
                marker.parent.mkdir(parents=True, exist_ok=True)
                marker.write_text('cancel-copy', encoding='utf-8')
            return real(session, *args, **{**kwargs, 'progress_callback': signal})
        with patch.object(reuse.ReuseSession, 'clone', cancelled):
            code, result = invoke('queue', 'run', '--project', str(self.root), '--reuse-identical')
        self.assertEqual(code, 2, result)
        self.assertEqual(result['data']['summary']['succeeded'], 1)
        self.assertEqual(result['data']['summary']['cancelled'], 1)
        self.assertEqual(result['data']['jobs'][1]['error']['code'], 'CANCELLED')
        project = load_json(self.root / 'project.json')
        self.assertEqual(len(project['outputs']), 1)
        self.assertFalse((self.root / 'renders/job-1.mp4').exists())
        self.assertFalse((self.root / 'renders/job-1.mp4.manifest.json').exists())
        self.assertFalse(list((self.root / 'renders').glob('.queue-reuse-*')))


if __name__ == '__main__':
    unittest.main()

