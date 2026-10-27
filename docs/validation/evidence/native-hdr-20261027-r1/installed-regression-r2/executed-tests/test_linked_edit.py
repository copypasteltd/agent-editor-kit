from __future__ import annotations

import contextlib
import copy
import importlib
import io
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image, ImageFont

from ai_ad_editor.cli import main
from ai_ad_editor.errors import AppError
from ai_ad_editor.project import create_project, save_project
from ai_ad_editor.utils import sha256_file
from ai_ad_editor.validator import validate_project


def planner():
    # Keep discovery possible against the fixed previous product too.
    return importlib.import_module('ai_ad_editor.edit_planner')


def clip(cid, start, end, **fields):
    return {'id': cid, 'asset_id': 'media', 'timeline_start_tick': start,
            'duration_tick': end-start, 'source_in_tick': 0, 'source_out_tick': end-start, **fields}


def track(tid, clips, kind='video', order=0, **fields):
    return {'id': tid, 'kind': kind, 'order': order, 'clips': clips, **fields}


def project(tracks):
    return {'project': {'id': 'test'}, 'settings': {'timebase': {'ticks_per_second': 90000,
            'display_fps': {'num': 30000, 'den': 1001}}}, 'assets': [],
            'sequences': [{'id': 'seq', 'name': 'edit', 'duration_tick': 100,
                           'tracks': tracks, 'markers': [{'id': 'marker', 'at_tick': 7}]}]}


def positions(p):
    return {c['id']: (t['id'], c['timeline_start_tick'], c['timeline_start_tick']+c['duration_tick'])
            for s in p['sequences'] for t in s['tracks'] for c in t['clips']}


