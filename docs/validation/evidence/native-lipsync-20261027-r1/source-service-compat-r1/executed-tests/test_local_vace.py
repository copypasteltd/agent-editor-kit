"""Joint-window behavior and real FFmpeg protocol tests; fixtures are not model quality evidence."""
from __future__ import annotations

import copy
import hashlib
import io
import json
import math
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from types import ModuleType
from unittest.mock import patch

import numpy as np
from PIL import Image

import test_local_matting as base_fixture
import test_local_inpainting as inpaint_fixture
from ai_ad_editor.errors import AppError
from ai_ad_editor.local_inpainting import normalize_options
from ai_ad_editor.local_matting import manifest_hash
from ai_ad_editor.local_matting import _pipeline_workspace
from ai_ad_editor.local_vace import VACE_ENGINE, MODEL_FILES, buffer_budget, model_files, normalize_generation, settings, verify_adapter, window_plan
from ai_ad_editor.runtime import configure_local_runtime
from ai_ad_editor.utils import atomic_write_json
from ai_ad_editor.vace_model import WEIGHT_FILES, load_local_weights, validate_weight_reads
from ai_ad_editor.vace_frames import process_frames

invoke=base_fixture.invoke


class VaceWindowTests(unittest.TestCase):
    def run_frames(self, *, frames=8, window=17, overlap=4, cuts=None, channel='alpha', options=None, infer=None, empty=False, generation_options=None):
        original=np.full((frames,48,64,4),180,np.uint8);original[:,:,:,3]=np.arange(64,dtype=np.uint8)[None,None,:]*4
        mask=np.zeros_like(original)
        if not empty:mask[:,16:32,24:40,3]=255;mask[:,16:32,24:40,:3]=255
        if channel=='luma':mask[:,:,:,3]=255
        generation=normalize_generation(prompt='保留背景纹理。\nDo not change the camera.',window_frames=window,window_overlap=overlap,scene_cut_frames=cuts,frames=frames,**(generation_options or {}))
        paired=np.concatenate([original,mask],axis=2)
        output=io.BytesIO();calls=[]
        def model(images,masks,g):
            calls.append((images.copy(),masks.copy(),copy.deepcopy(g)))
            return infer(images,masks,g) if infer else np.full(images.shape,.2,np.float32)
        metrics=process_frames(io.BytesIO(paired.tobytes()),output,width=64,height=48,frames=frames,generation=generation,channel=channel,
                               options=options or normalize_options(grow=0,context=0),infer=model)
        result=np.frombuffer(output.getvalue(),np.uint8).reshape(original.shape)
        return original,mask,result,metrics,calls

    def test_harmonic_runs_after_fractional_overlap_mix_and_preserves_original_alpha(self):
        from ai_ad_editor.repair_blend import harmonize_region, validate_blend_report
        observed=[]
        def blend(source,prediction,selected,**kw):
            observed.append(prediction.copy());return harmonize_region(source,prediction,selected,**kw)
        def model(images,masks,g):return np.full(images.shape,.2 if g['seed']==0 else .8,np.float32)
        options=normalize_options(grow=0,context=0,blend_mode='harmonic')
        with patch('ai_ad_editor.vace_frames.harmonize_region',side_effect=blend):
            original,mask,result,metrics,calls=self.run_frames(window=5,overlap=2,options=options,infer=model)
        self.assertEqual(len(calls),2);self.assertEqual(len(observed),8)
        np.testing.assert_allclose(observed[3][20,30],102,atol=1e-4)
        np.testing.assert_allclose(observed[4][20,30],153,atol=1e-4)
        np.testing.assert_array_equal(result,original)
        self.assertEqual(metrics['blend']['frames'],8)
        self.assertEqual(metrics['state_peak_bytes'],metrics['base_state_peak_bytes']+metrics['blend']['owned_array_peak_bytes'])
        validate_blend_report(metrics,options,width=64,height=48,frames=8)

    def test_harmonic_budget_full_selection_and_empty_bypass_before_model(self):
        generation=normalize_generation(prompt='empty background',window_frames=5,window_overlap=0)
        options=normalize_options(grow=0,context=0,blend_mode='harmonic')
        original=np.full((5,48,64,4),180,np.uint8);mask=np.zeros_like(original);mask[:,16:32,24:40,3]=255
        def run(budget=512*1024**2):
            return process_frames(io.BytesIO(np.concatenate([original,mask],axis=2).tobytes()),io.BytesIO(),width=64,height=48,frames=5,options=options,generation=generation,channel='alpha',budget=budget,infer=lambda *_:self.fail('Model must not load'))
        base=buffer_budget(64,48,generation,options['model_max_edge'])+64*48*24
        with self.assertRaisesRegex(ValueError,'ARRAY_BUDGET_EXCEEDED'):run(base+1)
        mask[:,:,:,3]=255
        with self.assertRaisesRegex(ValueError,'NO_BOUNDARY'):run()
        mask[:]=0;metrics=run();self.assertEqual(metrics['blend']['frames'],0);self.assertEqual(metrics['model_calls'],0)

    def test_explicit_input_scale_preserves_original_mapping_and_alpha(self):
        for factor in (1,2,4):
            with self.subTest(factor=factor):
                original,mask,result,metrics,calls=self.run_frames(window=5,overlap=2,options=normalize_options(grow=0,context=64,model_max_edge=64),generation_options={'model_input_scale':factor,'flow_shift':16})
                self.assertEqual(calls[0][0].shape,(5,64*factor,64*factor,3))
                self.assertEqual(metrics['model_peak_pixels'],5*64**2*factor**2)
                self.assertEqual(metrics['window_samples'][0]['model_size'],[64*factor,64*factor])
                selected=mask[:,:,:,3]!=0
                np.testing.assert_array_equal(result[selected,:3],51)
                np.testing.assert_array_equal(result[~selected],original[~selected])
                np.testing.assert_array_equal(result[:,:,:,3],original[:,:,:,3])
                for images,masks,generation in calls:
                    np.testing.assert_array_equal(images[masks!=0],127)
                    self.assertEqual(generation['model_input_scale'],factor);self.assertEqual(generation['flow_shift'],16.)
                def ramp(images,masks,generation):
                    h,w=images.shape[1:3];value=np.full(images.shape,.2,np.float32)
                    value[:,:,:,0]=(np.arange(w,dtype=np.float32)+.5)/w
                    value[:,:,:,1]=(np.arange(h,dtype=np.float32)[:,None]+.5)/h
                    return value
                _,mask,mapped,_,_=self.run_frames(window=5,overlap=2,options=normalize_options(grow=0,context=64,model_max_edge=64),generation_options={'model_input_scale':factor},infer=ramp)
                y,x=np.indices((48,64));reference=np.rint(np.stack([(x+.5)/64,(y+.5)/64,np.full((48,64),.2)],axis=2)*255)
                expected=np.broadcast_to(reference,mapped[:,:,:,:3].shape);selected=mask[:,:,:,3]!=0
                np.testing.assert_allclose(mapped[:,:,:,:3][selected],expected[selected],atol=1)

    def test_upscaled_conditioning_cannot_reveal_removed_source_colors(self):
        captured=[]
        for color in ([255,0,0],[0,0,255]):
            source=np.full((5,128,192,4),180,np.uint8);source[:,40:88,80:112,:3]=color
            mask=np.zeros_like(source);mask[:,40:88,80:112,3]=255
            def model(images,masks,generation):
                captured.append((images.copy(),masks.copy()));return np.full(images.shape,.5,np.float32)
            process_frames(io.BytesIO(np.concatenate([source,mask],axis=2).tobytes()),io.BytesIO(),width=192,height=128,frames=5,
                generation=normalize_generation(prompt='empty background',window_frames=5,window_overlap=0,model_input_scale=4),
                options=normalize_options(grow=0,context=1024,model_max_edge=64),channel='alpha',infer=model)
        np.testing.assert_array_equal(captured[0][0],captured[1][0]);np.testing.assert_array_equal(captured[0][1],captured[1][1])
        np.testing.assert_array_equal(captured[0][0][captured[0][1]!=0],127)

    def test_upscale_budget_fails_before_reading_or_loading_a_model(self):
        class NeverRead:
            def read(_self,*args):self.fail('Budget must reject before reading frames')
        generation=normalize_generation(prompt='background',model_input_scale=4)
        with self.assertRaisesRegex(ValueError,'WINDOW_BUFFER_BUDGET_EXCEEDED'):
            process_frames(NeverRead(),io.BytesIO(),width=512,height=288,frames=17,infer=lambda *_:self.fail('Model must not load'),
                options=normalize_options(model_max_edge=512),generation=generation,channel='alpha')

    def test_sampling_profile_defaults_and_invalid_values(self):
        default=normalize_generation(prompt='Keep original text.\n原文')
        self.assertEqual((default['flow_shift'],default['model_input_scale']),(3.,1))
        chosen=normalize_generation(prompt='Keep original text.\n原文',flow_shift=16,model_input_scale=4)
        self.assertEqual(chosen['prompt'],default['prompt']);self.assertEqual(chosen['flow_shift'],16.)
        for options in [{'flow_shift':v} for v in (True,0,float('nan'),float('inf'),33)]+[{'model_input_scale':v} for v in (True,0,3,1.5,'4')]:
            with self.subTest(options=options),self.assertRaises(AppError):normalize_generation(prompt='background',**options)

    def test_joint_context_padding_mask_and_original_alpha(self):
        original,mask,result,metrics,calls=self.run_frames()
        self.assertEqual(len(calls),1);self.assertEqual(calls[0][0].shape,(9,64,64,3))
        np.testing.assert_array_equal(calls[0][0][-1],calls[0][0][-2]);np.testing.assert_array_equal(calls[0][1][-1],calls[0][1][-2])
        np.testing.assert_array_equal(result[:,16:32,24:40,:3],51)
        selected=mask[:,:,:,3]!=0
        np.testing.assert_array_equal(result[~selected],original[~selected]);np.testing.assert_array_equal(result[:,:,:,3],original[:,:,:,3])
        self.assertEqual(metrics['padded_frames'],1);self.assertEqual(metrics['input_alpha_sha256'],metrics['output_alpha_sha256'])

    def test_selected_source_content_cannot_leak_into_resized_conditioning(self):
        captured=[]
        for color in ([255,0,0],[0,0,255]):
            original=np.full((5,128,192,4),180,np.uint8)
            original[:,40:88,80:112,:3]=color
            mask=np.zeros_like(original);mask[:,40:88,80:112,3]=255
            def infer(images,masks,generation):
                captured.append((images.copy(),masks.copy()))
                return np.full(images.shape,.5,np.float32)
            destination=io.BytesIO()
            metrics=process_frames(io.BytesIO(np.concatenate([original,mask],axis=2).tobytes()),destination,
                width=192,height=128,frames=5,generation=normalize_generation(prompt='empty gray background'),
                options=normalize_options(grow=0,context=1024,model_max_edge=64),channel='alpha',infer=infer)
            result=np.frombuffer(destination.getvalue(),np.uint8).reshape(original.shape)
            np.testing.assert_array_equal(result[mask[:,:,:,3]==0],original[mask[:,:,:,3]==0])
            self.assertEqual(metrics['conditioning'],'masked-rgb-127-before-and-after-resize')
        np.testing.assert_array_equal(captured[0][0],captured[1][0])
        np.testing.assert_array_equal(captured[0][1],captured[1][1])
        np.testing.assert_array_equal(captured[0][0][captured[0][1]!=0],127)
        self.assertTrue(np.any(captured[0][0][captured[0][1]==0]==180))

    def test_overlap_crossfade_has_known_values_and_no_duplicate_frames(self):
        _,_,result,metrics,calls=self.run_frames(window=5,overlap=2,infer=lambda image,mask,g:np.full(image.shape,.2 if g['seed']==0 else .8,np.float32))
        self.assertEqual(len(calls),2)
        np.testing.assert_array_equal(result[:,20,30,0],[51,51,51,102,153,204,204,204])
        self.assertEqual(metrics['overlap_frames_blended'],2);self.assertEqual(metrics['frames'],8)

    def test_high_overlap_keeps_all_frames_and_constant_reconstruction(self):
        _,_,result,metrics,calls=self.run_frames(frames=15,window=5,overlap=4)
        self.assertEqual(len(calls),11);self.assertEqual(metrics['overlap_frames_blended'],13)
        np.testing.assert_array_equal(result[:,20,30,0],51)

    def test_scene_boundary_has_no_joint_context_or_crossfade(self):
        _,_,result,metrics,calls=self.run_frames(frames=8,window=9,overlap=4,cuts=[4],infer=lambda a,m,g:np.full(a.shape,.2 if g['seed']==0 else .8,np.float32))
        self.assertEqual(len(calls),2);self.assertEqual(metrics['overlap_frames_blended'],0)
        np.testing.assert_array_equal(result[:,20,30,0],[51]*4+[204]*4)
        self.assertTrue(all(s['end']<=4 or s['start']>=4 for s in metrics['window_samples']))

    def test_empty_windows_bypass_model_and_preserve_all_input_bytes(self):
        original,mask,result,metrics,calls=self.run_frames(frames=14,window=5,overlap=2,empty=True)
        self.assertEqual(calls,[]);np.testing.assert_array_equal(result,original)
        self.assertEqual(metrics['model_calls'],0);self.assertEqual(metrics['empty_windows'],metrics['window_count'])
        self.assertEqual(metrics['source_rgba_sha256'],'sha256:'+hashlib.sha256(original.tobytes()).hexdigest())
        self.assertEqual(metrics['decoded_mask_rgba_sha256'],'sha256:'+hashlib.sha256(mask.tobytes()).hexdigest())

    def test_luma_and_inside_only_feather_respect_source_alpha(self):
        original,_,result,metrics,_=self.run_frames(channel='luma',options=normalize_options(grow=2,feather=2,context=0))
        np.testing.assert_array_equal(result[:,:14],original[:,:14]);np.testing.assert_array_equal(result[:,:,:,3],original[:,:,:,3])
        self.assertGreater(result[0,14,22,0],51);self.assertLess(result[0,14,22,0],180)
        self.assertEqual(metrics['mask_pixels'],400*8)

    def test_bad_model_dtype_shape_and_nonfinite_are_rejected(self):
        for callback in (lambda a,m,g:np.zeros((1,1,1,3),np.float32),lambda a,m,g:np.zeros(a.shape,np.float64),lambda a,m,g:np.full(a.shape,np.nan,np.float32)):
            with self.subTest(callback=callback),self.assertRaisesRegex(ValueError,'OUTPUT_INVALID'):self.run_frames(infer=callback)

    def test_resize_loss_and_window_memory_budget_rejected_before_model(self):
        original=np.full((1,120,180,4),255,np.uint8);mask=np.zeros_like(original);mask[0,-1,-1,3]=255
        generation=normalize_generation(prompt='repair')
        with self.assertRaisesRegex(ValueError,'MASK_LOST_DURING_RESIZE'):
            process_frames(io.BytesIO(np.concatenate([original,mask],axis=2).tobytes()),io.BytesIO(),width=180,height=120,frames=1,generation=generation,options=normalize_options(grow=0,context=1024,model_max_edge=64),channel='alpha',infer=lambda *_:self.fail())
        with self.assertRaisesRegex(ValueError,'BUFFER_BUDGET'):
            process_frames(io.BytesIO(),io.BytesIO(),width=1024,height=1024,frames=10,generation=generation,options=normalize_options(),channel='alpha',infer=lambda *_:self.fail())

    def test_partial_reads_and_truncated_or_extra_frames(self):
        class Partial(io.BytesIO):
            def read(self,n=-1):return super().read(min(n,13))
        pair=np.zeros((3,48,128,4),np.uint8);pair[:,:,:64,3]=128
        kwargs=dict(width=64,height=48,frames=3,generation=normalize_generation(prompt='repair'),options=normalize_options(),channel='alpha',infer=lambda *_:self.fail())
        metrics=process_frames(Partial(pair.tobytes()),io.BytesIO(),**kwargs);self.assertEqual(metrics['frames'],3)
        for raw in (pair.tobytes()[:-1],pair.tobytes()+b'!'):
            with self.assertRaises(ValueError):process_frames(io.BytesIO(raw),io.BytesIO(),**kwargs)

    def test_prompt_window_and_device_inputs_have_explicit_limits(self):
        for options in ({'prompt':''},{'seed':True},{'seed':-1},{'window_frames':8},{'window_overlap':17},{'scene_cut_frames':[4,4]},
                        {'scene_cut_frames':[8]},{'guidance_scale':math.nan},{'conditioning_scale':3},{'prompt_max_tokens':513},{'inference_steps':0}):
            with self.subTest(options=options),self.assertRaises(AppError):normalize_generation(**({'prompt':'repair','frames':8}|options))
        for opts in ({'device':'cpu'},{'threads':False},{'text_gpu_budget_mib':0}):
            with self.assertRaises(AppError):settings(**opts)
        g=normalize_generation(prompt='原文\n$(literal)',seed=2**63-1,window_frames=5,window_overlap=0)
        self.assertEqual(g['prompt'],'原文\n$(literal)');self.assertEqual(window_plan(10,g)[1]['seed'],0)


