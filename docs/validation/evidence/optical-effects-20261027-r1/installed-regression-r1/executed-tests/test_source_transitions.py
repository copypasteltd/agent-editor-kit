from __future__ import annotations

import contextlib
import copy
import io
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from ai_ad_editor.cli import main
from ai_ad_editor.errors import AppError
from ai_ad_editor.project import create_project, save_project
from ai_ad_editor.runtime import configure_local_runtime
from ai_ad_editor.source_transitions import analyze, build_plan, compile_for_render
from ai_ad_editor.utils import sha256_file
from ai_ad_editor.validator import validate_project

TPS, FPS, W, H, SR = 90000, 10, 64, 40, 48000


def clip(cid, a, b, asset='source', **kw):
    return {'id': cid, 'asset_id': asset, 'timeline_start_tick': int(a*TPS),
            'duration_tick': int((b-a)*TPS), 'source_in_tick': 2*TPS,
            'source_out_tick': int((2+b-a)*TPS), **kw}


def fixture():
    clips = [clip('a', 0, 2, link_id='ga'), clip('b', 2, 4, link_id='gb'), clip('c', 4, 6, link_id='gc')]
    audio = [clip('a_audio', 0, 2, 'sound', link_id='ga'), clip('b_audio', 2, 4, 'sound', link_id='gb'),
             clip('c_audio', 4, 6, 'sound', link_id='gc')]
    return {'project': {'id': 'p'}, 'settings': {'timebase': {'ticks_per_second': TPS,
            'display_fps': {'num': FPS, 'den': 1}}},
            'assets': [{'id': 'source', 'kind': 'video', 'probe': {'duration_seconds': 8}},
                       {'id': 'sound', 'kind': 'audio', 'probe': {'duration_seconds': 8}}],
            'sequences': [{'id': 'seq', 'name': 'seq', 'duration_tick': 6*TPS, 'tracks': [
                {'id': 'main', 'kind': 'video', 'order': 0, 'clips': clips},
                {'id': 'voice', 'kind': 'audio', 'order': 1, 'clips': audio}]}]}


def add(**kw):
    return {'action': 'add', 'id': 'tr_ab', 'from_clip_id': 'a', 'to_clip_id': 'b',
            'duration_tick': TPS, **kw}


def invoke(*argv):
    out = io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(io.StringIO()):
        code = main(list(argv))
    return code, json.loads(out.getvalue())


