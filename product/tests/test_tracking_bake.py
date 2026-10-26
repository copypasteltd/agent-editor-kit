"""Actual FloatTimeline playback proves baked keys, with isolated source fixtures."""
import copy
from fractions import Fraction
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

import numpy as np

from ai_ad_editor.bindings import bake_interchange_bindings
from ai_ad_editor.errors import AppError
from ai_ad_editor.float_timeline import FloatTimeline
from ai_ad_editor.tracking_bake import bake, compile_samples, PROTOCOL
import test_float_timeline as fixture
from test_float_tracking import scene


class TrackingBakeTests(unittest.TestCase):
    def setup_context(self, sources, *, mutate_verify=False, change_author=False):
        calls = []
        class Context:
            def __init__(ctx, root, project, sequence, encoder, **options):
                calls.append((project, sequence['id']))
                ctx.project = project
                ctx.timeline = FloatTimeline(project, sequence['id'], sources, working_signal=fixture.LINEAR)
                ctx.metadata = dict(projection_acceleration={'status': 'off'})
                if mutate_verify and not any(c.get('tracking_binding') for s in project['sequences'] for t in s['tracks'] for c in t['clips']):
                    render = ctx.timeline.render_frame
                    def bad(index):
                        pixels, metadata = render(index); pixels = pixels.copy(); pixels[0, 0, 0] += .01
                        return pixels, metadata
                    ctx.timeline.render_frame = bad
            def __enter__(ctx): return ctx
            def __exit__(ctx, *exc): return False
            def finish_sources(ctx):
                ctx.timeline.verify_sources(); ctx.metadata['providers_closed_before_publish'] = True
                if change_author and ctx.project is calls[0][0]: ctx.project.setdefault('provenance', {})['changed'] = True
        return Context, calls

    def run_bake(self, project, sources):
        before = copy.deepcopy(project); factory, calls = self.setup_context(sources)
        baked, proof = bake(Path('.'), project, context_factory=factory)
        self.assertEqual(project, before)
        self.assertTrue(proof['all_float32_frames_equal']); self.assertFalse(proof['external_renderer_verified'])
        self.assertEqual(proof['protocol'], PROTOCOL)
        self.assertTrue(all(r['providers_closed'] for r in proof['receipts']))
        self.assertEqual(len(calls), len(project['sequences']) * 2)
        self.assertFalse(any(c.get('tracking_binding') for s in baked['sequences'] for t in s['tracks'] for c in t['clips']))
        return baked, proof

    def test_native_every_frame_becomes_exact_unrounded_hold_keys(self):
        p, sources, _, _, _ = scene()
        baked, proof = self.run_bake(p, sources)
        self.assertEqual(proof['verified_frames'], 10); self.assertEqual(proof['samples'], 10)
        keys = baked['sequences'][0]['tracks'][1]['clips'][0]['keyframes']
        self.assertTrue(all(k['interpolation'] == 'hold' for t in keys for k in t['keyframes']))
        self.assertEqual(keys[0]['keyframes'][0]['value'], 1.5/8)

    def test_variable_native_PTS_nonzero_origin_is_not_average_FPS(self):
        p, sources, _, _, marker = scene(3)
        frames = [sources['a'].fetch(i) for i in range(3)]
        sources['a'] = fixture.source(frames, pts=[1000, 1002, 1007], durations=[2, 5, 3], time_base='1/10', origin=100)
        for row, at in zip(marker['tracking_binding']['observations'], (0, .2, .7)): row['at_seconds'] = at
        marker['tracking_binding']['range']['end_seconds'] = 1
        _, proof = self.run_bake(p, sources); self.assertEqual(proof['verified_frames'], 10)

    def test_fractional_NTSC_display_ticks_are_replayed_exactly_without_timebase_change(self):
        p, sources, _, _, _ = scene()
        p['settings']['timebase']['display_fps'] = {'num': 30000, 'den': 1001}
        baked, proof = self.run_bake(p, sources)
        self.assertEqual(proof['verified_frames'], 30)
        self.assertEqual(baked['settings']['timebase'], p['settings']['timebase'])

    def test_crop_TRS_actual_mask_and_scalar_opacity_are_included(self):
        p, sources, _, source, _ = scene()
        source['crop'] = dict(unit='normalized', x=.1, y=0, width=.8, height=1, fit='stretch')
        source['transform'] = dict(scale=.8, rotation=10, opacity=.75)
        source['mask'] = dict(type='rectangle', x=0, y=0, width=.5, height=1, feather=.1)
        source['keyframes'] = [dict(property='transform.position.x', keyframes=[
            dict(at_tick=0, value=.4, interpolation='linear'), dict(at_tick=100, value=.6)])]
        baked, _ = self.run_bake(p, sources)
        self.assertEqual(baked['sequences'][0]['tracks'][0]['clips'][0], source)

    def test_spatial_edge_and_paired_colour_transition_visibility_are_sampled(self):
        for kind in ('slideleft', 'distance'):
            with self.subTest(kind=kind):
                p, sources, _, source, _ = scene()
                if kind == 'slideleft': source['transition_in'] = dict(type=kind, duration=.5)
                else:
                    source['duration_tick'] = source['source_out_tick'] = 70
                    incoming = fixture.clip('incoming'); incoming.update(timeline_start_tick=50, duration_tick=50, source_out_tick=50)
                    p['sequences'][0]['tracks'][0]['clips'].append(incoming)
                    source['transition_out'] = incoming['transition_in'] = dict(type='distance', duration=.2)
                    p['sequences'][0]['tracks'][0]['overlap_policy'] = 'allow'
                self.run_bake(p, sources)

    def test_reverse_freeze_and_presentation_window_keep_author_clock(self):
        for mode in ('reverse', 'freeze', 'window'):
            p, sources, _, source, marker = scene()
            if mode == 'reverse': source['reverse'] = True
            elif mode == 'freeze':
                source['freeze'] = dict(at_tick=30, duration_tick=20); source['duration_tick'] = 120
                marker['duration_tick'] = marker['source_out_tick'] = p['sequences'][0]['duration_tick'] = 120
            else:
                source['presentation_window'] = marker['presentation_window'] = dict(version=1, authored_start_tick=0, authored_duration_tick=100, offset_tick=20)
                source['duration_tick'] = marker['duration_tick'] = p['sequences'][0]['duration_tick'] = 50
            with self.subTest(mode=mode): self.run_bake(p, sources)

    def test_nested_reverse_instances_are_sampled_at_actual_continuous_child_clock(self):
        p, sources, _, _, _ = scene(); child = p['sequences'][0]; child['id'] = 'child'
        parent = fixture.clip('parent'); parent.pop('asset_id'); parent.update(sequence_id='child', reverse=True)
        p['sequences'].insert(0, dict(id='main', duration_tick=100, tracks=[fixture.track([parent])]))
        baked, proof = self.run_bake(p, sources)
        self.assertEqual(proof['verified_frames'], 20); self.assertGreater(proof['samples'], 10)
        self.assertEqual(baked['sequences'][0], p['sequences'][0])

    def test_shared_output_speed_curve_and_repeated_retime_bake_complete_dependency_graph(self):
        from ai_ad_editor.edit_planner import build_edit_plan
        from test_tracking_edits import scene as edited_scene
        transforms = [dict(speed=.5), dict(reverse=True),
            dict(speed_curve=[dict(at_tick=0, speed=1, interpolation='hold'), dict(at_tick=50, speed=2, interpolation='hold')])]
        for transform in transforms:
            with self.subTest(transform=transform):
                p, sources = edited_scene()
                changed, _ = build_edit_plan(p, 'main', dict(action='retime', clip_ids=['source'], transform=transform))
                self.run_bake(changed, sources)

    def test_ROI_scale_and_rotation_reference_are_baked_without_recomputing_observations(self):
        p, sources, _, source, marker = scene()
        binding = marker['tracking_binding']; binding.update(scale_mode='roi', rotation_mode='source')
        source['keyframes'] = [dict(property='transform.rotation', keyframes=[
            dict(at_tick=0, value=0, interpolation='linear'), dict(at_tick=100, value=30)])]
        original = copy.deepcopy(binding['observations'])
        baked, _ = self.run_bake(p, sources)
        self.assertEqual(marker['tracking_binding']['observations'], original)
        self.assertTrue({'transform.scale', 'transform.rotation'}.issubset(
            {t['property'] for t in baked['sequences'][0]['tracks'][1]['clips'][0]['keyframes']}))

    def test_muted_target_retains_author_data_and_is_recorded_as_unsampled(self):
        p, sources, _, _, marker = scene(); p['sequences'][0]['tracks'][1]['muted'] = True
        baked, proof = self.run_bake(p, sources)
        self.assertEqual(proof['unsampled_paths'], ['main/marker'])
        expected = copy.deepcopy(marker); expected.pop('tracking_binding')
        self.assertEqual(baked['sequences'][0]['tracks'][1]['clips'][0], expected)

    def test_integer_key_conflict_and_subtick_steps_are_never_silently_rounded(self):
        _, _, _, _, marker = scene()
        for samples, code in ([[(1, {'opacity': 0.}), (1, {'opacity': 1.})], 'CLOCK_CONFLICT'],
                              [[(1.1, {'opacity': 0.}), (1.9, {'opacity': 1.})], 'SUBTICK']):
            with self.subTest(code=code), self.assertRaises(AppError) as caught: compile_samples(marker, samples)
            self.assertEqual(caught.exception.code, 'TRACK_BIND_BAKE_' + code)

    def test_unobservable_position_uses_authored_values_and_later_visible_sample_is_exact(self):
        p, sources, _, source, _ = scene(); source['duration_tick'] = 50
        baked, proof = self.run_bake(p, sources); self.assertEqual(proof['verified_frames'], 10)
        self.assertIn(0., [k['value'] for t in baked['sequences'][0]['tracks'][1]['clips'][0]['keyframes']
                           if t['property'] == 'transform.opacity' for k in t['keyframes']])

    def test_frame_budget_rejects_before_opening_sources(self):
        p, sources, _, _, _ = scene(); factory, calls = self.setup_context(sources)
        with patch('ai_ad_editor.tracking_bake.MAX_FRAMES', 0), self.assertRaises(AppError) as caught:
            bake(Path('.'), p, context_factory=factory)
        self.assertEqual(caught.exception.code, 'TRACK_BIND_BAKE_BUDGET'); self.assertEqual(calls, [])

    def test_sample_budget_never_produces_a_baked_graph(self):
        p, sources, _, _, _ = scene(); factory, _ = self.setup_context(sources)
        with patch('ai_ad_editor.tracking_bake.MAX_SAMPLES', 0), self.assertRaises(AppError) as caught:
            bake(Path('.'), p, context_factory=factory)
        self.assertEqual(caught.exception.code, 'TRACK_BIND_BAKE_BUDGET')

    def test_second_pass_pixel_difference_is_a_failure(self):
        p, sources, _, _, _ = scene(); factory, _ = self.setup_context(sources, mutate_verify=True)
        with self.assertRaises(AppError) as caught: bake(Path('.'), p, context_factory=factory)
        self.assertEqual(caught.exception.code, 'TRACK_BIND_BAKE_VERIFY')

    def test_cancelled_bake_opens_no_sources(self):
        p, sources, _, _, _ = scene(); factory, calls = self.setup_context(sources)
        with tempfile.TemporaryDirectory() as raw:
            marker = Path(raw)/'cancel'; marker.write_text('cancel')
            with self.assertRaises(AppError): bake(Path('.'), p, context_factory=factory, cancel_file=marker)
        self.assertEqual(calls, [])

    def test_changed_author_graph_is_detected(self):
        p, sources, _, _, _ = scene(); factory, _ = self.setup_context(sources, change_author=True)
        with self.assertRaises(AppError) as caught: bake(Path('.'), p, context_factory=factory)
        self.assertEqual(caught.exception.code, 'TRACK_BIND_BAKE_INPUT_CHANGED')

    def test_public_interchange_entry_requires_root_and_returns_native_receipt(self):
        p, sources, _, _, _ = scene(); factory, _ = self.setup_context(sources); receipt = {}
        with patch('ai_ad_editor.float_standard_render.FloatRenderContext', factory):
            result, ids = bake_interchange_bindings(p, Path('.'), receipt=receipt)
        self.assertEqual(ids, ['marker']); self.assertEqual(receipt['verified_frames'], 10)
        self.assertNotIn('tracking_binding', result['sequences'][0]['tracks'][1]['clips'][0])

    def test_agent_export_flag_writes_baked_graph_and_independent_original_sidecar(self):
        import json
        from ai_ad_editor.convert import export_external
        p, sources, _, _, marker = scene(); before = copy.deepcopy(p)
        factory, _ = self.setup_context(sources)
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw); output = root/'exports/baked.json'
            with patch('ai_ad_editor.float_standard_render.FloatRenderContext', factory):
                result = export_external(root, p, output, 'agent-json', bake_tracking=True)
            exported = json.loads(output.read_text('utf8'))
            original = json.loads(Path(result['source_sidecar']).read_text('utf8'))
            self.assertNotIn('tracking_binding', exported['sequences'][0]['tracks'][1]['clips'][0])
            self.assertEqual(original['sequences'][0]['tracks'][1]['clips'][0]['tracking_binding'], marker['tracking_binding'])
            self.assertEqual(result['report_data']['tracking_bake']['verified_frames'], 10)
        self.assertEqual(before, p)

    def test_export_guard_covers_source_assets_and_sidecar_names_before_baking(self):
        from ai_ad_editor.convert import export_external
        p, _, _, _, _ = scene()
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw); (root/'project.json').write_text('source')
            p['assets'][0]['uri'] = str(root/'exports/baked.json.source-agent.json')
            for output in (root/'project.json', root/'assets/new.json', root/'exports/baked.json'):
                with patch('ai_ad_editor.tracking_bake.bake') as execute, self.assertRaises(ValueError):
                    export_external(root, p, output, 'agent-json', bake_tracking=True)
                execute.assert_not_called()
            self.assertEqual((root/'project.json').read_text(), 'source')

    def test_invalid_flag_combination_and_clock_fail_before_source_io(self):
        from ai_ad_editor.convert import export_external
        p, sources, _, _, _ = scene(); factory, calls = self.setup_context(sources)
        with tempfile.TemporaryDirectory() as raw:
            with self.assertRaises(ValueError): export_external(Path(raw), p, Path(raw)/'out.otio', 'otio', bake_tracking=True)
        for bad in (0, True, 3.5):
            with self.subTest(clock=bad):
                q = copy.deepcopy(p); q['settings']['timebase']['ticks_per_second'] = bad
                with self.assertRaises(AppError) as caught: bake(Path('.'), q, context_factory=factory)
                self.assertEqual(caught.exception.code, 'TRACK_BIND_BAKE_CLOCK')
        self.assertEqual(calls, [])

    def test_mlt_extension_reads_actual_XML_with_fractional_profile(self):
        import json
        from ai_ad_editor.convert import import_external
        with tempfile.TemporaryDirectory() as raw:
            root=Path(raw); source=root/'native.MLT'
            source.write_text('<mlt><profile frame_rate_num="30000" frame_rate_den="1001" width="320" height="180"/></mlt>',encoding='utf8')
            result=import_external(source,root/'imported')
            imported=json.loads(Path(result['project']).read_bytes())
            self.assertEqual(imported['settings']['timebase']['display_fps'],{'num':30000,'den':1001})
            self.assertEqual(result['report_data']['source_format'],'mlt')

    def test_bake_flag_without_bindings_has_no_phantom_source_sidecar(self):
        from ai_ad_editor.convert import export_external
        p, _, _, _, marker=scene(); marker.pop('tracking_binding')
        with tempfile.TemporaryDirectory() as raw:
            root=Path(raw); result=export_external(root,p,root/'out.json','agent-json',bake_tracking=True)
            self.assertNotIn('source_sidecar',result); self.assertNotIn('preserved_source',result['report_data'])

    def test_OTIO_local_metadata_preserves_fractional_display_rate_and_integer_tick_domain(self):
        import json
        from ai_ad_editor.convert import import_external
        with tempfile.TemporaryDirectory() as raw:
            root=Path(raw); source=root/'timeline.otio'
            source.write_text(json.dumps(dict(OTIO_SCHEMA='Timeline.1',metadata=dict(ai_ad_editor=dict(
                ticks_per_second=100,display_fps=dict(num=30000,den=1001),duration_tick=123)),
                tracks=dict(OTIO_SCHEMA='Stack.1',children=[]))),encoding='utf8')
            result=import_external(source,root/'imported')
            imported=json.loads(Path(result['project']).read_bytes())
            self.assertEqual(imported['settings']['timebase']['ticks_per_second'],100)
            self.assertEqual(imported['settings']['timebase']['display_fps'],{'num':30000,'den':1001})
            self.assertEqual(imported['sequences'][0]['duration_tick'],123)


if __name__ == '__main__': unittest.main()
