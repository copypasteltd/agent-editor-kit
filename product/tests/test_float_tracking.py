"""Native tracking pixels/clocks against authored positions and independent geometry."""
import copy
from fractions import Fraction as F
import math
import unittest
from unittest.mock import patch

import numpy as np

from ai_ad_editor.bindings import make_binding,validate_binding,bake_interchange_bindings
from ai_ad_editor.errors import AppError
from ai_ad_editor.float_timeline import FloatTimeline
from ai_ad_editor.float_tracking import binding_plan
import test_float_timeline as fixture


def scene(count=10):
    positions=[1+i%6 for i in range(count)]
    frames=[]
    for x in positions:
        image=fixture.rgba((0,0,0,1));image[1,x]=[0,1,0,1];frames.append(image)
    source=fixture.clip('source');marker=fixture.clip('marker','marker');marker['transform']={'scale':.25}
    tracks=[fixture.track([source]),dict(id='labels',kind='overlay',order=1,clips=[marker])]
    p=fixture.project(tracks=tracks)
    p['settings']['pixel_pipeline']={'engine':'float32-native-v1'}
    p['assets'][0]['probe']={'video':{'width':8,'height':4,'fps':'10'},'streams':[dict(codec_type='video',
        avg_frame_rate='10/1',r_frame_rate='10/1',sample_aspect_ratio='1:1',start_time='0')]}
    p['assets'].append(dict(id='marker',kind='image',sha256=fixture.SHA))
    observed=dict(source_sha256=fixture.SHA,range=dict(start_seconds=0,end_seconds=count/10),
        frames=[dict(at_seconds=i/10,x=(x+.5)/8,y=1.5/4,width=.125,height=.25,confidence=1.) for i,x in enumerate(positions)])
    seq=p['sequences'][0]
    marker['tracking_binding']=make_binding(p,seq,tracks[0],source,tracks[1],marker,observed,
        offset_x=0,offset_y=0,scale_mode='none',scale_multiplier=1,rotation_mode='none')
    sources={'a':fixture.source(frames),'marker':fixture.source(fixture.rgba((1,0,0,1),(1,1)),still=True,durations=[0])}
    return p,sources,positions,source,marker


