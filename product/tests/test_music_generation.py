"""Music input/integrity/control tests; these never claim neural inference."""
import copy
import json
from pathlib import Path
import struct
import tempfile
import unittest

from ai_ad_editor.errors import AppError
from ai_ad_editor.local_music_generation import (
    ENGINE, FORMAT, MODEL_SHA256, PROTOCOL, model_files, prepare_request, recipe, validate_recipe,
)
from ai_ad_editor.lipsync_plan import digest
from ai_ad_editor.music_generation_pipeline import MusicDiagnosticSession, validate_response

ROOT = Path(__file__).resolve().parents[2]
HASH = 'sha256:' + 'a' * 64


def specification(**changes):
    return dict(format=FORMAT, prompt='Original quiet piano with a warm bass.', lyrics='',
                instrumental=True, duration_seconds=10, **changes)


def request_and_response(codes=True):
    generation = prepare_request(specification(generate_audio_codes=codes))
    request = dict(generation=generation, request_sha256=HASH, adapter={'sha256':HASH})
    response = dict(status='succeeded', protocol=PROTOCOL, network='disabled', blocked_network_events=[],
                    request_sha256=HASH, adapter_sha256=HASH, sample_rate=48000, channels=2,
                    samples=480000, output_bytes=3840000, padded=False, looped=False,
                    resampled=False, normalized=False, service_started=False, shared_queue_touched=False,
                    output_PCM_sha256=HASH, output_sha256=HASH, output_peak=.5, output_rms=.1,
                    model=dict(neural_backend='cuda', CPU_fallback=False,
                               local_weight_reads=[dict(file=name, backend='pread', opens=1) for name in sorted(MODEL_SHA256)],
                               dynamic_vram=False, offline_cli_flag_supported=True, elapsed_includes_runtime_import=True,
                               elapsed_seconds=10., timings=dict(runtime_import_seconds=1.,
                                   text_checkpoint_load_seconds=1., text_encode_seconds_including_device_load=1.,
                                   text_load_and_encode_seconds=2., diffusion_checkpoint_load_seconds=1.,
                                   diffusion_sample_seconds_including_device_load=1., diffusion_load_and_generate_seconds=2.,
                                   vae_checkpoint_load_seconds=1., vae_decode_seconds_including_device_load=1.,
                                   vae_load_and_decode_seconds=2.),
                               forwards={'text':2, 'language_model':50 if codes else 0, 'diffusion':8, 'vae':1},
                               forward_output_devices={'text':['cuda:0'], 'language_model':['cuda:0'] if codes else [],
                                                       'diffusion':['cuda:0'], 'vae':['cuda:0']}))
    return request, response


class MusicGenerationInputTests(unittest.TestCase):
    def test_native_clock_matches_integer_sample_oracle(self):
        data = specification()
        for duration, expected in [(10, 480000), (10.04, 481920), (600, 28800000)]:
            data['duration_seconds'] = duration
            result = prepare_request(data)
            self.assertEqual(round(result['duration_seconds'] * 48000), expected)

    def test_non_native_duration_is_refused_without_implicit_padding(self):
        data = specification()
        for duration in [10.01, 10.02, 9.96, 600.04]:
            data['duration_seconds'] = duration
            with self.assertRaises(AppError):
                prepare_request(data)

    def test_no_boolean_or_nonfinite_numeric_substitution(self):
        for name in ('duration_seconds', 'bpm', 'seed', 'steps'):
            for value in (True, False, float('nan'), float('inf'), -1):
                with self.subTest(field=name, value=value):
                    data = specification()
                    data[name] = value
                    with self.assertRaises(AppError):
                        prepare_request(data)

    def test_unknown_fields_and_unbounded_prompt_are_refused(self):
        for extra in ({'remote_url':'https://example.org'}, {'prompt':'x' * 4001}, {'prompt':'\x00'}):
            data = specification()
            data.update(extra)
            with self.assertRaises(AppError):
                prepare_request(data)

    def test_instrumental_does_not_discard_supplied_lyrics(self):
        data = specification()
        data['lyrics'] = 'Never silently discard these lyrics'
        with self.assertRaises(AppError):
            prepare_request(data)

    def test_singing_requires_explicit_lyrics_and_language(self):
        data = specification()
        data['instrumental'] = False
        with self.assertRaises(AppError):
            prepare_request(data)
        data['lyrics'] = '[Verse]\n迎着晨光向前走。'
        with self.assertRaises(AppError):
            prepare_request(data)
        data['language'] = 'zh'
        self.assertEqual(prepare_request(data)['lyrics'], data['lyrics'])

    def test_non_string_language_or_key_is_a_user_error(self):
        for name in ('language', 'keyscale'):
            data = specification()
            data[name] = {}
            with self.assertRaises(AppError):
                prepare_request(data)

    def test_original_unicode_prompt_and_whitespace_are_preserved(self):
        data = specification()
        data['prompt'] = ' 原创爵士 / original jazz\n不要自动翻译。'
        self.assertEqual(prepare_request(data)['prompt'], data['prompt'])

    def test_seed_steps_signature_and_mode_bounds(self):
        for name, value in [('seed', 2**63), ('steps', 0), ('steps', 33), ('timesignature', 5),
                            ('generate_audio_codes', 1), ('instrumental', 'true')]:
            data = specification()
            data[name] = value
            with self.assertRaises(AppError):
                prepare_request(data)


