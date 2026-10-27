from __future__ import annotations

import copy
import json
import unittest

from ai_ad_editor.edit_planner import build_edit_plan
from ai_ad_editor.errors import AppError
from ai_ad_editor.source_edits import expand_author
from ai_ad_editor.validator import validate_project
from test_range_edits import clip, track, project, positions
import test_clip_windows as _windows

TPS = 90000


def fixture(linked=False):
    v = clip('v', 20, 100, source_in_tick=20, source_out_tick=100)
    tracks = [track('main', [v])]
    if linked:
        v['link_id'] = 'av'
        tracks.append(track('voice', [dict(v, id='a', asset_id='sound')], 'audio', 1))
    value = project(tracks, duration=160)
    value['assets'].append({'id': 'sound', 'kind': 'audio', 'probe': {'duration_seconds': 20}})
    return value


def clips(value):
    return {c['id']: c for t in value['sequences'][0]['tracks'] for c in t['clips']}


class SourcePlannerTests(unittest.TestCase):
    def plan(self, value=None, action='slip', **fields):
        value = fixture() if value is None else value
        before = copy.deepcopy(value)
        result = build_edit_plan(value, 'seq', {'action': action, 'clip_id': 'v', **fields})
        self.assertEqual(value, before)
        return result

    def rejects(self, value, request, code):
        before = copy.deepcopy(value)
        with self.assertRaises(AppError) as caught:
            build_edit_plan(value, 'seq', request)
        self.assertEqual(caught.exception.code, code)
        self.assertEqual(value, before)

    def test_slip_moves_only_source_and_keeps_timeline(self):
        value = fixture()
        result, plan = self.plan(value, delta_source_tick=15)
        expected = copy.deepcopy(clips(value)['v'])
        expected.update(source_in_tick=35, source_out_tick=115)
        self.assertEqual(clips(result)['v'], expected)
        self.assertEqual(positions(result), positions(value))
        self.assertEqual(result['sequences'][0]['duration_tick'], 160)
        self.assertEqual(plan['source_changes'][0]['after_source'], [35, 115])

    def test_negative_and_reverse_slip_use_physical_source_sign(self):
        value = fixture(); clips(value)['v']['reverse'] = True
        result, _ = self.plan(value, delta_source_tick=-10)
        self.assertEqual([clips(result)['v'][k] for k in ('source_in_tick', 'source_out_tick')], [10, 90])

    def test_slip_preserves_curve_freeze_automation_and_window(self):
        value = fixture(); c = clips(value)['v']
        c.update(reverse=True, speed_curve=[{'at_tick': 0, 'speed': 1}, {'at_tick': 80, 'speed': 1}],
                 freeze={'at_tick': 20, 'duration_tick': 10},
                 keyframes=[{'property': 'audio.volume', 'keyframes': [{'at_tick': 40, 'value': .5}]}],
                 presentation_window={'version': 1, 'authored_start_tick': 0,
                                      'authored_duration_tick': 100, 'offset_tick': 10})
        result, _ = self.plan(value, delta_source_tick=5)
        for name in ('reverse', 'speed_curve', 'freeze', 'keyframes', 'presentation_window'):
            self.assertEqual(clips(result)['v'][name], c[name])

    def test_linked_slip_is_atomic_and_explicitly_optional(self):
        value = fixture(True)
        result, plan = self.plan(value, delta_source_tick=10)
        self.assertEqual(plan['selected_clip_ids'], ['a', 'v'])
        self.assertEqual([clips(result)[cid]['source_in_tick'] for cid in ('a', 'v')], [30, 30])
        result, _ = self.plan(value, delta_source_tick=10, options={'linked': False})
        self.assertEqual(clips(result)['a'], clips(value)['a'])

    def test_locked_linked_member_rejects_the_whole_slip(self):
        value = fixture(True); value['sequences'][0]['tracks'][1]['locked'] = True
        self.rejects(value, {'action': 'slip', 'clip_id': 'v', 'delta_source_tick': 1}, 'EDIT_TRACK_LOCKED')

    def test_slip_rejects_either_media_boundary(self):
        for delta in (-21, 101):
            with self.subTest(delta=delta):
                self.rejects(fixture(), {'action': 'slip', 'clip_id': 'v', 'delta_source_tick': delta}, 'SOURCE_EDIT_HANDLE_SHORTFALL')

    def test_fractional_recorded_source_bound_is_not_rounded_up(self):
        value = fixture(); value['assets'][0]['probe']['duration_seconds'] = 12.05
        result, _ = self.plan(value, delta_source_tick=20)
        self.assertEqual(clips(result)['v']['source_out_tick'], 120)
        self.rejects(value, {'action': 'slip', 'clip_id': 'v', 'delta_source_tick': 21}, 'SOURCE_EDIT_HANDLE_SHORTFALL')

    def test_unknown_or_nonfinite_source_duration_rejects(self):
        for duration in (None, 'NaN', 'Infinity', 0, -1):
            value = fixture(); value['assets'][0]['probe']['duration_seconds'] = duration
            with self.subTest(duration=duration):
                self.rejects(value, {'action': 'slip', 'clip_id': 'v', 'delta_source_tick': 1}, 'SOURCE_EDIT_BOUND_UNKNOWN')

    def test_static_asset_is_not_claimed_as_finite_source_video(self):
        value = fixture(); value['assets'][0]['kind'] = 'image'
        self.rejects(value, {'action': 'slip', 'clip_id': 'v', 'delta_source_tick': 1}, 'SOURCE_EDIT_KIND_UNSUPPORTED')

    def test_source_options_do_not_move_sync_tracks_or_riders(self):
        value = fixture(); value['sequences'][0]['editing'] = {'sync': True, 'linkage': True}
        value['sequences'][0]['tracks'].append(track('bed', [clip('b', 0, 160)], 'audio', 1))
        result, plan = self.plan(value, delta_source_tick=1)
        self.assertEqual(clips(result)['b'], clips(value)['b'])
        self.assertFalse(plan['request']['options']['sync'])
        self.assertFalse(plan['request']['options']['linkage'])
        for options in ({'sync': True}, {'linkage': True}):
            self.rejects(value, {'action': 'slip', 'clip_id': 'v', 'delta_source_tick': 1, 'options': options}, 'EDIT_RANGE_REQUEST_INVALID')

    def test_request_types_unknown_fields_and_policy_are_strict(self):
        requests = [{'action': 'slip', 'clip_id': 'v', 'delta_source_tick': d}
                    for d in (True, 1.5, None, 2**53)]
        requests += [{'action': 'extend_source', 'clip_id': 'v', 'head_tick': d} for d in (-1, True, .5)]
        requests += [{'action': 'slip', 'clip_id': 'v', 'delta_source_tick': 1, 'handle_policy': 'source'},
                     {'action': 'slide', 'clip_id': 'v', 'delta_tick': 1, 'handle_policy': True}]
        for request in requests:
            with self.subTest(request=request):
                self.rejects(fixture(), request, 'EDIT_RANGE_REQUEST_INVALID')

    def test_unknown_and_locked_direct_clip_return_structured_errors(self):
        self.rejects(fixture(), {'action': 'slip', 'clip_id': 'missing', 'delta_source_tick': 1}, 'EDIT_CLIP_NOT_FOUND')
        value = fixture(); value['sequences'][0]['tracks'][0]['locked'] = True
        self.rejects(value, {'action': 'extend_source', 'clip_id': 'v'}, 'EDIT_TRACK_LOCKED')

    def test_tracking_source_and_target_slip_reject(self):
        for target in (False, True):
            value = fixture(); c = clips(value)['v']
            binding = {'source_clip_id': 'v', 'source_track_id': 'main'}
            if target:
                c['tracking_binding'] = binding
            else:
                value['sequences'][0]['tracks'].append(track('labels', [clip('label', tracking_binding=binding)], 'subtitle', 1))
            self.rejects(value, {'action': 'slip', 'clip_id': 'v', 'delta_source_tick': 1}, 'EDIT_RANGE_BINDING_UNSUPPORTED')

    def test_real_transition_slip_rechecks_its_extra_handles(self):
        value = fixture(); sequence = value['sequences'][0]
        sequence['tracks'][0]['clips'] = [clip('v', 20, 60, source_in_tick=20, source_out_tick=60),
                                          clip('r', 60, 100, source_in_tick=20, source_out_tick=60)]
        sequence['source_transitions'] = [{'id': 'cut', 'type': 'dissolve', 'duration_tick': 10,
            'from_clip_id': 'v', 'to_clip_id': 'r', 'audio_pairs': []}]
        result, _ = self.plan(value, delta_source_tick=135)
        self.assertEqual(clips(result)['v']['source_out_tick'], 195)
        self.rejects(value, {'action': 'slip', 'clip_id': 'v', 'delta_source_tick': 136}, 'SOURCE_TRANSITION_HANDLE_SHORTFALL')

    def test_genuine_two_sided_extension(self):
        result, plan = self.plan(action='extend_source', head_tick=10, tail_tick=20)
        c = clips(result)['v']
        self.assertEqual([c[k] for k in ('timeline_start_tick', 'duration_tick', 'source_in_tick', 'source_out_tick')], [10, 110, 10, 120])
        self.assertEqual(c['presentation_window'], {'version': 1, 'authored_start_tick': 10,
                                                  'authored_duration_tick': 110, 'offset_tick': 0})
        self.assertEqual(plan['source_changes'][0]['source_left_tick'], 10)

    def test_extension_uses_retained_handles_before_growing_source(self):
        value = fixture(); c = clips(value)['v']
        c.update(duration_tick=20, timeline_start_tick=40,
                 presentation_window={'version': 1, 'authored_start_tick': 0,
                                      'authored_duration_tick': 80, 'offset_tick': 20})
        result, plan = self.plan(value, 'extend_source', head_tick=10, tail_tick=10)
        self.assertEqual([clips(result)['v'][k] for k in ('source_in_tick', 'source_out_tick')], [20, 100])
        self.assertEqual(clips(result)['v']['presentation_window']['offset_tick'], 10)
        self.assertEqual(plan['source_changes'], [])

    def test_mixed_retained_and_true_head_extension(self):
        value = fixture(); c = clips(value)['v']
        c.update(duration_tick=20, timeline_start_tick=40,
                 presentation_window={'version': 1, 'authored_start_tick': 0,
                                      'authored_duration_tick': 80, 'offset_tick': 20})
        result, plan = self.plan(value, 'extend_source', head_tick=30)
        self.assertEqual(clips(result)['v']['source_in_tick'], 10)
        self.assertEqual(clips(result)['v']['presentation_window']['offset_tick'], 0)
        self.assertEqual(plan['source_changes'][0]['head_tick'], 10)

    def test_extension_requires_actual_timeline_space_at_head(self):
        self.rejects(fixture(), {'action': 'extend_source', 'clip_id': 'v', 'head_tick': 21}, 'EDIT_RANGE_EMPTY_SIDE')

    def test_linked_extension_checks_every_source_before_commit(self):
        value = fixture(True); clips(value)['a'].update(source_in_tick=5, source_out_tick=80)
        self.rejects(value, {'action': 'extend_source', 'clip_id': 'v', 'head_tick': 10}, 'SOURCE_EDIT_PADDED_AUTHOR')
        clips(value)['a']['source_out_tick'] = 85
        self.rejects(value, {'action': 'extend_source', 'clip_id': 'v', 'head_tick': 10}, 'SOURCE_EDIT_HANDLE_SHORTFALL')

    def test_reverse_constant_speed_extension_maps_physical_sides(self):
        value = fixture(); c = clips(value)['v']; c.update(reverse=True, speed=2, duration_tick=40)
        result, _ = self.plan(value, 'extend_source', head_tick=10, tail_tick=5)
        self.assertEqual([clips(result)['v'][k] for k in ('source_in_tick', 'source_out_tick')], [10, 120])

    def test_fractional_head_tick_is_rejected_not_rounded(self):
        value = fixture(); clips(value)['v'].update(speed=.5, source_out_tick=60)
        self.rejects(value, {'action': 'extend_source', 'clip_id': 'v', 'head_tick': 1}, 'SOURCE_EDIT_SOURCE_GRID')

    def test_tail_includes_minimal_whole_source_tick_then_crops_output(self):
        value = fixture(); clips(value)['v'].update(speed=.5, source_out_tick=60)
        result, _ = self.plan(value, 'extend_source', tail_tick=1)
        self.assertEqual(clips(result)['v']['source_out_tick'], 61)
        self.assertEqual(clips(result)['v']['duration_tick'], 81)

    def test_implicit_curve_boundaries_and_original_control_values(self):
        value = fixture(); c = clips(value)['v']
        c.update(speed=2, duration_tick=70, speed_curve=[{'at_tick': 20, 'value': 1, 'interpolation': 'hold'}])
        result, _ = self.plan(value, 'extend_source', head_tick=5, tail_tick=5)
        points = clips(result)['v']['speed_curve']
        self.assertEqual([p['at_tick'] for p in points], [0, 10, 30, 90, 95])
        self.assertEqual(points[2]['value'], 1)
        self.assertEqual(clips(result)['v']['source_in_tick'], 10)

    def test_bezier_extension_keeps_original_controls_at_shifted_source_ticks(self):
        value = fixture(); c = clips(value)['v']
        c.update(duration_tick=40, speed_curve={'keyframes': [
            {'at_tick': 0, 'speed': 1, 'interpolation': 'bezier', 'control_points': [.2, .1, .8, .9]},
            {'at_tick': 80, 'speed': 2, 'interpolation': 'linear'}]})
        result, plan = self.plan(value, 'extend_source', head_tick=10, tail_tick=20)
        point = clips(result)['v']['speed_curve']['keyframes'][1]
        self.assertEqual(point['at_tick'], 10)
        self.assertEqual(point['control_points'], [.2, .1, .8, .9])
        self.assertGreaterEqual(plan['source_changes'][0]['actual_content_tick'], 70-1e-7)

    def test_freeze_and_all_effect_automation_shift_by_new_prefix(self):
        value = fixture(); c = clips(value)['v']; c['duration_tick'] = 100
        keys = [{'property': 'brightness', 'keyframes': [{'at_tick': 40, 'value': .2}]}]
        c.update(freeze={'at_tick': 30, 'duration_tick': 20}, keyframes=copy.deepcopy(keys),
                 effects=[{'type': 'brightness', 'keyframes': copy.deepcopy(keys)}],
                 audio={'effects': [{'keyframes': copy.deepcopy(keys)}]})
        result, plan = self.plan(value, 'extend_source', head_tick=10, tail_tick=10)
        c = clips(result)['v']
        self.assertEqual(c['freeze']['at_tick'], 40)
        self.assertEqual(c['effects'][0]['keyframes'][0]['keyframes'][0]['at_tick'], 50)
        self.assertEqual(c['audio']['effects'][0]['keyframes'][0]['keyframes'][0]['at_tick'], 50)
        self.assertEqual(plan['source_changes'][0]['shifted_keyframe_count'], 3)

    def test_padded_author_and_outside_freeze_are_explicit(self):
        value = fixture(); c = clips(value)['v']; c['duration_tick'] = 100
        self.rejects(value, {'action': 'extend_source', 'clip_id': 'v', 'tail_tick': 1}, 'SOURCE_EDIT_PADDED_AUTHOR')
        c['freeze'] = {'at_tick': 90, 'duration_tick': 20}
        self.rejects(value, {'action': 'extend_source', 'clip_id': 'v', 'tail_tick': 1}, 'SOURCE_EDIT_FREEZE_CLOCK_INVALID')

    def test_nested_source_bounds_and_normalized_curve_are_reported(self):
        value = fixture(); c = clips(value)['v']; c.pop('asset_id'); c['sequence_id'] = 'child'
        value['sequences'].append({'id': 'child', 'duration_tick': 120, 'tracks': []})
        result, _ = self.plan(value, 'extend_source', tail_tick=20)
        self.assertEqual(clips(result)['v']['source_out_tick'], 120)
        self.rejects(value, {'action': 'extend_source', 'clip_id': 'v', 'tail_tick': 21}, 'SOURCE_EDIT_HANDLE_SHORTFALL')
        c['speed_curve'] = [{'at_tick': 0, 'speed': 2}, {'at_tick': 80, 'speed': 2}]
        result, plan = self.plan(value, 'extend_source', tail_tick=10)
        change = plan['source_changes'][0]
        self.assertEqual(change['before_nested_curve_scale'], 2)
        self.assertAlmostEqual(change['after_nested_curve_scale'], 1.8)
        self.assertEqual(plan['warnings'][0]['code'], 'SOURCE_EDIT_NESTED_CURVE_RENORMALIZED')

    def test_nested_slip_uses_child_sequence_bound(self):
        value = fixture(); c = clips(value)['v']; c.pop('asset_id'); c['sequence_id'] = 'child'
        value['sequences'].append({'id': 'child', 'duration_tick': 120, 'tracks': []})
        result, _ = self.plan(value, delta_source_tick=20)
        self.assertEqual(clips(result)['v']['source_out_tick'], 120)
        self.rejects(value, {'action': 'slip', 'clip_id': 'v', 'delta_source_tick': 21}, 'SOURCE_EDIT_HANDLE_SHORTFALL')

    def test_source_extension_does_not_remove_cut_reference_gates(self):
        value = fixture(); value['sequences'][0]['source_transitions'] = [
            {'id': 'cut', 'from_clip_id': 'v', 'to_clip_id': 'missing', 'audio_pairs': []}]
        self.rejects(value, {'action': 'extend_source', 'clip_id': 'v', 'tail_tick': 1}, 'EDIT_RANGE_TRANSITION_UNSUPPORTED')

    def test_roll_uses_true_source_only_by_explicit_policy(self):
        value = fixture(); value['sequences'][0]['tracks'][0]['clips'] = [
            clip('l', 20, 60, source_in_tick=20, source_out_tick=60),
            clip('r', 60, 100, source_in_tick=60, source_out_tick=100)]
        request = {'action': 'roll', 'left_clip_id': 'l', 'right_clip_id': 'r', 'delta_tick': 10}
        self.rejects(value, request, 'EDIT_RANGE_HANDLE_SHORTFALL')
        result, plan = build_edit_plan(value, 'seq', dict(request, handle_policy='source'))
        self.assertEqual(clips(result)['l']['source_out_tick'], 70)
        self.assertEqual(clips(result)['r']['presentation_window']['offset_tick'], 10)
        self.assertEqual(positions(result), {'l': ('main', 20, 70), 'r': ('main', 70, 100)})
        self.assertEqual(len(plan['source_changes']), 1)

    def test_slide_true_handles_leave_middle_source_and_processing_unchanged(self):
        value = fixture(); value['sequences'][0]['tracks'][0]['clips'] = [
            clip('l', 20, 50, source_in_tick=20, source_out_tick=50),
            clip('v', 50, 70, source_in_tick=80, source_out_tick=100, reverse=True),
            clip('r', 70, 100, source_in_tick=120, source_out_tick=150)]
        result, plan = self.plan(value, 'slide', delta_tick=-10, handle_policy='source')
        middle = copy.deepcopy(clips(value)['v']); middle['timeline_start_tick'] -= 10
        self.assertEqual(clips(result)['v'], middle)
        self.assertEqual(clips(result)['r']['source_in_tick'], 110)
        self.assertEqual(len(plan['source_changes']), 1)

    def test_zero_source_actions_preserve_entire_project(self):
        for action, fields in [('slip', {'delta_source_tick': 0}), ('extend_source', {})]:
            value = fixture(True)
            result, plan = self.plan(value, action, **fields)
            self.assertEqual(result, value)
            self.assertEqual(plan['changes'], [])
            self.assertEqual(plan['source_changes'], [])