@unittest.skipUnless(sys.platform=='win32','Native Windows sharing behavior')
class PipelineCleanupTests(unittest.TestCase):
    def open_reader_without_delete_sharing(self,path):
        import ctypes
        from ctypes import wintypes
        kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        kernel.CreateFileW.argtypes=[wintypes.LPCWSTR,wintypes.DWORD,wintypes.DWORD,wintypes.LPVOID,wintypes.DWORD,wintypes.DWORD,wintypes.HANDLE]
        kernel.CreateFileW.restype=wintypes.HANDLE
        kernel.CloseHandle.argtypes=[wintypes.HANDLE];kernel.CloseHandle.restype=wintypes.BOOL
        handle=kernel.CreateFileW(str(path),0x80000000,3,None,3,0,None)
        if handle==ctypes.c_void_p(-1).value:raise ctypes.WinError(ctypes.get_last_error())
        return lambda:kernel.CloseHandle(handle)

    def test_transient_native_reader_is_released_and_cache_removed(self):
        configure_local_runtime()
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'.runtime/temp') as temporary:
            with _pipeline_workspace(Path(temporary)) as work:
                p=work/'worker.log';p.write_bytes(b'inference failed')
                close=self.open_reader_without_delete_sharing(p)
                thread=threading.Thread(target=lambda:(time.sleep(.2),close()))
                thread.start()
            thread.join(timeout=2)
            self.assertFalse(work.exists());self.assertFalse(thread.is_alive())

    def test_permanent_native_reader_reports_retained_cache_path(self):
        configure_local_runtime()
        with tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'.runtime/temp') as temporary:
            close=None
            try:
                with self.assertRaises(AppError) as failure:
                    with _pipeline_workspace(Path(temporary)) as work:
                        p=work/'worker.log';p.write_bytes(b'locked evidence')
                        close=self.open_reader_without_delete_sharing(p)
                self.assertEqual(failure.exception.code,'MATTING_CACHE_CLEANUP_FAILED')
                self.assertTrue(p.exists());self.assertEqual(p.read_bytes(),b'locked evidence')
            finally:
                if close:close()