def invoke(*argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = main(list(argv))
        except SystemExit as exc:
            return exc.code, {'errors': [{'code': 'CLI_USAGE_ERROR'}], 'stderr': err.getvalue()}
    return code, json.loads(out.getvalue())


class LinkedEditPlannerTests(unittest.TestCase):
    def plan(self, p, request):
        frozen = copy.deepcopy(p)
        result = planner().build_edit_plan(p, 'seq', request)
        self.assertEqual(p, frozen)
        return result

    def rejects(self, p, request, code):
        frozen = copy.deepcopy(p)
        with self.assertRaises(AppError) as caught:
            planner().build_edit_plan(p, 'seq', request)
        self.assertEqual(caught.exception.code, code)
        self.assertEqual(p, frozen)

    def test_sync_remove_moves_voice_but_preserves_locked_bed(self):
        p = project([track('main', [clip('intro', 0, 10), clip('delete', 10, 30), clip('outro', 30, 50)]),
                     track('voice', [clip('v', 30, 50)], 'audio', 1),
                     track('bed', [clip('music', 0, 50)], 'audio', 2, locked=True)])
        result, plan = self.plan(p, {'action': 'remove', 'clip_ids': ['delete'], 'options': {'ripple': True, 'sync': True}})
        self.assertEqual(positions(result), {'intro': ('main', 0, 10), 'outro': ('main', 10, 30),
                                            'v': ('voice', 10, 30), 'music': ('bed', 0, 50)})
        self.assertEqual(plan['short_tick'], 0)
        self.assertEqual(result['sequences'][0]['markers'], p['sequences'][0]['markers'])

    def test_linkage_deletes_rider_keeps_long_bed_and_moves_later_title(self):
        p = project([track('main', [clip('a', 0, 10), clip('b', 10, 20), clip('c', 20, 30), clip('d', 30, 40)]),
                     track('titles', [clip('on_b', 12, 18), clip('on_d', 32, 38)], 'subtitle', 1),
                     track('bed', [clip('music', 2, 39)], 'audio', 2)])
        result, plan = self.plan(p, {'action': 'remove', 'clip_ids': ['b'], 'options': {'ripple': 'main', 'linkage': True}})
        pos = positions(result)
        self.assertNotIn('on_b', pos)
        self.assertEqual(pos['on_d'], ('titles', 22, 28))
        self.assertEqual(pos['music'], ('bed', 2, 39))
        self.assertIn('music', plan['anchored_clip_ids'])

    def test_sync_wins_over_linkage_and_does_not_delete_rider(self):
        p = project([track('main', [clip('a', 0, 10), clip('b', 10, 20), clip('c', 20, 30)]),
                     track('titles', [clip('rider', 12, 18)], 'subtitle', 1)])
        result, _ = self.plan(p, {'action': 'remove', 'clip_ids': ['b'], 'options': {'ripple': True, 'sync': True, 'linkage': True}})
        self.assertEqual(positions(result)['rider'], ('titles', 12, 18))

    def test_track_sync_opt_out_stays_but_explicit_selection_still_edits(self):
        p = project([track('main', [clip('a', 0, 10), clip('b', 10, 20), clip('c', 20, 30)]),
                     track('voice', [clip('v', 20, 30)], 'audio', 1, sync_lock=False)])
        result, _ = self.plan(p, {'action': 'remove', 'clip_ids': ['b'], 'options': {'ripple': True, 'sync': True}})
        self.assertEqual(positions(result)['v'], ('voice', 20, 30))
        result, _ = self.plan(p, {'action': 'remove', 'clip_ids': ['v'], 'options': {'ripple': True, 'sync': True}})
        self.assertNotIn('v', positions(result))

    def test_sync_shortfall_uses_common_room_without_single_track_fallback(self):
        p = project([track('main', [clip('a', 0, 10), clip('b', 30, 40)]),
                     track('voice', [clip('cross', 5, 25), clip('v', 35, 45)], 'audio', 1)])
        result, plan = self.plan(p, {'action': 'close_gap', 'track_id': 'main', 'at_tick': 20, 'options': {'sync': True}})
        self.assertEqual(plan['short_tick'], 10)
        self.assertEqual(positions(result)['b'], ('main', 20, 30))
        self.assertEqual(positions(result)['v'], ('voice', 25, 35))
        self.assertEqual(positions(result)['cross'], ('voice', 5, 25))

    def test_multiple_removed_spans_are_unioned_then_closed_backwards(self):
        p = project([track('main', [clip('a', 0, 10), clip('b', 10, 20), clip('c', 20, 30), clip('d', 30, 40)]),
                     track('voice', [clip('b_audio', 10, 20), clip('v', 30, 40)], 'audio', 1)])
        result, plan = self.plan(p, {'action': 'remove', 'clip_ids': ['b', 'b_audio'], 'options': {'ripple': True, 'sync': True}})
        self.assertEqual(positions(result)['d'], ('main', 20, 30))
        self.assertEqual(positions(result)['v'], ('voice', 20, 30))
        self.assertEqual([s['delta_tick'] for s in plan['shifts']], [-10])

    def test_single_tick_gaps_and_fragments_survive_fractional_fps(self):
        p = project([track('main', [clip('a', 1, 2), clip('b', 3, 4), clip('c', 5, 6)])])
        result, plan = self.plan(p, {'action': 'close_gaps'})
        self.assertEqual(positions(result), {'a': ('main', 0, 1), 'b': ('main', 1, 2), 'c': ('main', 2, 3)})
        self.assertEqual(plan['short_tick'], 0)

    def test_link_merges_groups_and_unlink_clears_orphan_without_trimming_tail(self):
        p = project([track('main', [clip('a', 0, 10, link_id='g1'), clip('b', 10, 20, link_id='g2')]),
                     track('voice', [clip('aa', 0, 10, link_id='g1'), clip('bb', 10, 20, link_id='g2')], 'audio', 1)])
        result, plan = self.plan(p, {'action': 'link', 'clip_ids': ['a', 'b']})
        self.assertEqual(set(plan['selected_clip_ids']), {'a', 'b', 'aa', 'bb'})
        self.assertEqual({c['link_id'] for t in result['sequences'][0]['tracks'] for c in t['clips']}, {'g1'})
        self.assertEqual(result['sequences'][0]['duration_tick'], 100)
        result, _ = self.plan(result, {'action': 'unlink', 'clip_ids': ['a', 'b', 'aa']})
        self.assertTrue(all('link_id' not in c for t in result['sequences'][0]['tracks'] for c in t['clips']))

    def test_locked_link_member_rejects_whole_edit(self):
        p = project([track('main', [clip('a', 0, 10, link_id='g')]),
                     track('voice', [clip('v', 0, 10, link_id='g')], 'audio', 1, locked=True)])
        for request in ({'action': 'remove', 'clip_ids': ['a']}, {'action': 'shift', 'clip_ids': ['a'], 'delta_tick': 1},
                        {'action': 'unlink', 'clip_ids': ['a']}, {'action': 'link', 'clip_ids': ['a', 'v']}):
            with self.subTest(request=request):
                self.rejects(p, request, 'EDIT_TRACK_LOCKED')

    def test_shift_rejects_negative_and_main_track_collision_atomically(self):
        p = project([track('main', [clip('a', 0, 10), clip('b', 20, 30)])])
        self.rejects(p, {'action': 'shift', 'clip_ids': ['a'], 'delta_tick': -1}, 'EDIT_NEGATIVE_TIME')
        self.rejects(p, {'action': 'shift', 'clip_ids': ['b'], 'delta_tick': -15}, 'EDIT_MAIN_TRACK_COLLISION')

    def test_linkage_collision_creates_lane_with_original_audio_processing(self):
        p = project([track('main', [clip('a', 0, 10), clip('b', 10, 20), clip('c', 20, 30), clip('d', 30, 40)]),
                     track('voice', [clip('anchored', 0, 25), clip('rider', 31, 38)], 'audio', 1, audio={'volume': .25}),
                     track('wrong_bus', [], 'audio', 2, audio={'volume': 1.0})])
        result, plan = self.plan(p, {'action': 'remove', 'clip_ids': ['b'], 'options': {'ripple': 'main', 'linkage': True}})
        self.assertEqual(len(plan['new_tracks']), 1)
        lane = plan['new_tracks'][0]
        self.assertEqual(lane['audio'], {'volume': .25})
        self.assertEqual(positions(result)['rider'], (lane['id'], 21, 28))
        self.assertEqual(positions(result)['anchored'], ('voice', 0, 25))

    def test_collision_reuses_compatible_lane_and_rejects_effect_bus_relocation(self):
        p = project([track('main', [clip('a', 0, 10), clip('b', 10, 20), clip('c', 20, 30), clip('d', 30, 40)]),
                     track('voice', [clip('anchored', 0, 25), clip('rider', 31, 38)], 'audio', 1),
                     track('free', [], 'audio', 2)])
        request = {'action': 'remove', 'clip_ids': ['b'], 'options': {'ripple': 'main', 'linkage': True}}
        result, plan = self.plan(p, request)
        self.assertEqual(positions(result)['rider'], ('free', 21, 28))
        self.assertEqual(plan['new_track_ids'], [])
        p['sequences'][0]['tracks'][1]['audio'] = {'effects': [{'type': 'compressor'}]}
        self.rejects(p, request, 'EDIT_AUDIO_BUS_RELOCATION_UNSUPPORTED')
        p['sequences'][0]['tracks'][1]['audio'] = {'duck_under_voice': True}
        self.rejects(p, request, 'EDIT_AUDIO_BUS_RELOCATION_UNSUPPORTED')

    def test_large_integer_ticks_retain_one_tick_gap_and_shift(self):
        start = 2**60 + 3
        p = project([track('main', [clip('a', start, start+1), clip('b', start+2, start+3)])])
        result, plan = self.plan(p, {'action': 'close_gap', 'at_tick': start+1})
        self.assertEqual(positions(result)['b'], ('main', start+1, start+2))
        self.assertEqual(plan['shifts'][0]['delta_tick'], -1)
        result, _ = self.plan(result, {'action': 'shift', 'clip_ids': ['b'], 'delta_tick': 1})
        self.assertEqual(positions(result)['b'], ('main', start+2, start+3))

    def test_surviving_complex_source_clock_keys_rights_and_nested_references_are_unchanged(self):
        complex_clip = clip('complex', 30, 50, sequence_id='child', reverse=True, speed_curve=[{'at_tick': 0, 'speed': 1}],
                            keyframes=[{'property': 'transform.opacity', 'keyframes': [{'at_tick': 4, 'value': .4, 'interpolation': 'bezier', 'control_points': [.1, .8]}]}],
                            rights_dependencies=[{'rights_ref': 'rights', 'sha256': 'sha256:'+'a'*64}],
                            effects=[{'type': 'brightness', 'parameters': {'amount': .2}}], mask={'type': 'circle'})
        complex_clip.pop('asset_id')
        p = project([track('main', [clip('a', 0, 10), clip('gone', 10, 30), complex_clip])])
        p['sequences'].append({'id': 'child', 'name': 'child', 'duration_tick': 20, 'tracks': []})
        result, _ = self.plan(p, {'action': 'remove', 'clip_ids': ['gone'], 'options': {'ripple': True}})
        got = result['sequences'][0]['tracks'][0]['clips'][1]
        expected = copy.deepcopy(complex_clip); expected['timeline_start_tick'] = 10
        self.assertEqual(got, expected)
        self.assertEqual(result['sequences'][1], p['sequences'][1])

    def test_binding_relocation_updates_source_track_and_missing_or_locked_reference_rejects(self):
        p = project([track('main', [clip('a', 0, 10)]), track('over', [clip('stationary', 0, 15), clip('source', 20, 25)], order=1),
                     track('labels', [clip('label', 20, 25, tracking_binding={'source_clip_id': 'source', 'source_track_id': 'over'})], 'subtitle', 2)])
        result, plan = self.plan(p, {'action': 'shift', 'clip_ids': ['source'], 'delta_tick': -10})
        self.assertEqual(plan['rebound_clip_ids'], ['label'])
        new_track = positions(result)['source'][0]
        self.assertEqual(result['sequences'][0]['tracks'][2]['clips'][0]['tracking_binding']['source_track_id'], new_track)
        self.rejects(p, {'action': 'remove', 'clip_ids': ['source']}, 'EDIT_BINDING_SOURCE_REMOVED')
        p['sequences'][0]['tracks'][2]['locked'] = True
        self.rejects(p, {'action': 'shift', 'clip_ids': ['source'], 'delta_tick': -10}, 'EDIT_BOUND_REFERENCE_LOCKED')

    def test_sequence_file_subtitle_offsets_accumulate_and_clip_relative_does_not(self):
        p = project([track('main', []), track('captions', [clip('s', 10, 20, subtitle={'asset_uri': 'x.srt'}),
                     clip('relative', 30, 40, subtitle={'asset_uri': 'y.srt', 'asset_time_base': 'clip'})], 'subtitle', 1)])
        result, plan = self.plan(p, {'action': 'shift', 'clip_ids': ['s', 'relative'], 'delta_tick': 5})
        self.assertEqual(plan['retimed_subtitle_ids'], ['s'])
        result, _ = self.plan(result, {'action': 'shift', 'clip_ids': ['s'], 'delta_tick': -2})
        self.assertEqual(result['sequences'][0]['tracks'][1]['clips'][0]['subtitle']['asset_time_offset_tick'], -3)
        self.assertNotIn('asset_time_offset_tick', result['sequences'][0]['tracks'][1]['clips'][1]['subtitle'])

    def test_noop_preserves_tail_and_preexisting_unrelated_overlaps(self):
        p = project([track('main', [clip('a', 0, 10)]), track('over', [clip('x', 1, 9), clip('y', 2, 8)], order=1)])
        result, plan = self.plan(p, {'action': 'close_gaps'})
        self.assertEqual(result, p)
        self.assertEqual(plan['changes'], [])
        result, _ = self.plan(p, {'action': 'shift', 'clip_ids': ['a'], 'delta_tick': 0})
        self.assertEqual(result, p)

    def test_malformed_requests_are_structured_failures(self):
        p = project([track('main', [clip('a', 1, 2)])])
        bad = [None, [], {}, {'action': []}, {'action': 'download'},
               {'action': 'shift', 'clip_ids': ['a'], 'delta_tick': True},
               {'action': 'shift', 'clip_ids': ['a'], 'delta_tick': 1.0},
               {'action': 'remove', 'clip_ids': ['a', 'a']}, {'action': 'remove', 'clip_ids': [False]},
               {'action': 'remove', 'clip_ids': ['a'], 'options': {'sync': 1}},
               {'action': 'remove', 'clip_ids': ['a'], 'options': {'ripple': 1}},
               {'action': 'close_gaps', 'track_id': ''}, {'action': 'close_gaps', 'clip_ids': ['a']},
               {'action': 'close_gap', 'at_tick': .5}, {'action': 'remove', 'clip_ids': ['a'], 'options': {'unknown': True}}]
        for request in bad:
            with self.subTest(request=request):
                self.rejects(p, request, 'EDIT_REQUEST_INVALID')

    def test_planning_uses_no_media_or_network_process(self):
        p = project([track('main', [clip('a', 0, 10), clip('b', 20, 30)])])
        module = planner()
        with patch('subprocess.Popen', side_effect=AssertionError('planner must be pure')):
            result, _ = module.build_edit_plan(p, 'seq', {'action': 'close_gaps'})
        self.assertEqual(positions(result)['b'], ('main', 10, 20))


class LinkedEditCliTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='linked-edit-')
        self.addCleanup(self.temp.cleanup)
        self.root, self.p = create_project(Path(self.temp.name)/'project', name='linked')
        sequence = self.p['sequences'][0]
        sequence['tracks'][0]['clips'] = []
        self.request = Path(self.temp.name)/'request.json'

    def call(self, request, *extra):
        self.request.write_text(json.dumps(request), encoding='utf-8')
        return invoke('timeline', 'edit', '--project', str(self.root), '--input', str(self.request), *extra)

    def digest(self):
        return {p.relative_to(self.root).as_posix(): sha256_file(p) for p in self.root.rglob('*') if p.is_file()}

    def image_asset(self):
        image = Path(self.temp.name)/'black.png'
        Image.new('RGB', (160, 90), 'black').save(image)
        code, result = invoke('media', 'ingest', '--project', str(self.root), '--input', str(image), '--asset-id', 'black')
        self.assertEqual(code, 0, result)
        p = json.loads((self.root/'project.json').read_text(encoding='utf-8'))
        p['settings']['canvas'].update(width=160, height=90)
        p['settings']['timebase']['display_fps'] = {'num': 8, 'den': 1}
        p['sequences'][0]['duration_tick'] = 360000
        p['sequences'][0]['tracks'][0]['clips'] = [clip('bg', 0, 360000, asset_id='black')]
        save_project(self.root, p)
        return p

    def render_rgb(self, name):
        target = self.root/'renders'/(name+'.mp4')
        code, result = invoke('render', '--project', str(self.root), '--output', str(target), '--crf', '0', '--pixel-format', 'yuv444p')
        self.assertEqual(code, 0, result)
        raw = subprocess.check_output(['ffmpeg', '-v', 'error', '-i', str(target), '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-threads', '1', 'pipe:1'])
        size = 160*90*3
        self.assertEqual(len(raw)%size, 0)
        return [raw[i:i+size] for i in range(0, len(raw), size)]

    def subtitle_case(self, base='sequence', nested=False):
        p = self.image_asset()
        font = Path(self.temp.name)/'local-font.ttf'
        font.write_bytes(ImageFont.load_default(size=16).path.getvalue())
        srt = Path(self.temp.name)/'cues.srt'
        start, end = ('00:00:01,250', '00:00:01,750') if base == 'sequence' else ('00:00:00,250', '00:00:00,750')
        srt.write_text(f'1\n{start} --> {end}\nHELLO\n', encoding='utf-8')
        for path, aid in ((font, 'font'), (srt, 'cues')):
            code, result = invoke('media', 'ingest', '--project', str(self.root), '--input', str(path), '--asset-id', aid)
            self.assertEqual(code, 0, result)
        p = json.loads((self.root/'project.json').read_text(encoding='utf-8'))
        title = clip('title', 90000, 270000, asset_id='cues', subtitle={'asset_time_base': base, 'style': {'font_asset_id': 'font', 'fontsize': 40}})
        p['sequences'][0]['tracks'].append(track('captions', [title], 'subtitle', 2))
        if nested:
            child = p['sequences'][0]
            child['id'] = 'child'
            parent_clip = clip('parent', 0, 360000, sequence_id='child', reverse=True)
            parent_clip.pop('asset_id')
            p['sequences'].insert(0, {'id': 'seq_main', 'name': 'main', 'duration_tick': 360000,
                                    'tracks': [track('parent_video', [parent_clip])], 'markers': []})
        save_project(self.root, p)

    def test_file_subtitle_sequence_clock_is_preserved_after_repeated_moves(self):
        self.subtitle_case()
        before = self.render_rgb('before')
        self.assertEqual(len(before), 32)
        self.assertGreater(sum(before[11]), sum(before[0])+100)
        for delta in (90000, -45000):
            code, result = self.call({'action': 'shift', 'clip_ids': ['title'], 'delta_tick': delta})
            self.assertEqual(code, 0, result)
        after = self.render_rgb('after')
        self.assertEqual(after[12:28], before[8:24])
        self.assertEqual(sum(after[11]), sum(after[0]))
        saved = json.loads((self.root/'project.json').read_text(encoding='utf-8'))
        self.assertEqual(saved['sequences'][0]['tracks'][2]['clips'][0]['subtitle']['asset_time_offset_tick'], -45000)

    def test_file_subtitle_clip_clock_moves_without_added_offset(self):
        self.subtitle_case('clip')
        before = self.render_rgb('before')
        code, result = self.call({'action': 'shift', 'clip_ids': ['title'], 'delta_tick': 45000})
        self.assertEqual(code, 0, result)
        after = self.render_rgb('after')
        self.assertEqual(after[12:28], before[8:24])
        self.assertGreater(sum(after[15]), sum(after[0])+100)
        self.assertEqual(result['data']['plan']['retimed_subtitle_ids'], [])

    def test_file_subtitle_offset_survives_reverse_parent_clock(self):
        self.subtitle_case(nested=True)
        before = self.render_rgb('before')
        code, result = self.call({'action': 'shift', 'clip_ids': ['title'], 'delta_tick': 45000}, '--sequence-id', 'child')
        self.assertEqual(code, 0, result)
        after = self.render_rgb('after')
        self.assertEqual(after[4:28], before[8:32])
        self.assertGreater(sum(before[19]), sum(before[0])+100)
        self.assertGreater(sum(after[15]), sum(after[0])+100)

    def test_native_exchange_preserves_links_and_external_formats_report_losses(self):
        p = self.image_asset()
        p['sequences'][0]['editing'] = {'sync': True, 'linkage': True, 'main_track_id': 'track_video_1'}
        p['sequences'][0]['tracks'][0]['sync_lock'] = False
        p['sequences'][0]['tracks'][0]['clips'][0]['link_id'] = 'g'
        save_project(self.root, p)
        for fmt, suffix in (('agent-json', '.json'), ('package', '.aevpkg.zip')):
            target = Path(self.temp.name)/(fmt+suffix)
            code, result = invoke('convert', 'export', '--project', str(self.root), '--target-format', fmt, '--output', str(target))
            self.assertEqual(code, 0, result)
            imported = Path(self.temp.name)/(fmt+'-import')
            code, result = invoke('convert', 'import', '--input', str(target), '--output', str(imported))
            self.assertEqual(code, 0, result)
            restored = json.loads((imported/'project.json').read_text(encoding='utf-8'))
            self.assertEqual(restored['sequences'][0]['editing'], p['sequences'][0]['editing'])
            self.assertIs(restored['sequences'][0]['tracks'][0]['sync_lock'], False)
            self.assertEqual(restored['sequences'][0]['tracks'][0]['clips'][0]['link_id'], 'g')
        for fmt, suffix in (('otio', '.otio'), ('kdenlive-xml', '.kdenlive'), ('jianying-draft-json', '.json')):
            target = Path(self.temp.name)/(fmt+suffix)
            code, result = invoke('convert', 'export', '--project', str(self.root), '--target-format', fmt, '--output', str(target))
            self.assertEqual(code, 0, result)
            report = json.loads(Path(result['data']['report']).read_text(encoding='utf-8'))
            items = report['items']
            self.assertTrue(any(i.get('capability') == 'timeline-editing' and i.get('status') == 'Unsupported' for i in items), report)
        strict_target = Path(self.temp.name)/'strict.json'
        code, result = invoke('convert', 'export', '--project', str(self.root), '--target-format', 'jianying-draft-json', '--strict', '--output', str(strict_target))
        self.assertEqual(code, 2, result)
        self.assertFalse(strict_target.exists())

    def test_invalid_link_and_subtitle_offset_are_checked_without_jsonschema(self):
        p = self.image_asset()
        p['sequences'][0]['tracks'][0]['clips'][0]['link_id'] = False
        p['sequences'][0]['tracks'][0]['clips'][0]['subtitle'] = {'asset_time_offset_tick': True}
        with patch.dict('sys.modules', {'jsonschema': None}):
            report = validate_project(self.root, p)
        codes = {e['code'] for e in report['errors']}
        self.assertTrue({'EDIT_LINK_ID_INVALID', 'SUBTITLE_ASSET_OFFSET_INVALID'} <= codes, report)

    def test_nonzero_subtitle_offset_is_explicitly_lost_in_external_export(self):
        p = self.image_asset()
        p['sequences'][0]['tracks'][0]['clips'][0]['subtitle'] = {'text': 'offset metadata', 'asset_time_offset_tick': -45000}
        save_project(self.root, p)
        target = Path(self.temp.name)/'offset.otio'
        code, result = invoke('convert', 'export', '--project', str(self.root), '--target-format', 'otio', '--output', str(target))
        self.assertEqual(code, 0, result)
        report = json.loads(Path(result['data']['report']).read_text(encoding='utf-8'))
        self.assertTrue(any(i.get('source') == 'subtitle.asset_time_offset_tick' and i['status'] == 'Unsupported' for i in report['items']), report)

    def test_dry_run_is_read_only_apply_is_idempotent_and_stale_plan_rejects(self):
        self.p['sequences'][0]['editing'] = {'sync': True}
        save_project(self.root, self.p)
        before = self.digest()
        code, result = self.call({'action': 'close_gaps'}, '--dry-run', '--idempotency-key', 'plan')
        self.assertEqual(code, 0, result)
        self.assertEqual(before, self.digest())
        base = result['data']['plan']['base_project_sha256']
        code, first = self.call({'action': 'close_gaps'}, '--expected-project-sha256', base, '--idempotency-key', 'apply')
        self.assertEqual(code, 0, first)
        frozen = self.digest()
        code, replay = self.call({'action': 'close_gaps'}, '--expected-project-sha256', base, '--idempotency-key', 'apply')
        self.assertEqual(code, 0, replay)
        self.assertEqual(first['operation_id'], replay['operation_id'])
        self.assertEqual(frozen, self.digest())
        code, stale = self.call({'action': 'close_gaps'}, '--expected-project-sha256', base)
        self.assertEqual(code, 2, stale)
        self.assertEqual(stale['errors'][0]['code'], 'EDIT_PROJECT_CHANGED')
        self.assertEqual(frozen, self.digest())

    def test_compose_can_configure_sync_and_batch_edit_then_roll_back_late_failure(self):
        changes = {'operations': [
            {'op': 'update_sequence', 'patch': {'editing': {'sync': True, 'main_track_id': 'track_video_1'}}},
            {'op': 'update_track', 'track_id': 'track_audio_1', 'patch': {'sync_lock': False}},
            {'op': 'linked_edit', 'edit': {'action': 'close_gaps'}},
        ]}
        before = self.digest()
        self.request.write_text(json.dumps(changes), encoding='utf-8')
        code, result = invoke('timeline', 'compose', '--project', str(self.root), '--input', str(self.request), '--dry-run')
        self.assertEqual(code, 0, result)
        self.assertEqual(before, self.digest())
        changes['operations'].append({'op': 'not_supported'})
        self.request.write_text(json.dumps(changes), encoding='utf-8')
        code, result = invoke('timeline', 'compose', '--project', str(self.root), '--input', str(self.request))
        self.assertEqual(code, 2, result)
        self.assertEqual(before, self.digest())
        changes['operations'].pop()
        self.request.write_text(json.dumps(changes), encoding='utf-8')
        code, result = invoke('timeline', 'compose', '--project', str(self.root), '--input', str(self.request))
        self.assertEqual(code, 0, result)
        saved = json.loads((self.root/'project.json').read_text(encoding='utf-8'))
        self.assertTrue(saved['sequences'][0]['editing']['sync'])
        self.assertFalse(saved['sequences'][0]['tracks'][1]['sync_lock'])

    def test_save_then_operation_failure_rolls_back_project_snapshot_and_operations(self):
        before = self.digest()
        with patch('ai_ad_editor.cli._operation', side_effect=OSError('injected operation write failure')):
            with self.assertRaisesRegex(OSError, 'injected'):
                self.call({'action': 'close_gaps'})
        self.assertEqual(before, self.digest())

    def test_committed_edit_provenance_remains_local_policy_compatible(self):
        code, dry = self.call({'action': 'close_gaps'}, '--dry-run')
        self.assertEqual(code, 0, dry)
        code, result = self.call({'action': 'close_gaps'}, '--idempotency-key', 'local-policy')
        self.assertEqual(code, 0, result)
        self.assertEqual(result['data']['plan']['source']['repository'], 'openfilm/openfilm')
        code, audit = invoke('policy', 'audit', '--project', str(self.root))
        self.assertEqual(code, 0, audit)
        self.assertEqual(audit['data']['findings'], [])

    def test_compose_rejects_invalid_intermediate_model_before_planning(self):
        self.image_asset()
        changes = {'operations': [
            {'op': 'update_clip', 'track_id': 'track_video_1', 'clip_id': 'bg', 'patch': {'subtitle': None}},
            {'op': 'linked_edit', 'edit': {'action': 'shift', 'clip_ids': ['bg'], 'delta_tick': 1}},
        ]}
        before = self.digest()
        self.request.write_text(json.dumps(changes), encoding='utf-8')
        code, result = invoke('timeline', 'compose', '--project', str(self.root), '--input', str(self.request))
        self.assertEqual(code, 2, result)
        self.assertEqual(result['errors'][0]['code'], 'PROJECT_INVALID')
        self.assertEqual(before, self.digest())

    def test_builtin_and_schema_reject_new_configuration_types(self):
        cases = [({'editing': {'sync': 1}}, None, 'EDIT_CONFIGURATION_INVALID'),
                 ({'editing': {'main_track_id': None}}, None, 'EDIT_CONFIGURATION_INVALID'),
                 ({'editing': {'main_track_id': 'track_audio_1'}}, None, 'EDIT_CONFIGURATION_INVALID'),
                 ({'editing': {'unexpected': True}}, None, 'EDIT_CONFIGURATION_INVALID'),
                 ({'editing': []}, None, 'EDIT_CONFIGURATION_INVALID'),
                 ({}, 'sync_lock', 'EDIT_CONFIGURATION_INVALID')]
        for seq_patch, track_patch, expected in cases:
            with self.subTest(seq_patch=seq_patch, track_patch=track_patch):
                p = copy.deepcopy(self.p)
                p['sequences'][0].update(seq_patch)
                if track_patch:
                    p['sequences'][0]['tracks'][0][track_patch] = 1
                report = validate_project(self.root, p)
                self.assertIn(expected, {e['code'] for e in report['errors']}, report)
        p = copy.deepcopy(self.p)
        p['sequences'][0]['editing'] = {'sync': True, 'linked': False, 'linkage': True, 'main_track_id': 'track_video_1'}
        p['sequences'][0]['tracks'][0]['sync_lock'] = False
        self.assertTrue(validate_project(self.root, p)['ok'])


if __name__ == '__main__':
    unittest.main()
