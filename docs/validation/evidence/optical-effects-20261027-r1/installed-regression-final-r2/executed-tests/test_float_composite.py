"""Streaming CPU compositor vs published math, Decimal and actual FFmpeg."""
from decimal import Decimal,localcontext
import hashlib,json
from pathlib import Path
import subprocess,tempfile,unittest
import numpy as np
from ai_ad_editor.errors import AppError
from ai_ad_editor.float_composite import composite_rgba
from ai_ad_editor.float_raster import FloatRasterGraph,SEPARABLE,NONSEPARABLE
from ai_ad_editor.media import ffmpeg_path
from test_float_raster import reference_nonseparable,reference_separable

NATIVE_CALLS=[]
def reference(bottom,top,mode,opacity=1.,coverage=None):
    a=bottom.astype(np.float64);b=top.astype(np.float64);ab=a[...,3:4];ass=b[...,3:4]*opacity
    if coverage is not None:ass=ass*coverage[...,None]
    cb=a[...,:3];cs=b[...,:3]
    blend=reference_nonseparable(mode,cb,cs) if mode in NONSEPARABLE else reference_separable(mode,cb,cs)
    # Independent coverage partition: backdrop-only, overlap and source-only.
    p=cb*ab*(1-ass)+blend*ab*ass+cs*ass*(1-ab)
    alpha=1-(1-ab)*(1-ass)
    colour=np.divide(p,alpha,out=np.zeros_like(p),where=alpha>0)
    return np.concatenate((colour,alpha),-1).astype(np.float32)

