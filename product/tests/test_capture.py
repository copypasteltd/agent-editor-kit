"""Native capture contracts, media-independent failures and private argv syntax."""
import argparse
import contextlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from ai_ad_editor import capture
from ai_ad_editor.cli import build_parser, main
from ai_ad_editor.errors import AppError


def options(**updates):
    values = dict(kind="window", duration_seconds=2., fps=30, encoder="auto", window_title="Test board",
                  camera_id=None, microphone_id=None, width=None, height=None, offset_x=0, offset_y=0,
                  draw_mouse=False)
    return argparse.Namespace(**(values | updates))


class CaptureContractTests(unittest.TestCase):
    def test_unicode_device_ids_are_stable_and_bound_to_kind_and_path(self):
        text = ('[dshow @ 123] "镜头" (video)\n[dshow @ 123]   Alternative name "@device_camera"\n'
                '[dshow @ 123] "麦克风" (audio)\n[dshow @ 123]   Alternative name "@device_audio"\n')
        rows = capture.parse_devices(text)
        self.assertEqual([row['kind'] for row in rows], ['video', 'audio'])
        self.assertEqual(rows, capture.parse_devices(text.replace('@ 123', '@ 456')))
        self.assertNotEqual(rows[0]['id'], rows[1]['id'])
        self.assertEqual(capture.select_device(rows, rows[0]['id'], 'video'), rows[0])
        with self.assertRaises(AppError):
            capture.select_device(rows, rows[0]['id'], 'audio')

    def test_duplicate_hardware_identity_is_not_accepted(self):
        with self.assertRaises(AppError):
            capture.parse_devices('[dshow @ 123] "Mic" (audio)\n[dshow @ 124] "Mic" (audio)')

    def test_empty_hardware_inventory_does_not_claim_a_camera(self):
        result = argparse.Namespace(returncode=1, stderr='Could not enumerate video devices (or none found).\nCould not enumerate audio only devices (or none found).')
        with patch.object(capture.sys, 'platform', 'win32'), patch.object(capture, 'run_process', return_value=result):
            data = capture.list_devices()
        self.assertEqual((data['camera_count'], data['microphone_count']), (0, 0))
        self.assertFalse(data['capture_started'])

    def test_missing_dshow_backend_is_an_error(self):
        result = argparse.Namespace(returncode=1, stderr="Unknown input format: 'dshow'")
        with patch.object(capture.sys, 'platform', 'win32'), patch.object(capture, 'run_process', return_value=result):
            with self.assertRaises(AppError) as caught:
                capture.list_devices()
        self.assertEqual(caught.exception.code, 'CAPTURE_ENUMERATION_FAILED')

    def test_window_title_is_one_literal_argument(self):
        args = options(window_title="Example; $(do-not-run) 'a:b' 中文")
        capture.validate_options(args)
        command = capture.build_command(args, Path('space path/out.mp4'), None, None, 'libx264')
        self.assertIn('title=' + args.window_title, command)
        self.assertEqual(command[-1], 'space path\\out.mp4' if __import__('os').name == 'nt' else 'space path/out.mp4')
        self.assertEqual(command.count('-i'), 1)
        self.assertIn('-nostdin', command)
        self.assertIn('-n', command)

    def test_dshow_audio_is_mapped_to_second_input_for_video_and_first_for_audio(self):
        mic = {'name': "Mic's : name", 'alternative_name': None}
        video = capture.build_command(options(), Path('out.mp4'), None, mic, 'h264_nvenc')
        audio = capture.build_command(options(kind='microphone', window_title=None, microphone_id='mic'), Path('out.wav'), None, mic, 'libx264')
        self.assertIn('1:a:0', video)
        self.assertIn('0:a:0', audio)
        self.assertNotIn('-c:v', audio)
        self.assertIn("audio='Mic'\\''s : name'", video)
        self.assertIn('pcm_s16le', audio)

    def test_invalid_or_ambiguous_requests_fail_before_capture(self):
        for update in [dict(duration_seconds=float('nan')), dict(duration_seconds=float('inf')),
                       dict(duration_seconds=.1), dict(duration_seconds=3601), dict(fps=0), dict(fps=True),
                       dict(window_title=None), dict(window_title='bad\nname'), dict(width=100),
                       dict(kind='screen'), dict(kind='camera', window_title=None),
                       dict(kind='microphone', window_title=None), dict(offset_x=32768),
                       dict(encoder='cuda; command')]:
            with self.subTest(update=update), self.assertRaises(AppError):
                capture.validate_options(options(**update))

    def test_camera_and_microphone_have_explicit_valid_requests(self):
        capture.validate_options(options(kind='camera', window_title=None, camera_id='cam', width=640, height=480))
        capture.validate_options(options(kind='microphone', window_title=None, microphone_id='mic'))
        capture.validate_options(options(kind='screen', window_title=None, width=640, height=480, offset_x=-640))

    def test_cancelled_cli_does_not_enumerate_or_publish(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary) / 'project'
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(['project', 'init', str(root)]), 0)
            (root / 'stop').touch()
            before = (root / 'project.json').read_bytes()
            output = io.StringIO()
            with contextlib.redirect_stdout(output), patch.object(capture, 'list_devices', side_effect=AssertionError('must not enumerate')):
                code = main(['capture', 'record', '--project', str(root), '--kind', 'microphone',
                             '--microphone-id', 'unknown', '--duration-seconds', '1', '--cancel-file', 'stop'])
            self.assertNotEqual(code, 0)
            self.assertEqual(json.loads(output.getvalue())['errors'][0]['code'], 'CANCELLED')
            self.assertEqual((root / 'project.json').read_bytes(), before)
            self.assertFalse((root / 'assets/captures').exists())

    def test_cli_never_selects_a_microphone_implicitly(self):
        parsed = build_parser().parse_args(['capture', 'record', '--project', 'p', '--kind', 'screen', '--duration-seconds', '1'])
        self.assertIsNone(parsed.microphone_id)
        self.assertEqual(parsed.encoder, 'auto')


if __name__ == '__main__':
    unittest.main()
