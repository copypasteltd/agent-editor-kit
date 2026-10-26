"""Shared-output retime against original pixels, exact clocks and sound routing."""
import copy
from fractions import Fraction as F
import unittest
from unittest.mock import patch

import numpy as np

from ai_ad_editor.bindings import validate_project_bindings
from ai_ad_editor.clip_windows import apply_operation
from ai_ad_editor.edit_planner import build_edit_plan
from ai_ad_editor.errors import AppError
from ai_ad_editor.float_timeline import FloatTimeline
from ai_ad_editor.sequence_selection import selected, specialize_audio
import test_float_timeline as fixture
import test_tracking_edits as authored
import test_tracking_magnetic as magnetic


def rows(p):
    return {c['id']: c for t in p['sequences'][0]['tracks'] for c in t['clips']}


class NativeTrackingRetimeTests(unittest.TestCase):
    def plan(self, p, transform=None, cid='source', **kw):
        original = copy.deepcopy(p)
        result, plan = build_edit_plan(p, 'main', dict(action='retime', clip_ids=[cid],
            transform=transform or {'speed': 2}, **kw))
        self.assertEqual(original, p)
        validate_project_bindings(result)
        return result, plan

    def compare(self, original, changed, sources, times, left=False):
        before = FloatTimeline(original, 'main', sources, working_signal=fixture.LINEAR)
        after = FloatTimeline(changed, 'main', sources, working_signal=fixture.LINEAR)
        results = []
        for i, at in enumerate(times):
            before.tracking.reset_frame()
            metadata = []
            expected = before._sequence('main', at, metadata, root=True, left_limit=left)
            actual, report = after.render_frame(i)
            with self.subTest(frame=i, original_time=str(at)):
                np.testing.assert_array_equal(actual, expected)
                old = [r['tracking'] for r in metadata if 'tracking' in r]
                new = [r['tracking'] for r in report['layers'] if 'tracking' in r]
                self.assertEqual(len(old), len(new))
                for a, b in zip(old, new):
                    for key in ('native_pts', 'native_frame_index', 'source_author_tick', 'native_time', 'values'):
                        self.assertEqual(a.get(key), b.get(key), key)
            results.append(report)
        return results

    def reject(self, p, code, **kw):
        old = copy.deepcopy(p)
        with self.assertRaises(AppError) as caught:
            self.plan(p, **kw)
        self.assertEqual(caught.exception.code, code)
        self.assertEqual(p, old)

    def test_fast_source_closes_unlinked_follower_and_retains_original_observations(self):
        p, s = authored.scene(); out, plan = self.plan(p)
        self.compare(p, out, s, [F(i, 5) for i in range(5)])
        context = plan['steps'][0]['shared_author_context']
        self.assertEqual(context['context_clip_ids'], ['marker', 'source'])
        self.assertEqual(len(plan['created_sequences']), 1)
        self.assertEqual(rows(out)['source']['sequence_id'], rows(out)['marker']['sequence_id'])
        self.assertEqual(rows(out)['source']['link_id'], rows(out)['marker']['link_id'])
        child = out['sequences'][1]
        target = next(c for t in child['tracks'] for c in t['clips'] if c.get('tracking_binding'))
        self.assertEqual(target['tracking_binding']['observations'], rows(p)['marker']['tracking_binding']['observations'])
        self.assertFalse(context['model_inference']); self.assertFalse(context['display_keyframes_baked'])

    def test_slow_motion_evaluates_saved_geometry_between_display_frames(self):
        p, s = authored.scene(); out, _ = self.plan(p, {'speed': .5})
        self.compare(p, out, s, [F(i, 20) for i in range(20)])

    def test_reverse_propagates_exact_left_limit_to_source_and_target(self):
        p, s = authored.scene(); out, _ = self.plan(p, {'reverse': True})
        self.compare(p, out, s, [1-F(i, 10) for i in range(10)], left=True)

    def test_freeze_holds_shared_original_author_time(self):
        p, s = authored.scene(); out, _ = self.plan(p, {'freeze': {'at_tick': 30, 'duration_tick': 20}})
        times = [F(i, 10) if i < 3 else F(3, 10) if i < 5 else F(i-2, 10) for i in range(12)]
        self.compare(p, out, s, times)

    def test_piecewise_curve_uses_integral_on_shared_host_clock(self):
        p, s = authored.scene()
        curve = [{'at_tick': 0, 'speed': 1, 'interpolation': 'hold'},
                 {'at_tick': 50, 'speed': 2, 'interpolation': 'hold'}]
        out, _ = self.plan(p, {'speed_curve': curve})
        self.compare(p, out, s, [F(i, 10) if i <= 5 else F(1, 2)+2*(F(i, 10)-F(1, 2)) for i in range(8)])

    def test_existing_curve_crop_and_follower_alpha_remain_on_original_author_graph(self):
        p, s = authored.scene()
        rows(p)['source'].update(speed_curve=[{'at_tick': 0, 'speed': .6}, {'at_tick': 100, 'speed': 1.7}],
            crop={'unit': 'normalized', 'x': .1, 'y': 0, 'width': .8, 'height': 1})
        out, _ = self.plan(p)
        self.compare(p, out, s, [F(i, 5) for i in range(5)])

    def test_nonzero_native_VFR_origin_is_not_replaced_with_display_FPS(self):
        p, s = authored.scene()
        s['a'] = fixture.source([s['a'].fetch(i) for i in range(10)],
            pts=[500, 501, 503, 504, 507, 509, 511, 513, 516, 518],
            durations=[1, 2, 1, 3, 2, 2, 2, 3, 2, 2], time_base='1/20', origin=25)
        out, _ = self.plan(p)
        self.compare(p, out, s, [F(i, 5) for i in range(5)])

    def test_partial_host_keeps_both_parent_routes_and_reference_geometry(self):
        p, s = magnetic.scene(); out, plan = self.plan(p, cid='b', sync_content='retime')
        times = [F(0), F(1,10), F(2,10), F(3,10), F(5,10), F(65,100), F(75,100), F(85,100), F(95,100)]
        self.compare(p, out, s, times)
        self.assertEqual(out['sequences'][0]['duration_tick'], 85)
        self.assertEqual(len(plan['steps'][0]['tracking_binding_changes']), 2)
        for c in rows(out).values():
            if c.get('tracking_binding'):
                self.assertEqual(len(c['tracking_binding']['source_fragments']), 2)
                self.assertEqual(c['tracking_binding']['reference_output_tick'], 0)

    def test_readonly_fragment_context_preserves_original_nonzero_reference(self):
        p, s = magnetic.scene()
        p, _ = apply_operation(p, 'main', dict(op='split_clip', clip_id='source', at_tick=30))
        rows(p)['marker'].update(timeline_start_tick=20, duration_tick=80, source_out_tick=80)
        out, plan = self.plan(p, cid='b', sync_content='retime')
        self.assertIn('source_a', plan['steps'][0]['shared_author_context']['context_clip_ids'])
        times = [F(0), F(1,10), F(2,10), F(3,10), F(5,10), F(65,100), F(75,100), F(85,100), F(95,100)]
        self.compare(p, out, s, times)

    def test_intervening_unrelated_layer_and_noncommutative_blend_keep_original_slots(self):
        p, s = authored.scene(); seq = p['sequences'][0]
        seq['tracks'][1]['order'] = 2
        shade = fixture.clip('shade', 'shade'); shade['transform'] = {'opacity': .27}
        seq['tracks'].insert(1, dict(id='between', kind='overlay', order=1, clips=[shade]))
        p['assets'].append(dict(id='shade', kind='image', sha256=fixture.SHA))
        s['shade'] = fixture.source(fixture.rgba((.2, .4, .6, 1)), still=True, durations=[0])
        rows(p)['marker']['blend'] = {'mode': 'multiply', 'opacity': .73}
        rows(p)['source']['blend'] = {'opacity': .81}
        rows(p)['source']['keyframes'].append(dict(property='blend.opacity',
            keyframes=[dict(at_tick=0,value=.4),dict(at_tick=100,value=.9)]))
        out, _ = self.plan(p)
        self.compare(p, out, s, [F(i, 5) for i in range(5)])
        self.assertEqual(rows(out)['shade'], shade)

    def test_repeated_linked_retime_preserves_nested_shared_clock(self):
        p, s = authored.scene(); out, _ = self.plan(p)
        again, _ = self.plan(out, {'speed': .5})
        self.compare(p, again, s, [F(i, 10) for i in range(10)])

    def test_selected_audio_compilation_keeps_exactly_one_original_sound_leaf(self):
        p, s = authored.scene(); seq = p['sequences'][0]
        rows(p)['source']['link_id'] = 'sound_pair'
        sound = fixture.clip('sound', 'sound', link_id='sound_pair')
        seq['tracks'].append(dict(id='audio', kind='audio', order=2, clips=[sound], audio={'volume': .5}))
        p['assets'].append(dict(id='sound', kind='audio', sha256=fixture.SHA))
        out, _ = self.plan(p)
        private = specialize_audio(out)
        self.assertFalse(any('sequence_clip_id' in c for q in private['sequences'] for t in q['tracks'] for c in t['clips']))
        parents = rows(private)
        seqs = {q['id']: q for q in private['sequences']}
        self.assertEqual([c['asset_id'] for t in seqs[parents['sound']['sequence_id']]['tracks'] for c in t['clips']], ['sound'])
        for name in ('source', 'marker'):
            self.assertFalse(any(t['kind']=='audio' for t in seqs[parents[name]['sequence_id']]['tracks']))
        self.assertEqual(private['sequences'][0]['tracks'][2]['audio'], {'volume': .5})

    def test_readonly_locked_reference_outside_host_does_not_change(self):
        p, s = magnetic.scene()
        p, _ = apply_operation(p, 'main', dict(op='split_clip', clip_id='source', at_tick=30))
        source = rows(p)['source_a']
        lane = p['sequences'][0]['tracks'][1]
        lane['clips'] = [c for c in lane['clips'] if c['id'] != 'source_a']
        p['sequences'][0]['tracks'].append(dict(id='readonly',kind='video',order=1,locked=True,clips=[source]))
        binding = rows(p)['marker']['tracking_binding']
        for ref in binding['source_fragments']:
            if ref['clip_id']=='source_a': ref['track_id']='readonly'
        binding['source_track_id']='readonly'
        frozen = copy.deepcopy(p['sequences'][0]['tracks'][-1])
        out, _ = self.plan(p, cid='b',sync_content='retime')
        self.assertEqual(out['sequences'][0]['tracks'][-1], frozen)
        self.compare(p, out, s, [F(0),F(1,10),F(2,10),F(3,10),F(5,10),F(65,100),F(75,100),F(85,100),F(95,100)])

    def test_chained_follower_remains_in_same_shared_context(self):
        p, s = authored.scene()
        source, marker = rows(p)['source'], rows(p)['marker']
        # The intermediate is a real direct video with its own saved binding.
        carrier = copy.deepcopy(marker); carrier.update(id='carrier',asset_id='a')
        carrier['tracking_binding']['scale_mode']='none'
        carrier['tracking_binding']['rotation_mode']='none'
        p['sequences'][0]['tracks'].append(dict(id='carrier_track',kind='overlay',order=1,clips=[carrier]))
        marker['tracking_binding'].update(source_track_id='carrier_track',source_clip_id='carrier')
        p['sequences'][0]['tracks'][1]['order']=2
        out, plan = self.plan(p)
        self.assertEqual(plan['steps'][0]['shared_author_context']['context_clip_ids'], ['carrier','marker','source'])
        self.compare(p,out,s,[F(i,5) for i in range(5)])

    def test_locked_dependent_rejects_before_any_input_change(self):
        p, _ = authored.scene(); p['sequences'][0]['tracks'][1]['locked'] = True
        self.reject(p, 'EDIT_TRACK_LOCKED')

    def test_dependency_sync_lock_rejects_instead_of_breaking_clock(self):
        p, _ = authored.scene(); p['sequences'][0]['tracks'][1]['sync_lock'] = False
        self.reject(p, 'EDIT_RETIME_BINDING_SYNC_LOCK')

    def test_legacy_binding_guard_and_resource_budget_remain_atomic(self):
        p, _ = authored.scene(); p['settings'].pop('pixel_pipeline')
        self.reject(p, 'EDIT_RANGE_BINDING_UNSUPPORTED')
        p, _ = authored.scene()
        with patch('ai_ad_editor.retime_edits.MAX_CLIPS', 2):
            self.reject(p, 'EDIT_RETIME_RESOURCE_LIMIT')

    def test_invalid_and_default_pipeline_selections_never_fall_back(self):
        p, _ = authored.scene()
        for value, code in [(dict(sequence_id='absent', sequence_clip_id='source'), 'SEQUENCE_SELECTION_MISSING'),
                            (dict(asset_id='a', sequence_clip_id='source'), 'SEQUENCE_SELECTION_INVALID')]:
            with self.subTest(value=value):
                with self.assertRaises(AppError) as caught:
                    selected(p, value)
                self.assertEqual(caught.exception.code, code)
        out, _ = self.plan(p); out['settings'].pop('pixel_pipeline')
        with self.assertRaises(AppError) as caught:
            selected(out, rows(out)['source'])
        self.assertEqual(caught.exception.code, 'SEQUENCE_SELECTION_PIPELINE_REQUIRED')


if __name__ == '__main__':
    unittest.main()
