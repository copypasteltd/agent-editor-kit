"""Independent alpha/geometry/time oracles for the real Float32 transition host."""
import copy
import math
import unittest
from fractions import Fraction as F
import numpy as np
from ai_ad_editor.errors import AppError
from ai_ad_editor.float_transitions import TYPES, resolve, transition_rgba
from ai_ad_editor.float_timeline import FloatTimeline
from test_float_timeline import LINEAR, SHA, rgba, source, clip, project, track


class FloatTransitionKernelTests(unittest.TestCase):
    def code(self, code, function):
        with self.assertRaises(AppError) as caught: function()
        self.assertEqual(caught.exception.code, 'FLOAT_TRANSITION_'+code)

    def test_crossfade_is_premultiplied_not_double_source_over(self):
        a,b=rgba((1,0,0,.25)),rgba((0,0,1,.75))
        result,metadata=transition_rgba(a,b,.5)
        np.testing.assert_array_equal(result,rgba((.25,0,.75,.5)))
        self.assertIn('premultiplied',metadata['alpha'])
        np.testing.assert_array_equal(a,rgba((1,0,0,.25)))

    def test_hidden_colour_cannot_bleed_at_endpoints_or_spatial_motion(self):
        a=rgba((999,-200,80,0));b=rgba((0,.5,0,.6))
        for kind in sorted(TYPES):
            for progress in (0.,.37,1.):
                with self.subTest(kind=kind,progress=progress):
                    value,_=transition_rgba(a,b,progress,kind=kind)
                    self.assertTrue(np.isfinite(value).all())
                    self.assertTrue(np.all(value[:,:,3]>=0) and np.all(value[:,:,3]<=1))
                    self.assertTrue(np.all(value[value[:,:,3]==0,:3]==0))
                    # Opaque black/white mattes can add equal RGB; no red/blue poison.
                    self.assertLessEqual(float(np.abs(value[:,:,0]-value[:,:,2]).max()),1e-7)

    def test_full_catalogue_is_not_a_fade_alias_and_tiles_are_invariant(self):
        rng=np.random.default_rng(9713)
        a=rng.random((19,37,4),dtype=np.float32);b=rng.random((19,37,4),dtype=np.float32)
        for kind in sorted(TYPES):
            with self.subTest(kind=kind):
                first,_=transition_rgba(a,b,.371,kind=kind,tile_pixels=17)
                second,_=transition_rgba(a,b,.371,kind=kind,tile_pixels=262144)
                np.testing.assert_array_equal(first,second)
                if kind!='fade':
                    fade,_=transition_rgba(a,b,.371)
                    self.assertGreater(float(np.max(np.abs(first-fade))),.001)
                for progress,expected in ((0.,a),(1.,b)):
                    value,_=transition_rgba(a,b,progress,kind=kind)
                    np.testing.assert_array_equal(value,expected)

    def test_wipe_geometry_matches_explicit_integer_columns_and_rows(self):
        a,b=rgba(),rgba((0,0,1,1))
        for kind,selected in (
            ('wipeleft',np.indices((4,8))[1]<=4),('wiperight',np.indices((4,8))[1]>4),
            ('wipeup',np.indices((4,8))[0]<=2),('wipedown',np.indices((4,8))[0]>2),
            ('wipetr',(np.indices((4,8))[0]<=2)&(np.indices((4,8))[1]>4))):
            value,_=transition_rgba(a,b,.5,kind=kind)
            np.testing.assert_array_equal(value,np.where(selected[:,:,None],a,b))

    def test_slide_cover_reveal_move_actual_distinct_pixels(self):
        a=rgba();b=rgba();a[:,:,0]=np.arange(8)[None,:]/8;b[:,:,0]=(np.arange(8)[None,:]+8)/16
        for kind in ('slideleft','coverleft','revealleft'):
            value,_=transition_rgba(a,b,.5,kind=kind)
            expected=rgba()
            for x in range(8):
                shifted=x-4
                if kind=='slideleft':expected[:,x]=(b if shifted>=0 else a)[:,shifted%8]
                elif kind=='coverleft':expected[:,x]=b[:,shifted%8] if shifted>=0 else a[:,x]
                else:expected[:,x]=b[:,x] if shifted>=0 else a[:,shifted%8]
            np.testing.assert_array_equal(value,expected)

    def test_forward_blur_matches_direct_mean_including_shrinking_right_edge(self):
        rng=np.random.default_rng(22);a=rng.random((3,23,4),dtype=np.float32);b=rng.random(a.shape,dtype=np.float32)
        value,_=transition_rgba(a,b,.4,kind='hblur',tile_pixels=5)
        expected=np.empty_like(value);size=1+int(11*.8)
        for y in range(3):
            for x in range(23):
                pm=[]
                for image in (a,b):
                    window=image[y,x:min(23,x+size)].astype(np.float64)
                    window[:,:3]*=window[:,3:4];pm.append(window.mean(axis=0))
                mixed=.6*pm[0]+.4*pm[1]
                expected[y,x,3]=mixed[3];expected[y,x,:3]=mixed[:3]/mixed[3]
        np.testing.assert_allclose(value,expected,rtol=0,atol=3e-8)

    def test_dip_uses_exact_odd_frame_cut_fraction(self):
        a,b=rgba((1,0,0,.3)),rgba((0,0,1,.8))
        for kind,matte in (('dip_black',(0,0,0,1)),('dip_white',(1,1,1,1))):
            value,_=transition_rgba(a,b,F(1,3),kind=kind,cut_fraction=F(1,3))
            np.testing.assert_array_equal(value,rgba(matte))
            value,_=transition_rgba(a,b,F(2,3),kind=kind,cut_fraction=F(1,3))
            # At 2/3 the matte-to-B phase is exactly half complete.
            pm=np.asarray(matte,np.float64)*.5+np.array([0,0,.8,.8])*.5
            expected=np.r_[pm[:3]/pm[3],pm[3]].astype(np.float32)
            np.testing.assert_allclose(value,rgba(expected),rtol=0,atol=6e-8)

    def test_extended_rgb_is_preserved_and_fast_slow_have_explicit_domain(self):
        a,b=rgba((-3,4,2,.25)),rgba((5,-2,3,.75))
        value,_=transition_rgba(a,b,.5)
        np.testing.assert_array_equal(value,rgba((3,-.5,2.75,.5)))
        for kind in ('fadefast','fadeslow'):
            self.code('DOMAIN',lambda:transition_rgba(a,b,.5,kind=kind))

    def test_all_pixels_validated_even_at_endpoint_or_unselected_wipe_corner(self):
        a,b=rgba(),rgba();b[-1,-1,0]=np.nan
        for progress in (0.,.1,1.):
            self.code('VALUES',lambda:transition_rgba(a,b,progress,kind='wipeleft',tile_pixels=1))
        b=rgba();b[-1,-1,3]=1.1
        self.code('VALUES',lambda:transition_rgba(a,b,.5,tile_pixels=1))

    def test_budget_preflight_and_cancellation_preserve_both_inputs(self):
        a,b=rgba(),rgba((0,0,1,1));before=(a.copy(),b.copy())
        self.code('BUDGET',lambda:transition_rgba(a,b,.5,max_working_bytes=100))
        polls=[]
        def cancel():
            polls.append(1)
            if len(polls)==9:raise RuntimeError('cancelled during validation')
        with self.assertRaisesRegex(RuntimeError,'cancelled'):transition_rgba(a,b,.5,tile_pixels=1,cancel=cancel)
        np.testing.assert_array_equal(a,before[0]);np.testing.assert_array_equal(b,before[1])

    def test_cancellation_after_validation_during_pixel_production(self):
        a,b=rgba(),rgba((0,0,1,1));calls=[]
        def cancel():
            calls.append(1)
            if len(calls)==70:raise RuntimeError('pixel production cancelled')
        with self.assertRaisesRegex(RuntimeError,'pixel production cancelled'):
            transition_rgba(a,b,.37,kind='slideleft',tile_pixels=1,cancel=cancel)
        self.assertEqual(len(calls),70)
        np.testing.assert_array_equal(a,rgba());np.testing.assert_array_equal(b,rgba((0,0,1,1)))

    def test_aliases_and_invalid_options_do_not_select_unrelated_effects(self):
        for value,expected in (({'type':'dissolve'},'fade'),({'type':'wipe','direction':'up'},'wipeup'),
                               ({'type':'slide_left'},'slideleft'),({'type':'custom','source_type':'dip_white'},'dip_white')):
            self.assertEqual(resolve(value),expected)
        self.code('CONFIG',lambda:resolve({'type':'wipe','direction':'elsewhere'}))
        self.code('TYPE',lambda:resolve({'type':'made-up'}))
        for progress in (True,float('nan'),-.1,1.1):
            self.code('PROGRESS',lambda:transition_rgba(rgba(),rgba(),progress))


