"""Independent geometry, alpha, blur, author-clock and actual CLI evidence."""
import copy
import hashlib
import json
import math
import subprocess
import unittest

import numpy as np

from ai_ad_editor.errors import AppError
from ai_ad_editor.float_mask import apply_mask, compile_mask
from ai_ad_editor.float_timeline import FloatTimeline
from ai_ad_editor.media import ffmpeg_path
import test_float_timeline as timeline_fixture
import test_float_preview as preview_fixture


def apply(a, mask, tick=0, tracks=None, **kwargs):
    return apply_mask(a, compile_mask({'mask':mask, 'keyframes':tracks or []}), tick, **kwargs)


def track(name, start, end, *, mode='linear', stop=100, controls=None):
    first = {'at_tick':0, 'value':start, 'interpolation':mode}
    if controls is not None:
        first['control_points'] = controls
    return {'property':name, 'keyframes':[first, {'at_tick':stop, 'value':end}]}


def polygon_oracle(points, width, height):
    answer = np.zeros((height, width), np.float64)
    points = [(x*width, y*height) for x, y in points]
    for y in range(height):
        for x in range(width):
            intersections = 0
            for i, (a, b) in enumerate(points):
                c, d = points[(i+1) % len(points)]
                if ((b >= y and d < y) or (b < y and d >= y)) and x < a+(c-a)*(y-b)/(d-b):
                    intersections += 1
            answer[y, x] = intersections % 2
    return answer


def box_oracle(alpha, radius):
    answer = np.asarray(alpha, np.float64).copy()
    def mirror(i, length):
        return -i-1 if i < 0 else 2*length-i-1 if i >= length else i
    for axis in (1, 1, 0, 0):
        previous = answer.copy()
        for y in range(len(answer)):
            for x in range(answer.shape[1]):
                values = [previous[y, mirror(x+d, answer.shape[1])] if axis == 1 else previous[mirror(y+d, len(answer)), x]
                          for d in range(-radius, radius+1)]
                answer[y, x] = math.fsum(values)/(2*radius+1)
    return answer


