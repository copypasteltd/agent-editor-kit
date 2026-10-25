"""Analytic PCM and protocol checks; these are not neural-inference evidence."""
from __future__ import annotations
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import wave

import numpy as np

from ai_ad_editor.ctc_activity import refine_units
from ai_ad_editor.ctc_alignment import frame_boundary, map_text, timed_units
from ai_ad_editor.errors import AppError
from ai_ad_editor.local_ctc import prepare_text, validate_alignment
import test_ctc_alignment as fixtures
from test_local_asr import invoke


def unit(a, b, text='WORD!', index=0):
    return dict(text=text, start_char=index, end_char=index + len(text), start_sample=a, end_sample=b,
                posterior_geometric_mean=.7)


def tone(signal, a, b, amplitude=1000):
    signal[a:b] = np.where(np.arange(b-a) % 2, amplitude, -amplitude)


class ActivityPcmTests(unittest.TestCase):
    def test_weak_support_across_gap_attaches_without_padding(self):
        signal = np.zeros(16000, dtype='<i2')
        tone(signal, 3200, 3840, 8)
        tone(signal, 5120, 8000, 10000)
        result, report = refine_units(signal, [unit(5600, 7200)])
        self.assertEqual((result[0]['start_sample'], result[0]['end_sample']), (3200, 8000))
        self.assertEqual(report['support_attachments'][0]['status'], 'weak_support_attached')

    def test_short_gap_between_two_anchored_words_stays_separate(self):
        signal = np.zeros(16000, dtype='<i2')
        tone(signal, 3200, 6400, 10000)
        tone(signal, 7680, 10880, 10000)
        result, report = refine_units(signal, [unit(4000, 5600, 'FIRST', 0), unit(8000, 10000, 'SECOND', 6)])
        self.assertEqual([(u['start_sample'],u['end_sample']) for u in result], [(3200,6400),(7680,10880)])
        self.assertEqual(report['support_attachments'], [])

    def test_weak_component_near_two_anchored_words_remains_ambiguous(self):
        signal = np.zeros(20000, dtype='<i2')
        tone(signal, 3200, 6400, 10000)
        tone(signal, 7200, 7840, 8)
        tone(signal, 8640, 11840, 10000)
        result, report = refine_units(signal, [unit(4000, 5600, 'FIRST', 0), unit(9600, 11200, 'SECOND', 6)])
        self.assertEqual([(u['start_sample'],u['end_sample']) for u in result], [(3200,6400),(8640,11840)])
        self.assertEqual(report['support_attachments'][0]['status'], 'ambiguous_support_preserved')

    def test_weak_onset_and_tail_do_not_inherit_global_vowel_loudness(self):
        signal = np.zeros(16000, dtype='<i2')
        tone(signal, 3200, 5600, 8)
        tone(signal, 5600, 8000, 10000)
        tone(signal, 8000, 9600, 8)
        result, report = refine_units(signal, [unit(5800, 7600)])
        self.assertEqual((result[0]['start_sample'], result[0]['end_sample']), (3200, 9600))
        self.assertEqual(report['changed_units'], 1)

    def test_isolated_region_uses_sound_and_retains_every_other_field(self):
        signal = np.zeros(16000, dtype='<i2')
        tone(signal, 3200, 7200)
        original = [unit(4000, 6400)]
        before = signal.tobytes(), copy.deepcopy(original)
        result, report = refine_units(signal, original)
        self.assertEqual((result[0]['start_sample'], result[0]['end_sample']), (3200, 7200))
        self.assertEqual({k:v for k,v in result[0].items() if k not in ('start_sample', 'end_sample')},
                         {k:v for k,v in original[0].items() if k not in ('start_sample', 'end_sample')})
        self.assertEqual((signal.tobytes(), original), before)
        self.assertEqual(report['changed_units'], 1)

    def test_dc_noise_and_scale_preserve_isolated_bounds(self):
        for amplitude in (100, 1000, 10000):
            signal = np.zeros(16000, dtype='<i2')
            tone(signal, 3200, 7200, amplitude)
            noisy = (signal.astype(np.int32) + 173 + np.where(np.arange(len(signal)) % 2, 5, -5)).astype('<i2')
            result, report = refine_units(noisy, [unit(4000, 6400)])
            self.assertEqual((result[0]['start_sample'], result[0]['end_sample']), (3200, 7200))
            self.assertEqual(report['dc_offset'], 173)

    def test_one_continuous_activity_cannot_invent_internal_word_boundary(self):
        signal = np.zeros(16000, dtype='<i2')
        tone(signal, 2400, 9600)
        original = [unit(3200, 4800, 'FIRST', 0), unit(6400, 8000, 'SECOND', 6)]
        result, report = refine_units(signal, original)
        self.assertEqual(result, original)
        self.assertEqual([d['status'] for d in report['decisions']], ['shared_activity_preserved'] * 2)

    def test_noise_and_silence_are_not_high_confidence_boundaries(self):
        original = [unit(4000, 6400)]
        for signal in (np.zeros(16000, dtype='<i2'), np.tile(np.array([-100, 100], dtype='<i2'), 8000)):
            result, report = refine_units(signal, original)
            self.assertEqual(result, original)
            self.assertEqual(report['changed_units'], 0)
            self.assertNotEqual(report['decisions'][0]['status'], 'activity_estimated')

    def test_short_impulse_is_rejected(self):
        signal = np.zeros(16000, dtype='<i2')
        tone(signal, 4000, 4160, 12000)
        result, report = refine_units(signal, [unit(4000, 4160)])
        self.assertEqual(report['regions'], [])
        self.assertEqual(result[0]['start_sample'], 4000)

    def test_internal_gap_limit_does_not_pad_external_silence(self):
        for gap, expected_count in ((640, 1), (720, 2)):
            signal = np.zeros(16000, dtype='<i2')
            tone(signal, 3200, 4800)
            tone(signal, 4800 + gap, 7200)
            _, report = refine_units(signal, [unit(3600, 4400)])
            self.assertEqual(len(report['regions']), expected_count)
            self.assertEqual(report['regions'][0]['start_sample'], 3200)
            self.assertEqual(report['regions'][-1]['end_sample'], 7200)

    def test_offset_and_non_frame_tail_use_absolute_sample_clock(self):
        signal = np.zeros(16037, dtype='<i2')
        tone(signal, 12800, 16037)
        result, _ = refine_units(signal, [unit(14000 + 903, 15200 + 903)], offset=903)
        self.assertEqual((result[0]['start_sample'], result[0]['end_sample']), (13703, 16940))

    def test_movement_budget_and_cross_region_anchor_preserve_raw(self):
        signal = np.zeros(48000, dtype='<i2')
        tone(signal, 3200, 24000)
        original = [unit(18000, 20000)]
        self.assertEqual(refine_units(signal, original)[1]['decisions'][0]['status'], 'movement_budget_preserved')
        original = [unit(2800, 4800)]
        self.assertEqual(refine_units(signal, original)[1]['decisions'][0]['status'], 'anchor_crosses_region_preserved')

    def test_cancellation_and_invalid_pcm_or_order(self):
        def stop():
            raise RuntimeError('cancel requested')
        with self.assertRaisesRegex(RuntimeError, 'cancel requested'):
            refine_units(np.zeros(16000, dtype='<i2'), [unit(4000, 6400)], checkpoint=stop)
        invalid = [(np.zeros(10, dtype=np.float32), [unit(1, 4)]),
                   (np.zeros((10, 2), dtype='<i2'), [unit(1, 4)]),
                   (np.zeros(10, dtype='<i2'), [unit(4, 8), unit(2, 3)]),
                   (np.zeros(10, dtype='<i2'), []), (np.zeros(10, dtype='<i2'), [unit(True, 4)])]
        for signal, units in invalid:
            with self.assertRaises(AppError):
                refine_units(signal, units)