class CPUFloatCompositeTests(unittest.TestCase):
    def samples(self):
        rng=np.random.default_rng(20261022);a=rng.random((16,32,4),dtype=np.float32);b=rng.random((16,32,4),dtype=np.float32)
        for value in (a,b):
            value[0,:,3]=0;value[1,:,3]=1;value[2,:,:3]=0;value[3,:,:3]=1;value[4,:,:3]=.5;value[5,:,:3]=.25
        return a,b

    def test_all_32_modes_match_independent_coverage_partition_and_colour_oracles(self):
        a,b=self.samples()
        for mode in sorted(set(SEPARABLE)|NONSEPARABLE):
            with self.subTest(mode=mode):
                actual,metadata=composite_rgba(a,b,mode=mode,opacity=.731,tile_pixels=37)
                np.testing.assert_allclose(actual,reference(a,b,mode,.731),rtol=0,atol=6e-8)
                self.assertEqual(metadata['mode'],mode);self.assertFalse(metadata['estimated_bytes_are_peak_RSS'])

    def native(self,a,b,mode,opacity=.731,mask=False):
        base=Path(__file__).resolve().parents[1]/'.runtime/temp';base.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='CPU-float-native-',dir=base) as directory:
            root=Path(directory);command=[ffmpeg_path(),'-v','verbose','-filter_complex_threads','1']
            for i,value in enumerate((a,b)):
                raw=root/(str(i)+'.gbrapf32le');raw.write_bytes(np.moveaxis(value[...,[1,2,0,3]],-1,0).astype('<f4').tobytes())
                command+=['-f','rawvideo','-pixel_format','gbrapf32le','-video_size','32x16','-framerate','1','-i',str(raw)]
            graph=FloatRasterGraph();top=graph.mask('1:v','X/(W-1)') if mask else '1:v';target=graph.blend('0:v',top,mode=mode,opacity=str(opacity))
            command+=['-filter_complex',graph.graph(),'-map','['+target+']','-pix_fmt','gbrapf32le','-f','rawvideo','pipe:1']
            p=subprocess.run(command,capture_output=True,timeout=60,creationflags=subprocess.CREATE_NO_WINDOW)
            NATIVE_CALLS.append({'test':self.id(),'mode':mode,'command':command,'exit_code':p.returncode,
                'source_sha256':['sha256:'+hashlib.sha256(v.tobytes()).hexdigest() for v in (a,b)],
                'stdout_sha256':'sha256:'+hashlib.sha256(p.stdout).hexdigest(),'stderr_sha256':'sha256:'+hashlib.sha256(p.stderr).hexdigest(),
                'automatic_conversions':[s for s in p.stderr.decode('utf8','replace').splitlines() if 'auto-inserting filter' in s]})
            self.assertEqual(p.returncode,0,p.stderr.decode('utf8','replace')[-2000:]);self.assertEqual(len(p.stdout),a.nbytes)
            self.assertFalse(NATIVE_CALLS[-1]['automatic_conversions'])
            return np.moveaxis(np.frombuffer(p.stdout,'<f4').reshape(4,16,32)[[2,0,1,3]],0,-1)

    def test_all_32_modes_crosscheck_actual_native_FFmpeg_without_automatic_conversions(self):
        a,b=self.samples()
        for mode in sorted(set(SEPARABLE)|NONSEPARABLE):
            with self.subTest(mode=mode):
                actual,_=composite_rgba(a,b,mode=mode,opacity=.731);native=self.native(a,b,mode)
                delta=float(np.max(np.abs(actual.astype(np.float64)-native)))
                NATIVE_CALLS[-1]['CPU_maximum_absolute_error']=delta
                self.assertLessEqual(delta,4e-7)

    def test_mask_and_opacity_modify_coverage_only_and_match_actual_native_graph(self):
        a,b=self.samples();mask=np.broadcast_to(np.arange(32,dtype=np.float32)/31,(16,32)).copy()
        actual,_=composite_rgba(a,b,opacity=.37,coverage=mask)
        np.testing.assert_allclose(actual,reference(a,b,'normal',.37,mask),atol=6e-8,rtol=0)
        native=self.native(a,b,'normal',opacity=.37,mask=True)
        self.assertLessEqual(float(np.max(np.abs(actual.astype(np.float64)-native))),4e-7)

    def test_full_65536_gray_codes_survive_opaque_composition(self):
        gray=np.arange(65536,dtype=np.float32).reshape(64,1024)/65535
        source=np.stack((gray,gray,gray,np.ones_like(gray)),-1);background=np.zeros_like(source)
        result,_=composite_rgba(background,source,tile_pixels=997)
        np.testing.assert_array_equal(result,source);self.assertEqual(np.unique(result[...,0]).size,65536)

    def test_partial_alpha_negative_and_over_one_values_against_decimal(self):
        a=np.array([[[2.53715,-.4,.16,.3]]],dtype=np.float32);b=np.array([[[-1.25,3.7,.0021,.61]]],dtype=np.float32)
        result,_=composite_rgba(a,b,opacity=.37)
        with localcontext() as context:
            context.prec=70;d=lambda v:Decimal.from_float(float(v));ab=d(a[0,0,3]);ass=d(b[0,0,3])*d(.37);alpha=ab+ass*(1-ab)
            expected=[float((d(b[0,0,c])*ass+d(a[0,0,c])*ab*(1-ass))/alpha) for c in range(3)]+[float(alpha)]
        np.testing.assert_array_equal(result[0,0],np.asarray(expected,dtype=np.float32))

    def test_subnormal_alpha_retains_straight_colour_without_underflowing_internal_product(self):
        a=np.zeros((1,1,4),dtype=np.float32);b=np.array([[[.4,.8,.12,1e-38]]],dtype=np.float32)
        result,_=composite_rgba(a,b);np.testing.assert_array_equal(result,b)

    def test_hidden_RGB_has_no_influence_and_zero_alpha_is_canonical(self):
        a,b=self.samples();a[...,3]=0;b[...,3]=0;a[...,:3]=-400;b[...,:3]=700
        result,_=composite_rgba(a,b,mode='hue');np.testing.assert_array_equal(result,0)
        a[...,3]=1; a[...,:3]=.25
        result,_=composite_rgba(a,b,mode='multiply');np.testing.assert_array_equal(result,a)

    def test_zero_opacity_does_not_require_hidden_source_RGB_in_display_domain(self):
        a,b=self.samples();b[...,:3]=300
        result,_=composite_rgba(a,b,opacity=0,mode='screen');a[a[...,3]==0,:3]=0
        np.testing.assert_array_equal(result,a)

    def test_display_modes_reject_visible_extended_domain_without_clipping(self):
        a,b=self.samples();b[8,8]=[-.01,1.001,.5,.8]
        with self.assertRaises(AppError) as caught:composite_rgba(a,b,mode='screen')
        self.assertEqual(caught.exception.code,'FLOAT_COMPOSITE_DOMAIN')
        result,_=composite_rgba(a,b);self.assertTrue(np.isfinite(result).all())

    def test_nonoverlap_extended_RGB_survives_every_display_blend_without_domain_clipping(self):
        a,b=self.samples();a[...,3]=1;a[...,:3]=[-.4,2.53715,.5];b[...,3]=0
        for mode in sorted(set(SEPARABLE)|NONSEPARABLE):
            with self.subTest(mode=mode):
                result,_=composite_rgba(a,b,mode=mode);np.testing.assert_array_equal(result,a)

    def test_all_modes_are_byte_identical_under_different_tile_lengths(self):
        a,b=self.samples()
        for mode in sorted(set(SEPARABLE)|NONSEPARABLE):
            with self.subTest(mode=mode):
                first,_=composite_rgba(a,b,mode=mode,tile_pixels=1)
                second,_=composite_rgba(a,b,mode=mode,tile_pixels=411)
                np.testing.assert_array_equal(first,second)

    def test_inputs_remain_identical_on_success_late_failure_and_cancellation(self):
        a,b=self.samples();old=(a.tobytes(),b.tobytes());composite_rgba(a,b,mode='color',tile_pixels=7)
        self.assertEqual(old,(a.tobytes(),b.tobytes()))
        b[-1,-1,3]=2;old=(a.tobytes(),b.tobytes())
        with self.assertRaises(AppError):composite_rgba(a,b,tile_pixels=7)
        self.assertEqual(old,(a.tobytes(),b.tobytes()))
        b[-1,-1,3]=.5;old=(a.tobytes(),b.tobytes());count=0
        def cancel():
            nonlocal count
            count+=1
            if count==5:raise AppError('CANCELLED','test cancellation',exit_code=8)
        with self.assertRaises(AppError):composite_rgba(a,b,tile_pixels=7,cancel=cancel)
        self.assertEqual(count,5);self.assertEqual(old,(a.tobytes(),b.tobytes()))

    def test_invalid_surfaces_values_masks_and_budgets_are_rejected(self):
        a,b=self.samples()
        for value in (None,[],a.astype(np.float64),a[...,0],a[:,::2],a[:0]):
            with self.subTest(surface=type(value).__name__),self.assertRaises(AppError):composite_rgba(a,value)
        for kwargs in ({'tile_pixels':0},{'tile_pixels':True},{'tile_pixels':262145},{'max_working_bytes':1},
            {'coverage':np.ones((16,32),np.float64)},{'coverage':np.full((16,32),np.nan,dtype=np.float32)},
            {'coverage':np.full((16,32),1.001,dtype=np.float32)},{'opacity':False},{'opacity':float('nan')},{'opacity':-1},{'cancel':3},{'mode':'unknown'}):
            with self.subTest(kwargs=list(kwargs)),self.assertRaises(AppError):composite_rgba(a,b,**kwargs)
        for value in (float('nan'),float('inf')):
            b[0,0,0]=value
            with self.assertRaises(AppError):composite_rgba(a,b)

    def test_owned_output_shares_no_storage_with_inputs_or_mask(self):
        a,b=self.samples();mask=np.ones((16,32),dtype=np.float32);result,_=composite_rgba(a,b,coverage=mask)
        self.assertFalse(np.shares_memory(result,a));self.assertFalse(np.shares_memory(result,b));self.assertFalse(np.shares_memory(result,mask))
        self.assertTrue(result.flags.c_contiguous);self.assertEqual(result.dtype,np.float32)

if __name__=='__main__':unittest.main()
