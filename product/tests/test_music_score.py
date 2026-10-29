"""Independent PCM, editability, transaction and input-contract checks."""
import contextlib
import copy
from fractions import Fraction
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import wave

import numpy as np

from ai_ad_editor import music_score as music
from ai_ad_editor.cli import main
from ai_ad_editor.errors import AppError
from ai_ad_editor.execution_control import ExecutionInterrupted
from ai_ad_editor.project import create_project, ledger_file, load_project, project_file

ROOT = Path(__file__).resolve().parents[2]


def score(instrument='sine'):
    return dict(format='agent-music-score-v1', tempo_bpm=120, duration_beats=2, seed=721,
                master_gain_db=-6, tracks=[dict(id='lead', instrument=instrument, gain_db=-12,
                    notes=[dict(id='a', start_beat=0, duration_beats=2, pitch=69, velocity=.8)])])


def pcm(path):
    with wave.open(str(path), 'rb') as stream:
        assert stream.getframerate() == 48000 and stream.getnchannels() == 2 and stream.getsampwidth() == 2
        return np.frombuffer(stream.readframes(stream.getnframes()), dtype='<i2').reshape(-1, 2).copy()


class ScoreFixture(unittest.TestCase):
    def setUp(self):
        base = ROOT/'local/agent-ffmpeg/music-score59-test-work'
        base.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(prefix='score-', dir=base)
        self.addCleanup(self.temp.cleanup)
        self.home = Path(self.temp.name)

    def synth(self, data, name, **kwargs):
        canonical, plan = music.prepare(data)
        directory = self.home/name
        directory.mkdir()
        result = music.synthesize(canonical, plan, directory, **kwargs)
        return pcm(directory/'master.wav'), result, directory

