from __future__ import annotations

import copy
import hashlib
import json
import unittest

from ai_ad_editor.edit_planner import build_edit_plan, project_fingerprint
from ai_ad_editor.clip_windows import slice_clip
from ai_ad_editor.errors import AppError
from ai_ad_editor.validator import validate_project
import test_clip_windows as _window_tests


def clip(cid, a=0, b=80, **fields):
    return {'id': cid, 'asset_id': 'media', 'timeline_start_tick': a,
            'duration_tick': b-a, 'source_in_tick': 0, 'source_out_tick': b-a, **fields}


def track(tid, clips=(), kind='video', order=0, **fields):
    return {'id': tid, 'kind': kind, 'order': order, 'clips': list(clips), **fields}


def project(tracks=None, duration=100):
    return {'project': {'id': 'test'}, 'settings': {'timebase': {'ticks_per_second': 10,
            'display_fps': {'num': 10, 'den': 1}}},
            'assets': [{'id': 'media', 'kind': 'video', 'probe': {'duration_seconds': 20}}],
            'sequences': [{'id': 'seq', 'duration_tick': duration,
                'tracks': tracks or [track('main', [clip('v')])],
                'markers': [{'id': 'marker', 'at_tick': 7}]}]}


def incoming(cid='new', tid='main', a=0, b=10):
    return {'track_id': tid, 'clip': clip(cid, a, b)}


def positions(value):
    return {c['id']: (t['id'], c['timeline_start_tick'], c['timeline_start_tick']+c['duration_tick'])
            for s in value['sequences'] for t in s['tracks'] for c in t['clips']}


def handles(cid, a, b, offset, total=100, **fields):
    return clip(cid, a, b, source_out_tick=total,
                presentation_window={'version': 1, 'authored_start_tick': 0,
                                     'authored_duration_tick': total, 'offset_tick': offset}, **fields)