class SourceMediaTests(unittest.TestCase):
    call = _windows.ClipWindowTests.call
    setUpClass = _windows.ClipWindowTests.__dict__['setUpClass']
    clip = _windows.ClipWindowTests.clip
    saved = _windows.ClipWindowTests.saved
    pixels_and_samples = _windows.ClipWindowTests.pixels_and_samples
    same_media = _windows.ClipWindowTests.same_media

    def setUp(self):
        _windows.ClipWindowTests.setUp(self)
        self.seq['duration_tick'] = 6*TPS
        for t in self.seq['tracks']:
            t['clips'][0].update(timeline_start_tick=TPS, source_in_tick=2*TPS,
                                  source_out_tick=6*TPS, link_id='av')

    def apply(self, action, **fields):
        candidate, plan = build_edit_plan(self.project, self.sid, {'action': action, 'clip_id': 'v', **fields})
        validation = validate_project(self.root, candidate)
        self.assertTrue(validation['ok'], validation)
        return candidate, plan

    def test_real_linked_slip_matches_independent_manual_source_ranges(self):
        candidate, _ = self.apply('slip', delta_source_tick=TPS)
        expected = copy.deepcopy(self.project)
        for t in expected['sequences'][0]['tracks']:
            t['clips'][0].update(source_in_tick=3*TPS, source_out_tick=7*TPS)
        self.same_media(self.pixels_and_samples(candidate), self.pixels_and_samples(expected))

    def test_real_both_sided_extension_matches_manual_full_author(self):
        candidate, _ = self.apply('extend_source', head_tick=TPS, tail_tick=TPS)
        expected = copy.deepcopy(self.project)
        for t in expected['sequences'][0]['tracks']:
            t['clips'][0].update(source_in_tick=TPS, source_out_tick=7*TPS,
                                  timeline_start_tick=0, duration_tick=6*TPS)
        self.same_media(self.pixels_and_samples(candidate), self.pixels_and_samples(expected))

    def test_real_reverse_speed_extension_preserves_physical_source_choice(self):
        for t in self.seq['tracks']:
            t['clips'][0].update(reverse=True, speed=2, duration_tick=2*TPS)
        candidate, _ = self.apply('extend_source', head_tick=TPS//2, tail_tick=TPS//2)
        expected = copy.deepcopy(self.project)
        for t in expected['sequences'][0]['tracks']:
            t['clips'][0].update(source_in_tick=TPS, source_out_tick=7*TPS,
                                  timeline_start_tick=TPS//2, duration_tick=3*TPS)
        self.same_media(self.pixels_and_samples(candidate), self.pixels_and_samples(expected))

    def test_real_frozen_extension_reanchors_hold_and_effect_keys(self):
        for t in self.seq['tracks']:
            t['clips'][0].update(duration_tick=5*TPS, freeze={'at_tick': TPS, 'duration_tick': TPS, 'audio': 'silence'})
        self.seq['tracks'][0]['clips'][0]['effects'] = [{'type': 'brightness', 'parameters': {'brightness': 0},
            'keyframes': [{'property': 'brightness', 'keyframes': [{'at_tick': 0, 'value': 0, 'interpolation': 'linear'},
                             {'at_tick': 4*TPS, 'value': .2, 'interpolation': 'linear'}]}]}]
        candidate, _ = self.apply('extend_source', head_tick=TPS//2, tail_tick=TPS//2)
        expected = copy.deepcopy(self.project); expected['sequences'][0]['duration_tick'] = 13*TPS//2
        for t in expected['sequences'][0]['tracks']:
            t['clips'][0].update(source_in_tick=3*TPS//2, source_out_tick=13*TPS//2,
                                  timeline_start_tick=TPS//2, duration_tick=6*TPS)
            t['clips'][0]['freeze']['at_tick'] = 3*TPS//2
        keys = expected['sequences'][0]['tracks'][0]['clips'][0]['effects'][0]['keyframes'][0]['keyframes']
        keys[0]['at_tick'], keys[1]['at_tick'] = TPS//2, 9*TPS//2
        self.same_media(self.pixels_and_samples(candidate), self.pixels_and_samples(expected))

    def nested(self):
        child = copy.deepcopy(self.seq)
        child.update(id='child', duration_tick=8*TPS)
        for i, t in enumerate(child['tracks']):
            t['id'] = 'child'+str(i)
            t['clips'][0].update(id='child'+str(i)+'c', link_id='childav', timeline_start_tick=0,
                                 duration_tick=8*TPS, source_in_tick=0, source_out_tick=8*TPS)
            if t['kind'] == 'audio':
                t['clips'][0]['audio'] = {'volume': .75, 'fade_in': .2}
        self.project['sequences'].append(child)
        self.seq['tracks'][0]['clips'] = [{'id': 'v', 'sequence_id': 'child',
            'timeline_start_tick': TPS, 'duration_tick': 4*TPS,
            'source_in_tick': 2*TPS, 'source_out_tick': 6*TPS}]
        self.seq['tracks'][1]['clips'] = []

    def test_real_nested_extension_keeps_original_child_bus(self):
        self.nested()
        candidate, _ = self.apply('extend_source', head_tick=TPS, tail_tick=TPS)
        expected = copy.deepcopy(self.project)
        expected['sequences'][0]['tracks'][0]['clips'][0].update(source_in_tick=TPS, source_out_tick=7*TPS,
            timeline_start_tick=0, duration_tick=6*TPS)
        self.same_media(self.pixels_and_samples(candidate), self.pixels_and_samples(expected))

    def test_real_nested_curve_renormalization_is_explicit_and_matches_native_authoring(self):
        self.nested()
        self.seq['tracks'][0]['clips'][0]['speed_curve'] = [{'at_tick': 0, 'speed': 2}, {'at_tick': 4*TPS, 'speed': 2}]
        candidate, plan = self.apply('extend_source', tail_tick=TPS)
        self.assertEqual(plan['warnings'][0]['code'], 'SOURCE_EDIT_NESTED_CURVE_RENORMALIZED')
        expected = copy.deepcopy(self.project)
        expected['sequences'][0]['tracks'][0]['clips'][0].update(duration_tick=5*TPS, source_out_tick=8*TPS)
        self.same_media(self.pixels_and_samples(candidate), self.pixels_and_samples(expected))

    def test_real_slip_with_reverse_curve_and_freeze_keeps_author_automation(self):
        for t in self.seq['tracks']:
            t['clips'][0].update(reverse=True, duration_tick=5*TPS,
                freeze={'at_tick': TPS, 'duration_tick': TPS, 'audio': 'silence'},
                speed_curve=[{'at_tick': 0, 'speed': 1}, {'at_tick': 4*TPS, 'speed': 1}])
        candidate, _ = self.apply('slip', delta_source_tick=TPS)
        expected = copy.deepcopy(self.project)
        for t in expected['sequences'][0]['tracks']:
            t['clips'][0].update(source_in_tick=3*TPS, source_out_tick=7*TPS)
        self.same_media(self.pixels_and_samples(candidate), self.pixels_and_samples(expected))

    def test_cli_source_preview_hash_idempotency_and_late_batch_rollback(self):
        self.saved(); before = (self.root/'project.json').read_bytes()
        request = self.root/'source-edit.json'
        request.write_text(json.dumps({'action': 'slip', 'clip_id': 'v', 'delta_source_tick': TPS}), encoding='utf-8')
        preview = self.call('timeline', 'edit', '--project', self.root, '--input', request, '--dry-run')
        self.assertEqual(before, (self.root/'project.json').read_bytes())
        digest = preview['data']['plan']['base_project_sha256']
        self.call('timeline', 'edit', '--project', self.root, '--input', request,
                  '--expected-project-sha256', digest, '--idempotency-key', 'source-slip')
        after = (self.root/'project.json').read_bytes()
        self.call('timeline', 'edit', '--project', self.root, '--input', request,
                  '--expected-project-sha256', digest, '--idempotency-key', 'source-slip')
        self.assertEqual(after, (self.root/'project.json').read_bytes())

        self.call('timeline', 'edit', '--project', self.root, '--input', request,
                  '--expected-project-sha256', digest, expected=2)
        batch = self.root/'batch.json'; batch.write_text(json.dumps({'operations': [
            {'op': 'linked_edit', 'edit': {'action': 'extend_source', 'clip_id': 'v', 'tail_tick': TPS//2}},
            {'op': 'linked_edit', 'edit': {'action': 'slip', 'clip_id': 'v', 'delta_source_tick': 100*TPS}}]}), encoding='utf-8')
        result = self.call('timeline', 'compose', '--project', self.root, '--input', batch, expected=2)
        self.assertEqual(result['errors'][0]['code'], 'SOURCE_EDIT_HANDLE_SHORTFALL')
        self.assertEqual(after, (self.root/'project.json').read_bytes())


    def test_legacy_compose_slip_keeps_single_default_and_supports_explicit_linked(self):
        self.saved()
        request = self.root/'legacy-slip.json'
        request.write_text(json.dumps({'operations': [{'op': 'slip_clip', 'clip_id': 'v',
                                                       'delta_source_tick': TPS}]}), encoding='utf-8')
        self.call('timeline', 'compose', '--project', self.root, '--input', request)
        actual = json.loads((self.root/'project.json').read_text(encoding='utf-8'))
        self.assertEqual(actual['sequences'][0]['tracks'][0]['clips'][0]['source_in_tick'], 3*TPS)
        self.assertEqual(actual['sequences'][0]['tracks'][1]['clips'][0]['source_in_tick'], 2*TPS)
        self.saved()
        request.write_text(json.dumps({'operations': [{'op': 'slip_clip', 'clip_id': 'v',
                                                       'delta_source_tick': TPS, 'linked': True}]}), encoding='utf-8')
        self.call('timeline', 'compose', '--project', self.root, '--input', request)
        actual = json.loads((self.root/'project.json').read_text(encoding='utf-8'))
        self.assertEqual(actual['sequences'][0]['tracks'][1]['clips'][0]['source_in_tick'], 3*TPS)


if __name__ == '__main__':
    unittest.main()