class ScoreTests(ScoreFixture):
    def test_A4_fundamental_from_independent_FFT(self):
        actual, stats, _ = self.synth(score(), 'tone')
        self.assertEqual(actual.shape, (48000, 2))
        spectrum = np.abs(np.fft.rfft(actual[:, 0].astype(float)*np.hanning(len(actual))))
        hz = np.fft.rfftfreq(len(actual), 1/48000)[int(spectrum.argmax())]
        self.assertAlmostEqual(hz, 440, delta=1)
        self.assertFalse(stats['neural_model'])
        self.assertEqual(stats['model_forwards'], 0)

    def test_rational_beat_clock_matches_independent_fraction_oracle(self):
        data = score()
        data.update(tempo_bpm=137, duration_beats=1.7)
        data['tracks'][0]['notes'][0]['duration_beats'] = 1.7
        actual, _, _ = self.synth(data, 'clock')
        self.assertEqual(len(actual), round(Fraction(17, 10)*60*48000/137))

    def test_pan_extremes_produce_exact_silent_opposite_channel(self):
        for pan, silent in [(-1, 1), (1, 0)]:
            data = score(); data['tracks'][0]['pan'] = pan
            actual, _, _ = self.synth(data, 'pan'+str(pan))
            self.assertEqual(np.count_nonzero(actual[:, silent]), 0)
            self.assertGreater(np.count_nonzero(actual[:, 1-silent]), 1000)

    def test_all_instruments_have_finite_non_silent_bounded_PCM(self):
        for instrument in music.INSTRUMENTS:
            actual, stats, _ = self.synth(score(instrument), instrument)
            self.assertTrue(np.isfinite(actual).all())
            self.assertGreater(np.count_nonzero(actual), 100)
            self.assertLess(int(np.abs(actual.astype(np.int32)).max()), 32767)
            self.assertGreater(stats['rms'], 0)

    def test_noise_samples_independent_of_stream_chunk_size(self):
        data = score('snare')
        a, _, _ = self.synth(data, 'small', block_size=113)
        b, _, _ = self.synth(data, 'large', block_size=4096)
        np.testing.assert_array_equal(a, b)

    def test_seed_changes_noise_but_not_pitched_tone(self):
        for instrument, equal in [('sine', True), ('snare', False)]:
            data = score(instrument)
            a, _, _ = self.synth(data, instrument+'1')
            data['seed'] += 1
            b, _, _ = self.synth(data, instrument+'2')
            self.assertEqual(np.array_equal(a, b), equal)

    def test_track_and_note_reordering_keeps_full_PCM_identity(self):
        data = score('snare')
        second = copy.deepcopy(data['tracks'][0]); second['id'] = 'other'; second['instrument'] = 'bell'
        data['tracks'].append(second)
        for track in data['tracks']:
            track['notes'][0]['duration_beats'] = 1
            other = dict(track['notes'][0], id='b', start_beat=1)
            track['notes'].append(other)
        a, _, _ = self.synth(data, 'ordered')
        data['tracks'].reverse()
        for track in data['tracks']:track['notes'].reverse()
        b, _, _ = self.synth(data, 'reordered')
        np.testing.assert_array_equal(a, b)

    def test_exported_stems_recombine_within_quantization_error(self):
        data = score(); data['master_gain_db'] = 0
        data['tracks'].append(dict(id='bass', instrument='pluck', gain_db=-15,
                                  notes=[dict(id='c', start_beat=0, duration_beats=2, pitch=48)]))
        master, stats, directory = self.synth(data, 'stems', stems=True)
        stems = [pcm(directory/v['file']).astype(np.int32) for v in stats['stems'].values()]
        self.assertEqual(len(stems), 2)
        self.assertLessEqual(int(np.abs(master.astype(np.int32)-sum(stems)).max()), 1)

    def test_strict_numeric_duplicate_and_unknown_field_rejection(self):
        bad = []
        for key, value in [('tempo_bpm', True), ('tempo_bpm', float('nan')), ('seed', -1), ('seed', True), ('duration_beats', '2')]:
            data = score(); data[key] = value; bad.append(data)
        data = score(); data['surprise'] = 1; bad.append(data)
        data = score(); data['tracks'].append(copy.deepcopy(data['tracks'][0])); bad.append(data)
        data = score(); data['tracks'][0]['notes'].append(copy.deepcopy(data['tracks'][0]['notes'][0])); bad.append(data)
        data = score(); data['tracks'][0]['notes'][0]['pitch'] = True; bad.append(data)
        for data in bad:
            with self.assertRaises(AppError):music.prepare(data)

    def test_reject_note_outside_score_and_subsample_events(self):
        for start, duration in [(1, 2), (0, .000001)]:
            data = score(); data['tracks'][0]['notes'][0].update(start_beat=start, duration_beats=duration)
            with self.assertRaises(AppError):music.prepare(data)

    def test_quotas_reject_without_output(self):
        data = score(); data['duration_beats'] = 3000
        with self.assertRaises(AppError):music.prepare(data)
        canonical, plan = music.prepare(score())
        plan['frames'] = 600*48000
        plan['tracks'] *= 16
        with self.assertRaises(AppError):music.synthesize(canonical, plan, self.home, stems=True)
        self.assertFalse((self.home/'master.wav').exists())

    def test_explicit_limiter_records_overload_without_hard_clip(self):
        data = score(); data['master_gain_db'] = 0
        data['tracks'][0]['gain_db'] = 0
        for i in range(3):data['tracks'].append(dict(copy.deepcopy(data['tracks'][0]), id=f't{i}'))
        data['limiter'] = 'tanh'
        actual, stats, _ = self.synth(data, 'limited')
        self.assertGreater(stats['pre_limiter_peak'], 1)
        self.assertGreater(stats['over_unit_pre_limiter_samples'], 0)
        self.assertLess(int(np.abs(actual.astype(np.int32)).max()), 32767)


