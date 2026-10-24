"""Exact multichannel invariants, independently generated PCM and refusal gates."""
from __future__ import annotations

from pathlib import Path
import struct
import tempfile
import unittest

import numpy as np

from ai_ad_editor.audio_channel_links import detect_links, canonical_linked_pcm
from ai_ad_editor.audio_stretch import inspect_pcm
from ai_ad_editor.errors import AppError


def write_pcm(path, values):
    values = np.asarray(values, dtype="<f4")
    if values.ndim == 1:
        values = values[:, None]
    frames, channels = values.shape
    data = values.tobytes()
    fmt = struct.pack("<HHIIHH", 3, channels, 48000, 48000 * channels * 4, channels * 4, 32)
    path.write_bytes(b"RIFF" + struct.pack("<I", len(data) + 36) + b"WAVEfmt "
                     + struct.pack("<I", 16) + fmt + b"data" + struct.pack("<I", len(data)) + data)


def read_pcm(path):
    info = inspect_pcm(path)
    return np.frombuffer(path.read_bytes(), dtype="<f4", offset=info["data_offset"]).reshape(-1, info["channels"])


class AudioChannelLinkTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="exact-audio-links-")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.source = self.root / "source.wav"
        self.engine = self.root / "raw-engine.wav"
        self.output = self.root / "linked.wav"

    def proof(self, values):
        write_pcm(self.source, values)
        return detect_links(self.source, inspect_pcm(self.source))

    def test_eight_channel_copies_inversions_and_silence_preserve_independent_bytes(self):
        random = np.random.default_rng(1757)
        independent = random.uniform(-0.3, 0.3, (1039, 3)).astype("<f4")
        a, b, c = independent.T
        proof = self.proof(np.column_stack([a, b, -a, a, np.zeros_like(a), -b, c, -c]))
        self.assertEqual(proof["verified_source_frames"], 1039)
        self.assertEqual(proof["links"], [
            {"channel": 2, "reference": 0, "gain": -1},
            {"channel": 3, "reference": 0, "gain": 1},
            {"channel": 4, "reference": None, "gain": 0},
            {"channel": 5, "reference": 1, "gain": -1},
            {"channel": 7, "reference": 6, "gain": -1}])
        raw = random.uniform(-0.5, 0.5, (857, 8)).astype("<f4")
        write_pcm(self.engine, raw)
        source_before, engine_before = self.source.read_bytes(), self.engine.read_bytes()
        result = canonical_linked_pcm(self.engine, self.output, inspect_pcm(self.engine), proof)
        actual = read_pcm(self.output)
        for channel in (0, 1, 6):
            self.assertEqual(actual[:, channel].tobytes(), raw[:, channel].tobytes())
        self.assertTrue(np.array_equal(actual[:, 2], -actual[:, 0]))
        self.assertTrue(np.array_equal(actual[:, 3], actual[:, 0]))
        self.assertTrue(np.array_equal(actual[:, 5], -actual[:, 1]))
        self.assertTrue(np.array_equal(actual[:, 7], -actual[:, 6]))
        self.assertFalse(np.any(actual[:, 4]))
        self.assertEqual(self.source.read_bytes(), source_before)
        self.assertEqual(self.engine.read_bytes(), engine_before)
        self.assertFalse(result["arbitrary_stereo_phase_accepted"])

    def test_one_ulp_difference_is_not_treated_as_equal(self):
        left = np.linspace(-0.1, 0.2, 91, dtype="<f4")
        right = left.copy()
        right[47] = np.nextafter(right[47], np.float32(1))
        self.assertEqual(self.proof(np.column_stack([left, right]))["links"], [])

    def test_late_difference_after_full_block_vetoes_early_match(self):
        left = np.ones(65536 + 31, dtype="<f4") / 8
        right = -left
        right[-1] += np.float32(0.001)
        result = self.proof(np.column_stack([left, right]))
        self.assertEqual(result["links"], [])
        self.assertEqual(result["verified_source_frames"], len(left))

    def test_initial_silence_does_not_hide_later_nonzero_channels(self):
        left = np.zeros(65536 + 29, dtype="<f4")
        left[-17:] = np.linspace(-0.3, 0.3, 17)
        self.assertEqual(self.proof(np.column_stack([left, -left]))["links"],
                         [{"channel": 1, "reference": 0, "gain": -1}])

    def test_crop_uses_actual_output_samples_and_keeps_independent_channel(self):
        left = np.linspace(-0.2, 0.2, 113, dtype="<f4")
        proof = self.proof(np.column_stack([left, -left]))
        raw = np.column_stack([left[::-1], left * 2])
        write_pcm(self.engine, raw)
        result = canonical_linked_pcm(self.engine, self.output, inspect_pcm(self.engine), proof,
                                      start_frame=7, frames=31)
        actual = read_pcm(self.output)
        self.assertEqual(actual.shape, (31, 2))
        self.assertEqual(actual[:, 0].tobytes(), raw[7:38, 0].tobytes())
        self.assertTrue(np.array_equal(actual[:, 1], -raw[7:38, 0]))
        self.assertEqual(result["output_frames"], 31)

    def test_mono_nonzero_has_no_inferred_links(self):
        self.assertEqual(self.proof(np.array([0, 0.1, -0.2], dtype="<f4"))["links"], [])

    def test_all_silent_channels_are_explicitly_proven(self):
        self.assertEqual(self.proof(np.zeros((73, 3), dtype="<f4"))["links"],
                         [{"channel": i, "reference": None, "gain": 0} for i in range(3)])

    def test_other_gain_ratios_are_not_guessed(self):
        left = np.linspace(-0.2, 0.1, 103, dtype="<f4")
        self.assertEqual(self.proof(np.column_stack([left, left * 2]))["links"], [])

    def test_truncated_source_is_rejected(self):
        write_pcm(self.source, np.ones((61, 2), dtype="<f4"))
        info = inspect_pcm(self.source)
        self.source.write_bytes(self.source.read_bytes()[:-4])
        with self.assertRaises(AppError) as caught:
            detect_links(self.source, info)
        self.assertEqual(caught.exception.code, "AUDIO_CHANNEL_LINK_PCM_INVALID")

    def test_nonfinite_source_is_rejected(self):
        write_pcm(self.source, np.ones((61, 2), dtype="<f4"))
        info = inspect_pcm(self.source)
        raw = bytearray(self.source.read_bytes())
        struct.pack_into("<f", raw, info["data_offset"] + 17 * 4, float("nan"))
        self.source.write_bytes(raw)
        with self.assertRaises(AppError):
            detect_links(self.source, info)

    def test_cancelled_detection_does_not_publish_any_output(self):
        write_pcm(self.source, np.ones((61, 2), dtype="<f4"))
        cancel = self.root / "cancel"
        cancel.touch()
        with self.assertRaises(AppError) as caught:
            detect_links(self.source, inspect_pcm(self.source), cancel_file=cancel)
        self.assertEqual(caught.exception.code, "CANCELLED")
        self.assertFalse(self.output.exists())

    def test_invalid_reference_cycle_or_duplicate_is_refused_before_output(self):
        proof = self.proof(np.ones((61, 2), dtype="<f4"))
        write_pcm(self.engine, np.ones((31, 2), dtype="<f4"))
        invalid = [
            [{"channel": 1, "reference": 1, "gain": -1}],
            [{"channel": 1, "reference": 0, "gain": -1}] * 2,
            [{"channel": 1, "reference": 0, "gain": 2}],
            [{"channel": 1, "reference": 0, "gain": True}],
            [{"channel": 0, "reference": 1, "gain": 1}],
        ]
        for links in invalid:
            with self.subTest(links=links), self.assertRaises(AppError):
                canonical_linked_pcm(self.engine, self.output, inspect_pcm(self.engine), {**proof, "links": links})
            self.assertFalse(self.output.exists())

    def test_existing_output_is_preserved(self):
        proof = self.proof(np.ones((61, 2), dtype="<f4"))
        write_pcm(self.engine, np.ones((31, 2), dtype="<f4"))
        self.output.write_bytes(b"keep-existing-result")
        with self.assertRaises(FileExistsError):
            canonical_linked_pcm(self.engine, self.output, inspect_pcm(self.engine), proof)
        self.assertEqual(self.output.read_bytes(), b"keep-existing-result")


if __name__ == "__main__":
    unittest.main()
