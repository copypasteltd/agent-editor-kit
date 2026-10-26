"""Actual alpha/masks and 59 kernels, with independent pixel-difference oracles."""
import copy
import math
import unittest
from fractions import Fraction as F
from unittest.mock import patch

import numpy as np

from ai_ad_editor.bindings import make_binding
from ai_ad_editor.errors import AppError
from ai_ad_editor.float_timeline import FloatTimeline
from ai_ad_editor.float_transitions import TYPES, transition_rgba
from ai_ad_editor.float_transition_trace import trace
from ai_ad_editor.float_transition_plan import edge_progress, pair_progress
from test_float_tracking import scene
import test_float_timeline as f

BUDGET=64*1024**2


class PointFootprintTests(unittest.TestCase):
    def trace(self,a,b,q,**options):
        return trace(a,b,q,max_working_bytes=BUDGET,cancel=lambda:None,**options)

    def test_all_59_kernels_both_branches_match_independent_public_alpha_differences(self):
        self.assertEqual(len(TYPES),59)
        a=f.rgba((.2,.3,.4,.25),(19,37));b=a.copy();points=[(16.25,9.5),(19.,7.)]
        # A binary-exact alpha perturbation large enough to resolve the
        # Float32 output boundary, while staying inside the same distance gate.
        yy,xx=np.indices(a.shape[:2]);epsilon=.5
        for kind in sorted(TYPES):
            for branch in (0,1):
                for q in (.25,.625):
                    with self.subTest(kind=kind,branch=branch,q=q):
                        rows,fields,_=self.trace(a,b,q,kind=kind,branch=branch,points=points,retain=True)
                        base=transition_rgba(a,b,q,kind=kind)[0][:,:,3].astype(np.float64)
                        for j,(px,py) in enumerate(points):
                            images=[a.copy(),b.copy()]
                            tent=np.maximum(0,1-np.abs(xx-px))*np.maximum(0,1-np.abs(yy-py))
                            images[branch][:,:,3]+=np.asarray(epsilon*tent*images[branch][:,:,3],np.float32)
                            altered=transition_rgba(*images,q,kind=kind)[0][:,:,3].astype(np.float64)
                            expected=(altered-base)/epsilon
                            np.testing.assert_allclose(fields[:,:,j],expected,rtol=0,atol=8e-7)
                            mass=expected.sum();self.assertAlmostEqual(rows[j]['mass'],mass,delta=2e-6)
                            if mass>0:
                                self.assertAlmostEqual(rows[j]['x'],float((expected*xx).sum()/mass),delta=2e-4)
                                self.assertAlmostEqual(rows[j]['y'],float((expected*yy).sum()/mass),delta=2e-4)

    def test_distance_decisions_use_real_RGBA_and_ignore_the_private_probe_lane(self):
        a=f.rgba((1,0,0,1));b=f.rgba((0,0,1,1))
        rows,_,_=self.trace(a,b,.5,kind='distance',branch=0,points=[(2,1)])
        self.assertEqual(rows[0]['mass'],0)
        rows,_,_=self.trace(a,a,.5,kind='distance',branch=0,points=[(2,1)])
        self.assertEqual(rows[0]['mass'],.5)

    def test_black_and_white_generated_mattes_do_not_fabricate_source_visibility(self):
        a=f.rgba();b=f.rgba((0,0,1,1))
        for kind in ('dip_black','dip_white','circlecrop','rectcrop'):
            for branch in (0,1):
                rows,_,_=self.trace(a,b,.5,kind=kind,branch=branch,points=[(1,1)])
                self.assertEqual(rows[0]['mass'],0)
                self.assertIsNone(rows[0]['x'])

    def test_slide_transports_the_point_and_fade_retains_position(self):
        a=f.rgba();b=f.rgba()
        for kind,want,mass in (('slideleft',1,1),('fade',5,.5)):
            rows,_,_=self.trace(a,b,.5,kind=kind,branch=0,points=[(5,1)])
            self.assertEqual(rows[0]['x'],want);self.assertEqual(rows[0]['y'],1)
            self.assertEqual(rows[0]['mass'],mass)

    def test_two_sampling_steps_retain_the_full_density_and_do_not_reseed_a_centroid(self):
        a=f.rgba((.2,.3,.4,.5),(9,31));empty=np.zeros_like(a);point=(13.25,4.5)
        _,density,_=self.trace(empty,a,.625,kind='hblur',branch=1,points=[point],retain=True)
        first=transition_rgba(empty,a,.625,kind='hblur')[0]
        rows,last,_=self.trace(first,a,.375,kind='slideleft',branch=0,density=density,retain=True)
        yy,xx=np.indices(a.shape[:2]);epsilon=.125;changed=a.copy()
        changed[:,:,3]+=np.asarray(epsilon*.5*np.maximum(0,1-np.abs(xx-point[0]))*np.maximum(0,1-np.abs(yy-point[1])),np.float32)
        changed_first=transition_rgba(empty,changed,.625,kind='hblur')[0]
        expected=(transition_rgba(changed_first,a,.375,kind='slideleft')[0][:,:,3].astype(np.float64)-
            transition_rgba(first,a,.375,kind='slideleft')[0][:,:,3].astype(np.float64))/epsilon
        np.testing.assert_allclose(last[:,:,0],expected,rtol=0,atol=6e-7)
        self.assertAlmostEqual(rows[0]['mass'],expected.sum(),delta=2e-6)

    def test_endpoints_hidden_alpha_and_inputs_are_unchanged(self):
        a=f.rgba((0,0,0,.5));b=f.rgba((1,1,1,.25));original=(a.copy(),b.copy())
        for q,branch,mass in ((0.,0,.5),(0.,1,0),(1.,0,0),(1.,1,.25)):
            rows,_,_=self.trace(a,b,q,kind='pixelize',branch=branch,points=[(2,1)])
            self.assertEqual(rows[0]['mass'],mass)
        np.testing.assert_array_equal(a,original[0]);np.testing.assert_array_equal(b,original[1])

    def test_invalid_surface_density_coordinates_budget_and_mid_tile_cancel_are_explicit(self):
        a=f.rgba();b=a.copy()
        for options in ({},{'points':[(math.nan,1)]},{'points':[(1,1)],'density':np.zeros((4,8,1))},
                        {'density':np.full((4,8,1),-1.)},{'points':[(1,1)],'branch':True}):
            args=dict(kind='fade',branch=0);args.update(options)
            with self.assertRaises(AppError):self.trace(a,b,.5,**args)
        with self.assertRaises(AppError) as caught:
            trace(a,b,.5,kind='fade',branch=0,points=[(1,1)],max_working_bytes=100,cancel=lambda:None)
        self.assertEqual(caught.exception.code,'FLOAT_TRACKING_TRACE_BUDGET')
        calls=[]
        def cancel():
            calls.append(1)
            if len(calls)==7:raise RuntimeError('trace cancelled')
        with patch('ai_ad_editor.float_transition_trace.TILE',1),self.assertRaisesRegex(RuntimeError,'trace cancelled'):
            trace(a,b,.5,kind='slideleft',branch=0,points=[(1,1)],max_working_bytes=BUDGET,cancel=cancel)
        self.assertEqual(len(calls),7)


