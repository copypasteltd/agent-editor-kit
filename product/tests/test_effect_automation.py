"""Actual native commands, independent per-frame static references and clocks."""
from __future__ import annotations

import copy
from fractions import Fraction
import json
import math
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image

from ai_ad_editor.effect_automation import EffectAutomation, Curve, validate, normalized_tracks
from ai_ad_editor.effects import effect_catalog, get_effect
from ai_ad_editor.errors import AppError
from ai_ad_editor.media import ffmpeg_path
from ai_ad_editor.project import create_project, save_project, load_project
from ai_ad_editor.render import _effect_filters, build_filter_graph
from test_magnetic_reorder import invoke


def effect(kind='color_balance', prop='red', left=0., right=.4, *, end=90000, easing='linear'):
    return {'type': kind, 'keyframes': [{'property': prop, 'keyframes': [
        {'at_tick': 0, 'value': left, 'interpolation': easing},
        {'at_tick': end, 'value': right, 'interpolation': 'linear'}]}]}


def sample_clip(**fields):
    return {'id': 'clip', 'timeline_start_tick': 0, 'duration_tick': 90000, **fields}


class EffectAutomationCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='effect-automation-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def bind(self, value=None, compiler=None, clip=None):
        value = value or effect()
        compiler = compiler or EffectAutomation(self.root, '10', 90000)
        clip = clip or sample_clip()
        metadata = []
        chain = _effect_filters([value], [], 'clip', root=self.root, clip=clip,
                                automation=compiler, automation_meta=metadata)
        return chain, metadata[0], compiler


