"""Independent scalar sampling, analytic edges and byte-preserving float geometry."""
import math
import unittest
import numpy as np
from ai_ad_editor.errors import AppError
from ai_ad_editor.float_geometry import resample_rgba

IDENTITY=[[1,0,0],[0,1,0]]

def scalar_reference(source,size,matrix,method):
    width,height=size;answer=np.zeros((height,width,4),dtype=np.float64)
    for y in range(height):
        for x in range(width):
            u=sum(a*b for a,b in zip(matrix[0],(x,y,1)))
            v=sum(a*b for a,b in zip(matrix[1],(x,y,1)))
            if method=='nearest':
                xx,yy=math.floor(u+.5),math.floor(v+.5)
                if 0<=yy<len(source) and 0<=xx<source.shape[1] and source[yy,xx,3]>0:
                    answer[y,x]=source[yy,xx]
                continue
            rgb=np.zeros(3);alpha=0
            for yy in (math.floor(v),math.floor(v)+1):
                for xx in (math.floor(u),math.floor(u)+1):
                    if not (0<=yy<len(source) and 0<=xx<source.shape[1]):continue
                    weight=(1-abs(u-xx))*(1-abs(v-yy))
                    a=float(source[yy,xx,3]);rgb+=weight*a*source[yy,xx,:3].astype(np.float64);alpha+=weight*a
            answer[y,x,3]=alpha
            if alpha>0:answer[y,x,:3]=rgb/alpha
    return answer.astype(np.float32)

