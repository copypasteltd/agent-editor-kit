"""Independent emission integrals, birth/live clocks and actual native editing."""
import copy
from fractions import Fraction as F
import hashlib
import json
import math
from pathlib import Path
import tempfile
import unittest

import numpy as np

from ai_ad_editor.errors import AppError
from ai_ad_editor.procedural_particles import ParticleSource,normalize,uniform
from ai_ad_editor.particle_animation import BirthSchedule,EmitterAnimation,PROPERTIES,INTERPOLATIONS
from ai_ad_editor.float_gpu import FloatGPUSession
from ai_ad_editor.float_timeline import FloatTimeline
from ai_ad_editor.project import load_project,save_project
import test_procedural_particles as fixtures
from test_procedural_particles import solid,recipe,minimal,LINEAR

RECEIPTS=[]


def track(key,values,mode='linear'):
    return {'property':key,'keyframes':[{'at_tick':tick,'value':value,'interpolation':mode} for tick,value in values]}


def animated(*tracks,**values):
    return solid(keyframes=list(tracks),**values)


class EmitterNumericTests(unittest.TestCase):
    def test_linear_rate_count_and_inverse_birth_times(self):
        p=ParticleSource(animated(track('rate',[(0,2),(200,6)]),prewarm=False))
        schedule=p.animations[0].schedule
        for at in (F(0),F(1,4),F(1,2),F(1),F(3,2),F(2)):
            expected=2*at+at*at
            self.assertEqual(schedule.phase_at(at),expected)
            births=list(schedule.births(at,20,False))
            self.assertEqual(len(births),math.floor(expected)+1)
            for number,born in births:
                self.assertAlmostEqual(float(born),math.sqrt(1+number)-1,places=13)

    def test_zero_rate_gaps_and_delayed_first_birth(self):
        e=normalize(animated(track('rate',[(0,0),(50,4),(100,0),(150,2)],'hold'),rate=0))['emitters'][0]
        schedule=BirthSchedule(e,100,200)
        expected={F(0):0,F(1,4):0,F(1,2):0,F(3,4):1,F(1):2,F(5,4):2,F(3,2):2,F(7,4):F(5,2)}
        for at,phase in expected.items():self.assertEqual(schedule.phase_at(at),phase)
        self.assertIsNone(schedule.birth_at(-1))
        self.assertEqual(schedule.birth_at(0),F(1,2))
        self.assertEqual(schedule.birth_at(2),F(1))
        self.assertEqual(schedule.birth_at(3),F(2))
        self.assertEqual(list(schedule.births(F(1,4),20,True)),[])
        self.assertEqual(list(schedule.births(F(5,4),20,True)),[(0,F(1,2)),(1,F(3,4)),(2,F(1))])

    def test_integrals_for_all_polynomial_easings(self):
        integrals={'linear':lambda t:t*t/2,'ease_in':lambda t:t**3/3,
            'ease_out':lambda t:t*t-t**3/3,
            'ease_in_out':lambda t:2*t**3/3 if t<=F(1,2) else -t+2*t*t-F(2,3)*t**3+F(1,6)}
        for mode,integral in integrals.items():
            e=normalize(animated(track('rate',[(0,1),(100,5)],mode)))['emitters'][0]
            schedule=BirthSchedule(e,100,200)
            for at in (F(0),F(1,8),F(1,2),F(3,4),F(1)):
                self.assertEqual(schedule.phase_at(at),at+4*integral(at),(mode,at))
            self.assertEqual(schedule.phase_at(F(2)),F(1)+4*integral(F(1))+5)

    def test_bezier_integral_matches_independent_dense_trapezoids(self):
        curve=track('rate',[(0,1),(200,7)],'bezier')
        curve['keyframes'][0]['control_points']=[.12,.75,.8,.25]
        curve['keyframes'][1]['control_points']=[.12,.75,.8,.25]
        p=ParticleSource(animated(curve));animation=p.animations[0];schedule=animation.schedule
        # Integrating the public value sampler at every LUT knot is exact for
        # these piecewise-linear bezier segments (endpoint rounding tolerance).
        for end in (8,16,32):
            total=0.
            for i in range(end):
                a=i*200/32;b=(i+1)*200/32
                # rate is not among visual bases; use the common easing oracle.
                from ai_ad_editor.animation import keyframe_value
                clip={'keyframes':[curve]}
                left=keyframe_value(clip,('rate',),1,a)
                right=keyframe_value(clip,('rate',),1,b)
                total+=(left+right)/2*(b-a)/100
            self.assertAlmostEqual(float(schedule.phase_at(F(end*2,32))),total,places=6)

    def test_constant_curves_keep_old_static_pixels_bit_exact(self):
        config=recipe();old=ParticleSource(config)
        e=config['emitters'][0]
        e['keyframes']=[track(k,[(0,e[k]),(200,e[k])],'hold') for k in PROPERTIES]
        new=ParticleSource(config)
        for frame in (0,7,12,23):np.testing.assert_array_equal(new.frame(frame),old.frame(frame))

    def test_birth_parameters_do_not_drag_or_retime_existing_particles(self):
        p=ParticleSource(animated(track('position',[(0,[.2,.4]),(100,[.8,.4])]),
            track('velocity',[(0,[[.1,.1],[0,0]]),(100,[[.3,.3],[0,0]])]),
            track('lifetime',[(0,[4,4]),(100,[1,1])]),rate=1,prewarm=False))
        scene=p.scene(18)  # t1.5, births0 and1; no particle dies yet.
        self.assertEqual(len(scene),2)
        self.assertAlmostEqual(float(scene[0,0]),(.2+.1*1.5)*96-.5,places=5)
        self.assertAlmostEqual(float(scene[1,0]),(.8+.3*.5)*96-.5,places=5)
        self.assertEqual(len(p.scene(23)),2)

    def test_live_size_opacity_and_linear_light_colors(self):
        p=ParticleSource(animated(track('size',[(0,[.1,.1]),(100,[.2,.2])]),
            track('opacity',[(0,0),(100,1)]),track('colors',[(0,['#ff0000']),(100,['#0000ff'])]),
            track('aspect',[(0,1),(100,2)])))
        row=p.scene(6)[0]
        self.assertAlmostEqual(float(row[2]),.15*64,places=5)
        self.assertAlmostEqual(float(row[3]),.15*64/1.5,places=5)
        np.testing.assert_array_equal(row[6:9],[.5,0,.5]);self.assertEqual(float(row[9]),.5)

    def test_shape_step_and_nullable_color_end_require_hold(self):
        p=ParticleSource(animated(track('shape',[(0,'disc'),(100,'star')],'hold'),
            track('color_end',[(0,None),(100,'#ffffff')],'hold')))
        self.assertEqual(p.scene(11)[0,10],0);self.assertEqual(p.scene(12)[0,10],3)
        self.assertEqual(p.animations[0].value('color_end',99),None)
        self.assertEqual(p.animations[0].value('color_end',100),[1,1,1])

    def test_prewarm_uses_first_curve_values_at_negative_births(self):
        p=ParticleSource(animated(track('rate',[(0,2),(200,6)]),
            track('position',[(0,[.2,.5]),(100,[.8,.5])]),prewarm=True,lifetime=[1,1]))
        s=p.animations[0].schedule
        self.assertEqual(s.birth_at(-1),F(-1,2))
        scene=p.scene(0);self.assertEqual(len(scene),2)
        np.testing.assert_allclose(scene[:,0],[.2*96-.5,.2*96-.5],atol=2e-6)

    def test_random_access_seed_and_rate_boundary_are_order_independent(self):
        config=animated(track('rate',[(0,3),(200,7)],'ease_in_out'),
            track('position',[(0,[.2,.5]),(200,[.8,.5])]),rate=3)
        a,b=ParticleSource(config),ParticleSource(config)
        expected={i:a.frame(i) for i in range(24)}
        for frame in (23,0,12,8,23,6,1,12):np.testing.assert_array_equal(b.frame(frame),expected[frame])
        self.assertEqual(normalize(config),normalize(normalize(config)))
        self.assertTrue(a.animation_metadata)

    def test_key_time_rate_inverse_preserves_exact_birth_branch(self):
        p=ParticleSource(animated(track('rate',[(0,2),(200,6)]),
            track('position',[(0,[.2,.4]),(100,[.8,.4])],'hold'),rate=2))
        self.assertEqual(p.animations[0].schedule.birth_at(3),F(1))
        self.assertEqual(p.animations[0].born(F(1))['position'],[.8,.4])

    def test_animation_budget_uses_rate_and_lifetime_maxima(self):
        config=animated(track('rate',[(0,1),(100,1024)]),track('lifetime',[(0,[1,1]),(100,[120,120])]))
        with self.assertRaises(AppError) as caught:normalize(config)
        self.assertEqual(caught.exception.code,'PARTICLE_BUDGET')
        self.assertEqual(len(ParticleSource(solid(rate=0)).scene(1)),0)

    def test_invalid_tracks_and_discrete_interpolation_rejected(self):
        invalid=[[],[track('unknown',[(0,1)])],[track('seed',[(0,1)])],
            [track('opacity',[(0,0),(0,1)])],[track('opacity',[(-1,0)])],
            [track('opacity',[(201,0)])],[track('opacity',[(0,float('nan'))])],
            [track('opacity',[(0,0)]),track('opacity',[(1,1)])],
            [track('shape',[(0,'disc'),(100,'star')])],
            [track('color_end',[(0,None),(100,'#ffffff')])],
            [track('colors',[(0,['#ffffff']),(100,['#ff0000','#0000ff'])])],
            [track('velocity',[(0,[[1,-1],[0,1]])])],
            [track('rate',[(0,0),(100,-1)])],
            [track('opacity',[(i,0) for i in range(65)])]]
        for tracks in invalid:
            with self.subTest(tracks=str(tracks)[:80]),self.assertRaises(AppError):
                config=solid();config['emitters'][0]['keyframes']=tracks;normalize(config)

    def test_bezier_controls_and_unrecognized_fields_reject(self):
        for controls in (None,[0,1,2],[0,0,1,2],[False,1],[0,float('inf')]):
            t=track('rate',[(0,0),(100,2)],'bezier');t['keyframes'][0]['control_points']=controls
            t['keyframes'][1]['control_points']=[0,1]
            with self.assertRaises(AppError):normalize(animated(t))
        t=track('opacity',[(0,1)]);t['keyframes'][0]['control_points']=[0,1]
        with self.assertRaises(AppError):normalize(animated(t))

    def test_inverse_cache_is_bounded_and_cancel_is_polled(self):
        e=normalize(animated(track('rate',[(0,2),(200,6)])))['emitters'][0]
        schedule=BirthSchedule(e,100,200)
        for i in range(1,9):schedule.birth_at(i)
        self.assertLessEqual(len(schedule.cache),schedule.cache_limit)
        def cancel():raise AppError('CANCELLED','cancel integrated inverse',exit_code=8)
        schedule=BirthSchedule(e,100,200,cancel=cancel)
        with self.assertRaisesRegex(AppError,'cancel integrated inverse'):schedule.birth_at(1)