class SourceTransitionPlannerTests(unittest.TestCase):
    def plan(self, p, request):
        before = copy.deepcopy(p)
        result = build_plan(p, 'seq', request)
        self.assertEqual(p, before)
        return result

    def rejects(self, p, request, code):
        before = copy.deepcopy(p)
        with self.assertRaises(AppError) as caught:
            build_plan(p, 'seq', request)
        self.assertEqual(caught.exception.code, code)
        self.assertEqual(p, before)

    def test_source_windows_keep_cut_length_clips_and_linked_audio(self):
        p = fixture()
        changed, plan = self.plan(p, add())
        self.assertEqual(p['sequences'][0]['tracks'], changed['sequences'][0]['tracks'])
        self.assertEqual(plan['render_plan']['transitions'][0]['start_tick'], 135000)
        self.assertEqual(plan['render_plan']['transitions'][0]['end_tick'], 225000)
        h = {x['clip_id']: x for x in plan['render_plan']['handles']}
        self.assertEqual((h['a']['source_in_tick'], h['a']['source_out_tick']), (180000, 405000))
        self.assertEqual((h['b']['source_in_tick'], h['b']['source_out_tick']), (135000, 360000))
        self.assertEqual(h['a_audio']['tail_tick'], 45000)
        self.assertEqual(changed['sequences'][0]['duration_tick'], 540000)

    def test_resize_and_remove_restore_original_authored_model(self):
        p = fixture()
        changed, _ = self.plan(p, add())
        resized, plan = self.plan(changed, {'action': 'resize', 'id': 'tr_ab', 'duration_tick': 72000, 'type': 'dip_white'})
        self.assertEqual(plan['after']['type'], 'dip_white')
        self.assertEqual(resized['sequences'][0]['tracks'], p['sequences'][0]['tracks'])
        restored, _ = self.plan(resized, {'action': 'remove', 'id': 'tr_ab'})
        self.assertEqual(restored, p)

    def test_reverse_extends_opposite_source_edges(self):
        p = fixture()
        for c in p['sequences'][0]['tracks'][0]['clips']:
            c['reverse'] = True
        _, plan = self.plan(p, add(audio='none'))
        h = {x['clip_id']: x for x in plan['render_plan']['handles']}
        self.assertEqual((h['a']['source_in_tick'], h['a']['source_out_tick']), (135000, 360000))
        self.assertEqual((h['b']['source_in_tick'], h['b']['source_out_tick']), (180000, 405000))

    def test_constant_speed_scales_handles_without_floats(self):
        p = fixture()
        for c in p['sequences'][0]['tracks'][0]['clips']:
            c.update(speed=2, source_out_tick=6*TPS)
        _, plan = self.plan(p, add(audio='none'))
        h = {x['clip_id']: x for x in plan['render_plan']['handles']}
        self.assertEqual(h['a']['source_out_tick'], 7*TPS)
        self.assertEqual(h['b']['source_in_tick'], TPS)

    def test_fractional_frame_rate_odd_window_bias_is_exact(self):
        p = fixture()
        p['settings']['timebase']['display_fps'] = {'num': 30000, 'den': 1001}
        for t in p['sequences'][0]['tracks']:
            for i, c in enumerate(t['clips']):
                c.update(timeline_start_tick=i*60060, duration_tick=60060, source_in_tick=60060, source_out_tick=120120)
        _, plan = self.plan(p, add(duration_tick=15015))
        tr = plan['render_plan']['transitions'][0]
        self.assertEqual((tr['pre_tick'], tr['post_tick']), (6006, 9009))

    def test_short_source_tail_rejects_without_padding(self):
        p = fixture()
        p['assets'][0]['probe']['duration_seconds'] = 4.2
        self.rejects(p, add(), 'SOURCE_TRANSITION_HANDLE_SHORTFALL')

    def test_short_source_head_rejects_without_duration_clamp(self):
        p = fixture()
        p['sequences'][0]['tracks'][0]['clips'][1].update(source_in_tick=0, source_out_tick=2*TPS)
        self.rejects(p, add(), 'SOURCE_TRANSITION_HANDLE_SHORTFALL')

    def test_mismatched_constant_source_clock_rejects(self):
        p = fixture()
        p['sequences'][0]['tracks'][0]['clips'][0]['speed'] = 1.1
        self.rejects(p, add(), 'SOURCE_TRANSITION_CLOCK_MISMATCH')

    def test_source_subtick_extension_rejects(self):
        p = fixture()
        p['settings']['timebase']['display_fps'] = {'num': 90000, 'den': 1}
        c = p['sequences'][0]['tracks'][0]['clips'][0]
        c.update(speed=.5, source_out_tick=3*TPS)
        self.rejects(p, add(duration_tick=2, audio='none'), 'SOURCE_TRANSITION_SOURCE_GRID')

    def test_unaligned_duration_and_author_boundary_reject(self):
        self.rejects(fixture(), add(duration_tick=90001), 'SOURCE_TRANSITION_FRAME_GRID')
        p = fixture()
        p['sequences'][0]['tracks'][0]['clips'][0]['timeline_start_tick'] = 1
        self.rejects(p, add(audio='none'), 'SOURCE_TRANSITION_CUT')

    def test_second_cut_chain_preserves_both_middle_handles(self):
        p, _ = self.plan(fixture(), add())
        p, plan = self.plan(p, add(id='tr_bc', from_clip_id='b', to_clip_id='c'))
        b = next(h for h in plan['render_plan']['handles'] if h['clip_id'] == 'b')
        self.assertEqual((b['head_tick'], b['tail_tick']), (45000, 45000))
        self.assertEqual(len(plan['render_plan']['transitions']), 2)

    def test_duplicate_window_on_same_cut_rejects(self):
        p, _ = self.plan(fixture(), add())
        self.rejects(p, add(id='another'), 'SOURCE_TRANSITION_WINDOW_OVERLAP')

    def test_any_participating_audio_lock_rejects_all_three_actions(self):
        p = fixture()
        p['sequences'][0]['tracks'][1]['locked'] = True
        self.rejects(p, add(), 'SOURCE_TRANSITION_LOCKED')
        p, _ = self.plan(fixture(), add())
        p['sequences'][0]['tracks'][1]['locked'] = True
        for request in ({'action': 'resize', 'id': 'tr_ab', 'duration_tick': 72000}, {'action': 'remove', 'id': 'tr_ab'}):
            self.rejects(p, request, 'SOURCE_TRANSITION_LOCKED')

    def test_linked_audio_edge_mismatch_requires_explicit_none(self):
        p = fixture()
        p['sequences'][0]['tracks'][1]['clips'][1]['link_id'] = 'unrelated'
        self.rejects(p, add(), 'SOURCE_TRANSITION_LINK_EDGE_MISMATCH')
        _, plan = self.plan(p, add(audio='none'))
        self.assertEqual(plan['after']['audio_pairs'], [])

    def test_invalid_input_types_and_unknown_fields_reject(self):
        requests = [None, [], {'action': []}, add(audio=[]), add(duration_tick=True), add(duration_tick=90000.),
                    add(id=False), add(extra=True), {'action': 'remove', 'id': 'tr_ab', 'duration_tick': 1}]
        for request in requests:
            with self.subTest(request=request):
                self.rejects(fixture(), request, 'SOURCE_TRANSITION_INVALID')

    def test_unaccepted_clip_semantics_reject_explicitly(self):
        for fields in ({'speed_curve': [{'at_tick': 0, 'speed': 1}]}, {'freeze': {'duration_tick': 1}},
                       {'sequence_id': 'child'}, {'tracking_binding': {'version': 'test'}}, {'blend': {'mode': 'multiply'}}):
            p = fixture()
            p['sequences'][0]['tracks'][0]['clips'][0].update(fields)
            with self.subTest(fields=fields):
                self.rejects(p, add(), 'SOURCE_TRANSITION_CLIP_UNSUPPORTED')

    def test_legacy_edge_transition_is_not_overwritten(self):
        p = fixture()
        p['sequences'][0]['tracks'][0]['clips'][0]['transition_out'] = {'type': 'fade'}
        self.rejects(p, add(), 'SOURCE_TRANSITION_EDGE_CONFLICT')

    def test_nested_use_of_transition_sequence_keeps_original_declaration(self):
        p = fixture()
        p['sequences'].append({'id': 'parent', 'tracks': [{'id': 'pt', 'clips': [{'id': 'pc', 'sequence_id': 'seq'}]}]})
        changed, _ = self.plan(p, add())
        self.assertEqual(changed['sequences'][1], p['sequences'][1])
        self.assertEqual(changed['sequences'][0]['tracks'], p['sequences'][0]['tracks'])

    def test_global_duplicate_id_and_missing_reference_reject(self):
        self.rejects(fixture(), add(id='main'), 'SOURCE_TRANSITION_ID_DUPLICATE')
        self.rejects(fixture(), add(to_clip_id='absent'), 'SOURCE_TRANSITION_REFERENCE')

    def test_render_copy_keeps_authored_clocks_and_model_immutable(self):
        p, _ = self.plan(fixture(), add())
        frozen = copy.deepcopy(p)
        compiled, seq, plan = compile_for_render(p, 'seq')
        self.assertEqual(p, frozen)
        b = seq['tracks'][0]['clips'][1]
        self.assertEqual(b['_nested_keyframe_clock']['authored_start'], 2)
        self.assertEqual(b['_nested_subtitle_clock']['authored_duration_seconds'], 2)
        self.assertEqual(b['timeline_start_tick'], 135000)
        self.assertEqual(seq['duration_tick'], 540000)

    def test_pure_planning_uses_no_processes(self):
        with patch('subprocess.Popen', side_effect=AssertionError('planner must be pure')):
            self.plan(fixture(), add())


