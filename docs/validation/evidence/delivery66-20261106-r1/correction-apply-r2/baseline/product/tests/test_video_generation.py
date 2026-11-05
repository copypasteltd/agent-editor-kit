"""Generation conditioning, native transport and transactional admission.

Protocol workers are explicitly synthetic; real GPU acceptance is separate.
"""
from __future__ import annotations

import copy
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
from PIL import Image

import test_local_vace as fixture
from ai_ad_editor import video_generation as generation
from ai_ad_editor.errors import AppError
from ai_ad_editor.job_workspaces import Workspace, recover_workspaces
from ai_ad_editor.local_inpainting import normalize_options
from ai_ad_editor.project import create_project
from ai_ad_editor.runtime import configure_local_runtime
from ai_ad_editor.vace_frames import process_frames

def invoke(*args):
    return fixture.invoke(*map(str, args))


def configuration(**changes):
    values = dict(mode='text-to-video', width=64, height=64, frames=7, fps='12', image_fit='contain',
        sampling=dict(prompt='A red cube moves slowly.', window_frames=5, window_overlap=2, temporal_context='previous'))
    values.update(changes)
    return generation.configuration(**values)


class ConditioningTests(unittest.TestCase):
    def test_text_and_first_last_masks_reach_the_actual_window_processor(self):
        first = np.full((64, 64, 4), (180, 12, 30, 255), np.uint8)
        last = np.full((64, 64, 4), (15, 40, 210, 255), np.uint8)
        for mode, names in generation.MODES.items():
            with self.subTest(mode=mode):
                config = configuration(mode=mode); endpoints = {k: {'first': first, 'last': last}[k] for k in names}
                pairs = [generation.condition_frame(i, config, endpoints) for i in range(7)]
                source = np.stack([p[0] for p in pairs]); mask = np.stack([p[1] for p in pairs])
                destination = io.BytesIO(); calls = []
                def model(images, masks, settings):
                    calls.append((images.copy(), masks.copy()))
                    return np.full(images.shape, .25, np.float32)
                metrics = process_frames(io.BytesIO(np.concatenate([source, mask], axis=2).tobytes()), destination,
                    width=64, height=64, frames=7, options=normalize_options(grow=0, context=0),
                    generation=config['sampling'], channel='luma', infer=model)
                output = np.frombuffer(destination.getvalue(), np.uint8).reshape(7, 64, 64, 4)
                self.assertEqual(metrics['model_calls'], 2)
                np.testing.assert_array_equal(output[1:-1, :, :, :3], 64)
                self.assertTrue(np.all(calls[0][1][0] == (0 if 'first' in names else 255)))
                if 'first' in names: np.testing.assert_array_equal(output[0], first)
                if 'last' in names: np.testing.assert_array_equal(output[-1], last)
                for rgb, masks in calls: np.testing.assert_array_equal(rgb[masks != 0], 127)

    def test_exact_rational_clock_and_configuration_rebuild(self):
        c = configuration(fps='24000/1001', frames=17)
        self.assertEqual(c['fps'], '24000/1001')
        self.assertAlmostEqual(c['duration_seconds'], 17017/24000)
        self.assertEqual(c, generation.configuration(**{k:c[k] for k in
            ('mode','width','height','frames','fps','image_fit','sampling','storage_budget_mib')}))

    def test_raster_clock_resource_and_sampler_rejections(self):
        changes = [dict(width=63), dict(height=65), dict(width=True), dict(width=2064), dict(frames=4),
            dict(frames=4098), dict(fps='nan'), dict(fps='0'), dict(fps='1/0'), dict(fps=True), dict(fps='61'),
            dict(frames=4097, fps='1'), dict(storage_budget_mib=15), dict(mode='automatic'), dict(image_fit='auto'),
            dict(width=2048, height=2048, frames=81, storage_budget_mib=16),
            dict(sampling=dict(prompt='x', model_input_scale=2)),
            dict(sampling=dict(prompt='x', scene_cut_frames=[3])),
            dict(sampling=dict(prompt='x', window_overlap=0, temporal_context='previous'))]
        for change in changes:
            with self.subTest(change=change), self.assertRaises(AppError): configuration(**change)

    def test_image_fit_flatten_and_reject_are_explicit(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary)/'image.png'; Image.new('RGBA', (32,64), (200,100,40,128)).save(path)
            contain = generation.prepared_image(path, configuration())
            np.testing.assert_array_equal(contain[10,0], (0,0,0,255))
            np.testing.assert_array_equal(contain[10,32], (100,50,20,255))
            for fit in ('cover','stretch'):
                pixels = generation.prepared_image(path, configuration(image_fit=fit))
                self.assertEqual(pixels.shape, (64,64,4)); self.assertTrue(np.all(pixels[:,:,3] == 255))
            with self.assertRaises(AppError): generation.prepared_image(path, configuration(image_fit='reject'))


