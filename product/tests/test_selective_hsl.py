"""Real geq pixels against an independent colorsys/bisect HSL reference."""
from __future__ import annotations
from bisect import bisect_right
import colorsys
import copy
from fractions import Fraction
import json
import math
from pathlib import Path
import random
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image
from ai_ad_editor.capabilities import build_capability_manifest
from ai_ad_editor.clip_windows import apply_operation
from ai_ad_editor.edit_planner import build_edit_plan
from ai_ad_editor.effect_automation import EffectAutomation, validate
from ai_ad_editor.effects import effect_catalog, get_effect
from ai_ad_editor.errors import AppError
from ai_ad_editor.media import ffmpeg_path
from ai_ad_editor.project import create_project, load_project, save_project
from ai_ad_editor.render import _effect_filters, build_filter_graph
from test_magnetic_reorder import invoke
from test_spatial_automation import declared_bezier_reference

W,H,TPS=48,24,90000
CENTERS=(0,30,60,120,180,240,270,300)
NAMES=('red','orange','yellow','green','cyan','blue','purple','magenta')
CHANNELS={f'{name}_{axis}': (45. if axis=='hue' else .6)
          for name in NAMES for axis in ('hue','saturation','lightness')}
CHANNELS['intensity']=1.
FRAME=bytes(c for y in range(H) for x in range(W) for c in (
    *(round(v*255) for v in colorsys.hls_to_rgb(x/W,.08+.84*(y//4)/5,(0,.05,.5,.9)[y%4])),
    (0,128,255)[(x+y)%3]))


def oracle_pixel(rgb, params):
    """Neighbor interpolation and standard-library HLS, no product math."""
    h,l,s=colorsys.rgb_to_hls(*(v/255 for v in rgb))
    if s==0:
        return tuple(rgb)
    degrees=h*360
    right=bisect_right(CENTERS,degrees)
    a=CENTERS[right-1];b=CENTERS[right] if right<len(CENTERS) else 360
    t=(degrees-a)/(b-a)
    weights={NAMES[right-1]:1-t,NAMES[right%len(NAMES)]:t}
    def shift(axis):return sum(w*params.get(name+'_'+axis,0) for name,w in weights.items())
    def adjust(v,d):return v+(1-v)*d if d>=0 else v*(1+d)
    adjusted=colorsys.hls_to_rgb((h+shift('hue')/360)%1,adjust(l,shift('lightness')),adjust(s,shift('saturation')))
    strength=params.get('intensity',1)
    return tuple(math.floor(max(0,min(255,original+(255*value-original)*strength))+.5)
                 for original,value in zip(rgb,adjusted))


def oracle_frame(frame,params):
    result=bytearray(frame)
    for i in range(0,len(frame),4):result[i:i+3]=bytes(oracle_pixel(frame[i:i+3],params))
    return bytes(result)


def effect(prop='red_hue',left=0.,right=60.,*,params=None,easing='linear',end=TPS):
    point={'at_tick':0,'value':left,'interpolation':easing}
    if easing=='bezier':point['control_points']=[1/3,0,2/3,1]
    return {'type':'selective_hsl','parameters':params or {},'keyframes':[{'property':prop,'keyframes':[
        point,{'at_tick':end,'value':right,'interpolation':'linear'}]}]}


def sample(**fields):
    return {'id':'clip','timeline_start_tick':0,'duration_tick':TPS,**fields}


class SelectiveCase(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory(prefix='selective-hsl-');self.addCleanup(temp.cleanup);self.root=Path(temp.name)

    def bind(self,value,*,compiler=None,clip=None,start=0,rate='6'):
        compiler=compiler or EffectAutomation(self.root,rate,TPS);metadata=[];warnings=[]
        chain=_effect_filters(value if isinstance(value,list) else [value],warnings,'clip',root=self.root,clip=clip or sample(),
                              clip_start=start,tps=TPS,automation=compiler,automation_meta=metadata)
        self.assertFalse(warnings,warnings)
        return ','.join(chain) or 'null',metadata,compiler

    def native(self,value,*,frame=FRAME,count=6,rate='6',start=0,clip=None,threads=1):
        chain,metadata,compiler=self.bind(value,clip=clip,start=start,rate=rate)
        graph=self.root/'graph.ffgraph';graph.write_text(f'[0:v]setpts=PTS+{start}/TB,{chain},format=rgba[out]',encoding='utf8')
        result=subprocess.run([ffmpeg_path(),'-v','error','-filter_complex_threads',str(threads),
            '-f','rawvideo','-pixel_format','rgba','-video_size',f'{W}x{H}','-framerate',rate,'-i','pipe:0',
            '-filter_complex_script',graph,'-map','[out]','-fps_mode','passthrough','-f','rawvideo','-pix_fmt','rgba','pipe:1'],
            input=frame*count,capture_output=True,cwd=self.root,timeout=90)
        self.assertEqual(result.returncode,0,result.stderr.decode('utf8','replace'))
        self.assertEqual(len(result.stdout),len(frame)*count)
        return [result.stdout[i:i+len(frame)] for i in range(0,len(result.stdout),len(frame))],metadata,compiler

    def compare(self,actual,expected):
        self.assertLessEqual(max(abs(a-b) for a,b in zip(actual,expected)),1)
        self.assertEqual(actual[3::4],expected[3::4])


class SelectiveContractTests(SelectiveCase):
    def test_discovery_separates_real_hsl_kernel_from_native_command_channels(self):
        item=get_effect('selective_hsl');self.assertEqual(len(item['keyframe_parameters']),25)
        self.assertEqual(effect_catalog()['count'],51);self.assertEqual(effect_catalog()['catalog_version'],'0.11.0')
        manifest=build_capability_manifest()['capabilities']['effects'];self.assertEqual(manifest['selective_hsl']['numeric_channels'],25)
        self.assertEqual(manifest['numeric_effect_automation']['numeric_channels'],34)
        self.assertEqual(len(manifest['numeric_effect_automation']['effects']),10)

    def test_all_aliases_prefixes_and_parameter_tracks_execute(self):
        for alias in ['selective_hsl','hsl-bands','eight_band_hsl']:
            for prefix in ['', 'effect.', 'parameters.',alias.replace('-','_')+'.']:
                v=effect();v['type']=alias;v['keyframes'][0]['property']=prefix+'red_hue'
                v['parameters']['keyframes']=v.pop('keyframes')
                self.assertFalse(validate(v));_,meta,_=self.bind(v);self.assertEqual(meta[0]['animated_parameters'],['red_hue'])

    def test_static_unknown_nonfinite_boolean_and_outside_values_reject(self):
        for name,value in [('red_hue',True),('red_hue',10**400),('blue_saturation',1.01),
                           ('orange_lightness',-.01-1),('intensity',float('nan')),('bands',{}),('red_sat',.2)]:
            self.assertTrue(validate({'type':'selective_hsl','parameters':{name:value}}))

    def test_bad_tracks_duplicate_channels_ticks_and_controls_reject(self):
        for mutate in [lambda v:v['keyframes'].append(copy.deepcopy(v['keyframes'][0])),
                       lambda v:v['keyframes'][0].update(property='color'),
                       lambda v:v['keyframes'][0]['keyframes'][1].update(at_tick=0),
                       lambda v:v['keyframes'][0]['keyframes'][1].update(value=10**400),
                       lambda v:v['keyframes'][0]['keyframes'][0].update(interpolation='bezier',control_points=[0,10**400])]:
            v=effect();mutate(v);self.assertTrue(validate(v))
        self.assertTrue(validate(effect(end=TPS+1),duration_tick=TPS))

    def test_top_level_precedence_disabled_and_zero_intensity_bypass(self):
        v=effect();v['parameters']['keyframes']=[{'property':'bad','keyframes':[]}]
        self.assertFalse(validate(v));v['enabled']=False
        chain,meta,compiler=self.bind(v);self.assertEqual(chain,'null');self.assertEqual(meta,[])
        self.assertEqual(compiler.summary()['effect_instances_total'],0)
        v={'type':'selective_hsl','parameters':{'red_hue':120,'intensity':0}}
        self.assertTrue(self.bind(v)[1][0]['bypass'])
        self.assertEqual(self.native(v,count=1)[0],[FRAME])
        compiler=EffectAutomation(self.root,'6',TPS);compiler.samples=2_000_000;compiler.targets=1024
        _,meta,_=self.bind(v,compiler=compiler,clip=sample(duration_tick=100_000_000_000))
        self.assertEqual(meta[0]['state_samples'],0);self.assertIsNone(meta[0]['instance'])
        self.assertEqual(compiler.samples,2_000_000);self.assertEqual(compiler.hsl_instances,0)

    def test_single_expression_and_shared_recursive_limits_reject(self):
        with patch('ai_ad_editor.selective_hsl.MAX_KERNEL_BYTES',10):
            with self.assertRaises(AppError) as failure:self.bind(effect())
        self.assertEqual(failure.exception.code,'SELECTIVE_HSL_BUDGET')
        compiler=EffectAutomation(self.root,'6',TPS);compiler.targets=1024
        with self.assertRaises(AppError):self.bind(effect(),compiler=compiler)
        compiler=EffectAutomation(self.root,'6',TPS);compiler.samples=2_000_000
        with self.assertRaises(AppError):self.bind(effect(),compiler=compiler)
        compiler=EffectAutomation(self.root,'6',TPS);compiler.hsl_expression_bytes=16*1024**2
        with self.assertRaises(AppError):self.bind(effect(),compiler=compiler)

    def test_hsl_instances_also_consume_native_command_instance_budget(self):
        compiler=EffectAutomation(self.root,'6',TPS);compiler.hsl_instances=1024
        from test_effect_automation import effect as native_effect
        with self.assertRaises(AppError):self.bind(native_effect(),compiler=compiler)

    def test_metadata_records_algorithm_and_actual_frame_budget(self):
        _,meta,compiler=self.bind(effect());m=meta[0]
        self.assertEqual(m['bands_degrees'],dict(zip(NAMES,CENTERS)))
        self.assertEqual(m['sampled_frames'],6);self.assertEqual(m['alpha'],'exact-input-alpha')
        self.assertTrue(m['kernel_sha256'].startswith('sha256:'))
        self.assertEqual(compiler.summary()['effect_instances_total'],1)
        self.assertEqual(compiler.summary()['selective_hsl_expression_bytes'],m['kernel_bytes'])


class SelectiveNativeTests(SelectiveCase):
    def test_all_twenty_five_channels_match_independent_HLS_reference(self):
        for prop,right in CHANNELS.items():
            with self.subTest(prop=prop):
                params={'blue_hue':70} if prop=='intensity' else {}
                frames,_,_=self.native(effect(prop,0,right,params=params))
                self.assertNotEqual(frames[0],frames[-1])
                for i,frame in enumerate(frames):self.compare(frame,oracle_frame(FRAME,{**params,prop:right*i/6}))

    def test_negative_channel_adjustments_and_intensity_fade_match_reference(self):
        for prop in CHANNELS:
            right=-120 if prop.endswith('_hue') else -.75
            if prop=='intensity':
                frames,_,_=self.native(effect(prop,1,0,params={'orange_hue':70}))
                for i,frame in enumerate(frames):self.compare(frame,oracle_frame(FRAME,{'orange_hue':70,'intensity':1-i/6}))
            else:
                frames,_,_=self.native(effect(prop,0,right))
                for i,frame in enumerate(frames):self.compare(frame,oracle_frame(FRAME,{prop:right*i/6}))

    def test_static_mixed_controls_match_reference_for_random_hidden_colors(self):
        rng=random.Random(7651);frame=bytes(rng.randrange(256) for _ in range(len(FRAME)))
        params={'red_hue':35,'orange_hue':-10,'yellow_saturation':-.5,'green_lightness':.3,
                'cyan_hue':30,'blue_saturation':.7,'purple_lightness':-.4,'magenta_hue':-45,'intensity':.65}
        frames,_,_=self.native({'type':'selective_hsl','parameters':params},frame=frame,count=1)
        self.compare(frames[0],oracle_frame(frame,params))

    def test_each_pure_center_selects_only_its_band(self):
        for band,hue in zip(NAMES,CENTERS):
            rgb=bytes(round(x*255) for x in colorsys.hls_to_rgb(hue/360,.5,1))
            frame=(rgb+b'\x7f')*(W*H)
            params={name+'_hue':40 for name in NAMES if name!=band}
            got=self.native({'type':'selective_hsl','parameters':params},frame=frame,count=1)[0][0]
            self.compare(got,oracle_frame(frame,params))
            # Orange/purple RGB quantization changes true hue slightly; the
            # independent oracle, not the authored center label, is truth.

    def test_achromatic_pixels_and_alpha_remain_exact_under_all_adjustments(self):
        frame=bytes(c for i in range(W*H) for c in (i%256,i%256,i%256,(0,127,255)[i%3]))
        params={name:value for name,value in CHANNELS.items()}
        self.assertEqual(self.native({'type':'selective_hsl','parameters':params},frame=frame,count=1)[0],[frame])

    def test_neutral_animated_kernel_is_exact_identity_including_hidden_RGB(self):
        self.assertEqual(self.native(effect(right=0),count=2)[0],[FRAME,FRAME])

    def test_six_easings_are_applied_on_display_samples(self):
        functions={'hold':lambda t:0,'linear':lambda t:t,'ease_in':lambda t:t*t,
                   'ease_out':lambda t:1-(1-t)**2,'ease_in_out':lambda t:2*t*t if t<.5 else 1-2*(1-t)**2,
                   'bezier':declared_bezier_reference}
        for easing,function in functions.items():
            frames,_,_=self.native(effect(easing=easing))
            for i,frame in enumerate(frames):self.compare(frame,oracle_frame(FRAME,{'red_hue':60*function(i/6)}))

    def test_bezier_overshoot_is_bounded_before_color_math(self):
        v=effect('blue_saturation',0,1,easing='bezier');v['keyframes'][0]['keyframes'][0]['control_points']=[1/3,5,2/3,5]
        frames,_,_=self.native(v)
        for frame in frames:self.assertEqual(frame[3::4],FRAME[3::4])
        self.compare(frames[3],oracle_frame(FRAME,{'blue_saturation':1}))

    def test_fractional_rate_nonzero_placement_and_frame_time(self):
        rate='30000/1001';start=float(Fraction(1001,30000))*3
        frames,_,_=self.native(effect(),rate=rate,start=start,count=7)
        for i,frame in enumerate(frames):self.compare(frame,oracle_frame(FRAME,{'red_hue':60*i/float(Fraction(rate))}))

    def test_constant_speed_reverse_ancestor_uses_complete_author_parameters(self):
        mapping={'source_start':0.,'source_end':2.,'timeline_start':0.,'timeline_duration':1.,
                 'speed':2.,'reverse':True,'segments':[],'curve_scale':1.}
        clip=sample(_nested_keyframe_clock={'maps':[mapping],'authored_start':0.})
        frames,_,_=self.native(effect(right=120,end=2*TPS),clip=clip)
        for i,frame in enumerate(frames):self.compare(frame,oracle_frame(FRAME,{'red_hue':120-120*i/6}))

    def test_two_sequential_instances_have_independent_curves_and_shared_budget(self):
        values=[effect(),effect('yellow_saturation',0,-.8)]
        frames,metadata,compiler=self.native(values)
        self.assertEqual(len(metadata),2);self.assertEqual(compiler.summary()['effect_instances_total'],2)
        for i,frame in enumerate(frames):
            first=oracle_frame(FRAME,{'red_hue':60*i/6})
            self.compare(frame,oracle_frame(first,{'yellow_saturation':-.8*i/6}))

    def test_multiple_threads_and_repeated_instances_have_no_expression_state_leak(self):
        v=effect(params={'blue_saturation':.6});one=self.native(v,threads=1)[0]
        self.assertEqual(one,self.native(v,threads=4)[0])
        self.assertEqual(one,self.native(v,threads=1)[0])


class SelectiveIntegrationTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory(prefix='hsl-integration-');self.addCleanup(temp.cleanup)
        self.workspace=Path(temp.name);self.root,self.project=create_project(self.workspace/'project')
        path=self.workspace/'source.png';Image.frombytes('RGBA',(W,H),FRAME).save(path)
        code,result=invoke('media','ingest','--project',self.root,'--input',path,'--asset-id','source');self.assertEqual(code,0,result)
        self.project=load_project(self.root)[1];self.project['settings']['canvas']={'width':W,'height':H,'background':'#182238'}
        self.project['settings']['timebase']={'ticks_per_second':TPS,'display_fps':{'num':6,'den':1}}
        self.seq=self.project['sequences'][0];self.seq['duration_tick']=TPS
        self.seq['tracks'][0]['clips']=[sample(asset_id='source',source_in_tick=0,source_out_tick=TPS,effects=[effect()])]
        save_project(self.root,self.project)

    def pixels(self,p=None):
        p=p or self.project;inputs,graph,meta,warnings=build_filter_graph(self.root,p,p['sequences'][0])
        script=self.root/'graph.ffgraph';script.write_text(graph,encoding='utf8')
        result=subprocess.run([ffmpeg_path(),'-v','error','-filter_complex_threads','1',*inputs,
            '-filter_complex_script',script,'-map','[vout]','-fps_mode','passthrough','-f','rawvideo','-pix_fmt','rgba','pipe:1',
            '-map','[aout]','-f','null','NUL'],capture_output=True,cwd=self.root,timeout=90)
        self.assertEqual(result.returncode,0,result.stderr.decode('utf8','replace'))
        return [result.stdout[i:i+len(FRAME)] for i in range(0,len(result.stdout),len(FRAME))],meta,warnings

    def test_real_CLI_render_manifest_records_effect_and_author_clock(self):
        code,result=invoke('render','--project',self.root,'--output',self.root/'renders/hsl.mkv');self.assertEqual(code,0,result)
        manifest=json.loads(Path(result['data']['manifest']).read_bytes())
        items=[x for x in manifest['inputs'] if x.get('kind')=='selective-hsl'];self.assertEqual(len(items),1)
        self.assertEqual(items[0]['animated_parameters'],['red_hue']);self.assertEqual(items[0]['sampled_frames'],6)

    def test_invalid_static_and_dynamic_compose_reject_atomically(self):
        before=(self.root/'project.json').read_bytes();request=self.workspace/'bad.json'
        cases=[{'type':'selective_hsl','parameters':{'bad':1}},effect(end=TPS+1),effect(right=10**400)]
        v=effect(easing='bezier');v['keyframes'][0]['keyframes'][0]['control_points']=[0,10**400];cases.append(v)
        for v in cases:
            request.write_text(json.dumps({'operations':[{'op':'update_clip','clip_id':'clip','patch':{'effects':[v]}}]}),encoding='utf8')
            code,result=invoke('timeline','compose','--project',self.root,'--input',request)
            self.assertEqual(code,2,result);self.assertEqual((self.root/'project.json').read_bytes(),before)

    def test_interval_huge_value_returns_structured_validation_errors(self):
        from ai_ad_editor.validator import validate_project
        before=(self.root/'project.json').read_bytes();value=copy.deepcopy(self.project)
        value['settings']['adjustments']=[{'id':'bad','start_tick':0,'duration_tick':TPS,'effects':[effect(right=10**400)]}]
        report=validate_project(self.root,value)
        self.assertIn('EFFECT_AUTOMATION_VALUE_INVALID',{x['code'] for x in report['errors']})
        self.assertIn('EFFECT_KEYFRAME_VALUE_INVALID',{x['code'] for x in report['errors']})
        self.assertEqual((self.root/'project.json').read_bytes(),before)

    def test_trim_and_split_preserve_complete_author_hsl_phase(self):
        self.seq['tracks'][0]['clips'][0]['effects']=[effect(easing='ease_in_out')];before=self.pixels()[0]
        trimmed,_=apply_operation(self.project,self.seq['id'],{'op':'trim_clip','clip_id':'clip','start_tick':15000,'end_tick':75000,'timeline_start_tick':0})
        trimmed['sequences'][0]['duration_tick']=60000;self.assertEqual(self.pixels(trimmed)[0],before[1:5])
        split,_=apply_operation(self.project,self.seq['id'],{'op':'split_clip','clip_id':'clip','at_tick':45000})
        self.assertEqual(self.pixels(split)[0],before)

    def test_complete_output_reverse_retimes_hsl_and_keeps_editability(self):
        before=self.pixels()[0]
        after,_=build_edit_plan(self.project,self.seq['id'],{'action':'retime','clip_ids':['clip'],'transform':{'reverse':True}})
        self.assertEqual(self.pixels(after)[0],list(reversed(before)))
        self.assertIn('selective_hsl',json.dumps(after))

    def test_interval_adjustment_only_changes_selected_frames(self):
        self.seq['tracks'][0]['clips'][0].pop('effects');before=self.pixels()[0]
        self.project['settings']['adjustments']=[{'id':'hsl','start_tick':15000,'duration_tick':60000,'effects':[effect(end=60000)]}]
        frames,meta,_=self.pixels();self.assertEqual(frames[:1],before[:1]);self.assertEqual(frames[5:],before[5:])
        self.assertEqual(frames[1],before[1]);self.assertNotEqual(frames[4],before[4])
        self.assertEqual(next(x for x in meta if x.get('kind')=='selective-hsl')['sampled_frames'],4)

    def test_independent_text_layer_changes_hue_without_changing_coverage(self):
        self.project['settings'].setdefault('output',{}).setdefault('video',{})['pixel_format']='yuva420p'
        self.seq['tracks'][0]['clips']=[]
        self.seq['tracks'].append({'id':'words','kind':'subtitle','order':2,'clips':[{
            'id':'title','timeline_start_tick':0,'duration_tick':TPS,'source_in_tick':0,'source_out_tick':TPS,
            'subtitle':{'text':'TEST','style':{'fontsize':10,'fontcolor':'#ff0000','box':False,'x':.1,'y':.2}},
            'effects':[effect()]}]})
        frames,meta,_=self.pixels();self.assertNotEqual(frames[0],frames[-1])
        self.assertEqual(frames[0][3::4],frames[-1][3::4]);self.assertIn(0,frames[0][3::4])
        self.assertEqual(len([x for x in meta if x.get('kind')=='selective-hsl']),1)

    def test_package_keeps_authored_bands_and_decoded_result(self):
        before=self.pixels()[0];package=self.workspace/'portable.zip'
        code,result=invoke('convert','export','--project',self.root,'--output',package,'--target-format','package');self.assertEqual(code,0,result)
        target=self.workspace/'imported';code,result=invoke('convert','import','--input',package,'--output',target);self.assertEqual(code,0,result)
        self.root=target;imported=load_project(target)[1]
        self.assertEqual(imported['sequences'][0]['tracks'][0]['clips'][0]['effects'],[effect()]);self.assertEqual(self.pixels(imported)[0],before)

    def test_fragment_transfers_band_keys_across_projects(self):
        before=self.pixels()[0];library=self.workspace/'library';request=self.workspace/'fragment.json'
        request.write_text(json.dumps({'id':'hsl','version':1,'name':'HSL','sequence_id':self.seq['id']}),encoding='utf8')
        code,result=invoke('fragment','save','--project',self.root,'--library',library,'--input',request);self.assertEqual(code,0,result)
        target,new=create_project(self.workspace/'target');new['settings']=copy.deepcopy(self.project['settings']);save_project(target,new)
        request.write_text(json.dumps({'id':'hsl','version':1,'sequence_id':new['sequences'][0]['id'],'track_id':new['sequences'][0]['tracks'][0]['id'],'at_tick':0}),encoding='utf8')
        code,result=invoke('fragment','apply','--project',target,'--library',library,'--input',request);self.assertEqual(code,0,result)
        self.root=target;self.assertEqual(self.pixels(load_project(target)[1])[0],before)


if __name__=='__main__':unittest.main()
