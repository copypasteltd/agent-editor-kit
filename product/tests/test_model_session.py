"""Native IPC/locks and real FFmpeg transport with an explicitly synthetic model.

Real CUDA model loading and performance are validated by separate installed cases.
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
import subprocess
import sys
import time
import unittest
from unittest.mock import patch

import numpy as np

from ai_ad_editor.artifact_locks import (adopt_locked_attestation, artifact_entry, locked_attestation,
    shared_verification_scope, verification_scope)
from ai_ad_editor.errors import AppError
from ai_ad_editor import model_session as session
from ai_ad_editor.runtime import configure_local_runtime
from ai_ad_editor.vace_model import prompt_identity
from ai_ad_editor.vace_session_worker import PredictorCache
from test_video_generation import NativeGenerationTests, configuration, invoke


HARNESS = r'''
import sys,types,time
from pathlib import Path
sys.path[:0]=[PRODUCT_SITE,NUMPY_SITE]
from ai_ad_editor import vace_model, vace_session_worker
from ai_ad_editor.cuda_admission import HEADROOM_BYTES,POLICY,window_summary,record_window
from ai_ad_editor.vace_context import ConditioningTrace
import numpy as np
torch=types.ModuleType('torch');torch.__version__='synthetic-protocol-only'
torch.set_num_threads=lambda *_:None;torch.set_num_interop_threads=lambda *_:None
torch.cuda=types.SimpleNamespace(is_available=lambda:True,is_bf16_supported=lambda:True,reset_peak_memory_stats=lambda:None,max_memory_allocated=lambda:1024)
torch.backends=types.SimpleNamespace(cuda=types.SimpleNamespace(matmul=types.SimpleNamespace(allow_tf32=False)),cudnn=types.SimpleNamespace(allow_tf32=False))
sys.modules['torch']=torch
def admitted(stage,required):
 return dict(policy=POLICY,stage=stage,status='admitted',reservation=False,oom_guarantee=False,
  device_uuid='GPU-00000000-0000-0000-0000-000000000001',logical_device_index=0,required_free_bytes=required,
  torch_free_bytes=32*1024**3,torch_total_bytes=32*1024**3,physical_free_bytes=24*1024**3,physical_total_bytes=32*1024**3,effective_free_bytes=24*1024**3,
  idle_cache_release=dict(scope='current-worker',synchronized=True,empty_cache_called=True,completed=True,active_allocation_preserved=True,
  allocated_before_bytes=1024,reserved_before_bytes=2048,allocated_after_bytes=1024,reserved_after_bytes=1024,released_reserved_bytes=1024))
def load(_path,settings,generation,progress=None):
 class Model:
  def begin_generation(self,generation,progress=None):
   self.trace=ConditioningTrace() if generation.get('temporal_context')=='previous' else None
   self.generation=generation
   self.metadata=dict(versions={'torch':'synthetic-protocol-only'},prompt_truncated=False,prompt_extension=False,
    text_encoder_released_before_generation=True,text_offload_hooks_removed_before_generation=True,
    transformer_precision='bfloat16-with-declared-float32-stability-modules',vae_precision='float32',
    prompt_token_counts={'prompt':8,'negative_prompt':1},window_seconds=[],window_input_shapes=[],
    flow_shift=generation['flow_shift'],model_input_scale=generation['model_input_scale'],
    local_weight_reads=[dict(component=c,backend='pread',files=[dict(path=c+'/'+n,opens=1) for n in sorted(names)]) for c,names in vace_model.WEIGHT_FILES.items()],
    gpu_admission=dict(policy=POLICY,reservation=False,oom_guarantee=False,headroom_bytes=HEADROOM_BYTES,
     text=admitted('text-weights',settings['text_gpu_budget_mib']*1024**2+HEADROOM_BYTES),
     video=admitted('video-weights',2*1024**3+4096+HEADROOM_BYTES),video_weight_bytes=2*1024**3,prompt_embedding_bytes=4096,windows=window_summary()))
   return self.metadata
  def __call__(self,images,masks,options):
   if self.trace:
    self.trace.add(images,masks);self.metadata['conditioning_trace']=self.trace.snapshot()
   if Path(sys.argv[1]).with_name('slow.flag').exists():time.sleep(20)
   value=self.metadata['gpu_admission']['windows'];record_window(value,admitted('video-window-'+str(value['count']+1),HEADROOM_BYTES))
   self.metadata['window_seconds'].append(.01);self.metadata['window_input_shapes'].append(list(images.shape[:3]))
   return np.full(images.shape,.2,np.float32)
 model=Model();metadata=model.begin_generation(generation)
 return model,metadata
vace_model.load_predictor=load
vace_session_worker.main()
'''


class NativeSessionTests(NativeGenerationTests):
    # Reuse fixture setup only; inherited test methods are excluded by the runner.
    def start(self, **options):
        if not hasattr(self, 'adapter'): self.adapter = self.register()
        from ai_ad_editor import vace_frames
        harness = self.base/'session-harness.py'
        harness.write_text(HARNESS.replace('PRODUCT_SITE',repr(str(Path(vace_frames.__file__).resolve().parent.parent)))
            .replace('NUMPY_SITE',repr(str(Path(np.__file__).resolve().parent.parent))),encoding='utf8')
        original = subprocess.Popen
        def spawn(command, **kwargs):
            command = list(command); command[-2] = str(harness)
            return original(command, **kwargs)
        options.setdefault('idle_seconds',60)
        with patch('ai_ad_editor.model_session.subprocess.Popen',side_effect=spawn):
            value = session.launch(self.root,self.adapter,runtime_root=configure_local_runtime()['root'],**options)
        self.identity = value['session_id']; self.addCleanup(self.stop_if_alive)
        return value

    def stop_if_alive(self):
        if hasattr(self,'identity') and session.status(self.root,self.identity)['live']:
            session.stop(self.root,self.identity)

    def run_generation(self, asset, **changes):
        arguments = self.command(); arguments[arguments.index('--asset-id')+1] = asset
        for name, value in changes.items(): arguments += ['--'+name.replace('_','-'),str(value)]
        return invoke(*arguments,'--model-session',self.identity)

    def test_two_real_transports_reuse_one_model_and_reset_each_job(self):
        self.start()
        for i in range(2):
            code, value = self.run_generation('resident'+str(i),seed=i,timeline_start_seconds=i)
            self.assertEqual(code,0,value)
            result = value['data']['generation']['result']; execution=result['worker']['model_execution']
            self.assertTrue(result['rgba_roundtrip_verified'])
            self.assertEqual(execution['resident_model']['reused'],bool(i))
            self.assertEqual(execution['resident_model']['predictor_loads'],1)
            self.assertEqual(execution['resident_model']['inference_job'],i+1)
            self.assertEqual(len(execution['window_seconds']),2)
            proof=result['artifact_verification']
            self.assertEqual(proof['session_attested_files'],len(self.adapter['artifacts']))
            self.assertEqual(proof['bytes_hashed'],0)
            with self.assertRaises(PermissionError): (self.model/'model_index.json').write_bytes(b'no')
        self.assertEqual(session.status(self.root,self.identity)['completed_jobs'],2)
        before = self.metadata(); code,value=self.run_generation('changed',prompt='Different prompt.')
        self.assertEqual(code,10,value);self.assertIn('MODEL_SESSION_PROMPT_MISMATCH',str(value));self.clean(before)
        self.assertTrue(session.status(self.root,self.identity)['live'])
        stopped=session.stop(self.root,self.identity);self.assertTrue(stopped['process_exit_confirmed'])
        self.assertFalse(session.status(self.root,self.identity)['live'])
        (self.model/'tokenizer/spiece.model').write_bytes(b'write after session exit')

    def test_busy_foreign_adapter_and_invalid_stream_do_not_stop_lease_owner(self):
        self.start(); config=configuration()['sampling']
        with verification_scope(), session.lease(self.root,self.identity,self.adapter,config,timeout=30) as descriptor:
            with self.assertRaisesRegex(AppError,'MODEL_SESSION_BUSY'):
                with session.lease(self.root,self.identity,self.adapter,config,timeout=30):self.fail('busy accepted')
            connection=session.connect(session.read_config(self.root,self.identity))
            with connection:
                session.send_json(connection,dict(protocol=session.PROTOCOL,command='execute',request=dict(model_session=dict(descriptor,lease_id='wrong'))))
                self.assertFalse(session.receive_json(connection)['ok'])
            self.assertTrue(session.status(self.root,self.identity)['live'])
        wrong=copy.deepcopy(self.adapter);wrong['sha256']='sha256:'+'0'*64
        with verification_scope(),self.assertRaisesRegex(AppError,'MODEL_SESSION_ADAPTER_MISMATCH'):
            with session.lease(self.root,self.identity,wrong,config,timeout=30):self.fail('wrong adapter accepted')
        self.assertTrue(session.status(self.root,self.identity)['live'])

    def test_cancel_before_generation_retires_only_owned_session_and_rolls_back(self):
        self.start();before=self.metadata();marker=self.root/'cancel-session.flag';marker.touch()
        code,value=self.run_generation('cancelled',cancel_file=marker)
        self.assertEqual(code,8,value);self.clean(before)
        deadline=time.monotonic()+5
        while session.status(self.root,self.identity)['live'] and time.monotonic()<deadline:time.sleep(.05)
        self.assertFalse(session.status(self.root,self.identity)['live'])

    def test_inference_deadline_exits_resident_process_and_keeps_project(self):
        self.start();before=self.metadata()
        (session.directory(self.root,self.identity)/'slow.flag').touch()
        code,value=self.run_generation('deadline',timeout_seconds=3)
        self.assertNotEqual(code,0,value);self.clean(before)
        deadline=time.monotonic()+5
        while session.status(self.root,self.identity)['live'] and time.monotonic()<deadline:time.sleep(.05)
        self.assertFalse(session.status(self.root,self.identity)['live'])

    def test_owner_disconnect_retires_session_without_touching_foreign_files(self):
        self.start(); foreign=self.root/'foreign.txt';foreign.write_text('keep')
        connection=session.connect(session.read_config(self.root,self.identity))
        session.send_json(connection,dict(protocol=session.PROTOCOL,command='acquire',adapter_sha256=self.adapter['sha256'],
            generation=configuration()['sampling'],timeout=30))
        self.assertTrue(session.receive_json(connection)['ok']);connection.close()
        deadline=time.monotonic()+5
        while session.status(self.root,self.identity)['live'] and time.monotonic()<deadline:time.sleep(.05)
        self.assertFalse(session.status(self.root,self.identity)['live']);self.assertEqual(foreign.read_text(),'keep')

    def test_max_jobs_releases_model_after_successful_publication(self):
        self.start(max_jobs=1);code,value=self.run_generation('lastjob');self.assertEqual(code,0,value)
        deadline=time.monotonic()+5
        while session.status(self.root,self.identity)['live'] and time.monotonic()<deadline:time.sleep(.05)
        state=session.status(self.root,self.identity)
        self.assertFalse(state['live']);self.assertEqual(state['stop_reason'],'max-jobs-reached')
        self.assertEqual(invoke('validate','--project',self.root)[0],0)

    def test_idle_budget_exits_native_process(self):
        self.start(idle_seconds=10);deadline=time.monotonic()+15
        while session.status(self.root,self.identity)['live'] and time.monotonic()<deadline:time.sleep(.2)
        state=session.status(self.root,self.identity)
        self.assertFalse(state['live']);self.assertEqual(state['stop_reason'],'idle-budget')

    def test_changed_weight_bytes_cannot_become_ready(self):
        self.adapter=self.register(); path=next(self.model.glob('vae/*.safetensors'))
        raw=path.read_bytes();path.write_bytes(raw[:-1]+bytes([raw[-1]^1]))
        with self.assertRaises(AppError) as failure:self.start()
        self.assertEqual(failure.exception.code,'MODEL_SESSION_START_FAILED')
        states=list((self.root/'cache/model-sessions').glob('*/state.json'))
        self.assertEqual(len(states),1);self.assertEqual(json.loads(states[0].read_bytes())['status'],'failed')

    def test_control_cli_remains_available_during_active_project_write(self):
        self.start();before=self.metadata()
        (session.directory(self.root,self.identity)/'slow.flag').touch()
        program='import sys;sys.path[:0]='+repr([str(Path(session.__file__).resolve().parent.parent),str(Path(np.__file__).resolve().parent.parent)])+';from ai_ad_editor.cli import main;raise SystemExit(main(sys.argv[1:]))'
        prefix=[sys.executable,'-I','-B','-X','utf8','-c',program]
        generation_process=subprocess.Popen([*prefix,*map(str,self.command()),'--model-session',self.identity],
            stdin=subprocess.DEVNULL,stdout=subprocess.PIPE,stderr=subprocess.PIPE,creationflags=subprocess.CREATE_NO_WINDOW)
        try:
            deadline=time.monotonic()+20
            while not session.status(self.root,self.identity).get('active_inference') and time.monotonic()<deadline:
                self.assertIsNone(generation_process.poll());time.sleep(.05)
            self.assertTrue(session.status(self.root,self.identity)['active_inference'])
            for action in ('status','stop'):
                value=subprocess.run([*prefix,'media','model-session',action,'--project',str(self.root),'--session-id',self.identity],
                    capture_output=True,timeout=30,creationflags=subprocess.CREATE_NO_WINDOW)
                self.assertEqual(value.returncode,0,value.stdout.decode('utf8','replace')+value.stderr.decode('utf8','replace'))
                response=json.loads(value.stdout)
                if action=='status':self.assertTrue(response['data']['active_inference'])
                else:self.assertTrue(response['data']['process_exit_confirmed'])
            generation_process.communicate(timeout=15)
            self.assertNotEqual(generation_process.returncode,0);self.clean(before)
        finally:
            if generation_process.poll() is None:generation_process.kill()
            generation_process.communicate(timeout=15)


class SessionInvariantTests(unittest.TestCase):
    def test_prompt_contract_preserves_text_and_changes_only_explicit_fields(self):
        generation=configuration()['sampling'];original=prompt_identity(generation)
        for name,value in [('seed',9),('inference_steps',12),('flow_shift',8.)]:
            self.assertEqual(original,prompt_identity(dict(generation,**{name:value})))
        for name,value in [('prompt','new'),('negative_prompt','new'),('prompt_max_tokens',512)]:
            self.assertNotEqual(original,prompt_identity(dict(generation,**{name:value})))

    def test_predictor_cache_does_not_reload_and_resets_state(self):
        metadata={}; calls=[]
        class Model:
            def begin_generation(self,generation,progress=None):metadata.clear();calls.append('reset');return metadata
        model=Model();cache=PredictorCache('test');g=configuration()['sampling']
        with patch('ai_ad_editor.vace_model.load_predictor',return_value=(model,metadata)) as load:
            cache.predictor_for(dict(model_path='synthetic',settings={}),g,None)
            self.assertFalse(metadata['resident_model']['reused'])
            cache.predictor_for(dict(model_path='synthetic',settings={}),dict(g,seed=10),None)
            self.assertTrue(metadata['resident_model']['reused']);self.assertEqual(calls,['reset']);load.assert_called_once()
            with self.assertRaisesRegex(ValueError,'PROMPT_MISMATCH'):
                cache.predictor_for({},dict(g,prompt='other'),None)

    def test_attestation_overlap_blocks_writes_without_rehash_and_rejects_mutation(self):
        import tempfile
        with tempfile.TemporaryDirectory() as temporary:
            path=Path(temporary)/'weights.bin';path.write_bytes(b'verified local bytes')
            with verification_scope(session=True):
                artifact=artifact_entry(path,'model');proof=locked_attestation()
                with shared_verification_scope(None),verification_scope() as consumer:
                    adopt_locked_attestation(proof,[artifact])
                    self.assertEqual(consumer.summary()['bytes_hashed'],0)
                    self.assertEqual(artifact_entry(path,'model'),artifact)
                    with self.assertRaises(PermissionError):path.write_bytes(b'changed')
                for key,value in [('sha256','sha256:'+'0'*64),('bytes',1),('identity',[0,0,1,0])]:
                    changed=copy.deepcopy(proof);changed[0][key]=value
                    with shared_verification_scope(None),verification_scope(),self.assertRaises(AppError):
                        adopt_locked_attestation(changed,[artifact])
            path.write_bytes(b'changed after release')


def load_tests(loader, standard_tests, pattern):
    # Keep the existing generation suite separately counted. Only these new
    # native session tests execute here, with fixture inheritance for setup.
    names=[name for name in NativeSessionTests.__dict__ if name.startswith('test_')]
    return unittest.TestSuite([*(NativeSessionTests(name) for name in names),
                              loader.loadTestsFromTestCase(SessionInvariantTests)])
