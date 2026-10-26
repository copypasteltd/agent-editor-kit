"""Independent geometry/clock oracles and transactional native render integration."""
from __future__ import annotations
import contextlib,copy,hashlib,io,json,math,subprocess,tempfile,unittest
from fractions import Fraction as F
from pathlib import Path
import numpy as np
from ai_ad_editor import cli,render
from ai_ad_editor.errors import AppError
from ai_ad_editor.float_color_signal import ColorSignal
from ai_ad_editor.float_timeline import FloatTimeline
from ai_ad_editor.float_gpu import FloatGPUSession
from ai_ad_editor.media import ffmpeg_path
from ai_ad_editor.procedural_particles import ParticleSource,normalize,tile_index,validate_scene,identity,MAX_RASTER_VISITS
from ai_ad_editor.procedural_presets import source,catalog
from ai_ad_editor.project import create_project,save_project,load_project
from ai_ad_editor.source_edits import slip,source_bounds
from ai_ad_editor.validator import validate_project

RECEIPTS=[]
LINEAR=ColorSignal('bt709','linear')


def recipe(**updates):
    config=source('snow',canvas={'width':96,'height':64},fps={'num':12,'den':1},duration_tick=200,ticks_per_second=100,seed=73)
    config.update(updates);return config


def solid(**updates):
    # Only birth zero exists, with no random geometric or color ranges.
    e={'rate':.1,'lifetime':[20,20],'position':[.5,.5],'spread':[0,0],
       'velocity':[[0,0],[0,0]],'acceleration':[0,0],'size':[.15,.15],'size_end':1,
       'rotation':[0,0],'spin':[0,0],'colors':['#ff0000'],'fade_in':0,'fade_out':0,
       'softness':0,'opacity':.5,'prewarm':False}
    e.update(updates);return recipe(emitters=[e])


def minimal(config):
    return {'settings':{'canvas':{'width':96,'height':64,'background':'transparent'},
        'timebase':{'ticks_per_second':100,'display_fps':{'num':12,'den':1}}},'assets':[],
        'sequences':[{'id':'main','duration_tick':200,'tracks':[{'id':'v','kind':'overlay','order':0,'clips':[
            {'id':'p','timeline_start_tick':0,'duration_tick':200,'source_in_tick':0,'source_out_tick':200,'generator':config}]}]}]}


