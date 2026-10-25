"""Native regression oracles, independent geometry and scanline isolation."""
from __future__ import annotations

import math
from pathlib import Path
import subprocess
import tempfile
import unittest

from PIL import Image, ImageDraw

from ai_ad_editor.media import ffmpeg_path
from ai_ad_editor.render import (_dynamic_crop_filters, _sequence_raster_filters,
    _expr_arg, _transform_exprs, _geq_scanline_expression)
from ai_ad_editor.runtime import configure_local_runtime
from projection_legacy_oracle import legacy_dynamic_crop_filters, legacy_sequence_raster_filters


class ProjectionScanlineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        configure_local_runtime()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.image = Image.new('RGBA', (83,67))
        self.image.putdata([((x*23)%256,(y*31)%256,((x+y)*17)%256,
            (0,23,128,255)[(x+y)%4]) for y in range(67) for x in range(83)])

    def transform(self, **values):
        result = dict(scale='.87+T*.13', rotation='17+T*27', position_x='.47+T*.03',
                      position_y='.53', anchor_x='.39', anchor_y='.62', opacity='1')
        result.update(values)
        return result

    def render(self, kind, *, legacy=False, crop=None, clip=None, transform=None, sampling='bilinear',
               alpha=True, threads=1, clock=None, image=None, target=(79,53)):
        source = self.base/'input.png'; (image or self.image).save(source)
        sw,sh=(image or self.image).size;tw,th=target
        clip = dict(clip or {}, crop=crop or {'unit':'normalized','x':.11,'y':.07,'width':.73,'height':.81,'fit':'fit'})
        if kind == 'crop':
            function = legacy_dynamic_crop_filters if legacy else _dynamic_crop_filters
            filters = function(clip,clip['crop'],tw,th,sw,sh,.25,90000,alpha=alpha)
        else:
            function = legacy_sequence_raster_filters if legacy else _sequence_raster_filters
            filters = function(clip,transform or self.transform(),{'width':sw,'height':sh},
                {'width':tw,'height':th},.25,90000,sampling=sampling)
        chain=['format=rgba']
        if clock:chain.append('setpts='+_expr_arg(clock))
        chain.extend(filters)
        graph = self.base/'graph.txt';graph.write_text(','.join(chain),encoding='utf-8')
        result = subprocess.run([ffmpeg_path(),'-hide_banner','-v','error','-filter_threads',str(threads),
            '-loop','1','-framerate','4','-i',str(source),'-filter_script:v',str(graph),'-frames:v','4',
            '-fps_mode','passthrough','-f','rawvideo','-pix_fmt','rgba','pipe:1'],capture_output=True,timeout=90)
        self.assertEqual(result.returncode,0,result.stderr.decode('utf-8','replace'))
        self.assertEqual(len(result.stdout),tw*th*4*4)
        return result.stdout

    def compare(self, kind, **options):
        actual=self.render(kind,**options);expected=self.render(kind,legacy=True,**options)
        self.assertEqual(actual,expected)
        self.assertGreater(max(actual[3::4]),100,'An empty output does not prove sampling')
        return actual

    def keys(self):
        return [{'property':'crop.width','keyframes':[
            {'at_tick':0,'value':.6,'interpolation':'bezier','control_points':[.2,.1,.8,.9]},
            {'at_tick':90000,'value':.9}]},
            {'property':'crop.x','keyframes':[{'at_tick':0,'value':.05,'interpolation':'hold'},
                {'at_tick':45000,'value':.1},{'at_tick':90000,'value':.02}]}]

    def test_dynamic_crop_all_fit_modes_and_alpha_contracts(self):
        for fit in ('fit','fill','stretch'):
            for alpha in (False,True):
                with self.subTest(fit=fit,alpha=alpha):
                    self.compare('crop',crop={'unit':'normalized','width':.73,'height':.81,'x':.11,'y':.07,'fit':fit},
                                 clip={'keyframes':self.keys()},alpha=alpha,threads=7)

    def test_projection_all_fit_modes_both_sampling_methods(self):
        for fit in ('fit','fill','stretch'):
            for sampling in ('bilinear','area'):
                with self.subTest(fit=fit,sampling=sampling):
                    self.compare('sequence',crop={'width':61.2,'height':47.9,'x':8.3,'y':5.1,'fit':fit},
                                 sampling=sampling,threads=7)

    def test_animated_normalized_crop_and_keyed_motion_keep_old_pixels(self):
        clip={'keyframes':self.keys()+[{'property':'transform.rotation','keyframes':[
            {'at_tick':0,'value':-17.,'interpolation':'bezier','control_points':[.3,0,.7,1]},
            {'at_tick':90000,'value':35.}]}]}
        transform=_transform_exprs(clip,.25,90000)
        for sampling in ('bilinear','area'):
            self.compare('sequence',clip=clip,transform=transform,sampling=sampling,threads=7)

    def test_repeated_backward_timestamps_do_not_leave_row_constants_stale(self):
        for kind,sampling in (('crop','bilinear'),('sequence','bilinear'),('sequence','area')):
            with self.subTest(kind=kind,sampling=sampling):
                self.compare(kind,clip={'keyframes':self.keys()},sampling=sampling,threads=7,
                             clock='if(lt(N,2),2,if(eq(N,2),1,3))/TB')

    def test_plane_and_slice_threads_have_independent_state(self):
        for kind,sampling in (('crop','bilinear'),('sequence','bilinear'),('sequence','area')):
            first=self.compare(kind,sampling=sampling,threads=1)
            for threads in (2,7):
                self.assertEqual(first,self.compare(kind,sampling=sampling,threads=threads))

    def test_mismatched_odd_source_parent_canvases(self):
        for target in ((37,93),(109,31)):
            for sampling in ('bilinear','area'):
                self.compare('sequence',sampling=sampling,target=target,threads=7)

    def test_quarter_turn_extreme_anchor_and_negative_scale(self):
        for angle,scale,anchor in ((90,.4,0),(-31,1.7,1),(379,-.9,.27)):
            for sampling in ('bilinear','area'):
                self.compare('sequence',sampling=sampling,transform=self.transform(
                    rotation=str(angle),scale=str(scale),anchor_x=str(anchor)))

    def test_hidden_rgb_does_not_pollute_bilinear_or_area_edges(self):
        a=self.image.copy();b=self.image.copy()
        for y in range(67):
            for x in range(83):
                if a.getpixel((x,y))[3]==0:
                    a.putpixel((x,y),(0,0,0,0));b.putpixel((x,y),(0,255,0,0))
        for kind,sampling in (('crop','bilinear'),('sequence','bilinear'),('sequence','area')):
            self.assertEqual(self.compare(kind,sampling=sampling,image=a),self.compare(kind,sampling=sampling,image=b))

    def test_nested_reverse_keyframe_clock(self):
        from ai_ad_editor.time_mapping import make_map
        mapping=make_map(dict(timeline_start_tick=22500,source_in_tick=0,source_out_tick=90000,
                             duration_tick=90000,reverse=True),[],90000)
        clip={'keyframes':self.keys(),'_nested_keyframe_clock':{'maps':[mapping],'authored_start':0}}
        for kind,sampling in (('crop','bilinear'),('sequence','bilinear'),('sequence','area')):
            self.compare(kind,clip=clip,sampling=sampling,clock='(N/4+0.25)/TB',threads=7)

    def test_all_crop_and_transform_channels_exceed_register_capacity_safely(self):
        channels = [('crop.width',.67,.82),('crop.height',.7,.85),('crop.x',.1,.02),('crop.y',.05,.1),
                    ('transform.rotation',-17.,20.),('transform.scale',.8,1.2),
                    ('transform.position.x',.4,.55),('transform.position.y',.45,.6),
                    ('transform.anchor.x',.4,.6),('transform.anchor.y',.55,.45)]
        clip={'keyframes':[{'property':prop,'keyframes':[
            {'at_tick':0,'value':first,'interpolation':'bezier','control_points':[.2,.1,.8,.9]},
            {'at_tick':90000,'value':last}]} for prop,first,last in channels]}
        transform=_transform_exprs(clip,.25,90000)
        for sampling in ('bilinear','area'):
            with self.subTest(sampling=sampling):
                self.compare('sequence',clip=clip,transform=transform,sampling=sampling,threads=7)

    def test_stateful_pixel_and_unknown_calls_retain_old_path(self):
        for transform in (self.transform(rotation='T*17+X*.1'),
                          self.transform(position_x='.5+st(8,.02)'),
                          self.transform(scale='1+ld(9)*0')):
            for sampling in ('bilinear','area'):
                self.compare('sequence',transform=transform,sampling=sampling,threads=2)

    def test_marker_follows_independent_forward_geometry(self):
        image=Image.new('RGBA',(83,67),(0,0,0,0))
        ImageDraw.Draw(image).ellipse((47,22,51,26),fill=(255,0,0,255))
        transform=self.transform(rotation='-20+T*60',scale='.8',position_x='.5',position_y='.5',anchor_x='.5',anchor_y='.5')
        raw=self.render('sequence',image=image,crop={'fit':'stretch'},transform=transform,target=(83,67),threads=7)
        size=83*67*4
        for frame in range(4):
            data=raw[frame*size:(frame+1)*size]
            points=[(i%83,i//83) for i in range(83*67) if data[i*4]>200 and data[i*4+3]>100]
            self.assertTrue(points)
            actual=tuple(sum(p[axis] for p in points)/len(points) for axis in (0,1))
            angle=math.radians(-20+frame/4*60);dx,dy=(49+.5-83*.5)*.8,(24+.5-67*.5)*.8
            expected=(83*.5+dx*math.cos(angle)-dy*math.sin(angle)-.5,
                      67*.5+dx*math.sin(angle)+dy*math.cos(angle)-.5)
            for a,b in zip(actual,expected):self.assertLessEqual(abs(a-b),.7)

    def test_row_compiler_rejects_unsafe_allocation_and_non_pure_definitions(self):
        for definitions,body,registers in (({'a':'@{b}'},'@{a}',(0,)),
                ({'a':'T'},'st(0,@{a})',(0,)),({'a':'T'},'@{a}',(10,)),
                ({'a':'random(0)'},'@{a}',(0,)),({'a':'X'},'@{a}',(0,)),
                ({'a':'T'},'@{a}',(0,0))):
            with self.subTest(definitions=definitions,body=body,registers=registers):
                with self.assertRaises(ValueError):_geq_scanline_expression(definitions,body,registers)


if __name__=='__main__':unittest.main()
