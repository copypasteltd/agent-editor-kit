"""Complete output time maps, linked partial windows and atomic real CLI edits."""
from __future__ import annotations
import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image

from ai_ad_editor.clip_windows import slice_clip
from ai_ad_editor.edit_planner import build_edit_plan
from ai_ad_editor.errors import AppError
from ai_ad_editor.magnetic_mode import validate as validate_magnetic
from ai_ad_editor.project import create_project, save_project
from ai_ad_editor.retime_transform import Transform
from test_magnetic_reorder import clip, track, project, positions, invoke


def state(*extra):
    p=project();p['settings']['canvas']={'width':64,'height':32,'background':'#000000'}
    s=p['sequences'][0];s['duration_tick']=40;s['editing']={'magnetic':True}
    s['tracks'].extend(extra);return p


def request(transform=None,ids=('b',),**fields):
    return {'action':'retime','clip_ids':list(ids),'transform':transform or {'speed':2},**fields}


def root(p):return p['sequences'][0]
def at(p,cid):return next(c for t in root(p)['tracks'] for c in t['clips'] if c['id']==cid)


class CompleteOutputRetimeTests(unittest.TestCase):
    def plan(self,p,q):
        old=copy.deepcopy(p);answer=build_edit_plan(p,'seq',q);self.assertEqual(p,old);return answer

    def rejects(self,p,q,code):
        old=copy.deepcopy(p)
        with self.assertRaises(AppError) as caught:build_edit_plan(p,'seq',q)
        self.assertEqual(caught.exception.code,code);self.assertEqual(p,old)

    def test_main_fast_keeps_source_graph_and_packs_following_shots(self):
        out,plan=self.plan(state(),request())
        self.assertEqual([(at(out,c)['timeline_start_tick'],at(out,c)['duration_tick']) for c in 'abcd'],[(0,10),(10,5),(15,10),(25,10)])
        self.assertEqual(root(out)['duration_tick'],35);validate_magnetic(root(out))
        self.assertEqual(len(plan['created_sequences']),1)
        child=plan['created_sequences'][0]['tracks'][0]['clips'][0]
        self.assertEqual((child['source_in_tick'],child['source_out_tick']),(10,20))
        self.assertEqual(child['presentation_window']['authored_duration_tick'],10)

    def test_slow_main_pushes_tail_and_preserves_declared_blank_tail(self):
        p=state();root(p)['duration_tick']=60
        out,_=self.plan(p,request({'speed':.5}))
        self.assertEqual((at(out,'c')['timeline_start_tick'],root(out)['duration_tick']),(30,70))

    def test_multiple_main_hosts_use_original_domains_right_to_left(self):
        out,plan=self.plan(state(),request(ids=('b','d')))
        self.assertEqual([p['host_clip_id'] for p in plan['steps']],['d','b'])
        self.assertEqual([(at(out,c)['timeline_start_tick'],at(out,c)['duration_tick']) for c in 'abcd'],[(0,10),(10,5),(15,10),(25,5)])

    def test_linked_main_hosts_expand_without_double_processing(self):
        p=state();at(p,'b')['link_id']=at(p,'d')['link_id']='group'
        out,plan=self.plan(p,request());self.assertEqual(plan['expanded_clip_ids'],['b','d'])
        self.assertEqual(root(out)['duration_tick'],30)

    def test_whole_linked_audio_shares_same_host_domain(self):
        p=state(track('sound',[clip('voice',10,20,link_id='pair')],'audio',1));at(p,'b')['link_id']='pair'
        out,plan=self.plan(p,request());voice=at(out,'voice')
        self.assertEqual((voice['timeline_start_tick'],voice['duration_tick'],voice['speed']),(10,5,2))
        self.assertEqual(voice['source_in_tick'],10)
        self.assertEqual(len(plan['steps'][0]['retimed_members']),2)

    def test_partial_linked_audio_preserves_before_and_after_clock(self):
        p=state(track('sound',[clip('bed',0,40,link_id='pair')],'audio',1));at(p,'b')['link_id']='pair'
        out,_=self.plan(p,request());clips=root(out)['tracks'][1]['clips']
        self.assertEqual(sorted((c['timeline_start_tick'],c['duration_tick']) for c in clips),[(0,10),(10,5),(15,20)])
        after=next(c for c in clips if c['timeline_start_tick']==15)
        self.assertEqual(after['presentation_window']['offset_tick'],20)

    def test_nonlinked_music_ripple_shortens_without_speed_change(self):
        p=state(track('sound',[clip('bed',0,40)],'audio',1));out,_=self.plan(p,request())
        clips=root(out)['tracks'][1]['clips']
        self.assertEqual([(c['timeline_start_tick'],c['duration_tick']) for c in clips],[(0,15),(15,20)])
        self.assertTrue(all('sequence_id' not in c and 'speed' not in c for c in clips))
        self.assertEqual(clips[1]['presentation_window']['offset_tick'],20)

    def test_nonlinked_music_growth_inserts_blank_not_a_stretched_bed(self):
        out,_=self.plan(state(track('sound',[clip('bed',0,40)],'audio',1)),request({'speed':.5}))
        self.assertEqual([(c['timeline_start_tick'],c['duration_tick']) for c in root(out)['tracks'][1]['clips']],[(0,20),(30,20)])

    def test_explicit_sync_retime_retimes_intersection_only(self):
        p=state(track('sound',[clip('bed',0,40)],'audio',1));out,_=self.plan(p,request(sync_content='retime'))
        self.assertEqual(sorted((c['timeline_start_tick'],c['duration_tick']) for c in root(out)['tracks'][1]['clips']),[(0,10),(10,5),(15,20)])

    def test_sync_false_and_sync_lock_false_leave_background_stationary(self):
        for opts,flags in [({'sync':False},{}),({}, {'sync_lock':False})]:
            with self.subTest(opts=opts,flags=flags):
                out,_=self.plan(state(track('sound',[clip('bed',0,40)],'audio',1,**flags)),request(options=opts,sync_content='retime'))
                self.assertEqual(at(out,'bed'),clip('bed',0,40));self.assertEqual(root(out)['duration_tick'],40)

    def test_rider_retimes_when_linkage_enabled_without_sync(self):
        p=state(track('overlay',[clip('label',12,18)],'video',2))
        out,_=self.plan(p,request(options={'sync':False,'linkage':True}))
        c=at(out,'label');self.assertEqual((c['timeline_start_tick'],c['duration_tick']),(11,3))
        self.assertEqual(c['source_in_tick'],10)

    def test_reverse_reverses_partial_rider_position_and_content(self):
        p=state(track('overlay',[clip('label',10,13,link_id='pair')],'video',2));at(p,'b')['link_id']='pair'
        out,_=self.plan(p,request({'reverse':True}));c=at(out,'label')
        self.assertEqual((c['timeline_start_tick'],c['duration_tick']),(17,3));self.assertTrue(c['reverse'])
        self.assertEqual(c['presentation_window']['offset_tick'],7)

    def test_curve_body_uses_full_host_integral_instead_of_own_length(self):
        p=state(track('overlay',[clip('label',15,20,link_id='pair')],'video',2));at(p,'b')['link_id']='pair'
        curve={'keyframes':[{'at_tick':0,'speed':1,'interpolation':'hold'},{'at_tick':5,'speed':2,'interpolation':'hold'}]}
        out,_=self.plan(p,request({'speed_curve':curve}));c=at(out,'label')
        self.assertEqual((c['timeline_start_tick'],c['duration_tick']),(15,3))
        self.assertEqual(c['source_out_tick']-c['source_in_tick'],10)

    def test_freeze_extends_member_that_contains_the_actual_hold_frame(self):
        p=state(track('overlay',[clip('left',10,15,link_id='pair'),clip('right',15,20,link_id='pair')],'video',2));at(p,'b')['link_id']='pair'
        out,_=self.plan(p,request({'freeze':{'at_tick':5,'duration_tick':3}}))
        self.assertEqual((at(out,'left')['timeline_start_tick'],at(out,'left')['duration_tick']),(10,8))
        self.assertEqual((at(out,'right')['timeline_start_tick'],at(out,'right')['duration_tick']),(18,5))

    def test_original_window_curve_reverse_audio_and_keys_remain_in_child(self):
        p=state();c=at(p,'b');c.update(reverse=True,speed_curve={'keyframes':[{'at_tick':0,'speed':1}]},
            audio={'volume':.5},keyframes=[{'property':'opacity','keyframes':[{'at_tick':0,'value':.2}]}])
        original=copy.deepcopy(c);p['sequences'][0]['tracks'][0]['clips'][1]=slice_clip(c,1,9,start=10)
        # Keep a valid magnetic main after making the visible window shorter.
        at(p,'c')['timeline_start_tick']=18;at(p,'d')['timeline_start_tick']=28;root(p)['duration_tick']=38
        out,plan=self.plan(p,request());inner=plan['created_sequences'][0]['tracks'][0]['clips'][0]
        for key in ('source_in_tick','source_out_tick','speed_curve','reverse','audio','keyframes'):self.assertEqual(inner[key],original[key])
        self.assertEqual(inner['presentation_window']['offset_tick'],1)
        self.assertEqual(at(out,'b')['duration_tick'],4)

    def test_static_blend_remains_outside_and_is_not_baked_against_black(self):
        p=state();at(p,'b')['blend']={'mode':'multiply','opacity':.5}
        out,plan=self.plan(p,request());self.assertEqual(at(out,'b')['blend'],at(p,'b')['blend'])
        self.assertNotIn('blend',plan['created_sequences'][0]['tracks'][0]['clips'][0])

    def test_root_track_processing_and_named_routes_stay_on_original_bus(self):
        lane=track('sound',[clip('voice',10,20,link_id='pair')],'audio',1,audio={'compressor':{'threshold':.2}})
        p=state(lane);at(p,'b')['link_id']='pair';root(p)['audio_routing']={'tracks':[{'track_id':'sound','output':'master'}]}
        out,_=self.plan(p,request());self.assertEqual(root(out)['audio_routing'],root(p)['audio_routing'])
        self.assertEqual(root(out)['tracks'][1]['audio'],lane['audio'])

    def test_ids_avoid_assets_markers_links_and_other_sequences(self):
        p=state();p['assets'].append({'id':'b_author_sequence','kind':'video'});root(p)['markers'].append({'id':'b_author','at_tick':1})
        _,plan=self.plan(p,request());child=plan['created_sequences'][0]
        self.assertNotEqual(child['id'],'b_author_sequence');self.assertNotEqual(child['tracks'][0]['clips'][0]['id'],'b_author')

    def test_side_selection_does_not_move_main(self):
        p=state(track('overlay',[clip('label',10,20)],'video',2));out,_=self.plan(p,request(ids=('label',)))
        self.assertEqual(root(out)['tracks'][0],root(p)['tracks'][0]);self.assertEqual(at(out,'label')['duration_tick'],5)

    def test_same_side_group_selected_twice_rejects_instead_of_retiming_twice(self):
        p=state(track('overlay',[clip('left',0,10,link_id='pair'),clip('right',0,10,link_id='pair')],'video',2))
        self.rejects(p,request(ids=('left','right')),'EDIT_RETIME_DUPLICATE_GROUP')

    def test_mixed_selection_and_side_to_main_link_reject(self):
        p=state(track('sound',[clip('voice',10,20,link_id='pair')],'audio',1));at(p,'b')['link_id']='pair'
        self.rejects(p,request(ids=('b','voice')),'EDIT_RETIME_MIXED_SELECTION')
        self.rejects(p,request(ids=('voice',)),'EDIT_RETIME_MIXED_SELECTION')

    def test_locked_linked_member_rejects_the_whole_edit(self):
        p=state(track('sound',[clip('voice',10,20,link_id='pair')],'audio',1,locked=True));at(p,'b')['link_id']='pair'
        self.rejects(p,request(),'EDIT_TRACK_LOCKED')

    def test_tracking_reference_and_source_transition_endpoint_reject(self):
        p=state();at(p,'d')['tracking_binding']={'source_clip_id':'b','source_track_id':'main'}
        self.rejects(p,request(),'EDIT_RANGE_BINDING_UNSUPPORTED')
        p=state();root(p)['source_transitions']=[{'id':'cut','from_clip_id':'a','to_clip_id':'b'}]
        self.rejects(p,request(),'EDIT_RANGE_TRANSITION_UNSUPPORTED')

    def test_malformed_external_blend_and_old_cross_transition_reject(self):
        p=state();at(p,'b')['keyframes']=[{'property':'blend.opacity','keyframes':[]}]
        self.rejects(p,request(),'BLEND_AUTOMATION_INVALID')
        p=state();at(p,'b')['transition_in']={'type':'slideleft'}
        self.rejects(p,request(),'EDIT_RETIME_TRANSITION_UNSUPPORTED')

    def test_resource_limit_uses_exact_created_clips(self):
        with patch('ai_ad_editor.retime_edits.MAX_CLIPS',4):self.rejects(state(),request(),'EDIT_RETIME_RESOURCE_LIMIT')
        with patch('ai_ad_editor.retime_edits.MAX_CLIPS',5):self.plan(state(),request())

    def test_request_unknown_fields_and_non_boolean_switches_reject(self):
        for q in [request(unknown=1),request(options={'sync':1}),request(sync_content=[]),request(ids=('b','b'))]:
            with self.subTest(q=q):
                with self.assertRaises(AppError):self.plan(state(),q)

    def test_nonfinite_tiny_boolean_and_huge_speed_reject(self):
        for value in (True,0,.001,float('nan'),float('inf'),10**400):
            with self.subTest(value=str(value)[:30]):self.rejects(state(),request({'speed':value}),'EDIT_RETIME_REQUEST_INVALID')

    def test_freeze_invalid_ticks_and_unknown_transform_fields_reject(self):
        for transform in ({'freeze':{'at_tick':11,'duration_tick':2}}, {'freeze':{'duration_tick':True}},
                          {'freeze':{'duration_tick':2,'unknown':0}}, {'reverse':1}, {'unknown':1}):
            with self.subTest(transform=transform):
                with self.assertRaises(AppError):self.plan(state(),request(transform))

    def test_transform_shared_interval_boundaries_are_contiguous(self):
        settings=state()['settings'];t=Transform({'speed':.5,'reverse':True,'freeze':{'at_tick':10,'duration_tick':5}},10,settings)
        a,b=t.interval(0,5),t.interval(5,10)
        self.assertEqual((b[0],b[1],a[0],a[1]),(0,15,15,25))

    def test_curve_uses_existing_bounded_easing_compiler(self):
        t=Transform({'speed_curve':{'keyframes':[{'at_tick':0,'speed':1,'interpolation':'ease_in'}, {'at_tick':10,'speed':3}]}},10,state()['settings'])
        self.assertTrue(t.report()['curve_compilation']['adaptive']);self.assertLess(t.output,10)


class CompleteOutputRetimeCliTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(dir=Path(__file__).resolve().parents[1]/'.runtime');self.addCleanup(self.tmp.cleanup)
        self.root,_=create_project(Path(self.tmp.name)/'project','retime');self.path=self.root/'project.json'
        source=Path(self.tmp.name)/'image.png';Image.new('RGB',(64,32),'red').save(source)
        code,result=invoke('media','ingest','--project',self.root,'--input',source,'--asset-id','media');self.assertEqual(code,0,result)
        p=json.loads(self.path.read_bytes());p['settings']['timebase']=state()['settings']['timebase'];p['sequences']=state()['sequences'];save_project(self.root,p)

    def call(self,q,*,edit=True,extra=(),expected=0):
        path=Path(self.tmp.name)/'request.json';path.write_text(json.dumps(q),encoding='utf-8')
        code,result=invoke('timeline','edit' if edit else 'compose','--project',self.root,'--sequence-id','seq','--input',path,*extra)
        self.assertEqual(code,expected,result);return result

    def test_real_cli_dry_run_and_idempotent_apply(self):
        before=self.path.read_bytes();self.call(request(),extra=('--dry-run',));self.assertEqual(before,self.path.read_bytes())
        one=self.call(request(),extra=('--idempotency-key','retime'));before=self.path.read_bytes()
        two=self.call(request(),extra=('--idempotency-key','retime'));self.assertEqual(before,self.path.read_bytes());self.assertEqual(one['operation_id'],two['operation_id'])

    def test_compose_retime_and_later_failure_roll_back_atomically(self):
        before=self.path.read_bytes()
        self.call({'operations':[{'op':'retime_clip','clip_id':'b','transform':{'speed':2}}, {'op':'update_clip','clip_id':'c','patch':{'duration_tick':0}}]},edit=False,expected=2)
        self.assertEqual(before,self.path.read_bytes())
        self.call({'operations':[{'op':'retime_clip','clip_id':'b','transform':{'speed':2}}]},edit=False)
        self.assertEqual(at(json.loads(self.path.read_bytes()),'c')['timeline_start_tick'],15)

    def test_stale_hash_and_out_of_range_root_automation_leave_bytes_intact(self):
        before=self.path.read_bytes();self.call(request(),extra=('--expected-project-sha256','sha256:'+'0'*64),expected=2)
        self.assertEqual(before,self.path.read_bytes())
        p=json.loads(before);root(p)['markers']=[{'id':'late','at_tick':39,'label':'late'}];save_project(self.root,p);before=self.path.read_bytes()
        self.call(request(),expected=2);self.assertEqual(before,self.path.read_bytes())

    def test_native_package_roundtrip_keeps_editable_authors(self):
        self.call(request());package=Path(self.tmp.name)/'retime.aevpkg.zip'
        code,result=invoke('convert','export','--project',self.root,'--target-format','package','--output',package);self.assertEqual(code,0,result)
        target=Path(self.tmp.name)/'restored';code,result=invoke('convert','import','--input',package,'--output',target);self.assertEqual(code,0,result)
        p=json.loads((target/'project.json').read_bytes());self.assertEqual(len(p['sequences']),2)
        self.assertEqual(at(p,'b')['duration_tick'],5);validate_magnetic(root(p))

    def test_fragment_save_retains_retime_author_sequence_closure(self):
        self.call(request());query=Path(self.tmp.name)/'save.json';query.write_text(json.dumps({'id':'retime','version':1,'name':'retime','sequence_id':'seq','clip_ids':['b']}),encoding='utf-8')
        code,result=invoke('fragment','save','--project',self.root,'--library',Path(self.tmp.name)/'library','--input',query);self.assertEqual(code,0,result)
        saved=result['data']['fragment'];self.assertEqual(len(saved['project']['sequences']),2)
        self.assertEqual(saved['selection']['included'],['a','b','c','d'])

    def test_repeat_relative_retime_creates_an_editable_stack(self):
        self.call(request());self.call(request({'speed':.5}))
        p=json.loads(self.path.read_bytes());self.assertEqual(at(p,'b')['duration_tick'],10)
        self.assertEqual(len(p['sequences']),3);self.assertEqual(at(p,'c')['timeline_start_tick'],20)