class FloatTransitionTimelineTests(unittest.TestCase):
    def host(self,p,s):return FloatTimeline(p,'main',s,working_signal=LINEAR)

    def overlap(self,kind='dissolve'):
        a=clip('first','a');a.update(duration_tick=100,transition_out={'type':kind,'duration':.4})
        b=clip('second','b');b.update(timeline_start_tick=60,transition_in={'type':kind,'duration':.4})
        p=project([a,b],duration=160,assets=[{'id':v,'kind':'video','sha256':SHA} for v in ('a','b')])
        return p,{'a':source([rgba((1,0,0,.25))]*10),'b':source([rgba((0,0,1,.75))]*10)}

    def handles(self,kind='dissolve',duration=30):
        a,b=clip('first','a'),clip('second','b')
        a.update(source_in_tick=30,source_out_tick=130)
        b.update(timeline_start_tick=100,source_in_tick=30,source_out_tick=130)
        p=project([a,b],duration=200,assets=[{'id':v,'kind':'video','sha256':SHA,'probe':{'duration_seconds':2}} for v in ('a','b')])
        p['sequences'][0]['source_transitions']=[{'id':'cut','type':kind,'duration_tick':duration,
            'from_clip_id':'first','to_clip_id':'second','audio_pairs':[]}]
        frames=[rgba((i/20,0,0,1)) for i in range(20)]
        return p,{'a':source(frames),'b':source([rgba((0,0,i/20,1)) for i in range(20)])}

    def test_overlap_composites_once_and_keeps_authored_project_unchanged(self):
        p,s=self.overlap();before=copy.deepcopy(p);h=self.host(p,s)
        value,metadata=h.render_frame(8)
        np.testing.assert_array_equal(value,rgba((.25,0,.75,.5)))
        self.assertEqual(p,before);self.assertEqual(h.project,before)
        self.assertEqual(len(metadata['layers']),2)
        self.assertEqual(metadata['layers'][0]['paired_transition']['author_progress'],'1/2')

    def test_actual_handle_samples_and_original_keyframe_clock(self):
        p,s=self.handles()
        p['sequences'][0]['tracks'][0]['clips'][1]['keyframes']=[{'property':'opacity','keyframes':[
            {'at_tick':0,'value':.5},{'at_tick':100,'value':1.,'interpolation':'linear'}]}]
        before=copy.deepcopy(p);h=self.host(p,s)
        _,metadata=h.render_frame(9)
        row=next(r for r in metadata['layers'] if r['clip'].endswith('/second'))
        self.assertEqual(row['source_time'],'1/5');self.assertEqual(row['author_animation_tick'],'-10')
        self.assertEqual(row['opacity'],.5);self.assertEqual(row['native_frame_index'],2)
        self.assertTrue(row['paired_transition']['real_source_handles'])
        self.assertEqual(h.project,before);self.assertEqual(p,before)

    def test_odd_three_frame_dip_reaches_matte_at_original_cut(self):
        p,s=self.handles('dip_white');value,metadata=self.host(p,s).render_frame(10)
        np.testing.assert_array_equal(value,rgba((1,1,1,1)))
        self.assertEqual(metadata['layers'][0]['paired_transition']['cut_fraction'],1/3)

    def test_short_native_coverage_rejects_instead_of_freezing_or_transparency(self):
        p,s=self.handles();s['a']=source([rgba()]*10)
        h=self.host(p,s)
        with self.assertRaises(AppError) as caught:h.render_frame(10)
        self.assertEqual(caught.exception.code,'FLOAT_TIMELINE_SOURCE_HANDLE_COVERAGE')

    def test_reverse_real_handles_select_correct_native_right_edges(self):
        p,s=self.handles()
        for c in p['sequences'][0]['tracks'][0]['clips']:c['reverse']=True
        value,metadata=self.host(p,s).render_frame(10)
        for row in metadata['layers']:
            self.assertTrue(row['right_edge'])
        self.assertEqual(metadata['layers'][0]['native_frame_index'],2)
        self.assertEqual(metadata['layers'][1]['native_frame_index'],12)

    def test_group_wipe_fade_and_slide_use_child_canvas_and_author_clock(self):
        for kind in ('wipe','slide','fade'):
            p=project(duration=100);child=copy.deepcopy(p['sequences'][0]);child['id']='child';p['sequences'].append(child)
            parent=p['sequences'][0]['tracks'][0]['clips'][0]
            parent.pop('asset_id');parent.update(sequence_id='child',transition_in={'type':kind,'duration':.4,'direction':'left'})
            h=self.host(p,{'a':source([rgba()]*10)})
            first,meta=h.render_frame(0);last,_=h.render_frame(4)
            np.testing.assert_array_equal(first,rgba((0,0,0,0)));np.testing.assert_array_equal(last,rgba())
            middle,meta=h.render_frame(2);self.assertLess(float(middle[:,:,3].mean()),1.)
            self.assertIn('edge_transitions',meta['layers'][-1])

    def test_nested_reverse_propagates_left_limit_through_transition_cut(self):
        p,s=self.overlap('wipe');child=copy.deepcopy(p['sequences'][0]);child['id']='child'
        p['sequences'].append(child)
        parent=clip('parent');parent.pop('asset_id');parent.update(sequence_id='child',duration_tick=160,source_out_tick=160,reverse=True)
        p['sequences'][0]['tracks'][0]['clips']=[parent]
        h=self.host(p,s)
        _,meta=h.render_frame(8)
        members=[r for r in meta['layers'] if 'paired_transition' in r]
        self.assertEqual(len(members),2)
        self.assertTrue(members[0]['paired_transition']['left_limit'])
        self.assertEqual(members[0]['paired_transition']['author_progress'],'1/2')

    def test_trimmed_parent_enters_the_original_transition_halfway(self):
        p,s=self.overlap();child=copy.deepcopy(p['sequences'][0]);child['id']='child';p['sequences'].append(child)
        parent=clip('parent');parent.pop('asset_id')
        parent.update(sequence_id='child',duration_tick=60,source_out_tick=160,
            presentation_window={'version':1,'authored_start_tick':0,'authored_duration_tick':160,'offset_tick':80})
        p['sequences'][0].update(duration_tick=60);p['sequences'][0]['tracks'][0]['clips']=[parent]
        value,meta=self.host(p,s).render_frame(0)
        np.testing.assert_array_equal(value,rgba((.25,0,.75,.5)))
        self.assertEqual(meta['layers'][0]['paired_transition']['author_progress'],'1/2')

    def test_parent_freeze_holds_a_completed_transition_not_individual_endpoints(self):
        p,s=self.overlap();child=copy.deepcopy(p['sequences'][0]);child['id']='child';p['sequences'].append(child)
        parent=clip('parent');parent.pop('asset_id')
        parent.update(sequence_id='child',duration_tick=180,source_out_tick=160,freeze={'at_tick':80,'duration_tick':20})
        p['sequences'][0].update(duration_tick=180);p['sequences'][0]['tracks'][0]['clips']=[parent]
        h=self.host(p,s)
        for frame in (8,9,10):
            value,_=h.render_frame(frame)
            np.testing.assert_array_equal(value,rgba((.25,0,.75,.5)))

    def test_nonlinear_parent_uses_closed_form_child_transition_progress(self):
        for reverse in (False,True):
            p,s=self.overlap();child=copy.deepcopy(p['sequences'][0]);child['id']='child';p['sequences'].append(child)
            parent=clip('parent');parent.pop('asset_id')
            parent.update(sequence_id='child',source_out_tick=160,reverse=reverse,
                speed_curve={'keyframes':[{'at_tick':0,'speed':1},{'at_tick':160,'speed':3}]})
            p['sequences'][0].update(duration_tick=100);p['sequences'][0]['tracks'][0]['clips']=[parent]
            h=self.host(p,s)
            for frame in range(10):
                t=1-frame/10 if reverse else frame/10
                child_time=.8*(3**t-1)
                q=min(1,max(0,(child_time-.6)/.4))
                alpha=(1-q)*.25+q*.75
                want=rgba(((1-q)*.25/alpha,0,q*.75/alpha,alpha))
                value,_=h.render_frame(frame)
                np.testing.assert_allclose(value,want,rtol=0,atol=6e-8)

    def test_vfr_real_handles_select_original_native_holds(self):
        p,s=self.handles()
        pts=[0,20,40,80,120,170]
        for asset,colour in (('a',lambda i:(i/6,0,0,1)),('b',lambda i:(0,0,i/6,1))):
            s[asset]=source([rgba(colour(i)) for i in range(6)],pts=pts,durations=[20,20,40,40,50,30])
        _,meta=self.host(p,s).render_frame(10)
        self.assertEqual([r['native_frame_index'] for r in meta['layers']],[4,1])
        self.assertEqual([r['source_time'] for r in meta['layers']],['13/10','3/10'])

    def test_chained_real_handle_windows_are_independent_and_do_not_ripple(self):
        p,s=self.handles();third=clip('third','c');third.update(timeline_start_tick=200,source_in_tick=30,source_out_tick=130)
        seq=p['sequences'][0];seq['duration_tick']=300;seq['tracks'][0]['clips'].append(third)
        seq['source_transitions'].append({'id':'cut2','type':'slide_up','duration_tick':40,'from_clip_id':'second','to_clip_id':'third','audio_pairs':[]})
        p['assets'].append({'id':'c','kind':'video','sha256':SHA,'probe':{'duration_seconds':2}});s['c']=source([rgba((0,1,0,1))]*20)
        before=copy.deepcopy(p);h=self.host(p,s)
        self.assertEqual(h.frame_count,30)
        for frame,tid in ((10,'cut'),(20,'cut2')):
            _,meta=h.render_frame(frame)
            self.assertEqual(meta['layers'][0]['paired_transition']['id'],tid)
        self.assertEqual(p,before)

    def test_conflicting_pair_duration_and_auto_cloning_are_rejected(self):
        p,s=self.overlap();p['sequences'][0]['tracks'][0]['clips'][1]['transition_in']['duration']=.3
        with self.assertRaises(AppError) as caught:self.host(p,s)
        self.assertEqual(caught.exception.code,'FLOAT_TRANSITION_WINDOW')
        p,s=self.overlap();p['sequences'][0]['tracks'][0]['clips'][1]['timeline_start_tick']=100
        p['sequences'][0]['tracks'][0]['clips'][1]['transition_in']['auto_handle']=True
        with self.assertRaises(AppError) as caught:self.host(p,s)
        self.assertEqual(caught.exception.code,'FLOAT_TRANSITION_HANDLE_POLICY')


if __name__=='__main__':unittest.main()
