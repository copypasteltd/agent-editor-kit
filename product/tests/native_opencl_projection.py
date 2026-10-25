"""Explicit native-GPU regression suite; run by the evidence driver, no skips.

The expected geometry and pixels come from the retained pre-0.1.19 CPU
implementation, independent marker geometry and cell-overlap integration.
"""
from __future__ import annotations

import math
import hashlib
from pathlib import Path
import struct
import subprocess

from ai_ad_editor.media import ffmpeg_path
from ai_ad_editor.projection_opencl import ProjectionSession, HEADER, quote, device_info
from ai_ad_editor.render import (_dynamic_crop_filters, _sequence_raster_filters,
    _affine_video_filters, _expr_arg)
from projection_legacy_oracle import legacy_dynamic_crop_filters, legacy_sequence_raster_filters
from test_projection_scanline_cache import ProjectionScanlineTests


class NativeOpenCLProjectionTests(ProjectionScanlineTests):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.device = device_info('0.0')  # Absence is an error in this explicit suite.

    def setUp(self):
        super().setUp()
        self.number = 0

    def execute_graph(self, source, graph, *, gpu, threads, frames=4, pixel_format='rgba',
                      width=None, height=None):
        self.number += 1
        file = self.base/f'graph-{self.number}.txt'
        file.write_text('[0:v]'+graph+'[out]', encoding='utf8')
        args = [ffmpeg_path(), '-hide_banner', '-v', 'error', '-nostdin',
                '-filter_complex_threads', str(threads)]
        if gpu:
            args += ['-init_hw_device', 'opencl=aek_projection:0.0', '-filter_hw_device', 'aek_projection']
        if isinstance(source, list):
            args += source
        else:
            args += ['-loop', '1', '-framerate', '4', '-i', str(source)]
        args += ['-/filter_complex', str(file), '-map', '[out]', '-frames:v', str(frames),
                 '-fps_mode', 'passthrough', '-f', 'rawvideo', '-pix_fmt', pixel_format, 'pipe:1']
        result = subprocess.run(args, cwd=self.base, capture_output=True, timeout=90)
        self.assertEqual(result.returncode, 0, result.stderr.decode('utf8','replace'))
        if width and height:
            self.assertEqual(len(result.stdout), width*height*4*(4 if pixel_format=='gbrapf32le' else 1)*frames)
        return result.stdout

    def render(self, kind, *, legacy=False, crop=None, clip=None, transform=None, sampling='bilinear',
               alpha=True, threads=1, clock=None, image=None, target=(79,53)):
        source = self.base/'input.png'; (image or self.image).save(source)
        sw,sh=(image or self.image).size;tw,th=target
        clip = dict(clip or {}, crop=crop or {'unit':'normalized','x':.11,'y':.07,'width':.73,'height':.81,'fit':'fit'})
        projection=ProjectionSession(self.base,{'projection_acceleration':{'mode':'prefer'}},'test-'+str(self.number))
        options={} if legacy else {'projection':projection}
        if kind == 'crop':
            function = legacy_dynamic_crop_filters if legacy else _dynamic_crop_filters
            filters = function(clip,clip['crop'],tw,th,sw,sh,.25,90000,alpha=alpha,**options)
        else:
            function = legacy_sequence_raster_filters if legacy else _sequence_raster_filters
            filters = function(clip,transform or self.transform(),{'width':sw,'height':sh},
                {'width':tw,'height':th},.25,90000,sampling=sampling,**options)
        chain=['format=rgba']
        if clock:chain.append('setpts='+_expr_arg(clock))
        chain.extend(filters)
        if projection.replacements:projection.write_programs()
        result=self.execute_graph(source,','.join(chain),gpu=bool(projection.replacements),
                                  threads=threads,width=tw,height=th)
        if not legacy:
            pure = not any('pixel/stateful' in n.get('reason','') for n in projection.evidence['nodes'])
            self.assertEqual(bool(projection.replacements),pure)
        return result

    def test_affine_clock_quarter_turn_and_extreme_anchors(self):
        source=self.base/'affine.png';self.image.save(source)
        for clock in ('N/4/TB','if(lt(N,2),2,if(eq(N,2),1,3))/TB'):
            for angle,scale,anchor in (('17+T*27','.87+T*.13','.39'),('90','.4','0'),
                                       ('-31','1.7','1'),('379','-.9','.27')):
                transform=self.transform(rotation=angle,scale=scale,anchor_x=anchor)
                cpu=_affine_video_filters(transform)
                projection=ProjectionSession(self.base,{'projection_acceleration':{'mode':'require'}},'affine-'+str(self.number))
                gpu=_affine_video_filters(transform,projection=projection,width=83,height=67)
                self.assertTrue(projection.replacements);projection.write_programs()
                start=['format=rgba','setpts='+_expr_arg(clock)]
                expected=self.execute_graph(source,','.join(start+cpu),gpu=False,threads=7,width=83,height=67)
                actual=self.execute_graph(source,','.join(start+gpu),gpu=True,threads=7,width=83,height=67)
                self.assertEqual(actual,expected)

    def test_prefix_retains_cpu_order_and_all_binary64_bits(self):
        width,height,frames=17,13,3
        # Large cancellations, small terms and Float32 subnormals exercise the
        # prefix transport; this oracle does not call the GPU's prefix code.
        choices=(.25,1e20,1e-20,-1e20,2**23,-.125,1e-40,.7312345)
        values=[struct.unpack('<f',struct.pack('<f',choices[(i*7+i//17)%len(choices)]))[0]
                for i in range(width*height*4*frames)]
        source=self.base/'prefix-source.gbrapf32le'
        source.write_bytes(struct.pack('<'+'f'*len(values),*values))
        kernel=self.base/'prefix.cl';kernel.write_text('#define INTEGER_SOURCE 0\n'+HEADER,encoding='utf8')
        graph=(f'format=gbrapf32le,hwupload,program_opencl=source={quote(kernel.name)}:kernel=row_prefix:inputs=1:'
               f'size={3*width}x{height},program_opencl=source={quote(kernel.name)}:kernel=column_prefix:inputs=1:'
               f'size={3*width}x{height},hwdownload,format=gbrapf32le')
        raw=self.execute_graph(['-f','rawvideo','-pixel_format','gbrapf32le','-video_size',f'{width}x{height}',
            '-framerate','4','-i',str(source)],graph,gpu=True,threads=7,frames=frames,
            pixel_format='gbrapf32le',width=3*width,height=height)
        actual=struct.unpack('<'+'f'*(len(raw)//4),raw)
        for plane in range(frames*4):
            prefix=[]
            for y in range(height):
                total=0.;row=[]
                for x in range(width):
                    total+=values[plane*width*height+y*width+x];row.append(total)
                prefix.append(row)
            for x in range(width):
                total=0.
                for y in range(height):
                    total+=prefix[y][x]
                    offset=plane*width*height*3+(y*width+x)*3
                    a,b,c=actual[offset:offset+3]
                    self.assertEqual(struct.pack('<d',(a+b)+c),struct.pack('<d',total),
                                     (plane,x,y,(a,b,c),total))

    def test_area_matches_independent_fractional_cell_overlap(self):
        from PIL import Image
        image=Image.new('RGBA',(83,67));image.putdata([
            ((x%5)*55,(y%7)*35,((x+y)%3)*120,255) for y in range(67) for x in range(83)])
        crop={'x':8.3,'y':5.1,'width':61.2,'height':47.9,'fit':'stretch'}
        transform=self.transform(rotation='17',scale='.8',position_x='.5',position_y='.5',
                                 anchor_x='.39',anchor_y='.62')
        raw=self.compare('sequence',image=image,crop=crop,transform=transform,sampling='area')
        cosine,sine=math.cos(math.radians(17)),math.sin(math.radians(17))
        fw,fh=max(1.,1/(.8*79/61.2)),max(1.,1/(.8*53/47.9))
        for X,Y in ((0,0),(1,1),(40,26),(17,13),(62,37),(78,52)):
            dx,dy=X+.5-79*.5,Y+.5-53*.5
            cx=8.3+.39*61.2+(dx*cosine+dy*sine)/(.8*79/61.2)
            cy=5.1+.62*47.9+(-dx*sine+dy*cosine)/(.8*53/47.9)
            left,right=max(8.3,min(69.5,cx-fw/2)),max(8.3,min(69.5,cx+fw/2))
            top,bottom=max(5.1,min(53.,cy-fh/2)),max(5.1,min(53.,cy+fh/2))
            channels=[0.,0.,0.];coverage=0.
            for y in range(max(0,math.floor(top)),min(67,math.ceil(bottom))):
                for x in range(max(0,math.floor(left)),min(83,math.ceil(right))):
                    weight=max(0.,min(right,x+1)-max(left,x))*max(0.,min(bottom,y+1)-max(top,y))/(fw*fh)
                    coverage+=weight
                    for c in range(3):channels[c]+=image.getpixel((x,y))[c]*weight
            offset=(Y*79+X)*4;expected=[round(v/coverage) if coverage else 0 for v in channels]+[round(255*coverage)]
            for actual,want in zip(raw[offset:offset+4],expected):self.assertLessEqual(abs(actual-want),2)

    def large_image(self,size):
        from PIL import Image,ImageDraw
        image=Image.new('RGBA',size,(83,132,197,255));draw=ImageDraw.Draw(image)
        w,h=size
        for x in range(0,w,19):
            draw.line((x,0,x,h-1),fill=((x*17)%256,29,211,64+(x%192)),width=3)
        draw.rectangle((w//7,h//6,w//2,h*3//4),fill=(240,87,23,173))
        draw.ellipse((w//2,h//5,w*4//5,h*4//5),fill=(11,239,53,81))
        draw.rectangle((0,0,w//12,h//12),fill=(0,255,0,0))
        return image

    def test_1080p_and_4k_affine_full_frame_equality(self):
        for width,height in ((1920,1080),(3840,2160)):
            image=self.large_image((width,height));source=self.base/f'large-{width}.png';image.save(source)
            transform=self.transform(rotation='17.123456789',scale='.79123456789',
                position_x='.47123456789',position_y='.53123456789',anchor_x='.39123456789')
            projection=ProjectionSession(self.base,{'projection_acceleration':{'mode':'require','max_working_bytes':4*1024**3}},
                'large-affine-'+str(width))
            gpu=_affine_video_filters(transform,projection=projection,width=width,height=height)
            projection.write_programs()
            expected=self.execute_graph(source,','.join(['format=rgba']+_affine_video_filters(transform)),
                gpu=False,threads=7,frames=1,width=width,height=height)
            actual=self.execute_graph(source,','.join(['format=rgba']+gpu),gpu=True,threads=7,
                frames=1,width=width,height=height)
            self.assertTrue(actual==expected,(width,height,hashlib.sha256(actual).hexdigest(),hashlib.sha256(expected).hexdigest()))

    def test_4k_area_prefix_and_fractional_minification_full_frame(self):
        width,height=3840,2160;target=(960,540)
        source=self.base/'large-area.png';self.large_image((width,height)).save(source)
        clip={'crop':{'unit':'normalized','x':.031,'y':.057,'width':.831,'height':.793,'fit':'stretch'}}
        transform=self.transform(rotation='17.123456789',scale='.79123456789',position_x='.47123456789')
        projection=ProjectionSession(self.base,{'projection_acceleration':{'mode':'require','max_working_bytes':4*1024**3}},'large-area')
        arguments=(clip,transform,{'width':width,'height':height},{'width':target[0],'height':target[1]},.25,90000)
        cpu=_sequence_raster_filters(*arguments,sampling='area')
        gpu=_sequence_raster_filters(*arguments,sampling='area',projection=projection)
        projection.write_programs()
        expected=self.execute_graph(source,','.join(['format=rgba']+cpu),gpu=False,threads=7,frames=1,
                                    width=target[0],height=target[1])
        actual=self.execute_graph(source,','.join(['format=rgba']+gpu),gpu=True,threads=7,frames=1,
                                  width=target[0],height=target[1])
        self.assertTrue(actual==expected,(hashlib.sha256(actual).hexdigest(),hashlib.sha256(expected).hexdigest()))