class FloatMaskTests(unittest.TestCase):
    def test_all_basic_shapes_and_inversion_match_independent_integer_centres(self):
        a = timeline_fixture.rgba((-.1, 1.2, .25, .75), shape=(13, 20))
        y, x = np.indices(a.shape[:2])
        cases = [({'type':'rectangle', 'x':.2, 'y':.2, 'width':.3, 'height':.4}, (x >= 4) & (x <= 10) & (y >= 2.6) & (y <= 7.8)),
                 ({'type':'circle', 'radius':.25}, (x-10)**2+(y-6.5)**2 <= 3.25**2),
                 ({'type':'ellipse', 'rx':.2, 'ry':.3}, ((x-10)/4)**2+((y-6.5)/3.9)**2 <= 1)]
        for mask, coverage in cases:
            for invert in (False, True):
                with self.subTest(mask=mask, invert=invert):
                    result, _ = apply(a, dict(mask, invert=invert))
                    np.testing.assert_array_equal(result[..., 3], .75*(~coverage if invert else coverage))
                    self.assertEqual(result[..., :3].tobytes(), a[..., :3].tobytes())

    def test_concave_and_self_intersecting_polygon_match_scalar_even_odd_fill(self):
        cases = [[(.1,.1),(.9,.1),(.5,.5),(.9,.9),(.1,.9)], [(0,0),(1,1),(0,1),(1,0)],
                 [(0,0),(.5,0),(.5,.5),(.5,.5),(0,.5)]]
        a = timeline_fixture.rgba(shape=(13, 20))
        for points in cases:
            result, _ = apply(a, {'type':'polygon', 'points':points})
            np.testing.assert_array_equal(result[..., 3], polygon_oracle(points, 20, 13))

    def test_cubic_path_matches_explicit_bernstein_sample_geometry(self):
        controls = [(0,.5),(.1,0),(.9,0),(1,.5)]
        points = []
        for i in range(9):
            u = i/8
            points.append(tuple((1-u)**3*controls[0][a]+3*(1-u)**2*u*controls[1][a]+3*(1-u)*u*u*controls[2][a]+u**3*controls[3][a] for a in (0,1)))
        a = timeline_fixture.rgba(shape=(24, 40))
        mask = {'type':'path', 'curves':[dict(type='bezier', start=controls[0], c1=controls[1], c2=controls[2], end=controls[3], samples=8)]}
        actual, meta = apply(a, mask)
        np.testing.assert_array_equal(actual[..., 3], polygon_oracle(points, 40, 24))
        np.testing.assert_allclose(meta['points'], points, rtol=0, atol=2e-16)

    def test_animated_segment_control_aliases_change_real_shape(self):
        a = timeline_fixture.rgba(shape=(20, 32))
        mask = {'type':'path', 'curve_segments':[{'type':'cubic', 'from':[0,.5], 'control1':[0,0], 'control2':[1,0], 'to':[1,.5], 'samples':8}],
                'keyframes':[track('segments.0.c1.y',0,.8)]}
        first, _ = apply(a, mask, 0)
        last, meta = apply(a, mask, 100)
        points = []
        for i in range(9):
            u=i/8
            points.append((3*(1-u)*u*u+u**3, (1-u)**3*.5+3*(1-u)**2*u*.8+u**3*.5))
        np.testing.assert_array_equal(last[...,3], polygon_oracle(points,32,20))
        self.assertNotEqual(first.tobytes(),last.tobytes())
        self.assertEqual(len(meta['points']),9)

    def test_point_bracket_alias_and_mask_local_override_clip_track(self):
        mask={'type':'polygon','points':[[0,0],[1,0],[0,1]],'keyframes':[track('points[0].x',0,.5)]}
        a=timeline_fixture.rgba(shape=(20,32))
        result,_=apply(a,mask,100,tracks=[track('mask.points[0].x',0,.25)])
        np.testing.assert_array_equal(result[...,3],polygon_oracle([(.5,0),(1,0),(0,1)],32,20))

    def test_static_feather_blurs_existing_alpha_after_mask_and_keeps_RGB(self):
        a=timeline_fixture.rgba((-.2,1.3,.75,1),shape=(9,12));a[...,3]=np.arange(108).reshape(9,12)/107
        y,x=np.indices((9,12));inside=(x>=3)&(x<=9)&(y>=2.25)&(y<=6.75)
        for invert in (False,True):
            output,meta=apply(a,{'type':'rectangle','x':.25,'y':.25,'width':.5,'height':.5,'feather':.23,'invert':invert},tile_pixels=7)
            expected=box_oracle(a[...,3]*(~inside if invert else inside),2).astype(np.float32)
            np.testing.assert_array_equal(output[...,3],expected)
            self.assertEqual(output[...,:3].tobytes(),a[...,:3].tobytes());self.assertEqual(meta['box_radius_pixels'],2)
        wrong=box_oracle(inside,2)*a[...,3]
        self.assertGreater(float(np.max(np.abs(expected-wrong))),.01)

    def test_box_border_matches_native_alpha16_with_derived_integer_error_bound(self):
        h,w=9,12
        a=timeline_fixture.rgba((.2,.4,.6,1),shape=(h,w))
        codes=np.arange(h*w,dtype=np.uint16).reshape(h,w)*np.uint16(600)
        a[...,3]=codes.astype(np.float32)/65535
        actual,_=apply(a,{'type':'rectangle','feather':2/h})
        expected=box_oracle(a[...,3],2)
        np.testing.assert_array_equal(actual[...,3],expected.astype(np.float32))
        planes=np.zeros((4,h,w),'<u2');planes[:3]=12345;planes[3]=codes
        command=[ffmpeg_path(),'-nostdin','-v','error','-f','rawvideo','-pixel_format','gbrap16le','-video_size',f'{w}x{h}',
                 '-i','pipe:0','-vf','boxblur=luma_radius=0:chroma_radius=0:alpha_radius=2:alpha_power=2',
                 '-frames:v','1','-pix_fmt','gbrap16le','-f','rawvideo','pipe:1']
        process=subprocess.run(command,input=planes.tobytes(),stdout=subprocess.PIPE,stderr=subprocess.PIPE,check=True)
        native=np.frombuffer(process.stdout,'<u2').reshape(4,h,w)
        np.testing.assert_array_equal(native[:3],planes[:3])
        # Four integer passes: fixed-point reciprocal error plus half-code
        # rounding per pass. This bound is set before reading the observation.
        length=5;inverse=((1<<16)+length//2)//length
        bound=4*(65535*abs(inverse*length/65536-1)+.5)+1
        self.assertLessEqual(float(np.max(np.abs(native[3]-expected*65535))),bound)

    def test_animation_feather_is_inner_distance_not_static_blur(self):
        a=timeline_fixture.rgba(shape=(20,20));y,x=np.indices((20,20))
        mask={'type':'circle','radius':.4,'feather':.1,'keyframes':[track('feather',.1,.2)]}
        for at,f in ((0,.1),(50,.15),(100,.2)):
            output,meta=apply(a,mask,at)
            expected=np.clip((8-np.hypot(x-10,y-10))/(20*f),0,1).astype(np.float32)
            np.testing.assert_array_equal(output[...,3],expected)
            self.assertEqual(meta['box_radius_pixels'],0)
        static,_=apply(a,{'type':'circle','radius':.4,'feather':.1})
        self.assertNotEqual(static.tobytes(),apply(a,mask)[0].tobytes())

    def test_polygon_dynamic_feather_matches_independent_segment_distance(self):
        points=[(.1,.1),(.8,.2),(.5,.9)];h,w=17,23
        a=timeline_fixture.rgba(shape=(h,w));inside=polygon_oracle(points,w,h)
        expected=np.zeros((h,w),np.float32)
        for y in range(h):
            for x in range(w):
                distances=[]
                for i,(a0,b0) in enumerate(points):
                    c,d=points[(i+1)%3];a0*=w;b0*=h;c*=w;d*=h;dx=c-a0;dy=d-b0
                    u=min(1,max(0,((x-a0)*dx+(y-b0)*dy)/max(1e-6,dx*dx+dy*dy)))
                    distances.append(math.hypot(x-a0-u*dx,y-b0-u*dy))
                expected[y,x]=min(1,min(distances)/(min(w,h)*.2)) if inside[y,x] else 0
        mask={'type':'polygon','points':points,'keyframes':[track('feather',.2,.2)]}
        actual,_=apply(a,mask)
        np.testing.assert_allclose(actual[...,3],expected,rtol=0,atol=1e-7)

    def test_all_six_easings_use_original_author_ticks(self):
        functions={'linear':lambda p:p,'hold':lambda p:0,'ease_in':lambda p:p*p,
                   'ease_out':lambda p:1-(1-p)**2,'ease_in_out':lambda p:2*p*p if p<.5 else 1-2*(1-p)**2,
                   'bezier':lambda p:3*p*p-2*p**3}
        a=timeline_fixture.rgba(shape=(16,128))
        for mode,fn in functions.items():
            # Avoid an integer pixel exactly on the ideal analytic Bezier
            # border: the established author contract uses a serialized LUT.
            mask={'type':'rectangle','width':.103,'keyframes':[track('x',0,.8,mode=mode,controls=[0,1] if mode=='bezier' else None)]}
            for tick in (0,25,50,75,100):
                with self.subTest(mode=mode,tick=tick):
                    out,_=apply(a,mask,tick);p=tick/100
                    left=.8*(1 if tick==100 else fn(p))*128
                    expected=(np.arange(128)>=left)&(np.arange(128)<=left+.103*128)
                    np.testing.assert_array_equal(out[8,:,3],expected)

    def test_animated_invert_and_zero_feather_preserve_source_alpha(self):
        a=timeline_fixture.rgba((1,0,0,.37),shape=(10,10));y,x=np.indices((10,10))
        mask={'type':'rectangle','width':.5,'height':.5,'invert':True,'keyframes':[track('feather',0,0)]}
        out,_=apply(a,mask)
        np.testing.assert_array_equal(out[...,3],np.where((x<=5)&(y<=5),0,np.float32(.37)))

    def test_all_65536_alpha_levels_and_extended_hidden_RGB_keep_float_precision(self):
        a=timeline_fixture.rgba((-.2,1.4,-0.,1),shape=(256,256))
        a[...,3]=np.arange(65536,dtype=np.float32).reshape(256,256)/65535
        original=a.tobytes();out,_=apply(a,{'type':'rectangle'})
        self.assertEqual(out.tobytes(),original);self.assertEqual(a.tobytes(),original)
        tiny=np.nextafter(np.float32(0),np.float32(1));a[0,0,3]=tiny
        out,_=apply(a,{'type':'rectangle','keyframes':[track('feather',0,0)]})
        self.assertEqual(out[0,0,3],tiny)

    def test_static_blur_is_tile_partition_invariant_and_keeps_small_alpha(self):
        rng=np.random.default_rng(444);a=timeline_fixture.rgba(shape=(17,23));a[...,3]=rng.random((17,23)).astype(np.float32)*1e-7
        mask={'type':'polygon','points':[(0,0),(1,0),(.5,1)],'feather':.2}
        reference,_=apply(a,mask,tile_pixels=1)
        for tile in (7,64,65536):
            actual,_=apply(a,mask,tile_pixels=tile);np.testing.assert_array_equal(actual,reference)
        self.assertGreater(float(reference[...,3].max()),0)

    def test_shape_path_and_keyframe_errors_reject_without_silent_truncation(self):
        masks=[{'type':'polygon'}, {'type':'polygon','points':[[0,0]]*33}, {'type':'polygon','points':[[0,0],[1,0],[0,1]],'segments':[]},
               {'type':'path','segments':[{'type':'spline'}]}, {'type':'path','segments':[{'from':[0,0],'control1':[1,0],'control2':[1,1],'to':[0,1],'samples':17}]},
               {'type':'circle','cx':True}, {'type':'rectangle','width':.3,'w':.4}, {'type':'circle','invert':1},
               {'type':'circle','feather':.51}, {'type':'circle','keyframes':[track('width',0,1)]},
               {'type':'circle','keyframes':[track('radius',0,1,mode='unknown')]},
               {'type':'circle','keyframes':[track('radius',0,1,mode='bezier',controls=[2,0,0,1])]},
               {'type':'circle','unknown':1}]
        for mask in masks:
            with self.subTest(mask=mask),self.assertRaises(AppError):compile_mask({'mask':mask})

    def test_degenerate_animated_path_rejects_without_fabricating_coverage(self):
        a=timeline_fixture.rgba();mask={'type':'path','segments':[{'type':'cubic','from':[0,0],'control1':[0,0],'control2':[0,0],'to':[0,0],'samples':8}]}
        with self.assertRaises(AppError):apply(a,mask)

    def test_bad_surface_late_alpha_and_working_budget_preserve_input(self):
        for c,v in ((0,float('nan')),(1,float('inf')),(3,-.1),(3,1.1)):
            a=timeline_fixture.rgba();a[-1,-1,c]=v;before=a.tobytes()
            with self.assertRaises(AppError):apply(a,{'type':'circle'},tile_pixels=3)
            self.assertEqual(a.tobytes(),before)
        for a in (np.zeros((2,2,4),np.float64),np.zeros((2,2,4),np.float32)[:,::-1],np.zeros((0,2,4),np.float32)):
            with self.assertRaises(AppError):apply(a,{'type':'circle'})
        a=timeline_fixture.rgba();before=a.tobytes()
        for kwargs in ({'tile_pixels':True},{'max_working_bytes':1},{'tile_pixels':0}):
            with self.assertRaises(AppError):apply(a,{'type':'circle'},**kwargs)
        self.assertEqual(a.tobytes(),before)

    def test_mid_blur_cancellation_keeps_input_and_emits_no_partial_result(self):
        a=timeline_fixture.rgba(shape=(64,64));before=a.tobytes();calls=0
        def cancel():
            nonlocal calls
            calls+=1
            if calls==70:raise RuntimeError('cancel during static feather')
        with self.assertRaisesRegex(RuntimeError,'cancel during static feather'):
            apply(a,{'type':'circle','feather':.2},tile_pixels=64,cancel=cancel)
        self.assertEqual(a.tobytes(),before)

    def test_compiled_plan_is_detached_from_author_mutation(self):
        c={'mask':{'type':'circle','radius':.2,'keyframes':[track('radius',.2,.4)]}}
        plan=compile_mask(c);a=timeline_fixture.rgba();first=apply_mask(a,plan,100)[0]
        c['mask']['keyframes'][0]['keyframes'][1]['value']=.9;c['mask']['invert']=True
        np.testing.assert_array_equal(first,apply_mask(a,plan,100)[0])

    def test_nested_mask_uses_child_author_clock_before_parent_transform(self):
        a=timeline_fixture.rgba(shape=(10,20));p,s=timeline_fixture.image_project(a,size=(20,10))
        child=copy.deepcopy(p['sequences'][0]);child['id']='child';child['duration_tick']=200
        child_clip=child['tracks'][0]['clips'][0];child_clip.update(duration_tick=200,source_out_tick=200,
            mask={'type':'rectangle','width':.2,'keyframes':[track('x',0,.5)]})
        parent=p['sequences'][0]['tracks'][0]['clips'][0];parent.pop('asset_id');parent.update(sequence_id='child',speed=2,source_out_tick=200)
        p['sequences'].append(child);before=copy.deepcopy(p)
        host=FloatTimeline(p,'main',s,working_signal=timeline_fixture.LINEAR)
        actual,meta=host.render_frame(2);expected=a.copy();expected[:,:4]=0;expected[:,9:]=0
        np.testing.assert_array_equal(actual,expected);self.assertEqual(p,before)
        self.assertEqual(meta['layers'][0]['author_animation_tick'],'40')

    def test_presentation_window_does_not_restart_mask_local_keys(self):
        a=timeline_fixture.rgba(shape=(10,20));p,s=timeline_fixture.image_project(a,size=(20,10),duration=30)
        c=p['sequences'][0]['tracks'][0]['clips'][0];c.update(duration_tick=30,presentation_window={
            'version':1,'authored_start_tick':0,'authored_duration_tick':100,'offset_tick':40},
            mask={'type':'rectangle','width':.2,'keyframes':[track('x',0,.5)]})
        host=FloatTimeline(p,'main',s,working_signal=timeline_fixture.LINEAR)
        actual,meta=host.render_frame(0);expected=a.copy();expected[:,:4]=0;expected[:,9:]=0
        np.testing.assert_array_equal(actual,expected);self.assertEqual(meta['layers'][0]['mask']['author_tick'],'40')

    def test_real_standard_render_preview_PNG16_and_source_alpha_share_masks(self):
        case=preview_fixture.FloatPreviewTests('runTest');case.setUp()
        try:
            case.s['duration_tick']=18000
            opaque_output=copy.deepcopy(case.p['settings']['output'])
            case.transparent()
            pixels=case.visual(np.broadcast_to(np.array([.25,.25,.25,.5],np.float32),(2,16,32,4)).copy())
            c=case.s['tracks'][0]['clips'][0]
            c['mask']={'type':'polygon','points':[[0,0],[1,0],[.5,1]],'feather':.125}
            case.p['settings']['canvas']['background']='transparent'
            result=case.execute(end=2);actual=case.reference(result)
            source=np.rint(pixels.astype(np.float64)*65535).astype(np.float32)/65535
            expected=box_oracle(polygon_oracle([(0,0),(1,0),(.5,1)],32,16)*source[0,...,3],2).astype(np.float32)
            np.testing.assert_array_equal(actual[0,...,3],expected)
            frame=case.execute(mode='frame');png=case.png(frame)
            np.testing.assert_array_equal(png[...,3],np.rint(expected*65535).astype(np.uint16))
            # Encoded formal rendering uses the same source mask, composited
            # over explicit opaque black for its advertised YUV10 delivery.
            case.p['settings']['canvas']['background']='#000000'
            case.p['settings']['output']=opaque_output
            from ai_ad_editor.render import render_project
            from ai_ad_editor.project import project_write_lock
            with project_write_lock(case.root):
                formal=render_project(case.root,case.p,case.s,case.root/'renders/mask.mkv')
            raw=case.native([ffmpeg_path(),'-nostdin','-v','error','-i',formal['path'],'-an','-pix_fmt','yuv444p10le','-f','rawvideo','pipe:1'])
            y=np.frombuffer(raw,'<u2').reshape(2,3,16,32)[:,0]
            reference=np.ones_like(source)
            reference[...,:3]=(source[...,:3].astype(np.float64)*expected[None,...,None].astype(np.float64)).astype(np.float32)
            codes=np.rint(reference.astype(np.float64)*65535).astype('<u2')
            payload=np.moveaxis(codes[...,[1,2,0,3]],3,1).tobytes()
            from pathlib import Path
            manifest=json.loads(Path(formal['path']).with_suffix('.mkv.manifest.json').read_bytes())
            transport=manifest['delivery']['pixel_pipeline']['transport']
            self.assertEqual(transport['video_input_sha256'],'sha256:'+hashlib.sha256(payload).hexdigest())
            # Compare the actual codec's output against an independently
            # encoded declared RGB16 delivery. Ideal scalar luma is not a
            # lossless-codec oracle at sharp spatial edges.
            expected_input=case.root/'expected-mask.gbrap16';expected_input.write_bytes(payload)
            expected_movie=case.root/'expected-mask.mkv'
            case.native([ffmpeg_path(),'-nostdin','-v','error','-f','rawvideo','-pixel_format','gbrap16le',
                '-video_size','32x16','-framerate','10','-color_range','pc','-colorspace','rgb',
                '-color_primaries','bt709','-color_trc','linear','-i',expected_input,
                '-vf','format=gbrp16le,zscale=primariesin=709:transferin=linear:matrixin=gbr:rangein=full:primaries=709:transfer=linear:matrix=709:range=limited:chromal=left:dither=none,format=yuv444p10le',
                '-c:v','libx264','-crf','0','-preset','ultrafast',expected_movie])
            decoded=case.native([ffmpeg_path(),'-nostdin','-v','error','-i',expected_movie,'-an','-pix_fmt','yuv444p10le','-f','rawvideo','pipe:1'])
            self.assertEqual(raw,decoded);case.assert_clean()
        finally:
            case.tearDown();case.doCleanups()


if __name__=='__main__':unittest.main()