class EffectAutomationContractTests(EffectAutomationCase):
    def test_catalog_advertises_exact_numeric_channels_and_static_boolean(self):
        names = ('color_temperature', 'color_balance', 'color_wheel', 'exposure', 'color_levels')
        self.assertEqual(sum(len(get_effect(n)['keyframe_parameters']) for n in names), 19)
        self.assertTrue(all(get_effect(n)['keyframable'] for n in names))
        self.assertNotIn('preserve_luma', get_effect('color_wheel')['keyframe_parameters'])
        self.assertEqual(effect_catalog()['catalog_version'], '0.11.0')
        self.assertTrue(get_effect('rgb_curves')['keyframable'])

    def test_alias_prefix_and_top_level_precedence(self):
        value = effect('colorbalance', 'parameters.rs')
        value['parameters'] = {'keyframes': [{'property': 'invalid', 'keyframes': []}]}
        self.assertEqual(validate(value), [])
        self.assertEqual(normalized_tracks(value)[0]['property'], 'rs')
        value.pop('keyframes')
        self.assertEqual(validate(value)[0]['code'], 'EFFECT_AUTOMATION_PROPERTY_UNSUPPORTED')

    def test_duplicate_aliases_cannot_compete_for_one_native_option(self):
        value = effect(); other = copy.deepcopy(value['keyframes'][0]); other['property'] = 'rs'
        value['keyframes'].append(other)
        self.assertIn('EFFECT_AUTOMATION_DUPLICATE_PROPERTY', {e['code'] for e in validate(value)})

    def test_unknown_dynamic_properties_reject_including_command_tokens(self):
        for name in ('preserve_luma', 'rs; exposure@other exposure 3', 'all', ''):
            with self.subTest(name=name):
                self.assertEqual(validate(effect(prop=name))[0]['code'], 'EFFECT_AUTOMATION_PROPERTY_UNSUPPORTED')

    def test_values_are_numeric_finite_and_bounded(self):
        for number in (True, '0.2', math.inf, math.nan, -1.001, 1.001):
            with self.subTest(number=number):
                value = effect(); value['keyframes'][0]['keyframes'][0]['value'] = number
                self.assertIn('EFFECT_AUTOMATION_VALUE_INVALID', {e['code'] for e in validate(value)})

    def test_ticks_are_integer_strict_and_inside_complete_author_range(self):
        for number in (True, 0., -1, 0, 90001):
            with self.subTest(number=number):
                value = effect(); value['keyframes'][0]['keyframes'][1]['at_tick'] = number
                self.assertIn('EFFECT_AUTOMATION_TIME_INVALID', {e['code'] for e in validate(value, duration_tick=90000)})

    def test_bezier_controls_reject_malformed_numbers_and_x_ranges(self):
        for controls in (None, [], [True, 0], [-.1, 0, 1, 1], [0, 0, 1, math.nan]):
            with self.subTest(controls=controls):
                value = effect(easing='bezier'); value['keyframes'][0]['keyframes'][0]['control_points'] = controls
                self.assertIn('EFFECT_AUTOMATION_BEZIER_INVALID', {e['code'] for e in validate(value)})

    def test_disabled_effect_remains_disabled(self):
        value = effect(prop='unavailable'); value['enabled'] = False
        self.assertEqual(validate(value), [])
        compiler = EffectAutomation(self.root, '10', 90000)
        self.assertEqual(_effect_filters([value], [], 'clip', automation=compiler), [])
        self.assertEqual(compiler.targets, 0)

    def test_each_easing_is_evaluated_on_author_ticks(self):
        for name, expected in (('hold', 0), ('linear', .25), ('ease_in', .0625),
                               ('ease_out', .4375), ('ease_in_out', .125), ('bezier', .15625)):
            with self.subTest(name=name):
                value = effect(right=1, easing=name)
                if name == 'bezier': value['keyframes'][0]['keyframes'][0]['control_points'] = [0, 1]
                curve = Curve(value['keyframes'][0], sample_clip(), 0., 90000)
                self.assertAlmostEqual(curve.value(.25), expected, delta=1e-6)
                self.assertEqual(curve.value(-1), 0)
                self.assertEqual(curve.value(2), 1)

    def test_reverse_ancestor_maps_back_to_original_author_clock(self):
        mapping = {'source_start': 0., 'source_end': 2., 'timeline_start': 1.,
                   'timeline_duration': 1., 'speed': 2., 'reverse': True,
                   'segments': [], 'curve_scale': 1.}
        clip = sample_clip(timeline_start_tick=90000,
                           _nested_keyframe_clock={'maps': [mapping], 'authored_start': 0.})
        curve = Curve(effect(right=1, end=180000)['keyframes'][0], clip, 1., 90000)
        self.assertAlmostEqual(curve.value(1.25), .75)

    def test_missing_runtime_commands_fail_before_a_command_file_is_written(self):
        with patch('ai_ad_editor.effect_automation.runtime_options', return_value=frozenset()):
            with self.assertRaises(AppError) as caught: self.bind()
        self.assertEqual(caught.exception.code, 'EFFECT_AUTOMATION_NATIVE_COMMAND_UNAVAILABLE')
        self.assertFalse((self.root/'cache').exists())

    def budget(self, field, limit):
        with patch('ai_ad_editor.effect_automation.'+field, limit):
            with self.assertRaises(AppError) as caught: self.bind()
        self.assertEqual(caught.exception.code, 'EFFECT_AUTOMATION_BUDGET')

    def test_sample_budget_rejects_before_native_probe(self): self.budget('MAX_SAMPLES', 9)
    def test_command_budget_is_enforced(self): self.budget('MAX_COMMANDS', 1)
    def test_command_text_budget_is_enforced(self): self.budget('MAX_BYTES', 1)
    def test_instance_budget_is_enforced(self): self.budget('MAX_TARGETS', 0)

    def test_cache_corruption_is_not_silently_replaced(self):
        _, meta, _ = self.bind(); path = self.root/meta['command_file']; path.write_bytes(b'corrupt')
        with self.assertRaises(AppError) as caught: self.bind()
        self.assertEqual(caught.exception.code, 'EFFECT_AUTOMATION_CACHE_HASH_MISMATCH')
        self.assertEqual(path.read_bytes(), b'corrupt')

    def test_two_equal_effects_have_distinct_targets_and_deterministic_replay(self):
        compiler = EffectAutomation(self.root, '10', 90000)
        a = self.bind(compiler=compiler)[1]; b = self.bind(compiler=compiler)[1]
        self.assertNotEqual(a['target'], b['target'])
        self.assertEqual(compiler.summary()['targets'], 2)
        self.assertEqual(self.bind()[1], a)

    def test_fractional_fps_and_between_sample_command_placement(self):
        compiler = EffectAutomation(self.root, '30000/1001', 90000)
        _, meta, _ = self.bind(compiler=compiler)
        self.assertEqual(meta['sampled_frames'], 30)
        lines = (self.root/meta['command_file']).read_text().splitlines()
        self.assertEqual(float(lines[0].split()[0]), 0.)
        self.assertAlmostEqual(float(lines[1].split()[0]), 1001/60000, places=11)

    def test_overshoot_is_clamped_and_recorded(self):
        value = effect(left=0, right=1, easing='bezier')
        value['keyframes'][0]['keyframes'][0]['control_points'] = [3, 3]
        _, meta, _ = self.bind(value)
        self.assertGreater(meta['clamped_parameter_samples'], 0)
        values = [float(line.split()[-1].removesuffix(';')) for line in (self.root/meta['command_file']).read_text().splitlines()]
        self.assertTrue(all(-1 <= x <= 1 for x in values))

    def test_static_path_needs_no_runtime_context_or_commands(self):
        self.assertEqual(_effect_filters([{'type': 'color_balance', 'red': .1}], [], 'clip'),
                         ['colorbalance=rs=0.100000:gs=0.000000:bs=0.000000'])
        self.assertFalse((self.root/'cache').exists())