class FloatTrackingTests(unittest.TestCase):
    def host(self,p,s):return FloatTimeline(p,'main',s,working_signal=fixture.LINEAR)
    def row(self,meta):return next(r for r in meta['layers'] if r['clip'].endswith('/marker'))

    def test_actual_marker_pixels_follow_every_original_CFR_frame_without_mutating_authoring(self):
        p,s,positions,source,marker=scene();before=copy.deepcopy(p);h=self.host(p,s)
        for i,x in enumerate(positions):
            pixels,meta=h.render_frame(i);want=fixture.rgba((0,0,0,1));want[1,x]=[1,0,0,1]
            np.testing.assert_array_equal(pixels,want)
            state=self.row(meta)['tracking'];self.assertEqual(state['native_frame_index'],i)
            self.assertEqual(F(state['native_time']),F(i,10))
        self.assertEqual(p,before);self.assertFalse(h.metadata['tracking']['display_keyframes_baked'])

    def test_VFR_and_nonzero_demux_origin_hold_anchor_on_the_selected_video_frame(self):
        p,s,positions,source,marker=scene(3)
        s['a']=fixture.source([s['a'].fetch(i) for i in range(3)],pts=[1000,1002,1007],durations=[2,5,3],time_base='1/10',origin=100)
        for row,at in zip(marker['tracking_binding']['observations'],(0,.2,.7)):row['at_seconds']=at
        marker['tracking_binding']['range']['end_seconds']=1
        stream=p['assets'][0]['probe']['streams'][0];stream.update(avg_frame_rate='3/1',r_frame_rate='10/1',start_time='100')
        h=self.host(p,s)
        for i,want in enumerate([0,0,1,1,1,1,1,2,2,2]):
            pixels,meta=h.render_frame(i);self.assertEqual(self.row(meta)['tracking']['native_frame_index'],want)
            self.assertEqual(float(pixels[1,positions[want],0]),1.)
        with self.assertRaises(AppError):validate_binding(p,p['sequences'][0],p['sequences'][0]['tracks'][1],marker,native_clock=False)

    def test_partial_native_index_and_clocks_above_float64_integer_precision(self):
        p,s,positions,source,marker=scene(3);first=2**53+1
        s['a']=fixture.source([s['a'].fetch(i) for i in range(3)],pts=[first+i*3 for i in range(3)],durations=[3]*3,
            time_base='1/100',origin=F(first,100),start=47)
        p['settings']['timebase']['display_fps']={'num':100,'den':3};p['sequences'][0]['duration_tick']=9
        for c in (source,marker):c.update(duration_tick=9,source_out_tick=9)
        for row,at in zip(marker['tracking_binding']['observations'],(0,.03,.06)):row['at_seconds']=at
        marker['tracking_binding']['range']['end_seconds']=.09;h=self.host(p,s)
        for i in range(3):
            _,meta=h.render_frame(i);r=self.row(meta)['tracking']
            self.assertEqual(r['native_frame_index'],47+i);self.assertEqual(r['native_pts'],first+i*3)
            self.assertEqual(F(r['native_time']),F(i*3,100))

    def test_reverse_source_uses_original_half_open_selected_frame(self):
        p,s,positions,source,marker=scene();source['reverse']=True;h=self.host(p,s)
        for i in range(10):
            pixels,meta=h.render_frame(i);r=self.row(meta)['tracking']
            self.assertEqual(r['native_frame_index'],9-i);self.assertEqual(float(pixels[1,positions[9-i],0]),1.)

    def test_scalar_and_curve_retime_preserve_video_tracking_frame_identity(self):
        p,s,_,source,marker=scene();source['speed']=2
        for c in (source,marker):c['duration_tick']=50
        p['sequences'][0]['duration_tick']=50;h=self.host(p,s)
        for i in range(5):self.assertEqual(self.row(h.render_frame(i)[1])['tracking']['native_frame_index'],2*i)
        p,s,_,source,marker=scene(20);source['source_out_tick']=200
        source['speed_curve']={'keyframes':[{'at_tick':0,'speed':1},{'at_tick':200,'speed':3}]};h=self.host(p,s)
        for i in range(10):
            meta=h.render_frame(i)[1];want=min(19,math.floor((3**(i/10)-1)*10+1e-12))
            self.assertEqual(self.row(meta)['tracking']['native_frame_index'],want)

    def test_freeze_keeps_source_frame_but_retains_continuous_author_geometry_clock(self):
        p,s,_,source,marker=scene();source.update(duration_tick=150,freeze={'at_tick':40,'duration_tick':50},
            keyframes=[dict(property='transform.position.y',keyframes=[dict(at_tick=0,value=.5),dict(at_tick=150,value=.75)])])
        marker.update(duration_tick=150,source_out_tick=150);p['sequences'][0]['duration_tick']=150;h=self.host(p,s)
        for i in range(15):
            state=self.row(h.render_frame(i)[1])['tracking'];want=i if i<4 else 4 if i<9 else i-5
            self.assertEqual(state['native_frame_index'],want)
            self.assertAlmostEqual(state['values']['position.y'],.375+i/15*.25)

    def test_crop_stretch_rotation_and_half_pixel_anchor_match_independent_forward_geometry(self):
        p,s,_,source,marker=scene();source['crop']={'unit':'pixels','x':0,'y':0,'width':4,'height':4,'fit':'stretch'}
        source['transform']={'rotation':90,'scale':.5};h=self.host(p,s)
        state=self.row(h.render_frame(0)[1])['tracking']
        self.assertAlmostEqual(state['values']['position.x'],4.25/8)
        self.assertAlmostEqual(state['values']['position.y'],1.5/4)
        self.assertAlmostEqual(state['roi_width_pixels'],1.)
        self.assertTrue(state['inside_crop'])
        hidden=self.row(h.render_frame(4)[1])['tracking'];self.assertFalse(hidden['active']);self.assertEqual(hidden['values']['opacity'],0)

    def test_animated_crop_uses_the_same_author_rounding_and_visibility_as_pixels(self):
        p,s,positions,source,marker=scene();source['crop']={'unit':'pixels','x':0,'y':0,'width':4,'height':4,'fit':'stretch',
            'keyframes':[dict(property='x',keyframes=[dict(at_tick=0,value=0),dict(at_tick=100,value=4)])]}
        h=self.host(p,s)
        for i,x in enumerate(positions):
            state=self.row(h.render_frame(i)[1])['tracking'];origin=round(i*.4)
            self.assertAlmostEqual(state['values']['position.x'],(x+.5-origin)/4)
            self.assertEqual(state['active'],origin<=x+.5<origin+4)

    def test_binding_base_opacity_and_source_blend_are_applied_once(self):
        p,s,_,source,marker=scene();source['transform']={'opacity':.5};source['blend']={'opacity':.4}
        marker['tracking_binding']['base']['opacity']=.75;h=self.host(p,s)
        self.assertAlmostEqual(self.row(h.render_frame(0)[1])['opacity'],.75*.5*.4)
        marker['tracking_binding']['base']['opacity_keyframes']=[dict(at_tick=0,value=0),dict(at_tick=100,value=1)]
        h=self.host(p,s);self.assertAlmostEqual(self.row(h.render_frame(5)[1])['opacity'],.5*.5*.4)

    def test_roi_and_rotation_reference_is_deterministic_when_previewed_out_of_order(self):
        p,s,_,source,marker=scene();source['keyframes']=[dict(property='transform.scale',keyframes=[dict(at_tick=0,value=1),dict(at_tick=100,value=2)]),
            dict(property='transform.rotation',keyframes=[dict(at_tick=0,value=0),dict(at_tick=100,value=90)])]
        b=marker['tracking_binding'];b['scale_mode']='roi';b['rotation_mode']='source';h=self.host(p,s)
        state=self.row(h.render_frame(5)[1])['tracking'];self.assertAlmostEqual(state['values']['scale'],.375)
        self.assertAlmostEqual(state['values']['rotation'],45)
        self.assertAlmostEqual(self.row(h.render_frame(0)[1])['tracking']['values']['scale'],.25)
        h2=self.host(p,s);h2.render_frame(0);self.assertEqual(self.row(h2.render_frame(5)[1])['tracking']['values'],state['values'])

    def test_saved_binding_windows_retain_original_source_and_ROI_reference_clocks(self):
        p,s,_,source,marker=scene();source['keyframes']=[dict(property='transform.scale',keyframes=[dict(at_tick=0,value=1),dict(at_tick=100,value=2)])]
        marker['tracking_binding']['scale_mode']='roi'
        for c in (source,marker):c.update(duration_tick=40,presentation_window=dict(version=1,authored_start_tick=0,authored_duration_tick=100,offset_tick=30))
        p['sequences'][0]['duration_tick']=40;h=self.host(p,s)
        state=self.row(h.render_frame(0)[1])['tracking']
        self.assertEqual(state['native_frame_index'],3);self.assertEqual(F(state['source_author_tick']),30)
        self.assertAlmostEqual(state['values']['scale'],.25*1.3)

    def test_nested_reverse_and_double_reverse_use_child_canvas_once(self):
        for reverse,want in ((False,list(reversed(range(10)))),(True,list(range(10)))):
            p,s,_,source,marker=scene();source['reverse']=reverse;child=p['sequences'][0];child['id']='child';child['canvas']={'width':8,'height':4}
            p['settings']['canvas'].update(width=16,height=8)
            parent=fixture.clip('group');parent.pop('asset_id');parent.update(sequence_id='child',reverse=True)
            p['sequences'].insert(0,dict(id='main',duration_tick=100,tracks=[fixture.track([parent])]))
            h=self.host(p,s)
            for i,index in enumerate(want):self.assertEqual(self.row(h.render_frame(i)[1])['tracking']['native_frame_index'],index)

    def test_muted_source_hides_target_without_fetching_or_requiring_a_provider(self):
        p,s,_,source,marker=scene();p['sequences'][0]['tracks'][0]['muted']=True;s.pop('a');h=self.host(p,s)
        image,meta=h.render_frame(0);self.assertEqual(self.row(meta)['opacity'],0)
        self.assertEqual(float(image[...,3].max()),0)

    def test_observed_range_and_source_window_never_bind_outside_visible_source(self):
        p,s,_,source,marker=scene();b=marker['tracking_binding'];b['range'].update(start_seconds=.2,end_seconds=.8)
        b['observations']=b['observations'][2:8];h=self.host(p,s)
        for i in range(10):self.assertEqual(self.row(h.render_frame(i)[1])['tracking']['active'],2<=i<8)
        source['source_out_tick']=50;h=self.host(p,s)
        for i in range(5,10):self.assertFalse(self.row(h.render_frame(i)[1])['tracking']['active'])

    def test_declarative_plan_does_not_bake_CFR_keys_or_execute_inference(self):
        p,s,_,source,marker=scene();before=copy.deepcopy(p)
        plan=binding_plan(p,p['sequences'][0],p['sequences'][0]['tracks'][1],marker)
        self.assertEqual(plan['keyframes'],[]);self.assertEqual(plan['sampled_frames'],0);self.assertEqual(p,before)
        with self.assertRaises(AppError) as caught:bake_interchange_bindings(p)
        self.assertEqual(caught.exception.code,'TRACK_BIND_NATIVE_BAKE_REQUIRED')

    def test_invalid_identity_and_binding_budget_fail_before_pixel_fetch(self):
        p,s,_,source,marker=scene();marker['tracking_binding']['source_sha256']='sha256:'+'b'*64
        with self.assertRaises(AppError):self.host(p,s)
        p,s,_,source,marker=scene()
        with patch('ai_ad_editor.float_tracking.MAX_BINDINGS',0),self.assertRaises(AppError) as caught:self.host(p,s)
        self.assertEqual(caught.exception.code,'FLOAT_TRACKING_BUDGET')

    def test_chained_video_binding_projects_the_actual_bound_source_geometry_and_alpha(self):
        p,s,positions,source,marker=scene();seq=p['sequences'][0];tracks=seq['tracks']
        carrier=fixture.clip('carrier');carrier['transform']={'scale':.5,'opacity':.5}
        tracks.insert(1,dict(id='carrier_track',kind='overlay',order=1,clips=[carrier]));tracks[-1]['order']=2
        evidence=dict(source_sha256=fixture.SHA,range=copy.deepcopy(marker['tracking_binding']['range']),
            frames=copy.deepcopy(marker['tracking_binding']['observations']))
        carrier['tracking_binding']=make_binding(p,seq,tracks[0],source,tracks[1],carrier,evidence,
            offset_x=0,offset_y=0,scale_mode='none',scale_multiplier=1,rotation_mode='none')
        source['transform']={'opacity':.6}
        marker['tracking_binding']=make_binding(p,seq,tracks[1],carrier,tracks[2],marker,evidence,
            offset_x=0,offset_y=0,scale_mode='none',scale_multiplier=1,rotation_mode='none')
        h=self.host(p,s)
        for i,x in enumerate(positions):
            state=self.row(h.render_frame(i)[1])['tracking']
            self.assertAlmostEqual(state['values']['position.x'],1.5*(x+.5)/8-.25)
            self.assertAlmostEqual(state['values']['position.y'],1.5*1.5/4-.25)
            self.assertAlmostEqual(state['values']['opacity'],.6*.5)
            self.assertEqual(state['native_frame_index'],i)

    def test_chained_binding_cycle_is_rejected_before_any_native_frame_is_fetched(self):
        p,s,_,source,marker=scene();seq=p['sequences'][0];tracks=seq['tracks']
        carrier=fixture.clip('carrier');tracks[0]['clips'].append(carrier)
        evidence=dict(source_sha256=fixture.SHA,range=copy.deepcopy(marker['tracking_binding']['range']),
            frames=copy.deepcopy(marker['tracking_binding']['observations']))
        for target,origin in ((source,carrier),(carrier,source)):
            target['tracking_binding']=make_binding(p,seq,tracks[0],origin,tracks[0],target,evidence,
                offset_x=0,offset_y=0,scale_mode='none',scale_multiplier=1,rotation_mode='none')
        with patch.object(s['a'],'fetch',side_effect=AssertionError('must not fetch')),self.assertRaises(AppError) as caught:self.host(p,s)
        self.assertEqual(caught.exception.code,'FLOAT_TRACKING_CYCLE')


if __name__=='__main__':unittest.main()
