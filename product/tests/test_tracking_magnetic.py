"""Native magnetic permutations against independent original Float32 frames."""
import copy,unittest
from fractions import Fraction as F
from unittest.mock import patch

import numpy as np

from ai_ad_editor.bindings import validate_project_bindings
from ai_ad_editor.clip_windows import apply_operation
from ai_ad_editor.edit_planner import build_edit_plan
from ai_ad_editor.errors import AppError
from ai_ad_editor.float_timeline import FloatTimeline
import test_float_timeline as fixture
import test_tracking_edits as authored


def scene():
    p,s=authored.scene();seq=p['sequences'][0]
    source,labels=seq['tracks'];source['order']=1;labels['order']=2
    main=[]
    for name,a,b in [('a',0,30),('b',30,60),('c',60,100)]:
        clip=fixture.clip(name,'marker');clip.update(timeline_start_tick=a,duration_tick=b-a,source_out_tick=b-a,
            transform={'opacity':0})
        main.append(clip)
    seq['tracks'].insert(0,dict(id='magnet',kind='video',order=0,clips=main))
    seq['editing']=dict(main_track_id='magnet',magnetic=True)
    return p,s


def rows(p):return {c['id']:c for t in p['sequences'][0]['tracks'] for c in t['clips']}


class NativeTrackingMagneticTests(unittest.TestCase):
    def frames(self,p,s):
        host=FloatTimeline(p,'main',s,working_signal=fixture.LINEAR)
        return [host.render_frame(i) for i in range(host.frame_count)]

    def plan(self,p,**kw):
        old=copy.deepcopy(p)
        value,plan=build_edit_plan(p,'main',dict(action='reorder',clip_ids=['c'],before_clip_id='a',**kw))
        self.assertEqual(p,old);validate_project_bindings(value)
        return value,plan

    def equal(self,a,b):
        self.assertEqual(len(a),len(b))
        for i,(left,right) in enumerate(zip(a,b)):
            with self.subTest(frame=i):np.testing.assert_array_equal(left[0],right[0])

    def permuted(self,frames):return [frames[i] for i in [6,7,8,9,0,1,2,3,4,5]]

    def reject(self,p,code,**kw):
        old=copy.deepcopy(p)
        with self.assertRaises(AppError) as caught:self.plan(p,**kw)
        self.assertEqual(caught.exception.code,code);self.assertEqual(p,old)

    def test_split_source_and_follower_preserve_every_pixel_and_original_observations(self):
        p,s=scene();expected=self.frames(p,s);binding=copy.deepcopy(rows(p)['marker']['tracking_binding'])
        p,plan=self.plan(p);self.equal(self.frames(p,s),self.permuted(expected))
        self.assertEqual(len(plan['sync_splits']),2);self.assertEqual(len(plan['tracking_binding_changes']),3)
        self.assertEqual(len(plan['rebound_clip_ids']),3)
        for clip in rows(p).values():
            if clip.get('tracking_binding'):
                self.assertEqual(clip['tracking_binding']['observations'],binding['observations'])
                self.assertEqual(clip['tracking_binding']['reference_output_tick'],0)
                self.assertEqual(len(clip['tracking_binding']['source_fragments']),3)

    def test_source_and_target_link_groups_remain_paired_on_each_region(self):
        p,s=scene()
        for name in ('source','marker'):rows(p)[name]['link_id']='pair'
        original=self.frames(p,s);p,plan=self.plan(p);self.equal(self.frames(p,s),self.permuted(original))
        clips=rows(p);left,right=plan['sync_splits']
        for a,b in zip(left['pieces'],right['pieces']):
            self.assertEqual(a['original_range_tick'],b['original_range_tick'])
            self.assertEqual(clips[a['clip_id']]['link_id'],clips[b['clip_id']]['link_id'])
        self.assertEqual(len({c['link_id'] for c in clips.values() if c.get('link_id')}),3)

    def test_later_follower_keeps_nonzero_original_ROI_reference_after_permutation(self):
        p,s=scene();rows(p)['marker'].update(timeline_start_tick=20,duration_tick=80,source_out_tick=80)
        expected=self.frames(p,s);p,_=self.plan(p);self.equal(self.frames(p,s),self.permuted(expected))
        for c in rows(p).values():
            if c.get('tracking_binding'):self.assertEqual(c['tracking_binding']['reference_output_tick'],20)

    def test_reverse_curve_and_freeze_retain_complete_original_author_clock(self):
        for change in ({'reverse':True},{'speed_curve':[dict(at_tick=0,speed=1)]},
                       {'speed_curve':[dict(at_tick=0,speed=.7),dict(at_tick=100,speed=1.4)]},
                       {'freeze':dict(at_tick=30,duration_tick=20)}):
            with self.subTest(change=change):
                p,s=scene();rows(p)['source'].update(change)
                expected=self.frames(p,s);p,_=self.plan(p);self.equal(self.frames(p,s),self.permuted(expected))

    def test_already_split_main_source_reorders_and_rewrites_the_follower_route(self):
        p,s=authored.scene()
        p,_=apply_operation(p,'main',dict(op='split_clip',clip_id='source',at_tick=30,left_id='shot_a',right_id='rest'))
        p,_=apply_operation(p,'main',dict(op='split_clip',clip_id='rest',at_tick=30,left_id='shot_b',right_id='shot_c'))
        p['sequences'][0]['editing']=dict(main_track_id='video',magnetic=True)
        expected=self.frames(p,s);old=copy.deepcopy(p)
        p,plan=build_edit_plan(p,'main',dict(action='reorder',clip_ids=['shot_c'],before_clip_id='shot_a'))
        self.assertEqual(old['assets'],p['assets']);validate_project_bindings(p)
        self.equal(self.frames(p,s),self.permuted(expected))
        self.assertEqual(len(plan['sync_splits']),1)
        for c in rows(p).values():
            if c.get('tracking_binding'):
                self.assertEqual([r['clip_id'] for r in c['tracking_binding']['source_fragments']],['shot_c','shot_a','shot_b'])

    def test_whole_followers_on_each_main_shot_reorder_without_partition(self):
        p,s=scene()
        for cid in ('source','marker'):
            p,_=apply_operation(p,'main',dict(op='split_clip',clip_id=cid,at_tick=30,left_id=cid+'_one',right_id=cid+'_rest'))
            p,_=apply_operation(p,'main',dict(op='split_clip',clip_id=cid+'_rest',at_tick=30,left_id=cid+'_two',right_id=cid+'_three'))
        expected=self.frames(p,s);p,plan=self.plan(p);self.equal(self.frames(p,s),self.permuted(expected))
        self.assertEqual(plan['sync_splits'],[])

    def test_dynamic_source_crop_and_follower_opacity_survive_new_cut_order(self):
        p,s=scene();source=rows(p)['source']
        source['crop']=dict(x=0,y=0,width=.75,height=1)
        source['keyframes'].append(dict(property='crop.x',keyframes=[dict(at_tick=0,value=0),dict(at_tick=100,value=.25)]))
        expected=self.frames(p,s);p,_=self.plan(p);self.equal(self.frames(p,s),self.permuted(expected))

    def test_vfr_nonzero_demux_source_is_not_resnapped_after_reorder(self):
        p,s=scene();before=s['a'];pts=[1000,1007,1018,1020,1037,1042,1059,1063,1084,1094]
        s['a']=fixture.source([before.fetch(i) for i in range(10)],pts=pts,
            durations=[b-a for a,b in zip(pts,pts[1:]+[1100])],origin=F(10))
        expected=self.frames(p,s);p,_=self.plan(p);got=self.frames(p,s);self.equal(got,self.permuted(expected))
        actual=[next(r['tracking']['native_pts'] for r in meta['layers'] if r.get('tracking')) for _,meta in got]
        original=[next(r['tracking']['native_pts'] for r in meta['layers'] if r.get('tracking')) for _,meta in self.permuted(expected)]
        self.assertEqual(actual,original)

    def test_chained_video_carrier_and_later_target_keep_reference_geometry(self):
        p,s=scene();seq=p['sequences'][0];marker=rows(p)['marker']
        carrier=fixture.clip('carrier');carrier['transform']={'scale':.8}
        carrier['tracking_binding']=copy.deepcopy(marker['tracking_binding']);carrier['tracking_binding']['base'].update(scale=.8,opacity_keyframes=[])
        seq['tracks'].insert(2,dict(id='carrier_track',kind='overlay',order=2,clips=[carrier]));seq['tracks'][-1]['order']=3
        marker.update(timeline_start_tick=20,duration_tick=80,source_out_tick=80)
        marker['tracking_binding'].update(source_track_id='carrier_track',source_clip_id='carrier')
        expected=self.frames(p,s);p,plan=self.plan(p);self.equal(self.frames(p,s),self.permuted(expected))
        self.assertEqual(len(plan['tracking_binding_changes']),6)

    def test_inverse_reorder_restores_pixels_with_existing_fragment_reference_offsets(self):
        p,s=scene();binding=rows(p)['marker']['tracking_binding']
        binding.update(reference_output_tick=0,source_fragments=[dict(track_id='video',clip_id='source',author_offset_tick=20)])
        expected=self.frames(p,s);p,_=self.plan(p)
        p,plan=build_edit_plan(p,'main',dict(action='reorder',clip_ids=['c'],before_clip_id=None))
        self.equal(self.frames(p,s),expected)
        for c in rows(p).values():
            if c.get('tracking_binding'):
                self.assertTrue(all(r['author_offset_tick']==20 for r in c['tracking_binding']['source_fragments']))

    def test_unmoved_locked_follower_rejects_required_source_route_rewrite_atomically(self):
        p,_=scene();p['sequences'][0]['tracks'][-1]['locked']=True
        self.reject(p,'EDIT_BOUND_REFERENCE_LOCKED')

    def test_locked_linked_follower_rejects_before_partition(self):
        p,_=scene()
        for name in ('source','marker'):rows(p)[name]['link_id']='pair'
        p['sequences'][0]['tracks'][-1]['locked']=True
        self.reject(p,'EDIT_TRACK_LOCKED')

    def test_opt_out_follower_keeps_its_author_window_but_tracks_new_source_route(self):
        p,s=scene();p['sequences'][0]['tracks'][-1]['sync_lock']=False
        old=copy.deepcopy(rows(p)['marker']);p,plan=self.plan(p);new=rows(p)['marker']
        self.assertNotIn('presentation_window',new)
        self.assertEqual(new['timeline_start_tick'],old['timeline_start_tick']);self.assertEqual(new['duration_tick'],old['duration_tick'])
        self.assertEqual(len(new['tracking_binding']['source_fragments']),3)
        states=[next(r['tracking'] for r in m['layers'] if r.get('tracking')) for _,m in self.frames(p,s)]
        self.assertEqual([v['native_frame_index'] for v in states],[6,7,8,9,0,1,2,3,4,5])

    def test_legacy_tracking_cut_guard_is_retained(self):
        p,_=scene();p['settings'].pop('pixel_pipeline')
        self.reject(p,'EDIT_REORDER_SYNC_BINDING_UNSUPPORTED')

    def test_total_clip_and_binding_route_limits_reject_before_author_mutation(self):
        p,_=scene()
        with patch('ai_ad_editor.magnetic_reorder.MAX_CLIPS',8):self.reject(p,'EDIT_REORDER_RESOURCE_LIMIT')
        with patch('ai_ad_editor.binding_edits.MAX_SOURCE_FRAGMENTS',2):self.reject(p,'EDIT_BINDING_FRAGMENT_BUDGET')

if __name__=='__main__':unittest.main()