class EmitterCLITests(unittest.TestCase):
    setUp=fixtures.ParticleCLITests.setUp
    call=fixtures.ParticleCLITests.call
    # Only execute new tests here; the shared base tests run separately once.
    def apply(self):
        code,value=self.call('vfx','apply','--project',self.root,'--preset','confetti','--clip-id','test',
            '--duration-tick','180000','--source-duration-tick','360000','--enable-native')
        self.assertEqual(code,0,value);return value
    def points(self,values):
        path=Path(self.temp.name)/'emitter points.json';path.write_text(json.dumps(values),encoding='utf8');return path
    def test_animation_discovery_add_replace_remove_and_snapshot(self):
        self.apply();points=self.points(track('opacity',[(0,0),(360000,1)])['keyframes'])
        code,info=self.call('vfx','animation-properties');self.assertEqual(code,0,info);self.assertEqual(len(info['data']['properties']),21)
        args=['vfx','animate','--project',self.root,'--clip-id','test','--emitter-index','0','--property','opacity','--keyframes',points]
        before=(self.root/'project.json').read_bytes();code,planned=self.call(*args,'--dry-run');self.assertEqual(code,0,planned)
        self.assertEqual(before,(self.root/'project.json').read_bytes())
        code,applied=self.call(*args);self.assertEqual(code,0,applied);self.assertIn('before_snapshot_id',applied['data'])
        clip=applied['data']['clip'];self.assertEqual(clip['generator']['emitters'][0]['keyframes'][0]['property'],'opacity')
        code,value=self.call(*args);self.assertNotEqual(code,0);self.assertEqual(value['errors'][0]['code'],'PARTICLE_ANIMATION_CONFLICT')
        self.assertEqual(self.call(*args,'--replace')[0],0)
        code,value=self.call('vfx','animate','--project',self.root,'--clip-id','test','--emitter-index','0',
            '--property','opacity','--remove');self.assertEqual(code,0,value)
        self.assertNotIn('keyframes',value['data']['clip']['generator']['emitters'][0])
    def test_animation_files_conflict_idempotency_and_locked_track_are_atomic(self):
        self.apply();points=self.points(track('rate',[(0,0),(360000,20)])['keyframes'])
        args=['vfx','animate','--project',self.root,'--clip-id','test','--emitter-index','0','--property','rate','--keyframes',points,'--idempotency-key','emit-rate']
        code,first=self.call(*args);self.assertEqual(code,0,first)
        self.assertEqual(self.call(*args)[0],0)
        before=(self.root/'project.json').read_bytes();points.write_text(json.dumps(track('rate',[(0,1),(360000,20)])['keyframes']),encoding='utf8')
        code,value=self.call(*args);self.assertNotEqual(code,0);self.assertEqual(value['errors'][0]['code'],'IDEMPOTENCY_CONFLICT')
        self.assertEqual(before,(self.root/'project.json').read_bytes())
        root,p=load_project(self.root);next(t for t in p['sequences'][0]['tracks'] if t['clips'])['locked']=True;save_project(root,p)
        before=(root/'project.json').read_bytes()
        code,value=self.call(*args[:-2],'--replace');self.assertNotEqual(code,0);self.assertEqual(value['errors'][0]['code'],'PARTICLE_TRACK_LOCKED')
        self.assertEqual(before,(root/'project.json').read_bytes())
    def test_invalid_points_emitter_index_and_missing_file_do_not_mutate(self):
        self.apply();points=self.points([{'at_tick':360001,'value':1}]);before=(self.root/'project.json').read_bytes()
        args=['vfx','animate','--project',self.root,'--clip-id','test','--emitter-index','0','--property','opacity','--keyframes',points]
        for extra in ([],['--emitter-index','20'],['--keyframes',str(points)+'.missing']):
            code,value=self.call(*args,*extra);self.assertNotEqual(code,0,value);self.assertEqual(before,(self.root/'project.json').read_bytes())


