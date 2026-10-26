"""Independent crop sampling, author clocks, native crop and encoded delivery."""
import copy
import hashlib
import json
import math
from pathlib import Path
import subprocess
import unittest
from unittest.mock import patch

import numpy as np

from ai_ad_editor.errors import AppError
from ai_ad_editor.float_crop import compile_crop, project_crop, resolve_crop
from ai_ad_editor.float_timeline import FloatTimeline
from ai_ad_editor.media import ffmpeg_path
import test_float_timeline as fixture
import test_float_preview as preview_fixture


def track(name, left, right, mode='linear', controls=None, stop=100):
    key = {'at_tick':0, 'value':left, 'interpolation':mode}
    if controls is not None:
        key['control_points'] = controls
    return {'property':name, 'keyframes':[key, {'at_tick':stop, 'value':right, 'interpolation':'linear'}]}


def pattern(size=(13, 7)):
    w, h = size
    y, x = np.indices((h, w))
    a = np.ones((h, w, 4), np.float32)
    a[..., 0] = -.2+x*.08
    a[..., 1] = .1+y*.13
    a[..., 2] = .125+.25*((x+y)%3)
    a[..., 3] = (x+2*y)/(w+2*h-3)
    return a


def scalar_project(a, window, size, fit='fit', *, scale=1, rotation=0, position=(.5,.5), anchor=(.5,.5)):
    # Pixel-wise inverse rotation and bilinear premultiplied summation. Do not
    # use the product plan resolver, inverse matrix, vector gathers or easing.
    ow, oh = size
    cx, cy, cw, ch = window
    fw, fh = ow/cw, oh/ch
    if fit != 'stretch':
        fw = fh = min(fw, fh) if fit == 'fit' else max(fw, fh)
    angle = rotation*math.pi/180
    out = np.zeros((oh, ow, 4), np.float32)
    for y in range(oh):
        for x in range(ow):
            dx, dy = x+.5-position[0]*ow, y+.5-position[1]*oh
            sx = cx+anchor[0]*cw+(dx*math.cos(angle)+dy*math.sin(angle))/(scale*fw)-.5
            sy = cy+anchor[1]*ch+(-dx*math.sin(angle)+dy*math.cos(angle))/(scale*fh)-.5
            if not cx-.5 <= sx < cx+cw-.5 or not cy-.5 <= sy < cy+ch-.5:
                continue
            sx, sy = max(cx, min(cx+cw-1, sx)), max(cy, min(cy+ch-1, sy))
            ix, iy = math.floor(sx), math.floor(sy)
            accum = np.zeros(4, np.float64)
            for yy in (iy, iy+1):
                for xx in (ix, ix+1):
                    weight = (1-abs(sx-xx))*(1-abs(sy-yy))
                    sample = a[max(0,min(len(a)-1,yy)), max(0,min(a.shape[1]-1,xx))].astype(np.float64)
                    accum[3] += sample[3]*weight
                    accum[:3] += sample[:3]*sample[3]*weight
            if accum[3] > 0:
                accum[:3] /= accum[3]
            out[y, x] = accum
    return out


def apply(a, crop, size=None, tick=0, tracks=None, nested=False, **kwargs):
    plan = compile_crop({'crop':crop, 'keyframes':tracks or [], **({'sequence_id':'child'} if nested else {})})
    return project_crop(a, plan, tick, size or (a.shape[1],len(a)), **kwargs)


