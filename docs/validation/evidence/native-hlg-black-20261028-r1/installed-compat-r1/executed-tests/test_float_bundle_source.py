"""Verified bundle provider fixtures; actual media is checked by its smoke script."""
import hashlib,json,tempfile,unittest
from pathlib import Path
import numpy as np
from ai_ad_editor.errors import AppError
from ai_ad_editor.float_bundle import canonical
from ai_ad_editor.float_bundle_source import BundleSurfaceSource

def digest(p):return 'sha256:'+hashlib.sha256(p.read_bytes()).hexdigest()

class FloatBundleSourceTests(unittest.TestCase):
    def setUp(self):
        base=Path(__file__).resolve().parents[1]/'.runtime/temp';base.mkdir(parents=True,exist_ok=True)
        self.temp=tempfile.TemporaryDirectory(prefix='bundle-source-',dir=base);self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        original=self.root/'original.bin';original.write_bytes(b'explicit synthetic provider fixture, not a decoded media test')
        self.asset=dict(id='a',kind='video',sha256=digest(original),uri='original.bin');self.bundle=self.root/'bundle';self.bundle.mkdir()
        self.frames=np.arange(2*4*8*4,dtype=np.float32).reshape(2,4,8,4)/255;self.frames[...,3]=1
        (self.bundle/'frames.rgba-f32le').write_bytes(self.frames.astype('<f4').tobytes());(self.bundle/'clock.i64le').write_bytes(np.array([[3,30,10],[4,40,10]],'<i8').tobytes())
        recipe=dict(asset_id='a',source_sha256=self.asset['sha256'],working_signal={'primaries':'bt709','transfer':'linear'},geometry=None)
        self.manifest={'protocol':'agent-native-clock-float32-bundle-v1','pixel_format':'interleaved-straight-RGBA-f32le','frames':2,'width':8,'height':4,'native_time_base':'1/100',
            'selected_source_frame_start':3,'selected_source_frame_end_exclusive':5,'source_asset_id':'a','source_sha256':self.asset['sha256'],'geometry_boundary':None,
            'source_reader':{'format_info':{'start_time':'0.1'}},'recipe':recipe,'files':{}}
        for key,name in (('pixels','frames.rgba-f32le'),('clock','clock.i64le')):
            p=self.bundle/name;self.manifest['files'][key]={'name':name,'bytes':p.stat().st_size,'sha256':digest(p)}
        self.save()
    def save(self):
        self.manifest['recipe_sha256']='sha256:'+hashlib.sha256(canonical(self.manifest['recipe'])).hexdigest()
        (self.bundle/'bundle.json').write_text(json.dumps(self.manifest),encoding='utf8')
    def open(self,**opts):return BundleSurfaceSource(self.root,'bundle',self.asset,**opts)
    def code(self,value,fn):
        with self.assertRaises(AppError) as caught:fn()
        self.assertEqual(caught.exception.code,value)

    def test_source_frame_offset_native_origin_and_owned_copy_survive_closed_mmaps(self):
        with self.open() as s:
            actual,index=s.sample('0.2');self.assertEqual(index,3);np.testing.assert_array_equal(actual,self.frames[0]);self.assertFalse(np.shares_memory(actual,s.pixels))
            self.assertEqual(s.metadata['demux_origin'],'1/10');self.assertTrue(s.metadata['original_inputs_revalidated'])
        self.assertTrue(s.closed);self.assertIsNone(s.clock);self.assertIsNone(s.pixels);np.testing.assert_array_equal(actual,self.frames[0])
        self.code('FLOAT_BUNDLE_SOURCE_CLOSED',lambda:s.sample('0.2'));s.close()

    def test_pixel_and_original_changes_are_rejected_and_all_mmaps_close_on_failure(self):
        s=self.open();p=self.bundle/'frames.rgba-f32le'
        with p.open('r+b') as f:f.write(b'\x01\x00\x00\x00')
        self.code('FLOAT_BUNDLE_SOURCE_INPUT_CHANGED',lambda:s.sample('0.2'));self.code('FLOAT_BUNDLE_SOURCE_INPUT_CHANGED',s.close);self.assertTrue(s.closed)
        self.code('FLOAT_BUNDLE_CORRUPT',self.open)

    def test_original_bytes_revalidated_even_when_derived_bundle_is_intact(self):
        (self.root/'original.bin').write_bytes(b'changed original')
        self.code('FLOAT_BUNDLE_SOURCE_INPUT_CHANGED',self.open)

    def test_explicit_unknown_origin_is_required_and_known_origin_cannot_be_overridden(self):
        self.code('FLOAT_BUNDLE_SOURCE_CLOCK',lambda:self.open(demux_origin=0))
        self.manifest['source_reader']['format_info']['start_time']='N/A';self.save();self.code('FLOAT_BUNDLE_SOURCE_CLOCK',self.open)
        with self.open(demux_origin='1/10') as s:self.assertTrue(s.metadata['origin_from_caller']);self.assertEqual(s.sample('0.2')[1],3)

    def test_pretransformed_asset_mismatch_and_recipe_changes_are_rejected(self):
        self.manifest['recipe']['geometry']={'inverse':[[1,0,0],[0,1,0]]};self.save();self.code('FLOAT_BUNDLE_SOURCE_GEOMETRY',self.open)
        self.manifest['recipe']['geometry']=None;self.save();self.asset['id']='other';self.code('FLOAT_BUNDLE_SOURCE_ASSET',self.open)
        self.asset['id']='a';self.manifest['recipe_sha256']='sha256:'+'0'*64;(self.bundle/'bundle.json').write_text(json.dumps(self.manifest),encoding='utf8');self.code('FLOAT_BUNDLE_SOURCE_RECIPE',self.open)

    def test_cancellation_releases_owned_mmaps_without_replacing_primary_exception(self):
        calls=[]
        def cancel():
            calls.append(True)
            if len(calls)>3:raise AppError('CANCELLED','cancel frame source',exit_code=130)
        with self.assertRaises(AppError) as caught:
            with self.open(cancel=cancel) as s:s.sample('0.2')
        self.assertEqual(caught.exception.code,'CANCELLED');self.assertTrue(s.closed)

    def test_manifest_mutation_on_successful_exit_is_rejected_with_handles_released(self):
        s=self.open();self.manifest['source_reader']['format_info']['start_time']='0.2';self.save()
        self.code('FLOAT_BUNDLE_SOURCE_INPUT_CHANGED',s.close);self.assertTrue(s.closed)
        for p in self.bundle.iterdir():p.rename(p.with_suffix(p.suffix+'.released'))

if __name__=='__main__':unittest.main()
