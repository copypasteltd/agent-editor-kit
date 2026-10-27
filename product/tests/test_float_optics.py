"""Optical contracts: closed forms, integer channel maps, real GPU and delivery."""
import copy
from dataclasses import replace
from fractions import Fraction
import json
import math
from pathlib import Path
import tempfile
import unittest

import numpy as np

from ai_ad_editor.errors import AppError
from ai_ad_editor.float_color_signal import ColorSignal
from ai_ad_editor.float_effect_chain import EffectCompiler
from ai_ad_editor.float_optics import (SPECS,compile_optics,state_at,apply_optics,validate_optics,validate_state)
from ai_ad_editor.float_gpu import FloatGPUSession
from ai_ad_editor.project import load_project,save_project,project_write_lock
from ai_ad_editor.validator import validate_project
import test_procedural_particles as fixtures

LINEAR=ColorSignal('bt709','linear')
RECEIPTS=[]
def effect(kind='light_leak',**p):return dict(type=kind,parameters=p)
def keys(prop,a,b,mode='linear',end=100):
    first=dict(at_tick=0,value=a,interpolation=mode)
    if mode=='bezier':first['control_points']=[1/3,0,2/3,1]
    return dict(property=prop,keyframes=[first,dict(at_tick=end,value=b,interpolation='linear')])
def image(h=9,w=9):
    y,x=np.mgrid[:h,:w];a=np.ones((h,w,4),np.float32)
    a[:,:,0]=x/max(1,w-1);a[:,:,1]=y/max(1,h-1);a[:,:,2]=(x+y)/max(1,w+h-2)
    return a
def apply(a,e,at=0,**kw):return apply_optics(a,compile_optics(e),at,working_signal=LINEAR,**kw)