class FloatCropTests(unittest.TestCase):
    def test_all_fits_match_independent_alpha_weighted_pixels(self):
        a = pattern()
        for fit in ('fit', 'fill', 'stretch'):
            crop = {'x':1.25,'y':.75,'width':9.25,'height':4.6,'fit':fit}
            actual, meta = apply(a, crop, (11,9), nested=True)
            np.testing.assert_allclose(actual, scalar_project(a,(1.25,.75,9.25,4.6),(11,9),fit),rtol=0,atol=1.2e-7)
            self.assertEqual(meta['projection_passes'],1)
            self.assertFalse(meta['integer_intermediate'])

    def test_units_short_dimensions_and_mode_alias_are_equivalent(self):
        a = pattern((20,10))
        expected = apply(a,{'x':4,'y':2,'width':12,'height':6,'fit':'stretch'})[0]
        for unit in ('normalized','relative'):
            actual,_ = apply(a,{'unit':unit,'x':.2,'y':.2,'w':.6,'h':.6,'mode':'stretch'})
            np.testing.assert_array_equal(actual,expected)
        np.testing.assert_array_equal(apply(a,{'unit':'pixel','x':4,'y':2,'w':12,'h':6,'mode':'stretch'})[0],expected)

    def test_static_and_position_only_rounding_match_actual_native_crop(self):
        a = pattern((12,6))
        planar = np.moveaxis(a[..., [1,2,0,3]],2,0).astype('<f4').tobytes()
        for animated in (False, True):
            for x in (.4,.5,.6,1.9,9.):
                crop={'x':x,'y':1.6,'width':4.5,'height':3.5}
                keys=[track('crop.x',x,x)] if animated else []
                resolved=resolve_crop(compile_crop({'crop':crop,'keyframes':keys}),(12,6),50)
                expected_x=round(min(8,x)) if animated else min(10,round(x))
                self.assertEqual(resolved['window'],[float(expected_x),2.,float(min(4,12-expected_x)),4.])
                width=int(resolved['window'][2])
                native_x=f'max(0,min(iw-out_w,{x}))' if animated else str(expected_x)
                native=subprocess.run([ffmpeg_path(),'-nostdin','-v','error','-f','rawvideo','-pixel_format','gbrapf32le',
                    '-video_size','12x6','-i','pipe:0','-vf',f"crop={width}:4:x='{native_x}':y=2:exact=1",
                    '-frames:v','1','-f','rawvideo','-pix_fmt','gbrapf32le','pipe:1'],input=planar,capture_output=True,timeout=30)
                self.assertEqual(native.returncode,0,native.stderr)
                expected=np.moveaxis(np.frombuffer(native.stdout,'<f4').reshape(4,4,width)[[2,0,1,3]],0,-1).copy()
                expected[expected[...,3]==0]=0
                actual,_=apply(a,crop,(width,4),tick=50,tracks=keys)
                np.testing.assert_array_equal(actual,expected)

    def test_local_exact_name_override_and_width_alias_priority(self):
        plan=compile_crop({'crop':{'unit':'normalized','keyframes':[track('x',.2,.4),track('w',.3,.4)]},
            'keyframes':[track('crop.x',0,.1),track('crop.width',.8,.6)]})
        meta=resolve_crop(plan,(100,50),50)
        np.testing.assert_allclose(meta['window'],[30,0,70,50],rtol=0,atol=1e-14)
        self.assertEqual(plan.properties,frozenset(('crop.x','crop.width')))

    def test_animated_width_height_all_six_author_interpolations(self):
        from test_spatial_automation import declared_bezier_reference
        for mode, p in [('linear',.25),('hold',0),('ease_in',.0625),('ease_out',.4375),('ease_in_out',.125),
                        ('bezier',declared_bezier_reference(.25))]:
            keys=[track('width',.2,.8,mode,[1/3,0,2/3,1] if mode=='bezier' else None),track('height',.4,.8,mode,[1/3,0,2/3,1] if mode=='bezier' else None)]
            plan=compile_crop({'crop':{'unit':'normalized','x':.1,'y':.05,'keyframes':keys}})
            resolved=resolve_crop(plan,(100,50),25)
            np.testing.assert_allclose(resolved['window'],[10,2.5,20+60*p,20+20*p],rtol=0,atol=2e-14)

    def test_size_overshoot_clamps_then_origin_stays_inside_source(self):
        crop={'unit':'normalized','x':.9,'y':.9,'keyframes':[track('width',.3,.4,'bezier',[12,12]),track('height',.2,.4,'bezier',[-3,-3])]}
        actual,meta=apply(pattern((20,10)),crop,tick=50)
        self.assertEqual(meta['window'],[0.,8.,20.,2.])
        np.testing.assert_allclose(actual,scalar_project(pattern((20,10)),(0,8,20,2),(20,10)),atol=1.2e-7,rtol=0)

    def test_nested_static_crop_retains_fractional_source_units(self):
        plan=compile_crop({'sequence_id':'child','crop':{'unit':'relative','x':.123,'y':.071,'w':.61,'h':.69}})
        meta=resolve_crop(plan,(100,40),0)
        np.testing.assert_allclose(meta['window'],[12.3,2.84,61,27.6],rtol=0,atol=5e-15)
        self.assertEqual(meta['rounding'],'continuous-child-or-animated-size')

    def test_fill_rotation_reveals_texture_outside_resting_parent_view(self):
        a=fixture.rgba((1,0,0,1),shape=(12,4));a[:4,:,:3]=[0,1,0];a[8:,:,:3]=[0,0,1]
        rest,_=apply(a,{'fit':'fill'},(8,4),nested=True)
        turned,_=apply(a,{'fit':'fill'},(8,4),nested=True,rotation=90,scale=.5)
        self.assertTrue(np.all(rest[...,:3]==[1,0,0]))
        self.assertGreater(float(turned[...,1].max()),.9)
        self.assertGreater(float(turned[...,2].max()),.9)
        np.testing.assert_allclose(turned,scalar_project(a,(0,0,4,12),(8,4),'fill',rotation=90,scale=.5),rtol=0,atol=1.2e-7)

    def test_arbitrary_position_anchor_scale_rotation_are_single_pass(self):
        a=pattern();window=(1.1,.4,10.2,5.8)
        options={'scale':.83,'rotation':27,'position':(.43,.61),'anchor':(.2,.7)}
        actual,_=apply(a,dict(zip(('x','y','width','height'),window),fit='fill'),(12,8),nested=True,**options)
        np.testing.assert_allclose(actual,scalar_project(a,window,(12,8),'fill',**options),rtol=0,atol=1.2e-7)

    def test_fit_bars_are_transparent_and_preserve_lower_track(self):
        a=fixture.rgba((1,0,0,1),shape=(8,4))
        actual,_=apply(a,{'fit':'fit'},(8,4))
        self.assertTrue(np.all(actual[:,:3]==0));self.assertTrue(np.all(actual[:,5:]==0))
        np.testing.assert_array_equal(actual[:,3:5],fixture.rgba(shape=(4,2)))

    def test_alpha_weighting_excludes_hidden_RGB_and_avoids_dark_edge(self):
        a=fixture.rgba((100,-100,20,0),shape=(2,2));a[:,1]=[.25,.75,1.25,1]
        actual,_=apply(a,{'fit':'stretch'},(8,2))
        visible=actual[...,3]>0
        np.testing.assert_array_equal(actual[visible,:3],np.broadcast_to([.25,.75,1.25],(visible.sum(),3)))
        self.assertTrue(np.all(actual[~visible]==0))

    def test_tiny_alpha_negative_and_extended_RGB_survive_without_quantization(self):
        a=fixture.rgba((-.125,2.5,1.00001,np.nextafter(np.float32(0),np.float32(1))),shape=(2,2))
        actual,_=apply(a,{'fit':'stretch'},(7,5))
        np.testing.assert_array_equal(actual,np.broadcast_to(a[0,0],actual.shape))

    def test_identity_retains_all_65536_RGB_levels_and_readonly_input(self):
        a=fixture.rgba(shape=(256,256));a[...,0]=np.arange(65536,dtype=np.float32).reshape(256,256)/65535
        a.flags.writeable=False
        actual,_=apply(a,{'fit':'stretch'})
        np.testing.assert_array_equal(actual,a);self.assertEqual(len(np.unique(actual[...,0])),65536)
        self.assertFalse(np.shares_memory(a,actual))

    def test_unknown_conflicting_boolean_and_nonfinite_crop_fields_reject(self):
        cases=[{'x':True},{'x':float('nan')},{'width':10**400},{'unit':'percent'},{'fit':'unknown'},
            {'fit':'fit','mode':'fill'},{'width':2,'w':3},{'unit':'relative','height':1.1},{'unknown':1},[]]
        for crop in cases:
            with self.subTest(crop=str(crop)[:70]),self.assertRaises(AppError):compile_crop({'crop':crop})

    def test_invalid_duplicate_tracks_and_easing_reject(self):
        keys=[track('bad',0,1),track('width',0,1),track('x',0,1,'other'),track('x',0,1,'bezier',[2,0,0,1]),
            track('x',0,1,'bezier',[0,float('inf')])]
        for key in keys:
            with self.assertRaises(AppError):compile_crop({'crop':{'keyframes':[key]}})
        for mutate in ('duplicate','time','bool','string'):
            raw=[track('x',0,1)]
            if mutate=='duplicate':raw*=2
            if mutate=='time':raw[0]['keyframes'][1]['at_tick']=0
            if mutate=='bool':raw[0]['keyframes'][1]['value']=True
            if mutate=='string':raw[0]['keyframes'][1]['value']='1'
            with self.assertRaises(AppError):compile_crop({'crop':{'keyframes':raw}})

    def test_noncontiguous_wrong_type_and_empty_surfaces_reject(self):
        for a in (np.zeros((2,2,4),np.float64),np.zeros((2,2,4),np.float32)[:,::-1],np.zeros((0,2,4),np.float32)):
            with self.assertRaises(AppError):apply(a,{})

    def test_late_invalid_values_preserve_input(self):
        for channel,value in ((0,float('nan')),(1,float('inf')),(3,-.1),(3,1.1)):
            a=pattern();a[-1,-1,channel]=value;before=a.tobytes()
            with self.assertRaises(AppError):apply(a,{},tile_pixels=3)
            self.assertEqual(a.tobytes(),before)

    def test_budget_rejects_before_output_allocation(self):
        a=pattern();before=a.tobytes()
        with patch('ai_ad_editor.float_crop.np.empty',side_effect=AssertionError('must not allocate output')):
            with self.assertRaises(AppError) as caught:apply(a,{},max_working_bytes=1)
        self.assertEqual(caught.exception.code,'FLOAT_CROP_BUDGET');self.assertEqual(a.tobytes(),before)

    def test_mid_projection_cancellation_never_mutates_source(self):
        a=pattern((64,32));before=a.tobytes();calls=0
        def cancel():
            nonlocal calls
            calls+=1
            if calls==35:raise RuntimeError('cancel during projection')
        with self.assertRaisesRegex(RuntimeError,'cancel during projection'):apply(a,{},(128,64),tile_pixels=64,cancel=cancel)
        self.assertEqual(a.tobytes(),before)

    def test_tiles_are_bit_identical(self):
        a=pattern();crop={'x':.31,'y':.21,'width':8.71,'height':5.14,'fit':'fill'}
        reference=apply(a,crop,(19,11),nested=True,tile_pixels=1,rotation=13)[0]
        for size in (7,64,65536):
            np.testing.assert_array_equal(apply(a,crop,(19,11),nested=True,tile_pixels=size,rotation=13)[0],reference)

    def test_compiled_plan_is_detached_from_authored_mutation(self):
        clip={'crop':{'width':8,'keyframes':[track('x',0,3)]}}
        plan=compile_crop(clip);before=resolve_crop(plan,(13,7),50)
        clip['crop']['keyframes'][0]['keyframes'][1]['value']=10;clip['crop']['width']=2
        self.assertEqual(resolve_crop(plan,(13,7),50),before)

    def test_presentation_window_uses_original_crop_and_transform_clock(self):
        a=pattern((20,10));p,s=fixture.image_project(a,size=(20,10),duration=30)
        c=p['sequences'][0]['tracks'][0]['clips'][0]
        c.update(duration_tick=30,presentation_window={'version':1,'authored_start_tick':0,'authored_duration_tick':100,'offset_tick':40},
            crop={'unit':'normalized','height':.8,'fit':'stretch','keyframes':[track('width',.8,.4)]},
            keyframes=[track('transform.scale',1,.5)])
        before=copy.deepcopy(p);actual,meta=FloatTimeline(p,'main',s,working_signal=fixture.LINEAR).render_frame(0)
        np.testing.assert_allclose(actual,scalar_project(a,(0,0,12.8,8),(20,10),'stretch',scale=.8),rtol=0,atol=1.2e-7)
        self.assertEqual(meta['layers'][0]['crop']['author_tick'],40);self.assertEqual(p,before)

    def test_nested_reverse_child_clock_and_parent_crop_remain_distinct(self):
        a=pattern((20,10));p,s=fixture.image_project(a,size=(20,10))
        child=copy.deepcopy(p['sequences'][0]);child['id']='child';child['duration_tick']=200
        child['tracks'][0]['clips'][0].update(duration_tick=200,source_out_tick=200,
            crop={'unit':'normalized','width':.6,'fit':'stretch','keyframes':[track('x',0,.4,stop=200)]})
        parent=p['sequences'][0]['tracks'][0]['clips'][0];parent.pop('asset_id')
        parent.update(sequence_id='child',source_out_tick=200,speed=2,reverse=True,
            crop={'unit':'normalized','width':.8,'height':.8,'fit':'stretch','keyframes':[track('x',0,.2)]})
        p['sequences'].append(child)
        actual,meta=FloatTimeline(p,'main',s,working_signal=fixture.LINEAR).render_frame(2)
        intermediate=scalar_project(a,(6,0,12,10),(20,10),'stretch')
        expected=scalar_project(intermediate,(.8,0,16,8),(20,10),'stretch')
        np.testing.assert_allclose(actual,expected,rtol=0,atol=2.4e-7)
        self.assertAlmostEqual(meta['layers'][0]['crop']['author_tick'],160,places=10)
        self.assertEqual(meta['layers'][1]['crop']['author_tick'],20)

    def test_crop_mask_exposure_and_lower_layer_combine_in_parent_space(self):
        a=fixture.rgba((.25,.5,.75,.5),shape=(4,8));p,s=fixture.image_project(a,size=(8,4))
        c=p['sequences'][0]['tracks'][0]['clips'][0]
        c.update(crop={'fit':'stretch'},transform={'scale':.5},effects=[{'type':'exposure','parameters':{'exposure':1}}],mask={'type':'rectangle','width':.4})
        actual,meta=FloatTimeline(p,'main',s,working_signal=fixture.LINEAR).render_frame(0)
        expected=np.zeros((4,8,4),np.float32);expected[1:3,2:4]=[.5,1,1.5,.5]
        np.testing.assert_array_equal(actual,expected)
        self.assertEqual(meta['layers'][0]['crop']['projection_passes'],1)

    def test_orphan_crop_tracks_unknown_fields_and_area_interpolation_reject(self):
        p,s=fixture.image_project();p['sequences'][0]['tracks'][0]['clips'][0]['keyframes']=[track('crop.x',0,1)]
        with self.assertRaises(AppError):FloatTimeline(p,'main',s,working_signal=fixture.LINEAR)
        with self.assertRaises(AppError):apply(pattern(),{'unknown':1})
        with self.assertRaises(AppError):apply(pattern(),{},interpolation='area')

    def test_one_pixel_source_and_nearest_are_explicit(self):
        a=fixture.rgba((.2,.4,.6,.5),shape=(1,1))
        actual,_=apply(a,{'width':0,'height':0,'fit':'stretch'},(5,3))
        np.testing.assert_array_equal(actual,np.broadcast_to(a,actual.shape))
        a=pattern((2,2));expected=np.repeat(np.repeat(a,2,0),2,1);expected[expected[...,3]==0]=0
        np.testing.assert_array_equal(apply(a,{'fit':'stretch'},(4,4),interpolation='nearest')[0],expected)

    def test_invalid_transform_clock_size_and_budget_parameters_reject(self):
        for kwargs in ({'scale':0},{'scale':1e-320},{'rotation':float('inf')},{'anchor':(True,.5)},
                       {'tile_pixels':True},{'tile_pixels':0},{'cancel':False}):
            with self.subTest(kwargs=kwargs),self.assertRaises(AppError):apply(pattern(),{},**kwargs)
        for tick in (True,float('nan'),float('inf')):
            with self.assertRaises(AppError):apply(pattern(),{},tick=tick)
        for size in ((0,1),(True,4),(2,2,2),(16384,16384)):
            with self.assertRaises(AppError):apply(pattern(),{},size=size)

    def test_real_standard_render_preview_PNG16_share_animated_crop(self):
        case=preview_fixture.FloatPreviewTests('runTest');case.setUp()
        try:
            case.s['duration_tick']=18000
            opaque=copy.deepcopy(case.p['settings']['output']);case.transparent()
            original=np.stack([pattern((32,16))]*2)
            original[...,:3]=np.clip(original[...,:3],0,1)
            pixels=case.visual(original)
            clip=case.s['tracks'][0]['clips'][0]
            clip['crop']={'unit':'normalized','x':.1,'y':.1,'height':.6,'fit':'stretch',
                'keyframes':[track('width',.7,.5,stop=9000)]}
            preview=case.execute(end=2);actual=case.reference(preview)
            source=np.rint(pixels.astype(np.float64)*65535).astype(np.float32)/65535
            expected=np.stack([scalar_project(source[i],(3.2,1.6,32*(.7-.2*i),9.6),(32,16),'stretch') for i in range(2)])
            np.testing.assert_allclose(actual,expected,rtol=0,atol=1.2e-7)
            frame=case.execute(mode='frame');png=case.png(frame)
            np.testing.assert_allclose(png, np.rint(expected[0].astype(np.float64)*65535).astype(np.uint16),rtol=0,atol=1)
            case.p['settings']['canvas']['background']='#000000';case.p['settings']['output']=opaque
            from ai_ad_editor.render import render_project
            from ai_ad_editor.project import project_write_lock
            with project_write_lock(case.root):formal=render_project(case.root,case.p,case.s,case.root/'renders/crop.mkv')
            delivered=np.ones_like(expected)
            delivered[...,:3]=(expected[...,:3].astype(np.float64)*expected[...,3:4].astype(np.float64)).astype(np.float32)
            payload=np.moveaxis(np.rint(delivered[...,[1,2,0,3]].astype(np.float64)*65535).astype('<u2'),3,1).tobytes()
            manifest=json.loads(Path(formal['path']).with_suffix('.mkv.manifest.json').read_bytes())
            self.assertEqual(manifest['delivery']['pixel_pipeline']['transport']['video_input_sha256'],'sha256:'+hashlib.sha256(payload).hexdigest())
            raw=case.native([ffmpeg_path(),'-nostdin','-v','error','-i',formal['path'],'-an','-pix_fmt','yuv444p10le','-f','rawvideo','pipe:1'])
            expected_path=case.root/'expected-crop.gbrap16';expected_path.write_bytes(payload)
            expected_movie=case.root/'expected-crop.mkv'
            case.native([ffmpeg_path(),'-nostdin','-v','error','-f','rawvideo','-pixel_format','gbrap16le','-video_size','32x16','-framerate','10',
                '-color_range','pc','-colorspace','rgb','-color_primaries','bt709','-color_trc','linear','-i',expected_path,
                '-vf','format=gbrp16le,zscale=primariesin=709:transferin=linear:matrixin=gbr:rangein=full:primaries=709:transfer=linear:matrix=709:range=limited:chromal=left:dither=none,format=yuv444p10le',
                '-c:v','libx264','-crf','0','-preset','ultrafast',expected_movie])
            oracle=case.native([ffmpeg_path(),'-nostdin','-v','error','-i',expected_movie,'-an','-pix_fmt','yuv444p10le','-f','rawvideo','pipe:1'])
            self.assertEqual(raw,oracle);case.assert_clean()
        finally:
            case.tearDown();case.doCleanups()


if __name__=='__main__':unittest.main()
