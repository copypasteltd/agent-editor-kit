"""Author-clock frame host: independent clocks, pixels and rejected scopes."""
import copy,math,unittest
from fractions import Fraction as F
from unittest.mock import patch
import numpy as np
from ai_ad_editor.errors import AppError
from ai_ad_editor.float_color_signal import ColorSignal
from ai_ad_editor.float_timeline import FloatTimeline,TimedSurfaceSource

LINEAR=ColorSignal('bt709','linear')
SHA='sha256:'+'a'*64

def rgba(colour=(1,0,0,1),shape=(4,8)):
    return np.broadcast_to(np.asarray(colour,np.float32),(*shape,4)).copy()

def source(frames,*,pts=None,durations=None,time_base='1/100',origin=0,still=False,start=0,verify=None):
    if isinstance(frames,np.ndarray):frames=[frames]
    pts=list(range(0,len(frames)*10,10)) if pts is None else pts
    durations=[10]*len(frames) if durations is None else durations
    return TimedSurfaceSource(pts,durations,time_base,origin,lambda i:frames[i],signal=LINEAR,source_sha256=SHA,
        still=still,source_frame_start=start,verify=verify)

def clip(name='c',asset='a',**values):
    return dict(id=name,asset_id=asset,timeline_start_tick=0,duration_tick=100,source_in_tick=0,source_out_tick=100,**values)

def track(clips,**values):
    return dict(id='video',kind='video',order=0,clips=clips,**values)

def project(clips=None,*,size=(8,4),fps=(10,1),duration=100,assets=None,tracks=None):
    return {'settings':{'canvas':{'width':size[0],'height':size[1],'background':'transparent'},
        'timebase':{'ticks_per_second':100,'display_fps':{'num':fps[0],'den':fps[1]}}},
        'assets':assets or [{'id':'a','kind':'video','sha256':SHA}],
        'sequences':[{'id':'main','duration_tick':duration,'tracks':tracks if tracks is not None else [track(clips or [clip()])]}]}

def image_project(value=None,**options):
    p=project(**options);p['assets'][0]['kind']='image'
    return p,{'a':source(rgba() if value is None else value,still=True,durations=[0])}