class OpticalNumericTests(unittest.TestCase):
    def test_leak_center_and_axis_match_closed_gaussian_values(self):
        a=np.zeros((9,9,4),np.float32);a[:,:,3]=1
        actual,_=apply(a,effect(x=.5,y=.5,radius=1/9,aspect=2,red=1,green=.5,blue=0,brightness=2))
        np.testing.assert_array_equal(actual[4,4],[2,1,0,1])
        self.assertAlmostEqual(float(actual[4,5,0]),2*math.exp(-.5),places=6)
        self.assertAlmostEqual(float(actual[5,4,0]),2*math.exp(-.125),places=6)
    def test_leak_rotation_swaps_axes_and_is_resolution_isotropic(self):
        a=np.zeros((9,9,4),np.float32);a[:,:,3]=1
        x,_=apply(a,effect(x=.5,y=.5,radius=.2,aspect=3,angle=0))
        y,_=apply(a,effect(x=.5,y=.5,radius=.2,aspect=3,angle=90))
        np.testing.assert_array_equal(x.transpose(1,0,2),y)
    def test_flare_without_secondary_components_is_radial_gaussian(self):
        a=np.zeros((9,9,4),np.float32);a[:,:,3]=1
        v,_=apply(a,effect('lens_flare',x=.5,y=.5,radius=1/9,ghosts=0,halo=0,streak=0,red=1,green=1,blue=1))
        self.assertEqual(v[4,4,0],1)
        self.assertAlmostEqual(float(v[3,3,0]),math.exp(-1),places=7)
        np.testing.assert_array_equal(v,v[::-1,::-1])
    def test_ghost_count_adds_nonnegative_light_without_changing_coverage(self):
        a=image(27,35);a[:,:,:3]=0
        e=effect('lens_flare',radius=.12,x=.14,y=.2,ghosts=0)
        before,_=apply(a,e);e['parameters']['ghosts']=12;after,_=apply(a,e)
        self.assertTrue(np.all(after>=before));self.assertGreater(float(np.sum(after-before)),0)
        np.testing.assert_array_equal(after[:,:,3],a[:,:,3])
    def test_isotropic_leak_and_core_only_flare_are_equivalent(self):
        a=image(13,21)
        p=dict(x=.38,y=.7,radius=.21,brightness=.4,red=.8,green=.4,blue=.7,intensity=.63)
        leak,_=apply(a,effect(**p,aspect=1))
        flare,_=apply(a,effect('lens_flare',**p,ghosts=0,halo=0,streak=0))
        np.testing.assert_array_equal(leak,flare)
    def test_chromatic_integer_maps_match_exact_independent_pixel_indices(self):
        a=image();v,_=apply(a,effect('chromatic_aberration',red_shift=4.5,blue_shift=-4.5,falloff=1))
        indices=np.clip(2*np.arange(9)-4,0,8)
        np.testing.assert_array_equal(v[:,:,0],a[indices[:,None],indices[None,:],0])
        np.testing.assert_array_equal(v[:,:,1],a[:,:,1])
        np.testing.assert_array_equal(v[:,:,2],np.full((9,9),a[4,4,2],np.float32))
    def test_hidden_RGB_does_not_bleed_into_visible_channel(self):
        a=np.array([[[.2,.3,.4,1],[1000,-1000,999,0],[.8,.2,.1,1]]],np.float32)
        v,_=apply(a,effect('chromatic_aberration',x=0,y=.5,red_shift=.5,blue_shift=0,falloff=0))
        self.assertEqual(v[0,0,0],a[0,0,0]);np.testing.assert_array_equal(v[0,1],[0,0,0,0])
    def test_transparent_and_clamped_edges_and_single_pixel(self):
        a=np.array([[[.2,.3,.4,1]]],np.float32)
        e=effect('chromatic_aberration',x=-1,y=-1,red_shift=64,blue_shift=64,falloff=4)
        clamped,_=apply(a,e);np.testing.assert_array_equal(clamped,a)
        e['parameters']['edge']='transparent';transparent,_=apply(a,e)
        expected=a.copy();expected[:,:,[0,2]]=0
        np.testing.assert_array_equal(transparent,expected)
    def test_coverage_bits_include_16bit_ramp_subnormals_and_signed_zero(self):
        a=np.ones((256,256,4),np.float32);a[:,:,:3]=[.1,.2,.3]
        a[:,:,3]=np.arange(65536,dtype=np.float32).reshape(256,256)/65535
        bits=np.array([0,0x80000000,1,2,0x7fffff,0x800000,0x800001,0x3f800000],np.uint32)
        a.reshape(-1,4)[:8,3]=bits.view(np.float32)
        for kind in SPECS:
            v,_=apply(a,effect(kind))
            np.testing.assert_array_equal(v[:,:,3].view(np.uint32),a[:,:,3].view(np.uint32))
            self.assertTrue(np.all(v[:,:,:3][a[:,:,3]==0]==0))
    def test_zero_intensity_and_zero_work_are_bit_exact(self):
        a=image();a[0,0]=[10,-4,30,-0.]
        for kind in SPECS:
            v,m=apply(a,effect(kind,intensity=0));np.testing.assert_array_equal(v.view(np.uint32),a.view(np.uint32));self.assertFalse(m['active'])
        for e in [effect(brightness=0),effect('lens_flare',red=0,green=0,blue=0),effect('chromatic_aberration',red_shift=0,blue_shift=0)]:
            np.testing.assert_array_equal(apply(a,e)[0].view(np.uint32),a.view(np.uint32))
    def test_all_six_easings_keep_original_fractional_author_time(self):
        expected={'hold':0,'linear':.25,'ease_in':.0625,'ease_out':.4375,'ease_in_out':.125,'bezier':.15625}
        for mode,value in expected.items():
            e=effect();e['keyframes']=[keys('x',0,1,mode)]
            p=compile_optics(e);self.assertAlmostEqual(state_at(p,Fraction(25))['x'],value,places=7)
            self.assertEqual(state_at(p,100)['x'],1)
    def test_seek_order_tile_shape_and_input_bytes_do_not_change_result(self):
        a=image(13,17);before=a.tobytes();e=effect('lens_flare',brightness=.2)
        e['keyframes']=[keys('x',-.2,1.2),keys('angle',-70,45)]
        frames={at:apply(a,e,at,tile_pixels=1)[0] for at in [0,37,90,25]}
        for at in [90,0,25,37]:np.testing.assert_array_equal(apply(a,e,at,tile_pixels=262144)[0],frames[at])
        self.assertEqual(a.tobytes(),before)
    def test_invalid_declarations_and_mutated_immutable_plans_fail(self):
        for e in [effect(missing=1),effect(radius=0),effect(x=True),effect('lens_flare',ghosts=True),
                  effect('lens_flare',ghosts=13),effect('light_leak',ghosts=2),effect('chromatic_aberration',edge='wrap')]:
            with self.assertRaises(AppError):compile_optics(e)
        p=compile_optics(effect())
        for q in [replace(p,ghosts=1),replace(p,values=(('x',.1),('x',.2))),replace(p,values=(('bad',),)),replace(p,tracks_json='{}')]:
            with self.assertRaises(AppError):state_at(q,0)
        with self.assertRaises(AppError):validate_state([],{},0,'clamp')
        e=effect();e['keyframes']=[keys('x',0,1,end=101)];self.assertTrue(validate_optics(e,duration_tick=100))
    def test_bad_surface_signal_budget_and_cancellation_do_not_mutate_input(self):
        a=image();before=a.tobytes()
        for value in [a.astype(np.float64),a[:,::-1],np.zeros((0,9,4),np.float32)]:
            with self.assertRaises(AppError):apply(value,effect())
        bad=a.copy();bad[0,0,3]=1.01
        with self.assertRaises(AppError):apply(bad,effect())
        with self.assertRaises(AppError):apply(a,effect(),max_working_bytes=1)
        with self.assertRaises(AppError):apply_optics(a,compile_optics(effect()),0,working_signal=ColorSignal('bt709','srgb'))
        with self.assertRaises(AppError):apply(a,effect(),cancel=lambda:True)
        self.assertEqual(a.tobytes(),before)
    def test_ordered_chain_and_linear_intensity_add_only_once(self):
        a=image(11,13);compiler=EffectCompiler(resource_root=None,working_signal=LINEAR)
        e=effect(brightness=.4);one,_=compiler.apply(a,compiler.compile([e]),0)
        two,m=compiler.apply(a,compiler.compile([e,e]),0)
        np.testing.assert_allclose(two[:,:,:3]-a[:,:,:3],2*(one[:,:,:3]-a[:,:,:3]),atol=2e-7,rtol=0)
        self.assertEqual(len(m['ordered_effects']),2)
        half,_=apply(a,effect(brightness=.4,intensity=.5))
        np.testing.assert_allclose(half[:,:,:3]-a[:,:,:3],.5*(one[:,:,:3]-a[:,:,:3]),atol=1e-7,rtol=0)
    def test_catalog_aliases_are_defensive_and_legacy_execution_rejects(self):
        from ai_ad_editor.effects import get_effect,effect_catalog
        from ai_ad_editor.render import _effect_filters
        self.assertEqual(effect_catalog()['count'],51)
        for alias,canonical in [('lensflare','lens_flare'),('lightleak','light_leak'),('rgb_split','chromatic_aberration')]:
            item=get_effect(alias);self.assertEqual(item['id'],canonical);item['parameters'].clear();self.assertTrue(get_effect(alias)['parameters'])
            with self.assertRaises(AppError) as caught:_effect_filters([effect(alias)],[],'optics')
            self.assertEqual(caught.exception.code,'FLOAT_OPTICS_NATIVE_PIPELINE_REQUIRED')

