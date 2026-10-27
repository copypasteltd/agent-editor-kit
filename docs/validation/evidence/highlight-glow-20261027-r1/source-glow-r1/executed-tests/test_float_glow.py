"""Independent image-light references, real GPU kernels and editable delivery."""
import copy
from dataclasses import replace
from fractions import Fraction
import json
import math
from pathlib import Path
import tempfile
import unittest

import numpy as np

from ai_ad_editor.errors import AppError
from ai_ad_editor.float_color_signal import ColorSignal
from ai_ad_editor.float_effect_chain import EffectCompiler
from ai_ad_editor.float_glow import (SPECS, compile_glow, state_at, apply_glow,
    validate_glow, validate_state, admit_neighborhood, luma_coefficients)
from ai_ad_editor.float_gpu import FloatGPUSession
from ai_ad_editor.project import load_project, save_project
from ai_ad_editor.validator import validate_project
import test_procedural_particles as fixtures
import test_float_optics as optical_tests

LINEAR = ColorSignal('bt709', 'linear')
RECEIPTS = []


def effect(kind='bloom', **p):
    return dict(type=kind, parameters=p)


def apply(a, e, at=0, **kw):
    return apply_glow(a, compile_glow(e), at, working_signal=LINEAR, **kw)


def impulse(h=13, w=13):
    a = np.zeros((h, w, 4), np.float32)
    a[:, :, 3] = 1
    a[h//2, w//2, :3] = 1
    return a


class GlowNumericTests(unittest.TestCase):
    def test_impulse_matches_independent_two_dimensional_gaussian_at_every_pixel(self):
        a = impulse()
        actual, m = apply(a, effect(radius=1, threshold=0, knee=0))
        denominator = sum(math.exp(-.5*i*i) for i in range(-3, 4))**2
        expected = a.copy()
        for y in range(13):
            for x in range(13):
                if abs(x-6) <= 3 and abs(y-6) <= 3:
                    expected[y, x, :3] += math.exp(-.5*((x-6)**2+(y-6)**2))/denominator
        np.testing.assert_allclose(actual, expected, atol=1.2e-7, rtol=0)
        self.assertEqual(m['taps_per_axis'], 7)
        self.assertAlmostEqual(float(np.sum(actual[:, :, 0]-a[:, :, 0])), 1, places=6)

    def test_flat_clamped_field_has_exact_soft_knee_energy(self):
        a = np.full((5, 7, 4), .5, np.float32); a[:, :, 3] = 1
        b, _ = apply(a, effect(radius=2.25, threshold=.5, knee=.2, edge='clamp'))
        np.testing.assert_allclose(b[:, :, :3], .55, atol=1e-7, rtol=0)
        hard, _ = apply(a, effect(radius=2.25, threshold=.5, knee=0, edge='clamp'))
        np.testing.assert_array_equal(hard, a)

    def test_black_and_negative_RGB_do_not_create_light_even_with_soft_knee(self):
        for value in (0, -.4):
            a = np.full((4, 5, 4), value, np.float32); a[:, :, 3] = 1
            for kind in SPECS:
                b, _ = apply(a, effect(kind, threshold=0, knee=4))
                np.testing.assert_array_equal(b, a)

    def test_source_luminance_threshold_tracks_declared_D65_primaries(self):
        expected = {'bt709': (.212639, .715169, .072192),
                    'display-p3': (.228975, .691739, .079287),
                    'bt2020': (.2627, .677998, .059302)}
        a = np.array([[[1., 0, 0, 1]]], np.float32)
        values = []
        for primaries, ref in expected.items():
            np.testing.assert_allclose(luma_coefficients(primaries), ref, atol=1e-6, rtol=0)
            b, _ = apply_glow(a, compile_glow(effect(radius=0, threshold=.22, knee=0)), 0,
                             working_signal=ColorSignal(primaries, 'linear'))
            values.append(float(b[0, 0, 0]))
        self.assertEqual(values[0], 1)
        self.assertGreater(values[1], 1)
        self.assertGreater(values[2], values[1])

    def test_higher_threshold_cannot_add_more_light(self):
        rng = np.random.default_rng(39)
        a = rng.uniform(0, 1.5, (7, 9, 4)).astype(np.float32); a[:, :, 3] = 1
        previous = apply(a, effect(radius=.8, threshold=0))[0]
        for threshold in (.3, .7, 1.5, 16):
            b, _ = apply(a, effect(radius=.8, threshold=threshold))
            self.assertTrue(np.all(b <= previous)); previous = b
        np.testing.assert_array_equal(previous, a)

    def test_halation_removes_bright_core_and_tints_actual_neighbor_light(self):
        a = impulse(); b, _ = apply(a, effect('halation', radius=1, threshold=0, knee=0))
        np.testing.assert_array_equal(b[6, 6], a[6, 6])
        self.assertGreater(b[6, 7, 0], 0)
        self.assertAlmostEqual(float(b[6, 7, 1]/b[6, 7, 0]), .2, places=6)
        self.assertAlmostEqual(float(b[6, 7, 2]/b[6, 7, 0]), .05, places=6)

    def test_zero_core_suppression_with_matching_tint_is_bloom(self):
        a = impulse(); p = dict(radius=1.7, threshold=.2, knee=.1, red=.8, green=.4, blue=.2)
        b, _ = apply(a, effect(**p))
        h, _ = apply(a, effect('halation', **p, core_suppression=0))
        np.testing.assert_array_equal(h, b)

    def test_hidden_RGB_is_not_a_light_source_and_zero_coverage_stays_clean(self):
        a = impulse(); a[6, 6] = [1000, 900, 800, 0]
        b, _ = apply(a, effect(radius=1, threshold=0, knee=0))
        self.assertTrue(np.all(b[:, :, :3] == 0))

    def test_light_energy_is_weighted_by_source_coverage(self):
        a = impulse(); b, _ = apply(a, effect(radius=1, threshold=0, knee=0))
        a[6, 6, 3] = .25
        c, _ = apply(a, effect(radius=1, threshold=0, knee=0))
        np.testing.assert_allclose(c[:, :, :3]-a[:, :, :3], (b[:, :, :3]-a[:, :, :3])*.25, atol=7e-8, rtol=0)
        np.testing.assert_array_equal(c[:, :, 3], a[:, :, 3])

    def test_transparent_boundary_loses_outside_energy_clamp_extends_endpoint(self):
        a = np.ones((1, 1, 4), np.float32)
        t, _ = apply(a, effect(radius=1, threshold=0, knee=0))
        c, _ = apply(a, effect(radius=1, threshold=0, knee=0, edge='clamp'))
        norm = sum(math.exp(-.5*i*i) for i in range(-3, 4))
        self.assertAlmostEqual(float(t[0, 0, 0]), 1+1/norm**2, places=6)
        np.testing.assert_array_equal(c, [[[2, 2, 2, 1]]])

    def test_zero_sigma_is_explicit_local_bright_add_and_suppressed_halation_noop(self):
        a = impulse(); b, _ = apply(a, effect(radius=0, threshold=.25, knee=0))
        expected = a.copy(); expected[6, 6, :3] = 1.75
        np.testing.assert_array_equal(b, expected)
        h, m = apply(a, effect('halation', radius=0))
        np.testing.assert_array_equal(h.view(np.uint32), a.view(np.uint32)); self.assertFalse(m['active'])

    def test_alpha_ramp_subnormals_signed_zero_and_extended_RGB_are_preserved(self):
        a = np.ones((256, 256, 4), np.float32); a[:, :, :3] = [1.4, -.3, .8]
        a[:, :, 3] = np.arange(65536, dtype=np.float32).reshape(256, 256)/65535
        bits = np.array([0, 0x80000000, 1, 2, 0x7fffff, 0x800000], np.uint32)
        a.reshape(-1, 4)[:len(bits), 3] = bits.view(np.float32)
        for kind in SPECS:
            b, _ = apply(a, effect(kind, radius=.2, threshold=.1))
            np.testing.assert_array_equal(b[:, :, 3].view(np.uint32), a[:, :, 3].view(np.uint32))
            self.assertTrue(np.all(b[:, :, :3][a[:, :, 3] == 0] == 0))
            self.assertGreater(float(np.max(b[:, :, 0])), 1)

    def test_zero_strength_gain_or_tint_is_input_byte_exact(self):
        a = impulse(); a[0, 0] = [30, -4, 90, -0.]
        for kind in SPECS:
            for p in [dict(intensity=0), dict(gain=0), dict(red=0, green=0, blue=0)]:
                b, m = apply(a, effect(kind, **p))
                self.assertEqual(b.tobytes(), a.tobytes()); self.assertFalse(m['active'])

    def test_all_six_easings_sample_fractional_original_author_time(self):
        expected = {'hold': 0, 'linear': .25, 'ease_in': .0625, 'ease_out': .4375,
                    'ease_in_out': .125, 'bezier': .15625}
        for mode, value in expected.items():
            e = effect(); e['keyframes'] = [optical_tests.keys('threshold', 0, 1, mode)]
            self.assertAlmostEqual(state_at(compile_glow(e), Fraction(25))['threshold'], value, places=7)

    def test_seek_order_tiles_and_input_bytes_do_not_change_result(self):
        a = impulse(11, 15); before = a.tobytes(); e = effect()
        e['keyframes'] = [optical_tests.keys('radius', .25, 2.25)]
        values = {t: apply(a, e, t, tile_pixels=1)[0] for t in (0, 37, 99, 25)}
        for t in (99, 0, 25, 37):
            np.testing.assert_array_equal(apply(a, e, t, tile_pixels=262144)[0], values[t])
        self.assertEqual(a.tobytes(), before)

    def test_invalid_parameters_keys_and_mutated_plans_are_rejected(self):
        for p in [dict(radius=32.01), dict(knee=-.1), dict(threshold=True), dict(edge='wrap'),
                  dict(unknown=1), dict(core_suppression=1)]:
            with self.assertRaises(AppError): compile_glow(effect(**p))
        p = compile_glow(effect())
        for q in [replace(p, edge='wrap'), replace(p, values=(('radius', 1), ('radius', 2))),
                  replace(p, values=(('bad',),)), replace(p, tracks_json='{}')]:
            with self.assertRaises(AppError): state_at(q, 0)
        with self.assertRaises(AppError): validate_state([], {}, 'transparent')
        e = effect(); e['keyframes'] = [optical_tests.keys('radius', 0, 2, end=101)]
        self.assertTrue(validate_glow(e, duration_tick=100))
        e['keyframes'] = [optical_tests.keys('edge', 0, 1)]
        with self.assertRaises(AppError): compile_glow(e)

    def test_surface_signal_workspace_and_neighbor_budgets_fail_before_allocation(self):
        a = impulse()
        for bad in [a.astype(np.float64), a[:, ::-1], np.empty((0, 1, 4), np.float32)]:
            with self.assertRaises(AppError): apply(bad, effect())
        for bad_value in (math.nan, math.inf):
            b = a.copy(); b[0, 0, 0] = bad_value
            with self.assertRaises(AppError): apply(b, effect())
        with self.assertRaises(AppError): apply(a, effect(), max_working_bytes=1)
        with self.assertRaises(AppError): admit_neighborhood(16777216, 32)
        with self.assertRaises(AppError):
            apply_glow(a, compile_glow(effect()), 0, working_signal=ColorSignal('bt709', 'srgb'))
        self.assertEqual(admit_neighborhood(1, 0)[3], 2)

    def test_mid_operator_cancellation_does_not_mutate_input(self):
        a = impulse(); before = a.tobytes(); count = [0]
        def cancel():
            count[0] += 1
            return count[0] > 9
        with self.assertRaises(AppError) as caught: apply(a, effect(), cancel=cancel)
        self.assertEqual(caught.exception.code, 'RENDER_CANCELLED'); self.assertEqual(a.tobytes(), before)

    def test_overflow_is_structured_and_ordered_chain_recomputes_actual_highlights(self):
        a = np.full((1, 1, 4), np.finfo(np.float32).max, np.float32); a[:, :, 3] = 1
        with self.assertRaises(AppError) as caught: apply(a, effect(radius=0, threshold=0, gain=8))
        self.assertEqual(caught.exception.code, 'FLOAT_GLOW_OVERFLOW')
        compiler = EffectCompiler(resource_root=None, working_signal=LINEAR)
        e = effect(radius=0, threshold=0, knee=0)
        a = impulse(); two, m = compiler.apply(a, compiler.compile([e, e]), 0)
        self.assertEqual(two[6, 6, 0], 4); self.assertEqual(len(m['ordered_effects']), 2)

    def test_catalog_aliases_and_legacy_rejection_are_exact(self):
        from ai_ad_editor.effects import effect_catalog, get_effect
        from ai_ad_editor.render import _effect_filters
        self.assertEqual(effect_catalog()['count'], 51)
        for alias, canonical in [('highlight_bloom', 'bloom'), ('film_halation', 'halation')]:
            self.assertEqual(get_effect(alias)['id'], canonical)
            with self.assertRaises(AppError) as caught: _effect_filters([effect(alias)], [], 'glow')
            self.assertEqual(caught.exception.code, 'FLOAT_GLOW_NATIVE_PIPELINE_REQUIRED')


class GlowGPUTests(unittest.TestCase):
    def test_real_four_stage_kernels_match_CPU_for_edges_fractional_radii_and_primaries(self):
        rng = np.random.default_rng(3939)
        a = rng.uniform(-.2, 2, (11, 17, 4)).astype(np.float32); a[:, :, 3] = rng.uniform(0, 1, (11, 17))
        a[0, 0] = [800, -70, 600, -0.]
        a[0, 1, 3] = np.array([1], np.uint32).view(np.float32)[0]
        errors = []
        with tempfile.TemporaryDirectory() as folder:
            with FloatGPUSession(folder, {'projection_acceleration': {'mode': 'require', 'device': '0.0'}}, max_pixels=187) as gpu:
                native_before = copy.deepcopy(gpu.evidence['native']['operations'])
                for kind in SPECS:
                    for edge in ('transparent', 'clamp'):
                        for radius in (0., .2, 1.25, 32.):
                            e = effect(kind, radius=radius, edge=edge, threshold=.27, knee=.13)
                            if kind == 'halation': e['parameters']['core_suppression'] = .75
                            for primaries in ('bt709', 'display-p3', 'bt2020'):
                                p = compile_glow(e); signal = ColorSignal(primaries, 'linear')
                                ref, _ = apply_glow(a, p, 0, working_signal=signal)
                                actual, m = apply_glow(a, p, 0, working_signal=signal, gpu=gpu)
                                np.testing.assert_allclose(actual, ref, rtol=0, atol=3e-6)
                                np.testing.assert_array_equal(actual[:, :, 3].view(np.uint32), a[:, :, 3].view(np.uint32))
                                errors.append(float(np.max(np.abs(actual-ref)))); self.assertTrue(m['GPU'])
                self.assertEqual(gpu.evidence['operations']['glow'], 48)
                for name, count in [('glow_bright', 48), ('glow_blur', 96), ('glow_merge', 48)]:
                    self.assertEqual(gpu.evidence['native']['operations'][name]-native_before.get(name, 0), count)
            self.assertTrue(gpu.evidence['worker_closed']); self.assertTrue(gpu.evidence['control']['threads_closed'])
            RECEIPTS.append(dict(group='glow-48-actual-operations',max_errors=errors,GPU=gpu.evidence))

    def test_noop_and_invalid_dispatch_are_atomic_then_ordered_GPU_chain_works(self):
        a = impulse()
        with tempfile.TemporaryDirectory() as folder:
            with FloatGPUSession(folder, {'projection_acceleration': {'mode': 'require', 'device': '0.0'}}, max_pixels=169) as gpu:
                for kind in SPECS:
                    np.testing.assert_array_equal(apply(a, effect(kind, intensity=0), gpu=gpu)[0], a)
                self.assertFalse(gpu.evidence['operations'])
                with self.assertRaises(AppError): gpu.glow(a, 'bad', {}, 'transparent', 'bt709')
                self.assertFalse(gpu.evidence['operations'])
                compiler = EffectCompiler(resource_root=None, working_signal=LINEAR, gpu=gpu)
                e = effect(radius=1, threshold=0, knee=0)
                result, m = compiler.apply(a, compiler.compile([e]), 0)
                np.testing.assert_allclose(result, apply(a, e)[0], atol=3e-6, rtol=0)
                self.assertTrue(m['ordered_effects'][0]['GPU'])
            RECEIPTS.append(dict(group='glow-atomic-noop',GPU=gpu.evidence))

    def test_GPU_operator_cancellation_releases_worker_shared_memory_and_control(self):
        state = dict(armed=False, polls=0)
        def cancel():
            if state['armed']:
                state['polls'] += 1
                if state['polls'] >= 3: raise AppError('CANCELLED', 'owned glow cancellation', exit_code=6)
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(AppError) as caught:
                with FloatGPUSession(folder, {'projection_acceleration': {'mode': 'require', 'device': '0.0'}}, max_pixels=169, cancel=cancel) as gpu:
                    state['armed'] = True; p = compile_glow(effect())
                    gpu.glow(impulse(), p.effect_type, state_at(p, 0), p.edge, 'bt709')
            self.assertEqual(caught.exception.code, 'CANCELLED')
            self.assertTrue(gpu.evidence['worker_closed']); self.assertTrue(gpu.evidence['shared_handles_closed'])
            self.assertTrue(gpu.evidence['control']['threads_closed']); self.assertTrue(gpu.evidence['control']['streams_closed'])
            RECEIPTS.append(dict(group='glow-owned-cancel',GPU=gpu.evidence))


class GlowIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.f = fixtures.ParticleIntegrationTests('runTest'); self.f.setUp(); self.addCleanup(self.f.doCleanups)
        self.f.c['effects'] = [effect(radius=1.5, threshold=.1, gain=.7),
                               effect('halation', radius=2.5, threshold=.2, gain=.8)]
        self.f.c['effects'][0]['keyframes'] = [optical_tests.keys('radius', .5, 3.5, end=180000)]
        self.f.p['settings']['pixel_pipeline']['range_policy'] = 'clip'
        save_project(self.f.root, self.f.p)

    def collect(self):
        RECEIPTS.extend(copy.deepcopy(fixtures.RECEIPTS)); fixtures.RECEIPTS.clear()

    def test_same_decoded_source_CPU_GPU_encoding_and_complete_PCM_match(self):
        from PIL import Image
        from ai_ad_editor.media import ffmpeg_path
        f = self.f; picture = f.base/'shared-glow.png'
        a = np.zeros((64, 96, 3), np.uint8); a[22:41, 35:61] = [255, 225, 170]
        Image.fromarray(a).save(picture)
        f.call('media', 'ingest', '--project', f.root, '--input', picture, '--asset-id', 'picture',
               '--license-spdx', 'CC0-1.0', '--verification-status', 'verified', '--evidence', 'Original numeric highlight test chart')
        _, f.p = load_project(f.root); f.s = f.p['sequences'][0]; f.c = f.s['tracks'][0]['clips'][0]
        f.c.pop('generator'); f.c['asset_id'] = 'picture'
        f.p['settings']['pixel_pipeline']['sources']['picture'] = dict(source_signal=vars(LINEAR), display_geometry='square-unrotated', demux_origin='0')
        a = f.execute('cpu.mkv'); f.p['settings']['projection_acceleration'] = dict(mode='require', device='0.0')
        b = f.execute('gpu.mkv')
        x, y = (np.frombuffer(f.video(p), '<u2') for p in (a, b))
        self.assertEqual(len(x), 24*96*64*3)
        error = int(np.max(np.abs(x.astype(int)-y.astype(int)))); self.assertLessEqual(error, 1)
        pcm = [f.native([ffmpeg_path(), '-nostdin', '-v', 'error', '-i', p, '-map', '0:a:0', '-vn', '-c:a', 'pcm_f32le', '-f', 'f32le', 'pipe:1']) for p in (a, b)]
        self.assertEqual(pcm[0], pcm[1]); self.assertEqual(len(pcm[0]), 768000)
        m = json.loads(b.with_suffix('.mkv.manifest.json').read_bytes())
        self.assertEqual(m['delivery']['pixel_pipeline']['projection_acceleration']['operations']['glow'], 48)
        self.collect(); RECEIPTS.append(dict(group='glow-shared-source-encoding',frames=24,maximum_10bit_code_error=error,PCM_bytes=len(pcm[0])))

    def test_particle_glow_composition_retains_existing_Float32_error_budget(self):
        from ai_ad_editor.float_timeline import FloatTimeline
        f = self.f; cpu = FloatTimeline(f.p, f.s['id'], {}, working_signal=LINEAR)
        errors = []
        with FloatGPUSession(f.root, {'projection_acceleration': {'mode': 'require', 'device': '0.0'}}, max_pixels=96*64) as gpu:
            accelerated = FloatTimeline(f.p, f.s['id'], {}, working_signal=LINEAR, gpu=gpu)
            for i in range(24):
                a = cpu.render_frame(i)[0]; b = accelerated.render_frame(i)[0]
                errors.append(float(np.max(np.abs(a-b)))); self.assertLessEqual(errors[-1], 3e-6)
            self.assertEqual(gpu.evidence['operations']['particles'], 24); self.assertEqual(gpu.evidence['operations']['glow'], 48)
        RECEIPTS.append(dict(group='glow-particle-composition',maximum_float_error=max(errors),GPU=gpu.evidence))

    def test_package_and_local_OTIO_preserve_all_effects_keys_and_encoded_frames(self):
        self.f.test_package_and_otio_restore_editable_source_and_identical_full_encoding()
        for kind in ('package', 'otio'):
            _, p = load_project(self.f.base/('restored-'+kind))
            c = next(c for t in p['sequences'][0]['tracks'] for c in t['clips'] if c['id'] == self.f.c['id'])
            self.assertEqual(c['effects'], self.f.c['effects'])
        self.collect()

    def test_split_and_nested_reverse_sample_continuous_original_glow_time(self):
        from ai_ad_editor.float_timeline import FloatTimeline
        from ai_ad_editor.clip_windows import slice_clip
        f = self.f; original = copy.deepcopy(f.p)
        frames = [FloatTimeline(f.p, f.s['id'], {}, working_signal=LINEAR).render_frame(i)[0] for i in range(24)]
        f.s['tracks'][0]['clips'] = [slice_clip(f.c, 0, 75000, clip_id='left'), slice_clip(f.c, 75000, 180000, clip_id='right')]
        split = FloatTimeline(f.p, f.s['id'], {}, working_signal=LINEAR)
        for i in range(24): np.testing.assert_array_equal(split.render_frame(i)[0], frames[i])
        child = copy.deepcopy(f.s); child['id'] = 'child'
        f.s['tracks'][0]['clips'] = [dict(id='nested', sequence_id='child', timeline_start_tick=0, duration_tick=180000,
            source_in_tick=0, source_out_tick=180000, reverse=True)]
        f.p['sequences'].append(child); nested = FloatTimeline(f.p, f.s['id'], {}, working_signal=LINEAR)
        for i in range(24):
            tick = math.nextafter(float(180000-i*7500), -math.inf)
            p = copy.deepcopy(original); e = p['sequences'][0]['tracks'][0]['clips'][0]['effects'][0]
            values = state_at(compile_glow(e), tick); e.pop('keyframes'); e['parameters'].update(values)
            expected = FloatTimeline(p, f.s['id'], {}, working_signal=LINEAR).render_frame(23-i)[0]
            np.testing.assert_array_equal(nested.render_frame(i)[0], expected)
        RECEIPTS.append(dict(group='glow-original-clock',split_frames=24,nested_reverse_left_limit_frames=24))

    def test_real_preview_cache_key_edit_and_persistent_GPU_queue(self):
        optical_tests.OpticalIntegrationTests.test_preview_cache_changes_with_effect_key_and_GPU_queue_matches_direct(self)

    def test_adjustments_use_selected_root_interval_once_with_actual_GPU_dispatch(self):
        from ai_ad_editor.float_timeline import FloatTimeline
        f = self.f; f.c.pop('effects')
        plain = FloatTimeline(f.p, f.s['id'], {}, working_signal=LINEAR).render_frame(12)[0]
        e = effect('halation', radius=2, threshold=.05); e['keyframes'] = [optical_tests.keys('intensity', 0, 1, end=90000)]
        f.p['settings']['adjustments'] = [dict(id='glow-interval', start_tick=45000, duration_tick=90000, effects=[e])]
        self.assertTrue(validate_project(f.root, f.p, strict_rights=False)['ok'])
        with FloatGPUSession(f.root, {'projection_acceleration': {'mode': 'require', 'device': '0.0'}}, max_pixels=96*64) as gpu:
            timeline = FloatTimeline(f.p, f.s['id'], {}, working_signal=LINEAR, gpu=gpu)
            actual = timeline.render_frame(12)[0]; expected, _ = apply(plain, e, 45000)
            np.testing.assert_allclose(actual, expected, atol=3e-6, rtol=0)
            self.assertEqual(gpu.evidence['operations']['glow'], 1)
        e['keyframes'][0]['keyframes'][-1]['at_tick'] = 90001
        self.assertFalse(validate_project(f.root, f.p, strict_rights=False)['ok'])
        self.assertTrue(gpu.evidence['worker_closed'])
        RECEIPTS.append(dict(group='glow-root-interval-once',GPU=gpu.evidence))


if __name__ == '__main__':
    unittest.main(verbosity=2)
