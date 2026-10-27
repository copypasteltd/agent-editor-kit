"""Authored child pixels and independently mapped nested transition clocks."""
from __future__ import annotations

import copy
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import unittest
from unittest.mock import patch

import numpy as np

import test_source_transitions as base_tests
import test_audio_stretch as audio_tests
from ai_ad_editor.errors import AppError
from ai_ad_editor.inline_sequences import graph_namespace, transition_descendants, budget
from ai_ad_editor.project import save_project
from ai_ad_editor.render import build_filter_graph
from ai_ad_editor.source_transitions import build_plan

TPS, FPS, W, H, SR = base_tests.TPS,base_tests.FPS,base_tests.W,base_tests.H,base_tests.SR


class InlineSequencePlanningTests(unittest.TestCase):
    def test_namespace_preserves_quoted_text_and_escaped_brackets(self):
        graph = "[0:v]drawtext=text='[42:v] and [keep]':x=2[v];[v]null[video];[1:a]anull[aout]"
        self.assertEqual(graph_namespace(graph,'child_',3),
                         "[3:v]drawtext=text='[42:v] and [keep]':x=2[child_v];[child_v]null[child_video];[4:a]anull[child_aout]")
        self.assertEqual(graph_namespace(r"[0:v]drawtext=text=\[literal\][v]",'q_',2),
                         r"[2:v]drawtext=text=\[literal\][q_v]")

    def test_reachable_transition_branches_and_cycles(self):
        p=base_tests.fixture()
        p['sequences'][0]['source_transitions']=[{'id':'sentinel'}]
        p['sequences'].append({'id':'parent','tracks':[{'clips':[{'sequence_id':'seq'}]}]})
        reachable,bearing=transition_descendants(p,'parent')
        self.assertEqual(reachable,{'parent','seq'})
        self.assertTrue(bearing['parent'])
        p['sequences'][0]['tracks'][0]['clips'].append({'sequence_id':'parent'})
        with self.assertRaises(AppError) as c:transition_descendants(p,'parent')
        self.assertEqual(c.exception.code,'SEQUENCE_CYCLE')

    def test_surface_and_child_projection_charges_are_cumulative(self):
        child={'kind':'sequence-inline-surface','estimated_surface_working_bytes':30,'inputs':[
            {'kind':'sequence-projection-budget','estimated_working_bytes':50}]}
        root={'estimated_working_bytes':40}
        self.assertEqual(budget([child],root,{'max_working_bytes':120})['estimated_working_bytes'],120)
        with self.assertRaises(AppError) as c:budget([child],root,{'max_working_bytes':119})
        self.assertEqual(c.exception.code,'SEQUENCE_INLINE_BUDGET_EXCEEDED')

    def test_frozen_ancestor_keeps_child_transition_authorship(self):
        p=base_tests.fixture()
        parent={'id':'parent','tracks':[{'id':'pv','clips':[{'id':'pc','sequence_id':'seq',
            'duration_tick':7*TPS,'source_in_tick':0,'source_out_tick':6*TPS,
            'freeze':{'at_tick':2*TPS,'duration_tick':TPS,'audio_mode':'silence'}}]}]}
        p['sequences'].append(parent)
        changed,plan=build_plan(p,'seq',base_tests.add())
        self.assertEqual(changed['sequences'][1],parent)
        self.assertEqual(len(plan['render_plan']['transitions']),1)


class NestedTransitionCliTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        raw_source = base_tests.raw_source
        # A one-frame phase error must exceed pixel rounding tolerances.
        with patch.object(base_tests, 'raw_source', side_effect=lambda p: raw_source(p,step=47)):
            base_tests.SourceTransitionCliTests.setUpClass.__func__(cls)
    @classmethod
    def tearDownClass(cls):base_tests.SourceTransitionCliTests.tearDownClass.__func__(cls)
    setUp=base_tests.SourceTransitionCliTests.setUp
    p=base_tests.SourceTransitionCliTests.p
    render=base_tests.SourceTransitionCliTests.render

    def nested(self, *, source_in=TPS, source_out=5*TPS, duration=4*TPS, **fields):
        p=self.p()
        child=copy.deepcopy(p['sequences'][0]);child['id']='child'
        p['sequences']=[child]
        p,_=build_plan(p,'child',base_tests.add())
        p,_=build_plan(p,'child',base_tests.add(id='tr_bc',from_clip_id='b',to_clip_id='c'))
        parent={'id':self.sequence_id,'name':'parent','duration_tick':duration,'tracks':[
            {'id':'parent_video','kind':'video','order':0,'clips':[
                {'id':'parent_clip','sequence_id':'child','timeline_start_tick':0,'duration_tick':duration,
                 'source_in_tick':source_in,'source_out_tick':source_out,**fields}]}]}
        p['sequences'].insert(0,parent)
        save_project(self.root,p)
        return p

    def reference(self):
        source=self.source_rgb
        out=np.concatenate([source[20:40]]*3).astype(float)
        for start in (15,35):
            for k in range(start,start+10):
                local=k-(0 if start==15 else 20)
                w=(k-start)/10
                out[k]=source[20+local]*(1-w)+source[local]*w
        return out

    def assert_pixels(self,actual,reference,tolerance=3):
        self.assertEqual(actual.shape,reference.shape)
        self.assertLessEqual(float(np.abs(actual.astype(float)-reference).max()),tolerance)

    def test_trimmed_parent_preserves_two_authored_transition_windows(self):
        p=self.nested();before=copy.deepcopy(p)
        rgb,pcm,result=self.render('nested-trim')
        self.assert_pixels(rgb,self.reference()[10:50])
        self.assertEqual(len(pcm),4*SR)
        after=self.p()
        for field in ('sequences','assets','settings'):
            self.assertEqual(before[field],after[field])
        manifest=json.loads(Path(result['data']['manifest']).read_text(encoding='utf-8')) if 'data' in result else None
        self.assertIsNotNone(manifest)
        surface=next(v for v in manifest['inputs'] if v.get('kind')=='sequence-inline-surface')
        self.assertEqual(surface['sequence_id'],'child')
        self.assertEqual(surface['intermediate_files'],0)

    def test_trim_entering_the_middle_of_a_transition_keeps_original_progress(self):
        self.nested(source_in=189000,source_out=369000,duration=2*TPS)
        rgb,_,_=self.render('partial-window')
        self.assert_pixels(rgb,self.reference()[21:41])

    def test_parent_reverse_reverses_completed_transition_pixels(self):
        self.nested(reverse=True)
        rgb,_,_=self.render('nested-reverse')
        self.assert_pixels(rgb,self.reference()[10:50][::-1])

    def test_grandparent_reverse_keeps_nested_surface_scope_and_child_clock(self):
        p=self.nested();p['sequences'][0]['id']='middle'
        outer={'id':self.sequence_id,'name':'outer','duration_tick':4*TPS,'tracks':[
            {'id':'outer_video','kind':'video','order':0,'clips':[
                {'id':'outer_clip','sequence_id':'middle','timeline_start_tick':0,'duration_tick':4*TPS,
                 'source_in_tick':0,'source_out_tick':4*TPS,'reverse':True}]}]}
        p['sequences'].insert(0,outer);save_project(self.root,p)
        rgb,_,_=self.render('grandparent-reverse')
        self.assert_pixels(rgb,self.reference()[10:50][::-1])

    def test_parent_opacity_uses_parent_clock_after_curve_composition(self):
        p=self.nested(speed_curve=[{'at_tick':0,'speed':1},{'at_tick':4*TPS,'speed':3}],keyframes=[
            {'property':'transform.opacity','keyframes':[{'at_tick':0,'value':.4,'interpolation':'linear'},
                                                       {'at_tick':4*TPS,'value':.8,'interpolation':'linear'}]}])
        rgb,_,_=self.render('parent-opacity')
        times=np.arange(40)/FPS
        selected=np.floor((1+(np.exp(math.log(3)*times/4)-1)/.5)*FPS+1e-6).astype(int)
        expected=self.reference()[selected]*(.4+times[:,None,None,None]*.1)
        self.assert_pixels(rgb,expected,tolerance=4)

    def test_child_transparency_survives_native_surface_before_parent_background(self):
        p=self.nested()
        for c in p['sequences'][1]['tracks'][0]['clips']:c['transform']={'opacity':.5}
        p['sequences'][0]['tracks'][0]['order']=1
        p['sequences'][0]['tracks'].insert(0,{'id':'background','kind':'video','order':0,'clips':[
            {'id':'background_clip','asset_id':'source','timeline_start_tick':0,'duration_tick':4*TPS,
             'source_in_tick':0,'source_out_tick':4*TPS}]})
        save_project(self.root,p)
        rgb,_,_=self.render('child-alpha')
        expected=self.source_rgb[:40]*.5+self.reference()[10:50]*.5
        self.assert_pixels(rgb,expected,tolerance=4)

    def test_forward_audio_uses_independent_source_windows_and_authored_envelopes(self):
        self.nested()
        _,pcm,_=self.render('nested-pcm')
        reference=np.concatenate([self.source_pcm[2*SR:4*SR]]*3).copy()
        for start in (int(1.5*SR),int(3.5*SR)):
            w=np.arange(SR)/SR
            reference[start:start+SR]=self.source_pcm[int(3.5*SR):int(4.5*SR)]*(1-w[:,None])+self.source_pcm[int(1.5*SR):int(2.5*SR)]*w[:,None]
        self.assertLessEqual(float(np.abs(pcm-reference[SR:5*SR]).max()),3e-7)

    def test_reverse_audio_envelopes_follow_original_continuous_child_clock(self):
        self.nested(reverse=True)
        _,pcm,_=self.render('nested-reverse-pcm')
        expected=np.zeros((4*SR,2),dtype=float)
        # Exact reversed source sample selections. Envelopes use authored
        # presentation time (right boundary at the first reversed sample).
        for child_a,child_b,source_a,source_b,which in ((1.,2.5,3.,4.5,'a'),(1.5,4.5,1.5,4.5,'b'),(3.5,5.,1.5,3.,'c')):
            begin=round((5-child_b)*SR);end=round((5-child_a)*SR)
            child_clock=5-np.arange(begin,end)/SR
            gain=np.ones(end-begin)
            if which in ('a','b'):
                cut=1.5 if which=='a' else 3.5
                gain*=1-np.clip(child_clock-cut,0,1)
            if which in ('b','c'):
                cut=1.5 if which=='b' else 3.5
                gain*=np.clip(child_clock-cut,0,1)
            expected[begin:end]+=self.source_pcm[round(source_a*SR):round(source_b*SR)][::-1]*gain[:,None]
        self.assertLessEqual(float(np.abs(pcm-expected).max()),3e-7)

    def test_nested_surface_preserves_registered_r3_sources_and_audio_bus(self):
        binary=os.environ.get('AI_AD_EDITOR_TEST_RUBBERBAND') or shutil.which('rubberband')
        if not binary:self.skipTest('Requires an explicitly supplied existing native Rubber Band executable')
        self.binary=Path(binary).resolve();self.license=self.binary.with_name('COPYING.txt');self.dll=self.binary.with_name('sndfile.dll')
        p=self.nested(duration=2*TPS,speed=2)
        p['settings']['audio_stretch']=audio_tests.OfflineAudioStretchTests.config(self)
        save_project(self.root,p)
        rgb,pcm,result=self.render('nested-r3')
        self.assert_pixels(rgb,self.reference()[10:50:2])
        self.assertEqual(len(pcm),2*SR);self.assertTrue(np.isfinite(pcm).all())
        manifest=json.loads(Path(result['data']['manifest']).read_text(encoding='utf-8'))
        jobs=[item['audio_stretch'] for item in manifest['inputs'] if item.get('audio_stretch')]
        self.assertEqual(len(jobs),3)
        self.assertTrue(all(Path(j['source']).is_file() and '__inline' not in j['source'] for j in jobs))

    def test_parent_double_speed_selects_completed_child_frames(self):
        self.nested(duration=2*TPS,speed=2)
        rgb,_,_=self.render('nested-double')
        self.assert_pixels(rgb,self.reference()[10:50:2])

    def test_parent_nonlinear_curve_retimes_the_composite_not_crossfade_endpoints(self):
        self.nested(speed_curve=[{'at_tick':0,'speed':1},{'at_tick':4*TPS,'speed':3}])
        rgb,_,_=self.render('nested-curve')
        times=np.arange(40)/FPS
        source=1+(np.exp(math.log(3)*times/4)-1)/.5
        selected=np.floor(source*FPS+1e-6).astype(int)
        self.assert_pixels(rgb,self.reference()[selected])

    def test_same_child_twice_uses_independent_frame_windows(self):
        p=self.nested(source_in=0,source_out=6*TPS,duration=6*TPS)
        parent=p['sequences'][0]
        second=copy.deepcopy(parent['tracks'][0]['clips'][0]);second.update(id='again',timeline_start_tick=6*TPS)
        parent['tracks'][0]['clips'].append(second);parent['duration_tick']=12*TPS
        save_project(self.root,p)
        rgb,_,_=self.render('two-instances')
        self.assert_pixels(rgb,np.concatenate([self.reference()]*2))

    def test_graph_planning_does_not_run_processes_or_modify_author_data(self):
        p=self.nested();frozen=copy.deepcopy(p)
        with patch('subprocess.Popen',side_effect=AssertionError('planner must not execute')):
            inputs,graph,metadata,warnings=build_filter_graph(self.root,p,p['sequences'][0])
        self.assertEqual(p,frozen)
        self.assertIn('sequence-inline-surface',[v.get('kind') for v in metadata])
        self.assertEqual(inputs.count('-i'),6)

    def test_internal_surface_id_does_not_collide_with_authored_ancestor_sequence(self):
        p=self.nested()
        p['sequences'][0]['id']='child__surface'
        inputs,graph,metadata,warnings=build_filter_graph(self.root,p,p['sequences'][0])
        self.assertIn('sequence-inline-surface',[v.get('kind') for v in metadata])
        audio=[v['clip_id'] for v in metadata if v.get('kind')=='audio']
        video=[v['clip_id'] for v in metadata if v.get('kind')=='video']
        self.assertFalse(set(audio)&set(video))

    def test_all_transition_types_keep_child_pixels_under_reverse_nonlinear_parent(self):
        for kind in ('dissolve','crossfade','dip_black','dip_white','wipe_left','wipe_right','wipe_up','wipe_down',
                     'slide_left','slide_right','slide_up','slide_down'):
            with self.subTest(kind=kind):
                save_project(self.root,copy.deepcopy(self.base_project))
                p=self.nested(reverse=True,speed_curve=[{'at_tick':0,'speed':1},{'at_tick':4*TPS,'speed':3}])
                for declaration in p['sequences'][1]['source_transitions']:declaration['type']=kind
                save_project(self.root,p)
                output=self.root/'renders'/('child-'+kind+'.mkv')
                code,result=base_tests.invoke('render','--project',str(self.root),'--sequence-id','child',
                    '--output',str(output),'--container','mkv','--crf','0','--pixel-format','yuv444p','--audio-codec','pcm_f32le')
                self.assertEqual(code,0,result)
                raw=subprocess.check_output(['ffmpeg','-v','error','-i',str(output),'-an','-pix_fmt','rgb24','-f','rawvideo','pipe:1'])
                child=np.frombuffer(raw,np.uint8).reshape(-1,H,W,3)
                rgb,_,_=self.render('parent-'+kind)
                times=np.arange(40)/FPS
                source=1+(np.exp(math.log(3)*(4-times)/4)-1)/.5
                selected=np.ceil(source*FPS-1e-6).astype(int)-1
                self.assert_pixels(rgb,child[selected])

    def test_child_render_warnings_remain_visible_with_their_sequence_scope(self):
        p=self.nested()
        p['sequences'][1]['tracks'][0]['clips'][0]['keyframes']=[
            {'property':'transform.opacity','keyframes':[{'at_tick':0,'value':.5,'interpolation':'bezier'},
                                                       {'at_tick':TPS,'value':1}]}]
        _,_,_,warnings=build_filter_graph(self.root,p,p['sequences'][0])
        self.assertTrue(any(w.get('feature')=='bezier_keyframe' and w.get('inline_sequence_path')==['child']
                            for w in warnings),warnings)

    def test_combined_surface_budget_rejects_before_render_job(self):
        p=self.nested();p['settings']['sequence_sampling']={'max_working_bytes':225000}
        save_project(self.root,p)
        code,failure=base_tests.invoke('render','--project',str(self.root),'--dry-run')
        self.assertEqual(code,2,failure)
        self.assertEqual(failure['errors'][0]['code'],'SEQUENCE_INLINE_BUDGET_EXCEEDED')


if __name__=='__main__':unittest.main()
