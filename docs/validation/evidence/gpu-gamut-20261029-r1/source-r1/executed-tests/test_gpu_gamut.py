"""Real GPU colour math, explicit worker failure/cleanup and encoded timeline integration."""
import copy,json,tempfile,unittest
from pathlib import Path
import numpy as np
from ai_ad_editor.errors import AppError
from ai_ad_editor.float_gpu import FloatGPUSession
from ai_ad_editor.float_gpu_native import NativeGPU
from ai_ad_editor.float_hdr import map_display,LuminanceSignal
from ai_ad_editor.project import save_project
import test_float_gamut as gamut_tests
MAPPING=gamut_tests.MAPPING

RECEIPTS=[]
SIGNAL=LuminanceSignal('bt709','linear',100)

class GPUColourTests(unittest.TestCase):
    def test_binary64_random_extended_RGB_exposure_alpha_and_counts(self):
        rng=np.random.default_rng(5201)
        source=rng.uniform(-.25,5,(257,257,4)).astype(np.float32)
        source[...,1]=np.maximum(source[...,1],.2);source[...,3]=rng.uniform(0,1,(257,257))
        source[0,0]=[0,0,0,-0.];source[0,1]=[1,1,1,np.array([1],np.uint32).view(np.float32)[0]]
        before=source.tobytes();errors=[]
        with tempfile.TemporaryDirectory() as folder:
            with FloatGPUSession(folder,{'projection_acceleration':dict(mode='require',device='0.0')},max_pixels=257*257) as gpu:
                for exposure in (-3,0,2,16):
                    mapping={**MAPPING,'exposure_stops':exposure}
                    expected,_,cpu=map_display(source,SIGNAL,mapping)
                    actual,_,receipt=map_display(source,SIGNAL,mapping,gpu=gpu)
                    error=float(np.max(np.abs(actual-expected)));errors.append(error)
                    self.assertLessEqual(error,2e-6)
                    np.testing.assert_array_equal(actual[...,3].view(np.uint32),source[...,3].view(np.uint32))
                    self.assertEqual(source.tobytes(),before);self.assertTrue(receipt['perceptual_gamut']['GPU'])
                    for key in ('gamut_pixels_mapped','gamut_chroma_reduced_pixels','gamut_lightness_to_black_pixels','gamut_lightness_to_white_pixels'):
                        self.assertEqual(receipt['perceptual_gamut'][key],cpu['perceptual_gamut'][key])
                    self.assertEqual(receipt['above_declared_peak_pixels'],cpu['above_declared_peak_pixels'])
                self.assertEqual(gpu.evidence['operations']['gamut_map'],4)
            self.assertTrue(gpu.evidence['worker_closed']);self.assertTrue(gpu.evidence['shared_handles_closed'])
            RECEIPTS.append(dict(scope='four-66049-pixel-GPU-mappings',errors=errors,GPU=copy.deepcopy(gpu.evidence)))

    def test_invalid_policy_is_atomic_and_valid_operation_still_works(self):
        a=np.ones((2,3,4),np.float32)
        with tempfile.TemporaryDirectory() as folder:
            with FloatGPUSession(folder,{'projection_acceleration':dict(mode='require',device='0.0')},max_pixels=6) as gpu:
                with self.assertRaises(AppError):gpu.gamut_map(a,{**MAPPING,'gamut_policy':'clip'})
                self.assertNotIn('gamut_map',gpu.evidence['operations'])
                result,_=gpu.gamut_map(a,MAPPING);self.assertTrue(np.isfinite(result).all())
            RECEIPTS.append(dict(scope='invalid-policy-before-dispatch',GPU=copy.deepcopy(gpu.evidence)))

    def test_negative_CIE_Y_worker_failure_is_not_CPU_fallback(self):
        a=np.ones((2,3,4),np.float32);a[...,:3]=-1;before=a.tobytes()
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(AppError) as caught:
                with FloatGPUSession(folder,{'projection_acceleration':dict(mode='require',device='0.0')},max_pixels=6) as gpu:
                    gpu.gamut_map(a,MAPPING)
            self.assertEqual(caught.exception.code,'FLOAT_HDR_GAMUT');self.assertEqual(a.tobytes(),before)
            self.assertTrue(gpu.evidence['worker_closed']);self.assertFalse(gpu.evidence['runtime_failure_CPU_fallback'])
            self.assertTrue(gpu.evidence['shared_handles_closed']);self.assertTrue(gpu.evidence['control']['threads_closed'])
            RECEIPTS.append(dict(scope='negative-CIE-Y-owned-worker-rejection',GPU=copy.deepcopy(gpu.evidence)))

    def test_cancellation_closes_worker_shared_handles_and_control(self):
        state=dict(armed=False,polls=0)
        def cancel():
            if state['armed']:
                state['polls']+=1
                if state['polls']>=3:raise AppError('CANCELLED','owned GPU colour cancellation',exit_code=6)
        a=np.ones((13,13,4),np.float32)
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(AppError) as caught:
                with FloatGPUSession(folder,{'projection_acceleration':dict(mode='require',device='0.0')},max_pixels=169,cancel=cancel) as gpu:
                    state['armed']=True;gpu.gamut_map(a,MAPPING)
            self.assertEqual(caught.exception.code,'CANCELLED')
            self.assertTrue(gpu.evidence['worker_closed']);self.assertTrue(gpu.evidence['shared_handles_closed'])
            self.assertTrue(gpu.evidence['control']['threads_closed']);self.assertTrue(gpu.evidence['control']['streams_closed'])
            RECEIPTS.append(dict(scope='owned-GPU-colour-cancel',GPU=copy.deepcopy(gpu.evidence)))

class GPUColourIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.g=gamut_tests.GamutIntegrationTests('runTest');self.g.setUp();self.addCleanup(self.g.doCleanups)
        self.f=self.g.f

    def test_formal_SDR_render_preview_and_complete_encoded_video_PCM(self):
        from ai_ad_editor.media import ffmpeg_path
        f=self.f;self.g.configure_SDR();cpu=f.execute('cpu.mkv')
        f.p['settings']['projection_acceleration']=dict(mode='require',device='0.0');save_project(f.root,f.p)
        actual=f.execute('gpu.mkv');meta=actual['delivery']['pixel_pipeline']
        self.assertTrue(meta['last_display_mapping']['perceptual_gamut']['GPU'])
        self.assertEqual(meta['projection_acceleration']['operations']['gamut_map'],8)
        self.assertEqual(f.decode_y(cpu['path'],32,16).tobytes(),f.decode_y(actual['path'],32,16).tobytes())
        def pcm(p):return f.native([ffmpeg_path(),'-nostdin','-v','error','-i',p,'-map','0:a:0','-vn','-c:a','pcm_f32le','-f','f32le','pipe:1'])
        self.assertEqual(pcm(cpu['path']),pcm(actual['path']));self.assertEqual(pcm(actual['path']),self.g.h.samples[:38400].tobytes())
        before=(f.root/'project.json').read_bytes()
        code,value=f.invoke('preview','frame','--project',f.root,'--frame','3','--height','64');self.assertEqual(code,0,value)
        preview=value['data'];self.assertEqual(preview['request']['display_mapping_source'],'display_mapping')
        self.assertEqual(preview['pixel_pipeline']['projection_acceleration']['operations']['gamut_map'],1)
        self.assertEqual((f.root/'project.json').read_bytes(),before)
        RECEIPTS.append(dict(scope='actual-GPU-SDR-eight-frame-encode-complete-PCM-and-inherited-preview',render=actual,preview=preview))

    def test_explicit_HDR_viewing_mapping_uses_GPU_without_author_change(self):
        f=self.f;f.p['settings']['projection_acceleration']=dict(mode='require',device='0.0');save_project(f.root,f.p)
        before=(f.root/'project.json').read_bytes()
        code,value=f.invoke('preview','frame','--project',f.root,'--frame','2','--height','64');self.assertEqual(code,0,value)
        preview=value['data'];self.assertEqual(preview['request']['display_mapping_source'],'preview_mapping')
        self.assertTrue(preview['pixel_pipeline']['last_preview_mapping']['perceptual_gamut']['GPU'])
        self.assertEqual((f.root/'project.json').read_bytes(),before)
        RECEIPTS.append(dict(scope='actual-HDR-explicit-GPU-SDR-view',preview=preview))
