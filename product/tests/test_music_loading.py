"""Native loader policy and failure boundaries; fixtures do not run a model."""
import copy
from pathlib import Path
import sys
import tempfile
from types import ModuleType
import unittest
from unittest.mock import patch

from ai_ad_editor.errors import AppError
from ai_ad_editor.music_generation_model import WEIGHT_NAMES, runtime_arguments, validate_weight_reads, weight_reader
from ai_ad_editor.music_generation_pipeline import validate_response
from test_music_generation import request_and_response


BASE = Path(__file__).resolve().parents[1] / '.runtime/test-music-loading'
FLAGS = ('--base-directory', '--models-directory', '--use-pytorch-cross-attention',
         '--disable-pinned-memory', '--disable-dynamic-vram')


class RuntimeArgumentsTests(unittest.TestCase):
    def core(self, flags, extra=''):
        BASE.mkdir(parents=True, exist_ok=True)
        temporary = tempfile.TemporaryDirectory(dir=BASE)
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        (root / 'comfy').mkdir()
        (root / 'comfy/cli_args.py').write_text(
            '\n'.join('parser.add_argument(' + repr(flag) + ')' for flag in flags) + '\n' + extra,
            encoding='utf-8')
        return root

    def test_optional_frontend_offline_flag_uses_declared_parser_options(self):
        for flags in (FLAGS, (*FLAGS, '--offline')):
            root = self.core(flags)
            argv, supported = runtime_arguments(root, root / 'work')
            self.assertEqual(supported, '--offline' in flags)
            self.assertEqual('--offline' in argv, supported)
            self.assertIn('--disable-dynamic-vram', argv)
            self.assertIn(str(root / 'work/comfy/models'), argv)

    def test_missing_memory_policy_flag_is_refused(self):
        root = self.core(FLAGS[:-1])
        with self.assertRaisesRegex(ValueError, 'REQUIRED_RUNTIME_FLAGS_MISSING'):
            runtime_arguments(root, root / 'work')

    def test_a_documentation_string_is_not_a_supported_flag(self):
        root = self.core(FLAGS, "message = '--offline'\n")
        argv, supported = runtime_arguments(root, root / 'work')
        self.assertFalse(supported)
        self.assertNotIn('--offline', argv)


class WeightReaderTests(unittest.TestCase):
    def setUp(self):
        BASE.mkdir(parents=True, exist_ok=True)
        temporary = tempfile.TemporaryDirectory(dir=BASE)
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        for name in WEIGHT_NAMES:
            (self.root / name).write_bytes(b'fixture only, never model inference')
        self.module = ModuleType('safetensors')
        self.calls, self.report = [], []
        self.pointer = object()

        def native(filename, framework, device='cpu', *, backend='mmap'):
            self.calls.append((Path(filename), framework, device, backend))
            return self.pointer

        self.native = self.module.safe_open = native
        scope = patch.dict(sys.modules, {'safetensors': self.module})
        scope.start()
        self.addCleanup(scope.stop)

    def test_all_components_use_pread_and_return_native_reader_unchanged(self):
        for name in sorted(WEIGHT_NAMES):
            with weight_reader(self.root, (name,), read_report=self.report):
                result = self.module.safe_open(self.root / name, 'pt')
                self.assertIs(result, self.pointer)
            self.assertIs(self.module.safe_open, self.native)
        self.assertEqual(len(self.calls), 4)
        self.assertEqual({call[3] for call in self.calls}, {'pread'})
        validate_weight_reads(self.report)

    def test_native_backend_error_never_retries_mmap(self):
        calls = []

        def failed(*unused, **options):
            calls.append(options['backend'])
            raise TypeError('unsupported native backend')

        self.module.safe_open = failed
        with self.assertRaisesRegex(TypeError, 'unsupported native backend'):
            with weight_reader(self.root, ('vae.safetensors',), read_report=self.report):
                self.module.safe_open(self.root / 'vae.safetensors', 'pt')
        self.assertEqual(calls, ['pread'])
        self.assertIs(self.module.safe_open, failed)
        self.assertEqual(self.report, [])

    def test_foreign_component_is_refused_before_native_reader(self):
        with self.assertRaisesRegex(ValueError, 'OUTSIDE_COMPONENT'):
            with weight_reader(self.root, ('vae.safetensors',), read_report=self.report):
                self.module.safe_open(self.root / 'diffusion_model.safetensors', 'pt')
        self.assertEqual(self.calls, [])
        self.assertEqual(self.report, [])
        self.assertIs(self.module.safe_open, self.native)

    def test_partial_two_encoder_read_cannot_claim_completion(self):
        with self.assertRaisesRegex(ValueError, 'NOT_USED_FOR_ALL_COMPONENTS'):
            with weight_reader(self.root, ('text_encoder.safetensors', 'language_model.safetensors'), read_report=self.report):
                self.module.safe_open(self.root / 'text_encoder.safetensors', 'pt')
        self.assertEqual(self.report, [])
        self.assertIs(self.module.safe_open, self.native)

    def test_loader_exception_restores_reader_without_success_report(self):
        with self.assertRaisesRegex(RuntimeError, 'controlled loader failure'):
            with weight_reader(self.root, ('vae.safetensors',), read_report=self.report):
                self.module.safe_open(self.root / 'vae.safetensors', 'pt')
                raise RuntimeError('controlled loader failure')
        self.assertEqual(self.report, [])
        self.assertIs(self.module.safe_open, self.native)

    def test_unknown_or_duplicated_component_inventory_is_refused(self):
        for names in ((), ('unregistered.bin',), ('vae.safetensors', 'vae.safetensors')):
            with self.subTest(names=names), self.assertRaisesRegex(ValueError, 'COMPONENT_SET_INVALID'):
                with weight_reader(self.root, names, read_report=self.report):
                    self.fail('invalid inventory accepted')
        self.assertEqual(self.calls, [])

    def test_missing_duplicated_or_mmap_report_cannot_publish(self):
        valid = [dict(file=name, backend='pread', opens=1) for name in sorted(WEIGHT_NAMES)]
        validate_weight_reads(valid)
        variants = [valid[:-1], valid + [valid[0]], [valid[0]] * 4]
        for field, value in [('backend', 'mmap'), ('opens', True), ('opens', 0), ('file', 'outside.bin')]:
            changed = copy.deepcopy(valid)
            changed[0][field] = value
            variants.append(changed)
        for report in variants:
            with self.subTest(report=report), self.assertRaises(ValueError):
                validate_weight_reads(report)


class CompleteMusicClockTests(unittest.TestCase):
    def test_omitted_import_time_or_invalid_stage_clock_cannot_publish(self):
        for field, value in [('elapsed_includes_runtime_import', False), ('dynamic_vram', True),
                             ('elapsed_seconds', 0.), ('elapsed_seconds', float('nan'))]:
            request, response = request_and_response()
            response['model'][field] = value
            with self.subTest(field=field), self.assertRaises(AppError):
                validate_response(response, request)
        for value in (True, -1., float('inf')):
            request, response = request_and_response()
            response['model']['timings']['runtime_import_seconds'] = value
            with self.subTest(value=value), self.assertRaises(AppError):
                validate_response(response, request)

    def test_old_loading_report_or_unknown_clock_cannot_publish(self):
        request, response = request_and_response()
        del response['model']['local_weight_reads']
        with self.assertRaises(AppError):
            validate_response(response, request)
        request, response = request_and_response()
        response['model']['timings']['gpu_only_seconds'] = 1.
        with self.assertRaises(AppError):
            validate_response(response, request)


if __name__ == '__main__':
    unittest.main()