def create_protocol_model(root):
    """Tiny structural files only. Never passed to Torch or asserted to be real weights."""
    root.mkdir()
    configs={
        'model_index.json':{'_class_name':'WanVACEPipeline','scheduler':['diffusers','UniPCMultistepScheduler'],'text_encoder':['transformers','UMT5EncoderModel'],'tokenizer':['transformers','T5TokenizerFast'],'transformer':['diffusers','WanVACETransformer3DModel'],'vae':['diffusers','AutoencoderKLWan']},
        'transformer/config.json':{'_class_name':'WanVACETransformer3DModel','num_attention_heads':12,'attention_head_dim':128,'num_layers':30,'in_channels':16,'out_channels':16,'text_dim':4096,'vace_in_channels':96,'patch_size':[1,2,2],'ffn_dim':8960,'freq_dim':256,'vace_layers':list(range(0,30,2)),'image_dim':None,'added_kv_proj_dim':None},
        'text_encoder/config.json':{'architectures':['UMT5EncoderModel'],'d_model':4096,'d_ff':10240,'d_kv':64,'num_heads':64,'num_layers':24,'vocab_size':256384,'feed_forward_proj':'gated-gelu'},
        'vae/config.json':{'_class_name':'AutoencoderKLWan','base_dim':96,'dim_mult':[1,2,4,4],'num_res_blocks':2,'temperal_downsample':[False,True,True],'z_dim':16,'attn_scales':[],'latents_mean':[0.]*16,'latents_std':[1.]*16},
        'scheduler/scheduler_config.json':{'_class_name':'UniPCMultistepScheduler','prediction_type':'flow_prediction','use_flow_sigmas':True,'num_train_timesteps':1000,'solver_order':2}}
    maps={'text_encoder':{},'transformer':{}}
    for i,name in enumerate(sorted(MODEL_FILES)):
        path=root/name;path.parent.mkdir(exist_ok=True,parents=True)
        if name.endswith('.safetensors'):
            key='protocol_fixture.'+str(i);header=json.dumps({key:{'dtype':'F32','shape':[1],'data_offsets':[0,4]}}).encode()
            path.write_bytes(struct.pack('<Q',len(header))+header+struct.pack('<f',.5))
            if name.startswith(('text_encoder/','transformer/')):maps[name.split('/')[0]][key]=path.name
        elif name.endswith('.json'):
            if name.endswith('.index.json'):folder=name.split('/')[0];value={'weight_map':maps[folder]}
            else:value=configs.get(name,{'protocol_fixture':True})
            atomic_write_json(path,value)
        else:path.write_bytes(b'protocol tokenizer fixture, not inference data')
    # Index files may sort before their shards; write complete maps after construction.
    for folder,stem in [('text_encoder','model'),('transformer','diffusion_pytorch_model')]:atomic_write_json(root/folder/(stem+'.safetensors.index.json'),{'weight_map':maps[folder]})


