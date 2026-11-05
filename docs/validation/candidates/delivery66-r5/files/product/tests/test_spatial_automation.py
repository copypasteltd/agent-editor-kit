"""Native spatial/keying commands, static per-frame oracles and editable clocks."""
from __future__ import annotations
import copy
from fractions import Fraction
import json
import math
from pathlib import Path
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
from test_effect_automation import effect, sample_clip
from test_magnetic_reorder import invoke

TPS=90000
W,H=64,36
FRAME=bytes(c for y in range(H) for x in range(W) for c in (
    20+(x//4%2)*190,225-(y//4%2)*175,35+(x*3+y*5)%190,
    (0,127,255)[(x//8+y//8)%3]))
CHANNELS={
    'blur':{'radius':(0.,6.)},
    'color_contrast':{'red':(-.6,.6),'green':(-.6,.6),'blue':(-.6,.6),
        'red_weight':(0.,1.),'green_weight':(0.,1.),'blue_weight':(0.,1.),'preserve_luma':(0.,1.)},
    'lens_correction':{'k1':(-.4,.4),'k2':(-.4,.4),'cx':(.2,.8),'cy':(.2,.8)},
    'chroma_key':{'similarity':(.01,.5),'blend':(0.,.5)},
}
STATIC={'blur':{},'color_contrast':{'red':.4,'green':-.3,'blue':.2,
        'red_weight':.7,'green_weight':.5,'blue_weight':.9},
        'lens_correction':{'k1':.3,'k2':-.1},'chroma_key':{'color':'0x00ff00','similarity':.2}}


def value(kind='blur',prop='radius',left=0.,right=6.,**kwargs):
    out=effect(kind,prop,left,right,**kwargs);out['parameters']=copy.deepcopy(STATIC[kind]);return out


def reference(kind,prop,number):
    # Deliberately independent of renderer/SPECS/Curve and command text.
    params={**STATIC[kind],prop:number}
    if kind=='blur':return f"gblur=sigma={number:.6f}:sigmaV={number:.6f}"
    if kind=='color_contrast':
        return 'colorcontrast='+':'.join(f'{native}={params.get(author,0):.6f}' for author,native in (
            ('red','rc'),('green','gm'),('blue','by'),('red_weight','rcw'),
            ('green_weight','gmw'),('blue_weight','byw'),('preserve_luma','pl')))
    if kind=='lens_correction':
        return 'lenscorrection='+':'.join(f'{name}={params.get(name,.5 if name in {"cx","cy"} else 0):.6f}' for name in ('k1','k2','cx','cy'))
    return f"colorkey=color=0x00ff00:similarity={params.get('similarity',.1):.6f}:blend={params.get('blend',0):.6f}"


def declared_bezier_reference(t):
    # Existing author contract: 33 knots, a 20-step inverse at each knot,
    # then a serialized 8-decimal linear segment. This is intentionally not
    # the analytic cubic between knots. Do not call the product evaluator.
    def knot(n):
        lo,hi=0.,1.
        for _ in range(20):
            u=(lo+hi)/2
            x=(1-u)**2*u+2*(1-u)*u*u+u**3
            if x<n/32:lo=u
            else:hi=u
        u=(lo+hi)/2
        return 3*(1-u)*u*u+u**3
    j=min(31,int(t*32));a,b=knot(j),knot(j+1)
    return float(f'{a:.8f}')+float(f'{(b-a)*32:.8f}')*(t-j/32)


class SpatialCase(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory(prefix='spatial-automation-');self.addCleanup(temp.cleanup)
        self.root=Path(temp.name)

    def bind(self, v=None, *, compiler=None, clip=None, start=0):
        compiler=compiler or EffectAutomation(self.root,'6',TPS);metadata=[];warnings=[]
        chain=_effect_filters([v or value()],warnings,'clip',root=self.root,clip=clip or sample_clip(),
            clip_start=start,tps=TPS,automation=compiler,automation_meta=metadata)
        return ','.join(chain),metadata,compiler,warnings

    def native(self, chain, *, count=6, rate='6', start=0):
        graph=f'[0:v]setpts=PTS+{start}/TB,{chain},format=rgba[out]'
        result=subprocess.run([ffmpeg_path(),'-v','error','-filter_complex_threads','1',
            '-f','rawvideo','-pixel_format','rgba','-video_size',f'{W}x{H}','-framerate',rate,'-i','pipe:0',
            '-filter_complex',graph,'-map','[out]','-fps_mode','passthrough','-f','rawvideo','-pix_fmt','rgba','pipe:1'],
            input=FRAME*count,capture_output=True,cwd=self.root,timeout=60)
        self.assertEqual(result.returncode,0,result.stderr.decode('utf8','replace'))
        self.assertEqual(len(result.stdout),len(FRAME)*count)
        return [result.stdout[i:i+len(FRAME)] for i in range(0,len(result.stdout),len(FRAME))]

    def compare(self,v,oracle,*,count=6,rate='6',start=0):
        compiler=EffectAutomation(self.root,rate,TPS)
        chain,meta,_,warnings=self.bind(v,compiler=compiler,start=start)
        self.assertFalse(warnings,warnings)
        frames=self.native(chain,count=count,rate=rate,start=start)
        for i,frame in enumerate(frames):
            expected=self.native(oracle(i/float(Fraction(rate))),count=1)[0]
            if v['type']=='chroma_key':
                out=bytearray(expected)
                out[3::4]=bytes(round(a*b/255) for a,b in zip(FRAME[3::4],expected[3::4]))
                expected=bytes(out)
            self.assertLessEqual(max(abs(a-b) for a,b in zip(frame,expected)),1,(v['type'],i))
            self.assertEqual(frame[3::4],expected[3::4],(v['type'],i,'alpha'))
        return frames,meta


class SpatialContractTests(SpatialCase):
    def test_catalog_and_manifest_advertise_exactly_fourteen_new_channels(self):
        self.assertEqual(effect_catalog()['count'],51)
        self.assertEqual(effect_catalog()['catalog_version'],'0.11.0')
        for kind,props in CHANNELS.items():self.assertEqual(set(get_effect(kind)['keyframe_parameters']),set(props))
        manifest=build_capability_manifest()['capabilities']['effects']
        self.assertEqual(manifest['numeric_effect_automation']['numeric_channels'],34)
        self.assertEqual(len(manifest['numeric_effect_automation']['effects']),10)
        self.assertEqual(manifest['numeric_color_automation']['numeric_channels'],27)
        self.assertNotIn('color',get_effect('chroma_key')['keyframe_parameters'])

    def test_catalog_color_contrast_defaults_match_actual_neutral_static_mapping(self):
        for name in ('red','green','blue'):self.assertEqual(get_effect('color_contrast')['parameters'][name]['default'],0)
        chain=_effect_filters([{'type':'color_contrast'}],[],'clip')
        self.assertEqual(self.native(','.join(chain),count=1)[0],FRAME)

    def test_all_effect_aliases_property_prefixes_and_parameter_nesting_bind(self):
        for kind,aliases in {'blur':['blur','gblur','gaussian-blur'],
            'color_contrast':['colorcontrast','color_contrast'],
            'lens_correction':['lens_correction','lenscorrection'],
            'chroma_key':['chroma_key','chromakey','green_screen']}.items():
            prop=next(iter(CHANNELS[kind]));left,right=CHANNELS[kind][prop]
            for alias in aliases:
                for prefix in ('effect.','parameters.',alias.replace('-','_')+'.'):
                    with self.subTest(alias=alias,prefix=prefix):
                        v=value(kind,prop,left,right);v['type']=alias
                        v['parameters']['keyframes']=v.pop('keyframes');v['parameters']['keyframes'][0]['property']=prefix+prop
                        self.assertEqual(validate(v),[])
                        metadata=self.bind(v)[1]
                        self.assertEqual(len([x for x in metadata if x['kind']=='effect-automation']),1)
                        self.assertEqual(len([x for x in metadata if x['kind']=='colorkey-alpha-coverage']),int(kind=='chroma_key'))

    def test_duplicate_native_aliases_are_rejected(self):
        for kind,prop,alias in [('blur','radius','sigma'),('color_contrast','red','rc')]:
            v=value(kind,prop,*CHANNELS[kind][prop]);v['keyframes'].append(copy.deepcopy(v['keyframes'][0]))
            v['keyframes'][-1]['property']=alias
            self.assertIn('EFFECT_AUTOMATION_DUPLICATE_PROPERTY',{x['code'] for x in validate(v)})

    def test_nonfinite_boolean_string_huge_and_out_of_range_numbers_reject(self):
        for kind,prop,invalid in [('blur','radius',-1),('chroma_key','similarity',0),
            ('lens_correction','cx',1.01),('color_contrast','red',1.01)]:
            for number in (True,'0.5',math.inf,math.nan,10**400,invalid):
                with self.subTest(kind=kind,number=str(number)[:30]):
                    v=value(kind,prop,*CHANNELS[kind][prop]);v['keyframes'][0]['keyframes'][0]['value']=number
                    self.assertIn('EFFECT_AUTOMATION_VALUE_INVALID',{x['code'] for x in validate(v)})

    def test_static_color_plane_enum_and_injection_tracks_reject(self):
        for kind,prop in [('blur','planes'),('blur','sigmaV'),('chroma_key','color'),
            ('lens_correction','i'),('lens_correction','fc'),('color_contrast','red;evil')]:
            v=value(kind);v['keyframes'][0]['property']=prop
            self.assertEqual(validate(v)[0]['code'],'EFFECT_AUTOMATION_PROPERTY_UNSUPPORTED')

    def test_huge_bezier_control_rejects_with_structured_validation(self):
        v=value(easing='bezier');v['keyframes'][0]['keyframes'][0]['control_points']=[0,10**400]
        self.assertIn('EFFECT_AUTOMATION_BEZIER_INVALID',{x['code'] for x in validate(v)})

    def test_top_level_tracks_take_precedence_and_disabled_effect_has_no_commands(self):
        v=value();v['parameters']['keyframes']=[{'property':'bad','keyframes':[]}]
        self.assertEqual(len(self.bind(v)[1]),1)
        v['enabled']=False
        chain,meta,compiler,warnings=self.bind(v)
        self.assertEqual((chain,meta,compiler.targets,warnings),('',[],0,[]))

    def test_blur_requires_both_native_axes_before_writing_cache(self):
        with patch('ai_ad_editor.effect_automation.runtime_options',return_value=frozenset({'sigma'})):
            with self.assertRaises(AppError) as caught:self.bind()
        self.assertEqual(caught.exception.code,'EFFECT_AUTOMATION_NATIVE_COMMAND_UNAVAILABLE')
        self.assertFalse((self.root/'cache').exists())

    def test_four_new_families_share_recursive_budget_with_existing_color(self):
        compiler=EffectAutomation(self.root,'6',TPS)
        for kind,props in CHANNELS.items():
            prop=next(iter(props));self.bind(value(kind,prop,*props[prop]),compiler=compiler)
        with patch('ai_ad_editor.effect_automation.MAX_SAMPLES',24):
            with self.assertRaises(AppError) as caught:self.bind(effect(),compiler=compiler)
        self.assertEqual(caught.exception.code,'EFFECT_AUTOMATION_BUDGET')
        self.assertEqual(compiler.summary()['targets'],4)

    def test_corrupt_derived_command_file_is_retained_and_rejected(self):
        _,meta,_,_=self.bind();path=self.root/meta[0]['command_file'];path.write_bytes(b'bad')
        with self.assertRaises(AppError) as caught:self.bind()
        self.assertEqual(caught.exception.code,'EFFECT_AUTOMATION_CACHE_HASH_MISMATCH')
        self.assertEqual(path.read_bytes(),b'bad')

    def test_static_key_compositor_budget_is_shared_across_recursive_calls(self):
        compiler=EffectAutomation(self.root,'6',TPS)
        with patch('ai_ad_editor.effect_automation.MAX_TARGETS',1):
            _effect_filters([{'type':'chroma_key'}],[],'a',automation=compiler)
            with self.assertRaises(AppError) as caught:
                _effect_filters([{'type':'chroma_key'}],[],'b',automation=compiler)
        self.assertEqual(caught.exception.code,'EFFECT_AUTOMATION_BUDGET')


class SpatialNativeTests(SpatialCase):
    def test_static_and_dynamic_keys_use_distinct_root_coverage_labels(self):
        compiler=EffectAutomation(self.root,'6',TPS);meta=[]
        chain=_effect_filters([{'type':'chroma_key'},{'type':'chroma_key'},
            value('chroma_key','similarity',.01,.5)],[],'stack',clip=sample_clip(),
            automation=compiler,automation_meta=meta)
        nodes=[x for x in meta if x['kind']=='colorkey-alpha-coverage']
        self.assertEqual(len(nodes),3);self.assertEqual(len({x['target'] for x in nodes}),3)
        for frame in self.native(','.join(chain)):
            self.assertTrue(all(a<=b for a,b in zip(frame[3::4],FRAME[3::4])))

    def test_keying_never_reveals_transparent_pixels_and_preserves_partial_coverage(self):
        frames=self.native(self.bind(value('chroma_key','similarity',.01,.5))[0])
        for i,frame in enumerate(frames):
            native_key=self.native(reference('chroma_key','similarity',.01+.49*i/6),count=1)[0]
            expected=bytes(round(a*b/255) for a,b in zip(FRAME[3::4],native_key[3::4]))
            self.assertEqual(frame[3::4],expected,i)
            self.assertTrue(all(a<=b for a,b in zip(frame[3::4],FRAME[3::4])),i)

    def test_static_keying_preserves_original_alpha_without_a_runtime_compiler(self):
        chain=_effect_filters([{'type':'chroma_key','similarity':.00001}],[],'static')
        self.assertEqual(self.native(','.join(chain),count=1)[0],FRAME)

    def test_all_fourteen_channels_match_independent_static_native_frame_oracles(self):
        for kind,props in CHANNELS.items():
            for prop,(left,right) in props.items():
                with self.subTest(kind=kind,prop=prop):
                    frames,_=self.compare(value(kind,prop,left,right),
                        lambda t:reference(kind,prop,left+(right-left)*t))
                    self.assertGreater(len(set(frames)),1,(kind,prop,'control had no actual effect'))

    def test_six_interpolation_types_change_both_blur_axes(self):
        for easing,fn in [('hold',lambda t:0),('linear',lambda t:t),('ease_in',lambda t:t*t),
            ('ease_out',lambda t:2*t-t*t),('ease_in_out',lambda t:2*t*t if t<.5 else 1-2*(1-t)**2),
            ('bezier',declared_bezier_reference)]:
            with self.subTest(easing=easing):
                v=value(easing=easing)
                if easing=='bezier':v['keyframes'][0]['keyframes'][0]['control_points']=[1/3,0,2/3,1]
                self.compare(v,lambda t:reference('blur','radius',6*fn(t)))

    def test_zero_blur_is_byte_exact_identity_including_transparent_RGB(self):
        v=value(left=0,right=0)
        self.assertEqual(self.native(self.bind(v)[0]),[FRAME]*6)
        static=_effect_filters([{'type':'blur','radius':0}],[],'clip')
        self.assertEqual(self.native(','.join(static),count=1)[0],FRAME)

    def test_blur_animates_alpha_as_well_as_RGB(self):
        frames,_=self.compare(value(),lambda t:reference('blur','radius',6*t))
        self.assertEqual(frames[0],FRAME)
        self.assertNotEqual(frames[-1][3::4],FRAME[3::4])

    def test_fractional_display_rate_and_nonzero_placement_use_local_author_time(self):
        v=value(end=TPS)
        # The shifted timestamps must not shift the local parameter phase.
        self.compare(v,lambda t:reference('blur','radius',6*t),count=6,rate='6000/1001',start=1001/6000)

    def test_two_distinct_instances_cannot_cross_modify(self):
        compiler=EffectAutomation(self.root,'6',TPS)
        a=self.bind(value(),compiler=compiler);b=self.bind(value('lens_correction','k1',-.4,.4),compiler=compiler)
        self.assertNotEqual(a[1][0]['target'],b[1][0]['target'])
        frames=self.native(a[0]+','+b[0])
        for i,frame in enumerate(frames):
            expected=self.native(reference('blur','radius',i)+','+reference('lens_correction','k1',-.4+.8*i/6),count=1)[0]
            self.assertEqual(frame,expected)

    def test_constant_speed_reverse_ancestor_uses_original_author_phase(self):
        v=value();v['keyframes'][0]['keyframes'][-1]['at_tick']=2*TPS
        mapping={'source_start':0.,'source_end':2.,'timeline_start':0.,'timeline_duration':1.,
                 'speed':2.,'reverse':True,'segments':[],'curve_scale':1.}
        clip=sample_clip(_nested_keyframe_clock={'maps':[mapping],'authored_start':0.})
        chain=self.bind(v,clip=clip)[0];frames=self.native(chain)
        for i,frame in enumerate(frames):self.assertEqual(frame,self.native(reference('blur','radius',6-i),count=1)[0])


class SpatialIntegrationTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory(prefix='spatial-integration-');self.addCleanup(temp.cleanup)
        self.workspace=Path(temp.name);self.root,self.project=create_project(self.workspace/'project')
        path=self.workspace/'source.png';Image.frombytes('RGBA',(W,H),FRAME).convert('RGB').save(path)
        code,result=invoke('media','ingest','--project',self.root,'--input',path,'--asset-id','source')
        self.assertEqual(code,0,result);self.project=load_project(self.root)[1]
        self.project['settings']['canvas']={'width':W,'height':H,'background':'#182238'}
        self.project['settings']['timebase']={'ticks_per_second':TPS,'display_fps':{'num':6,'den':1}}
        self.seq=self.project['sequences'][0];self.seq['duration_tick']=TPS
        self.seq['tracks'][0]['clips']=[sample_clip(asset_id='source',source_in_tick=0,source_out_tick=TPS,effects=[value()])]
        save_project(self.root,self.project)

    def pixels(self,p=None):
        p=p or self.project;inputs,graph,meta,warnings=build_filter_graph(self.root,p,p['sequences'][0])
        script=self.root/'graph.ffgraph';script.write_text(graph,encoding='utf8')
        result=subprocess.run([ffmpeg_path(),'-v','error','-filter_complex_threads','1',*inputs,
            '-filter_complex_script',str(script),'-map','[vout]','-fps_mode','passthrough','-f','rawvideo','-pix_fmt','rgba','pipe:1',
            '-map','[aout]','-f','null','NUL'],capture_output=True,cwd=self.root,timeout=90)
        self.assertEqual(result.returncode,0,result.stderr.decode('utf8','replace'));self.assertEqual(len(result.stdout)%len(FRAME),0)
        return [result.stdout[i:i+len(FRAME)] for i in range(0,len(result.stdout),len(FRAME))],meta,warnings

    def stack(self):
        return [value(kind,prop,*props[prop]) for kind,props in CHANNELS.items() for prop in [next(iter(props))]]

    def test_real_CLI_persists_four_native_controls_in_render_manifest(self):
        self.seq['tracks'][0]['clips'][0]['effects']=self.stack();save_project(self.root,self.project)
        output=self.root/'renders/stack.mkv';code,result=invoke('render','--project',self.root,'--output',output)
        self.assertEqual(code,0,result);manifest=json.loads(Path(result['data']['manifest']).read_bytes())
        controls=[x for x in manifest['inputs'] if x.get('kind')=='effect-automation']
        self.assertEqual({x['effect'] for x in controls},set(CHANNELS));self.assertEqual(len({x['target'] for x in controls}),4)

    def test_invalid_dynamic_color_and_tick_compose_are_atomic(self):
        before=(self.root/'project.json').read_bytes();path=self.workspace/'invalid.json'
        for prop,end in [('color',TPS),('similarity',TPS+1)]:
            v=value('chroma_key','similarity',.01,.5,end=end);v['keyframes'][0]['property']=prop
            path.write_text(json.dumps({'operations':[{'op':'update_clip','clip_id':'clip','patch':{'effects':[v]}}]}),encoding='utf8')
            code,result=invoke('timeline','compose','--project',self.root,'--input',path)
            self.assertEqual(code,2,result);self.assertEqual((self.root/'project.json').read_bytes(),before)

    def test_trim_and_split_retain_complete_nonlinear_effect_phase(self):
        self.seq['tracks'][0]['clips'][0]['effects']=[value(easing='ease_in_out')];before=self.pixels()[0]
        trimmed,_=apply_operation(self.project,self.seq['id'],{'op':'trim_clip','clip_id':'clip','start_tick':15000,'end_tick':75000,'timeline_start_tick':0})
        trimmed['sequences'][0]['duration_tick']=60000;self.assertEqual(self.pixels(trimmed)[0],before[1:5])
        split,_=apply_operation(self.project,self.seq['id'],{'op':'split_clip','clip_id':'clip','at_tick':45000})
        self.assertEqual(self.pixels(split)[0],before)

    def test_relative_reverse_retimes_the_complete_authored_effect(self):
        before=self.pixels()[0]
        out,_=build_edit_plan(self.project,self.seq['id'],{'action':'retime','clip_ids':['clip'],'transform':{'reverse':True}})
        self.assertEqual(self.pixels(out)[0],list(reversed(before)))

    def test_interval_adjustment_keeps_unselected_frames_and_uses_local_phase(self):
        self.seq['tracks'][0]['clips'][0].pop('effects');before=self.pixels()[0]
        self.project['settings']['adjustments']=[{'id':'soft','start_tick':15000,'duration_tick':60000,
            'effects':[value(end=60000)]}]
        frames,meta,_=self.pixels();self.assertEqual(frames[:1],before[:1]);self.assertEqual(frames[5:],before[5:])
        self.assertEqual(frames[1],before[1]);self.assertNotEqual(frames[4],before[4])
        self.assertEqual(next(x for x in meta if x.get('kind')=='effect-automation')['sampled_frames'],4)

    def test_package_roundtrip_keeps_all_author_parameters_and_decoded_pixels(self):
        self.seq['tracks'][0]['clips'][0]['effects']=self.stack();save_project(self.root,self.project)
        before=self.pixels()[0];package=self.workspace/'portable.zip'
        code,result=invoke('convert','export','--project',self.root,'--output',package,'--target-format','package');self.assertEqual(code,0,result)
        target=self.workspace/'imported';code,result=invoke('convert','import','--input',package,'--output',target);self.assertEqual(code,0,result)
        self.root=target;imported=load_project(target)[1]
        self.assertEqual(imported['sequences'][0]['tracks'][0]['clips'][0]['effects'],self.stack())
        self.assertEqual(self.pixels(imported)[0],before)

    def test_fragment_transfer_rebuilds_commands_without_source_cache(self):
        self.seq['tracks'][0]['clips'][0]['effects']=self.stack();save_project(self.root,self.project);before=self.pixels()[0]
        library=self.workspace/'library';q=self.workspace/'fragment.json'
        q.write_text(json.dumps({'id':'soft-key','version':1,'name':'Animated effects','sequence_id':self.seq['id']}),encoding='utf8')
        code,result=invoke('fragment','save','--project',self.root,'--library',library,'--input',q);self.assertEqual(code,0,result)
        target,new=create_project(self.workspace/'target');new['settings']=copy.deepcopy(self.project['settings']);save_project(target,new)
        q.write_text(json.dumps({'id':'soft-key','version':1,'sequence_id':new['sequences'][0]['id'],
            'track_id':new['sequences'][0]['tracks'][0]['id'],'at_tick':0}),encoding='utf8')
        code,result=invoke('fragment','apply','--project',target,'--library',library,'--input',q);self.assertEqual(code,0,result)
        self.root=target;self.assertEqual(self.pixels(load_project(target)[1])[0],before)


if __name__=='__main__':unittest.main()
