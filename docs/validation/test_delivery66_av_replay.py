"""Independent media-content counterexamples; no model inference or remote calls."""
import array
import copy
import datetime as dt
import json
from pathlib import Path
import sys
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import delivery66_av_replay as replay


class MediaContentContracts(unittest.TestCase):
    def setUp(self):
        self.probe = dict(streams=[
            dict(codec_type='video', width=320, height=568, nb_read_frames='300',
                 avg_frame_rate='30/1', time_base='1/15360', duration_ts=153600),
            dict(codec_type='audio', channels=2, sample_rate='48000',
                 time_base='1/48000', duration_ts=480000)])
        self.pcm = array.array('f', [.125, -.125] * 480256).tobytes()

    def test_complete_non_silent_stereo_with_codec_padding(self):
        result = replay.media_summary(self.probe, self.pcm)
        self.assertEqual(result['audio']['decoded_samples_per_channel'], 480256)
        self.assertEqual(result['audio']['rms'], .125)
        self.assertEqual(result['video']['nb_read_frames'], '300')

    def test_original_audio_only_project_cannot_satisfy_AV_acceptance(self):
        self.probe['streams'].pop(0)
        with self.assertRaises(ValueError):
            replay.media_summary(self.probe, self.pcm)

    def test_an_extra_audio_track_is_not_silently_ignored(self):
        self.probe['streams'].append(copy.deepcopy(self.probe['streams'][1]))
        with self.assertRaises(ValueError):
            replay.media_summary(self.probe, self.pcm)

    def test_missing_last_video_frame_is_rejected(self):
        self.probe['streams'][0]['nb_read_frames'] = '299'
        with self.assertRaises(ValueError):
            replay.media_summary(self.probe, self.pcm)

    def test_matching_duration_text_does_not_hide_wrong_video_clock(self):
        self.probe['streams'][0].update(duration='10.0', duration_ts=153599)
        with self.assertRaises(ValueError):
            replay.media_summary(self.probe, self.pcm)

    def test_wrong_audio_clock_is_rejected(self):
        self.probe['streams'][1]['duration_ts'] = 479999
        with self.assertRaises(ValueError):
            replay.media_summary(self.probe, self.pcm)

    def test_nan_and_infinite_samples_cannot_pass_a_digest_check(self):
        for value in [float('nan'), float('inf'), -float('inf')]:
            with self.subTest(value=str(value)):
                bad = array.array('f', [.125, -.125] * 480000)
                bad[-1] = value
                with self.assertRaises(ValueError):
                    replay.media_summary(self.probe, bad.tobytes())

    def test_silence_truncation_and_excess_padding_are_rejected(self):
        for pcm in [b'\0' * 3840000, self.pcm[:-1], self.pcm[:3800000],
                    array.array('f', [.125, -.125] * 483000).tobytes()]:
            with self.subTest(byte_count=len(pcm)):
                with self.assertRaises(ValueError):
                    replay.media_summary(self.probe, pcm)


def main():
    replay.check_code()
    out = replay.CONTRACTS.parent
    replay.handoff.require(not out.exists(), 'Preserve earlier centralized contracts')
    out.mkdir()
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(MediaContentContracts)
    count = suite.countTestCases()
    with (out / 'tests.stderr').open('x', encoding='utf-8', newline='\n') as stream:
        result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    replay.check_code()
    proof = dict(status='passed' if result.wasSuccessful() and not result.skipped else 'failed',
        observed_at_utc=dt.datetime.now(dt.timezone.utc).isoformat(), tests=result.testsRun,
        discovered_tests=count, failures=len(result.failures), errors=len(result.errors),
        skipped=len(result.skipped), fixture_only=True, new_model_forwards=0, remote_actions=0,
        code_phase_sha256=replay.handoff.sha(replay.CODE_PHASE),
        code_files=replay.handoff.load(replay.CODE_PHASE)['files'])
    replay.handoff.save(out / 'verification.json', proof)
    print(json.dumps(proof, ensure_ascii=False))
    return 0 if proof['status'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