class RangeEditPlannerTests(unittest.TestCase):
    def plan(self, value, request):
        before = copy.deepcopy(value)
        result = build_edit_plan(value, 'seq', request)
        self.assertEqual(value, before)
        return result

    def rejects(self, value, request, code):
        before = copy.deepcopy(value)
        with self.assertRaises(AppError) as caught:
            build_edit_plan(value, 'seq', request)
        self.assertEqual(caught.exception.code, code)
        self.assertEqual(value, before)

    def test_insert_splits_linked_audio_and_keeps_author_payload(self):
        data = {'reverse': True, 'speed_curve': [{'at_tick': 0, 'speed': 1}, {'at_tick': 80, 'speed': 1}],
                'keyframes': [{'property': 'transform.opacity', 'keyframes': [{'at_tick': 70, 'value': .5, 'interpolation': 'linear'}]}]}
        value = project([track('main', [clip('v', link_id='av', **data)]),
                         track('voice', [clip('a', link_id='av')], 'audio', 1)])
        result, plan = self.plan(value, {'action': 'insert', 'at_tick': 10, 'items': [incoming()]})
        self.assertEqual(positions(result), {'v': ('main', 0, 10), 'v_after': ('main', 20, 90),
                         'new': ('main', 10, 20), 'a': ('voice', 0, 10), 'a_after': ('voice', 20, 90)})
        pieces = result['sequences'][0]['tracks'][0]['clips'][:2]
        for piece in pieces:
            for key in data:
                self.assertEqual(piece[key], data[key])
        self.assertEqual(pieces[1]['presentation_window']['offset_tick'], 10)
        self.assertEqual(result['sequences'][0]['duration_tick'], 110)
        self.assertIn('new', [c['clip_id'] for c in plan['changes'] if c['before'] is None])
        self.assertEqual(plan['base_project_sha256'], project_fingerprint(value))

    def test_overwrite_middle_retains_both_correct_source_sides(self):
        result, _ = self.plan(project(), {'action': 'overwrite', 'at_tick': 10, 'items': [incoming()]})
        self.assertEqual(positions(result), {'v': ('main', 0, 10), 'v_after': ('main', 20, 80), 'new': ('main', 10, 20)})
        right = next(c for c in result['sequences'][0]['tracks'][0]['clips'] if c['id'] == 'v_after')
        self.assertEqual(right['presentation_window']['offset_tick'], 20)

    def test_lift_preserves_gap_and_total_duration(self):
        result, _ = self.plan(project(), {'action': 'lift', 'at_tick': 10, 'duration_tick': 10, 'track_ids': ['main']})
        self.assertEqual(positions(result), {'v': ('main', 0, 10), 'v_after': ('main', 20, 80)})
        self.assertEqual(result['sequences'][0]['duration_tick'], 100)

    def test_extract_closes_exact_interval(self):
        result, _ = self.plan(project(), {'action': 'extract', 'at_tick': 10, 'duration_tick': 10, 'track_ids': ['main']})
        self.assertEqual(positions(result), {'v': ('main', 0, 10), 'v_after': ('main', 10, 70)})
        self.assertEqual(result['sequences'][0]['duration_tick'], 90)

    def test_extract_never_truncates_unselected_bed(self):
        value = project([track('main', [clip('v')]), track('bed', [clip('a', 0, 100)], 'audio', 1)])
        result, _ = self.plan(value, {'action': 'extract', 'at_tick': 10, 'duration_tick': 10, 'track_ids': ['main']})
        self.assertEqual(positions(result)['a'], ('bed', 0, 100))
        self.assertEqual(result['sequences'][0]['duration_tick'], 100)

    def test_whole_move_retimes_file_cues_but_not_existing_window(self):
        value = project([track('main', [clip('v', 10, 30)]),
            track('text', [clip('s', 10, 30, subtitle={'asset_uri': 'local://s.srt'}),
                           handles('w', 40, 60, 20, subtitle={'asset_uri': 'local://s.srt'})], 'subtitle', 1)])
        result, plan = self.plan(value, {'action': 'insert', 'at_tick': 0, 'items': [incoming()], 'options': {'sync': True}})
        text = {c['id']: c for c in result['sequences'][0]['tracks'][1]['clips']}
        self.assertEqual(text['s']['subtitle']['asset_time_offset_tick'], -10)
        self.assertNotIn('asset_time_offset_tick', text['w']['subtitle'])
        self.assertEqual(plan['retimed_subtitle_ids'], ['s'])

    def test_insert_past_end_includes_explicit_blank_range(self):
        result, _ = self.plan(project(), {'action': 'insert', 'at_tick': 130, 'duration_tick': 30, 'items': [incoming()]})
        self.assertEqual(result['sequences'][0]['duration_tick'], 160)
        self.assertEqual(positions(result)['new'], ('main', 130, 140))

    def test_overwrite_past_end_includes_explicit_trailing_blank(self):
        result, _ = self.plan(project(), {'action': 'overwrite', 'at_tick': 120, 'duration_tick': 30, 'items': [incoming()]})
        self.assertEqual(result['sequences'][0]['duration_tick'], 150)

    def test_extract_all_keeps_one_tick_empty_sequence(self):
        result, _ = self.plan(project(), {'action': 'extract', 'at_tick': 0, 'duration_tick': 100, 'track_ids': ['main']})
        self.assertEqual(positions(result), {})
        self.assertEqual(result['sequences'][0]['duration_tick'], 1)

    def test_lift_all_keeps_duration(self):
        result, _ = self.plan(project(), {'action': 'lift', 'at_tick': 0, 'duration_tick': 100, 'track_ids': ['main']})
        self.assertEqual(positions(result), {})
        self.assertEqual(result['sequences'][0]['duration_tick'], 100)

    def test_invalid_requests_reject_strictly(self):
        base = {'action': 'insert', 'at_tick': 10, 'items': [incoming()]}
        requests = [dict(base, at_tick=v) for v in (True, 1.5, None, -1)]
        requests += [dict(base, duration_tick=0), dict(base, mystery=True),
                     dict(base, options={'sync': 1}), dict(base, options={'ripple': True}),
                     dict(base, items=[]), dict(base, duration_tick=5),
                     {'action': 'lift', 'at_tick': 0, 'duration_tick': 1, 'track_ids': ['main', 'main']}]
        for request in requests:
            with self.subTest(request=request):
                self.rejects(project(), request, 'EDIT_RANGE_REQUEST_INVALID')
        self.rejects(project(), dict(base, action=[]), 'EDIT_REQUEST_INVALID')

    def test_range_past_end_rejects_without_clamp(self):
        self.rejects(project(), {'action': 'extract', 'at_tick': 95, 'duration_tick': 10, 'track_ids': ['main']}, 'EDIT_RANGE_OUTSIDE_SEQUENCE')

    def test_unknown_track_returns_structured_error(self):
        self.rejects(project(), {'action': 'insert', 'at_tick': 0, 'items': [incoming(tid='missing')]}, 'EDIT_TRACK_NOT_FOUND')

    def test_relative_incoming_offsets_and_explicit_group_tail(self):
        result, _ = self.plan(project(), {'action': 'insert', 'at_tick': 10, 'duration_tick': 30,
                                         'items': [incoming(a=5, b=15)]})
        self.assertEqual(positions(result)['new'], ('main', 15, 25))
        self.assertEqual(positions(result)['v_after'], ('main', 40, 110))
        self.assertEqual(result['sequences'][0]['duration_tick'], 130)

    def test_global_incoming_id_collision_includes_markers_assets_and_removed_ids(self):
        for cid in ('marker', 'media', 'seq', 'main', 'v'):
            with self.subTest(cid=cid):
                self.rejects(project(), {'action': 'overwrite', 'at_tick': 0, 'duration_tick': 100, 'items': [incoming(cid)]}, 'EDIT_RANGE_ID_CONFLICT')

    def test_incoming_ids_reserved_before_generated_cut_ids(self):
        result, _ = self.plan(project(), {'action': 'insert', 'at_tick': 10, 'items': [incoming('v_after')]})
        self.assertIn('v_after_2', positions(result))
        self.assertEqual(positions(result)['v_after'], ('main', 10, 20))

    def test_duplicate_incoming_id_rejects(self):
        self.rejects(project(), {'action': 'insert', 'at_tick': 10, 'items': [incoming(), incoming()]}, 'EDIT_RANGE_ID_CONFLICT')

    def test_incoming_invalid_link_ids_reject_before_hash_lookup(self):
        for bad in ([], {}, True, 1, '', 'contains space'):
            item = incoming(); item['clip']['link_id'] = bad
            self.rejects(project(), {'action': 'insert', 'at_tick': 10, 'items': [item]}, 'EDIT_RANGE_REQUEST_INVALID')
        item = incoming(); item['clip']['link_id'] = None
        result, _ = self.plan(project(), {'action': 'insert', 'at_tick': 10, 'items': [item]})
        self.assertIn('new', positions(result))

    def test_incoming_cannot_join_existing_link_group(self):
        value = project([track('main', [clip('v', link_id='existing')])])
        item = incoming(); item['clip']['link_id'] = 'existing'
        self.rejects(value, {'action': 'insert', 'at_tick': 10, 'items': [item]}, 'EDIT_RANGE_LINK_CONFLICT')

    def test_overlapping_incoming_requires_explicit_track_policy(self):
        items = [incoming('n1'), incoming('n2', a=5, b=15)]
        self.rejects(project(), {'action': 'insert', 'at_tick': 10, 'items': items}, 'EDIT_RANGE_INCOMING_OVERLAP')
        value = project(); value['sequences'][0]['tracks'][0]['overlap_policy'] = 'allow'
        result, plan = self.plan(value, {'action': 'insert', 'at_tick': 10, 'items': items})
        self.assertEqual(positions(result)['n2'], ('main', 15, 25))
        self.assertEqual(plan['new_track_ids'], [])

    def test_locked_empty_target_rejects(self):
        value = project([track('main', [], locked=True)])
        self.rejects(value, {'action': 'insert', 'at_tick': 0, 'items': [incoming()]}, 'EDIT_TRACK_LOCKED')

    def test_sync_keeps_locked_bed_and_opted_out_track(self):
        value = project([track('main', [clip('v')]), track('bed', [clip('bed')], 'audio', 1, locked=True),
                         track('voice', [clip('a')], 'audio', 2, sync_lock=False)])
        result, _ = self.plan(value, {'action': 'insert', 'at_tick': 10, 'items': [incoming()], 'options': {'sync': True}})
        self.assertEqual(positions(result)['bed'], ('bed', 0, 80))
        self.assertEqual(positions(result)['a'], ('voice', 0, 80))

    def test_locked_linked_member_rejects_atomically(self):
        value = project([track('main', [clip('v', link_id='av')]),
                         track('voice', [clip('a', link_id='av')], 'audio', 1, locked=True)])
        self.rejects(value, {'action': 'insert', 'at_tick': 10, 'items': [incoming()]}, 'EDIT_TRACK_LOCKED')

    def test_linkage_moves_rider_but_keeps_multi_cut_bed(self):
        value = project([track('main', [clip('a', 0, 20), clip('b', 20, 40), clip('c', 40, 80)]),
                         track('side', [clip('title', 45, 50)], 'video', 1),
                         track('bed', [clip('music', 0, 80)], 'audio', 2)])
        result, _ = self.plan(value, {'action': 'insert', 'at_tick': 10, 'items': [incoming()], 'options': {'linkage': True}})
        self.assertEqual(positions(result)['title'], ('side', 55, 60))
        self.assertEqual(positions(result)['music'], ('bed', 0, 80))

    def test_link_closure_reaches_main_and_riders_from_audio_selection(self):
        value = project([track('main', [clip('v', 20, 40, link_id='av')]),
                         track('voice', [clip('a', 20, 40, link_id='av')], 'audio', 1),
                         track('side', [clip('title', 25, 30)], 'video', 2)])
        result, _ = self.plan(value, {'action': 'insert', 'at_tick': 10, 'items': [incoming(tid='voice')], 'options': {'linkage': True}})
        self.assertEqual(positions(result)['title'], ('side', 35, 40))

    def collision_project(self, audio=False):
        return project([track('main', [clip('a', 0, 10), clip('b', 10, 20), clip('c', 20, 30), clip('d', 30, 40)]),
            track('side', [clip('rider', 16, 18), clip('anchored', 18, 40)],
                  'audio' if audio else 'video', 1, audio={'effects': [{'type': 'lowpass', 'frequency': 400}]} if audio else {})])

    def test_rider_collision_uses_reviewable_processing_equivalent_lane(self):
        result, plan = self.plan(self.collision_project(), {'action': 'insert', 'at_tick': 0, 'items': [incoming(b=5)], 'options': {'linkage': True}})
        self.assertTrue(plan['new_track_ids'])
        self.assertIn(positions(result)['rider'][0], plan['new_track_ids'])
        self.assertEqual(positions(result)['anchored'], ('side', 18, 40))

    def test_effect_bus_collision_rejects_instead_of_changing_sound(self):
        self.rejects(self.collision_project(True), {'action': 'insert', 'at_tick': 0, 'items': [incoming(b=5)], 'options': {'linkage': True}}, 'EDIT_AUDIO_BUS_RELOCATION_UNSUPPORTED')

    def test_cutting_tracking_source_rejects(self):
        value = project([track('main', [clip('v')]), track('side', [clip('label', tracking_binding={'source_clip_id': 'v'})], 'video', 1)])
        self.rejects(value, {'action': 'lift', 'at_tick': 10, 'duration_tick': 10, 'track_ids': ['main']}, 'EDIT_RANGE_BINDING_UNSUPPORTED')

    def test_removing_bound_source_without_label_rejects(self):
        value = project([track('main', [clip('v')]), track('side', [clip('label', tracking_binding={'source_clip_id': 'v'})], 'video', 1)])
        self.rejects(value, {'action': 'lift', 'at_tick': 0, 'duration_tick': 100, 'track_ids': ['main']}, 'EDIT_BINDING_SOURCE_REMOVED')

    def transitioned(self):
        value = project([track('main', [clip('a', 0, 20), clip('b', 20, 40)])])
        value['sequences'][0]['source_transitions'] = [{'id': 'transition', 'type': 'dissolve', 'duration_tick': 2,
            'from_clip_id': 'a', 'to_clip_id': 'b', 'audio_pairs': []}]
        return value

    def test_removing_entire_transition_removes_declaration(self):
        result, plan = self.plan(self.transitioned(), {'action': 'lift', 'at_tick': 0, 'duration_tick': 40, 'track_ids': ['main']})
        self.assertEqual(result['sequences'][0]['source_transitions'], [])
        self.assertEqual(plan['removed_transition_ids'], ['transition'])

    def test_partial_transition_endpoint_cut_rejects(self):
        self.rejects(self.transitioned(), {'action': 'lift', 'at_tick': 5, 'duration_tick': 5, 'track_ids': ['main']}, 'EDIT_RANGE_TRANSITION_UNSUPPORTED')

    def test_inserting_at_declared_transition_cut_rejects(self):
        self.rejects(self.transitioned(), {'action': 'insert', 'at_tick': 20, 'items': [incoming()]}, 'EDIT_RANGE_TRANSITION_UNSUPPORTED')

    def test_whole_transition_group_moves_without_reauthoring(self):
        result, _ = self.plan(self.transitioned(), {'action': 'insert', 'at_tick': 0, 'items': [incoming()]})
        self.assertEqual(positions(result)['a'], ('main', 10, 30))
        self.assertEqual(positions(result)['b'], ('main', 30, 50))
        self.assertEqual(result['sequences'][0]['source_transitions'], self.transitioned()['sequences'][0]['source_transitions'])

    def roll_project(self, linked=False):
        tracks = [track('main', [handles('l', 0, 20, 10, link_id='left'), handles('r', 20, 40, 30, link_id='right')])]
        if linked:
            tracks.append(track('voice', [handles('al', 0, 20, 10, link_id='left'), handles('ar', 20, 40, 30, link_id='right')], 'audio', 1))
        return project(tracks, 40)

    def test_roll_reselects_retained_handles_and_keeps_total(self):
        result, plan = self.plan(self.roll_project(), {'action': 'roll', 'left_clip_id': 'l', 'right_clip_id': 'r', 'delta_tick': 5})
        self.assertEqual(positions(result), {'l': ('main', 0, 25), 'r': ('main', 25, 40)})
        clips = result['sequences'][0]['tracks'][0]['clips']
        self.assertEqual([c['presentation_window']['offset_tick'] for c in clips], [10, 35])
        self.assertEqual(result['sequences'][0]['duration_tick'], 40)
        self.assertEqual(plan['cut_pairs'], [{'left_clip_id': 'l', 'right_clip_id': 'r'}])

    def test_negative_roll_keeps_correct_head(self):
        result, _ = self.plan(self.roll_project(), {'action': 'roll', 'left_clip_id': 'l', 'right_clip_id': 'r', 'delta_tick': -5})
        self.assertEqual(positions(result)['r'], ('main', 15, 40))
        self.assertEqual(result['sequences'][0]['tracks'][0]['clips'][1]['presentation_window']['offset_tick'], 25)

    def test_roll_updates_linked_audio_cut_pairs(self):
        result, plan = self.plan(self.roll_project(True), {'action': 'roll', 'left_clip_id': 'l', 'right_clip_id': 'r', 'delta_tick': 5})
        self.assertEqual(positions(result)['al'], ('voice', 0, 25))
        self.assertEqual(positions(result)['ar'], ('voice', 25, 40))
        self.assertEqual(len(plan['cut_pairs']), 2)

    def test_roll_shared_split_link_group_selects_cut_sides(self):
        value = self.roll_project(True)
        for t in value['sequences'][0]['tracks']:
            for c in t['clips']: c['link_id'] = 'all'
        result, _ = self.plan(value, {'action': 'roll', 'left_clip_id': 'l', 'right_clip_id': 'r', 'delta_tick': 5})
        self.assertEqual(positions(result)['ar'], ('voice', 25, 40))

    def test_roll_handle_shortfall_and_empty_side_reject(self):
        value = project([track('main', [clip('l', 0, 20), clip('r', 20, 40)])], 40)
        self.rejects(value, {'action': 'roll', 'left_clip_id': 'l', 'right_clip_id': 'r', 'delta_tick': 5}, 'EDIT_RANGE_HANDLE_SHORTFALL')
        self.rejects(self.roll_project(), {'action': 'roll', 'left_clip_id': 'l', 'right_clip_id': 'r', 'delta_tick': -20}, 'EDIT_RANGE_EMPTY_SIDE')

    def test_roll_incomplete_link_pair_rejects(self):
        value = self.roll_project(True); value['sequences'][0]['tracks'][1]['clips'].pop()
        self.rejects(value, {'action': 'roll', 'left_clip_id': 'l', 'right_clip_id': 'r', 'delta_tick': 5}, 'EDIT_RANGE_LINK_GEOMETRY')

    def test_roll_sync_reaches_unlinked_exact_cut_pairs(self):
        value = self.roll_project(True)
        for c in value['sequences'][0]['tracks'][1]['clips']: c.pop('link_id')
        result, _ = self.plan(value, {'action': 'roll', 'left_clip_id': 'l', 'right_clip_id': 'r', 'delta_tick': 5, 'options': {'sync': True}})
        self.assertEqual(positions(result)['ar'], ('voice', 25, 40))
        value['sequences'][0]['tracks'][1]['sync_lock'] = False
        result, _ = self.plan(value, {'action': 'roll', 'left_clip_id': 'l', 'right_clip_id': 'r', 'delta_tick': 5, 'options': {'sync': True}})
        self.assertEqual(positions(result)['ar'], ('voice', 20, 40))

    def slide_project(self, linked=False):
        tracks = [track('main', [handles('l', 0, 20, 0), clip('m', 20, 40), handles('r', 40, 60, 30)])]
        if linked:
            tracks.append(track('voice', [handles('al', 0, 20, 0), clip('am', 20, 40), handles('ar', 40, 60, 30)], 'audio', 1))
            for t in tracks:
                for c, group in zip(t['clips'], ['left', 'middle', 'right']): c['link_id'] = group
        return project(tracks, 60)

    def test_slide_moves_body_unchanged_and_adjusts_both_neighbors(self):
        value = self.slide_project()
        result, _ = self.plan(value, {'action': 'slide', 'clip_id': 'm', 'delta_tick': 5})
        self.assertEqual(positions(result), {'l': ('main', 0, 25), 'm': ('main', 25, 45), 'r': ('main', 45, 60)})
        actual = result['sequences'][0]['tracks'][0]['clips'][1]
        expected = copy.deepcopy(value['sequences'][0]['tracks'][0]['clips'][1]); expected['timeline_start_tick'] += 5
        self.assertEqual(actual, expected)

    def test_slide_keeps_linked_audio_middle_and_both_edges(self):
        result, plan = self.plan(self.slide_project(True), {'action': 'slide', 'clip_id': 'm', 'delta_tick': 5})
        self.assertEqual(positions(result)['am'], ('voice', 25, 45))
        self.assertEqual(positions(result)['ar'], ('voice', 45, 60))
        self.assertEqual(len(plan['cut_pairs']), 2)

    def test_slide_sync_and_main_riders_have_explicit_different_scopes(self):
        value = self.slide_project(True)
        for t in value['sequences'][0]['tracks']:
            for c in t['clips']: c.pop('link_id', None)
        value['sequences'][0]['tracks'].append(track('title', [clip('label', 25, 30)], 'video', 2, sync_lock=False))
        result, _ = self.plan(value, {'action': 'slide', 'clip_id': 'm', 'delta_tick': 5, 'options': {'sync': True, 'linkage': True}})
        self.assertEqual(positions(result)['am'], ('voice', 25, 45))
        self.assertEqual(positions(result)['label'], ('title', 30, 35))

    def test_slide_requires_continuous_neighbors_and_available_handles(self):
        value = self.slide_project(); value['sequences'][0]['tracks'][0]['clips'][0]['timeline_start_tick'] = 1
        self.rejects(value, {'action': 'slide', 'clip_id': 'm', 'delta_tick': 5}, 'EDIT_RANGE_CUT_INVALID')
        value = self.slide_project(); value['sequences'][0]['tracks'][0]['clips'][2]['presentation_window']['offset_tick'] = 0
        self.rejects(value, {'action': 'slide', 'clip_id': 'm', 'delta_tick': -5}, 'EDIT_RANGE_HANDLE_SHORTFALL')

    def test_zero_roll_and_slide_are_actual_noops(self):
        for value, request in [(self.roll_project(), {'action': 'roll', 'left_clip_id': 'l', 'right_clip_id': 'r', 'delta_tick': 0}),
                               (self.slide_project(), {'action': 'slide', 'clip_id': 'm', 'delta_tick': 0})]:
            result, plan = self.plan(value, request)
            self.assertEqual(result, value)
            self.assertEqual(plan['changes'], [])

    def test_unknown_clip_returns_structured_error(self):
        self.rejects(project(), {'action': 'slide', 'clip_id': 'missing', 'delta_tick': 1}, 'EDIT_CLIP_NOT_FOUND')