class CompleteBusTempoClockTests(unittest.TestCase):
    def mapped(self,transform,duration=10):
        from ai_ad_editor.time_mapping import make_map
        from ai_ad_editor.speed_curves import compile_curve
        c={'source_in_tick':10,'source_out_tick':20,'timeline_start_tick':10,'duration_tick':duration,**transform}
        return make_map(c,compile_curve(c,10,10),10)

    def test_constant_nested_audio_keeps_one_native_tempo_context(self):
        from ai_ad_editor.time_mapping import audio_windows
        parts=audio_windows([self.mapped({'speed':2},5)],1,2)
        self.assertEqual(len(parts),1);self.assertEqual(parts[0],(0.,1.,2.,.5))

    def test_hold_knot_is_exact_and_adjacent_equal_tempos_merge(self):
        from ai_ad_editor.time_mapping import audio_windows
        mapping=self.mapped({'speed_curve':[{'at_tick':0,'speed':1,'interpolation':'hold'},
            {'at_tick':6,'speed':2,'interpolation':'hold'},{'at_tick':10,'speed':2}]},8)
        parts=audio_windows([mapping],1,2)
        self.assertEqual(len(parts),2);self.assertAlmostEqual(parts[0][1],.6)
        self.assertAlmostEqual(parts[0][2],1);self.assertAlmostEqual(parts[1][2],2)
        self.assertAlmostEqual(parts[-1][3],.8)

    def test_reverse_keeps_source_order_before_pcm_reversal(self):
        from ai_ad_editor.time_mapping import audio_windows
        parts=audio_windows([self.mapped({'speed':2,'reverse':True},5)],1,2)
        self.assertEqual(len(parts),1);self.assertAlmostEqual(parts[-1][3],.5)

    def test_ancestor_knot_projects_back_through_reverse_and_speed(self):
        from ai_ad_editor.time_mapping import audio_windows,make_map
        first=self.mapped({'speed':2,'reverse':True},5)
        second=make_map({'source_in_tick':10,'source_out_tick':15,'timeline_start_tick':0,'duration_tick':4},
            [(0.,.3,1.,1.),(.3,.5,2.,2.)],10)
        parts=audio_windows([first,second],1,2)
        self.assertEqual(len(parts),2);self.assertAlmostEqual(parts[0][1],.4)
        self.assertAlmostEqual(parts[0][2],4);self.assertAlmostEqual(parts[1][2],2)
        self.assertAlmostEqual(parts[-1][3],.4)


if __name__=='__main__':unittest.main()