class FloatGeometryTests(unittest.TestCase):
    def test_identity_keeps_all_65536_gray_codes_and_source_unchanged(self):
        gray=np.arange(65536,dtype=np.float32).reshape(64,1024)/65535
        source=np.stack((gray,gray,gray,np.ones_like(gray)),axis=-1)
        original=source.tobytes()
        for method in ('nearest','bilinear'):
            with self.subTest(method=method):
                actual,meta=resample_rgba(source,(1024,64),IDENTITY,interpolation=method,tile_pixels=71)
                self.assertEqual(actual.tobytes(),original)
                self.assertEqual(np.unique(actual[...,0]).size,65536)
                self.assertFalse(meta['estimated_bytes_are_peak_RSS'])
        self.assertEqual(source.tobytes(),original)

    def test_random_affine_rotation_scale_translation_match_independent_scalar(self):
        rng=np.random.default_rng(35);source=rng.random((7,9,4),dtype=np.float32)
        source[0,:,3]=0;source[1,:,3]=1
        matrix=[[.73,-.21,-.34],[.37,1.13,-.17]]
        for method in ('nearest','bilinear'):
            with self.subTest(method=method):
                actual,_=resample_rgba(source,(11,8),matrix,interpolation=method,tile_pixels=13)
                np.testing.assert_allclose(actual,scalar_reference(source,(11,8),matrix,method),rtol=0,atol=1e-7)

    def test_integer_translation_and_outside_are_exact(self):
        source=np.arange(6*8*4,dtype=np.float32).reshape(6,8,4)/191;source[...,3]=1
        actual,_=resample_rgba(source,(12,10),[[1,0,-2],[0,1,-3]],tile_pixels=17)
        expected=np.zeros((10,12,4),dtype=np.float32);expected[3:9,2:10]=source
        np.testing.assert_array_equal(actual,expected)

    def test_quarter_turn_matches_independent_transpose(self):
        source=np.arange(3*5*4,dtype=np.float32).reshape(3,5,4)/59;source[...,3]=1
        actual,_=resample_rgba(source,(3,5),[[0,1,0],[-1,0,2]])
        np.testing.assert_array_equal(actual,np.rot90(source,k=-1))

    def test_hidden_rgb_does_not_bleed_and_edge_keeps_visible_color(self):
        source=np.array([[[1,0,0,1],[0,10000,10000,0]]],dtype=np.float32)
        actual,_=resample_rgba(source,(3,1),[[.5,0,0],[0,1,0]])
        np.testing.assert_array_equal(actual[0],[[1,0,0,1],[1,0,0,.5],[0,0,0,0]])

    def test_negative_and_high_channels_are_retained_without_HDR_claim(self):
        source=np.array([[[-2,4,100,.5],[20,-5,2,.25]]],dtype=np.float32)
        actual,meta=resample_rgba(source,(3,1),[[.5,0,0],[0,1,0]])
        expected=scalar_reference(source,(3,1),[[.5,0,0],[0,1,0]],'bilinear')
        np.testing.assert_array_equal(actual,expected)
        self.assertFalse(meta['HDR_accepted']);self.assertFalse(meta['editor_integrated'])

    def test_tiny_sources_partial_outside_and_remote_coordinates_are_finite(self):
        source=np.array([[[.12,.34,.56,.78]]],dtype=np.float32)
        for matrix in ([[1,0,-.5],[0,1,-.5]],[[1,0,1e9],[0,1,-1e9]]):
            with self.subTest(matrix=matrix):
                actual,_=resample_rgba(source,(3,4),matrix,tile_pixels=1)
                np.testing.assert_allclose(actual,scalar_reference(source,(3,4),matrix,'bilinear'),rtol=0,atol=1e-7)
                self.assertTrue(np.isfinite(actual).all())

    def test_chunk_sizes_do_not_change_numeric_results(self):
        source=np.random.default_rng(981).random((16,32,4),dtype=np.float32)
        expected,_=resample_rgba(source,(31,17),[[.9,.1,-.5],[-.1,.9,.75]],tile_pixels=527)
        for tile in (1,7,64):
            actual,_=resample_rgba(source,(31,17),[[.9,.1,-.5],[-.1,.9,.75]],tile_pixels=tile)
            np.testing.assert_array_equal(actual,expected)

    def test_invalid_surface_matrix_dimensions_and_budget_reject(self):
        source=np.ones((2,3,4),dtype=np.float32)
        for bad in (source.astype(np.float64),source[:,::-1],np.zeros((2,3,3),dtype=np.float32)):
            with self.subTest(surface=bad.shape),self.assertRaises(AppError):resample_rgba(bad,(3,2),IDENTITY)
        for size in ((True,2),(0,1),(16385,2),(8192,8192)):
            with self.subTest(size=size),self.assertRaises(AppError):resample_rgba(source,size,IDENTITY)
        for matrix in ([[0,0,0],[0,0,0]],[[1,0,float('nan')],[0,1,0]],[[True,False,False],[False,True,False]],[[1e10,0,0],[0,1,0]],'file=secret'):
            with self.subTest(matrix=matrix),self.assertRaises(AppError):resample_rgba(source,(3,2),matrix)
        with self.assertRaises(AppError):resample_rgba(source,(3,2),IDENTITY,max_working_bytes=1)
        with self.assertRaises(AppError):resample_rgba(source,(3,2),IDENTITY,tile_pixels=262145)
        with self.assertRaises(AppError):resample_rgba(source,(3,2),IDENTITY,interpolation='guess')
        for bad in (float('nan'),-1,1.1):
            value=source.copy();value[0,0,3]=bad
            with self.subTest(alpha=bad),self.assertRaises(AppError):resample_rgba(value,(3,2),IDENTITY)

    def test_cancellation_is_polled_inside_bounded_processing_without_mutation(self):
        source=np.ones((16,32,4),dtype=np.float32);before=source.tobytes();calls=0
        def cancel():
            nonlocal calls
            calls+=1
            if calls==10:raise AppError('CANCELLED','test cancellation',exit_code=8)
        with self.assertRaises(AppError) as caught:
            resample_rgba(source,(32,16),IDENTITY,tile_pixels=64,cancel=cancel)
        self.assertEqual(caught.exception.code,'CANCELLED');self.assertEqual(calls,10)
        self.assertEqual(source.tobytes(),before)
