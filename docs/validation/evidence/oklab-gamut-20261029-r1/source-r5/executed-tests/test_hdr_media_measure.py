"""Native RGB/YUV encoded fixtures and independent post-codec metric checks."""
from fractions import Fraction
import contextlib
import copy
import io
import json
from pathlib import Path
import unittest
from unittest.mock import patch

import numpy as np

from ai_ad_editor import cli, hdr_media_measure as media
from ai_ad_editor.hdr_measure import LightMeter
from ai_ad_editor.float_hdr import LuminanceSignal
from ai_ad_editor.errors import AppError
from ai_ad_editor.project import save_project
from ai_ad_editor.media import ffmpeg_path
import test_float_standard_render as fixture

RECEIPTS = []
SIGNAL = dict(primaries='bt2020', transfer='linear', reference_white_nits=100)


class MeterClockTests(unittest.TestCase):
    def test_native_values_are_not_requantized_to_RGB16(self):
        value=np.array([[[.1234567,.05,.01,1]]],np.float32)
        m=LightMeter(LuminanceSignal(**SIGNAL),1,1,quantize_rgb16=False)
        m.add(0,value,Fraction(1,10)); r=m.result()
        self.assertEqual(r['peak_pixel']['maxrgb']['nits'],float(value[0,0,0])*100)
        self.assertNotEqual(r['peak_pixel']['maxrgb']['nits'],round(float(value[0,0,0])*65535)/65535*100)
        self.assertTrue(r['codec_output_measured'])

    def test_native_VFR_durations_gaps_overlaps_and_unknown_last_duration(self):
        r=media._clock([40,41,44],[1,2,3],Fraction(1,8))
        self.assertEqual(r['native_span_seconds'],'7/8')
        self.assertEqual(r['gaps_between_declared_exposures'],1)
        self.assertEqual(media._clock([0,1],[2,1],Fraction(1,10))['overlaps_between_declared_exposures'],1)
        for pts,durations in [([0,1],[1,0]),([0,0],[1,1]),([],[]),([0],[1,2])]:
            with self.subTest(pts=pts),self.assertRaises(AppError):media._clock(pts,durations,Fraction(1,10))