class ActivityValidationTests(unittest.TestCase):
    def test_controller_recomputes_source_audio_and_rejects_mutated_evidence(self):
        runtime = fixtures.ROOT / 'product/.runtime/temp'
        runtime.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=runtime) as directory:
            pcm = Path(directory) / 'input.wav'
            signal = np.zeros(16000, dtype='<i2')
            tone(signal, 3200, 8000)
            with wave.open(str(pcm), 'wb') as stream:
                stream.setparams((1, 2, 16000, 0, 'NONE', 'not compressed'))
                stream.writeframes(signal.tobytes())
            tokens = map_text('A!', {'<pad>':0, 'A':1}, 0)
            segment = dict(text='A!', start_char=0, end_char=2, start_sample=0, end_sample=None, **tokens)
            prepared = dict(format='txt', original_text='A!', original_file_text='A!', index_basis='unicode_codepoints',
                            granularity='whitespace', case='upper', boundary_mode='activity', stride_samples=320,
                            receptive_samples=400, segments=[segment])
            char = dict(**tokens['tokens'][0], start_frame=13, end_frame=20, posterior_geometric_mean=.9,
                        start_sample=frame_boundary(13,50,16000,320,400), end_sample=frame_boundary(20,50,16000,320,400))
            raw = timed_units('A!', [char], offset=0, granularity='whitespace')
            refined, activity = refine_units(signal, raw)
            actual = dict(format='agent-ctc-alignment-v1', **{k:prepared[k] for k in (
                'original_text','original_file_text','index_basis','granularity','case','boundary_mode','stride_samples','receptive_samples')},
                sample_rate=16000, samples=16000, segments=[dict(text='A!', start_char=0, end_char=2,
                    ignored=tokens['ignored'], start_sample=0,end_sample=16000,frames=50,characters=[char],
                    raw_units=raw, units=refined, activity=activity)])
            self.assertIs(validate_alignment(actual, prepared, 16000, pcm_path=pcm), actual)
            changes = [lambda x:x['segments'][0]['units'][0].update(start_sample=3120),
                       lambda x:x['segments'][0]['activity'].update(changed_units=0),
                       lambda x:x['segments'][0]['raw_units'][0].update(start_sample=3200),
                       lambda x:x.update(boundary_mode='ctc'),
                       lambda x:x['segments'][0]['characters'][0].update(text='B')]
            for change in changes:
                altered = copy.deepcopy(actual)
                change(altered)
                with self.assertRaises(AppError):
                    validate_alignment(altered, prepared, 16000, pcm_path=pcm)
            with self.assertRaises(AppError):
                validate_alignment(actual, prepared, 16000)
            with self.assertRaises(AppError):
                validate_alignment(actual, {**prepared, 'boundary_mode':'ctc'}, 16000, pcm_path=pcm)


class ActivityCliTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.CtcCliTests(methodName='runTest')
        self.addCleanup(self.fixture.doCleanups)
        self.fixture.setUp()
        self.fixture.register()

    def enrich(self, value, request):
        prepared = request['prepared']
        value['alignment']['boundary_mode'] = prepared['boundary_mode']
        if prepared['boundary_mode'] != 'activity':
            return
        with wave.open(request['input'], 'rb') as stream:
            pcm = np.frombuffer(stream.readframes(stream.getnframes()), dtype='<i2')
        for segment in value['alignment']['segments']:
            segment['raw_units'] = segment['units']
            segment['units'], segment['activity'] = refine_units(
                pcm[segment['start_sample']:segment['end_sample']], segment['raw_units'], offset=segment['start_sample'])

    def test_explicit_dry_run_and_invalid_character_mode_do_not_infer(self):
        f = self.fixture
        before = f.metadata()
        with patch('ai_ad_editor.local_ctc.run_process') as runner:
            code, value = invoke(*f.options(), '--boundary-mode', 'activity', '--dry-run')
            self.assertEqual(code, 0, value)
            self.assertEqual(value['data']['prepared']['boundary_mode'], 'activity')
            code, value = invoke(*f.options(), '--boundary-mode', 'activity', '--granularity', 'character', '--dry-run')
            self.assertEqual(code, 2, value)
        runner.assert_not_called()
        self.assertEqual(f.metadata(), before)

    def test_protocol_keeps_raw_and_applies_units_with_review(self):
        f = self.fixture
        f.change = self.enrich
        with patch('ai_ad_editor.local_ctc.run_process', side_effect=f.fake_runner):
            code, value = invoke(*f.options(), '--boundary-mode', 'activity', '--apply', '--track-id', 'captions')
        self.assertEqual(code, 0, value)
        result = value['data']['result']
        self.assertTrue(result['review_required'])
        segment = result['segments'][0]
        self.assertEqual(segment['raw_units'], segment['units'])  # PCM is deliberate silence.
        self.assertEqual(segment['activity']['changed_units'], 0)
        self.assertEqual(len(value['data']['generated_clips']), 1)

    def test_bad_activity_diagnostics_reject_without_committing(self):
        f = self.fixture
        before = f.metadata()
        def change(value, request):
            self.enrich(value, request)
            value['alignment']['segments'][0]['activity']['changed_units'] = 7
        f.change = change
        with patch('ai_ad_editor.local_ctc.run_process', side_effect=f.fake_runner):
            code, value = invoke(*f.options(), '--boundary-mode', 'activity')
        self.assertEqual(code, 6, value)
        self.assertEqual(f.metadata(), before)
        self.assertFalse((f.root / 'assets/aligned/new.json').exists())


if __name__ == '__main__':
    unittest.main()