class ParticleTests(unittest.TestCase):
    def code(self,expected,fn):
        with self.assertRaises(AppError) as caught:fn()
        self.assertEqual(caught.exception.code,expected)

    def test_birth_trajectory_and_interior_alpha_have_independent_numeric_oracles(self):
        p=ParticleSource(solid(velocity=[[.1,.1],[.2,.2]],acceleration=[.04,-.08]))
        scene=p.scene(6);self.assertEqual(scene.shape,(1,13))
        at=.5
        self.assertAlmostEqual(scene[0,0],(.5+.1*at+.5*.04*at**2)*96-.5,places=5)
        self.assertAlmostEqual(scene[0,1],(.5+.2*at-.5*.08*at**2)*64-.5,places=5)
        frame=p.frame(6);x,y=map(lambda n:int(round(n)),scene[0,:2])
        np.testing.assert_array_equal(frame[y,x],[1,0,0,.5]);np.testing.assert_array_equal(frame[0,0],[0,0,0,0])

    def test_overlap_is_ordered_linear_premultiplied_over(self):
        config=solid();blue=copy.deepcopy(config['emitters'][0]);blue['colors']=['#0000ff'];config['emitters'].append(blue)
        f=ParticleSource(config).frame(4)
        np.testing.assert_allclose(f[32,48],[1/3,0,2/3,.75],atol=3e-8)
        config['emitters'].reverse();g=ParticleSource(config).frame(4)
        np.testing.assert_allclose(g[32,48],[2/3,0,1/3,.75],atol=3e-8)

    def test_exact_fractional_grid_matches_half_open_media_intervals(self):
        p=ParticleSource(recipe(fps={'num':30000,'den':1001},duration_tick=107))
        self.assertEqual(p.frames,33)
        for index in range(p.frames):
            point=F(index*1001,30000)
            self.assertEqual(p.index_at(point),index)
            self.assertEqual(p.index_at(point,right_edge=True),index-1 if index else None)
        self.assertIsNone(p.index_at(F(107,100)))
        self.assertEqual(p.index_at(F(107,100),right_edge=True),32)
        self.assertIsNone(p.index_at(-1));self.assertIsNone(p.index_at(2))

    def test_seek_reorder_seed_and_emitter_defaults_are_deterministic(self):
        a=ParticleSource(recipe());b=ParticleSource(recipe());expected={i:a.frame(i) for i in range(24)}
        for index in [23,0,11,5,23,4,0]:np.testing.assert_array_equal(b.frame(index),expected[index])
        self.assertEqual(normalize(normalize(recipe())),normalize(recipe()))
        self.assertEqual(a.sha256,identity(normalize(recipe())))
        self.assertFalse(np.array_equal(ParticleSource(recipe(seed=74)).frame(11),expected[11]))

    def test_all_six_recipes_are_visible_and_different_without_external_assets(self):
        hashes=[]
        for row in catalog():
            p=ParticleSource(source(row['id'],canvas={'width':192,'height':108},fps={'num':12,'den':1},duration_tick=300,ticks_per_second=100,seed=3))
            f=p.frame(12);self.assertTrue(np.isfinite(f).all());self.assertGreater(float(f[:,:,3].sum()),1)
            self.assertEqual(row['external_assets'],[]);self.assertEqual(row['license'],'MIT')
            hashes.append(hashlib.sha256(f.tobytes()).hexdigest())
        self.assertEqual(len(set(hashes)),6)

    def test_rotated_rectangle_corners_are_not_clipped_by_disc_bounds(self):
        f=ParticleSource(solid(shape='rectangle',rotation=[45,45],size=[.3,.3],opacity=1)).frame(5)
        # At x=center+1.25 radius,y=center the point is inside a rotated square.
        self.assertEqual(float(f[32,71,3]),1.)

    def test_shapes_palette_fades_and_transparency(self):
        hashes=[]
        for shape in ('disc','rectangle','diamond','star','ring'):
            f=ParticleSource(solid(shape=shape)).frame(4);hashes.append(hashlib.sha256(f.tobytes()).hexdigest())
            self.assertTrue(np.all(f[:,:,:3][f[:,:,3]==0]==0))
        self.assertEqual(len(set(hashes)),5)
        p=ParticleSource(solid(lifetime=[2,2],fade_in=.5,fade_out=.5))
        self.assertEqual(float(p.frame(0)[:,:,3].max()),0.)
        self.assertAlmostEqual(float(p.frame(6)[:,:,3].max()),.25)
        p=ParticleSource(solid(colors=['#808080']))
        self.assertAlmostEqual(float(p.frame(4)[32,48,0]),((128/255+.055)/1.055)**2.4,places=7)

    def test_resource_limits_and_bad_parameters_fail_before_allocation(self):
        for change in ({'seed':True},{'seed':-1},{'duration_tick':60001},{'fps':{'num':121,'den':1}},
                       {'canvas':{'width':8192,'height':8192}},{'unrecognized':1}):
            with self.assertRaises(AppError):normalize(recipe(**change))
        for change in ({'colors':['bad']},{'velocity':[[1,-1],[0,1]]},{'rate':float('nan')},
                       {'lifetime':[120,120],'rate':1000},{'opacity':True},{'shape':'unknown'}):
            with self.assertRaises(AppError):normalize(solid(**change))
        self.code('PARTICLE_BUDGET',lambda:ParticleSource(recipe()).frame(0,max_working_bytes=100))
        self.code('PARTICLE_BUDGET',lambda:ParticleSource(recipe()).frame(0,max_working_bytes=True))
        config=solid(rate=100,lifetime=[20,20],size=[.5,.5],prewarm=True)
        config['canvas']={'width':384,'height':256}
        self.code('PARTICLE_BUDGET',lambda:ParticleSource(config).frame(0))

    def test_cancel_interrupts_scene_and_raster(self):
        calls=[]
        def cancel():
            calls.append(1)
            if len(calls)>10:raise AppError('CANCELLED','test',exit_code=8)
        self.code('CANCELLED',lambda:ParticleSource(recipe(),cancel=cancel).frame(5))

    def test_tile_indices_reject_tampering_and_unsafe_device_data(self):
        scene=ParticleSource(recipe()).scene(5);tiles=tile_index(scene,(96,64))
        validate_scene(scene,tiles,(96,64));bad=tiles.copy();bad[-1]^=1
        self.code('PARTICLE_SCENE',lambda:validate_scene(scene,bad,(96,64)))
        bad=scene.copy();bad[0,2]=0
        self.code('PARTICLE_SCENE',lambda:validate_scene(bad,tiles,(96,64)))

    def test_native_clock_reverse_split_crop_and_keyframes_keep_particle_identity(self):
        p=minimal(recipe());c=p['sequences'][0]['tracks'][0]['clips'][0]
        c.update(source_in_tick=25,source_out_tick=175,duration_tick=150,reverse=True)
        p['sequences'][0]['duration_tick']=150
        host=FloatTimeline(p,'main',{},working_signal=LINEAR)
        indices=[]
        for index in range(18):
            _,meta=host.render_frame(index);indices.append(meta['layers'][0]['native_frame_index'])
        self.assertEqual(indices,[math.ceil((F(175,100)-F(i,12))*12)-1 for i in range(18)])
        c.update(transform={'opacity':.4},keyframes=[{'property':'transform.position.x','keyframes':[
            {'at_tick':0,'value':48},{'at_tick':150,'value':52}]}])
        host=FloatTimeline(p,'main',{},working_signal=LINEAR);f,meta=host.render_frame(0)
        self.assertAlmostEqual(meta['layers'][0]['opacity'],.4)
        self.assertEqual(meta['layers'][0]['particles']['source_frame_index'],20)
        self.assertLessEqual(float(f[:,:,3].max()),.4)

    def test_particle_slip_bounds_are_the_declared_source_not_current_author_window(self):
        p=minimal(recipe());c=p['sequences'][0]['tracks'][0]['clips'][0]
        c.update(source_in_tick=20,source_out_tick=120,duration_tick=100)
        changed,info=slip(p,c,50);self.assertEqual([changed['source_in_tick'],changed['source_out_tick']],[70,170])
        self.assertEqual(source_bounds(p,c)['end_tick'],200);self.assertEqual(info['source_kind'],'particles')
        self.code('SOURCE_EDIT_HANDLE_SHORTFALL',lambda:slip(p,c,81))


