"""YCbCr code/range/siting references and real native high-precision decodes."""
from fractions import Fraction
import hashlib
import math
from pathlib import Path
import subprocess
import tempfile
import unittest
import numpy as np
from ai_ad_editor.errors import AppError
from ai_ad_editor.float_yuv import YUVSpec,decode_frame,frame_bytes,layout
from ai_ad_editor.float_yuv_source import NativeYUVSource
from ai_ad_editor.media import ffmpeg_path

NATIVE_CALLS=[]

def digest(data):return 'sha256:'+hashlib.sha256(data).hexdigest()

def pack(y,u,v,*,alpha=None,endian='<u2'):
    return b''.join(p.astype(endian).tobytes() for p in (y,u,v,*(() if alpha is None else (alpha,))))

def scalar(y,u,v,x,yy,*,sx,sy,location,bits,matrix,value_range):
    # Fixed independent scalar oracle: sample four neighbours explicitly, then
    # solve green from the original luminance equation (not decoder formula).
    ox=0 if 'left' in location else (sx-1)/2
    oy=0 if location.startswith('top') else sy-1 if location.startswith('bottom') else (sy-1)/2
    px=max(0,min(u.shape[1]-1,(x-ox)/sx));py=max(0,min(u.shape[0]-1,(yy-oy)/sy))
    xx0,yy0=math.floor(px),math.floor(py);xx1=min(xx0+1,u.shape[1]-1);yy1=min(yy0+1,u.shape[0]-1)
    def sample(p):
        return sum(float(p[j,i])*w for i,j,w in ((xx0,yy0,(1-px+xx0)*(1-py+yy0)),
            (xx1,yy0,(px-xx0)*(1-py+yy0)),(xx0,yy1,(1-px+xx0)*(py-yy0)),(xx1,yy1,(px-xx0)*(py-yy0))))
    if value_range=='limited':
        scale=2**(bits-8);l=(float(y[yy,x])-16*scale)/(219*scale);cb=(sample(u)-128*scale)/(224*scale);cr=(sample(v)-128*scale)/(224*scale)
    else:
        maximum=2**bits-1;l=float(y[yy,x])/maximum;cb=(sample(u)-2**(bits-1))/maximum;cr=(sample(v)-2**(bits-1))/maximum
    kr,kb={'bt709':(.2126,.0722),'bt470bg':(.299,.114),'smpte170m':(.299,.114),'bt2020nc':(.2627,.0593)}[matrix]
    r=l+cr*(2-2*kr);b=l+cb*(2-2*kb);g=(l-kr*r-kb*b)/(1-kr-kb)
    return r,g,b