class MusicGenerationRecipeTests(unittest.TestCase):
    def make_recipe(self):
        return recipe(specification(), dict(model_sha256=HASH, runtime_sha256=HASH),
                      samples=480000, pcm_sha256=HASH, wav_sha256=HASH)

    def test_recipe_keeps_full_request_and_native_clock(self):
        value = self.make_recipe()
        self.assertIs(validate_recipe(value), value)
        self.assertEqual(value['samples'], 480000)
        self.assertEqual(value['request']['prompt'], specification()['prompt'])

    def test_prompt_lyrics_and_runtime_changes_are_covered_by_digest(self):
        for field in ('prompt', 'lyrics'):
            value = self.make_recipe()
            value['request'][field] += 'changed'
            with self.assertRaises(AppError):
                validate_recipe(value)
        value = self.make_recipe()
        value['runtime_sha256'] = 'sha256:' + 'b' * 64
        with self.assertRaises(AppError):
            validate_recipe(value)

    def test_rehashed_but_inconsistent_sample_clock_is_refused(self):
        value = self.make_recipe()
        value['samples'] += 1
        value['sha256'] = digest(value)
        with self.assertRaises(AppError):
            validate_recipe(value)

    def test_recipe_must_match_its_actual_audio_asset(self):
        value = self.make_recipe()
        validate_recipe(value, asset={'kind':'audio', 'sha256':HASH})
        for asset in ({'kind':'video', 'sha256':HASH}, {'kind':'audio', 'sha256':'sha256:'+'b'*64}):
            with self.assertRaises(AppError):
                validate_recipe(value, asset=asset)

    def test_recipe_unknown_fields_are_refused_even_after_rehash(self):
        value = self.make_recipe()
        value['silent_padding'] = True
        value['sha256'] = digest(value)
        with self.assertRaises(AppError):
            validate_recipe(value)


class MusicModelSchemaTests(unittest.TestCase):
    def test_bfloat16_with_a_large_language_vocabulary_is_readable(self):
        base = ROOT / 'product/.runtime/test-music-generation'
        base.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=base) as directory:
            root = Path(directory)
            header = json.dumps({'embedding':dict(dtype='BF16', shape=[217204, 1],
                                                  data_offsets=[0, 434408])}).encode()
            data = struct.pack('<Q', len(header)) + header + bytes(434408)
            for name in MODEL_SHA256:
                (root / name).write_bytes(data)
            self.assertEqual(len(model_files(root)), 4)

    def test_incomplete_tensor_payload_is_a_specific_model_error(self):
        base = ROOT / 'product/.runtime/test-music-generation'
        base.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=base) as directory:
            root = Path(directory)
            header = json.dumps({'tensor':dict(dtype='BF16', shape=[8], data_offsets=[0, 16])}).encode()
            for name in MODEL_SHA256:
                (root / name).write_bytes(struct.pack('<Q', len(header)) + header + bytes(8))
            with self.assertRaises(AppError) as caught:
                model_files(root)
            self.assertEqual(caught.exception.code, 'MUSIC_GENERATION_MODEL')


class MusicGenerationResponseTests(unittest.TestCase):
    def test_failure_diagnostics_redact_supplied_prompt_and_lyrics(self):
        generation = dict(prompt='Private client music direction', lyrics='私有客户歌词。')
        session = MusicDiagnosticSession(ROOT, {'generation':generation},
                                         {'model_path':'E:/private/model', 'executable':'E:/private/python.exe'})
        cleaned = session.cause('Failure: ' + generation['prompt'] + ' / ' + generation['lyrics'])
        self.assertNotIn(generation['prompt'], cleaned)
        self.assertNotIn(generation['lyrics'], cleaned)

    def test_both_explicit_language_model_modes_have_distinct_evidence(self):
        for codes in (True, False):
            request, response = request_and_response(codes)
            validate_response(response, request)

    def test_cuda_discovery_without_actual_forward_is_refused(self):
        for field in ('text', 'diffusion', 'vae', 'language_model'):
            request, response = request_and_response()
            response['model']['forwards'][field] = 0
            with self.assertRaises(AppError):
                validate_response(response, request)

    def test_cpu_copy_to_cuda_cannot_substitute_for_neural_forward(self):
        for field in ('text', 'diffusion', 'vae', 'language_model'):
            request, response = request_and_response()
            response['model']['forward_output_devices'][field] = ['cpu']
            with self.assertRaises(AppError):
                validate_response(response, request)

    def test_cpu_fallback_shared_service_or_output_processing_is_refused(self):
        request, initial = request_and_response()
        for field in ('padded', 'looped', 'resampled', 'normalized', 'service_started', 'shared_queue_touched'):
            response = copy.deepcopy(initial)
            response[field] = True
            with self.assertRaises(AppError):
                validate_response(response, request)
        response = copy.deepcopy(initial)
        response['model']['CPU_fallback'] = True
        with self.assertRaises(AppError):
            validate_response(response, request)

    def test_requested_mode_cannot_be_silently_changed(self):
        request, response = request_and_response(False)
        response['model']['forwards']['language_model'] = 1
        with self.assertRaises(AppError):
            validate_response(response, request)

    def test_sample_count_and_pcm_byte_count_are_independently_checked(self):
        for field in ('samples', 'output_bytes', 'sample_rate', 'channels'):
            request, response = request_and_response()
            response[field] += 1
            with self.assertRaises(AppError):
                validate_response(response, request)

    def test_mismatched_request_or_blocked_network_cannot_publish(self):
        request, response = request_and_response()
        response['request_sha256'] = 'sha256:' + 'b' * 64
        with self.assertRaises(AppError):
            validate_response(response, request)
        request, response = request_and_response()
        response['blocked_network_events'] = ['attempted network']
        with self.assertRaises(AppError):
            validate_response(response, request)

    def test_silent_or_nonfinite_signal_is_refused(self):
        for value in (0, -1, float('nan'), float('inf'), True):
            request, response = request_and_response()
            response['output_rms'] = value
            with self.assertRaises(AppError):
                validate_response(response, request)


if __name__ == '__main__':
    unittest.main()
