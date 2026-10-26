"""Edited native tracking compared to untouched Float32 pixels and source PTS."""
import copy
import unittest
from fractions import Fraction as F
from unittest.mock import patch

import numpy as np

from ai_ad_editor.bindings import validate_binding, validate_project_bindings
from ai_ad_editor.clip_windows import apply_operation
from ai_ad_editor.edit_planner import build_edit_plan
from ai_ad_editor.errors import AppError
from ai_ad_editor.float_timeline import FloatTimeline
from ai_ad_editor.range_edits import build_range_plan
import test_float_timeline as fixture
import test_float_tracking as tracking


def scene():
    p,s,_,source,marker=tracking.scene()
    source['keyframes']=[dict(property='transform.scale',keyframes=[dict(at_tick=0,value=.7),dict(at_tick=100,value=1.1)]),
        dict(property='transform.rotation',keyframes=[dict(at_tick=0,value=-20),dict(at_tick=100,value=35)])]
    marker['tracking_binding'].update(scale_mode='roi',rotation_mode='source')
    marker['tracking_binding']['base']['opacity_keyframes']=[dict(at_tick=0,value=.4),dict(at_tick=100,value=1)]
    return p,s


class NativeTrackingEditTests(unittest.TestCase):
    def frames(self,p,s):
        h=FloatTimeline(p,'main',s,working_signal=fixture.LINEAR)
        return [h.render_frame(i) for i in range(h.frame_count)]

    def equal(self,a,b):
        self.assertEqual(len(a),len(b))
        for i,(x,y) in enumerate(zip(a,b)):
            with self.subTest(frame=i):np.testing.assert_array_equal(x[0],y[0])

    def split(self,p,cid,at=40):
        return apply_operation(p,'main',dict(op='split_clip',clip_id=cid,at_tick=at))[0]

    def test_split_source_and_target_in_either_order_preserves_every_pixel_and_authored_keys(self):
        for order in (('source','marker'),('marker','source')):
            p,s=scene();old=copy.deepcopy(p);expected=self.frames(p,s)
            for cid in order:p=self.split(p,cid)
            self.equal(self.frames(p,s),expected)
            self.assertFalse(validate_project_bindings(p))
            for t in p['sequences'][0]['tracks']:
                for c in t['clips']:
                    original=next(x for track in old['sequences'][0]['tracks'] for x in track['clips'] if c['id'].startswith(x['id']))
                    self.assertEqual(c.get('keyframes'),original.get('keyframes'))
                    if c.get('tracking_binding'):self.assertEqual(c['tracking_binding']['observations'],original['tracking_binding']['observations'])

    def test_repeated_split_and_trim_keep_only_live_fragments_and_original_reference(self):
        p,s=scene();expected=self.frames(p,s);p=self.split(p,'source');p=self.split(p,'source_b',30)
        p=self.split(p,'marker');p=self.split(p,'marker_b',30)
        p,_=apply_operation(p,'main',dict(op='trim_clip',clip_id='source_b_a',start_tick=10,end_tick=30))
        got=self.frames(p,s)
        self.equal(got[:4],expected[:4]);self.equal(got[5:],expected[5:])
        state=next(r['tracking'] for r in got[4][1]['layers'] if 'tracking' in r)
        self.assertFalse(state['active']);self.assertEqual(state['values']['opacity'],0)
        for t in p['sequences'][0]['tracks']:
            for c in t['clips']:
                if c.get('tracking_binding'):self.assertEqual(c['tracking_binding']['reference_output_tick'],0)

    def test_ripple_insert_and_delete_preserve_frames_around_exact_blank_gap(self):
        p,s=scene();before=copy.deepcopy(p);expected=self.frames(p,s)
        p,plan=apply_operation(p,'main',dict(op='ripple_insert',at_tick=40,duration_tick=20))
        self.assertTrue(plan['tracking_binding_changes']);got=self.frames(p,s)
        self.equal(got[:4],expected[:4]);self.equal(got[6:],expected[4:])
        self.assertTrue(all(not x[0].any() for x in got[4:6]))
        p,_=apply_operation(p,'main',dict(op='ripple_delete',at_tick=40,duration_tick=20))
        self.equal(self.frames(p,s),expected)
        self.assertEqual(before['sequences'][0]['tracks'][0]['clips'][0]['duration_tick'],100)

    def test_native_VFR_reverse_and_freeze_split_uses_same_original_indices(self):
        for mode in ('VFR','reverse','freeze','curve'):
            p,s=scene();source=p['sequences'][0]['tracks'][0]['clips'][0]
            if mode=='VFR':
                s['a']=fixture.source([s['a'].fetch(i) for i in range(10)],pts=[500,501,503,504,507,509,511,513,516,518],
                    durations=[1,2,1,3,2,2,2,3,2,2],time_base='1/20',origin=25)
            if mode=='reverse':source['reverse']=True
            if mode=='freeze':source.update(freeze={'at_tick':30,'duration_tick':20},speed=1.25)
            if mode=='curve':source['speed_curve']={'keyframes':[{'at_tick':0,'speed':.5},{'at_tick':100,'speed':2}]}
            expected=self.frames(p,s);p=self.split(self.split(p,'source',30),'marker',60)
            got=self.frames(p,s);self.equal(got,expected)
            a=[next(r['tracking']['native_frame_index'] for r in m['layers'] if 'tracking' in r) for _,m in expected]
            b=[next(r['tracking']['native_frame_index'] for r in m['layers'] if 'tracking' in r) for _,m in got]
            self.assertEqual(a,b)

    def test_source_only_insert_hides_follower_in_gap_then_follows_shifted_source(self):
        p,s,positions,source,marker=tracking.scene()
        p,_=apply_operation(p,'main',dict(op='ripple_insert',track_id='video',at_tick=40,duration_tick=20))
        rows=self.frames(p,s)
        for i in range(10):
            state=next(r['tracking'] for r in rows[i][1]['layers'] if 'tracking' in r)
            if 4<=i<6:self.assertEqual(state['values']['opacity'],0)
            else:
                want=i if i<4 else i-2
                self.assertEqual(state['native_frame_index'],want)
                self.assertEqual(state['values']['position.x'],(positions[want]+.5)/8)

    def test_range_lift_extract_insert_and_overwrite_replan_real_retained_windows(self):
        for action in ('lift','extract','insert','overwrite'):
            p,s=scene();expected=self.frames(p,s)
            request=dict(action=action,at_tick=30,duration_tick=20,options={'sync':True,'linked':False})
            if action in {'lift','extract'}:request['track_ids']=['video','labels']
            else:
                incoming=fixture.clip('inserted');incoming.update(duration_tick=20,source_out_tick=20)
                request['items']=[dict(track_id='video',clip=incoming)]
            p,plan=build_range_plan(p,'main',request);self.assertTrue(plan['tracking_binding_changes'])
            got=self.frames(p,s);self.equal(got[:3],expected[:3])
            if action=='extract':self.equal(got[3:],expected[5:])
            elif action=='insert':self.equal(got[5:],expected[3:])
            else:self.equal(got[5:],expected[5:])

    def test_complete_source_removal_retains_hidden_binding_and_all_observation_evidence(self):
        for method in ('range','whole'):
            p,s=scene();old=copy.deepcopy(p['sequences'][0]['tracks'][1]['clips'][0]['tracking_binding'])
            if method=='range':p,plan=build_range_plan(p,'main',dict(action='lift',at_tick=0,duration_tick=100,track_ids=['video'],options={'linked':False}))
            else:p,plan=build_edit_plan(p,'main',dict(action='remove',clip_ids=['source'],options={'linked':False}))
            b=p['sequences'][0]['tracks'][1]['clips'][0]['tracking_binding']
            self.assertEqual(b['source_fragments'],[]);self.assertEqual(b['observations'],old['observations'])
            for pixels,meta in self.frames(p,s):
                self.assertFalse(pixels.any());self.assertEqual(meta['layers'][0]['tracking']['reason'],'source-route-empty-after-edit')
            self.assertFalse(validate_project_bindings(p))

    def test_locked_dependent_and_invalid_split_are_atomic(self):
        p,s=scene();p['sequences'][0]['tracks'][1]['locked']=True;old=copy.deepcopy(p)
        with self.assertRaises(AppError) as caught:self.split(p,'source')
        self.assertEqual(caught.exception.code,'EDIT_BOUND_REFERENCE_LOCKED');self.assertEqual(p,old)
        p,s=scene();old=copy.deepcopy(p)
        with self.assertRaises(AppError):self.split(p,'source',100)
        self.assertEqual(p,old)

    def test_legacy_pipeline_keeps_explicit_guard_and_refuses_native_route_fields(self):
        p,s=scene();p['settings'].pop('pixel_pipeline')
        with self.assertRaises(AppError) as caught:self.split(p,'source')
        self.assertEqual(caught.exception.code,'CLIP_WINDOW_BINDING_UNSUPPORTED')
        target=p['sequences'][0]['tracks'][1]['clips'][0];target['tracking_binding']['source_fragments']=[]
        with self.assertRaises(AppError):validate_binding(p,p['sequences'][0],p['sequences'][0]['tracks'][1],target)

    def test_overlap_duplicate_and_missing_fragment_reject_before_fetch(self):
        for kind in ('overlap','duplicate','missing'):
            p,s=scene();seq=p['sequences'][0];c=copy.deepcopy(seq['tracks'][0]['clips'][0]);c['id']='other';seq['tracks'][0]['clips'].append(c)
            binding=seq['tracks'][1]['clips'][0]['tracking_binding']
            binding['source_fragments']=[dict(track_id='video',clip_id='source'),dict(track_id='video',clip_id='other' if kind=='overlap' else 'source' if kind=='duplicate' else 'absent')]
            with patch.object(s['a'],'fetch',side_effect=AssertionError('must reject before pixel fetch')),self.assertRaises(AppError):self.frames(p,s)

    def test_cycle_through_secondary_fragment_and_aggregate_budget_reject(self):
        p,s=scene();p=self.split(p,'source');seq=p['sequences'][0]
        a,b=seq['tracks'][0]['clips'];target=seq['tracks'][1]['clips'][0]
        b['tracking_binding']=copy.deepcopy(target['tracking_binding'])
        b['tracking_binding'].update(source_clip_id=a['id'],source_fragments=[dict(track_id='video',clip_id=a['id'])])
        a['tracking_binding']=copy.deepcopy(b['tracking_binding'])
        a['tracking_binding'].update(source_clip_id=b['id'],source_fragments=[dict(track_id='video',clip_id=b['id'])])
        self.assertTrue(validate_project_bindings(p))
        p,s=scene();p=self.split(p,'source')
        with patch('ai_ad_editor.float_tracking.MAX_SOURCE_REFERENCES',1),self.assertRaises(AppError) as caught:self.frames(p,s)
        self.assertEqual(caught.exception.code,'FLOAT_TRACKING_BUDGET')

    def test_source_slip_and_real_extension_stay_explicitly_guarded(self):
        p,s=scene()
        with self.assertRaises(AppError) as caught:build_range_plan(p,'main',dict(action='slip',clip_id='source',delta_source_tick=10))
        self.assertEqual(caught.exception.code,'EDIT_RANGE_BINDING_UNSUPPORTED')
        with self.assertRaises(AppError) as caught:build_range_plan(p,'main',dict(action='extend_source',clip_id='source',head_tick=0,tail_tick=10))
        self.assertEqual(caught.exception.code,'EDIT_RANGE_BINDING_SOURCE_EXTENSION_UNSUPPORTED')

    def test_retained_roll_preserves_pixels_and_slide_follows_the_new_source_clock(self):
        p,s=scene();expected=self.frames(p,s);p=self.split(p,'source')
        p,_=build_range_plan(p,'main',dict(action='roll',left_clip_id='source_a',right_clip_id='source_b',
            delta_tick=10,options={'linked':False}))
        self.equal(self.frames(p,s),expected)
        p,s,_,_,_=tracking.scene();expected=self.frames(p,s)
        p=self.split(self.split(p,'source',30),'source_b',40)
        p,_=build_range_plan(p,'main',dict(action='slide',clip_id='source_b_a',delta_tick=10,options={'linked':False}))
        self.equal(self.frames(p,s),[expected[i] for i in [0,1,2,3,3,4,5,6,8,9]])

    def test_nonzero_original_ROI_reference_survives_source_and_target_ripple(self):
        p,s=scene();target=p['sequences'][0]['tracks'][1]['clips'][0]
        target.update(timeline_start_tick=20,duration_tick=80,source_out_tick=80)
        expected=self.frames(p,s)
        p,_=apply_operation(p,'main',dict(op='ripple_insert',at_tick=50,duration_tick=20))
        got=self.frames(p,s);self.equal(got[:5],expected[:5]);self.equal(got[7:],expected[5:])
        for c in p['sequences'][0]['tracks'][1]['clips']:
            self.assertEqual(c['tracking_binding']['reference_output_tick'],20)

    def test_edited_chain_retains_intermediate_pose_at_later_follower_reference(self):
        p,s=scene();seq=p['sequences'][0];source=seq['tracks'][0]['clips'][0]
        marker=seq['tracks'][1]['clips'][0]
        carrier=fixture.clip('carrier');carrier['transform']={'scale':.8}
        carrier['tracking_binding']=copy.deepcopy(marker['tracking_binding'])
        carrier['tracking_binding']['base'].update(scale=.8,opacity_keyframes=[])
        seq['tracks'].insert(1,dict(id='carrier_track',kind='overlay',order=1,clips=[carrier]))
        seq['tracks'][-1]['order']=2
        marker.update(timeline_start_tick=20,duration_tick=80,source_out_tick=80)
        marker['tracking_binding'].update(source_track_id='carrier_track',source_clip_id='carrier')
        expected=self.frames(p,s);p=self.split(p,'source',50)
        self.equal(self.frames(p,s),expected)


if __name__=='__main__':unittest.main()