class NativeMediaTests(fixture.FloatStandardRenderTests):
    # Inherit only fixture helpers, not unrelated integration tests.
    def plan(self, **kwargs):
        return media.prepare(self.root,'assets/source.mkv',SIGNAL,**kwargs)

    def test_actual_RGB_all_frames_and_independent_16bit_oracle(self):
        source=np.ones((3,2,4,4),np.float32)
        source[0,:,:,:3]=[1,0,0];source[1,:,:,:3]=[.5,.5,.5];source[2,:,:,:3]=0
        self.visual(source)
        plan=self.plan();before=(self.root/'assets/source.mkv').read_bytes()
        result=media.measure(self.root,plan)
        q=np.rint(source.astype(np.float64)*65535)/65535
        self.assertAlmostEqual(result['peak_pixel']['maxrgb']['nits'],100,places=7)
        # Independent BT.2020 CIE Y primary weights: the grey frame wins Y.
        self.assertEqual(result['peak_pixel']['cie_y']['frame'],1)
        self.assertAlmostEqual(result['maximum_frame_average']['cie_y']['nits'],q[1,0,0,0]*100,places=5)
        self.assertEqual(result['frames'],3);self.assertEqual(result['analyzed_duration_seconds'],'3/10')
        self.assertEqual(result['native_decoder_exit_code'],0)
        self.assertTrue(result['owned_threads_terminated']);self.assertTrue(result['all_source_frames_measured'])
        self.assertEqual(before,(self.root/'assets/source.mkv').read_bytes())
        self.assertFalse(result['automatically_written_SEI']);RECEIPTS.append(dict(test=self.id(),result=result))

    def test_actual_YUV_limited_10bit_neutral_PQ_matches_independent_formula(self):
        # Known native ten-bit YCbCr: no RGB encoder conversion before the fixture.
        w,h,n=4,2,3
        raw=self.root/'assets/pq.yuv'
        raw.write_bytes(b''.join(np.concatenate([np.full(w*h,y,dtype='<u2'),
            np.full(w*h,512,dtype='<u2'),np.full(w*h,512,dtype='<u2')]).tobytes() for y in [64,502,940]))
        target=self.root/'assets/pq.mkv'
        self.native([ffmpeg_path(),'-v','error','-f','rawvideo','-pixel_format','yuv444p10le',
            '-video_size','4x2','-framerate','10','-i',raw,'-c:v','ffv1','-level','3',target])
        signal=dict(primaries='bt2020',transfer='pq-st2084',reference_white_nits=203)
        plan=media.prepare(self.root,'assets/pq.mkv',signal,pixel_family='yuv',
            yuv=dict(matrix='bt2020nc',range='limited',chroma_location='left'),scan='progressive')
        result=media.measure(self.root,plan)
        from test_float_hdr import pq_decimal
        expected=[pq_decimal(v) for v in [0,.5,1]]
        self.assertAlmostEqual(result['peak_pixel']['maxrgb']['nits'],10000,delta=1e-6)
        self.assertAlmostEqual(result['duration_weighted_frame_average_nits']['maxrgb'],sum(expected)/3,delta=1e-7)
        self.assertEqual(result['range_counts']['clipped_components'],0)
        self.assertEqual(result['source_reader']['native_stream']['pix_fmt'],'yuv444p10le')
        RECEIPTS.append(dict(test=self.id(),result=result,independent_PQ_nits=expected))

    def test_dry_run_does_not_start_native_reader_and_cli_is_readonly(self):
        self.visual(np.ones((1,2,4,4),np.float32));save_project(self.root,self.p)
        signal=self.root/'signal.json';signal.write_text(json.dumps(SIGNAL))
        before=(self.root/'project.json').read_bytes() if (self.root/'project.json').exists() else None
        args=['surface','measure-media','--project',self.root,'--input','assets/source.mkv',
              '--signal-json',signal,'--pixel-family','rgb']
        with patch.object(media,'probe_frames',side_effect=AssertionError('dry-run decoded')):
            code,r=self.invoke(*args,'--dry-run')
        self.assertEqual(code,0,r);self.assertFalse(r['data']['native_decode_started'])
        self.assertIn(('surface','measure-media'),cli._READ_ONLY_PROJECT_COMMANDS)
        code,actual=self.invoke(*args);self.assertEqual(code,0,actual)
        self.assertTrue(actual['data']['codec_output_measured'])
        self.assertEqual(before,(self.root/'project.json').read_bytes())
        RECEIPTS.append(dict(test=self.id(),dryrun=r,actual=actual))

    def test_signal_region_family_and_external_input_reject_before_decode(self):
        self.visual(np.ones((1,2,4,4),np.float32))
        for changes in [dict(region=[-1,0,1,1]),dict(pixel_family='rgb',scan='progressive'),
                        dict(pixel_family='yuv'),dict(range_policy='auto')]:
            with self.subTest(changes=changes),self.assertRaises(AppError):self.plan(**changes)
        with self.assertRaises(AppError):media.prepare(self.root,'assets/source.mkv',dict(primaries='bt2020',transfer='linear'))
        with self.assertRaises(AppError):media.prepare(self.root,'https://example.com/video.mp4',SIGNAL)
        plan=self.plan(region=[0,0,99,1])
        with self.assertRaises(AppError):media.measure(self.root,plan)

    def test_source_plan_mutation_and_precancel_fail_closed(self):
        self.visual(np.ones((2,2,4,4),np.float32))
        plan=self.plan();changed=copy.deepcopy(plan);changed['recipe']['signal']['reference_white_nits']=200
        with self.assertRaises(AppError):media.measure(self.root,changed)
        marker=self.root/'cancel';marker.touch()
        with self.assertRaises(AppError) as caught:media.measure(self.root,plan,cancel_file=marker)
        self.assertEqual(caught.exception.code,'CANCELLED')
        with (self.root/'assets/source.mkv').open('ab') as out:out.write(b'changed')
        with self.assertRaises(AppError):media.measure(self.root,plan)

    def test_real_first_frame_cancel_cleans_decoder(self):
        self.visual(np.ones((8,2,4,4),np.float32));marker=self.root/'cancel'
        readers=[];original=media.NativeRGBSource
        def opened(*args,**kwargs):
            reader=original(*args,**kwargs);readers.append(reader);return reader
        with patch.object(media,'NativeRGBSource',opened),self.assertRaises(AppError) as caught:
            media.measure(self.root,self.plan(),cancel_file=marker,progress=lambda *_:marker.touch())
        self.assertEqual(caught.exception.code,'CANCELLED')
        self.assertEqual(readers[0].position,1);self.assertTrue(readers[0].closed)
        self.assertIsNotNone(readers[0].pipe.process.poll())
        self.assertTrue(all(not t.is_alive() for t in readers[0].pipe.threads))

    def test_actual_native_VFR_uses_original_nonzero_PTS_and_durations(self):
        self.visual(np.ones((8,2,4,4),np.float32),vfr=True)
        plan=media.prepare(self.root,'assets/source.nut',SIGNAL)
        result=media.measure(self.root,plan)
        self.assertEqual(result['frames'],8)
        self.assertGreater(result['native_clock']['first_pts'],0)
        self.assertTrue(result['all_source_frames_measured'])
        self.assertFalse(result['source_reader']['CFR_normalization'])
        RECEIPTS.append(dict(test=self.id(),result=result))

    def test_actual_YUV_negative_components_require_explicit_clip_and_count(self):
        raw=self.root/'assets/range.yuv';target=self.root/'assets/range.mkv'
        raw.write_bytes(np.concatenate([np.full(8,64,dtype='<u2'),np.full(8,64,dtype='<u2'),
                                       np.full(8,64,dtype='<u2')]).tobytes())
        self.native([ffmpeg_path(),'-v','error','-f','rawvideo','-pixel_format','yuv444p10le',
            '-video_size','4x2','-framerate','10','-i',raw,'-c:v','ffv1','-level','3',target])
        kwargs=dict(pixel_family='yuv',yuv=dict(matrix='bt2020nc',range='limited',chroma_location='left'),scan='progressive')
        with self.assertRaises(AppError):media.measure(self.root,media.prepare(self.root,'assets/range.mkv',SIGNAL,**kwargs))
        r=media.measure(self.root,media.prepare(self.root,'assets/range.mkv',SIGNAL,range_policy='clip',**kwargs))
        self.assertEqual(r['range_counts']['negative_components'],16)
        self.assertEqual(r['range_counts']['clipped_components'],16)
        self.assertEqual(r['minimum_RGB_component_nits'],0)
        RECEIPTS.append(dict(test=self.id(),result=r))


# Prevent unittest from also collecting inherited fixture tests.
for _name in dir(fixture.FloatStandardRenderTests):
    if _name.startswith('test_') and _name not in NativeMediaTests.__dict__:
        setattr(NativeMediaTests,_name,None)