MOCK_WORKER=r'''
import json,sys,time
from pathlib import Path
sys.path.insert(0,PRODUCT_SOURCE);sys.path.insert(0,NUMPY_SOURCE)
import numpy as np
from ai_ad_editor.vace_frames import process_frames
from ai_ad_editor.vace_context import ConditioningTrace
from ai_ad_editor.utils import atomic_write_json
request=json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'));mode=sys.argv[2]
if mode in {'wait','cancel'}:
    if mode=='cancel':Path(sys.argv[3]).write_text('cancel',encoding='utf-8')
    time.sleep(20)
if mode=='fail':raise RuntimeError('controlled inference failure')
info=request['video'];shapes=[]
conditioning_trace=ConditioningTrace() if request['generation'].get('temporal_context')=='previous' else None
def model(images,masks,generation):
    if conditioning_trace is not None:conditioning_trace.add(images,masks)
    shapes.append(list(images.shape[:3]));return np.full(images.shape,.2,np.float32)
metrics=process_frames(sys.stdin.buffer,sys.stdout.buffer,width=info['width'],height=info['height'],frames=info['frames'],generation=request['generation'],options=request['inpainting'],channel=request['mask']['channel'],infer=model)
from ai_ad_editor.cuda_admission import HEADROOM_BYTES,POLICY,window_summary,record_window
# Protocol-only metadata: never presented as real device/model evidence.
def admitted(stage,required):
    return {'policy':POLICY,'stage':stage,'status':'admitted','reservation':False,'oom_guarantee':False,
      'device_uuid':'GPU-00000000-0000-0000-0000-000000000001','logical_device_index':0,'required_free_bytes':required,
      'torch_free_bytes':32*1024**3,'torch_total_bytes':32*1024**3,'physical_free_bytes':24*1024**3,
      'physical_total_bytes':32*1024**3,'effective_free_bytes':24*1024**3,
      'idle_cache_release':{'scope':'current-worker','synchronized':True,'empty_cache_called':True,
        'completed':True,'active_allocation_preserved':True,'allocated_before_bytes':1024,
        'reserved_before_bytes':2048,'allocated_after_bytes':1024,'reserved_after_bytes':1024,
        'released_reserved_bytes':1024}}
gpu={'policy':POLICY,'reservation':False,'oom_guarantee':False,'headroom_bytes':HEADROOM_BYTES,
 'text':admitted('text-weights',request['adapter']['settings']['text_gpu_budget_mib']*1024**2+HEADROOM_BYTES),
 'video':admitted('video-weights',2*1024**3+4096+HEADROOM_BYTES),'video_weight_bytes':2*1024**3,
 'prompt_embedding_bytes':4096,'windows':window_summary()}
for i in range(metrics['model_calls']):record_window(gpu['windows'],admitted('video-window-'+str(i+1),HEADROOM_BYTES))
response={'protocol':request['protocol'],'engine':request['engine'],'status':'succeeded','network':'disabled','blocked_network_events':[],
 'request_sha256':request['request_sha256'],'source_sha256':request['source']['sha256'],'adapter_sha256':request['adapter']['sha256'],
 'mask_sha256':request['mask']['sha256'],'mask_plan_sha256':request['mask']['plan_sha256'],'inpainting':request['inpainting'],'generation':request['generation'],'providers':['torch-cuda'],'metrics':metrics,
 'model_loaded':metrics['model_calls']>0,'model_execution':{'gpu_admission':gpu,'prompt_truncated':False,'prompt_extension':False,'text_encoder_released_before_generation':True,'transformer_precision':'bfloat16-with-declared-float32-stability-modules','vae_precision':'float32','prompt_token_counts':{'prompt':12,'negative_prompt':1},'window_seconds':[0.1]*metrics['model_calls'],'flow_shift':request['generation']['flow_shift'],'model_input_scale':request['generation']['model_input_scale'],'window_input_shapes':shapes}}
response['model_execution']['text_offload_hooks_removed_before_generation']=True
if conditioning_trace is not None and metrics['model_calls']:
    response['model_execution']['conditioning_trace']=conditioning_trace.snapshot()
from ai_ad_editor.vace_model import WEIGHT_FILES
response['model_execution']['local_weight_reads']=[{'component':component,'backend':'pread','files':[{'path':component+'/'+name,'opens':1} for name in sorted(names)]} for component,names in WEIGHT_FILES.items()]
files={a['path']:a['bytes'] for a in request['adapter']['artifacts']}
response['artifact_verification']={'mode':'windows-read-lock-command-scope','files_hashed':len(files),'bytes_hashed':sum(files.values()),'digest_reuses_while_locked':len(request['adapter']['artifacts']),'write_and_delete_sharing':False,'persists_across_commands':False}
if mode=='bad_blend':metrics['blend']['mode']='invented'
if mode=='bad_blend_budget':metrics['blend']['owned_array_peak_bytes']+=1
if mode=='bad_blend_residual':metrics['blend']['residual_ratio_max']=2
if mode=='bad_blend_samples':metrics['blend']['samples']=[]
if mode=='bad_generation':response['generation']={**response['generation'],'seed':99}
if mode=='bad_window':metrics['window_plan_sha256']='sha256:'+'0'*64
if mode=='bad_calls':metrics['empty_windows']+=1
if mode=='bad_alpha':metrics['output_alpha_sha256']='sha256:'+'0'*64
if mode=='bad_rgba':metrics['rgba_sha256']='sha256:'+'0'*64
if mode=='bad_network':response['blocked_network_events']=['socket.connect']
if mode=='bad_provider':response['providers']=['torch-cpu']
if mode=='bad_loaded':response['model_loaded']=False
if mode=='bad_tokens':response['model_execution']['prompt_token_counts']['prompt']=100000
if mode=='bad_flow':response['model_execution']['flow_shift']=99.
if mode=='bad_scale':response['model_execution']['model_input_scale']=0
if mode=='bad_shape':response['model_execution']['window_input_shapes'][0][0]=3
if mode=='bad_raster':response['model_execution']['window_input_shapes'][0][1]+=16*request['generation']['model_input_scale']
if mode=='missing_shapes':response['model_execution'].pop('window_input_shapes')
if mode=='bad_precision':response['model_execution']['vae_precision']='float16'
if mode=='missing_gpu':response['model_execution'].pop('gpu_admission')
if mode=='bad_gpu_device':gpu['video']['device_uuid']='GPU-00000000-0000-0000-0000-000000000002'
if mode=='bad_gpu_free':gpu['text']['physical_free_bytes']=1
if mode=='bad_gpu_count':gpu['windows']['count']+=1
if mode=='bad_gpu_guarantee':gpu['oom_guarantee']=True
if mode=='missing_gpu_cache':gpu['video'].pop('idle_cache_release')
if mode=='bad_gpu_cache':gpu['video']['idle_cache_release']['allocated_after_bytes']=1
if mode=='bad_text_hooks':response['model_execution']['text_offload_hooks_removed_before_generation']=False
if mode=='missing_reads':response['model_execution'].pop('local_weight_reads')
if mode=='bad_read_backend':response['model_execution']['local_weight_reads'][0]['backend']='mmap'
if mode=='bad_read_inventory':response['model_execution']['local_weight_reads'][0]['files'].pop()
if mode=='bad_read_count':response['model_execution']['local_weight_reads'][0]['files'][0]['opens']=True
if mode=='bad_read_duplicate':response['model_execution']['local_weight_reads'][1]=response['model_execution']['local_weight_reads'][0]
if mode=='bad_conditioning':metrics['conditioning']='original-object-pixels'
if mode=='missing_context_report':metrics.pop('temporal_context',None)
if mode=='bad_context_trace':response['model_execution']['conditioning_trace']['sha256']='sha256:'+'0'*64
if mode=='unrequested_context_report':metrics['temporal_context']={}
if mode=='bad_verification':response['artifact_verification']['digest_reuses_while_locked']=0
if mode=='race':Path(sys.argv[3]).write_bytes(b'external output')
atomic_write_json(Path(request['response']),response)
'''