class ScoreCliTests(ScoreFixture):
    def setUp(self):
        super().setUp()
        self.project = self.home/'project'
        create_project(self.project, 'Score test', 'score_test')
        self.input = self.home/'score.json'
        self.input.write_text(json.dumps(score()), encoding='utf-8')

    def cli(self, *argv):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = main(list(map(str, argv)))
        return code, json.loads(output.getvalue())

    def unchanged(self):
        return [project_file(self.project).read_bytes(), ledger_file(self.project).read_bytes()]

    def test_inspect_and_dry_run_leave_metadata_and_asset_tree_unchanged(self):
        before = self.unchanged()
        code, value = self.cli('music', 'inspect-score', '--input', self.input)
        self.assertEqual(code, 0); self.assertEqual(value['data']['frames'], 48000)
        self.assertEqual(value['data']['device']['selected'], 'cpu')
        code, _ = self.cli('music', 'compose', '--project', self.project, '--input', self.input, '--dry-run')
        self.assertEqual(code, 0)
        self.assertEqual(self.unchanged(), before)
        self.assertFalse((self.project/'assets/music-scores').exists())

    def test_compose_applies_audio_and_retains_unverified_rights(self):
        code, value = self.cli('music', 'compose', '--project', self.project, '--input', self.input,
                               '--new-asset-id', 'song', '--stems', '--apply', '--track-id', 'track_audio_1')
        self.assertEqual(code, 0, value)
        data = value['data']
        self.assertEqual(data['audio_stats']['frames'], 48000)
        self.assertEqual(data['rights']['verification_status'], 'unverified')
        self.assertEqual(data['rights']['permitted_uses'], ['internal'])
        self.assertEqual(data['generated_clip']['asset_id'], 'song')
        self.assertTrue((self.project/data['score']['score_uri']).is_file())

    def test_invalid_target_precedes_synthesis_and_mutation(self):
        before = self.unchanged()
        code, _ = self.cli('music', 'compose', '--project', self.project, '--input', self.input,
                           '--apply', '--track-id', 'track_video_1')
        self.assertEqual(code, 2); self.assertEqual(self.unchanged(), before)
        self.assertFalse((self.project/'assets/music-scores').exists())

    def test_clipping_and_cancellation_remove_owned_outputs_and_restore_metadata(self):
        before = self.unchanged()
        with patch.object(music, 'checkpoint', side_effect=ExecutionInterrupted('CANCELLED', 'test cancellation', exit_code=8)):
            code, _ = self.cli('music', 'compose', '--project', self.project, '--input', self.input)
        self.assertEqual(code, 8); self.assertEqual(self.unchanged(), before)
        self.assertEqual(list((self.project/'assets/music-scores').iterdir()), [])
        data = score(); data['master_gain_db'] = 0; data['tracks'][0]['gain_db'] = 0
        for i in range(3):data['tracks'].append(dict(copy.deepcopy(data['tracks'][0]), id=f't{i}'))
        self.input.write_text(json.dumps(data), encoding='utf-8')
        code, _ = self.cli('music', 'compose', '--project', self.project, '--input', self.input)
        self.assertEqual(code, 6); self.assertEqual(self.unchanged(), before)
        self.assertEqual(list((self.project/'assets/music-scores').iterdir()), [])

    def test_failure_after_asset_commit_rolls_back_project_and_rights(self):
        original, before = music.commit_asset, self.unchanged()
        def fail(*args, **kwargs):
            original(*args, **kwargs)
            raise AppError('TEST_LATE_FAILURE', 'Injected after metadata write', exit_code=6)
        with patch.object(music, 'commit_asset', side_effect=fail):
            code, _ = self.cli('music', 'compose', '--project', self.project, '--input', self.input)
        self.assertEqual(code, 6); self.assertEqual(self.unchanged(), before)
        self.assertEqual(list((self.project/'assets/music-scores').iterdir()), [])

    def test_package_preserves_editable_score_stems_and_full_PCM_recomposition(self):
        code, value = self.cli('music', 'compose', '--project', self.project, '--input', self.input, '--stems', '--new-asset-id', 'song')
        self.assertEqual(code, 0, value)
        original = self.project/value['data']['asset']['uri']
        package = self.home/'editable.zip'
        code, value = self.cli('convert', 'export', '--project', self.project, '--output', package, '--target-format', 'package')
        self.assertEqual(code, 0, value)
        imported = self.home/'imported'
        code, value = self.cli('convert', 'import', '--input', package, '--output', imported)
        self.assertEqual(code, 0, value)
        saved_score = imported/'assets/music-scores/song/score.json'
        self.assertTrue(saved_score.exists())
        self.assertTrue((saved_score.parent/'stem-00.wav').exists())
        code, value = self.cli('music', 'compose', '--project', imported, '--input', saved_score, '--new-asset-id', 'recomposed')
        self.assertEqual(code, 0, value)
        np.testing.assert_array_equal(pcm(original), pcm(imported/value['data']['asset']['uri']))

    def test_four_effects_are_actual_editable_non_silent_audio(self):
        for preset in music.EFFECTS:
            code, value = self.cli('music', 'effect', '--project', self.project, '--preset', preset,
                                   '--duration-seconds', '.1', '--new-asset-id', preset)
            self.assertEqual(code, 0, value)
            self.assertEqual(value['data']['audio_stats']['frames'], 4800)
            self.assertGreater(value['data']['audio_stats']['nonzero_samples'], 0)
            self.assertEqual(value['data']['score']['command'], 'music.effect')


if __name__ == '__main__':
    unittest.main()