class NativeGenerationTests(unittest.TestCase):
    metadata = fixture.NativeVaceTests.metadata
    fake_command = fixture.NativeVaceTests.fake_command
    ingest = fixture.NativeVaceTests.ingest
    register = fixture.NativeVaceTests.register

    @classmethod
    def setUpClass(cls): configure_local_runtime()

    def setUp(self):
        fixture.NativeVaceTests.setUp(self)
        # Execute this test's selected source/installed package in the child.
        source = str(Path(__file__).resolve().parents[1]/'src')
        self.worker.write_text(self.worker.read_text('utf8').replace(repr(source),
            repr(str(Path(generation.__file__).resolve().parent.parent))), encoding='utf8')
        self.first = self.base/'first.png'; self.last = self.base/'last.png'
        Image.new('RGB', (64,64), (180,12,30)).save(self.first)
        Image.new('RGB', (64,64), (15,40,210)).save(self.last)
        self.first_id = self.ingest(self.first); self.last_id = self.ingest(self.last)
        self.output = self.root/'assets/derived/generated.mov'

    def command(self, mode='text-to-video'):
        args = ['media','generate','--project',str(self.root),'--adapter-id','vace','--asset-id','generated',
            '--width','64','--height','64','--frames','7','--fps','12','--prompt','A red cube moves slowly.',
            '--window-frames','5','--window-overlap','2','--mode',mode,'--apply','--track-id','track_video_1']
        if 'first' in generation.MODES[mode]: args += ['--first-asset-id', self.first_id]
        if 'last' in generation.MODES[mode]: args += ['--last-asset-id', self.last_id]
        return args

    def decoded(self):
        raw = subprocess.run(['ffmpeg','-nostdin','-v','error','-i',str(self.output),'-an','-pix_fmt','rgba',
            '-f','rawvideo','pipe:1'], capture_output=True, check=True).stdout
        return np.frombuffer(raw, np.uint8).reshape(7,64,64,4)

    def clean(self, before):
        self.assertEqual(before, self.metadata()); self.assertFalse(self.output.exists())
        self.assertFalse(list((self.root/'cache/managed-jobs').glob('job-*')))
        self.assertFalse((self.root/'operations/project-transaction.json').exists())

    def test_dry_run_admits_four_modes_without_mutation_or_inference(self):
        self.register(); before = self.metadata()
        with patch('ai_ad_editor.video_generation.execute') as infer:
            for mode in generation.MODES:
                code, value = invoke(*self.command(mode), '--dry-run')
                self.assertEqual(code,0,value); self.assertFalse(value['data']['model_inference_executed'])
            infer.assert_not_called()
        self.clean(before)

    def test_default_command_configuration_fits_the_window_budget(self):
        self.register(); before = self.metadata()
        code, value = invoke('media','generate','--project',self.root,'--adapter-id','vace',
            '--asset-id','defaults','--prompt','A quiet studio shot.','--dry-run')
        self.assertEqual(code,0,value)
        self.assertLess(value['data']['configuration']['estimated_window_array_bytes'],512*1024**2)
        self.clean(before)

    def test_all_modes_native_encode_decode_and_editable_apply(self):
        self.register()
        for mode in generation.MODES:
            with self.subTest(mode=mode), self.fake_command():
                args = self.command(mode); args[args.index('--asset-id')+1] = mode
                args += ['--timeline-start-seconds', str(list(generation.MODES).index(mode))]
                code, value = invoke(*args); self.assertEqual(code,0,value)
                data = value['data']; proof = data['generation']; self.output = self.root/data['asset']['uri']
                self.assertTrue(proof['result']['rgba_roundtrip_verified'])
                self.assertEqual(proof['result']['video']['frames'],7)
                self.assertEqual(proof['result']['worker']['metrics']['model_calls'],2)
                pixels = self.decoded(); self.assertTrue(np.all(pixels[:,:,:,3] == 255))
                self.assertTrue(np.any(pixels[1:-1,:,:,:3] != 127))
                for name in generation.MODES[mode]: self.assertTrue(proof['endpoint_checks'][name]['equal'])
                self.assertEqual(data['rights']['verification_status'],'unverified')
                self.assertIn('visual_adapter_vace',data['rights']['derived_from'])
                self.assertFalse(any(s['codec_type']=='audio' for s in data['asset']['probe']['streams']))
        self.assertEqual(invoke('validate','--project',self.root)[0],0)
        self.assertEqual(invoke('rights','check','--project',self.root)[0],7)
        self.assertFalse(list((self.root/'cache/managed-jobs').glob('job-*')))

    def test_invalid_mode_parameters_track_clock_budget_before_worker(self):
        self.register(); before = self.metadata()
        changes = [('--first-asset-id',self.first_id), ('--track-id','track_audio_1'), ('--timeout-seconds','nan'),
            ('--timeout-seconds','0'), ('--timeline-start-seconds','nan'), ('--storage-budget-mib','1'),
            ('--frames','4'), ('--fps','61'), ('--width','65'), ('--window-overlap','0')]
        with patch('ai_ad_editor.video_generation.execute') as infer:
            for flag, value in changes:
                code, result = invoke(*self.command(),flag,value,'--dry-run'); self.assertNotEqual(code,0,result)
            infer.assert_not_called()
        self.clean(before)

    def test_tampered_image_and_adapter_never_reach_inference(self):
        self.register(); before = self.metadata()
        project = json.loads((self.root/'project.json').read_bytes())
        original = self.root/next(a['uri'] for a in project['assets'] if a['id']==self.first_id)
        with patch('ai_ad_editor.video_generation.execute') as infer:
            original.write_bytes(original.read_bytes()+b'changed')
            self.assertEqual(invoke(*self.command('image-to-video'))[0],10)
            self.evidence.write_bytes(self.evidence.read_bytes()+b'changed')
            self.assertEqual(invoke(*self.command())[0],10); infer.assert_not_called()
        self.clean(before)

    def test_native_bad_worker_rollback_leaves_inputs_and_metadata(self):
        self.register(); before = self.metadata(); images = (self.first.read_bytes(), self.last.read_bytes())
        with self.fake_command('bad_rgba'): code, value = invoke(*self.command('first-last-to-video'))
        self.assertNotEqual(code,0,value); self.clean(before)
        self.assertEqual(images,(self.first.read_bytes(),self.last.read_bytes()))

    def test_cancel_and_timeout_remove_owned_conditions_before_publication(self):
        self.register(); before = self.metadata(); marker = self.root/'cancel.flag'; marker.touch()
        self.assertEqual(invoke(*self.command(),'--cancel-file',marker)[0],8); marker.unlink(); self.clean(before)
        code, value = invoke(*self.command(),'--timeout-seconds','.001')
        self.assertEqual(code,8,value); self.clean(before)

    def test_metadata_save_failure_rolls_back_already_published_movie(self):
        self.register(); before = self.metadata()
        with self.fake_command(), patch('ai_ad_editor.generation_cli.save_project', side_effect=OSError('fixture disk failure')):
            code, value = invoke(*self.command('image-to-video'))
        self.assertNotEqual(code,0,value); self.clean(before)

    def test_recipe_tamper_is_rejected_and_fragment_rebinds_both_images(self):
        self.register()
        with self.fake_command(): code, value = invoke(*self.command('first-last-to-video'))
        self.assertEqual(code,0,value); asset = value['data']['asset']; original = asset['source']['video_generation']
        bad = copy.deepcopy(asset); bad['source']['video_generation']['configuration']['frames'] = 8
        with self.assertRaises(AppError): generation.validate_recipe(bad['source']['video_generation'],asset=bad)
        library = self.base/'library'; request = self.base/'fragment.json'
        request.write_text(json.dumps(dict(id='generated_group',version=1,sequence_id='seq_main')),encoding='utf8')
        code, result = invoke('fragment','save','--project',self.root,'--library',library,'--input',request)
        self.assertEqual(code,0,result)
        target, _ = create_project(self.base/'target')
        request.write_text(json.dumps(dict(id='generated_group',version=1,sequence_id='seq_main',
            track_id='track_video_1',at_tick=0,instance_id='reuse')),encoding='utf8')
        code, result = invoke('fragment','apply','--project',target,'--library',library,'--input',request)
        self.assertEqual(code,0,result)
        imported = json.loads((target/'project.json').read_bytes())
        asset = next(a for a in imported['assets'] if a.get('source',{}).get('video_generation'))
        rebound = asset['source']['video_generation']; self.assertNotEqual(original['sha256'],rebound['sha256'])
        for name in ('first','last'):
            self.assertNotEqual(original['images'][name]['asset_id'],rebound['images'][name]['asset_id'])
            self.assertEqual(original['images'][name]['sha256'],rebound['images'][name]['sha256'])
        self.assertEqual(invoke('validate','--project',target)[0],0)

    def test_crashed_generation_workspace_cleans_only_owned_uncommitted_files(self):
        before = self.metadata(); original = self.first.read_bytes()
        job = Workspace(self.root,'video-generation'); condition = job.path/'conditions.mov'; condition.write_bytes(b'condition')
        output = self.root/'assets/derived/orphan.mov'; job.publish(condition,output); job.lease.close()
        preview = recover_workspaces(self.root,dry_run=True); self.assertTrue(output.exists())
        self.assertEqual(preview['cleaned'],0)
        proof = recover_workspaces(self.root); self.assertEqual(proof['cleaned'],1)
        self.assertFalse(output.exists()); self.assertEqual(original,self.first.read_bytes()); self.clean(before)


if __name__ == '__main__': unittest.main()