class OpticalGPUTests(unittest.TestCase):
    def test_three_kinds_fractional_edges_extended_RGB_and_coverage_match_CPU(self):
        rng=np.random.default_rng(381);a=rng.uniform(-.2,1.4,(19,27,4)).astype(np.float32)
        a[:,:,3]=rng.uniform(0,1,(19,27));a[0,0]=[300,-80,90,-0.]
        a[0,1,3]=np.array([1],np.uint32).view(np.float32)[0]
        errors=[]
        with tempfile.TemporaryDirectory() as folder:
            with FloatGPUSession(folder,{'projection_acceleration':{'mode':'require','device':'0.0'}},max_pixels=19*27) as gpu:
                for e in [effect('lens_flare',ghosts=12,x=.9,y=-.2,angle=37,brightness=.5),
                          effect('light_leak',radius=.2,aspect=3,angle=-43),
                          effect('chromatic_aberration',red_shift=5.25,blue_shift=-4.75,falloff=1.7),
                          effect('chromatic_aberration',red_shift=64,blue_shift=-64,edge='transparent',falloff=4)]:
                    ref,_=apply(a,e);actual,m=apply(a,e,gpu=gpu)
                    np.testing.assert_allclose(actual,ref,rtol=3e-7,atol=3e-6)
                    np.testing.assert_array_equal(actual[:,:,3].view(np.uint32),a[:,:,3].view(np.uint32))
                    self.assertTrue(m['GPU']);errors.append(float(np.max(np.abs(actual-ref))))
            self.assertTrue(gpu.evidence['worker_closed']);self.assertTrue(gpu.evidence['control']['threads_closed'])
            RECEIPTS.append(dict(group='optics-GPU',max_errors=errors,GPU=gpu.evidence))
    def test_noop_skips_dispatch_invalid_state_is_atomic_and_next_dispatch_works(self):
        with tempfile.TemporaryDirectory() as folder:
            with FloatGPUSession(folder,{'projection_acceleration':{'mode':'require','device':'0.0'}},max_pixels=81) as gpu:
                a=image();before=copy.deepcopy(gpu.evidence['operations'])
                for kind in SPECS:np.testing.assert_array_equal(apply(a,effect(kind,intensity=0),gpu=gpu)[0],a)
                self.assertEqual(gpu.evidence['operations'],before)
                with self.assertRaises(AppError):gpu.optics(a,'bad',{},0,'clamp')
                self.assertEqual(gpu.evidence['operations'],before)
                compiler=EffectCompiler(resource_root=None,working_signal=LINEAR,gpu=gpu)
                value,m=compiler.apply(a,compiler.compile([effect(brightness=.1)]),0)
                self.assertTrue(m['ordered_effects'][0]['GPU']);self.assertEqual(gpu.evidence['operations']['optics'],1)
            RECEIPTS.append(dict(group='optics-noop',GPU=gpu.evidence))
    def test_optical_dispatch_cancellation_closes_owned_worker_and_control(self):
        state={'armed':False,'polls':0}
        def cancel():
            if state['armed']:
                state['polls']+=1
                if state['polls']>=3:raise AppError('CANCELLED','owned optical test cancellation',exit_code=6)
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaises(AppError) as caught:
                with FloatGPUSession(folder,{'projection_acceleration':{'mode':'require','device':'0.0'}},max_pixels=81,cancel=cancel) as gpu:
                    state['armed']=True
                    p=compile_optics(effect());gpu.optics(image(),p.effect_type,state_at(p,0),p.ghosts,p.edge)
            self.assertEqual(caught.exception.code,'CANCELLED');self.assertTrue(gpu.evidence['worker_closed'])
            self.assertTrue(gpu.evidence['control']['threads_closed']);self.assertTrue(gpu.evidence['control']['streams_closed'])
            RECEIPTS.append(dict(group='optics-cancel',polls=state['polls'],GPU=gpu.evidence))

class OpticalIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.f=fixtures.ParticleIntegrationTests('runTest');self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.f.c['effects']=[effect('lens_flare',brightness=.08,ghosts=4),
            effect('light_leak',brightness=.06,radius=.3),effect('chromatic_aberration',red_shift=1,blue_shift=-1)]
        self.f.c['effects'][0]['keyframes']=[keys('x',.1,.85,end=180000)]
        self.f.p['settings']['pixel_pipeline']['range_policy']='clip'
        save_project(self.f.root,self.f.p)
    def collect(self):RECEIPTS.extend(copy.deepcopy(fixtures.RECEIPTS));fixtures.RECEIPTS.clear()
    def test_real_CPU_GPU_encoding_and_complete_PCM(self):
        # Both backends decode the same authored pixels. Particle rasterization
        # is independently covered below; its tiny coverage errors must not be
        # confused with the optical kernels' arithmetic or codec quantization.
        from PIL import Image
        from ai_ad_editor.media import ffmpeg_path
        f=self.f;picture=f.base/'shared-source.png'
        Image.fromarray(np.rint(image(64,96)[:,:,:3]*255).astype(np.uint8)).save(picture)
        f.call('media','ingest','--project',f.root,'--input',picture,'--asset-id','picture',
            '--license-spdx','CC0-1.0','--verification-status','verified',
            '--evidence','Original numeric test chart; explicitly linear RGB values.')
        _,f.p=load_project(f.root);f.s=f.p['sequences'][0];f.c=f.s['tracks'][0]['clips'][0]
        f.c.pop('generator');f.c['asset_id']='picture'
        f.p['settings']['pixel_pipeline']['sources']['picture']={
            'source_signal':vars(LINEAR),'display_geometry':'square-unrotated','demux_origin':'0'}
        a=f.execute('cpu.mkv');f.p['settings']['projection_acceleration']={'mode':'require','device':'0.0'}
        b=f.execute('gpu.mkv')
        x=np.frombuffer(f.video(a),'<u2');y=np.frombuffer(f.video(b),'<u2')
        self.assertEqual(len(x),24*96*64*3)
        code_error=int(np.max(np.abs(x.astype(int)-y.astype(int))))
        self.assertLessEqual(code_error,1)
        audio=[self.f.native([ffmpeg_path(),'-nostdin','-v','error','-i',self.f.root/('renders/'+n+'.mkv'),
            '-map','0:a:0','-vn','-c:a','pcm_f32le','-f','f32le','pipe:1']) for n in ['cpu','gpu']]
        self.assertEqual(audio[0],audio[1]);self.assertEqual(len(audio[0]),768000)
        m=json.loads((self.f.root/'renders/gpu.mkv.manifest.json').read_bytes())
        self.assertEqual(m['delivery']['pixel_pipeline']['projection_acceleration']['operations']['optics'],72)
        self.collect();RECEIPTS.append(dict(group='same-source-CPU-GPU-encoding',frames=24,
            complete_PCM_bytes=len(audio[0]),maximum_10bit_code_error=code_error))
    def test_particle_composition_preserves_original_float_raster_error_budget(self):
        from ai_ad_editor.float_timeline import FloatTimeline
        f=self.f;cpu=FloatTimeline(f.p,f.s['id'],{},working_signal=LINEAR)
        errors=[]
        with FloatGPUSession(f.root,{'projection_acceleration':{'mode':'require','device':'0.0'}},max_pixels=96*64) as gpu:
            accelerated=FloatTimeline(f.p,f.s['id'],{},working_signal=LINEAR,gpu=gpu)
            for i in range(24):
                a=cpu.render_frame(i)[0];b=accelerated.render_frame(i)[0]
                errors.append(float(np.max(np.abs(a-b))))
                self.assertLessEqual(errors[-1],3e-6,(i,errors[-1]))
            self.assertEqual(gpu.evidence['operations']['particles'],24)
            self.assertEqual(gpu.evidence['operations']['optics'],72)
        RECEIPTS.append(dict(group='particle-optics-Float32-composition',frames=24,
            maximum_float_error=max(errors),GPU=copy.deepcopy(gpu.evidence)))
    def test_package_and_local_OTIO_preserve_curves_and_all_encoded_frames(self):
        self.f.test_package_and_otio_restore_editable_source_and_identical_full_encoding()
        for kind in ['package','otio']:
            _,p=load_project(self.f.base/('restored-'+kind))
            c=next(c for t in p['sequences'][0]['tracks'] for c in t['clips'] if c['id']==self.f.c['id'])
            self.assertEqual(c['effects'],self.f.c['effects'])
        self.collect()
    def test_source_clock_survives_clip_split_and_nested_reverse(self):
        from ai_ad_editor.float_timeline import FloatTimeline
        from ai_ad_editor.clip_windows import slice_clip
        f=self.f;original=copy.deepcopy(f.p)
        host=FloatTimeline(f.p,f.s['id'],{},working_signal=LINEAR)
        frames=[host.render_frame(i)[0] for i in range(24)]
        f.s['tracks'][0]['clips']=[slice_clip(f.c,0,75000,clip_id='left'),
            slice_clip(f.c,75000,180000,clip_id='right')]
        split=FloatTimeline(f.p,f.s['id'],{},working_signal=LINEAR)
        for i in range(24):np.testing.assert_array_equal(split.render_frame(i)[0],frames[i])
        child=copy.deepcopy(f.s);child['id']='child'
        f.s['tracks'][0]['clips']=[dict(id='nested',sequence_id='child',timeline_start_tick=0,
            duration_tick=180000,source_in_tick=0,source_out_tick=180000,reverse=True)]
        f.p['sequences'].append(child);nested=FloatTimeline(f.p,f.s['id'],{},working_signal=LINEAR)
        clocks=[]
        for i in range(24):
            # Reverse selects the previous half-open native frame but evaluates
            # continuous effect automation at the original author's left limit.
            tick=math.nextafter(float(180000-i*7500),-math.inf)
            reference=copy.deepcopy(original);e=reference['sequences'][0]['tracks'][0]['clips'][0]['effects'][0]
            sampled=state_at(compile_optics(e),tick);e.pop('keyframes');e['parameters'].update(sampled)
            expected=FloatTimeline(reference,f.s['id'],{},working_signal=LINEAR).render_frame(23-i)[0]
            actual,m=nested.render_frame(i);np.testing.assert_array_equal(actual,expected)
            row=next(r for r in m['layers'] if r['clip'].startswith('child/'))
            self.assertEqual(row['author_animation_tick'],str(tick))
            self.assertEqual(row['native_frame_index'],23-i)
            self.assertAlmostEqual(sampled['x'],.1+.75*tick/180000,places=14)
            clocks.append(dict(frame=i,source_frame=23-i,author_tick=str(tick),x=sampled['x']))
        RECEIPTS.append(dict(group='optical-split-nested-reverse',all_24_split_frames_equal=True,
            all_24_left_limit_reference_frames_equal=True,clocks=clocks))
    def test_preview_cache_changes_with_effect_key_and_GPU_queue_matches_direct(self):
        from ai_ad_editor import preview
        f=self.f;f.p['settings']['projection_acceleration']={'mode':'require','device':'0.0'}
        save_project(f.root,f.p);request=preview.plan(f.p,f.s,start_frame=0,end_frame=3,mode='range',height=64)
        with project_write_lock(f.root):
            a=preview.preview_project(f.root,f.p,f.s,request=request)
            b=preview.preview_project(f.root,f.p,f.s,request=request)
        self.assertTrue(b['cache_hit'])
        f.c['effects'][0]['keyframes'][0]['keyframes'][0]['value']=.3;save_project(f.root,f.p)
        with project_write_lock(f.root):c=preview.preview_project(f.root,f.p,f.s,request=request)
        self.assertNotEqual(a['cache_key'],c['cache_key']);self.assertFalse(c['cache_hit'])
        p=f.base/'job.json';p.write_text(json.dumps(dict(job_id='optical-job',container='mkv',output='renders/queued.mkv')),encoding='utf8')
        f.call('queue','enqueue','--project',f.root,'--input',p);queued=f.call('queue','run','--project',f.root,'--job-id','optical-job')
        self.assertEqual(queued['summary']['succeeded'],1)
        self.assertEqual(f.video(f.execute('direct.mkv')),f.video(f.root/'renders/queued.mkv'))
        self.collect();RECEIPTS.append(dict(group='optical-preview-queue',preview=[a,b,c],queue=queued))
    def test_adjustments_use_selected_root_interval_once_and_validate_author_clock(self):
        from ai_ad_editor.float_timeline import FloatTimeline
        f=self.f;f.c.pop('effects');base=FloatTimeline(f.p,f.s['id'],{},working_signal=LINEAR)
        plain=base.render_frame(12)[0]
        e=effect('light_leak',brightness=.2);e['keyframes']=[keys('intensity',0,1,end=90000)]
        f.p['settings']['adjustments']=[dict(id='optical-interval',start_tick=45000,duration_tick=90000,effects=[e])]
        self.assertTrue(validate_project(f.root,f.p,strict_rights=False)['ok'])
        adjusted=FloatTimeline(f.p,f.s['id'],{},working_signal=LINEAR)
        actual=adjusted.render_frame(12)[0];expected,_=apply(plain,e,45000)
        np.testing.assert_array_equal(actual,expected)
        e['keyframes'][0]['keyframes'][-1]['at_tick']=90001
        self.assertFalse(validate_project(f.root,f.p,strict_rights=False)['ok'])

if __name__=='__main__':unittest.main(verbosity=2)
