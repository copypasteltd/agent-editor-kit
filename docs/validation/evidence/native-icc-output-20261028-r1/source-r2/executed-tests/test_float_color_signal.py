"""Independent scalar transfers, published rational matrices and colour edges."""
import math
import unittest
import numpy as np
from ai_ad_editor.errors import AppError
from ai_ad_editor.float_color_signal import ColorSignal,convert_rgba

# Independent oracle: W3C CSS Color 4's rational XYZ matrices. Production
# derives its matrices from primary xy coordinates instead of these values.
XYZ={'bt709':np.array([[506752/1228815,87881/245763,12673/70218],
    [87098/409605,175762/245763,12673/175545],[7918/409605,87881/737289,1001167/1053270]]),
    'display-p3':np.array([[608311/1250200,189793/714400,198249/1000160],
    [35783/156275,247089/357200,198249/2500400],[0,32229/714400,5220557/5000800]]),
    'bt2020':np.array([[63426534/99577255,20160776/139408157,47086771/278816314],
    [26158966/99577255,472592308/697040785,8267143/139408157],[0,19567812/697040785,295819943/278816314]])}

def surface(values):
    rgb=np.array(values,np.float32).reshape(1,-1,3)
    return np.concatenate((rgb,np.ones((*rgb.shape[:2],1),np.float32)),-1)