class FloatYUVTests(unittest.TestCase):
    def test_all_65536_full_range_neutral_luma_values_survive(self):
        y=np.arange(65536,dtype=np.uint16).reshape(64,1024);c=np.full_like(y,32768)
        value,meta=decode_frame(pack(y,c,c),'yuv444p16le',1024,64,spec=YUVSpec('bt709','full','center'))
        expected=y.astype(np.float64)/65535
        for channel in range(3):
            np.testing.assert_array_equal(np.rint(value[...,channel].astype(np.float64)*65535).astype(np.uint16),y)
            self.assertEqual(np.unique(value[...,channel]).size,65536)
        self.assertTrue(np.all(value[...,3]==1));self.assertFalse(meta['HDR_accepted'])
        self.assertLess(float(np.max(np.abs(value[...,0]-expected))),3e-8)

    def test_broadcast_limited_ten_bit_black_white_and_headroom(self):
        y=np.array([[0,64,502,940,1023]],np.uint16);c=np.full_like(y,512)
        value,meta=decode_frame(pack(y,c,c),'yuv444p10le',5,1,spec=YUVSpec('bt709','limited','left'))
        np.testing.assert_allclose(value[0,:,0],[-64/876,0,.5,1,959/876],rtol=0,atol=6e-8)
        self.assertTrue(np.all(value[...,3]==1));self.assertEqual(meta['alpha_range'],'full')

    def test_all_matrices_ranges_subsampling_and_locations_match_scalar_oracle(self):
        rng=np.random.default_rng(7096012020);w,h=7,5
        for sampling,sx,sy in [('444',1,1),('422',2,1),('420',2,2)]:
            y=rng.integers(0,1024,(h,w),dtype=np.uint16);u=rng.integers(0,1024,((h+sy-1)//sy,(w+sx-1)//sx),dtype=np.uint16);v=rng.integers(0,1024,u.shape,dtype=np.uint16)
            for matrix in ('bt709','smpte170m','bt470bg','bt2020nc'):
                for vr in ('full','limited'):
                    for loc in ('left','center','topleft','top','bottomleft','bottom'):
                        with self.subTest(sampling=sampling,matrix=matrix,range=vr,location=loc):
                            value,_=decode_frame(pack(y,u,v),'yuv'+sampling+'p10le',w,h,spec=YUVSpec(matrix,vr,loc))
                            expected=np.array([[scalar(y,u,v,x,yy,sx=sx,sy=sy,location=loc,bits=10,matrix=matrix,value_range=vr) for x in range(w)] for yy in range(h)])
                            np.testing.assert_allclose(value[...,:3],expected,rtol=0,atol=1.2e-7)

    def test_chroma_sites_change_edges_and_odd_sized_planes_remain_bounded(self):
        y=np.full((3,5),128,np.uint8);u=np.array([[0,96,255],[255,160,0]],np.uint8);v=np.full_like(u,128)
        outputs=[]
        for loc in ('left','center','topleft','top','bottomleft','bottom'):
            value,_=decode_frame(pack(y,u,v,endian='u1'),'yuv420p',5,3,spec=YUVSpec('bt709','full',loc));outputs.append(value.tobytes())
        self.assertEqual(len(set(outputs)),6)
        self.assertEqual(frame_bytes('yuv420p',5,3),27)

    def test_alpha_uses_full_range_and_keeps_all_sixteen_bit_codes(self):
        a=np.arange(65536,dtype=np.uint16).reshape(64,1024);y=np.full_like(a,4096);c=np.full_like(a,32768)
        value,meta=decode_frame(pack(y,c,c,alpha=a),'yuva444p16le',1024,64,spec=YUVSpec('bt709','limited','center'))
        self.assertTrue(np.all(value[...,:3]==0));np.testing.assert_array_equal(np.rint(value[...,3].astype(np.float64)*65535).astype(np.uint16),a)
        self.assertEqual(np.unique(value[...,3]).size,65536);self.assertTrue(meta['source_has_alpha'])

    def test_integer_bit_depths_and_big_endian_match_declared_codes(self):
        for bits in (9,10,12,14,16):
            maximum=2**bits-1;y=np.array([[0,maximum//3,maximum]],np.uint16);c=np.full_like(y,2**(bits-1))
            for endian in ('le','be'):
                value,_=decode_frame(pack(y,c,c,endian='<u2' if endian=='le' else '>u2'),'yuv444p'+str(bits)+endian,3,1,spec=YUVSpec('bt2020nc','full','center'))
                np.testing.assert_allclose(value[...,:3],np.repeat((y.astype(np.float64)/maximum)[...,None],3,-1),rtol=0,atol=3e-8)

    def test_native_NV12_NV21_and_P010_P012_P016_equal_planar_values(self):
        rng=np.random.default_rng(61022);w,h=6,4
        for bits,names in [(8,('nv12','nv21')),(10,('p010le','p010be')),(12,('p012le','p012be')),(16,('p016le','p016be'))]:
            y=rng.integers(0,2**bits,(h,w),dtype=np.uint16);u=rng.integers(0,2**bits,(h//2,w//2),dtype=np.uint16);v=rng.integers(0,2**bits,u.shape,dtype=np.uint16)
            fmt='yuv420p'+('' if bits==8 else str(bits)+'le');vr=YUVSpec('bt709','limited','left')
            expected,_=decode_frame(pack(y,u,v,endian='u1' if bits==8 else '<u2'),fmt,w,h,spec=vr)
            for name in names:
                info=layout(name);uv=np.stack((v,u) if name=='nv21' else (u,v),-1)
                # Padding is deliberately nonzero; native MSB formats ignore it.
                shift=16-bits if bits>8 else 0
                yy=np.left_shift(y,shift);pair=np.left_shift(uv,shift)
                if shift:yy|=(1<<shift)-1;pair|=(1<<shift)-1
                raw=yy.astype(info.dtype).tobytes()+pair.astype(info.dtype).tobytes()
                actual,_=decode_frame(raw,name,w,h,spec=vr);np.testing.assert_array_equal(actual,expected)

    def test_below_black_and_above_white_RGB_are_preserved(self):
        y=np.array([[0,65535]],np.uint16);u=np.array([[0,65535]],np.uint16);v=np.array([[65535,0]],np.uint16)
        value,_=decode_frame(pack(y,u,v),'yuv444p16le',2,1,spec=YUVSpec('bt709','limited','center'))
        self.assertLess(float(value[...,:3].min()),0);self.assertGreater(float(value[...,:3].max()),1)

    def test_explicit_premultiplied_alpha_unassociates_and_canonicalizes_zero(self):
        y=np.array([[0,64,128]],np.uint8);c=np.full_like(y,128);a=np.array([[0,128,255]],np.uint8)
        value,_=decode_frame(pack(y,c,c,alpha=a,endian='u1'),'yuva444p',3,1,spec=YUVSpec('bt709','full','center'),alpha_association='premultiplied')
        np.testing.assert_array_equal(value[0,0],0);np.testing.assert_allclose(value[0,1,:3],.5,atol=6e-8,rtol=0)

    def test_invalid_metadata_native_bytes_codes_dimensions_and_budgets_reject(self):
        for args in [('auto','limited','left'),('bt2020c','full','left'),('bt709','guess','left'),('bt709','full','unknown'),('bt709;movie=x','full','left'),([],{},None)]:
            with self.assertRaises(AppError):YUVSpec(*args)
        spec=YUVSpec('bt709','full','center');y=np.ones((2,2),np.uint16)*1024
        with self.assertRaises(AppError):decode_frame(pack(y,y,y),'yuv444p10le',2,2,spec=spec)
        raw=bytes(12)
        for changes in ({'raw':raw[:-1]},{'raw':memoryview(bytearray(24))[::2]},{'pixel_format':'yuyv422'},
                {'width':True},{'height':0},{'width':16385},{'max_working_bytes':1},{'max_working_bytes':True},
                {'spec':None},{'alpha_association':'auto'},{'cancel':1}):
            kwargs=dict(raw=raw,pixel_format='yuv444p',width=2,height=2,spec=spec);kwargs.update(changes)
            with self.subTest(changes=str(changes)):
                with self.assertRaises(AppError):decode_frame(**kwargs)

    def test_output_owns_memory_and_source_bytearray_is_unchanged(self):
        source=bytearray([16,64,128,235,128,128,128,128,128,128,128,128]);before=bytes(source)
        value,_=decode_frame(source,'yuv444p',2,2,spec=YUVSpec('bt709','limited','center'))
        self.assertTrue(value.flags.c_contiguous);self.assertFalse(np.shares_memory(value,np.frombuffer(source,np.uint8)))
        value.fill(0);self.assertEqual(bytes(source),before)

    def test_cancellation_is_polled_during_large_frame_conversion(self):
        raw=bytes(1024*96*3);calls=[]
        def cancel():
            calls.append(1)
            if len(calls)==4:raise AppError('CANCELLED','test cancellation',exit_code=8)
        with self.assertRaises(AppError) as caught:decode_frame(raw,'yuv444p',1024,96,spec=YUVSpec('bt709','full','center'),cancel=cancel)
        self.assertEqual(caught.exception.code,'CANCELLED');self.assertEqual(len(calls),4)

    def test_explicit_progressive_scan_is_required_before_decoder(self):
        for scan in (None,'auto','interlaced'):
            with self.assertRaises(AppError) as caught:NativeYUVSource('.',__file__,digest(Path(__file__).read_bytes()),spec=YUVSpec('bt709','full','left'),scan=scan)
            self.assertEqual(caught.exception.code,'FLOAT_YUV_SCAN')

    def test_actual_native_FFV1_YUV16_VFR_source_keeps_all_codes_and_clock(self):
        base=Path(__file__).resolve().parents[1]/'.runtime/temp';base.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='yuv-float-',dir=base) as name:
            root=Path(name);y=np.arange(65536,dtype=np.uint16).reshape(64,1024);c=np.full_like(y,32768)
            raw=root/'source.yuv444p16le';raw.write_bytes(pack(y,c,c)*2);source=root/'source.nut'
            command=[ffmpeg_path(),'-v','error','-f','rawvideo','-pixel_format','yuv444p16le','-video_size','1024x64','-framerate','8',
                '-color_range','pc','-colorspace','bt709','-color_primaries','bt709','-color_trc','bt709','-i',str(raw),
                '-vf',"setpts='(N*3/8+5)/TB'",'-fps_mode','passthrough','-c:v','ffv1','-level','3','-color_range','pc','-colorspace','bt709','-color_primaries','bt709','-color_trc','bt709',str(source)]
            p=subprocess.run(command,capture_output=True,timeout=60,creationflags=subprocess.CREATE_NO_WINDOW)
            NATIVE_CALLS.append({'test':self.id(),'command':command,'exit_code':p.returncode,'stderr_sha256':digest(p.stderr)})
            self.assertEqual(p.returncode,0,p.stderr.decode('utf8','replace'))
            # Verify the actual encoded original before attributing any later
            # error to the float decoder. Forced output tags alone can trigger
            # integer YUV->RGB->YUV while creating this lossless fixture.
            command=[ffmpeg_path(),'-v','verbose','-i',str(source),'-map','0:v:0','-an','-frames:v','2',
                '-pix_fmt','yuv444p16le','-fps_mode','passthrough','-f','rawvideo','pipe:1']
            p=subprocess.run(command,capture_output=True,timeout=60,creationflags=subprocess.CREATE_NO_WINDOW)
            NATIVE_CALLS.append({'test':self.id(),'purpose':'independent-encoded-original-native-code-verification',
                'command':command,'exit_code':p.returncode,'stderr_sha256':digest(p.stderr),'stdout_sha256':digest(p.stdout)})
            self.assertEqual(p.returncode,0,p.stderr.decode('utf8','replace'));self.assertEqual(p.stdout,raw.read_bytes())
            self.assertNotIn('auto-inserting filter',p.stderr.decode('utf8','replace'))
            with NativeYUVSource(root,source,digest(source.read_bytes()),spec=YUVSpec('bt709','full','center'),scan='progressive') as reader:
                frames=list(reader);self.assertEqual(len(frames),2)
                for index,frame in enumerate(frames):
                    self.assertEqual(frame.pts*frame.time_base,Fraction(5)+Fraction(index*3,8))
                    for channel in range(3):np.testing.assert_array_equal(np.rint(frame.rgba[...,channel].astype(np.float64)*65535).astype(np.uint16),y)
                self.assertTrue(reader.complete);self.assertFalse(reader.metadata['scan_automatically_verified'])
            NATIVE_CALLS.append({'test':self.id(),'command':reader.metadata['command'],'exit_code':reader.pipe.process.poll(),
                'decoded_frames':reader.position,'native_index':reader.metadata['native_index'],'requested_prefix_complete':reader.complete})

    def test_actual_native_zscale_float_RGB_agrees_for_limited_and_full_444(self):
        base=Path(__file__).resolve().parents[1]/'.runtime/temp';base.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='yuv-zscale-oracle-',dir=base) as name:
            root=Path(name);rng=np.random.default_rng(70916);y=rng.integers(0,65536,(8,16),dtype=np.uint16);u=rng.integers(0,65536,y.shape,dtype=np.uint16);v=rng.integers(0,65536,y.shape,dtype=np.uint16)
            raw=pack(y,u,v);source=root/'source.yuv444p16le';source.write_bytes(raw)
            for vr in ('full','limited'):
                ours,_=decode_frame(raw,'yuv444p16le',16,8,spec=YUVSpec('bt709',vr,'center'))
                command=[ffmpeg_path(),'-v','verbose','-f','rawvideo','-pixel_format','yuv444p16le','-video_size','16x8','-i',str(source),
                    '-vf','zscale=matrixin=bt709:rangein='+vr+':primariesin=bt709:transferin=bt709:matrix=gbr:range=full:primaries=bt709:transfer=bt709:dither=none,format=gbrpf32le',
                    '-frames:v','1','-f','rawvideo','pipe:1']
                p=subprocess.run(command,capture_output=True,timeout=60,creationflags=subprocess.CREATE_NO_WINDOW)
                row={'test':self.id(),'command':command,'exit_code':p.returncode,'output_sha256':digest(p.stdout),'stderr_sha256':digest(p.stderr)};NATIVE_CALLS.append(row)
                self.assertEqual(p.returncode,0,p.stderr.decode('utf8','replace'));self.assertNotIn('auto-inserting filter',p.stderr.decode('utf8','replace'))
                native=np.moveaxis(np.frombuffer(p.stdout,'<f4').reshape(3,8,16)[[2,0,1]],0,-1)
                row['maximum_absolute_error']=float(np.max(np.abs(ours[...,:3].astype(np.float64)-native)))
                np.testing.assert_allclose(ours[...,:3],native,rtol=0,atol=5e-7)
