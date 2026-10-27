"""Independent matrix/vertex, native Float32 and real encoded LUT evidence."""
import copy
from fractions import Fraction
import hashlib
import itertools
import json
import math
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from ai_ad_editor.errors import AppError
from ai_ad_editor.float_color_signal import ColorSignal
from ai_ad_editor.float_effect_chain import EffectCompiler
from ai_ad_editor.float_lut import compile_lut, apply_lut, verify_dependencies, INTERPOLATIONS
from ai_ad_editor.float_timeline import FloatTimeline
from ai_ad_editor.lut_library import prepare_lut_registration, register_lut
from ai_ad_editor.media import ffmpeg_path
import test_float_timeline as fixture
import test_float_preview as preview_fixture

LINEAR = {'primaries':'bt709','transfer':'linear'}
SRGB = {'primaries':'bt709','transfer':'srgb'}


def write_cube(path, size=3, *, transform=None, domain=None):
    transform = transform or (lambda r,g,b:(.1+.7*r+.16*g*b,.02+.8*g+.1*r*b,.08+.72*b+.1*r*g))
    table = np.array([transform(r/(size-1),g/(size-1),b/(size-1))
        for b in range(size) for g in range(size) for r in range(size)],np.float32)
    header = 'TITLE "Original numeric # fixture" # comment\nLUT_3D_SIZE '+str(size)+'\n'
    if domain:
        header += 'DOMAIN_MIN '+' '.join(map(str,domain[0]))+'\nDOMAIN_MAX '+' '.join(map(str,domain[1]))+'\n'
    path.write_text(header+''.join(' '.join(format(float(c),'.9g') for c in row)+'\n' for row in table),encoding='utf8',newline='\n')
    return table.reshape(size,size,size,3)


def effect(**parameters):
    return {'type':'lut3d','parameters':{'path':'look.cube','input_signal':dict(LINEAR),'output_signal':dict(LINEAR),**parameters}}


def track(left=0,right=1,mode='linear',controls=None,stop=100,name='intensity'):
    first = {'at_tick':0,'value':left,'interpolation':mode}
    if controls is not None:first['control_points'] = controls
    return {'property':name,'keyframes':[first,{'at_tick':stop,'value':right,'interpolation':'linear'}]}


def scalar_lookup(table, values, method, domain=((0,0,0),(1,1,1))):
    """Independent per-pixel polynomial or barycentric linear-system oracle."""
    n = len(table); result = []
    def sample(v,low):
        q = np.minimum(low+np.array(v,dtype=int),n-1)
        return table[q[2],q[1],q[0]].astype(np.float64)
    for value in values:
        q = (np.minimum(1,np.maximum(0,(value-np.array(domain[0]))/(np.array(domain[1])-domain[0]))).astype(np.float32)*np.float32(n-1)).astype(np.float64)
        low = np.floor(q).astype(int); f = q-low
        if method=='nearest':
            xyz = np.floor(q+.5).astype(int); out = table[xyz[2],xyz[1],xyz[0]]
        elif method=='trilinear':
            out = np.zeros(3,np.float64)
            for vertex in itertools.product((0,1),repeat=3):
                weight = math.prod(f[a] if vertex[a] else 1-f[a] for a in range(3))
                out += sample(vertex,low)*weight
        elif method=='tetrahedral':
            for permutation in itertools.permutations(range(3)):
                if all(f[permutation[k]]>=f[permutation[k+1]] for k in range(2)):break
            vertices = [np.zeros(3,int)]
            for axis in permutation:
                point = vertices[-1].copy(); point[axis] = 1; vertices.append(point)
            matrix = np.column_stack((np.ones(4),np.array(vertices)))
            weights = np.linalg.solve(matrix.T,np.r_[1.,f])
            out = sum(weights[i]*sample(v,low) for i,v in enumerate(vertices))
        elif method=='prism':
            triangle = [(0,0),(0,1),(1,1)] if f[2]>f[0] else [(0,0),(1,0),(1,1)]
            weights = np.linalg.solve(np.column_stack((np.ones(3),triangle)).T,[1,f[0],f[2]])
            lower = sum(weights[i]*sample((r,0,b),low) for i,(r,b) in enumerate(triangle))
            upper = sum(weights[i]*sample((r,1,b),low) for i,(r,b) in enumerate(triangle))
            out = lower*(1-f[1])+upper*f[1]
        else:
            axis = 0 if f[0]<f[1] and f[0]<f[2] else 1 if f[1]<f[0] and f[1]<f[2] else 2
            others = [a for a in range(3) if a!=axis]
            vertices = []
            for u,v in ((0,0),(1,0),(0,1),(1,1)):
                point = np.zeros(3);point[others] = [u,v];vertices.append(point)
            vertices.append(np.ones(3))
            basis = lambda v:[1,*v,v[others[0]]*v[others[1]]]
            coefficients = np.linalg.solve(np.array([basis(v) for v in vertices]),np.array([sample(v,low) for v in vertices]))
            out = np.array(basis(f))@coefficients
        result.append(out)
    return np.asarray(result,np.float32)