class NativeVaceTests(unittest.TestCase):
    metadata=base_fixture.NativeMattingTests.metadata
    decode=base_fixture.NativeMattingTests.decode
    fake_command=base_fixture.NativeMattingTests.fake_command
    ingest=inpaint_fixture.NativeInpaintingTests.ingest

    @classmethod
    def setUpClass(cls):configure_local_runtime()

    def setUp(self):
        base_fixture.NativeMattingTests.setUp(self)
        self.model=self.base/'vace';create_protocol_model(self.model)
        self.worker.write_text(MOCK_WORKER.replace('PRODUCT_SOURCE',repr(str(Path(__file__).resolve().parents[1]/'src'))).replace('NUMPY_SOURCE',repr(str(Path(np.__file__).resolve().parent.parent))),encoding='utf-8')
        self.mask=self.base/'mask.png';pixels=np.zeros((48,64,4),np.uint8);pixels[16:32,24:40,3]=255;Image.fromarray(pixels).save(self.mask)
        self.mask_id=self.ingest(self.mask)
        self.options=['--project',str(self.root),'--adapter-id','vace','--engine',VACE_ENGINE,'--model-path',str(self.model),'--executable',sys.executable,'--evidence',str(self.evidence),'--device','cuda']
        self.output=self.root/'assets/derived/repaired.mov'

    def register(self):
        code,result=invoke('media','adapter','register',*self.options);self.assertEqual(code,0,result);return result['data']['adapter']

    def command(self):
        return ['media','inpaint','--project',str(self.root),'--asset-id',self.asset_id,'--mask-asset-id',self.mask_id,'--adapter-id','vace',
                '--derived-asset-id','repaired','--prompt','修复背景纹理。\nKeep the camera unchanged.','--window-frames','5','--window-overlap','2','--mask-grow','0','--fps','16',
                '--apply','--track-id','track_video_1','--audio-track-id','track_audio_1']

    def assert_clean_failure(self,before):
        self.assertFalse(self.output.exists());self.assertEqual(self.metadata(),before)
        self.assertFalse(list((self.root/'cache/inpainting').glob('*')));self.assertFalse((self.root/'operations/project-transaction.json').exists())

    def test_registration_dry_run_inspect_and_complete_inventory(self):
        before=self.metadata();code,result=invoke('media','adapter','register',*self.options,'--dry-run')
        self.assertEqual(code,0,result);self.assertEqual(self.metadata(),before)
        adapter=self.register();self.assertEqual(adapter['model_file_count'],17);self.assertEqual(len(adapter['artifacts']),39)
        self.assertTrue({'model_session','session_worker','session_relay'}.issubset({a['role'] for a in adapter['artifacts']}))
        self.assertTrue(verify_adapter(adapter)['ok'])
        self.assertTrue(invoke('media','adapter','inspect','--project',str(self.root),'--adapter-id','vace')[1]['data']['verification']['ok'])

    def test_missing_cuda_admission_implementation_cannot_reuse_old_manifest(self):
        adapter=self.register()
        self.assertEqual(sum(a['role']=='cuda_admission' for a in adapter['artifacts']),1)
        adapter['artifacts']=[a for a in adapter['artifacts'] if a['role']!='cuda_admission']
        adapter['sha256']=manifest_hash(adapter)
        self.assertFalse(verify_adapter(adapter)['ok'])

    def test_missing_session_implementation_cannot_attest_old_inventory(self):
        adapter=self.register()
        for role in ('model_session','session_worker','session_relay'):
            changed=copy.deepcopy(adapter)
            changed['artifacts']=[a for a in changed['artifacts'] if a['role']!=role]
            changed['sha256']=manifest_hash(changed)
            self.assertFalse(verify_adapter(changed)['ok'])

    def test_model_inventory_custom_code_architecture_and_map_rejection(self):
        missing=self.model/'tokenizer/spiece.model';original=missing.read_bytes();missing.unlink()
        with self.assertRaises(AppError):model_files(self.model)
        missing.write_bytes(original)
        extra=self.model/'custom.py';extra.write_text('not executed',encoding='utf-8')
        with self.assertRaises(AppError):model_files(self.model)
        extra.unlink()
        for name,key,value in [('text_encoder/config.json','auto_map',{}),('text_encoder/config.json','num_layers',100000),('transformer/config.json','ffn_dim',1000000)]:
            path=self.model/name;raw=path.read_bytes();data=json.loads(raw);data[key]=value;atomic_write_json(path,data)
            with self.subTest(key=key),self.assertRaises(AppError):model_files(self.model)
            path.write_bytes(raw)
        path=self.model/'text_encoder/model.safetensors.index.json';raw=path.read_bytes();data=json.loads(raw);data['weight_map'][next(iter(data['weight_map']))]='../outside.safetensors';atomic_write_json(path,data)
        with self.assertRaises(AppError):model_files(self.model)
        path.write_bytes(raw)

    def test_profile_cli_plan_reports_explicit_sampling_and_scaled_budget(self):
        self.register();before=self.metadata()
        with patch('ai_ad_editor.cli.matte_native') as worker:
            code,result=invoke(*self.command(),'--flow-shift','16','--model-input-scale','4','--dry-run')
            self.assertEqual(code,0,result);worker.assert_not_called();plan=result['data']['plan']
            self.assertEqual(plan['generation']['flow_shift'],16.);self.assertEqual(plan['generation']['model_input_scale'],4)
            self.assertEqual(plan['owned_array_budget_bytes'],buffer_budget(plan['video']['width'],plan['video']['height'],plan['generation'],plan['inpainting']['model_max_edge']))
            for flags in (['--flow-shift','nan'],['--flow-shift','0']):self.assertEqual(invoke(*self.command(),*flags,'--dry-run')[0],2)
        self.assertEqual(self.metadata(),before)

    def test_scaled_protocol_pipeline_preserves_audio_and_output_coordinates(self):
        self.register()
        with self.fake_command():code,result=invoke(*self.command(),'--flow-shift','16','--model-input-scale','4')
        self.assertEqual(code,0,result);report=result['data']['inpainting'];execution=report['worker']['model_execution']
        self.assertEqual(execution['flow_shift'],16.);self.assertEqual(execution['model_input_scale'],4)
        self.assertEqual(execution['window_input_shapes'],[[5,256,256],[5,256,256]])
        source=np.repeat(self.decode(self.source),2,axis=0);output=self.decode(self.output)
        np.testing.assert_array_equal(output[:,:16],source[:,:16]);np.testing.assert_array_equal(output[:,16:32,24:40,:3],51)
        np.testing.assert_array_equal(output[:,:,:,3],source[:,:,:,3]);self.assertTrue(report['rgba_roundtrip_verified'])
        np.testing.assert_allclose(self.decode(self.output,audio=True),self.decode(self.source,audio=True),atol=1e-5)

    def test_model_evidence_settings_and_tokenizer_tamper_rejected(self):
        adapter=self.register()
        for path in (self.evidence,self.model/'tokenizer/spiece.model',self.model/'vae/diffusion_pytorch_model.safetensors'):
            raw=path.read_bytes();path.write_bytes(raw+b'changed')
            self.assertFalse(verify_adapter(adapter)['ok'])
            with patch('ai_ad_editor.cli.matte_native') as worker:self.assertEqual(invoke(*self.command())[0],10);worker.assert_not_called()
            path.write_bytes(raw)
        changed=copy.deepcopy(adapter);changed['settings']['device']='cpu';changed['sha256']=manifest_hash(changed);self.assertFalse(verify_adapter(changed)['ok'])

    def test_dry_plan_prompt_windows_and_role_gates_do_not_execute(self):
        self.register();before=self.metadata()
        with patch('ai_ad_editor.cli.matte_native') as worker:
            code,result=invoke(*self.command(),'--dry-run');self.assertEqual(code,0,result);worker.assert_not_called()
            plan=result['data']['plan'];self.assertEqual(len(plan['windows']),2);self.assertEqual(plan['generation']['prompt'],'修复背景纹理。\nKeep the camera unchanged.')
            for opts in (['--prompt',''],['--window-frames','8'],['--scene-cut-frame','8'],['--model-max-edge','0']):self.assertNotEqual(invoke(*self.command(),*opts,'--dry-run')[0],0)
            self.assertNotEqual(invoke('media','matting','--project',str(self.root),'--asset-id',self.asset_id,'--adapter-id','vace','--derived-asset-id','wrong')[0],0)
        self.assertEqual(self.metadata(),before)

    def test_lama_rejects_vace_only_prompt_seed_and_registration_options(self):
        inpaint_fixture.NativeInpaintingTests.setUp(self)
        inpaint_fixture.NativeInpaintingTests.register(self)
        command=inpaint_fixture.NativeInpaintingTests.command(self)
        before=self.metadata()
        with patch('ai_ad_editor.cli.matte_native') as worker:
            for options in (['--prompt','repair'],['--seed','0'],['--window-frames','5'],['--flow-shift','16'],['--model-input-scale','2'],['--temporal-context','none'],['--temporal-context','previous']):
                self.assertEqual(invoke(*command,*options)[0],2)
            worker.assert_not_called()
        self.assertEqual(invoke('media','adapter','register',*self.options,'--text-gpu-budget-mib','4096')[0],2)
        self.assertEqual(self.metadata(),before)

    def test_real_ffmpeg_pipeline_preserves_audio_outside_pixels_and_rights(self):
        self.register()
        with self.fake_command():code,result=invoke(*self.command())
        self.assertEqual(code,0,result);data=result['data'];report=data['inpainting']
        self.assertTrue(report['rgba_roundtrip_verified']);self.assertEqual(report['worker']['metrics']['model_calls'],2)
        output=self.decode(self.output);source=np.repeat(self.decode(self.source),2,axis=0)
        np.testing.assert_array_equal(output[:,:16],source[:,:16]);np.testing.assert_array_equal(output[:,:,:,3],source[:,:,:,3]);np.testing.assert_array_equal(output[:,16:32,24:40,:3],51)
        self.assertTrue(data['generated_clip']);self.assertTrue(data['generated_audio_clip']);self.assertTrue(report['audio']['preserve'])
        np.testing.assert_allclose(self.decode(self.output,audio=True),self.decode(self.source,audio=True),atol=1e-5)
        self.assertEqual(len(data['rights']['derived_from']),3)
        self.assertEqual(invoke('policy','audit','--project',str(self.root))[0],0)
        self.assertEqual(invoke('rights','check','--project',str(self.root),'--target','commercial_ad')[0],7)

    def test_malformed_worker_reports_fail_without_publishing(self):
        self.register();before=self.metadata()
        for mode in ('bad_generation','bad_window','bad_calls','bad_alpha','bad_rgba','bad_network','bad_provider','bad_loaded','bad_tokens','bad_precision','bad_conditioning','bad_verification','bad_flow','bad_scale','bad_shape','bad_raster','missing_shapes','bad_blend','missing_gpu','bad_gpu_device','bad_gpu_free','bad_gpu_count','bad_gpu_guarantee','missing_gpu_cache','bad_gpu_cache','bad_text_hooks','missing_reads','bad_read_backend','bad_read_inventory','bad_read_count','bad_read_duplicate','fail'):
            with self.subTest(mode=mode),self.fake_command(mode):
                code,result=invoke(*self.command());self.assertEqual(code,6,result);self.assert_clean_failure(before)

    def test_harmonic_protocol_rollback_and_successful_delivery(self):
        self.register();before=self.metadata()
        with self.fake_command():code,result=invoke(*self.command(),'--repair-blend','harmonic','--blend-max-iterations','1')
        self.assertEqual(code,6,result);self.assert_clean_failure(before)
        for mode in ('bad_blend_budget','bad_blend_residual','bad_blend_samples'):
            with self.subTest(mode=mode),self.fake_command(mode):
                code,result=invoke(*self.command(),'--repair-blend','harmonic');self.assertEqual(code,6,result)
            self.assert_clean_failure(before)
        with self.fake_command():code,result=invoke(*self.command(),'--repair-blend','harmonic')
        self.assertEqual(code,0,result)
        report=result['data']['inpainting'];self.assertEqual(report['worker']['metrics']['blend']['frames'],8)
        self.assertTrue(report['rgba_roundtrip_verified']);self.assertTrue(report['audio']['preserve'])
        output=self.decode(self.output);source=np.repeat(self.decode(self.source),2,axis=0)
        np.testing.assert_array_equal(output[:,:16],source[:,:16]);np.testing.assert_array_equal(output[:,:,:,3],source[:,:,:,3])

    def test_timeout_cancel_kill_all_pipeline_children_and_rollback(self):
        self.register();before=self.metadata();cancel=self.base/'cancel.flag'
        real_popen=subprocess.Popen;children=[]
        def record(*args,**kwargs):
            child=real_popen(*args,**kwargs);children.append(child);return child
        for mode,opts in [('wait',['--timeout-seconds','.5']),('cancel',['--cancel-file',str(cancel)])]:
            with self.subTest(mode=mode),patch('ai_ad_editor.local_matting.subprocess.Popen',side_effect=record),self.fake_command(mode,str(cancel)):
                code,result=invoke(*self.command(),*opts);self.assertEqual(code,8,result)
            self.assertTrue(all(child.poll() is not None for child in children));self.assert_clean_failure(before);cancel.unlink(missing_ok=True)

    def test_output_race_and_project_save_failure_preserve_transaction(self):
        self.register();before=self.metadata()
        with self.fake_command('race',str(self.output)):code,result=invoke(*self.command())
        self.assertEqual(code,6,result);self.assertEqual(self.output.read_bytes(),b'external output');self.output.unlink();self.assert_clean_failure(before)
        with self.fake_command(),patch('ai_ad_editor.cli.save_project',side_effect=OSError('controlled save failure')):code,result=invoke(*self.command())
        self.assertEqual(code,6,result);self.assert_clean_failure(before)

    def test_idempotent_replay_and_project_package_restore_registry(self):
        self.register()
        with self.fake_command():code,result=invoke(*self.command(),'--idempotency-key','vace-once')
        self.assertEqual(code,0,result)
        with patch('ai_ad_editor.cli.matte_native') as worker:
            code,replay=invoke(*self.command(),'--idempotency-key','vace-once');self.assertEqual(code,0,replay);worker.assert_not_called()
            for flags in (['--flow-shift','16'],['--model-input-scale','4']):
                code,conflict=invoke(*self.command(),*flags,'--idempotency-key','vace-once')
                self.assertEqual(code,2,conflict);self.assertEqual(conflict['errors'][0]['code'],'IDEMPOTENCY_CONFLICT')
            worker.assert_not_called()
        code,snap=invoke('project','snapshot','--project',str(self.root),'--label','vace-delivery');self.assertEqual(code,0,snap)
        restored=invoke('project','restore','--project',str(self.root),'--snapshot',snap['data']['snapshot_id']);self.assertEqual(restored[0],0,restored)
        package=self.base/'vace.aevpkg.zip'
        code,result=invoke('convert','export','--project',str(self.root),'--output',str(package),'--target-format','package');self.assertEqual(code,0,result)
        code,result=invoke('convert','import','--input',str(package),'--output',str(self.base/'unpacked'));self.assertEqual(code,0,result)
        self.assertEqual(invoke('validate','--project',str(self.base/'unpacked'))[0],0)


class LocalWeightReaderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name); self.calls = []; self.report = []
        self.modules = {name: ModuleType(name) for name in (
            'safetensors', 'safetensors.torch', 'transformers', 'transformers.modeling_utils')}
        def native(filename, framework, device='cpu', *, backend='mmap'):
            self.calls.append((Path(filename), framework, device, backend)); return object()
        self.native = native
        self.modules['safetensors'].safe_open = native
        self.modules['safetensors'].torch = self.modules['safetensors.torch']
        self.modules['transformers'].modeling_utils = self.modules['transformers.modeling_utils']
        for name in ('safetensors.torch', 'transformers.modeling_utils'):
            self.modules[name].safe_open = native
        self.scope = patch.dict(sys.modules, self.modules); self.scope.start(); self.addCleanup(self.scope.stop)
        for component, names in WEIGHT_FILES.items():
            directory = self.root/component; directory.mkdir()
            for name in names: (directory/name).write_bytes(b'fake fixture, never a model')

    def options(self):
        return {'local_files_only': True, 'use_safetensors': True, 'dtype': 'sentinel-dtype',
                'device_map': {'layer': 0}, 'max_memory': {0: 7168, 'cpu': 8192}, 'output_loading_info': True}

    def loader(self, directory, **options):
        self.assertEqual(options, self.options())
        directory = Path(directory)
        for i, path in enumerate(sorted(directory.glob('*.safetensors'))):
            module = self.modules['transformers.modeling_utils' if i%2 else 'safetensors.torch']
            module.safe_open(path, framework='pt', device='cpu', backend='mmap')
        return 'same-model', {'missing_keys': [], 'unexpected_keys': []}

    def restored(self):
        for name in ('safetensors', 'safetensors.torch', 'transformers.modeling_utils'):
            self.assertIs(self.modules[name].safe_open, self.native)

    def test_each_component_routes_both_aliases_to_pread_and_preserves_model_options(self):
        for component in WEIGHT_FILES:
            result = load_local_weights(self.loader, self.root/component, read_report=self.report, **self.options())
            self.assertEqual(result, ('same-model', {'missing_keys': [], 'unexpected_keys': []})); self.restored()
        self.assertEqual(len(self.calls), 6); self.assertTrue(all(row[3]=='pread' for row in self.calls))
        validate_weight_reads(self.report)

    def test_native_failure_does_not_retry_mmap_and_restores_aliases(self):
        def failed(filename, framework, device='cpu', *, backend='mmap'):
            self.calls.append(backend); raise TypeError('backend unsupported')
        self.native = failed
        for module in ('safetensors', 'safetensors.torch', 'transformers.modeling_utils'):
            self.modules[module].safe_open = failed
        with self.assertRaisesRegex(TypeError, 'backend unsupported'):
            load_local_weights(self.loader, self.root/'vae', read_report=self.report, **self.options())
        self.assertEqual(self.calls, ['pread']); self.assertFalse(self.report); self.restored()

    def test_loader_exception_after_partial_reads_restores_aliases_without_success_report(self):
        def failed(directory, **options):
            self.modules['transformers.modeling_utils'].safe_open(Path(directory)/WEIGHT_FILES['text_encoder'][0], 'pt')
            raise RuntimeError('controlled loader failure')
        with self.assertRaisesRegex(RuntimeError, 'controlled loader failure'):
            load_local_weights(failed, self.root/'text_encoder', read_report=self.report, **self.options())
        self.assertFalse(self.report); self.restored()

    def test_unregistered_file_and_other_component_are_rejected_before_native_read(self):
        outside = self.root/'outside.safetensors'; outside.write_bytes(b'not allowed')
        for path in (outside, self.root/'text_encoder'/WEIGHT_FILES['text_encoder'][0]):
            def failed(directory, **options): self.modules['safetensors.torch'].safe_open(path, 'pt')
            with self.subTest(path=path), self.assertRaisesRegex(ValueError, 'OUTSIDE_COMPONENT'):
                load_local_weights(failed, self.root/'vae', read_report=self.report, **self.options())
            self.restored()
        self.assertFalse(self.calls); self.assertFalse(self.report)

    def test_partial_or_bypassed_load_cannot_claim_complete_weight_reads(self):
        def partial(directory, **options):
            self.modules['safetensors.torch'].safe_open(Path(directory)/WEIGHT_FILES['text_encoder'][0], 'pt')
        for loader in (partial, lambda *_a, **_k: 'bypass'):
            with self.assertRaisesRegex(ValueError, 'NOT_USED_FOR_ALL_SHARDS'):
                load_local_weights(loader, self.root/'text_encoder', read_report=self.report, **self.options())
            self.restored()
        self.assertFalse(self.report)

    def test_preexisting_alias_replacement_and_nonlocal_modes_fail_closed(self):
        for field in ('local_files_only', 'use_safetensors'):
            options=self.options(); options[field]=False
            with self.assertRaisesRegex(ValueError, 'LOCAL_SAFETENSORS_LOAD_REQUIRED'):
                load_local_weights(self.loader, self.root/'vae', read_report=self.report, **options)
        self.modules['transformers.modeling_utils'].safe_open=lambda *_a, **_k: None
        with self.assertRaisesRegex(ValueError, 'UNEXPECTED_SAFETENSORS_READER'):
            load_local_weights(self.loader, self.root/'vae', read_report=self.report, **self.options())
        self.assertFalse(self.calls)

    def test_missing_weights_and_unsupported_framework_fail_before_native_read(self):
        path=self.root/'vae'/WEIGHT_FILES['vae'][0];path.unlink()
        with self.assertRaisesRegex(ValueError, 'FILE_MISSING'):
            load_local_weights(self.loader, self.root/'vae', read_report=self.report, **self.options())
        path.write_bytes(b'fixture')
        for framework, backend in [('np', 'mmap'), ('pt', 'unknown')]:
            def failed(directory, **options): self.modules['safetensors.torch'].safe_open(path, framework, backend=backend)
            with self.assertRaisesRegex(ValueError, 'OUTSIDE_COMPONENT'):
                load_local_weights(failed, self.root/'vae', read_report=self.report, **self.options())
            self.restored()
        self.assertFalse(self.calls)

    def test_report_rejects_wrong_backend_missing_shards_duplicates_and_invalid_counts(self):
        for component in WEIGHT_FILES:
            load_local_weights(self.loader, self.root/component, read_report=self.report, **self.options())
        cases=[None, [], self.report[:2]]
        for mutate in (
            lambda v:v[0].update(backend='mmap'), lambda v:v[0]['files'].pop(),
            lambda v:v.__setitem__(1, copy.deepcopy(v[0])), lambda v:v[0]['files'][0].update(opens=True),
            lambda v:v[0]['files'][0].update(path='../escape'), lambda v:v[0].update(extra=True),
            lambda v:v[0]['files'][0].update(opens=1025)):
            value=copy.deepcopy(self.report);mutate(value);cases.append(value)
        for value in cases:
            with self.subTest(value=value), self.assertRaises(ValueError): validate_weight_reads(value)


if __name__=='__main__':unittest.main()