def raw_source(path, phase=0, *, width=W, height=H, frames=80, step=2):
    """Analytic grayscale source: frame index is visible in each pixel."""
    values = (32+((np.arange(frames)+phase)*step)%190).astype('uint8')
    rgb = np.broadcast_to(values[:, None, None, None], (frames, height, width, 3)).copy()
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24',
                    '-s', f'{width}x{height}', '-r', str(FPS), '-i', 'pipe:0', '-an', '-c:v', 'ffv1',
                    '-pix_fmt', 'gbrp', str(path)], input=rgb.tobytes(), check=True, capture_output=True)
    return rgb


class SourceTransitionCliTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        configure_local_runtime()
        cls.base = tempfile.TemporaryDirectory(prefix='source-transition-fixture-')
        cls.basepath = Path(cls.base.name)
        root, p = create_project(cls.basepath/'project', name='source-handles')
        source = cls.basepath/'source.mkv'
        cls.source_rgb = raw_source(source)
        n = np.arange(8*SR)/SR
        cls.source_pcm = np.stack((.1+.01*n, -.05+.005*n), axis=1).astype('<f4')
        wav = cls.basepath/'sound.wav'
        subprocess.run(['ffmpeg', '-v', 'error', '-y', '-f', 'f32le', '-ar', str(SR), '-ac', '2',
                        '-i', 'pipe:0', '-c:a', 'pcm_f32le', str(wav)], input=cls.source_pcm.tobytes(), check=True, capture_output=True)
        for path, aid in ((source, 'source'), (wav, 'sound')):
            code, result = invoke('media', 'ingest', '--project', str(root), '--input', str(path), '--asset-id', aid)
            if code:
                raise AssertionError(result)
        cls.base_project = json.loads((root/'project.json').read_text(encoding='utf-8'))
        cls.base_project['settings']['canvas'].update(width=W, height=H)
        cls.base_project['settings']['timebase']['display_fps'] = {'num': FPS, 'den': 1}
        cls.base_project['sequences'][0].update(duration_tick=6*TPS, tracks=fixture()['sequences'][0]['tracks'])
        cls.sequence_id = cls.base_project['sequences'][0]['id']
        save_project(root, cls.base_project)
        cls.fixture_root = root

    @classmethod
    def tearDownClass(cls):
        cls.base.cleanup()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='source-transition-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)/'project'
        shutil.copytree(self.fixture_root, self.root)
        self.request = Path(self.temp.name)/'request.json'

    def call(self, request, *extra, domain='transition'):
        self.request.write_text(json.dumps(request), encoding='utf-8')
        return invoke('timeline', domain, '--project', str(self.root), '--input', str(self.request), *extra)

    def p(self):
        return json.loads((self.root/'project.json').read_text(encoding='utf-8'))

    def digest(self):
        return {p.relative_to(self.root).as_posix(): sha256_file(p) for p in self.root.rglob('*') if p.is_file()}

    def render(self, name):
        output = self.root/'renders'/(name+'.mkv')
        code, result = invoke('render', '--project', str(self.root), '--output', str(output), '--container', 'mkv',
                              '--crf', '0', '--pixel-format', 'yuv444p', '--audio-codec', 'pcm_f32le')
        self.assertEqual(code, 0, result)
        rgb = subprocess.check_output(['ffmpeg', '-v', 'error', '-i', str(output), '-an', '-pix_fmt', 'rgb24', '-f', 'rawvideo', 'pipe:1'])
        pcm = subprocess.check_output(['ffmpeg', '-v', 'error', '-i', str(output), '-vn', '-ar', str(SR), '-ac', '2', '-f', 'f32le', 'pipe:1'])
        return np.frombuffer(rgb, dtype='uint8').reshape(-1, H, W, 3), np.frombuffer(pcm, dtype='<f4').reshape(-1, 2), result

    def test_dry_run_snapshot_idempotency_and_stale_hash(self):
        before = self.digest()
        code, dry = self.call(add(), '--dry-run')
        self.assertEqual(code, 0, dry)
        self.assertEqual(self.digest(), before)
        fingerprint = dry['data']['plan']['project_sha256']
        code, result = self.call(add(), '--expected-project-sha256', fingerprint, '--idempotency-key', 'source-add')
        self.assertEqual(code, 0, result)
        after = self.digest()
        code, replay = self.call(add(), '--expected-project-sha256', fingerprint, '--idempotency-key', 'source-add')
        self.assertEqual(code, 0, replay)
        self.assertEqual(replay['operation_id'], result['operation_id'])
        self.assertEqual(self.digest(), after)
        code, failure = self.call({'action': 'resize', 'id': 'tr_ab', 'duration_tick': 72000}, '--expected-project-sha256', fingerprint)
        self.assertEqual(code, 2, failure)
        self.assertEqual(failure['errors'][0]['code'], 'EDIT_PROJECT_CHANGED')
        self.assertEqual(self.digest(), after)

    def test_failure_after_save_rolls_back_all_metadata(self):
        before = self.digest()
        with patch('ai_ad_editor.cli._operation', side_effect=OSError('injected transition operation failure')):
            with self.assertRaisesRegex(OSError, 'injected'):
                self.call(add())
        self.assertEqual(self.digest(), before)

    def test_compose_source_transition_batch_atomicity(self):
        batch = {'operations': [{'op': 'source_transition', 'transition': add()},
                                {'op': 'source_transition', 'transition': add(id='tr_bc', from_clip_id='b', to_clip_id='c')},
                                {'op': 'source_transition', 'transition': add(id='bad', to_clip_id='missing')}]}
        before = self.digest()
        code, result = self.call(batch, domain='compose')
        self.assertEqual(code, 2, result)
        self.assertEqual(self.digest(), before)
        batch['operations'].pop()
        code, result = self.call(batch, domain='compose')
        self.assertEqual(code, 0, result)
        self.assertEqual(len(self.p()['sequences'][0]['source_transitions']), 2)

    def test_schema_fallback_and_stale_cut_both_reject(self):
        self.assertEqual(self.call(add())[0], 0)
        p = self.p()
        p['sequences'][0]['source_transitions'][0]['duration_tick'] = True
        with patch.dict('sys.modules', {'jsonschema': None}):
            report = validate_project(self.root, p)
        self.assertIn('SOURCE_TRANSITION_INVALID', {e['code'] for e in report['errors']})
        p = self.p()
        p['sequences'][0]['tracks'][0]['clips'][1]['timeline_start_tick'] += 9000
        report = validate_project(self.root, p)
        self.assertIn('SOURCE_TRANSITION_CUT', {e['code'] for e in report['errors']})
        for bad in (True, None, {}, [{'id': []}], [False]):
            p = self.p()
            other = copy.deepcopy(p['sequences'][0])
            other['id'] = 'invalid_other'
            other['source_transitions'] = bad
            p['sequences'].append(other)
            with patch.dict('sys.modules', {'jsonschema': None}):
                report = validate_project(self.root, p)
            self.assertFalse(report['ok'])

    def test_native_roundtrips_preserve_and_external_formats_report_loss(self):
        self.assertEqual(self.call(add())[0], 0)
        original = self.p()['sequences'][0]['source_transitions']
        for fmt, suffix in (('agent-json', '.json'), ('package', '.zip')):
            target = Path(self.temp.name)/(fmt+suffix)
            code, result = invoke('convert', 'export', '--project', str(self.root), '--target-format', fmt, '--output', str(target))
            self.assertEqual(code, 0, result)
            restored = Path(self.temp.name)/(fmt+'-restored')
            code, result = invoke('convert', 'import', '--input', str(target), '--output', str(restored))
            self.assertEqual(code, 0, result)
            saved = json.loads((restored/'project.json').read_text(encoding='utf-8'))
            self.assertEqual(saved['sequences'][0]['source_transitions'], original)
        for fmt in ('otio', 'kdenlive-xml', 'jianying-draft-json'):
            output = Path(self.temp.name)/(fmt+'.json')
            code, result = invoke('convert', 'export', '--project', str(self.root), '--target-format', fmt, '--output', str(output))
            self.assertEqual(code, 0, result)
            report = json.loads(Path(result['data']['report']).read_text(encoding='utf-8'))
            self.assertTrue(any(i.get('source') == 'sequence.source_transitions' and i.get('status') == 'Unsupported' for i in report['items']), report)
        target = Path(self.temp.name)/'strict.json'
        code, result = invoke('convert', 'export', '--project', str(self.root), '--target-format', 'jianying-draft-json', '--strict', '--output', str(target))
        self.assertEqual(code, 2, result)
        self.assertFalse(target.exists())

    def test_real_source_crossfade_chain_pixels_and_independent_pcm(self):
        before_rgb, before_pcm, _ = self.render('before')
        self.assertEqual(self.call(add())[0], 0)
        self.assertEqual(self.call(add(id='tr_bc', from_clip_id='b', to_clip_id='c'))[0], 0)
        rgb, pcm, result = self.render('chain')
        self.assertEqual(len(rgb), 60)
        self.assertEqual(len(pcm), 6*SR)
        expected_rgb = self.source_rgb[np.tile(np.arange(20, 40), 3), H//2, W//2, 0].astype(float)
        expected_pcm = np.tile(self.source_pcm[2*SR:4*SR], (3, 1)).copy()
        for cut in (2, 4):
            for n in range(15, 25):
                progress = (n-15)/10
                output_frame = n+(cut-2)*FPS
                a, b = 20+n, n
                expected_rgb[output_frame] = (1-progress)*self.source_rgb[a, H//2, W//2, 0]+progress*self.source_rgb[b, H//2, W//2, 0]
            start, end = int((cut-.5)*SR), int((cut+.5)*SR)
            offset = np.arange(end-start)
            progress = offset/(end-start)
            a = self.source_pcm[int(3.5*SR)+offset]
            b = self.source_pcm[int(1.5*SR)+offset]
            expected_pcm[start:end] = a*(1-progress[:, None])+b*progress[:, None]
        # Encoded RGB/YUV round trips are separate from source-window math.
        self.assertLessEqual(float(np.max(np.abs(rgb[:, H//2, W//2, 0].astype(float)-expected_rgb))), 3)
        np.testing.assert_allclose(pcm, expected_pcm, atol=2e-7, rtol=0)
        outside = [i for i in range(60) if not (15 <= i < 25 or 35 <= i < 45)]
        self.assertLessEqual(int(np.max(np.abs(rgb[outside].astype(int)-before_rgb[outside].astype(int)))), 1)
        self.assertFalse(any(w.get('feature') == 'complex_transition_auto_handle' for w in result.get('warnings', [])))
        self.assertEqual(self.call({'action': 'remove', 'id': 'tr_ab'})[0], 0)
        self.assertEqual(self.call({'action': 'remove', 'id': 'tr_bc'})[0], 0)
        restored_rgb, restored_pcm, _ = self.render('restored')
        np.testing.assert_array_equal(restored_rgb, before_rgb)
        np.testing.assert_array_equal(restored_pcm, before_pcm)

    def test_reverse_source_frames_are_taken_from_real_opposite_handles(self):
        p = self.p()
        for c in p['sequences'][0]['tracks'][0]['clips']:
            c['reverse'] = True
        save_project(self.root, p)
        self.assertEqual(self.call(add(audio='none'))[0], 0)
        rgb, _, _ = self.render('reverse')
        expected = self.source_rgb[np.tile(np.arange(39, 19, -1), 3), H//2, W//2, 0].astype(float)
        for n in range(15, 25):
            progress = (n-15)/10
            expected[n] = (1-progress)*self.source_rgb[39-n, H//2, W//2, 0]+progress*self.source_rgb[59-n, H//2, W//2, 0]
        self.assertLessEqual(float(np.max(np.abs(rgb[:, H//2, W//2, 0].astype(float)-expected))), 3)

    def test_authored_audio_volume_and_fades_keep_phase_when_head_extended(self):
        p = self.p()
        b = p['sequences'][0]['tracks'][1]['clips'][1]
        b['audio'] = {'fade_in': .25, 'fade_out': .25}
        b['keyframes'] = [{'property': 'audio.volume', 'keyframes': [{'at_tick': 0, 'value': .5, 'interpolation': 'linear'}, {'at_tick': 2*TPS, 'value': 1., 'interpolation': 'linear'}]}]
        save_project(self.root, p)
        _, before, _ = self.render('audio-before')
        self.assertEqual(self.call(add())[0], 0)
        _, after, _ = self.render('audio-after')
        np.testing.assert_allclose(after[int(2.5*SR):int(3.8*SR)], before[int(2.5*SR):int(3.8*SR)], rtol=0, atol=2e-7)
        # Negative authored phase before B starts must remain zero under its
        # original fade-in, rather than restarting the fade at the handle.
        start = int(1.5*SR)
        offset = np.arange(SR//2)
        gain = 1-offset/SR
        expected = self.source_pcm[int(3.5*SR)+offset]*gain[:, None]
        np.testing.assert_allclose(after[start:2*SR], expected, rtol=0, atol=2e-7)

    def test_video_animation_effect_and_mask_preserve_authored_phase(self):
        p = self.p()
        b = p['sequences'][0]['tracks'][0]['clips'][1]
        points = [{'at_tick': 0, 'value': .3, 'interpolation': 'linear'},
                  {'at_tick': 2*TPS, 'value': .8, 'interpolation': 'linear'}]
        b['keyframes'] = [{'property': 'transform.opacity', 'keyframes': points}]
        b['effects'] = [{'type': 'brightness', 'parameters': {'amount': 0}, 'keyframes': [
            {'property': 'amount', 'keyframes': [{'at_tick': 0, 'value': 0., 'interpolation': 'linear'},
                                                {'at_tick': 2*TPS, 'value': .15, 'interpolation': 'linear'}]}]}]
        b['mask'] = {'type': 'rectangle', 'x': .1, 'y': .1, 'width': .8, 'height': .8}
        save_project(self.root, p)
        before, _, _ = self.render('keys-before')
        self.assertEqual(self.call(add())[0], 0)
        after, _, _ = self.render('keys-after')
        self.assertLessEqual(int(np.max(np.abs(before[25:40].astype(int)-after[25:40].astype(int)))), 1)

    def test_black_white_dip_is_at_authored_cut_even_with_odd_frame_window(self):
        for kind, color in (('dip_black', 0), ('dip_white', 255)):
            for frames in (1, 5, 10):
                with self.subTest(kind=kind, frames=frames):
                    save_project(self.root, copy.deepcopy(self.base_project))
                    self.assertEqual(self.call(add(type=kind, duration_tick=frames*TPS//FPS))[0], 0)
                    rgb, _, _ = self.render(kind+str(frames))
                    pre, post = frames//2, frames-frames//2
                    for k in range(20-pre, 20+post):
                        if k <= 20:
                            mix = 1 if pre == 0 else (k-(20-pre))/pre
                            expected = (1-mix)*self.source_rgb[20+k, H//2, W//2, 0]+mix*color
                        else:
                            mix = (k-20)/post
                            expected = mix*self.source_rgb[k, H//2, W//2, 0]+(1-mix)*color
                        self.assertLessEqual(abs(int(rgb[k, H//2, W//2, 0])-expected), 3)
                    self.assertLessEqual(abs(int(rgb[20, H//2, W//2, 0])-color), 1)


if __name__ == '__main__':
    unittest.main()
