"""Actual native pixels and clocks after editing tracked physical source media."""
import copy
from fractions import Fraction as F
import unittest
import numpy as np

from ai_ad_editor.bindings import validate_binding, validate_project_bindings
from ai_ad_editor.clip_windows import apply_operation
from ai_ad_editor.errors import AppError
from ai_ad_editor.float_timeline import FloatTimeline
from ai_ad_editor.range_edits import build_range_plan
import test_float_timeline as fixture
import test_float_tracking as tracking


def scene():
    p,s,positions,source,marker=tracking.scene(20)
    p['assets'][0]['probe']['duration_seconds']=2
    source.update(timeline_start_tick=20,duration_tick=80,source_in_tick=20,source_out_tick=100)
    return p,s,positions


def clips(p):return {c['id']:c for t in p['sequences'][0]['tracks'] for c in t['clips']}


class NativeTrackingSourceEditTests(unittest.TestCase):
    def frames(self,p,s):
        host=FloatTimeline(p,'main',s,working_signal=fixture.LINEAR)
        return [host.render_frame(i) for i in range(host.frame_count)]

    def plan(self,p,**args):
        before=copy.deepcopy(p);result=build_range_plan(p,'main',args)
        self.assertEqual(p,before);self.assertFalse(validate_project_bindings(result[0]))
        return result

    def pixels_equal(self,a,b):
        self.assertEqual(len(a),len(b))
        for i,(x,y) in enumerate(zip(a,b)):
            with self.subTest(frame=i):np.testing.assert_array_equal(x[0],y[0])

    def tracking(self,meta):return next(r['tracking'] for r in meta['layers'] if r.get('tracking'))

    def test_slip_reprojects_against_actual_new_native_frame_in_both_directions(self):
        for reverse in (False,True):
            for delta in (-10,20):
                p,s,positions=scene();clips(p)['source']['reverse']=reverse
                observations=copy.deepcopy(clips(p)['marker']['tracking_binding']['observations'])
                after,plan=self.plan(p,action='slip',clip_id='source',delta_source_tick=delta)
                frames=self.frames(after,s)
                for i in range(2,10):
                    state=self.tracking(frames[i][1]);expected=(11-i if reverse else i)+delta//10
                    self.assertEqual(state['native_frame_index'],expected)
                    self.assertEqual(F(state['native_time']),F(expected,10))
                    self.assertEqual(float(frames[i][0][1,positions[expected],0]),1)
                self.assertEqual(clips(after)['marker']['tracking_binding']['observations'],observations)
                self.assertTrue(plan['tracking_binding_changes'][0]['source_edits'])
                self.assertEqual(clips(after)['source']['timeline_start_tick'],20)

    def test_slipped_unobserved_frames_hide_instead_of_inventing_motion(self):
        p,s,_=scene();b=clips(p)['marker']['tracking_binding'];b['range']={'start_seconds':.2,'end_seconds':.6}
        b['observations']=[o for o in b['observations'] if .2<=o['at_seconds']<=.6]
        after,_=self.plan(p,action='slip',clip_id='source',delta_source_tick=40)
        frames=self.frames(after,s)
        for i in range(2,10):
            state=self.tracking(frames[i][1]);self.assertFalse(state['active'])
            self.assertEqual(state['values']['opacity'],0)

    def test_repeated_slip_reports_dependency_and_rejects_locked_follower_atomically(self):
        p,s,_=scene();p,_=self.plan(p,action='slip',clip_id='source',delta_source_tick=10)
        p['sequences'][0]['tracks'][1]['locked']=True;before=copy.deepcopy(p)
        with self.assertRaises(AppError) as caught:build_range_plan(p,'main',dict(action='slip',clip_id='source',delta_source_tick=10))
        self.assertEqual(caught.exception.code,'EDIT_BOUND_REFERENCE_LOCKED');self.assertEqual(p,before)

    def test_head_extension_preserves_every_existing_pixel_and_ROI_rotation_reference(self):
        for reverse in (False,True):
            p,s,_=scene();source=clips(p)['source'];source['reverse']=reverse
            source['keyframes']=[dict(property='transform.scale',keyframes=[dict(at_tick=0,value=.7),dict(at_tick=80,value=1.1)]),
                dict(property='transform.rotation',keyframes=[dict(at_tick=0,value=-20),dict(at_tick=80,value=35)])]
            b=clips(p)['marker']['tracking_binding'];b.update(scale_mode='roi',rotation_mode='source')
            expected=self.frames(p,s)
            after,plan=self.plan(p,action='extend_source',clip_id='source',head_tick=20,tail_tick=0)
            self.pixels_equal(self.frames(after,s)[2:10],expected[2:10])
            bound=clips(after)['marker']['tracking_binding']
            self.assertEqual(bound['reference_output_tick'],0)
            self.assertEqual(bound['source_fragments'],[dict(track_id='video',clip_id='source',author_offset_tick=20)])
            self.assertEqual(plan['source_changes'][0]['head_tick'],20)

    def test_fragment_specific_extension_and_repeated_split_keep_independent_reference_offsets(self):
        p,s,_=scene();source=clips(p)['source']
        source['keyframes']=[dict(property='transform.scale',keyframes=[dict(at_tick=0,value=.5),dict(at_tick=80,value=1.2)])]
        clips(p)['marker']['tracking_binding']['scale_mode']='roi'
        expected=self.frames(p,s)
        p,_=apply_operation(p,'main',dict(op='split_clip',clip_id='source',at_tick=40))
        p,_=self.plan(p,action='extend_source',clip_id='source_a',head_tick=20,tail_tick=0)
        p,_=apply_operation(p,'main',dict(op='split_clip',clip_id='source_a',at_tick=30))
        refs=clips(p)['marker']['tracking_binding']['source_fragments']
        self.assertEqual([r.get('author_offset_tick',0) for r in refs],[20,20,0])
        self.pixels_equal(self.frames(p,s)[2:10],expected[2:10])

    def test_repeated_real_head_extensions_accumulate_the_source_author_shift(self):
        p,s,_=scene();c=clips(p)['source'];c.update(timeline_start_tick=40,source_in_tick=40,source_out_tick=100,duration_tick=60)
        expected=self.frames(p,s)
        for head in (10,20):p,_=self.plan(p,action='extend_source',clip_id='source',head_tick=head,tail_tick=0)
        ref=clips(p)['marker']['tracking_binding']['source_fragments'][0]
        self.assertEqual(ref['author_offset_tick'],30)
        self.pixels_equal(self.frames(p,s)[4:],expected[4:])

    def test_target_video_extension_reanchors_base_opacity_and_keeps_existing_composite(self):
        p,s,_=scene();target=clips(p)['marker'];target.update(asset_id='a',timeline_start_tick=20,duration_tick=80,source_in_tick=20,source_out_tick=100)
        b=target['tracking_binding'];b['base'].update(opacity_keyframes=[dict(at_tick=0,value=.2),dict(at_tick=80,value=.9)])
        expected=self.frames(p,s)
        p,plan=self.plan(p,action='extend_source',clip_id='marker',head_tick=20,tail_tick=0)
        self.assertEqual([o['at_tick'] for o in clips(p)['marker']['tracking_binding']['base']['opacity_keyframes']],[20,100])
        self.assertEqual(plan['source_changes'][0]['shifted_binding_opacity_keys'],2)
        self.pixels_equal(self.frames(p,s)[2:],expected[2:])

    def test_freeze_and_scalar_speed_preserve_original_tracking_on_extension(self):
        for mode in ('freeze','speed','curve'):
            p,s,_=scene();source=clips(p)['source']
            if mode=='freeze':
                source.update(duration_tick=100,freeze=dict(at_tick=20,duration_tick=20))
                p['sequences'][0]['duration_tick']=120;clips(p)['marker'].update(duration_tick=120,source_out_tick=120)
            if mode=='speed':source.update(speed=2,duration_tick=40)
            if mode=='curve':source['speed_curve']=[dict(at_tick=0,speed=1),dict(at_tick=80,speed=1)]
            before=self.frames(p,s);p,_=self.plan(p,action='extend_source',clip_id='source',head_tick=10 if mode=='speed' else 20,tail_tick=0)
            self.pixels_equal(self.frames(p,s)[2:],before[2:])

    def test_nonzero_VFR_slip_uses_real_pts_and_observations_without_cfr_resnapping(self):
        from bisect import bisect_right
        p,s,positions=scene();old=s['a'];ticks=[1000]
        for i in range(19):ticks.append(ticks[-1]+(10 if i%2 else 15))
        durations=[b-a for a,b in zip(ticks,ticks[1:])]+[10]
        s['a']=fixture.source([old.fetch(i) for i in range(20)],pts=ticks,durations=durations,time_base='1/100',origin=10)
        binding=clips(p)['marker']['tracking_binding']
        for o,t in zip(binding['observations'],ticks):o['at_seconds']=(t-1000)/100
        binding['range']['end_seconds']=(ticks[-1]-1000+10)/100
        p['assets'][0]['probe']['duration_seconds']=binding['range']['end_seconds']
        p,_=self.plan(p,action='slip',clip_id='source',delta_source_tick=15)
        for i,(pixels,meta) in enumerate(self.frames(p,s)):
            if i<2:continue
            index=bisect_right(ticks,1000+i*10+15)-1;state=self.tracking(meta)
            self.assertEqual(state['native_frame_index'],index)
            self.assertEqual(state['native_pts'],ticks[index]);self.assertEqual(float(pixels[1,positions[index],0]),1.)

    def test_piecewise_hold_curve_inverse_is_exact_at_source_frame_boundaries(self):
        for reverse in (False,True):
            p,s,_=scene();c=clips(p)['source'];c['reverse']=reverse
            c['speed_curve']=[dict(at_tick=0,speed=1,interpolation='hold'),dict(at_tick=40,speed=2,interpolation='hold'),dict(at_tick=80,speed=2)]
            host=FloatTimeline(p,'main',s,working_signal=fixture.LINEAR)
            for elapsed in range(81):
                normalized=F((80-elapsed if reverse else elapsed)*60,80)
                expected=20+(normalized if normalized<=40 else 40+(normalized-40)*2)
                actual,_,_=host._source_time(c,F(elapsed),'main/source')
                self.assertEqual(actual,expected/100)

    def test_chained_bound_video_head_extension_keeps_downstream_reference_and_all_pixels(self):
        p,s,_=scene();seq=p['sequences'][0];marker=clips(p)['marker']
        carrier=copy.deepcopy(marker);carrier.update(id='carrier',asset_id='a',timeline_start_tick=20,duration_tick=80,source_in_tick=20,source_out_tick=100)
        carrier['tracking_binding']['base']['scale']=.6
        seq['tracks'].insert(1,dict(id='carrier_track',kind='overlay',order=1,clips=[carrier]));seq['tracks'][-1]['order']=2
        marker['tracking_binding'].update(source_track_id='carrier_track',source_clip_id='carrier',scale_mode='roi',rotation_mode='source')
        before=self.frames(p,s);p,_=self.plan(p,action='extend_source',clip_id='carrier',head_tick=20,tail_tick=0)
        self.assertEqual(clips(p)['marker']['tracking_binding']['source_fragments'][0]['author_offset_tick'],20)
        self.pixels_equal(self.frames(p,s)[2:],before[2:])

    def test_source_handle_roll_extends_one_fragment_without_replacing_observations(self):
        p,s,_=scene();source=clips(p)['source'];source.update(duration_tick=40,source_out_tick=60)
        right=copy.deepcopy(source);right.update(id='right',timeline_start_tick=60,source_in_tick=60,source_out_tick=100)
        p['sequences'][0]['tracks'][0]['clips'].append(right)
        b=clips(p)['marker']['tracking_binding'];b['source_fragments']=[dict(track_id='video',clip_id=k) for k in ('source','right')]
        expected=self.frames(p,s)
        p,plan=self.plan(p,action='roll',left_clip_id='source',right_clip_id='right',delta_tick=10,handle_policy='source',options={'linked':False})
        self.pixels_equal(self.frames(p,s)[2:10],expected[2:10]);self.assertTrue(plan['source_changes'])

    def test_invalid_offsets_and_existing_physical_or_legacy_guards(self):
        p,s,_=scene();p,_=self.plan(p,action='extend_source',clip_id='source',head_tick=10,tail_tick=0)
        for invalid in (-1,True,.5,2**53):
            bad=copy.deepcopy(p);target=clips(bad)['marker'];target['tracking_binding']['source_fragments'][0]['author_offset_tick']=invalid
            with self.assertRaises(AppError):validate_binding(bad,bad['sequences'][0],bad['sequences'][0]['tracks'][1],target)
        for request,code in [(dict(action='slip',clip_id='source',delta_source_tick=200),'SOURCE_EDIT_HANDLE_SHORTFALL'),
            (dict(action='extend_source',clip_id='source',head_tick=100,tail_tick=0),'EDIT_RANGE_EMPTY_SIDE')]:
            old=copy.deepcopy(p)
            with self.assertRaises(AppError) as caught:build_range_plan(p,'main',request)
            self.assertEqual(caught.exception.code,code);self.assertEqual(p,old)
        legacy=copy.deepcopy(p);legacy['settings'].pop('pixel_pipeline')
        with self.assertRaises(AppError) as caught:build_range_plan(legacy,'main',dict(action='slip',clip_id='source',delta_source_tick=1))
        self.assertEqual(caught.exception.code,'EDIT_RANGE_BINDING_UNSUPPORTED')

if __name__=='__main__':unittest.main()