class TrackingVisibilityTests(unittest.TestCase):
    def host(self,p,s,**options):return FloatTimeline(p,'main',s,working_signal=f.LINEAR,**options)
    def state(self,h,index):
        _,meta=h.render_frame(index)
        return next(r['tracking'] for r in meta['layers'] if r['clip']=='main/marker')

    def fixed(self):
        p,s,_,source,marker=scene()
        for obs in marker['tracking_binding']['observations']:obs.update(x=1.5/8,y=1.5/4)
        return p,s,source,marker

    def pair(self,kind='slideleft'):
        p,s,source,marker=self.fixed();seq=p['sequences'][0];source['transition_out']={'type':kind,'duration':.4}
        for obs in marker['tracking_binding']['observations']:obs['x']=5.5/8
        peer=f.clip('peer','b');peer.update(timeline_start_tick=60,transition_in={'type':kind,'duration':.4})
        seq['tracks'][0]['clips'].append(peer);seq['duration_tick']=160
        p['assets'].append({'id':'b','kind':'video','sha256':f.SHA,'probe':copy.deepcopy(p['assets'][0]['probe'])})
        s['b']=f.source([f.rgba((0,0,1,1))]*10)
        return p,s,source,marker,peer

    def test_actual_source_pixel_alpha_and_scalar_opacity_are_each_applied_once(self):
        p,s,source,marker=self.fixed();frames=[s['a'].fetch(i).copy() for i in range(10)]
        for frame in frames:frame[1,1,3]=.25
        s['a']=f.source(frames);source['transform']={'opacity':.5};source['blend']={'opacity':.4}
        marker['tracking_binding']['base']['opacity']=.75
        state=self.state(self.host(p,s),0)
        self.assertEqual(state['visibility']['input_canvas_alpha'],.25)
        self.assertAlmostEqual(state['values']['opacity'],.75*.25*.5*.4)
        for frame in frames:frame[1,1,3]=0
        state=self.state(self.host(p,s),0)
        self.assertFalse(state['active']);self.assertEqual(state['reason'],'source-anchor-footprint-invisible')

    def test_all_five_mask_types_hide_the_anchor_without_changing_observations(self):
        shapes=[{'type':'rectangle','x':.6,'width':.4},
            {'type':'circle','cx':.8,'cy':.5,'radius':.1},
            {'type':'ellipse','cx':.8,'cy':.5,'rx':.1,'ry':.2},
            {'type':'polygon','points':[[.6,0],[1,0],[1,1],[.6,1]]},
            {'type':'path','points':[[.6,0],[1,0],[1,1],[.6,1]]}]
        for shape in shapes:
            for invert,want in ((False,False),(True,True)):
                with self.subTest(shape=shape['type'],invert=invert):
                    p,s,source,marker=self.fixed();source['mask']={**shape,'invert':invert};before=copy.deepcopy(p)
                    state=self.state(self.host(p,s),0);self.assertEqual(state['active'],want)
                    self.assertEqual(state['values']['opacity'],int(want));self.assertEqual(p,before)

    def test_animated_feather_crop_and_TRS_sample_the_rendered_canvas_alpha(self):
        for crop in (False,True):
            p,s,source,marker=self.fixed();source['transform']={'scale':.8,'rotation':17}
            if crop:source['crop']={'unit':'pixels','x':0,'y':0,'width':6,'height':4,'fit':'stretch'}
            source['mask']={'type':'rectangle','x':0,'y':0,'width':.5,'height':1,'feather':.2,
                'keyframes':[{'property':'width','keyframes':[{'at_tick':0,'value':.25},{'at_tick':100,'value':1}]}]}
            bare=copy.deepcopy(p);bare['sequences'][0]['tracks'].pop();source_host=self.host(bare,s)
            h=self.host(p,s)
            for i in (0,2,5,8):
                rgba=source_host.render_frame(i)[0];state=self.state(h,i)
                x=state['values']['position.x']*8-.5;y=state['values']['position.y']*4-.5
                expected=sum(max(0.,1-abs(xx-x))*max(0.,1-abs(yy-y))*float(rgba[yy,xx,3])
                    for yy in range(4) for xx in range(8))
                self.assertAlmostEqual(state['values']['opacity'],expected,places=7)

    def test_paired_slide_and_unmatched_edge_move_the_label_with_the_source_pixels(self):
        p,s,source,marker,_=self.pair();before=copy.deepcopy(p);state=self.state(self.host(p,s),8)
        self.assertAlmostEqual(state['values']['position.x'],1.5/8)
        self.assertEqual(state['values']['position.y'],1.5/4);self.assertEqual(state['values']['opacity'],1)
        self.assertTrue(state['visibility']['steps'][0]['pair']);self.assertEqual(p,before)
        p,s,source,marker=self.fixed();source['transition_out']={'type':'slideleft','duration':.4}
        for obs in marker['tracking_binding']['observations']:obs['x']=5.5/8
        state=self.state(self.host(p,s),8)
        self.assertAlmostEqual(state['values']['position.x'],1.5/8)

    def test_wipe_and_dip_hide_lost_points_but_mattes_remain_visible_on_screen(self):
        p,s,source,marker,_=self.pair('wipeleft')
        for obs in marker['tracking_binding']['observations']:obs['x']=6.5/8
        state=self.state(self.host(p,s),8);self.assertFalse(state['active'])
        p,s,source,marker,_=self.pair('dip_white');h=self.host(p,s)
        state=self.state(h,8);self.assertFalse(state['active']);self.assertEqual(state['values']['opacity'],0)
        pixels,_=h.render_frame(8);np.testing.assert_array_equal(pixels,f.rgba((1,1,1,1)))

    def test_roi_and_rotation_follow_spatial_probes_and_hide_when_endpoint_is_lost(self):
        p,s,source,marker,_=self.pair();b=marker['tracking_binding'];b.update(scale_mode='roi',rotation_mode='source')
        state=self.state(self.host(p,s),8)
        self.assertEqual(state['values']['scale'],.25);self.assertEqual(state['values']['rotation'],0)
        self.assertEqual(state['roi_width_pixels'],1)
        p,s,source,marker,_=self.pair('wipeleft');b=marker['tracking_binding'];b.update(scale_mode='roi')
        for obs in b['observations']:obs.update(x=4.5/8,width=.125)
        state=self.state(self.host(p,s),8)
        self.assertFalse(state['active']);self.assertEqual(state['reason'],'source-ROI-footprint-unobservable')

    def test_fade_base_alpha_is_not_multiplied_twice_and_mute_stays_fetch_free(self):
        p,s,source,marker,_=self.pair('dissolve');source['transform']={'opacity':.5}
        marker['tracking_binding']['base']['opacity']=.4
        self.assertAlmostEqual(self.state(self.host(p,s),8)['values']['opacity'],.1)
        p['sequences'][0]['tracks'][0]['muted']=True
        with patch.object(s['a'],'fetch',side_effect=AssertionError('muted source fetched')):
            self.assertFalse(self.state(self.host(p,s),8)['active'])

    def test_transition_peer_binding_cycle_rejects_before_fetch(self):
        p,s,source,marker,peer=self.pair('distance');seq=p['sequences'][0];track=seq['tracks'][0]
        evidence={'source_sha256':f.SHA,'range':copy.deepcopy(marker['tracking_binding']['range']),
            'frames':copy.deepcopy(marker['tracking_binding']['observations'])}
        peer['tracking_binding']=make_binding(p,seq,track,source,track,peer,evidence,
            offset_x=0,offset_y=0,scale_mode='none',scale_multiplier=1,rotation_mode='none')
        with patch.object(s['a'],'fetch',side_effect=AssertionError('must not fetch')),self.assertRaises(AppError) as caught:
            self.host(p,s)
        self.assertEqual(caught.exception.code,'FLOAT_TRACKING_VISIBILITY_CYCLE')

    def test_source_layer_is_not_reprojected_and_mutable_metadata_is_not_shared(self):
        p,s,source,marker=self.fixed();h=self.host(p,s)
        with patch.object(h,'_project',wraps=h._project) as project:
            _,meta=h.render_frame(0);self.assertEqual(project.call_count,2)
        key=('main/source',F(0),False);meta['layers'][0]['opacity']=0
        self.assertEqual(h._layer_cache[key][3]['opacity'],1)
        h.render_frame(1);self.assertNotIn(key,h._layer_cache)

    def test_left_limits_use_the_same_edge_and_pair_clock_as_actual_reversed_render(self):
        p,s,source,marker,peer=self.pair('wipeleft');h=self.host(p,s)
        at=F(4,5);state=h.tracking.evaluate('main/marker',at,left_limit=True)
        progress=state['visibility']['steps'][0]['progress']
        self.assertEqual(progress,math.nextafter(.5,-math.inf))
        edge={'edge':'out','duration':40,'authored_duration':100}
        self.assertEqual(edge_progress(edge,F(80)),.5)
        pair=h.transition_plans['main/video']['pairs'][0]
        self.assertEqual(pair_progress(pair,80,left_limit=True),(F(1,2),math.nextafter(.5,-math.inf)))

    def test_incoming_source_anchor_moves_in_the_other_branch_and_fades_in(self):
        p,s,source,marker,peer=self.pair('slideleft');b=marker['tracking_binding']
        b.update(source_clip_id='peer',asset_id='b');marker.update(timeline_start_tick=60)
        for obs in b['observations']:obs['x']=1.5/8
        state=self.state(self.host(p,s),8)
        self.assertEqual(state['visibility']['steps'][0]['branch'],1)
        self.assertEqual(state['values']['position.x'],5.5/8)
        self.assertEqual(state['native_frame_index'],2)
        source['transition_out']['type']=peer['transition_in']['type']='dissolve'
        state=self.state(self.host(p,s),8);self.assertEqual(state['values']['opacity'],.5)

    def test_own_edge_then_pair_preserves_the_field_with_actual_peer_pixels(self):
        p,s,source,marker,peer=self.pair('slideleft')
        source['transition_in']={'type':'hblur','duration':.8};h=self.host(p,s)
        state=self.state(h,7);self.assertEqual(len(state['visibility']['steps']),2)
        self.assertTrue(state['visibility']['steps'][0]['retained_density'])
        # Alpha difference through two independent public renders, not the
        # tracking helper, must recover the same outgoing contribution field.
        raw=f.rgba((0,0,0,1));empty=np.zeros_like(raw);changed=raw.copy();changed[1,5,3]=.5
        a=transition_rgba(empty,raw,.875,kind='hblur')[0]
        altered=transition_rgba(empty,changed,.875,kind='hblur')[0]
        b=f.rgba((0,0,1,1));base=transition_rgba(a,b,.25,kind='slideleft')[0]
        marked=transition_rgba(altered,b,.25,kind='slideleft')[0]
        expected=(base[:,:,3].astype(np.float64)-marked[:,:,3].astype(np.float64))*2
        yy,xx=np.indices(expected.shape);mass=expected.sum()
        self.assertAlmostEqual(state['opacity'],mass,places=7)
        self.assertAlmostEqual(state['values']['position.x'],((expected*xx).sum()/mass+.5)/8,places=7)

    def test_real_source_handle_dip_keeps_original_PTS_and_loses_the_matte_anchor(self):
        p,s,_,source,marker=scene(20);seq=p['sequences'][0]
        source.update(source_in_tick=30,source_out_tick=130)
        peer=f.clip('peer');peer.update(timeline_start_tick=100,source_in_tick=30,source_out_tick=130)
        seq['tracks'][0]['clips'].append(peer);seq['duration_tick']=200
        seq['source_transitions']=[dict(id='real',type='dip_white',duration_tick=30,
            from_clip_id='source',to_clip_id='peer',audio_pairs=[])]
        p['assets'][0]['probe']['duration_seconds']=2
        marker.update(duration_tick=120,source_out_tick=120)
        h=self.host(p,s);state=self.state(h,10)
        self.assertEqual(state['native_pts'],130)
        self.assertEqual(state['reason'],'source-anchor-footprint-invisible')
        self.assertTrue(state['visibility']['steps'][0]['real_source_handles'])

    def test_mask_and_edge_survive_shared_retime_with_exact_pixels_and_native_clocks(self):
        from ai_ad_editor.edit_planner import build_edit_plan
        from test_tracking_retime import NativeTrackingRetimeTests
        p,s,source,marker=self.fixed();source['transition_in']={'type':'slideleft','duration':.4}
        source['mask']={'type':'rectangle','width':.75,'height':1,'feather':.1}
        for obs in marker['tracking_binding']['observations']:obs['x']=5.5/8
        changed,_=build_edit_plan(p,'main',dict(action='retime',clip_ids=['source'],transform={'speed':2}))
        NativeTrackingRetimeTests().compare(p,changed,s,[F(i,5) for i in range(5)])


if __name__=='__main__':unittest.main()