class RangeEditMediaTests(unittest.TestCase):
    call = _window_tests.ClipWindowTests.call
    setUp = _window_tests.ClipWindowTests.setUp
    setUpClass = _window_tests.ClipWindowTests.__dict__['setUpClass']
    clip = _window_tests.ClipWindowTests.clip
    saved = _window_tests.ClipWindowTests.saved
    pixels_and_samples = _window_tests.ClipWindowTests.pixels_and_samples
    same_media = _window_tests.ClipWindowTests.same_media

    def req(self, action='insert', **extra):
        return {'action': action, 'at_tick': 90000, 'items': [
            {'track_id': self.seq['tracks'][0]['id'], 'clip': {**self.clip('newv', self.video), 'source_in_tick': 6*90000, 'source_out_tick': 7*90000, 'duration_tick': 90000}},
            {'track_id': self.seq['tracks'][1]['id'], 'clip': {**self.clip('newa', self.audio), 'source_in_tick': 6*90000, 'source_out_tick': 7*90000, 'duration_tick': 90000}}], **extra}

    def incoming_media(self):
        value = copy.deepcopy(self.project)
        seq = value['sequences'][0]; seq['duration_tick'] = 90000
        for track, item in zip(seq['tracks'], self.req()['items']): track['clips'] = [item['clip']]
        return self.pixels_and_samples(value)

    def test_real_insert_preserves_frames_and_exact_pcm(self):
        before = self.pixels_and_samples(self.project); new = self.incoming_media()
        result, _ = build_edit_plan(self.project, self.sid, self.req())
        self.assertTrue(validate_project(self.root, result)['ok'])
        actual = self.pixels_and_samples(result); byte = 48000*2*4
        self.same_media(actual, (before[0][:10]+new[0]+before[0][10:], before[1][:byte]+new[1]+before[1][byte:]))

    def test_real_overwrite_reverse_curve_animation_keeps_authored_output(self):
        video, audio = self.seq['tracks'][0]['clips'][0], self.seq['tracks'][1]['clips'][0]
        for item in (video, audio):
            item['reverse'] = True
            item['speed_curve'] = {'keyframes': [{'at_tick': 0, 'speed': .5, 'interpolation': 'ease_in_out'}, {'at_tick': 4*90000, 'speed': 1.5, 'interpolation': 'linear'}]}
        video['keyframes'] = [{'property': 'transform.position.x', 'keyframes': [{'at_tick': 0, 'value': .5, 'interpolation': 'ease_in_out'}, {'at_tick': 4*90000, 'value': .65, 'interpolation': 'linear'}]}]
        audio['audio'] = {'fade_in': .3, 'fade_out': .4}
        before = self.pixels_and_samples(self.project); new = self.incoming_media()
        disabled = copy.deepcopy(self.project)
        disabled['sequences'][0]['tracks'][0]['clips'][0].pop('keyframes')
        self.assertNotEqual(hashlib.sha256(b''.join(before[0])).hexdigest(),
                            hashlib.sha256(b''.join(self.pixels_and_samples(disabled)[0])).hexdigest())
        result, _ = build_edit_plan(self.project, self.sid, self.req('overwrite'))
        actual = self.pixels_and_samples(result); byte = 48000*2*4
        self.same_media(actual, (before[0][:10]+new[0]+before[0][20:], before[1][:byte]+new[1]+before[1][2*byte:]))

    def test_real_lift_and_extract_select_correct_original_ranges(self):
        before = self.pixels_and_samples(self.project); byte = 48000*2*4
        for action in ('lift', 'extract'):
            result, _ = build_edit_plan(self.project, self.sid, {'action': action, 'at_tick': 90000,
                'duration_tick': 90000, 'track_ids': [t['id'] for t in self.seq['tracks']]})
            actual = self.pixels_and_samples(result)
            if action == 'extract': expected = (before[0][:10]+before[0][20:], before[1][:byte]+before[1][2*byte:])
            else: expected = (before[0][:10]+[bytes(len(before[0][0]))]*10+before[0][20:], before[1][:byte]+bytes(byte)+before[1][2*byte:])
            self.same_media(actual, expected)

    def test_real_nested_insert_preserves_processed_child_bus(self):
        before = self.pixels_and_samples(self.project)
        ref = copy.deepcopy(self.project); refseq = ref['sequences'][0]; refseq['duration_tick'] = 90000
        for t, item in zip(refseq['tracks'], self.req()['items']): t['clips'] = [item['clip']]
        refseq['tracks'][1]['audio'] = {'volume': .6}
        child_media = self.pixels_and_samples(ref)
        value = copy.deepcopy(self.project); child = copy.deepcopy(refseq); child['id'] = 'insert_child'
        for t in child['tracks']: t['id'] = 'child_' + t['id']
        value['sequences'].append(child)
        container = {'id': 'insert_group', 'sequence_id': 'insert_child', 'timeline_start_tick': 0,
                     'duration_tick': 90000, 'source_in_tick': 0, 'source_out_tick': 90000}
        result, _ = build_edit_plan(value, self.sid, {'action': 'insert', 'at_tick': 90000,
            'items': [{'track_id': self.seq['tracks'][0]['id'], 'clip': container}], 'options': {'sync': True}})
        validation = validate_project(self.root, result)
        self.assertTrue(validation['ok'], validation)
        byte = 48000*2*4
        self.same_media(self.pixels_and_samples(result),
                        (before[0][:10]+child_media[0]+before[0][10:], before[1][:byte]+child_media[1]+before[1][byte:]))

    def author(self, prefix, source_start, duration=4*90000, reverse=False):
        value = copy.deepcopy(self.project)
        seq = value['sequences'][0]; seq['duration_tick'] = duration
        for t, asset in zip(seq['tracks'], [self.video, self.audio]):
            c = self.clip(prefix + ('v' if t['kind'] == 'video' else 'a'), asset)
            c.update(source_in_tick=source_start, source_out_tick=source_start+duration,
                     duration_tick=duration, reverse=reverse, link_id=prefix)
            if t['kind'] == 'video':
                c['keyframes'] = [{'property': 'transform.position.x', 'keyframes': [
                    {'at_tick': 0, 'value': .5, 'interpolation': 'ease_in_out'},
                    {'at_tick': duration, 'value': .65, 'interpolation': 'linear'}]}]
            else:
                c['audio'] = {'fade_in': .3, 'fade_out': .4}
            t['clips'] = [c]
        return value

    def test_real_roll_uses_full_original_author_handles_for_picture_and_audio(self):
        left, right = self.author('L', 90000), self.author('R', 3*90000, reverse=True)
        lmedia, rmedia = self.pixels_and_samples(left), self.pixels_and_samples(right)
        value = copy.deepcopy(left)
        for target, lt, rt in zip(value['sequences'][0]['tracks'], left['sequences'][0]['tracks'], right['sequences'][0]['tracks']):
            target['clips'] = [slice_clip(lt['clips'][0], 0, 2*90000),
                               slice_clip(rt['clips'][0], 2*90000, 4*90000, start=2*90000)]
        result, plan = build_edit_plan(value, self.sid, {'action': 'roll', 'left_clip_id': 'Lv', 'right_clip_id': 'Rv', 'delta_tick': 90000})
        self.assertTrue(validate_project(self.root, result)['ok'])
        actual = self.pixels_and_samples(result); byte = 3*48000*2*4
        self.same_media(actual, (lmedia[0][:30]+rmedia[0][30:], lmedia[1][:byte]+rmedia[1][byte:]))
        self.assertEqual(len(plan['cut_pairs']), 2)

    def test_real_slide_keeps_middle_processing_and_reselects_both_original_neighbors(self):
        left, middle, right = self.author('L', 90000), self.author('M', 5*90000, 90000), self.author('R', 3*90000, reverse=True)
        lmedia, mmedia, rmedia = self.pixels_and_samples(left), self.pixels_and_samples(middle), self.pixels_and_samples(right)
        value = copy.deepcopy(left)
        for target, lt, mt, rt in zip(value['sequences'][0]['tracks'], left['sequences'][0]['tracks'], middle['sequences'][0]['tracks'], right['sequences'][0]['tracks']):
            mid = copy.deepcopy(mt['clips'][0]); mid['timeline_start_tick'] = 90000
            target['clips'] = [slice_clip(lt['clips'][0], 0, 90000), mid,
                               slice_clip(rt['clips'][0], 2*90000, 4*90000, start=2*90000)]
        result, _ = build_edit_plan(value, self.sid, {'action': 'slide', 'clip_id': 'Mv', 'delta_tick': 45000})
        self.assertTrue(validate_project(self.root, result)['ok'])
        actual = self.pixels_and_samples(result); left_byte, right_byte = 72000*2*4, 120000*2*4
        self.same_media(actual, (lmedia[0][:15]+mmedia[0]+rmedia[0][25:], lmedia[1][:left_byte]+mmedia[1]+rmedia[1][right_byte:]))

    def test_cli_preview_hash_idempotency_and_compose_rollback(self):
        self.saved(); request = self.root/'request.json'
        request.write_text(json.dumps(self.req()), encoding='utf-8')
        old = (self.root/'project.json').read_bytes()
        planned = self.call('timeline', 'edit', '--project', self.root, '--input', request, '--dry-run')
        self.assertEqual((self.root/'project.json').read_bytes(), old)
        digest = planned['data']['plan']['base_project_sha256']
        self.call('timeline', 'edit', '--project', self.root, '--input', request, '--expected-project-sha256', digest, '--idempotency-key', 'insert')
        saved = (self.root/'project.json').read_bytes()
        self.call('timeline', 'edit', '--project', self.root, '--input', request, '--expected-project-sha256', digest, '--idempotency-key', 'insert')
        self.assertEqual((self.root/'project.json').read_bytes(), saved)
        rejected = self.call('timeline', 'edit', '--project', self.root, '--input', request, '--expected-project-sha256', digest, expected=2)
        self.assertEqual(rejected['errors'][0]['code'], 'EDIT_PROJECT_CHANGED')
        request.write_text(json.dumps({'operations': [{'op': 'linked_edit', 'edit': {
            'action': 'lift', 'at_tick': 90000, 'duration_tick': 90000,
            'track_ids': [self.seq['tracks'][0]['id']]}}, {'op': 'unknown_operation'}]}), encoding='utf-8')
        self.call('timeline', 'compose', '--project', self.root, '--input', request, expected=2)
        self.assertEqual((self.root/'project.json').read_bytes(), saved)


if __name__ == '__main__':
    unittest.main()