class EffectAutomationNativeTests(EffectAutomationCase):
    def native(self, chain, *, count=10, rate='10', source=None):
        pixel = bytes((24, 55, 90, 31, 95, 120, 140, 127, 180, 170, 160, 255, 225, 230, 235, 196))
        frame = pixel*8
        data = source if source is not None else frame*count
        command = [ffmpeg_path(), '-hide_banner', '-v', 'error', '-filter_threads', '1',
                   '-f', 'rawvideo', '-pixel_format', 'rgba', '-video_size', '8x4', '-framerate', rate,
                   '-i', 'pipe:0', '-vf', chain, '-f', 'rawvideo', '-pix_fmt', 'rgba', 'pipe:1']
        result = subprocess.run(command, input=data, capture_output=True, cwd=self.root)
        self.assertEqual(result.returncode, 0, result.stderr.decode('utf-8', errors='replace'))
        self.assertEqual(len(result.stdout), len(data))
        return [result.stdout[i:i+128] for i in range(0, len(data), 128)]

    def compare(self, value, reference, *, rate='10'):
        compiler = EffectAutomation(self.root, rate, 90000)
        chain, metadata, _ = self.bind(value, compiler)
        count = math.ceil(float(Fraction(rate)))
        actual = self.native(','.join(chain), count=count, rate=rate)
        maximum = 0
        for index, frame in enumerate(actual):
            expected = self.native(reference(index/float(Fraction(rate))), count=1, rate=rate)[0]
            maximum = max(maximum, max(abs(a-b) for a, b in zip(frame, expected)))
            self.assertLessEqual(maximum, 1, (value['type'], index, maximum))
            self.assertEqual(frame[3::4], expected[3::4])
        self.assertGreater(len(set(actual)), 1)
        return metadata

    def test_real_native_commands_execute_all_five_color_families(self):
        cases = [
            (effect(), lambda t: f'colorbalance=rs={.4*t:.6f}:gs=0:bs=0'),
            (effect('color_temperature', 'kelvin', 3000, 12000), lambda t:
             'colorbalance=rs={:.6f}:gs={:.6f}:bs={:.6f}'.format(
                 -.3*max(-1, min(1, (3000+9000*t-6500)/6500)),
                 -.05*max(-1, min(1, (3000+9000*t-6500)/6500)),
                 .3*max(-1, min(1, (3000+9000*t-6500)/6500)))),
            (effect('color_wheel', 'midtones_blue', -.3, .4), lambda t: f'colorbalance=bm={-.3+.7*t:.6f}'),
            (effect('exposure', 'amount', -.6, .7), lambda t: f'exposure=exposure={-.6+1.3*t:.6f}:black=0'),
            (effect('color_levels', 'output_white', .5, 1), lambda t:
             'colorlevels='+':'.join(f'{c}omax={.5+.5*t:.6f}' for c in 'rgb')),
        ]
        for value, reference in cases:
            with self.subTest(kind=value['type']): self.compare(value, reference)

    def test_all_nine_wheel_channels_and_preserved_alpha(self):
        value = {'type': 'color_wheel', 'preserve_luma': True, 'keyframes': []}
        options = []
        for i, (tone, suffix) in enumerate((('shadows', 's'), ('midtones', 'm'), ('highlights', 'h'))):
            for j, (channel, prefix) in enumerate((('red', 'r'), ('green', 'g'), ('blue', 'b'))):
                amount = .03*(1+i*3+j)
                value['keyframes'] += effect('color_wheel', tone+'_'+channel, -amount, amount)['keyframes']
                options.append((prefix+suffix, amount))
        self.compare(value, lambda t: 'colorbalance='+':'.join(f'{name}={-a+2*a*t:.6f}' for name, a in options)+':pl=1')

    def test_native_hold_changes_on_exact_display_boundary(self):
        value = effect(easing='hold', end=45000)
        self.compare(value, lambda t: f'colorbalance=rs={0 if t < .5 else .4:.6f}')

    def test_native_fractional_display_rate_uses_actual_sample_times(self):
        self.compare(effect(), lambda t: f'colorbalance=rs={.4*t:.6f}', rate='30000/1001')

    def test_two_native_instances_do_not_cross_modify(self):
        compiler = EffectAutomation(self.root, '10', 90000)
        a = self.bind(effect(right=.3), compiler)[0]
        b = self.bind(effect(prop='blue', left=.2, right=-.2), compiler)[0]
        actual = self.native(','.join(a+b))
        for index, frame in enumerate(actual):
            expected = self.native(f'colorbalance=rs={.03*index:.6f},colorbalance=bs={.2-.04*index:.6f}', count=1)[0]
            self.assertLessEqual(max(abs(a-b) for a, b in zip(frame, expected)), 1)


class EffectAutomationCliTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='effect-cli-'); self.addCleanup(self.temp.cleanup)
        self.workspace = Path(self.temp.name)
        source = self.workspace/'source.png'; Image.new('RGB', (32, 16), (60, 100, 140)).save(source)
        self.root, self.project = create_project(self.workspace/'project')
        self.project['settings']['canvas'] = {'width': 32, 'height': 16, 'background': '#000000'}
        self.project['settings']['timebase'] = {'ticks_per_second': 90000, 'display_fps': {'num': 10, 'den': 1}}
        save_project(self.root, self.project)
        code, result = invoke('media', 'ingest', '--project', self.root, '--input', source)
        self.assertEqual(code, 0, result)
        self.project = load_project(self.root)[1]
        self.asset = result['data']['asset']['id']
        self.sequence = self.project['sequences'][0]
        self.sequence['duration_tick'] = 90000
        self.sequence['tracks'][0]['clips'] = [sample_clip(asset_id=self.asset, source_in_tick=0,
                                                           source_out_tick=90000, effects=[effect()])]
        save_project(self.root, self.project)

    def test_real_cli_plan_and_render_persist_runtime_evidence(self):
        output = self.root/'renders/result.mkv'
        code, plan = invoke('render', '--project', self.root, '--output', output, '--dry-run')
        self.assertEqual(code, 0, plan)
        metadata = [x for x in plan['data']['plan']['inputs'] if x.get('kind') == 'effect-automation']
        self.assertEqual(len(metadata), 1)
        self.assertEqual(metadata[0]['sampled_frames'], 10)
        self.assertFalse(any(x.get('code') == 'EFFECT_KEYFRAME_PROPERTY_UNSUPPORTED' for x in plan['data']['plan']['warnings']))
        code, rendered = invoke('render', '--project', self.root, '--output', output)
        self.assertEqual(code, 0, rendered)
        self.assertTrue(output.is_file())
        manifest = json.loads(Path(rendered['data']['manifest']).read_bytes())
        self.assertTrue(any(x.get('kind') == 'effect-automation' for x in manifest['inputs']))

    def test_cli_rejects_unknown_dynamic_channel_without_writing_project(self):
        before = (self.root/'project.json').read_bytes()
        operation = self.workspace/'edit.json'
        operation.write_text(json.dumps({'operations': [{'op': 'update_clip', 'clip_id': 'clip',
            'patch': {'effects': [effect(prop='bad')]}}]}), encoding='utf-8')
        code, result = invoke('timeline', 'compose', '--project', self.root, '--input', operation)
        self.assertNotEqual(code, 0, result)
        self.assertIn('EFFECT_AUTOMATION_PROPERTY_UNSUPPORTED', json.dumps(result))
        self.assertEqual((self.root/'project.json').read_bytes(), before)

    def test_recursive_window_and_parent_own_effects_share_unique_budget(self):
        child = copy.deepcopy(self.sequence); child['id'] = 'child'; child['tracks'][0]['id'] = 'child_track'
        child['tracks'][0]['clips'][0]['id'] = 'inner'
        child['tracks'][0]['clips'][0]['presentation_window'] = {
            'version': 1, 'offset_tick': 0, 'authored_duration_tick': 90000, 'authored_start_tick': 0}
        self.project['sequences'].append(child)
        self.sequence['tracks'][0]['clips'] = [sample_clip(sequence_id='child', source_in_tick=0,
                                                          source_out_tick=90000, effects=[effect(prop='blue')])]
        _, _, metadata, _ = build_filter_graph(self.root, self.project, self.sequence)
        budget = next(x for x in metadata if x.get('kind') == 'effect-automation-budget')
        self.assertEqual(budget['targets'], 2)
        self.assertEqual(budget['state_samples'], 20)