class ParticleCLITests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='particles-');self.addCleanup(self.temp.cleanup)
        self.root,self.p=create_project(Path(self.temp.name)/'project');save_project(self.root,self.p)
    def call(self,*args):
        buf=io.StringIO()
        with contextlib.redirect_stdout(buf):code=cli.main(list(map(str,args)))
        value=json.loads(buf.getvalue());return code,value
    def test_dry_run_apply_update_show_and_failed_change_are_transactional(self):
        before=(self.root/'project.json').read_bytes()
        args=['vfx','apply','--project',self.root,'--preset','snow','--clip-id','snow','--duration-tick','90000','--enable-native']
        code,value=self.call(*args,'--dry-run');self.assertEqual(code,0,value)
        self.assertEqual((self.root/'project.json').read_bytes(),before)
        code,value=self.call(*args);self.assertEqual(code,0,value)
        code,value=self.call('vfx','show','--project',self.root,'--clip-id','snow');self.assertEqual(code,0,value)
        old=value['data']['clip'];self.assertEqual(value['data']['generator']['type'],'particles')
        code,value=self.call('vfx','update','--project',self.root,'--clip-id','snow','--preset','embers','--seed','8')
        self.assertEqual(code,0,value);new=value['data']['clip']
        for key in ('id','timeline_start_tick','duration_tick','source_in_tick','source_out_tick'):self.assertEqual(old[key],new[key])
        before=(self.root/'project.json').read_bytes()
        code,value=self.call('vfx','update','--project',self.root,'--clip-id','snow','--preset','snow','--seed','-1')
        self.assertNotEqual(code,0);self.assertEqual((self.root/'project.json').read_bytes(),before)
    def test_source_signals_and_backend_are_explicit(self):
        code,value=self.call('vfx','apply','--project',self.root,'--preset','snow','--duration-tick','90000')
        self.assertNotEqual(code,0);self.assertEqual(value['errors'][0]['code'],'PARTICLE_NATIVE_PIPELINE_REQUIRED')
        code,value=self.call('vfx','list');self.assertEqual(code,0,value);self.assertEqual(value['data']['count'],6)
    def test_locked_tracks_and_unused_or_zero_source_arguments_are_rejected(self):
        args=['vfx','apply','--project',self.root,'--preset','snow','--clip-id','snow','--duration-tick','90000','--enable-native']
        code,value=self.call(*args);self.assertEqual(code,0,value)
        root,p=load_project(self.root);track=next(t for t in p['sequences'][0]['tracks'] if t['clips']);track['locked']=True
        save_project(root,p);before=(root/'project.json').read_bytes()
        code,value=self.call('vfx','update','--project',root,'--clip-id','snow','--preset','rain')
        self.assertNotEqual(code,0);self.assertEqual(value['errors'][0]['code'],'PARTICLE_TRACK_LOCKED')
        self.assertEqual((root/'project.json').read_bytes(),before)
        code,value=self.call(*args,'--source-duration-tick','0');self.assertNotEqual(code,0)
        self.assertEqual(value['errors'][0]['code'],'PARTICLE_SOURCE_DURATION_ARGUMENT')
        path=Path(self.temp.name)/'signals.json';path.write_text('[]',encoding='utf8')
        code,value=self.call('vfx','apply','--project',root,'--preset','snow','--duration-tick','90000','--source-signals',path)
        self.assertNotEqual(code,0);self.assertEqual(value['errors'][0]['code'],'PARTICLE_SOURCE_SIGNAL_ARGUMENT')
    def test_custom_source_file_is_loaded_and_seed_override_is_retained(self):
        path=Path(self.temp.name)/'custom source.json';path.write_text(json.dumps(solid()),encoding='utf8')
        code,value=self.call('vfx','apply','--project',self.root,'--config',path,'--clip-id','custom',
            '--duration-tick','180000','--enable-native','--seed','94')
        self.assertEqual(code,0,value);config=value['data']['clip']['generator']
        self.assertEqual(config['seed'],94);self.assertEqual(config['canvas'],{'width':96,'height':64})
    def test_empty_explicit_signal_file_is_loaded_for_a_new_project(self):
        path=Path(self.temp.name)/'signals.json';path.write_text('{}',encoding='utf8')
        code,value=self.call('vfx','apply','--project',self.root,'--preset','rain','--duration-tick','90000',
            '--source-signals',path,'--enable-native')
        self.assertEqual(code,0,value);self.assertEqual(load_project(self.root)[1]['settings']['pixel_pipeline']['sources'],{})
    def test_invalid_missing_and_oversize_JSON_return_structured_error_and_no_mutation(self):
        path=Path(self.temp.name)/'invalid.json';before=(self.root/'project.json').read_bytes()
        for data in (None,'{"bad":',' '*1100000):
            if data is not None:path.write_text(data,encoding='utf8')
            code,value=self.call('vfx','apply','--project',self.root,'--config',path,'--duration-tick','90000','--enable-native')
            self.assertNotEqual(code,0);self.assertEqual(value['errors'][0]['code'],'PARTICLE_JSON')
            self.assertEqual((self.root/'project.json').read_bytes(),before)

    def test_file_content_change_conflicts_instead_of_replaying_stale_configuration(self):
        path=Path(self.temp.name)/'custom.json';path.write_text(json.dumps(solid()),encoding='utf8')
        signals=Path(self.temp.name)/'signals.json';signals.write_text('{}',encoding='utf8')
        args=['vfx','apply','--project',self.root,'--config',path,'--clip-id','custom',
            '--duration-tick','180000','--enable-native','--source-signals',signals,'--idempotency-key','particle-files']
        code,first=self.call(*args);self.assertEqual(code,0,first)
        before=(self.root/'project.json').read_bytes()
        code,replay=self.call(*args);self.assertEqual(code,0,replay)
        self.assertEqual(first['data']['clip'],replay['data']['clip'])
        changed=solid();changed['seed']+=1;path.write_text(json.dumps(changed),encoding='utf8')
        code,value=self.call(*args);self.assertNotEqual(code,0)
        self.assertEqual(value['errors'][0]['code'],'IDEMPOTENCY_CONFLICT')
        path.write_text(json.dumps(solid()),encoding='utf8');signals.write_text('{"new":{}}',encoding='utf8')
        code,value=self.call(*args);self.assertNotEqual(code,0)
        self.assertEqual(value['errors'][0]['code'],'IDEMPOTENCY_CONFLICT')
        self.assertEqual((self.root/'project.json').read_bytes(),before)


