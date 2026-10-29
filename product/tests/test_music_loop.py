"""Independent overlap oracle, sample-clock, real CLI rollback and package tests."""
import contextlib
import hashlib
import io
import json
import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import wave
import numpy as np

from ai_ad_editor import music_loop as loop
from ai_ad_editor.cli import main
from ai_ad_editor.errors import AppError
from ai_ad_editor.execution_control import ExecutionInterrupted
from ai_ad_editor.project import create_project

ROOT=Path(__file__).resolve().parents[2]

def write_wav(path, data, rate=48000):
    with wave.open(str(path),'wb') as w:
        w.setparams((2,2,rate,0,'NONE','not compressed'));w.writeframes(np.asarray(data,dtype='<i2').tobytes())

def read_wav(path):
    with wave.open(str(path),'rb') as w:
        return np.frombuffer(w.readframes(w.getnframes()),dtype='<i2').reshape(-1,2).copy()

class LoopFixture(unittest.TestCase):
    def setUp(self):
        base=ROOT/'local/agent-ffmpeg/music-loop60-test-work';base.mkdir(parents=True,exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(dir=base);self.addCleanup(self.temp.cleanup)
        self.home=Path(self.temp.name)
        x=np.rint(np.linspace(-10000,10000,48000)).astype('<i2')
        self.samples=np.column_stack([x,-x]).astype('<i2')
        self.source=self.home/'input.wav';write_wav(self.source,self.samples)

class LoopDSPTests(LoopFixture):
    def test_exact_cycle_shortening_and_bit_identical_unprocessed_body(self):
        target=self.home/'out.wav';stats=loop.repair_pcm(self.source,target,4800,'raised-cosine')
        data=read_wav(target);self.assertEqual(data.shape,(43200,2))
        np.testing.assert_array_equal(data[:38400],self.samples[4800:-4800])
        self.assertEqual(stats['shortened_frames'],4800)
        self.assertEqual(stats['PCM_sha256'],hashlib.sha256(data.tobytes()).hexdigest())

    def test_independent_scalar_linear_overlap_oracle(self):
        target=self.home/'out.wav';m=11;loop.repair_pcm(self.source,target,m,'linear')
        data=read_wav(target)[-m:]
        expected=np.array([[round((int(self.samples[-m+i,c])*(m-1-i)+int(self.samples[i,c])*i)/(m-1))
                            for c in range(2)] for i in range(m)])
        np.testing.assert_allclose(data,expected,atol=1,rtol=0)

    def test_independent_scalar_cosine_oracle_and_complementary_gains(self):
        target=self.home/'out.wav';m=113;loop.repair_pcm(self.source,target,m,'raised-cosine')
        expected=[]
        for i in range(m):
            w=(1-math.cos(math.pi*i/(m-1)))/2
            expected.append([round(int(self.samples[-m+i,c])*(1-w)+int(self.samples[i,c])*w) for c in range(2)])
        np.testing.assert_allclose(read_wav(target)[-m:],expected,atol=1,rtol=0)

    def test_stream_chunk_size_does_not_change_any_output_PCM(self):
        a,b=self.home/'a.wav',self.home/'b.wav'
        loop.repair_pcm(self.source,a,4800,'raised-cosine',block_size=113)
        loop.repair_pcm(self.source,b,4800,'raised-cosine',block_size=4096)
        self.assertEqual(a.read_bytes(),b.read_bytes())

    def test_actual_boundary_metric_matches_independent_PCM_measurement(self):
        p=self.home/'out.wav';s=loop.repair_pcm(self.source,p,4800,'raised-cosine');data=read_wav(p).astype(np.int32)
        self.assertEqual(s['repaired_boundary_delta'],np.max(np.abs(data[0]-data[-1]))/32768)
        self.assertLess(s['repaired_boundary_delta'],s['original_boundary_delta']/1000)
        self.assertFalse(s['perceptual_seamlessness_accepted'])

    def test_channel_polarity_and_no_normalization(self):
        p=self.home/'out.wav';s=loop.repair_pcm(self.source,p,4800,'linear');data=read_wav(p).astype(np.int32)
        np.testing.assert_array_equal(data[:,0],-data[:,1]);self.assertFalse(s['hidden_normalization'])
        self.assertLessEqual(np.abs(data).max(),np.abs(self.samples.astype(np.int32)).max())

    def test_reject_invalid_overlap_curves_bool_and_nonfinite(self):
        for value in [True,False,0,-1,float('nan'),float('inf'),5001,.001]:
            with self.assertRaises(AppError):loop.fade_samples(value,'linear')
        with self.assertRaises(AppError):loop.fade_samples(100,'invented')
        self.assertEqual(loop.fade_samples(1000/48,'linear'),1000)

    def test_reject_short_wrong_rate_and_silent_PCM(self):
        with self.assertRaises(AppError):loop.repair_pcm(self.source,self.home/'long.wav',24000,'linear')
        write_wav(self.home/'rate.wav',self.samples,44100)
        with self.assertRaises(AppError):loop.repair_pcm(self.home/'rate.wav',self.home/'wrong.wav',10,'linear')
        write_wav(self.home/'zero.wav',np.zeros((100,2)))
        with self.assertRaises(AppError):loop.repair_pcm(self.home/'zero.wav',self.home/'silent.wav',10,'linear')

    def test_truncated_declared_PCM_rejected(self):
        self.source.write_bytes(self.source.read_bytes()[:-80])
        with self.assertRaises(AppError) as err:loop.repair_pcm(self.source,self.home/'bad.wav',4800,'linear')
        self.assertEqual(err.exception.code,'MUSIC_LOOP_TRUNCATED')

    def test_recipe_strict_fields_source_hash_and_parameter_contract(self):
        value=dict(format='agent-audio-loop-v1',source_asset_id='source',source_sha256='sha256:'+'1'*64,crossfade_ms=100,curve='linear')
        self.assertEqual(loop.read_recipe(value)['asset_id'],'source')
        for bad in [dict(value,extra=True),dict(value,source_sha256='invalid'),dict(value,crossfade_ms=True),dict(value,format='invented')]:
            with self.assertRaises(AppError):loop.read_recipe(bad)

class LoopCLITests(LoopFixture):
    def setUp(self):
        super().setUp();self.project=self.home/'project';create_project(self.project,'Loop','loop_test')
        self.notice=self.home/'SOURCE.txt';self.notice.write_text('Original analytical ramp fixture CC0-1.0',encoding='utf-8')
        code,value=self.cli('media','ingest','--project',self.project,'--input',self.source,'--asset-id','source',
            '--license-spdx','CC0-1.0','--verification-status','unverified','--evidence',self.notice,'--creator','Original fixture')
        self.assertEqual(code,0,value)

    def cli(self,*args):
        output=io.StringIO()
        with contextlib.redirect_stdout(output):code=main(list(map(str,args)))
        return code,json.loads(output.getvalue())

    def metadata(self):return [(self.project/name).read_bytes() for name in ['project.json','rights-ledger.json']]
    def repair(self,*args):return self.cli('music','repair-loop','--project',self.project,'--asset-id','source',*args)

    def test_dry_run_is_readonly_and_does_not_promise_exact_decoded_length(self):
        before=self.metadata();code,value=self.repair('--dry-run')
        self.assertEqual(code,0,value);self.assertEqual(self.metadata(),before)
        self.assertTrue(value['data']['exact_sample_count_requires_decode'])
        self.assertFalse((self.project/'assets/music-loops').exists())

    def test_real_apply_preserves_unverified_permissions_and_source(self):
        before=self.source.read_bytes();code,value=self.repair('--new-asset-id','fixed','--apply','--track-id','track_audio_1')
        self.assertEqual(code,0,value);d=value['data']
        self.assertEqual(d['audio_stats']['frames'],43200);self.assertEqual(d['generated_clip']['asset_id'],'fixed')
        self.assertEqual(d['rights']['verification_status'],'unverified');self.assertEqual(d['rights']['derived_from'],['source'])
        self.assertNotIn('commercial_ad',d['rights']['permitted_uses']);self.assertEqual(self.source.read_bytes(),before)
        self.assertFalse((self.project/d['asset']['uri']).with_name('decoded.wav').exists())

    def test_invalid_placement_rejected_before_decode(self):
        before=self.metadata()
        with patch.object(loop,'run_process',side_effect=AssertionError('must not decode')):
            code,_=self.repair('--apply','--track-id','track_video_1')
        self.assertEqual(code,2);self.assertEqual(self.metadata(),before)
        self.assertFalse((self.project/'assets/music-loops').exists())

    def test_cancel_during_PCM_write_cleans_owned_tree(self):
        before=self.metadata()
        with patch.object(loop,'checkpoint',side_effect=ExecutionInterrupted('CANCELLED','cancel',exit_code=8)):
            code,_=self.repair()
        self.assertEqual(code,8);self.assertEqual(self.metadata(),before)
        self.assertEqual(list((self.project/'assets/music-loops').iterdir()),[])

    def test_failure_after_real_asset_commit_restores_project_and_rights(self):
        original,before=loop.commit_asset,self.metadata()
        def fail(*args,**kwargs):
            original(*args,**kwargs);raise AppError('INJECTED_FAILURE','after actual commit',exit_code=6)
        with patch.object(loop,'commit_asset',side_effect=fail):code,_=self.repair()
        self.assertEqual(code,6);self.assertEqual(self.metadata(),before)
        self.assertEqual(list((self.project/'assets/music-loops').iterdir()),[])

    def test_mismatched_recipe_and_explicit_option_conflict_rejected_readonly(self):
        before=self.metadata();p=self.home/'recipe.json'
        p.write_text(json.dumps(dict(format='agent-audio-loop-v1',source_asset_id='source',source_sha256='sha256:'+'0'*64,crossfade_ms=100,curve='linear')),encoding='utf-8')
        code,_=self.cli('music','repair-loop','--project',self.project,'--input',p)
        self.assertEqual(code,3);self.assertEqual(self.metadata(),before)
        code,_=self.repair('--input',p);self.assertEqual(code,2);self.assertEqual(self.metadata(),before)

    def test_package_keeps_recipe_parent_rights_and_complete_PCM_repair(self):
        code,v=self.repair('--new-asset-id','fixed');self.assertEqual(code,0,v)
        audio=read_wav(self.project/v['data']['asset']['uri']);recipe_uri=v['data']['recipe_uri']
        package=self.home/'editable.zip';code,v=self.cli('convert','export','--project',self.project,'--output',package,'--target-format','package');self.assertEqual(code,0,v)
        imported=self.home/'imported';code,v=self.cli('convert','import','--input',package,'--output',imported);self.assertEqual(code,0,v)
        self.assertTrue((imported/recipe_uri).is_file())
        code,v=self.cli('music','repair-loop','--project',imported,'--input',imported/recipe_uri,'--new-asset-id','again');self.assertEqual(code,0,v)
        np.testing.assert_array_equal(audio,read_wav(imported/v['data']['asset']['uri']))
        self.assertEqual(v['data']['rights']['verification_status'],'unverified')

    def test_blocked_parent_rights_cannot_be_laundered(self):
        p=self.project/'rights-ledger.json';ledger=json.loads(p.read_bytes())
        source=next(r for r in ledger['records'] if r['asset_id']=='source');source['takedown_status']='blocked'
        p.write_text(json.dumps(ledger),encoding='utf-8');before=self.metadata();code,v=self.repair()
        self.assertEqual(code,7,v);self.assertEqual(self.metadata(),before)
        self.assertFalse((self.project/'assets/music-loops').exists())

if __name__=='__main__':unittest.main()