class FloatTimelineTests(unittest.TestCase):
    def host(self,p,sources,**options):return FloatTimeline(p,'main',sources,working_signal=LINEAR,**options)
    def code(self,expected,fn):
        with self.assertRaises(AppError) as caught:fn()
        self.assertEqual(caught.exception.code,expected)

    def test_exact_native_VFR_nonzero_origin_and_both_half_open_edges(self):
        s=source([rgba((v,0,0,1)) for v in (.1,.2,.3,.4)],pts=[-3,0,4,11],durations=[2,4,7,3],time_base='1/10',origin=F(-3,10))
        cases=[(-1,None,None),(0,0,None),(F(3,10),1,0),(F(7,10),2,1),(F(14,10),3,2),(F(17,10),None,3),(2,None,None)]
        for t,left,right in cases:
            self.assertEqual(s.index_at(t),left);self.assertEqual(s.index_at(t,right_edge=True),right)
        self.assertEqual(s.index_at(F(1,4)),0) # Packet duration does not erase the display hold to the next original PTS.

    def test_unknown_video_EOF_is_rejected_without_average_FPS_substitution(self):
        s=source([rgba(),rgba()],durations=[10,0]);self.assertEqual(s.index_at(F(1,20)),0)
        self.code('FLOAT_TIMELINE_EOF_UNKNOWN',lambda:s.index_at(F(1,10)))

    def test_partial_bundle_offset_reports_original_source_frame_index(self):
        s=source([rgba(),rgba()],pts=[30,40],start=3)
        value,index=s.sample(F(4,10));self.assertEqual(index,4);self.assertIsNotNone(value)
        self.assertEqual(s.sample(F(2,10)),(None,None))

    def test_invalid_native_clocks_callbacks_and_surface_contract_are_rejected(self):
        for options in ({'pts':[0,0]},{'durations':[10,-1]},{'pts':[True,10]},{'time_base':0},{'start':-1},{'still':True}):
            with self.subTest(options=options),self.assertRaises(AppError):source([rgba(),rgba()],**options)
        s=source(np.zeros((4,8,4),np.float64));self.code('FLOAT_TIMELINE_SURFACE',lambda:s.sample(0))
        s=source(np.zeros((0,8,4),np.float32));self.code('FLOAT_TIMELINE_SURFACE',lambda:s.sample(0))

    def test_VFR_source_holds_forward_and_reverse_match_independent_intervals(self):
        frames=[rgba((v,.1,.2,1)) for v in (.2,.4,.8)]
        s=source(frames,pts=[5,8,15],durations=[3,7,5],time_base='1/10',origin=F(1,2))
        for reverse in (False,True):
            c=clip();c.update(duration_tick=150,source_out_tick=150,reverse=reverse)
            h=self.host(project([c],duration=150),{'a':s})
            expected=([0]*3+[1]*7+[2]*5) if not reverse else ([2]*5+[1]*7+[0]*3)
            for i,index in enumerate(expected):
                value,meta=h.render_frame(i);np.testing.assert_array_equal(value,frames[index]);self.assertEqual(meta['layers'][0]['native_frame_index'],index)

    def test_NTSC_clock_with_original_PTS_above_float64_integer_precision(self):
        first=2**53+1;pts=[first,first+3003,first+6006];frames=[rgba((i/2,0,0,1)) for i in range(3)]
        s=source(frames,pts=pts,durations=[3003]*3,time_base='1/90000',origin=F(first,90000))
        c=clip();c.update(duration_tick=9009,source_out_tick=9009);p=project([c],duration=9009,fps=(30000,1001));p['settings']['timebase']['ticks_per_second']=90000
        h=self.host(p,{'a':s});self.assertEqual(h.frame_count,3)
        for i in range(3):
            value,meta=h.render_frame(i);np.testing.assert_array_equal(value,frames[i]);self.assertEqual(meta['author_time'],str(F(i*1001,30000)))

    def test_static_picture_holds_for_the_authored_clip_not_the_packet_duration(self):
        p,s=image_project(duration=125);p['sequences'][0]['tracks'][0]['clips'][0].update(duration_tick=125,source_out_tick=125)
        h=self.host(p,s);self.assertEqual(h.frame_count,13)
        for i in range(13):np.testing.assert_array_equal(h.render_frame(i)[0],rgba())
        p['assets'][0]['kind']='video';self.code('FLOAT_TIMELINE_SOURCE',lambda:self.host(p,s))

    def test_scalar_speed_and_visible_empty_prefix_tail_leave_underlying_canvas(self):
        frames=[rgba((i/9,0,0,1)) for i in range(10)];s=source(frames,pts=list(range(20,120,10)),origin=0)
        c=clip();c.update(speed=2,duration_tick=70,source_out_tick=140)
        h=self.host(project([c],duration=100),{'a':s})
        expected=[None,0,2,4,6,8,None,None,None,None]
        for i,index in enumerate(expected):
            value,_=h.render_frame(i);np.testing.assert_array_equal(value,np.zeros_like(frames[0]) if index is None else frames[index])

    def test_track_order_is_stable_and_muted_and_audio_tracks_do_not_fetch(self):
        red=rgba((1,0,0,1));green=rgba((0,1,0,.5));blue=rgba((0,0,1,.5))
        clips=[clip(name='red',asset='r'),clip(name='green',asset='g'),clip(name='blue',asset='b')]
        tracks=[dict(id='green',kind='video',order=1,clips=[clips[1]]),dict(id='red',kind='video',order=0,clips=[clips[0]]),dict(id='blue',kind='video',order=1,clips=[clips[2]]),
            dict(id='muted',kind='video',order=5,muted=True,clips=[clip(name='missing',asset='missing')]),dict(id='audio',kind='audio',order=0,clips=[clip(name='missing2',asset='missing')])]
        assets=[dict(id=k,kind='image',sha256=SHA) for k in 'rgb'];p=project(tracks=tracks,assets=assets)
        h=self.host(p,{k:source(v,still=True,durations=[0]) for k,v in zip('rgb',(red,green,blue))});value,meta=h.render_frame(0)
        np.testing.assert_array_equal(value,rgba((.25,.25,.5,1)));self.assertEqual([v['clip'] for v in meta['layers']],['main/red','main/green','main/blue'])

    def test_background_hex_is_converted_from_explicit_sRGB_to_linear_without_alpha_transfer(self):
        p=project(tracks=[]);p['settings']['canvas']['background']='#80808080';value,_=self.host(p,{}).render_frame(0)
        # The public signal API takes Float32; the independent formula must
        # start from that exact input boundary, then round its output once.
        expected=np.float32(((float(np.float32(128/255))+.055)/1.055)**2.4)
        np.testing.assert_array_equal(value[...,:3],expected);np.testing.assert_array_equal(value[...,3],np.float32(128/255))

    def test_translation_and_clockwise_quarter_rotation_preserve_pixel_centres(self):
        v=rgba();v[...,0]=np.arange(32,dtype=np.float32).reshape(4,8)/31
        p,s=image_project(v);p['sequences'][0]['tracks'][0]['clips'][0]['transform']={'position_x':.75}
        actual,_=self.host(p,s).render_frame(0);expected=np.zeros_like(v);expected[:,2:]=v[:,:6];np.testing.assert_array_equal(actual,expected)
        v=v[:,:4].copy();p,s=image_project(v,size=(4,4));p['sequences'][0]['tracks'][0]['clips'][0]['transform']={'rotation':90}
        actual,_=self.host(p,s).render_frame(0);np.testing.assert_allclose(actual,np.rot90(v,-1),atol=1e-7,rtol=0)

    def test_all_six_opacity_easings_are_evaluated_on_the_author_animation_clock(self):
        functions={'linear':lambda t:t,'hold':lambda t:0,'ease_in':lambda t:t*t,'ease_out':lambda t:1-(1-t)**2,'ease_in_out':lambda t:2*t*t if t<.5 else 1-(-2*t+2)**2/2}
        for name,fn in functions.items():
            p,s=image_project(fps=(4,1));c=p['sequences'][0]['tracks'][0]['clips'][0];c['keyframes']=[{'property':'opacity','keyframes':[{'at_tick':0,'value':0,'interpolation':name},{'at_tick':100,'value':1}]}]
            h=self.host(p,s)
            for i in range(4):np.testing.assert_array_equal(h.render_frame(i)[0],rgba((0,0,0,0)) if i==0 or name=='hold' else rgba((1,0,0,fn(i/4))))
        # The established cubic lookup is separately exercised at a symmetry point.
        c['keyframes'][0]['keyframes'][0].update(interpolation='bezier',control_points=[.25,.1,.25,1.]);h=self.host(p,s)
        self.assertGreater(float(h.render_frame(2)[0][0,0,3]),.8);self.assertLess(float(h.render_frame(2)[0][0,0,3]),.81)

    def test_65536_gray_levels_retain_float_precision_through_animated_mask_and_opacity(self):
        gray=np.arange(65536,dtype=np.float32).reshape(64,1024)/65535;v=np.stack((gray,gray,gray,np.ones_like(gray)),-1)
        p,s=image_project(v,size=(1024,64));c=p['sequences'][0]['tracks'][0]['clips'][0];c.update(mask={'type':'rectangle','width':.5},transform={'opacity':.37})
        c['keyframes']=[{'property':'mask.width','keyframes':[{'at_tick':0,'value':.5},{'at_tick':100,'value':1}]}];h=self.host(p,s)
        for i,end in ((0,512),(5,768)):
            actual,_=h.render_frame(i);expected=v.copy();expected[...,3]=np.float32(.37);expected[:,end+1:]=0;np.testing.assert_array_equal(actual,expected)

    def test_circle_ellipse_and_inverted_masks_match_independent_integer_pixel_geometry(self):
        p,s=image_project();y,x=np.indices((4,8));c=p['sequences'][0]['tracks'][0]['clips'][0]
        for mask,expected in (({'type':'circle','radius':.25},(x-4)**2+(y-2)**2<=1),({'type':'ellipse','rx':.25,'ry':.25},((x-4)/2)**2+(y-2)**2<=1)):
            for invert in (False,True):
                c['mask']={**mask,'invert':invert};actual,_=self.host(p,s).render_frame(0);want=rgba();want[~(~expected if invert else expected)]=0;np.testing.assert_array_equal(actual,want)

    def test_freeze_holds_the_source_clock_while_opacity_continues_and_reverse_edges_are_exact(self):
        frames=[rgba((i/9,0,0,1)) for i in range(10)];c=clip();c.update(duration_tick=150,freeze={'at_tick':50,'duration_tick':50})
        for reverse in (False,True):
            c['reverse']=reverse;h=self.host(project([c],duration=150),{'a':source(frames)})
            expected=([0,1,2,3,4]+[5]*6+[6,7,8,9]) if not reverse else ([9,8,7,6,5]+[4]*6+[3,2,1,0])
            for i,index in enumerate(expected):
                value,meta=h.render_frame(i);np.testing.assert_array_equal(value,frames[index]);self.assertEqual(meta['layers'][0]['author_animation_tick'],str(i*10))

    def test_endpoint_freeze_uses_the_in_range_display_frame_in_either_direction(self):
        frames=[rgba((i/9,0,0,1)) for i in range(10)]
        for reverse,index in ((False,9),(True,0)):
            c=clip();c.update(reverse=reverse,duration_tick=150,freeze={'at_tick':100,'duration_tick':50});h=self.host(project([c],duration=150),{'a':source(frames)})
            for i in range(10,15):np.testing.assert_array_equal(h.render_frame(i)[0],frames[index])

    def test_presentation_window_preserves_source_and_animation_author_positions(self):
        frames=[rgba((i/9,0,0,1)) for i in range(10)];c=clip();c.update(duration_tick=30,presentation_window={'version':1,'authored_start_tick':0,'authored_duration_tick':100,'offset_tick':40},
            keyframes=[{'property':'opacity','keyframes':[{'at_tick':0,'value':0},{'at_tick':100,'value':1}]}])
        before=copy.deepcopy(c);h=self.host(project([c],duration=30),{'a':source(frames)})
        for i in range(3):
            actual,meta=h.render_frame(i);expected=frames[i+4].copy();expected[...,3]=np.float32((i+4)/10);np.testing.assert_array_equal(actual,expected);self.assertEqual(meta['layers'][0]['author_animation_tick'],str((i+4)*10))
        self.assertEqual(c,before)

    def test_linear_speed_curve_matches_closed_form_integral_forward_and_reverse(self):
        frames=[rgba((i/19,0,0,1)) for i in range(20)];s=source(frames);c=clip();c.update(source_out_tick=200,speed_curve={'keyframes':[{'at_tick':0,'speed':1},{'at_tick':200,'speed':3}]})
        for reverse in (False,True):
            c['reverse']=reverse;h=self.host(project([c]),{'a':s})
            for i in range(10):
                t=1-i/10 if reverse else i/10;seconds=3**t-1;index=min(19,math.floor(seconds*10+1e-12));actual,meta=h.render_frame(i)
                np.testing.assert_array_equal(actual,frames[index]);self.assertAlmostEqual(float(F(meta['layers'][0]['source_time'])),seconds,places=13)

    def nested(self,*,parent_reverse=False,child_reverse=False):
        p,s=image_project(size=(4,4),fps=(4,1));p['assets']=[dict(id=k,kind='image',sha256=SHA) for k in ('r','b')];s={k:source(rgba(v,(4,4)),still=True,durations=[0]) for k,v in (('r',(1,0,0,1)),('b',(0,0,1,1)))}
        left=clip('left','r');left.update(duration_tick=50,source_out_tick=50);right=clip('right','b');right.update(timeline_start_tick=50,duration_tick=50,source_out_tick=50)
        child={'id':'child','duration_tick':100,'tracks':[track([left,right])]};parent=clip('parent');parent.pop('asset_id');parent.update(sequence_id='child',reverse=parent_reverse)
        p['sequences'][0]['tracks'][0]['clips']=[parent];p['sequences'].append(child)
        if child_reverse:
            grand=copy.deepcopy(child);grand['id']='grand';child['tracks'][0]['clips']=[dict(parent,id='inside',sequence_id='grand',reverse=True)];p['sequences'].append(grand)
        return p,s

    def test_nested_reverse_left_limits_and_double_reverse_at_cut_boundaries(self):
        for parent_reverse,child_reverse,want in ((False,False,[0,0,1,1]),(True,False,[1,1,0,0]),(True,True,[0,0,1,1])):
            p,s=self.nested(parent_reverse=parent_reverse,child_reverse=child_reverse);h=self.host(p,s)
            for i,blue in enumerate(want):np.testing.assert_array_equal(h.render_frame(i)[0],rgba((0,0,1,1) if blue else (1,0,0,1),(4,4)))

    def test_nested_group_opacity_is_applied_once_after_children_composite(self):
        p,s=self.nested();p['settings']['canvas']['background']='#00ff00';parent=p['sequences'][0]['tracks'][0]['clips'][0];parent['transform']={'opacity':.5}
        child=p['sequences'][1];child['tracks'][0]['clips'][0].update(duration_tick=100,source_out_tick=100)
        child['tracks'][0]['clips'][1].update(timeline_start_tick=0,duration_tick=100,source_out_tick=100,transform={'opacity':.5})
        actual,_=self.host(p,s).render_frame(0);np.testing.assert_array_equal(actual,rgba((.25,.5,.25,1),(4,4)))

    def test_nested_sequence_uses_its_own_raster_before_parent_fit(self):
        p,s=image_project(rgba((1,0,0,1),(2,4)),size=(8,4));child=copy.deepcopy(p['sequences'][0]);child.update(id='child',canvas={'width':4,'height':2})
        parent=clip('parent');parent.pop('asset_id');parent['sequence_id']='child';p['sequences'][0]['tracks'][0]['clips']=[parent];p['sequences'].append(child)
        actual,meta=self.host(p,s).render_frame(0);self.assertEqual(meta['layers'][-1]['inverse_affine'],[[.5,0.,-.25],[-0.,.5,-.25]])
        expected=np.ones((4,8),np.float32);expected[[0,-1]]*=.75;expected[:,[0,-1]]*=.75;np.testing.assert_array_equal(actual[...,3],expected)

    def test_all_32_blend_modes_dispatch_on_float_surfaces_and_preserve_input_ownership(self):
        from ai_ad_editor.float_raster import SEPARABLE,NONSEPARABLE
        p,s=image_project(rgba((.3,.6,.7,.8)));c=p['sequences'][0]['tracks'][0]['clips'][0];p['settings']['canvas']['background']='#526d91'
        original=s['a'].fetch(0).copy()
        for mode in set(SEPARABLE)|NONSEPARABLE:
            c['blend']={'mode':mode,'opacity':.43};h=self.host(p,s);v,meta=h.render_frame(0);self.assertEqual(v.dtype,np.float32);self.assertTrue(np.isfinite(v).all());self.assertEqual(meta['layers'][0]['opacity'],.43)
            v[:]=0;np.testing.assert_array_equal(s['a'].fetch(0),original)

    def test_source_SHA_signal_and_unsupported_operations_cannot_silently_fall_back(self):
        p,s=image_project();base=copy.deepcopy(p)
        for field,value in (('effects',[{'type':'hqdn3d'}]),('generator',{'type':'color'}),('mask',{'type':'gradient'}),('mask',{'type':'rounded_rectangle'}),('keyframes',[{'property':'unknown','keyframes':[]}])):
            p=copy.deepcopy(base);p['sequences'][0]['tracks'][0]['clips'][0][field]=value;self.code('FLOAT_TIMELINE_UNSUPPORTED',lambda:self.host(p,s))
        p=copy.deepcopy(base);p['assets'][0]['sha256']='sha256:'+'b'*64;self.code('FLOAT_TIMELINE_SOURCE',lambda:self.host(p,s))
        p=copy.deepcopy(base);s['a'].signal=ColorSignal('bt709','srgb');self.code('FLOAT_TIMELINE_SOURCE',lambda:self.host(p,s))

    def test_invalid_ticks_cycles_frame_limits_and_post_child_layer_budget_are_rejected(self):
        p,s=image_project();p['sequences'][0]['tracks'][0]['clips'][0]['duration_tick']=True;self.code('FLOAT_TIMELINE_CLOCK',lambda:self.host(p,s))
        p,s=self.nested();p['sequences'][1]['tracks'][0]['clips']=[dict(p['sequences'][0]['tracks'][0]['clips'][0],id='loop')];self.code('FLOAT_TIMELINE_NESTING',lambda:self.host(p,s))
        p,s=image_project();h=self.host(p,s)
        for index in (-1,10,True,1.0):self.code('FLOAT_TIMELINE_RANGE',lambda:h.render_frame(index))
        p,s=self.nested();h=self.host(p,s)
        with patch('ai_ad_editor.float_timeline.MAX_LAYERS_PER_FRAME',1):self.code('FLOAT_TIMELINE_BUDGET',lambda:h.render_frame(0))

    def test_cancel_verify_hooks_and_project_and_frame_immutability(self):
        p,s=image_project();before=copy.deepcopy(p);original=s['a'].fetch(0).copy();polls=[];checked=[]
        s['a'].verify_callback=lambda:checked.append(True);h=self.host(p,s,cancel=lambda:polls.append(True));h.verify_sources();self.assertEqual(checked,[True]);self.assertGreater(len(polls),1)
        p['sequences'][0]['tracks'][0]['clips']=[];np.testing.assert_array_equal(h.render_frame(0)[0],original)
        def stop():raise AppError('CANCELLED','actual cancellation',exit_code=130)
        h.poll=stop;self.code('CANCELLED',lambda:h.render_frame(0));np.testing.assert_array_equal(s['a'].fetch(0),original);self.assertNotEqual(p,before)

if __name__=='__main__':unittest.main()
