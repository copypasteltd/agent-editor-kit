"""Actual pinned native OCIO contract tests; not a substitute for timeline acceptance."""
import unittest
from unittest.mock import patch
import numpy as np
from ai_ad_editor.errors import AppError
from ai_ad_editor import ocio_runtime as ocio

def selection(key='aces-2.1'):
    view='ACES 1.0 - SDR Video' if key=='aces-1.3' else 'ACES 2.0 - SDR 100 nits (Rec.709)'
    return dict(config=key,display='sRGB - Display',view=view,
                exposure_stops=0,input_interpretation='scene-linear-ACEScg')

class OCIORuntimeTests(unittest.TestCase):
    def sample(self):
        a=np.random.default_rng(45).uniform(-.1,5,(11,13,4)).astype(np.float32)
        a[:,:,3]=np.linspace(0,1,143,dtype=np.float32).reshape(11,13)
        a[0,0,3]=-0.0
        return a

    def test_three_real_configs(self):
        c=ocio.catalog()
        self.assertEqual(len(c['configs']),3)
        for key in ocio.CONFIGS:
            with ocio.DisplayTransform(selection(key)) as t:
                b,m=t.apply(self.sample())
                self.assertTrue(np.isfinite(b).all())
                self.assertEqual(m['frames'],1)
                self.assertFalse(m['GPU'])
            self.assertTrue(t.closed)

    def test_native_processor_equivalence(self):
        a=self.sample();expected=a.copy()
        c=ocio.config('aces-2.1');o=ocio.native()
        p=c.getProcessor(o.DisplayViewTransform(src='ACEScg',display='sRGB - Display',view=selection()['view'])).getDefaultCPUProcessor()
        p.applyRGBA(expected.reshape(-1,4));expected[:,:,3]=a[:,:,3]
        with ocio.DisplayTransform(selection()) as t:b,_=t.apply(a)
        np.testing.assert_array_equal(b,expected)

    def test_tile_alpha_and_input_ownership(self):
        a=self.sample();before=a.tobytes()
        with ocio.DisplayTransform(selection()) as t:
            b,_=t.apply(a,tile_pixels=1);c,_=t.apply(a,tile_pixels=1000)
        np.testing.assert_allclose(b,c,rtol=0,atol=2e-6)
        self.assertEqual(b[:,:,3].tobytes(),a[:,:,3].tobytes())
        self.assertEqual(a.tobytes(),before)
        self.assertFalse(np.shares_memory(a,b))

    def test_exposure_before_display_transform(self):
        a=self.sample();a[:,:,:3]*=.1
        with ocio.DisplayTransform({**selection(),'exposure_stops':2}) as t:b,_=t.apply(a)
        a[:,:,:3]*=4
        with ocio.DisplayTransform(selection()) as t:c,_=t.apply(a)
        np.testing.assert_array_equal(b,c)

    def test_invalid_configuration(self):
        for key,value in [('config',{}),('config','latest'),('view',None),('exposure_stops',True),('exposure_stops',float('nan')),('input_interpretation','display-linear')]:
            with self.subTest(key=key,value=value),self.assertRaises(AppError):ocio.DisplayTransform({**selection(),key:value})
        with self.assertRaises(AppError):ocio.DisplayTransform({**selection(),'view':'invented ACES 2.1 view'})

    def test_invalid_surfaces_and_budgets(self):
        with ocio.DisplayTransform(selection()) as t:
            for a in [np.zeros((2,3,3),np.float32),self.sample().astype(np.float64),self.sample()[:,::2],np.full((1,1,4),np.nan,np.float32)]:
                with self.subTest(shape=a.shape),self.assertRaises(AppError):t.apply(a)
            for kwargs in [dict(tile_pixels=True),dict(tile_pixels=0),dict(max_working_bytes=1)]:
                with self.assertRaises(AppError):t.apply(self.sample(),**kwargs)

    def test_cancel_does_not_count_partial_frame(self):
        calls=0
        def cancel():
            nonlocal calls
            calls+=1
            if calls==4:raise RuntimeError('cancelled')
        with ocio.DisplayTransform(selection()) as t:
            with self.assertRaisesRegex(RuntimeError,'cancelled'):t.apply(self.sample(),cancel=cancel,tile_pixels=3)
            self.assertEqual(t.metadata['frames'],0)

    def test_closed_processor_rejects_work(self):
        t=ocio.DisplayTransform(selection());t.close();t.close()
        with self.assertRaises(AppError):t.apply(self.sample())

    def test_runtime_file_hashes(self):
        self.assertEqual(len(ocio.runtime_paths()),6)
        with patch.object(ocio,'MANIFEST_SHA256','0'*64),self.assertRaises(AppError):ocio.runtime_paths()

if __name__=='__main__':unittest.main()