class EmitterGPUTests(unittest.TestCase):
    def test_live_shapes_colors_and_integrated_rate_match_cpu_all_frames(self):
        shape=track('shape',[(0,'disc'),(50,'rectangle'),(100,'ring'),(150,'star')],'hold')
        config=animated(shape,track('rate',[(0,2),(200,12)],'ease_in_out'),
            track('colors',[(0,['#ff6a20']),(200,['#208aff'])]),track('glow',[(0,0),(200,.6)]),
            track('position',[(0,[.1,.5]),(200,[.8,.5])]),rate=2)
        source=ParticleSource(config);errors=[]
        with tempfile.TemporaryDirectory() as folder:
            with FloatGPUSession(folder,{'projection_acceleration':{'mode':'require','device':'0.0'}},max_pixels=96*64) as gpu:
                for frame in range(24):
                    cpu=source.frame(frame);actual=source.frame(frame,gpu=gpu)
                    errors.append(max(float(np.max(abs(cpu[:,:,3]-actual[:,:,3]))),
                        float(np.max(abs(cpu[:,:,:3]*cpu[:,:,3:4]-actual[:,:,:3]*actual[:,:,3:4])))))
                    self.assertLessEqual(errors[-1],3e-6)
            self.assertTrue(gpu.evidence['worker_closed']);self.assertTrue(gpu.evidence['control']['threads_closed'])
            RECEIPTS.append(dict(group='emitter_animation',frames=24,CPU_GPU_max_error=max(errors),GPU=gpu.evidence))


class EmitterIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.fixture=fixtures.ParticleIntegrationTests('runTest');self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        emitter=self.fixture.c['generator']['emitters'][0]
        emitter['keyframes']=[track('rate',[(0,4),(90000,15),(270000,2)],'ease_in_out'),
            track('position',[(0,[.15,.25]),(270000,[.8,.65])]),
            track('colors',[(0,['#ff5e40']),(270000,['#4a8dff'])]),
            track('opacity',[(0,.4),(135000,.95),(270000,.15)])]
        save_project(self.fixture.root,self.fixture.p)
    def collect(self):
        RECEIPTS.extend(copy.deepcopy(fixtures.RECEIPTS));fixtures.RECEIPTS.clear()
    def test_real_animated_cpu_gpu_encoding_and_every_PCM(self):
        self.fixture.test_real_cpu_gpu_encoding_and_every_pcm_sample_agree();self.collect()
    def test_animated_package_OTIO_and_full_encoding_roundtrip(self):
        self.fixture.test_package_and_otio_restore_editable_source_and_identical_full_encoding();self.collect()
    def test_animated_split_and_nested_reverse_preserve_original_source_clock(self):
        self.fixture.test_window_split_and_nested_reverse_have_identical_frames_and_source_ids()
    def test_key_change_invalidates_actual_preview_and_queue_matches_direct(self):
        f=self.fixture
        from ai_ad_editor import preview
        from ai_ad_editor.project import project_write_lock
        request=preview.plan(f.p,f.s,start_frame=0,end_frame=3,mode='range',height=64)
        with project_write_lock(f.root):
            a=preview.preview_project(f.root,f.p,f.s,request=request)
            b=preview.preview_project(f.root,f.p,f.s,request=request)
        self.assertTrue(b['cache_hit']);self.assertEqual(a['cache_key'],b['cache_key'])
        f.c['generator']['emitters'][0]['keyframes'][-1]['keyframes'][0]['value']=.8
        save_project(f.root,f.p)
        with project_write_lock(f.root):c=preview.preview_project(f.root,f.p,f.s,request=request)
        self.assertNotEqual(c['cache_key'],a['cache_key']);self.assertFalse(c['cache_hit'])
        path=f.base/'job.json';path.write_text(json.dumps({'job_id':'emitter-job','container':'mkv','output':'renders/queued.mkv'}),encoding='utf8')
        f.call('queue','enqueue','--project',f.root,'--input',path)
        result=f.call('queue','run','--project',f.root,'--job-id','emitter-job')
        self.assertEqual(result['summary']['succeeded'],1)
        self.assertEqual(f.video(f.execute('direct.mkv')),f.video(f.root/'renders/queued.mkv'))
        self.collect();RECEIPTS.append(dict(preview=[a,b,c],queue=result))


if __name__=='__main__':unittest.main(verbosity=2)