class FloatColorSignalTests(unittest.TestCase):
    def test_identical_signal_preserves_all_sixteen_bit_codes_and_independent_alpha(self):
        codes=np.arange(65536,dtype=np.float32).reshape(64,1024)/65535
        source=np.stack((codes,codes[:,::-1],codes,np.flip(codes)),axis=-1).copy()
        result,meta=convert_rgba(source,ColorSignal('bt709','srgb'),ColorSignal('bt709','srgb'))
        self.assertEqual(result.tobytes(),source.tobytes());self.assertFalse(np.shares_memory(source,result));self.assertTrue(meta['same_signal_byte_exact'])

    def test_srgb_published_values_inverse_and_forward_preserve_sign_and_high_values(self):
        source=surface([[0,.04045,.5],[1,-.5,1.5]])
        result,_=convert_rgba(source,ColorSignal('bt709','srgb'),ColorSignal('bt709','linear'))
        expected=[[[0,float(source[0,0,1])/12.92,.21404114048223255],[1,-.21404114048223255,((1.5+.055)/1.055)**2.4]]]
        # Compare the nearest representable public Float32 value. At 2.537,
        # half an ulp already exceeds the old fixed 6e-8 threshold.
        np.testing.assert_array_equal(result[...,:3],np.asarray(expected,dtype=np.float32))
        encoded,_=convert_rgba(surface([[.18,.5,-.5]]),ColorSignal('bt709','linear'),ColorSignal('bt709','srgb'))
        np.testing.assert_allclose(encoded[0,0,:3],[.46135612950044164,.7353569830524495,-.7353569830524495],rtol=0,atol=4e-8)

    def test_bt709_inverse_OETF_is_explicit_and_differs_from_gamma24_display_interpretation(self):
        source=surface([[.04,.5,1]])
        linear,meta=convert_rgba(source,ColorSignal('bt709','bt709-oetf'),ColorSignal('bt709','linear'))
        display,_=convert_rgba(source,ColorSignal('bt709','gamma24'),ColorSignal('bt709','linear'))
        np.testing.assert_allclose(linear[0,0,:3],[float(source[0,0,0])/4.5,((.5+.099)/1.099)**(1/.45),1],rtol=0,atol=2e-8)
        self.assertGreater(float(linear[0,0,1]-display[0,0,1]),.05)
        self.assertIn('not-BT1886',meta['bt709_interpretation'])

    def test_power_curves_match_scalar_math_and_do_not_touch_alpha(self):
        source=surface([[-.7,.2,1.2]]);source[...,3]=.271828
        for curve,power in [('gamma22',2.2),('gamma24',2.4)]:
            result,_=convert_rgba(source,ColorSignal('bt709',curve),ColorSignal('bt709','linear'))
            truth=[math.copysign(abs(float(v))**power,float(v)) for v in source[0,0,:3]]
            np.testing.assert_allclose(result[0,0,:3],truth,rtol=0,atol=6e-8);self.assertEqual(result[...,3].tobytes(),source[...,3].tobytes())

    def test_all_D65_primary_transforms_match_published_rational_XYZ_oracle(self):
        rng=np.random.default_rng(20261022);source=rng.uniform(-.5,1.5,(3,5,4)).astype(np.float32);source[...,3]=.6
        for src in XYZ:
            for dst in XYZ:
                with self.subTest(source=src,target=dst):
                    result,meta=convert_rgba(source,ColorSignal(src,'linear'),ColorSignal(dst,'linear'),tile_pixels=7)
                    xyz=np.einsum('ij,hwj->hwi',XYZ[src],source[...,:3].astype(np.float64))
                    expected=np.einsum('ij,hwj->hwi',np.linalg.inv(XYZ[dst]),xyz)
                    np.testing.assert_allclose(result[...,:3],expected,rtol=0,atol=1.2e-7);self.assertFalse(meta['chromatic_adaptation'])

    def test_wide_gamut_red_stays_above_one_and_negative_in_BT709(self):
        source=surface([[1,0,0]])
        result,meta=convert_rgba(source,ColorSignal('display-p3','linear'),ColorSignal('bt709','linear'))
        self.assertGreater(float(result[0,0,0]),1.2);self.assertLess(float(result[0,0,1]),-.04);self.assertLess(float(result[0,0,2]),-.019)
        self.assertEqual(meta['gamut_mapping'],'none');self.assertFalse(meta['HDR_accepted'])

    def test_neutral_white_and_roundtrip_between_gamuts_remain_relative(self):
        white=surface([[1,1,1],[.18,.18,.18]])
        for src in XYZ:
            for dst in XYZ:
                result,_=convert_rgba(white,ColorSignal(src,'linear'),ColorSignal(dst,'linear'))
                np.testing.assert_allclose(result,white,rtol=0,atol=6e-8)
        source=surface([[.1,.6,.9],[.8,.2,.3]])
        intermediate,_=convert_rgba(source,ColorSignal('bt709','srgb'),ColorSignal('bt2020','linear'))
        result,_=convert_rgba(intermediate,ColorSignal('bt2020','linear'),ColorSignal('bt709','srgb'))
        # An intermediate public Float32 gamut surface quantizes correlated
        # components before the inverse matrix. Reconstruct both boundaries
        # independently with the published XYZ matrices and scalar transfers.
        scalar_linear=lambda v:float(v)/12.92 if abs(float(v))<=.04045 else math.copysign(((abs(float(v))+.055)/1.055)**2.4,float(v))
        scalar_encode=lambda v:float(v)*12.92 if abs(float(v))<=.0031308 else math.copysign(1.055*abs(float(v))**(1/2.4)-.055,float(v))
        oracle_linear=np.vectorize(scalar_linear)(source[...,:3])
        oracle_mid=np.einsum('ij,hwj->hwi',np.linalg.inv(XYZ['bt2020'])@XYZ['bt709'],oracle_linear).astype(np.float32)
        np.testing.assert_array_equal(intermediate[...,:3],oracle_mid)
        oracle_back=np.einsum('ij,hwj->hwi',np.linalg.inv(XYZ['bt709'])@XYZ['bt2020'],oracle_mid.astype(np.float64))
        oracle=np.vectorize(scalar_encode)(oracle_back).astype(np.float32)
        np.testing.assert_array_max_ulp(result[...,:3],oracle,maxulp=2)
        self.assertLess(float(np.max(np.abs(result-source))),2e-7)

    def test_linear_light_black_white_mix_encodes_to_expected_srgb_value(self):
        # A half-coverage white over black is 0.5 in linear light, not in the
        # encoded signal. This checks the colour stage; actual FFmpeg over is
        # independently covered by test_float_raster and native media.
        result,_=convert_rgba(surface([[.5,.5,.5]]),ColorSignal('bt709','linear'),ColorSignal('bt709','srgb'))
        np.testing.assert_allclose(result[0,0,:3],.7353569830524495,rtol=0,atol=4e-8)
        self.assertGreater(float(result[0,0,0]),.7)

    def test_hidden_straight_RGB_is_converted_without_changing_zero_alpha(self):
        source=surface([[.5,.25,.75]]);source[...,3]=0;before=source.tobytes()
        result,_=convert_rgba(source,ColorSignal('bt709','srgb'),ColorSignal('bt709','linear'))
        self.assertTrue(np.all(result[...,3]==0));self.assertGreater(float(result[0,0,0]),.2);self.assertEqual(source.tobytes(),before)

    def test_tile_length_changes_do_not_change_rounding_or_output_bytes(self):
        source=np.random.default_rng(62).uniform(-.3,1.3,(19,31,4)).astype(np.float32);source[...,3]=.5
        outputs=[]
        for tile in (1,7,127,65536):
            value,_=convert_rgba(source,ColorSignal('display-p3','srgb'),ColorSignal('bt709','srgb'),tile_pixels=tile);outputs.append(value.tobytes())
        self.assertTrue(all(value==outputs[0] for value in outputs))

    def test_invalid_signals_surface_values_shapes_and_budgets_reject(self):
        for args in [('auto','srgb'),('bt709','auto'),('bt709','smpte2084'),('D50','linear'),([],None)]:
            with self.assertRaises(AppError):ColorSignal(*args)
        signal=ColorSignal('bt709','linear');source=surface([[.5,.5,.5],[.1,.2,.3]])
        for value in [source.astype(np.float64),source[...,::-1],source.reshape(2,4),np.empty((0,1,4),np.float32)]:
            with self.assertRaises(AppError):convert_rgba(value,signal,signal)
        for cell,value in [((0,0,0),float('nan')),((0,0,1),float('inf')),((0,0,3),1.1)]:
            invalid=source.copy();invalid[cell]=value
            with self.assertRaises(AppError):convert_rgba(invalid,signal,signal)
        for change in [{'tile_pixels':0},{'tile_pixels':True},{'max_working_bytes':1},{'max_working_bytes':True},{'cancel':1}]:
            with self.assertRaises(AppError):convert_rgba(source,signal,signal,**change)
        with self.assertRaises(AppError):convert_rgba(source,None,signal)
        with self.assertRaises(AppError) as caught:convert_rgba(surface([[1e38,0,0]]),ColorSignal('bt709','srgb'),signal)
        self.assertEqual(caught.exception.code,'FLOAT_COLOR_VALUES')

    def test_cancel_during_chunks_does_not_modify_the_caller_surface(self):
        source=np.ones((5,7,4),np.float32);before=source.tobytes();calls=[]
        def cancel():
            calls.append(1)
            if len(calls)==3:raise AppError('CANCELLED','test cancel',exit_code=8)
        with self.assertRaises(AppError) as caught:convert_rgba(source,ColorSignal('bt709','srgb'),ColorSignal('bt709','linear'),tile_pixels=3,cancel=cancel)
        self.assertEqual(caught.exception.code,'CANCELLED');self.assertEqual(source.tobytes(),before)
