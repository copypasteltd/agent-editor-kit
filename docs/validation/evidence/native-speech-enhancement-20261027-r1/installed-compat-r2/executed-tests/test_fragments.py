"""Cross-project edited groups: real files, rights, clocks and rollback."""
from __future__ import annotations

import contextlib
import copy
import hashlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
from PIL import Image

from ai_ad_editor import fragments
from ai_ad_editor.artifact_locks import verification_scope
from ai_ad_editor.cli import main
from ai_ad_editor.errors import AppError
from ai_ad_editor.media import ffmpeg_path
from ai_ad_editor.project import create_project, load_project, project_write_lock, save_project
from ai_ad_editor.rights import (add_record, check_project_rights, create_disposition_decision,
                                load_ledger, revise_record, save_ledger)
from ai_ad_editor.runtime import configure_local_runtime
from ai_ad_editor.utils import atomic_write_json, sha256_file
from ai_ad_editor.validator import validate_project

TPS = 90000


def invoke(*args):
    capture = io.StringIO()
    with contextlib.redirect_stdout(capture), contextlib.redirect_stderr(io.StringIO()):
        code = main(list(map(str, args)))
    return code, json.loads(capture.getvalue())


def tree(path):
    return {p.relative_to(path).as_posix(): sha256_file(p) for p in path.rglob('*') if p.is_file()}


class FragmentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        configure_local_runtime()
        cls.media_temp = tempfile.TemporaryDirectory(prefix='fragment-inputs-')
        cls.media = Path(cls.media_temp.name)
        Image.new('RGB', (64, 40), (220, 40, 10)).save(cls.media/'red.png')
        Image.new('RGB', (64, 40), (10, 50, 230)).save(cls.media/'blue.png')
        cls.ffmpeg = ffmpeg_path()
        subprocess.run([cls.ffmpeg, '-v', 'error', '-f', 'lavfi', '-i', 'testsrc2=size=64x40:rate=10:duration=6',
            '-f', 'lavfi', '-i', 'sine=frequency=433:sample_rate=48000:duration=6',
            '-c:v', 'libx264', '-preset', 'ultrafast', '-crf', '0', '-pix_fmt', 'yuv444p',
            '-c:a', 'pcm_f32le', '-ac', '2', '-y', str(cls.media/'source.mkv')], check=True, capture_output=True)

    @classmethod
    def tearDownClass(cls):
        cls.media_temp.cleanup()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='fragment-test-')
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.source, p = create_project(self.base/'source')
        self.target, q = create_project(self.base/'target')
        self.library = self.base/'library'
        for root, project in ((self.source, p), (self.target, q)):
            project['settings']['canvas'].update(width=64, height=40)
            project['settings']['timebase']['display_fps'] = {'num': 10, 'den': 1}
            project['settings']['output'] = {'container': 'mkv', 'video': {'codec': 'libx264', 'preset': 'ultrafast',
                'crf': 0, 'pixel_format': 'yuv444p'}, 'audio': {'codec': 'pcm_f32le', 'bitrate': '192k'}}
            save_project(root, project)
        self.call('media', 'ingest', '--project', self.source, '--input', self.media/'red.png', '--asset-id', 'same')
        self.call('media', 'ingest', '--project', self.target, '--input', self.media/'blue.png', '--asset-id', 'same')
        p = self.p()
        p['sequences'][0]['duration_tick'] = 3*TPS
        p['sequences'][0]['tracks'][0]['clips'] = [self.clip('picture', TPS, 2*TPS, 'same', link_id='link')]
        p['sequences'][0]['markers'] = [{'id': 'mark', 'at_tick': TPS, 'label': 'picture'}]
        save_project(self.source, p)
        self.save_req = {'id': 'intro', 'version': 1, 'name': '片头 CTA', 'tags': ['广告', 'CTA'], 'sequence_id': 'seq_main'}
        self.apply_req = {'id': 'intro', 'version': 1, 'sequence_id': 'seq_main', 'track_id': 'track_video_1', 'at_tick': 0}

    def p(self, root=None):
        return load_project(root or self.source)[1]

    @staticmethod
    def clip(cid, start, duration, asset=None, **extra):
        return {'id': cid, 'timeline_start_tick': start, 'duration_tick': duration, 'source_in_tick': 0,
                'source_out_tick': duration, **({'asset_id': asset} if asset else {}), **extra}

    def call(self, *args, expected=0):
        code, result = invoke(*args)
        self.assertEqual(code, expected, result)
        return result

    def req(self, value, name='request'):
        path = self.base/(name+'.json')
        atomic_write_json(path, value)
        return path

    def save(self, request=None, *extra, expected=0):
        return self.call('fragment', 'save', '--project', self.source, '--library', self.library,
                         '--input', self.req(request or self.save_req, 'save'), *extra, expected=expected)

    def apply(self, request=None, *extra, expected=0):
        return self.call('fragment', 'apply', '--project', self.target, '--library', self.library,
                         '--input', self.req(request or self.apply_req, 'apply'), *extra, expected=expected)

    def test_dry_run_save_and_apply_do_not_write_any_project_or_library_file(self):
        before = tree(self.source)
        self.save(None, '--dry-run')
        self.assertEqual(tree(self.source), before)
        self.assertFalse(self.library.exists())
        self.save()
        before, lib = tree(self.target), tree(self.library)
        self.apply(None, '--dry-run')
        self.assertEqual(tree(self.target), before)
        self.assertEqual(tree(self.library), lib)

    def test_immutable_versions_search_and_offline_library_move(self):
        saved = self.save()
        self.assertEqual(self.save(expected=2)['errors'][0]['code'], 'FRAGMENT_VERSION_EXISTS')
        self.save({**self.save_req, 'version': 2})
        result = self.call('fragment', 'list', '--library', self.library, '--query', 'cta')
        self.assertEqual(len(result['data']['fragments']), 2)
        self.assertFalse(result['data']['fragments'][0]['resources_verified'])
        moved = self.base/'moved'
        shutil.move(self.library, moved)
        self.library = moved
        inspected = self.call('fragment', 'inspect', '--library', moved, '--id', 'intro', '--version', '1')
        self.assertEqual(inspected['data']['fragment_sha256'], saved['data']['plan']['fragment_sha256'])
        self.apply()

    def test_same_name_different_bytes_and_repeated_instances_keep_source_immutable(self):
        self.save()
        before = tree(self.library)
        original = self.p(self.target)['assets'][0]
        first = self.apply()['data']['plan']
        second = self.apply({**self.apply_req, 'at_tick': 2*TPS})['data']['plan']
        p = self.p(self.target)
        self.assertEqual(p['assets'][0], original)
        self.assertNotEqual(first['id_maps']['asset']['same'], second['id_maps']['asset']['same'])
        self.assertNotEqual(first['id_maps']['link']['link'], second['id_maps']['link']['link'])
        self.assertEqual(tree(self.library), before)
        self.assertEqual(len(p['sequences']), 3)
        self.assertTrue(validate_project(self.target, p)['ok'])

    def test_nonzero_author_clock_marker_and_plain_text_not_id_replaced(self):
        p = self.p()
        p['sequences'][0]['tracks'].append({'id': 'sub', 'kind': 'subtitle', 'order': 1, 'clips': [
            self.clip('caption', TPS, 2*TPS, generator={'type': 'text'}, subtitle={'text': 'picture', 'style': {'font_size': 12}})]})
        save_project(self.source, p)
        self.save()
        plan = self.apply()['data']['plan']
        self.assertEqual(plan['entry_clip']['source_in_tick'], TPS)
        p = self.p(self.target)
        saved = p['sequences'][1]
        self.assertEqual(saved['tracks'][0]['clips'][0]['timeline_start_tick'], TPS)
        self.assertEqual(saved['tracks'][2]['clips'][0]['subtitle']['text'], 'picture')
        self.assertEqual(saved['markers'][0]['label'], 'picture')
        self.assertEqual(saved['markers'][0]['at_tick'], TPS)
        self.assertNotEqual(saved['markers'][0]['id'], 'mark')

    def test_link_and_nested_sequence_dependency_closure(self):
        p = self.p()
        main = p['sequences'][0]
        child = copy.deepcopy(main)
        child.update(id='child', markers=[])
        for t in child['tracks']:
            t['id'] = 'child_'+t['id']
            for c in t['clips']:
                c.update(id='child_'+c['id'], link_id='childlink')
        p['sequences'].append(child)
        main['tracks'][0]['clips'].append(self.clip('nested', TPS, 2*TPS, sequence_id='child', link_id='link'))
        main['tracks'][0]['overlap_policy'] = 'allow'
        save_project(self.source, p)
        result = self.save({**self.save_req, 'clip_ids': ['picture']})
        payload = result['data']['fragment']
        self.assertEqual(payload['selection']['expanded'], ['nested'])
        self.assertEqual(len(payload['project']['sequences']), 2)
        plan = self.apply()['data']['plan']
        imported = self.p(self.target)['sequences'][1]
        nested = next(c for c in imported['tracks'][0]['clips'] if c.get('sequence_id'))
        self.assertEqual(nested['sequence_id'], plan['id_maps']['sequence']['child'])

    def test_missing_asset_or_rights_dependency_rejects_without_library(self):
        p = self.p()
        p['sequences'][0]['tracks'][0]['clips'][0]['rights_dependencies'] = [{'rights_ref': 'missing', 'sha256': 'sha256:'+'a'*64}]
        save_project(self.source, p)
        result = self.save(expected=2)
        self.assertEqual(result['errors'][0]['code'], 'FRAGMENT_RIGHTS_MISSING')
        self.assertFalse(self.library.exists())

    def test_tampered_source_asset_and_library_resource_rejected(self):
        self.save()
        entry = fragments.entry_path(self.library, 'intro', 1)
        payload = json.loads((entry/'fragment.json').read_text(encoding='utf-8'))
        file = entry/payload['files'][0]['path']
        file.write_bytes(file.read_bytes()+b'changed')
        before = tree(self.target)
        result = self.apply(expected=2)
        self.assertEqual(result['errors'][0]['code'], 'FRAGMENT_RESOURCE_HASH_MISMATCH')
        self.assertEqual(tree(self.target), before)
        asset = self.source/self.p()['assets'][0]['uri']
        asset.write_bytes(asset.read_bytes()+b'changed')
        result = self.save({**self.save_req, 'version': 2}, expected=2)
        self.assertEqual(result['errors'][0]['code'], 'FRAGMENT_RESOURCE_HASH_MISMATCH')

    def test_manifest_traversal_and_unlisted_runtime_resource_reject(self):
        self.save()
        path = fragments.entry_path(self.library, 'intro', 1)/'fragment.json'
        original = json.loads(path.read_text(encoding='utf-8'))
        changed = copy.deepcopy(original)
        changed['files'][0]['path'] = '../outside.png'
        path.write_bytes(fragments.json_bytes(changed))
        self.assertEqual(self.apply(expected=2)['errors'][0]['code'], 'FRAGMENT_PATH_INVALID')
        changed = copy.deepcopy(original)
        changed['project']['assets'][0]['uri'] = '../outside.png'
        path.write_bytes(fragments.json_bytes(changed))
        self.assertEqual(self.apply(expected=2)['errors'][0]['code'], 'FRAGMENT_RESOURCE_UNLISTED')

    def test_stale_project_and_fragment_plan_hashes_rejected(self):
        self.save()
        plan = self.apply(None, '--dry-run')['data']['plan']
        self.assertEqual(self.apply(None, '--expected-project-sha256', 'sha256:'+'0'*64, expected=2)['errors'][0]['code'], 'FRAGMENT_PROJECT_CHANGED')
        self.assertEqual(self.apply(None, '--expected-fragment-sha256', 'sha256:'+'0'*64, expected=2)['errors'][0]['code'], 'FRAGMENT_VERSION_CHANGED')
        self.apply(None, '--expected-project-sha256', plan['project_sha256'], '--expected-fragment-sha256', plan['fragment_sha256'])

    def test_incompatible_clock_color_and_global_context_rejected(self):
        self.save()
        original = self.p(self.target)
        for key, value in [('timebase', {'ticks_per_second': TPS, 'display_fps': {'num': 20, 'den': 1}}),
                           ('color', {'primaries': 'bt2020', 'transfer': 'bt709', 'matrix': 'bt709', 'range': 'limited'})]:
            p = copy.deepcopy(original)
            p['settings'][key] = value
            save_project(self.target, p)
            self.assertEqual(self.apply(expected=2)['errors'][0]['code'], 'FRAGMENT_CONTEXT_MISMATCH')
        p = copy.deepcopy(original)
        p['settings']['adjustments'] = [{'type': 'brightness', 'parameters': {'brightness': 0.1}}]
        save_project(self.target, p)
        self.assertEqual(self.apply(expected=2)['errors'][0]['code'], 'FRAGMENT_CONTEXT_UNSUPPORTED')

    def test_different_target_canvas_preserves_native_saved_canvas(self):
        self.save()
        p = self.p(self.target)
        p['settings']['canvas'].update(width=80, height=64)
        save_project(self.target, p)
        self.apply()
        self.assertEqual(self.p(self.target)['sequences'][1]['canvas'], {'width': 64, 'height': 40})

    def test_locked_track_collision_and_instance_reuse_rejected(self):
        self.save()
        p = self.p(self.target)
        p['sequences'][0]['tracks'][0]['locked'] = True
        save_project(self.target, p)
        self.assertEqual(self.apply(expected=2)['errors'][0]['code'], 'FRAGMENT_TARGET_TRACK_INVALID')
        p['sequences'][0]['tracks'][0]['locked'] = False
        save_project(self.target, p)
        self.apply({**self.apply_req, 'instance_id': 'explicit'})
        self.assertEqual(self.apply(expected=2)['errors'][0]['code'], 'FRAGMENT_TARGET_COLLISION')
        self.assertEqual(self.apply({**self.apply_req, 'at_tick': 2*TPS, 'instance_id': 'explicit'}, expected=2)['errors'][0]['code'], 'FRAGMENT_INSTANCE_EXISTS')

    def test_idempotent_replay_and_changed_request_conflict(self):
        self.save()
        result = self.apply(None, '--idempotency-key', 'same-key')
        before = tree(self.target)
        replay = self.apply(None, '--idempotency-key', 'same-key')
        self.assertEqual(result['operation_id'], replay['operation_id'])
        self.assertIn('IDEMPOTENT_REPLAY', {w['code'] for w in replay['warnings']})
        self.assertEqual(tree(self.target), before)
        self.assertEqual(self.apply({**self.apply_req, 'at_tick': 2*TPS}, '--idempotency-key', 'same-key', expected=2)['errors'][0]['code'], 'IDEMPOTENCY_CONFLICT')

    def test_rights_revisions_restrictions_and_disposition_history_keep_publish_block(self):
        ledger = load_ledger(self.source)
        revise_record(ledger, 'same', {'verification_status': 'verified', 'permitted_uses': ['commercial_ad'],
            'evidence': 'local://unavailable-record'}, reason='review', actor='test')
        revise_record(ledger, 'same', {'verification_status': 'restricted', 'restrictions': ['no-advertising']}, reason='restriction', actor='test')
        proposed = create_disposition_decision(ledger, 'same', action='delete', status='proposed', reason='test')
        create_disposition_decision(ledger, 'same', action='delete', status='approved', reason='approved', supersedes_decision_id=proposed['decision_id'])
        save_ledger(self.source, ledger)
        self.save()
        plan = self.apply()['data']['plan']
        aid = plan['id_maps']['right']['same']
        target_ledger = load_ledger(self.target)
        history = [r for r in target_ledger['records'] if r['asset_id'] == aid]
        self.assertEqual([r['verification_status'] for r in history], ['unverified', 'verified', 'restricted'])
        self.assertEqual(history[0]['superseded_by'], history[1]['record_id'])
        checked = check_project_rights(self.p(self.target), target_ledger)
        self.assertIn('RIGHTS_DISPOSITION_BLOCKED', {f['code'] for f in checked['failures']})
        self.assertEqual(len([d for d in target_ledger['decisions'] if d['asset_id'] == aid]), 2)

    def test_rights_only_model_parent_is_copied_without_model_execution_or_weights(self):
        ledger = load_ledger(self.source)
        add_record(ledger, {'asset_id': 'model', 'kind': 'model', 'sha256': 'sha256:'+'a'*64,
            'license_spdx': 'LicenseRef-UNVERIFIED', 'verification_status': 'unverified'})
        revise_record(ledger, 'same', {'derived_from': ['model']}, reason='provenance', actor='test')
        save_ledger(self.source, ledger)
        saved = self.save()['data']['fragment']
        self.assertEqual(len(saved['files']), 1)
        plan = self.apply()['data']['plan']
        copied = next(r for r in load_ledger(self.target)['records'] if r['asset_id'] == plan['id_maps']['right']['model'])
        self.assertEqual(copied['verification_status'], 'unverified')
        self.assertFalse((self.target/'models').exists())

    def test_ordinary_late_failure_rolls_back_project_ledger_and_copied_files(self):
        self.save()
        before = tree(self.target)
        with patch('ai_ad_editor.cli.save_project', side_effect=AppError('INJECTED_FAILURE', 'late failure', exit_code=2)):
            result = self.apply(expected=2)
        self.assertEqual(result['errors'][0]['code'], 'INJECTED_FAILURE')
        self.assertEqual(tree(self.target), before)

    def test_copy_failure_never_publishes_partial_library_version(self):
        with patch('ai_ad_editor.fragments.shutil.copyfile', side_effect=OSError('disk full')):
            result = self.save(expected=2)
        self.assertEqual(result['errors'][0]['code'], 'FRAGMENT_IO_FAILED')
        self.assertFalse((fragments.entry_path(self.library, 'intro', 1)/'fragment.json').exists())
        self.assertFalse(list(self.library.rglob('.fragment-*')))

    def test_budget_and_invalid_selection_reject_before_writes(self):
        for value in ([], ['missing'], ['picture', 'picture']):
            self.assertEqual(self.save({**self.save_req, 'clip_ids': value}, expected=2)['errors'][0]['code'], 'FRAGMENT_SELECTION_INVALID')
        self.assertEqual(self.save(None, '--max-bytes', '1', expected=2)['errors'][0]['code'], 'FRAGMENT_BUDGET_EXCEEDED')
        self.assertFalse(self.library.exists())

    def test_partial_ducking_bus_rejects_but_complete_sequence_keeps_processing(self):
        p = self.p()
        p['sequences'][0]['tracks'][0]['audio'] = {'duck_under_voice': True, 'volume': 0.8}
        p['sequences'][0]['tracks'][0]['clips'].append(self.clip('other', 0, TPS, 'same'))
        save_project(self.source, p)
        self.assertEqual(self.save({**self.save_req, 'clip_ids': ['picture']}, expected=2)['errors'][0]['code'], 'FRAGMENT_PARTIAL_BUS_UNSUPPORTED')
        self.save()
        self.apply()
        self.assertEqual(self.p(self.target)['sequences'][1]['tracks'][0]['audio'], {'duck_under_voice': True, 'volume': 0.8})

    def test_project_native_lock_conflict(self):
        self.save()
        with project_write_lock(self.target):
            result = self.apply(expected=6)
        self.assertEqual(result['errors'][0]['code'], 'PROJECT_WRITE_LOCKED')

    def decode(self, path, audio=False):
        args = ['-vn', '-f', 'f32le', '-ac', '2', '-ar', '48000'] if audio else ['-an', '-f', 'rawvideo', '-pix_fmt', 'rgb24']
        raw = subprocess.run([self.ffmpeg, '-v', 'error', '-i', str(path), *args, '-'], check=True, capture_output=True).stdout
        return np.frombuffer(raw, dtype='<f4' if audio else np.uint8)

    def render(self, root, name, **args):
        extra = [str(x) for key, value in args.items() for x in ('--'+key.replace('_', '-'), value)]
        self.call('render', '--project', root, '--output', root/'renders'/(name+'.mkv'), *extra)
        return root/'renders'/(name+'.mkv')

    def test_real_cross_project_video_and_pcm_match_isolated_author_clock_reference(self):
        self.call('media', 'ingest', '--project', self.source, '--input', self.media/'source.mkv', '--asset-id', 'movie')
        p = self.p()
        p['sequences'][0]['tracks'][0]['clips'] = [self.clip('movie_clip', TPS, 2*TPS, 'movie', source_in_tick=TPS, source_out_tick=3*TPS)]
        p['sequences'][0]['tracks'][1]['audio'] = {'volume': 0.7, 'pan': -0.2}
        p['sequences'][0]['tracks'][1]['clips'] = [self.clip('sound', TPS, 2*TPS, 'movie', source_in_tick=TPS, source_out_tick=3*TPS,
            audio={'volume': 0.8, 'pan': 0.1}, link_id='movie_link')]
        p['sequences'][0]['tracks'][0]['clips'][0]['link_id'] = 'movie_link'
        save_project(self.source, p)
        self.save()
        actual = self.apply()['data']['plan']
        result = self.render(self.target, 'actual')
        # Independent baseline uses original authors and assets with a manually
        # authored wrapper; it does not use fragment extraction/remapping.
        p = self.p()
        root_sequence = {'id': 'reference', 'name': 'reference', 'duration_tick': 2*TPS, 'tracks': [
            {'id': 'reference_track', 'kind': 'video', 'order': 0, 'clips': [
                self.clip('reference_clip', 0, 2*TPS, sequence_id='seq_main', source_in_tick=TPS, source_out_tick=3*TPS)]}]}
        p['sequences'].append(root_sequence)
        save_project(self.source, p)
        reference = self.render(self.source, 'reference', sequence_id='reference')
        np.testing.assert_array_equal(self.decode(result), self.decode(reference))
        np.testing.assert_allclose(self.decode(result, audio=True), self.decode(reference, audio=True), atol=1e-8, rtol=0)
        self.assertEqual(actual['source_entry']['origin_tick'], TPS)

    def test_explicit_font_lut_and_file_caption_resources_are_portable(self):
        font_source = Path('C:/Windows/Fonts/arial.ttf')
        self.assertTrue(font_source.exists())
        self.call('media', 'ingest', '--project', self.source, '--input', font_source, '--asset-id', 'font')
        caption = self.base/'caption.srt'
        caption.write_text('1\n00:00:01,000 --> 00:00:03,000\npicture\n', encoding='utf-8')
        self.call('media', 'ingest', '--project', self.source, '--input', caption, '--asset-id', 'caption_file')
        lut = self.base/'inverse.cube'
        lut.write_text('LUT_3D_SIZE 2\n'+''.join(f'{1-r} {1-g} {1-b}\n' for b in range(2) for g in range(2) for r in range(2)), encoding='utf-8')
        self.call('lut', 'register', '--project', self.source, '--input', lut, '--lut-id', 'look')
        p = self.p()
        assets = {a['id']: a for a in p['assets']}
        p['sequences'][0]['tracks'][0]['clips'][0]['effects'] = [{'type': 'lut3d', 'parameters': {'lut_id': 'look', 'intensity': 0.6}}]
        p['sequences'][0]['tracks'].append({'id': 'sub', 'kind': 'subtitle', 'order': 2, 'clips': [
            self.clip('subtitle', TPS, 2*TPS, 'caption_file', subtitle={'asset_uri': assets['caption_file']['uri'],
                'style': {'fontfile': assets['font']['uri'], 'font_asset_id': 'font', 'font_size': 12}})]})
        save_project(self.source, p)
        self.save()
        self.apply()
        actual = self.render(self.target, 'portable')
        p['sequences'].append({'id': 'ref', 'name': 'reference', 'duration_tick': 2*TPS, 'tracks': [{'id': 'reftrack', 'kind': 'video', 'order': 0,
            'clips': [self.clip('refclip', 0, 2*TPS, sequence_id='seq_main', source_in_tick=TPS, source_out_tick=3*TPS)]}]})
        save_project(self.source, p)
        expected = self.render(self.source, 'ref', sequence_id='ref')
        np.testing.assert_array_equal(self.decode(actual), self.decode(expected))
        self.assertFalse((self.target/'assets/lut-library.json').exists())
        self.assertEqual(len(self.p(self.target)['assets']), 4)

    def test_selected_source_transition_closure_renders_original_video_and_pcm(self):
        from ai_ad_editor.source_transitions import build_plan
        self.call('media', 'ingest', '--project', self.source, '--input', self.media/'source.mkv', '--asset-id', 'movie')
        p = self.p()
        seq = p['sequences'][0]
        seq['tracks'][0]['clips'] = [self.clip('excluded', 0, TPS, 'same')]
        for index, cid in enumerate(('a', 'b')):
            c = self.clip(cid, (index+1)*TPS, TPS, 'movie', source_in_tick=(index+1)*TPS,
                source_out_tick=(index+2)*TPS, link_id='link_'+cid)
            seq['tracks'][0]['clips'].append(c)
            seq['tracks'][1]['clips'].append({**copy.deepcopy(c), 'id': cid+'_audio'})
        p, _ = build_plan(p, 'seq_main', {'action': 'add', 'id': 'cut', 'from_clip_id': 'a', 'to_clip_id': 'b', 'duration_tick': 36000})
        save_project(self.source, p)
        saved = self.save({**self.save_req, 'clip_ids': ['a']})['data']['fragment']
        self.assertEqual(saved['selection']['included'], ['a', 'a_audio', 'b', 'b_audio'])
        self.assertEqual(saved['selection']['expanded'], ['a_audio', 'b', 'b_audio'])
        plan = self.apply()['data']['plan']
        imported = self.p(self.target)['sequences'][1]
        tr = imported['source_transitions'][0]
        self.assertEqual(tr['id'], plan['id_maps']['transition']['cut'])
        self.assertEqual(tr['audio_pairs'][0]['to_clip_id'], plan['id_maps']['clip']['b_audio'])
        actual = self.render(self.target, 'transition')
        # Construct the isolated authored baseline directly, not from payload.
        p['sequences'][0]['tracks'][0]['clips'] = [c for c in p['sequences'][0]['tracks'][0]['clips'] if c['id'] != 'excluded']
        p['sequences'].append({'id': 'reference', 'name': 'reference', 'duration_tick': 2*TPS,
            'tracks': [{'id': 'reftrack', 'kind': 'video', 'order': 0, 'clips': [
                self.clip('refclip', 0, 2*TPS, sequence_id='seq_main', source_in_tick=TPS, source_out_tick=3*TPS)]}]})
        save_project(self.source, p)
        expected = self.render(self.source, 'transition-ref', sequence_id='reference')
        np.testing.assert_array_equal(self.decode(actual), self.decode(expected))
        np.testing.assert_allclose(self.decode(actual, audio=True), self.decode(expected, audio=True), atol=1e-8, rtol=0)

    def test_tracking_binding_source_is_selected_and_rebound_without_model(self):
        from ai_ad_editor.bindings import make_binding
        self.call('media', 'ingest', '--project', self.source, '--input', self.media/'source.mkv', '--asset-id', 'movie')
        p = self.p()
        seq = p['sequences'][0]
        seq['tracks'].append({'id': 'overlay', 'kind': 'video', 'order': 2, 'clips': []})
        source_clip = self.clip('tracked_source', 0, 3*TPS, 'movie')
        target_clip = self.clip('label', TPS, 2*TPS, 'same')
        seq['tracks'][0]['clips'] = [source_clip]
        seq['tracks'][2]['clips'] = [target_clip]
        asset = next(a for a in p['assets'] if a['id'] == 'movie')
        tracking = {'source_sha256': asset['sha256'], 'range': {'start_seconds': 0, 'end_seconds': 3},
            'frames': [{'at_seconds': v, 'x': 0.25+v/10, 'y': 0.25, 'width': 0.2, 'height': 0.2, 'confidence': 1.0} for v in (0, 1, 2, 3)]}
        target_clip['tracking_binding'] = make_binding(p, seq, seq['tracks'][0], source_clip, seq['tracks'][2], target_clip,
            tracking, offset_x=0, offset_y=0, scale_mode='none', scale_multiplier=1, rotation_mode='none')
        save_project(self.source, p)
        saved = self.save({**self.save_req, 'clip_ids': ['label']})['data']['fragment']
        self.assertEqual(saved['selection']['expanded'], ['tracked_source'])
        plan = self.apply()['data']['plan']
        binding = self.p(self.target)['sequences'][1]['tracks'][2]['clips'][0]['tracking_binding']
        self.assertEqual(binding['source_clip_id'], plan['id_maps']['clip']['tracked_source'])
        self.assertEqual(binding['source_track_id'], plan['id_maps']['track']['track_video_1'])
        self.assertEqual(binding['asset_id'], plan['id_maps']['asset']['movie'])
        self.render(self.target, 'binding')

    def test_library_native_lock_conflict_and_save_idempotency(self):
        with fragments._native_byte_lock(self.library/'fragment-write.lock', timeout=0,
                error_code='BUSY', message='test'):
            self.assertEqual(self.save(expected=6)['errors'][0]['code'], 'FRAGMENT_LIBRARY_LOCKED')
        first = self.save(None, '--idempotency-key', 'save-key')
        before = tree(self.library)
        second = self.save(None, '--idempotency-key', 'save-key')
        self.assertEqual(first['data']['plan'], second['data']['plan'])
        self.assertEqual(tree(self.library), before)

    def test_evidence_files_and_list_paths_relocated_with_rights_history(self):
        ledger = load_ledger(self.source)
        proof = self.source/'local-evidence.txt'
        proof.write_text('self-created test evidence', encoding='utf-8')
        revise_record(ledger, 'same', {'evidence': [str(proof), {'path': str(proof), 'note': 'same'}]}, reason='proof', actor='test')
        save_ledger(self.source, ledger)
        self.save()
        plan = self.apply()['data']['plan']
        aid = plan['id_maps']['right']['same']
        record = next(r for r in load_ledger(self.target)['records'] if r['asset_id'] == aid and r.get('active'))
        self.assertTrue((self.target/record['evidence'][0]).is_file())
        self.assertEqual(record['evidence'][1]['path'], record['evidence'][0])
        self.assertEqual(record['evidence'][1]['note'], 'same')

    def test_unknown_runtime_clip_reference_rejects_insertion(self):
        p = self.p()
        p['sequences'][0]['tracks'][0]['clips'][0]['future_clip_id'] = 'picture'
        save_project(self.source, p)
        self.save()
        self.assertEqual(self.apply(expected=2)['errors'][0]['code'], 'FRAGMENT_REFERENCE_UNSUPPORTED')

    def test_unpublished_staging_manifest_is_never_a_visible_library_version(self):
        self.save()
        published = fragments.entry_path(self.library, 'intro', 1)
        staging = published.parent/'.fragment-interrupted-save'
        staging.mkdir()
        shutil.copyfile(published/'fragment.json', staging/'fragment.json')
        before = tree(self.library)
        result = self.call('fragment', 'list', '--library', self.library)
        self.assertEqual([(r['id'], r['version']) for r in result['data']['fragments']], [('intro', 1)])
        self.assertEqual(tree(self.library), before)

    def test_version_directory_junction_cannot_escape_the_library_root(self):
        destination = fragments.entry_path(self.library, 'intro', 1)
        destination.parent.mkdir(parents=True)
        outside = self.base/'outside-version'
        outside.mkdir()
        (outside/'fragment.json').write_text('{}\n', encoding='utf-8')
        if hasattr(Path, 'is_junction') and __import__('os').name == 'nt':
            made = subprocess.run(['cmd.exe', '/d', '/c', 'mklink', '/J', str(destination), str(outside)], capture_output=True)
            self.assertEqual(made.returncode, 0, made.stderr)
        else:
            destination.symlink_to(outside, target_is_directory=True)
        result = self.call('fragment', 'inspect', '--library', self.library, '--id', 'intro', '--version', 1, expected=2)
        self.assertEqual(result['errors'][0]['code'], 'FRAGMENT_PATH_INVALID')