class FloatLUTTests(unittest.TestCase):
    def setUp(self):
        base = Path(__file__).resolve().parents[1]/'.runtime/temp';base.mkdir(parents=True,exist_ok=True)
        temporary = tempfile.TemporaryDirectory(prefix='float-lut-',dir=base);self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.table = write_cube(self.root/'look.cube')

    def plan(self,value=None,**kwargs):
        return compile_lut(value or effect(),resource_root=self.root,**kwargs)

    def apply(self,a,value=None,tick=0,**kwargs):
        return apply_lut(a,self.plan(value),tick,working_signal=fixture.LINEAR,**kwargs)

    def native(self,a,method,*,scalar=True):
        planar = np.moveaxis(a[...,[1,2,0,3]],2,0).astype('<f4').tobytes()
        result = subprocess.run([ffmpeg_path(),'-nostdin','-v','error',*(['-cpuflags','0'] if scalar else []),'-filter_threads','1',
            '-f','rawvideo','-pixel_format','gbrapf32le','-video_size',f'{a.shape[1]}x{len(a)}','-i','pipe:0',
            '-vf',f'lut3d=file=look.cube:interp={method}','-frames:v','1','-pix_fmt','gbrapf32le','-f','rawvideo','pipe:1'],
            input=planar,capture_output=True,cwd=self.root,timeout=30)
        self.assertEqual(result.returncode,0,result.stderr.decode('utf8','replace'))
        return np.moveaxis(np.frombuffer(result.stdout,'<f4').reshape(4,*a.shape[:2])[[2,0,1,3]],0,-1).copy()

    def test_five_interpolations_match_independent_polynomial_and_barycentric_systems(self):
        rng = np.random.default_rng(71)
        self.table = write_cube(self.root/'look.cube',4,transform=lambda *v:rng.uniform(-.3,1.5,3))
        a = rng.uniform(-.2,1.2,(3,29,4)).astype(np.float32);a[...,3] = rng.uniform(0,1,(3,29))
        a.reshape(-1,4)[:5,:3] = [[.2,.2,.4],[.2,.4,.2],[.4,.2,.2],[0,0,0],[1,1,1]]
        for method in INTERPOLATIONS:
            actual,meta = self.apply(a,effect(interpolation=method))
            expected = scalar_lookup(self.table,a.reshape(-1,4)[:,:3],method).reshape(3,29,3)
            np.testing.assert_allclose(actual[...,:3],expected,rtol=0,atol=1.2e-7)
            np.testing.assert_array_equal(actual[...,3],a[...,3]);self.assertFalse(meta['integer_intermediate'])

    def test_five_interpolations_match_actual_native_Float32_including_axis_ties(self):
        rng = np.random.default_rng(81)
        write_cube(self.root/'look.cube',4,transform=lambda *v:rng.uniform(-.3,1.5,3))
        a = rng.uniform(-.2,1.2,(3,29,4)).astype(np.float32);a[...,3] = rng.uniform(0,1,(3,29))
        a.reshape(-1,4)[:8,:3] = [[.2,.2,.4],[.2,.4,.2],[.4,.2,.2],[0,0,0],[1,1,1],[.5,.5,.5],[1/3,2/3,.5],[.5,.5,.25]]
        for method in INTERPOLATIONS:
            actual,_ = self.apply(a,effect(interpolation=method))
            np.testing.assert_allclose(actual,self.native(a,method),rtol=0,atol=8e-7)

    def test_all_five_default_cpu_native_oracles_on_aligned_width(self):
        rng = np.random.default_rng(82)
        write_cube(self.root/'look.cube',4,transform=lambda *v:rng.uniform(-.3,1.5,3))
        a = rng.uniform(0,1,(3,32,4)).astype(np.float32)
        for method in INTERPOLATIONS:
            actual,_ = self.apply(a,effect(interpolation=method))
            np.testing.assert_allclose(actual,self.native(a,method,scalar=False),rtol=0,atol=8e-7)

    def test_domain_offset_range_and_clamping_are_explicit(self):
        domain = ((-.2,.1,.3),(.8,1.3,2.3))
        table = write_cube(self.root/'look.cube',domain=domain)
        a = fixture.rgba(shape=(2,3));a[...,:3] = [[[-2,0,.3],[0,.7,1.3],[2,2,5]]]*2
        for method in INTERPOLATIONS:
            actual,meta = self.apply(a,effect(interpolation=method))
            expected = scalar_lookup(table,a.reshape(-1,4)[:,:3],method,domain).reshape(2,3,3)
            np.testing.assert_allclose(actual[...,:3],expected,rtol=0,atol=1.2e-7)
            self.assertEqual(meta['domain_min'],list(domain[0]))

    def test_native_pyramid_tie_convention_is_not_silently_argmin(self):
        rng = np.random.default_rng(91)
        table = write_cube(self.root/'look.cube',2,transform=lambda *v:rng.uniform(-.3,1.5,3))
        a = fixture.rgba((.2,.2,.7,1))
        actual,_ = self.apply(a,effect(interpolation='pyramid'))
        expected = scalar_lookup(table,a.reshape(-1,4)[:,:3],'pyramid').reshape(4,8,3)
        np.testing.assert_array_equal(actual[...,:3],expected)
        np.testing.assert_allclose(actual,self.native(a,'pyramid'),rtol=0,atol=8e-7)

    def test_input_alpha_and_hidden_straight_rgb_are_independent(self):
        a = fixture.rgba((.3,.4,.5,0));a[0,1,3] = np.nextafter(np.float32(0),np.float32(1));a[0,2,3] = .5
        actual,_ = self.apply(a)
        np.testing.assert_array_equal(actual[...,3],a[...,3])
        np.testing.assert_array_equal(actual[...,:3],np.broadcast_to(actual[0,3,:3],actual[...,:3].shape))

    def test_zero_strength_is_bit_exact_for_extended_rgb_and_negative_zero(self):
        a = fixture.rgba((-.125,2.5,-0.,1));a[0,0,3] = -0.
        actual,meta = self.apply(a,effect(intensity=0))
        self.assertEqual(actual.tobytes(),a.tobytes());self.assertFalse(np.shares_memory(a,actual));self.assertTrue(meta['intensity_zero_bit_exact'])

    def test_neutral_table_retains_all_65536_gray_levels(self):
        write_cube(self.root/'look.cube',2,transform=lambda r,g,b:(r,g,b))
        a = fixture.rgba(shape=(256,256));a[...,:3] = np.arange(65536,dtype=np.float32).reshape(256,256,1)/65535
        a.flags.writeable = False
        for method in ('trilinear','tetrahedral','pyramid','prism'):
            actual,_ = self.apply(a,effect(interpolation=method))
            np.testing.assert_array_equal(actual,a);self.assertEqual(len(np.unique(actual[...,0])),65536)

    def test_table_output_extended_rgb_is_not_clipped(self):
        write_cube(self.root/'look.cube',2,transform=lambda *v:(-.25,1.75,1.00001))
        actual,_ = self.apply(fixture.rgba())
        np.testing.assert_array_equal(actual[...,:3],np.broadcast_to(np.float32([-.25,1.75,1.00001]),actual[...,:3].shape))

    def test_encoded_table_signal_converts_back_before_linear_intensity_mix(self):
        write_cube(self.root/'look.cube',2,transform=lambda *v:(.5,.75,.25))
        a = fixture.rgba((.05,.15,.25,.5))
        actual,meta = self.apply(a,effect(input_signal=SRGB,output_signal=SRGB,intensity=.4))
        encoded = np.array([.5,.75,.25],np.float64)
        linear = np.where(encoded<=.04045,encoded/12.92,((encoded+.055)/1.055)**2.4).astype(np.float32)
        expected = (a[...,:3].astype(np.float64)*.6+linear.astype(np.float64)*.4).astype(np.float32)
        np.testing.assert_array_equal(actual[...,:3],expected);self.assertEqual(meta['mix_domain'],'linear-working-straight-RGB')

    def test_input_signal_is_applied_before_table_lookup(self):
        write_cube(self.root/'look.cube',2,transform=lambda r,g,b:(r,g,b))
        a = fixture.rgba((.05,.15,.25,1))
        actual,_ = self.apply(a,effect(input_signal=SRGB,output_signal=LINEAR))
        expected = (1.055*a[...,:3].astype(np.float64)**(1/2.4)-.055).astype(np.float32)
        np.testing.assert_array_equal(actual[...,:3],expected)

    def test_explicit_wide_gamut_input_and_output_roundtrip(self):
        write_cube(self.root/'look.cube',2,transform=lambda r,g,b:(r,g,b))
        a = fixture.rgba((.3,.4,.5,.75))
        wide = {'primaries':'bt2020','transfer':'linear'}
        actual,_ = self.apply(a,effect(input_signal=wide,output_signal=wide))
        np.testing.assert_allclose(actual,a,rtol=0,atol=6e-8)

    def test_all_six_intensity_interpolations_match_author_math(self):
        from test_spatial_automation import declared_bezier_reference
        write_cube(self.root/'look.cube',2,transform=lambda *v:(1,0,0))
        a = fixture.rgba((0,0,1,.5))
        for mode,value in [('linear',.25),('hold',0),('ease_in',.0625),('ease_out',.4375),('ease_in_out',.125),('bezier',declared_bezier_reference(.25))]:
            e = effect();e['keyframes'] = [track(mode=mode,controls=[1/3,0,2/3,1] if mode=='bezier' else None)]
            actual,meta = self.apply(a,e,tick=25)
            np.testing.assert_array_equal(actual,fixture.rgba((value,0,1-value,.5)))
            self.assertAlmostEqual(meta['intensity'],value,places=14)

    def test_author_fractional_ticks_boundaries_and_bezier_overshoot(self):
        write_cube(self.root/'look.cube',2,transform=lambda *v:(1,0,0))
        e = effect();e['keyframes'] = [track()]
        _,meta = self.apply(fixture.rgba(),e,tick=Fraction(25,2));self.assertEqual(meta['intensity'],.125)
        for tick,expected in ((-20,0),(0,0),(100,1),(150,1)):
            _,meta = self.apply(fixture.rgba(),e,tick=tick);self.assertEqual(meta['intensity'],expected)
        for controls,expected in (([12,12],1),([-12,-12],0)):
            e['keyframes'] = [track(mode='bezier',controls=controls)]
            _,meta = self.apply(fixture.rgba(),e,tick=50);self.assertEqual(meta['intensity'],expected)

    def test_intensity_aliases_and_parameter_local_tracks_are_equivalent(self):
        for kind,name in (('lut','effect.intensity'),('cube','parameters.intensity'),('look','look.intensity'),('lut3d','intensity')):
            e = effect();e['type'] = kind;e['parameters']['keyframes'] = [track(name=name)]
            _,meta = self.apply(fixture.rgba(),e,tick=40);self.assertEqual(meta['intensity'],.4)

    def test_compiled_table_and_tracks_are_immutable(self):
        e = effect();e['keyframes'] = [track()];plan = self.plan(e)
        before = plan.cube.payload;e['keyframes'][0]['keyframes'][0]['value'] = 1
        with self.assertRaises(ValueError):plan.cube.table.setflags(write=True)
        with self.assertRaises(ValueError):plan.cube.table[0,0,0,0] = 2
        _,meta = apply_lut(fixture.rgba(),plan,0,working_signal=fixture.LINEAR)
        self.assertEqual(meta['intensity'],0);self.assertEqual(plan.cube.payload,before)

    def test_parser_bom_title_comments_red_fastest_and_domain(self):
        path = self.root/'look.cube';path.write_bytes(b'\xef\xbb\xbf'+path.read_bytes())
        plan = self.plan();np.testing.assert_array_equal(plan.cube.table,self.table)
        self.assertEqual(plan.cube.dependency.sha256,'sha256:'+hashlib.sha256(path.read_bytes()).hexdigest())

    def test_parser_rejects_incomplete_extra_nonfinite_and_unknown_data(self):
        cases = ['LUT_3D_SIZE 2\n0 0 0\n','LUT_3D_SIZE 2\n'+'0 0 0\n'*9,
            'LUT_3D_SIZE 2\n'+'nan 0 0\n'*8,'LUT_3D_SIZE 2\n'+'1e100 0 0\n'*8,
            'LUT_1D_SIZE 2\n0 0 0\n','LUT_3D_SIZE 2\nDOMAIN_MIN 1 0 0\n'+'0 0 0\n'*8,
            'LUT_3D_SIZE 2\nLUT_3D_SIZE 2\n'+'0 0 0\n'*8,
            'LUT_3D_SIZE 2\n0 0 0\nDOMAIN_MIN 0 0 0\n'+'0 0 0\n'*7]
        for text in cases:
            (self.root/'look.cube').write_text(text,encoding='utf8')
            with self.assertRaises(AppError):self.plan()

    def test_parser_line_encoding_dimensions_and_format_budgets_reject(self):
        for raw in (b'\xff',b'#'+b'x'*4096,b'LUT_3D_SIZE 1\n',b'LUT_3D_SIZE 257\n'):
            (self.root/'look.cube').write_bytes(raw)
            with self.assertRaises(AppError):self.plan()
        (self.root/'look.dat').write_text('unsupported')
        with self.assertRaises(AppError):self.plan(effect(path='look.dat'))

    def test_parser_budget_rejects_before_table_allocation(self):
        (self.root/'look.cube').write_text('LUT_3D_SIZE 256\n')
        with patch('ai_ad_editor.float_lut.bytearray',side_effect=AssertionError('no table allocation'),create=True):
            with self.assertRaises(AppError) as caught:self.plan(max_working_bytes=1024)
        self.assertEqual(caught.exception.code,'FLOAT_LUT_BUDGET')

    def test_missing_or_ambiguous_signals_never_guess(self):
        for signals in ({'input_signal':None},{'output_signal':None},{'input_signal':{'transfer':'srgb'}},
            {'input_signal':{'primaries':'bt709','transfer':'pq'}},{'output_signal':{**LINEAR,'nits':100}}):
            with self.assertRaises(AppError):self.plan(effect(**signals))

    def test_remote_outside_missing_ambiguous_and_bad_paths_reject(self):
        for path in ('https://example.org/a.cube','file://look.cube','//server/a.cube','../outside.cube','missing.cube',True):
            with self.assertRaises(AppError):self.plan(effect(path=path))
        for e in (effect(file='other.cube'),effect(lut_id='also-path'),effect(unused=1)):
            with self.assertRaises(AppError):self.plan(e)

    def test_registered_resource_sha_and_registry_are_bound(self):
        record = register_lut(self.root,prepare_lut_registration(self.root,self.root/'look.cube',lut_id='look'))
        e = effect(lut_id='look');e['parameters'].pop('path');plan = self.plan(e)
        verify_dependencies(plan.dependencies)
        (self.root/record['uri']).write_bytes(b'changed')
        with self.assertRaises(AppError):verify_dependencies(plan.dependencies)
        with self.assertRaises(AppError):self.plan(e)

    def test_path_resource_change_rejected_but_frozen_plan_retains_original_bytes(self):
        plan = self.plan();a = fixture.rgba((.2,.3,.4,.5))
        before = apply_lut(a,plan,0,working_signal=fixture.LINEAR)[0]
        write_cube(self.root/'look.cube',transform=lambda *v:(1,0,0))
        np.testing.assert_array_equal(apply_lut(a,plan,0,working_signal=fixture.LINEAR)[0],before)
        with self.assertRaises(AppError):verify_dependencies(plan.dependencies)
        self.assertFalse(np.array_equal(self.apply(a)[0],before))

    def test_invalid_tracks_values_duplicates_and_controls_reject(self):
        bad = [track(name='path'),track(left=True),track(left='0'),track(right=1.1),track(mode='unknown'),
            track(mode='bezier',controls=[2,0,0,1]),track(mode='bezier',controls=[0,math.inf])]
        for t in bad:
            e = effect();e['keyframes'] = [t]
            with self.assertRaises(AppError):self.plan(e)
        e = effect();e['keyframes'] = [track(),track()]
        with self.assertRaises(AppError):self.plan(e)
        e['keyframes'] = [track(stop=0)]
        with self.assertRaises(AppError):self.plan(e)
        e['keyframes'] = [track()];e['parameters']['keyframes'] = [track()]
        with self.assertRaises(AppError):self.plan(e)

    def test_invalid_static_options_do_not_fall_back(self):
        for options in ({'intensity':True},{'intensity':-1},{'intensity':math.nan},{'interpolation':'unknown'}):
            with self.assertRaises(AppError):self.plan(effect(**options))
        with self.assertRaises(AppError):compile_lut(effect(),resource_root=None)

    def test_tile_partition_is_bit_identical(self):
        a = np.random.default_rng(13).uniform(0,1,(11,37,4)).astype(np.float32)
        for method in INTERPOLATIONS:
            expected = self.apply(a,effect(interpolation=method,intensity=.41),tile_pixels=407)[0]
            for tile in (1,7,23):
                actual = self.apply(a,effect(interpolation=method,intensity=.41),tile_pixels=tile)[0]
                self.assertEqual(actual.tobytes(),expected.tobytes())

    def test_late_invalid_input_never_mutates_source(self):
        for channel,value in ((0,math.nan),(2,math.inf),(3,-.1),(3,1.1)):
            a = fixture.rgba();a[-1,-1,channel] = value;before = a.tobytes()
            with self.assertRaises(AppError):self.apply(a,tile_pixels=3)
            self.assertEqual(a.tobytes(),before)

    def test_surface_and_argument_contracts_reject(self):
        for a in (np.zeros((4,8,4),np.float64),np.zeros((0,8,4),np.float32),fixture.rgba()[:,::-1]):
            with self.assertRaises(AppError):self.apply(a)
        for kwargs in ({'tile_pixels':True},{'tile_pixels':0},{'cancel':False},{'max_working_bytes':True}):
            with self.assertRaises(AppError):self.apply(fixture.rgba(),**kwargs)
        for tick in (True,math.nan,math.inf):
            with self.assertRaises(AppError):self.apply(fixture.rgba(),tick=tick)

    def test_apply_budget_rejects_before_output_allocation(self):
        plan = self.plan()
        with patch('ai_ad_editor.float_lut.np.empty_like',side_effect=AssertionError('no output allocation')):
            with self.assertRaises(AppError) as caught:apply_lut(fixture.rgba(),plan,0,working_signal=fixture.LINEAR,max_working_bytes=1)
        self.assertEqual(caught.exception.code,'FLOAT_LUT_BUDGET')

    def test_cancellation_mid_tile_preserves_source_and_parser_can_cancel(self):
        a = fixture.rgba(shape=(32,64));before = a.tobytes();calls = 0
        def cancel():
            nonlocal calls
            calls += 1
            if calls==15:raise AppError('TEST_CANCELLED','stop',exit_code=2)
        with self.assertRaises(AppError) as caught:self.apply(a,tile_pixels=7,cancel=cancel)
        self.assertEqual(caught.exception.code,'TEST_CANCELLED');self.assertEqual(a.tobytes(),before)
        with self.assertRaises(AppError):self.plan(cancel=lambda:(_ for _ in ()).throw(AppError('CANCEL','stop',exit_code=2)))

    def test_exposure_lut_order_is_retained_and_shared_table_loaded_once(self):
        write_cube(self.root/'look.cube',2,transform=lambda r,g,b:(r*r,g*g,b*b))
        compiler = EffectCompiler(resource_root=self.root,working_signal=fixture.LINEAR)
        lut = effect(intensity=.7);exposure = {'type':'exposure','parameters':{'amount':1}}
        a = fixture.rgba((.7,.8,.9,.5))
        first = compiler.apply(a,compiler.compile([exposure,lut]),0)[0]
        second,meta = compiler.apply(a,compiler.compile([lut,exposure]),0)
        np.testing.assert_allclose(first[0,0,:3],[1.12,1.18,1.24],rtol=0,atol=1.2e-7)
        np.testing.assert_allclose(second[0,0,:3],[1.4,1.6,1.8],rtol=0,atol=1.2e-7)
        self.assertEqual([r['type'] for r in meta['ordered_effects']],['lut3d','exposure']);self.assertEqual(len(compiler.cubes),1)

    def test_multiple_lut_order_disabled_items_and_unknown_effect_rejection(self):
        write_cube(self.root/'red.cube',2,transform=lambda *v:(1,0,0))
        write_cube(self.root/'blue.cube',2,transform=lambda *v:(0,0,1))
        compiler = EffectCompiler(resource_root=self.root,working_signal=fixture.LINEAR)
        disabled = {'type':'not-implemented','enabled':False}
        actual,meta = compiler.apply(fixture.rgba(),compiler.compile([effect(path='red.cube'),disabled,effect(path='blue.cube',intensity=.5)]),40)
        np.testing.assert_array_equal(actual,fixture.rgba((.5,0,.5,1)));self.assertEqual(len(meta['ordered_effects']),2)
        with self.assertRaises(AppError):compiler.compile([{'type':'not-implemented'}])

    def test_author_window_uses_original_intensity_clock_and_preserves_ir(self):
        write_cube(self.root/'look.cube',2,transform=lambda *v:(1,0,0))
        p,s = fixture.image_project(fixture.rgba((0,0,1,1)),duration=30)
        c = p['sequences'][0]['tracks'][0]['clips'][0]
        e = effect();e['keyframes'] = [track()]
        c.update(duration_tick=30,presentation_window={'version':1,'authored_start_tick':0,'authored_duration_tick':100,'offset_tick':40},effects=[e])
        before = copy.deepcopy(p)
        actual,meta = FloatTimeline(p,'main',s,working_signal=fixture.LINEAR,resource_root=self.root).render_frame(0)
        np.testing.assert_array_equal(actual,fixture.rgba((.4,0,.6,1)));self.assertEqual(p,before)
        self.assertEqual(meta['layers'][0]['effects']['ordered_effects'][0]['intensity'],.4)

    def test_nested_reverse_has_distinct_child_and_parent_author_intensity(self):
        write_cube(self.root/'look.cube',2,transform=lambda *v:(1,0,0))
        write_cube(self.root/'blue.cube',2,transform=lambda *v:(0,0,1))
        p,s = fixture.image_project(fixture.rgba((0,1,0,1)))
        child = copy.deepcopy(p['sequences'][0]);child['id'] = 'child';child['duration_tick'] = 200
        red = effect();red['keyframes'] = [track(stop=200)]
        child['tracks'][0]['clips'][0].update(duration_tick=200,source_out_tick=200,effects=[red])
        c = p['sequences'][0]['tracks'][0]['clips'][0];c.pop('asset_id')
        blue = effect(path='blue.cube');blue['keyframes'] = [track()]
        c.update(sequence_id='child',source_out_tick=200,speed=2,reverse=True,effects=[blue]);p['sequences'].append(child)
        actual,meta = FloatTimeline(p,'main',s,working_signal=fixture.LINEAR,resource_root=self.root).render_frame(2)
        np.testing.assert_allclose(actual,fixture.rgba((.64,.16,.2,1)),rtol=0,atol=6e-8)
        self.assertAlmostEqual(meta['layers'][0]['effects']['ordered_effects'][0]['intensity'],.8,places=14)
        self.assertEqual(meta['layers'][1]['effects']['ordered_effects'][0]['intensity'],.2)

    def test_timeline_source_verification_includes_lut_dependencies(self):
        p,s = fixture.image_project();p['sequences'][0]['tracks'][0]['clips'][0]['effects'] = [effect()]
        host = FloatTimeline(p,'main',s,working_signal=fixture.LINEAR,resource_root=self.root);host.verify_sources()
        (self.root/'look.cube').write_text('changed')
        with self.assertRaises(AppError):host.verify_sources()

    def test_real_render_preview_png16_pcm_and_changed_lut_cache(self):
        case = preview_fixture.FloatPreviewTests('runTest');case.setUp()
        try:
            case.s['duration_tick'] = 18000
            original = fixture.rgba((.2,.4,.6,.5),shape=(16,32));original[...,0] = np.arange(32,dtype=np.float32)[None,:]/31
            pixels = case.visual(np.stack([original]*2));audio = case.audio()
            path = case.root/'look.cube';write_cube(path,2,transform=lambda *v:(1,0,0))
            e = effect(intensity=0);e['keyframes'] = [track(left=.25,right=.75,stop=9000)]
            case.s['tracks'][0]['clips'][0]['effects'] = [e]
            before = copy.deepcopy(case.p);result = case.execute(end=2);actual = case.reference(result)
            source = np.rint(pixels.astype(np.float64)*65535).astype(np.float32)/65535
            expected = source.copy()
            for i,strength in enumerate((.25,.75)):
                graded = (source[i,...,:3].astype(np.float64)*(1-strength)+np.array([1,0,0])*strength).astype(np.float32)
                expected[i,...,:3] = (graded.astype(np.float64)*source[i,...,3:4].astype(np.float64)).astype(np.float32)
            expected[...,3] = 1
            np.testing.assert_allclose(actual,expected,rtol=0,atol=6e-8)
            for section in ('settings','sequences','assets'):self.assertEqual(case.p[section],before[section])
            self.assertEqual(case.pcm(result),audio[:9600].tobytes())
            cached = case.execute(end=2);self.assertTrue(cached['cache_hit'])
            png = case.png(case.execute(mode='frame'));np.testing.assert_allclose(png,np.rint(expected[0].astype(np.float64)*65535).astype(np.uint16),rtol=0,atol=1)
            from ai_ad_editor.render import render_project
            from ai_ad_editor.project import project_write_lock
            with project_write_lock(case.root):formal = render_project(case.root,case.p,case.s,case.root/'renders/lut.mkv')
            payload = np.moveaxis(np.rint(expected[...,[1,2,0,3]].astype(np.float64)*65535).astype('<u2'),3,1).tobytes()
            manifest = json.loads(Path(formal['path']).with_suffix('.mkv.manifest.json').read_bytes())
            self.assertEqual(manifest['delivery']['pixel_pipeline']['transport']['video_input_sha256'],'sha256:'+hashlib.sha256(payload).hexdigest())
            delivered_pcm = case.native([ffmpeg_path(),'-nostdin','-v','error','-i',formal['path'],'-map','0:a:0','-vn','-f','f32le','-c:a','pcm_f32le','pipe:1'])
            self.assertEqual(delivered_pcm,audio[:9600].tobytes())
            old_key = result['cache_key'];write_cube(path,2,transform=lambda *v:(0,0,1))
            changed = case.execute(end=2);self.assertNotEqual(changed['cache_key'],old_key);self.assertFalse(changed['cache_hit'])
            self.assertFalse(np.array_equal(case.reference(changed),actual));case.assert_clean()
        finally:case.doCleanups()
