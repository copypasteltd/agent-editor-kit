"""Actual native RGB decodes, original VFR clocks and owned reader lifecycle."""
from fractions import Fraction
import hashlib
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
import numpy as np
from ai_ad_editor.errors import AppError
from ai_ad_editor.float_video_source import NativeRGBSource
from ai_ad_editor.media import ffmpeg_path
from ai_ad_editor.native_video_index import IndexContext

NATIVE_CALLS=[]

def digest(path):return 'sha256:'+hashlib.sha256(path.read_bytes()).hexdigest()

class NativeFloatSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        base=Path(__file__).resolve().parents[1]/'.runtime/temp';base.mkdir(parents=True,exist_ok=True)
        cls.temp=tempfile.TemporaryDirectory(prefix='native-float-reader-',dir=base);cls.root=Path(cls.temp.name)
        rng=np.random.default_rng(20261022);cls.codes=rng.integers(0,65536,(4,4,16,32),dtype=np.uint16)
        raw=cls.root/'source.gbrap16le';raw.write_bytes(cls.codes.astype('<u2').tobytes());cls.source=cls.root/'source.nut'
        commands=[([ffmpeg_path(),'-v','error','-f','rawvideo','-pixel_format','gbrap16le','-video_size','32x16',
            '-framerate','8','-i',str(raw),'-vf',
            "setpts='(if(eq(N,0),0,if(eq(N,1),1,if(eq(N,2),3,7)))/8+5)/TB'",'-fps_mode','passthrough',
            '-c:v','ffv1','-level','3',str(cls.source)],'native-RGBA16-VFR-original'),
            ([ffmpeg_path(),'-v','error','-f','lavfi','-i','testsrc2=s=32x16:r=4:d=1','-c:v','libx264',
              '-pix_fmt','yuv420p',str(cls.root/'yuv.mp4')],'native-YUV-unsupported-control')]
        for command,label in commands:
            p=subprocess.run(command,capture_output=True,timeout=60,creationflags=subprocess.CREATE_NO_WINDOW)
            NATIVE_CALLS.append({'label':label,'command':command,'exit_code':p.returncode,
                'stderr_sha256':'sha256:'+hashlib.sha256(p.stderr).hexdigest()})
            if p.returncode:raise RuntimeError(p.stderr.decode('utf8','replace'))
        cls.source_sha=digest(cls.source)

    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()

    def reader(self,**kwargs):return NativeRGBSource(self.root,self.source,self.source_sha,**kwargs)

    def record(self,reader):
        NATIVE_CALLS.append({'test':self.id(),'command':reader.metadata['command'],
            'exit_code':reader.pipe.process.poll(),'decoded_frames':reader.position,
            'requested_prefix_complete':reader.complete,'all_source_frames_decoded':reader.metadata.get('all_source_frames_decoded',False)})

    def test_native_RGBA16_all_codes_and_original_VFR_absolute_clock(self):
        with self.reader() as reader:
            frames=list(reader)
            self.assertEqual(len(frames),4)
            for index,frame in enumerate(frames):
                self.assertEqual(frame.index,index)
                self.assertEqual(frame.pts*frame.time_base,Fraction(5)+Fraction((0,1,3,7)[index],8))
                self.assertEqual(frame.duration*frame.time_base,Fraction(1,8))
                expected=np.moveaxis(self.codes[index,[2,0,1,3]],0,-1)
                np.testing.assert_array_equal(np.rint(frame.rgba.astype(np.float64)*65535).astype(np.uint16),expected)
            self.assertTrue(reader.complete);self.assertTrue(reader.metadata['all_source_frames_decoded'])
            self.assertFalse(reader.metadata['CFR_normalization']);self.assertFalse(reader.metadata['autorotation'])
            self.assertFalse(reader.metadata['network']);self.assertEqual(reader.metadata['source_sha256'],self.source_sha)
        self.assertTrue(reader.closed);self.record(reader)

    def test_explicit_prefix_keeps_frame_clock_without_claiming_whole_source_decoded(self):
        with self.reader(stop_frame=2) as reader:
            frames=list(reader);self.assertEqual(len(frames),2)
            self.assertTrue(reader.complete);self.assertFalse(reader.metadata['all_source_frames_decoded'])
            self.assertEqual(reader.metadata['source_frame_count'],4)
            self.assertEqual(frames[-1].pts*frames[-1].time_base,Fraction(41,8))
        self.record(reader)

    def test_early_context_exit_closes_only_owned_process_and_threads(self):
        with self.reader() as reader:
            frame=reader.read();self.assertEqual(frame.index,0)
        self.assertTrue(reader.closed);self.assertFalse(reader.complete)
        self.assertIsNotNone(reader.pipe.process.poll())
        self.assertTrue(all(not thread.is_alive() for thread in reader.pipe.threads));self.record(reader)
        with self.assertRaises(AppError):reader.read()

    def test_cancel_after_first_frame_propagates_and_cleans_owned_process(self):
        marker=self.root/'read.cancel'
        try:
            with self.assertRaises(AppError) as caught:
                with self.reader(cancel_file=marker) as reader:
                    reader.read();marker.write_text('cancel',encoding='utf8');reader.read()
            self.assertEqual(caught.exception.code,'CANCELLED')
            self.assertTrue(reader.closed);self.assertIsNotNone(reader.pipe.process.poll());self.record(reader)
        finally:marker.unlink(missing_ok=True)

    def test_source_hash_change_during_decode_rejects_before_final_frame_delivery(self):
        copy=self.root/'changing.nut';shutil.copyfile(self.source,copy)
        with self.assertRaises(AppError) as caught:
            with NativeRGBSource(self.root,copy,digest(copy)) as reader:
                reader.read()
                with copy.open('ab') as stream:stream.write(b'actual-source-content-change')
                list(reader)
        self.assertEqual(caught.exception.code,'FLOAT_VIDEO_INPUT_CHANGED')
        self.assertTrue(reader.closed);self.assertFalse(reader.complete);self.record(reader)

    def test_registered_hash_mismatch_rejects_before_starting_decoder(self):
        reader=NativeRGBSource(self.root,self.source,'sha256:'+'0'*64)
        with self.assertRaises(AppError) as caught:reader.__enter__()
        self.assertEqual(caught.exception.code,'FLOAT_VIDEO_INPUT_CHANGED');self.assertIsNone(reader.pipe)

    def test_persisted_native_index_can_be_reused_without_changing_float_values(self):
        first=self.reader(persist_index=True)
        with first:expected=[f.rgba.tobytes() for f in first]
        second=self.reader(persist_index=True)
        with second:
            actual=[f.rgba.tobytes() for f in second]
            self.assertEqual(actual,expected)
            self.assertIn(second.metadata['native_index']['status'],('verified-cache-hit','cache-hit'))
        self.record(first);self.record(second)

    def test_shared_memory_index_reuse_keeps_original_clock_and_owned_values(self):
        context=IndexContext(self.root,persist=False)
        with self.reader(index_context=context) as first:a=list(first)
        with self.reader(index_context=context) as second:
            b=list(second);self.assertEqual(second.metadata['native_index']['status'],'memory-reuse')
        for left,right in zip(a,b):
            self.assertEqual((left.pts,left.duration,left.time_base),(right.pts,right.duration,right.time_base))
            self.assertEqual(left.rgba.tobytes(),right.rgba.tobytes())
        self.record(first);self.record(second)

    def test_unknown_YUV_colour_adapter_rejects_without_silent_RGB_conversion(self):
        source=self.root/'yuv.mp4';reader=NativeRGBSource(self.root,source,digest(source))
        with self.assertRaises(AppError) as caught:reader.__enter__()
        self.assertEqual(caught.exception.code,'FLOAT_PIXELS_FORMAT');self.assertIsNone(reader.pipe)

    def test_invalid_prefix_or_alpha_association_is_rejected_before_decoder(self):
        for kwargs in ({'stop_frame':0},{'stop_frame':5},{'stop_frame':True},{'alpha_association':'auto'}):
            with self.subTest(kwargs=kwargs):
                reader=self.reader(**kwargs)
                with self.assertRaises(AppError):reader.__enter__()
                self.assertIsNone(reader.pipe)