class ParticleGPUTests(unittest.TestCase):
    def test_actual_gpu_five_shapes_prewarms_and_translucent_over_match_cpu(self):
        with tempfile.TemporaryDirectory(prefix='particle-gpu-') as folder:
            with FloatGPUSession(Path(folder),{'projection_acceleration':{'mode':'require','device':'0.0'}},max_pixels=192*108) as gpu:
                errors=[]
                for name in ('snow','confetti','embers','bokeh','rain','sparkles'):
                    config=source(name,canvas={'width':192,'height':108},fps={'num':12,'den':1},duration_tick=200,ticks_per_second=100,seed=93)
                    p=ParticleSource(config)
                    for frame in (0,7,23):
                        cpu=p.frame(frame);actual=p.frame(frame,gpu=gpu)
                        # Straight RGB near zero alpha amplifies tiny coverage errors;
                        # compare premultiplied light plus coverage independently.
                        delta=max(float(np.max(np.abs(cpu[:,:,3]-actual[:,:,3]))),
                            float(np.max(np.abs(cpu[:,:,:3]*cpu[:,:,3:4]-actual[:,:,:3]*actual[:,:,3:4]))))
                        errors.append(delta);self.assertLessEqual(delta,3e-6,(name,frame,delta))
                for shape in ('disc','rectangle','diamond','star','ring'):
                    p=ParticleSource(solid(shape=shape,rotation=[43,43],softness=.37,glow=.5,colors=['#7bbacf']))
                    cpu=p.frame(11);actual=p.frame(11,gpu=gpu)
                    delta=max(float(np.max(np.abs(cpu[:,:,3]-actual[:,:,3]))),
                        float(np.max(np.abs(cpu[:,:,:3]*cpu[:,:,3:4]-actual[:,:,:3]*actual[:,:,3:4]))))
                    errors.append(delta);self.assertLessEqual(delta,3e-6,(shape,delta))
                self.assertEqual(gpu.evidence['operations']['particles'],23)
                gpu.evidence['particle_cpu_max_error']=max(errors)
            self.assertTrue(gpu.evidence['worker_closed']);RECEIPTS.append(copy.deepcopy(gpu.evidence))


class ParticleIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='particle-integration-');self.addCleanup(self.temp.cleanup)
        self.base=Path(self.temp.name);self.root,self.p=create_project(self.base/'project')
        s=self.p['settings'];s['canvas'].update(width=96,height=64,background='#102030')
        s['timebase']['display_fps']={'num':12,'den':1};s['color']['transfer']='linear'
        from ai_ad_editor.float_standard_render import ENGINE
        s['pixel_pipeline']={'engine':ENGINE,'working_signal':vars(LINEAR),'output_signal':vars(LINEAR),'sources':{}}
        s['output']={'container':'mkv','video':{'codec':'libx264','crf':0,'preset':'ultrafast','pixel_format':'yuv444p10le'},
            'audio':{'codec':'pcm_f32le'}}
        self.s=self.p['sequences'][0];self.s['duration_tick']=180000
        self.c={'id':'particles','timeline_start_tick':0,'duration_tick':180000,'source_in_tick':0,
            'source_out_tick':180000,'generator':source('confetti',canvas={'width':96,'height':64},
                fps={'num':12,'den':1},duration_tick=270000,ticks_per_second=90000,seed=91)}
        self.s['tracks']=[{'id':'video','kind':'video','order':0,'clips':[self.c]}]
        save_project(self.root,self.p)
    def call(self,*args):
        out=io.StringIO()
        with contextlib.redirect_stdout(out):code=cli.main(list(map(str,args)))
        value=json.loads(out.getvalue());self.assertEqual(code,0,value);return value['data']
    def execute(self,name='actual.mkv',root=None,project=None):
        from ai_ad_editor.project import project_write_lock
        root=root or self.root;project=project or self.p;save_project(root,project)
        with project_write_lock(root):result=render.render_project(root,project,project['sequences'][0],root/'renders'/name)
        RECEIPTS.append({'test':self.id(),'render':copy.deepcopy(result)});return Path(result['path'])
    def native(self,command):
        result=subprocess.run(list(map(str,command)),capture_output=True,timeout=120,creationflags=subprocess.CREATE_NO_WINDOW)
        self.assertEqual(result.returncode,0,result.stderr.decode('utf8','replace'))
        RECEIPTS.append({'test':self.id(),'argv':list(map(str,command)),'exit_code':result.returncode,
            'stdout_bytes':len(result.stdout),'stdout_sha256':hashlib.sha256(result.stdout).hexdigest()})
        return result.stdout
    def video(self,path):
        return self.native([ffmpeg_path(),'-nostdin','-v','error','-i',path,'-map','0:v:0','-an','-pix_fmt','yuv444p10le','-f','rawvideo','pipe:1'])
    def test_real_cpu_gpu_encoding_and_every_pcm_sample_agree(self):
        a=self.execute('cpu.mkv');self.p['settings']['projection_acceleration']={'mode':'require','device':'0.0'}
        b=self.execute('gpu.mkv')
        x=np.frombuffer(self.video(a),'<u2');y=np.frombuffer(self.video(b),'<u2')
        self.assertEqual(len(x),24*96*64*3);self.assertLessEqual(int(np.max(np.abs(x.astype(int)-y.astype(int)))),1)
        audio=self.native([ffmpeg_path(),'-nostdin','-v','error','-i',b,'-map','0:a:0','-vn','-c:a','pcm_f32le','-f','f32le','pipe:1'])
        self.assertEqual(len(audio),2*48000*2*4);self.assertTrue(np.all(np.frombuffer(audio,'<f4')==0))
        manifest=json.loads(b.with_suffix('.mkv.manifest.json').read_bytes())
        evidence=manifest['delivery']['pixel_pipeline']['projection_acceleration']
        self.assertEqual(evidence['operations']['particles'],24);self.assertTrue(evidence['worker_closed'])
    def test_package_and_otio_restore_editable_source_and_identical_full_encoding(self):
        from ai_ad_editor.convert import export_external,import_external
        before=self.video(self.execute('original.mkv'))
        for format,suffix in (('package','.aevpkg.zip'),('otio','.otio')):
            exported=self.base/('editable'+suffix);result=export_external(self.root,self.p,exported,format)
            imported=import_external(exported,self.base/('restored-'+format))
            root,p=load_project(imported['root']);c=next(c for t in p['sequences'][0]['tracks'] for c in t['clips'])
            self.assertEqual(c['generator'],self.c['generator']);self.assertEqual(p['assets'],[])
            self.assertTrue(validate_project(root,p,strict_rights=False)['ok'])
            after=self.video(self.execute('restored.mkv',root,p));self.assertEqual(before,after)
            RECEIPTS.append({'test':self.id(),'format':format,'all_frames_equal':True,'export':result['report_data']})
    def test_real_preview_cache_seed_edit_and_persistent_queue(self):
        from ai_ad_editor import preview
        from ai_ad_editor.project import project_write_lock
        request=preview.plan(self.p,self.s,start_frame=0,end_frame=3,mode='range',height=64)
        with project_write_lock(self.root):
            a=preview.preview_project(self.root,self.p,self.s,request=request)
            b=preview.preview_project(self.root,self.p,self.s,request=request)
        self.assertEqual(a['cache_key'],b['cache_key']);self.assertTrue(b['cache_hit'])
        self.c['generator']['seed']+=1;save_project(self.root,self.p)
        with project_write_lock(self.root):c=preview.preview_project(self.root,self.p,self.s,request=request)
        self.assertNotEqual(a['cache_key'],c['cache_key']);self.assertFalse(c['cache_hit'])
        path=self.base/'job.json';path.write_text(json.dumps({'job_id':'particle-job','container':'mkv','output':'renders/queued.mkv'}),encoding='utf8')
        self.call('queue','enqueue','--project',self.root,'--input',path)
        result=self.call('queue','run','--project',self.root,'--job-id','particle-job')
        self.assertEqual(result['summary']['succeeded'],1)
        self.assertEqual(self.video(self.execute('direct.mkv')),self.video(self.root/'renders/queued.mkv'))
        RECEIPTS.append({'test':self.id(),'preview':[a,b,c],'queue':result})
    def test_window_split_and_nested_reverse_have_identical_frames_and_source_ids(self):
        from ai_ad_editor.clip_windows import slice_clip
        original=FloatTimeline(self.p,self.s['id'],{},working_signal=LINEAR)
        frames=[original.render_frame(i)[0] for i in range(24)]
        self.s['tracks'][0]['clips']=[slice_clip(self.c,0,75000,clip_id='left'),slice_clip(self.c,75000,180000,clip_id='right')]
        split=FloatTimeline(self.p,self.s['id'],{},working_signal=LINEAR)
        for i in range(24):np.testing.assert_array_equal(split.render_frame(i)[0],frames[i])
        child=copy.deepcopy(self.s);child['id']='child';self.s['tracks'][0]['clips']=[{'id':'nested','sequence_id':'child',
            'timeline_start_tick':0,'duration_tick':180000,'source_in_tick':0,'source_out_tick':180000,'reverse':True}]
        self.p['sequences'].append(child)
        nested=FloatTimeline(self.p,self.s['id'],{},working_signal=LINEAR)
        for i in range(24):np.testing.assert_array_equal(nested.render_frame(i)[0],frames[23-i])
    def test_legacy_never_drops_generator_and_fingerprint_includes_kernel(self):
        p=copy.deepcopy(self.p);p['settings'].pop('pixel_pipeline')
        with self.assertRaises(AppError) as caught:render.build_filter_graph(self.root,p,p['sequences'][0])
        self.assertEqual(caught.exception.code,'PARTICLE_NATIVE_PIPELINE_REQUIRED')
        before=render.render_fingerprints(self.p,self.s,self.p['settings'],self.root)
        self.assertIn('runtime:particles:float_gpu_native',before['input_hashes'])
        self.c['generator']['seed']+=1
        after=render.render_fingerprints(self.p,self.s,self.p['settings'],self.root)
        self.assertNotEqual(before['project_fingerprint'],after['project_fingerprint'])


if __name__=='__main__':unittest.main()
