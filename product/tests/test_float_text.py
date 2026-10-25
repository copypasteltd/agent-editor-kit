"""Real native glyphs against independent linear color, clock and media oracles."""
import copy
from fractions import Fraction as F
import hashlib
from pathlib import Path
import subprocess
import tempfile
import threading
import unittest
from unittest.mock import patch

import numpy as np
from PIL import ImageFont

from ai_ad_editor.errors import AppError
from ai_ad_editor.float_color_signal import ColorSignal
from ai_ad_editor.float_text import FloatTextHost
from ai_ad_editor.float_timeline import FloatTimeline,TimedSurfaceSource
from ai_ad_editor.media import ffmpeg_path

LINEAR=ColorSignal('bt709','linear')
NATIVE_CALLS=[]
TEXT_RECEIPTS=[]


def linear(rgb):
    x=np.asarray(rgb,dtype=np.float64)/255
    return np.where(x<=.04045,x/12.92,((x+.055)/1.055)**2.4)


class FloatTextTests(unittest.TestCase):
    def setUp(self):
        base=Path(__file__).resolve().parents[1]/'.runtime/temp';base.mkdir(parents=True,exist_ok=True)
        self.temporary=tempfile.TemporaryDirectory(prefix='float-text-',dir=base)
        self.addCleanup(self.temporary.cleanup);self.root=Path(self.temporary.name)
        (self.root/'assets').mkdir()
        self.font=self.root/'assets/local.ttf';self.font.write_bytes(ImageFont.load_default(size=16).path.getvalue())
        self.assets={'font':{'id':'font','kind':'font','uri':'assets/local.ttf',
            'sha256':'sha256:'+hashlib.sha256(self.font.read_bytes()).hexdigest()}}
        self.host=FloatTextHost(self.root,self.assets,LINEAR,100,F(10))
        self.size=(240,100)

    def title(self,text='HHHH',**style):
        return {'id':'title','generator':{'type':'text'},'timeline_start_tick':0,'duration_tick':100,
            'source_in_tick':0,'source_out_tick':100,'subtitle':{'text':text,'style':{
                'font_asset_id':'font','fontsize':32,'fontcolor':'#4080c080','box':False,'x':'10','y':'20',**style}}}

    def sample(self,clip=None,tick=0,*,left=False,size=None,host=None):
        host=host or self.host;plan=host.prepare(clip or self.title(),independent=True)
        value,record=host.sample(plan,F(tick,100),F(tick),size or self.size,left_limit=left)
        TEXT_RECEIPTS.append({'test':self.id(),**copy.deepcopy(record)})
        return value,record

    def native_coverage(self,component,style):
        # Independent RGBA8 raster and Python float64 source-over oracle.
        colors={k:('white' if k==component else 'black@0') for k in
            ('fontcolor','bordercolor','shadowcolor','boxcolor')}
        opts=dict(fontfile="'assets/local.ttf'",fontsize=32,x=10,y=20,box=1,boxborderw=5,borderw=3,shadowx=5,shadowy=4)
        opts.update(style);opts.update(colors)
        graph='color=c=black:s=240x100:r=1:d=1,format=rgba,drawtext=text=HHHH:'+':'.join(f'{k}={v}' for k,v in opts.items())
        cmd=[ffmpeg_path(),'-nostdin','-v','error','-filter_threads','1','-f','lavfi','-i',graph,
            '-frames:v','1','-pix_fmt','rgba','-f','rawvideo','-']
        result=subprocess.run(cmd,cwd=self.root,capture_output=True,timeout=60,creationflags=subprocess.CREATE_NO_WINDOW)
        NATIVE_CALLS.append({'test':self.id(),'argv':cmd,'exit_code':result.returncode,
            'stdout_sha256':hashlib.sha256(result.stdout).hexdigest(),'stderr':result.stderr.decode('utf8','replace')})
        self.assertEqual(result.returncode,0,result.stderr)
        return np.frombuffer(result.stdout,np.uint8).reshape(100,240,4)[:,:,0].astype(np.float64)/255

    def project(self,clip=None):
        return {'settings':{'canvas':{'width':240,'height':100,'background':'transparent'},
            'timebase':{'ticks_per_second':100,'display_fps':{'num':10,'den':1}}},
            'assets':list(self.assets.values()),'sequences':[{'id':'main','duration_tick':100,
            'tracks':[{'id':'titles','kind':'subtitle','clips':[clip or self.title()]}]}]}

    def timeline(self,p,sources=None):
        return FloatTimeline(p,'main',sources or {},working_signal=LINEAR,resource_root=self.root)

    def test_half_alpha_and_srgb_EOTF_match_independent_reference(self):
        a,receipt=self.sample();alpha=a[:,:,3];solid=alpha>0
        self.assertAlmostEqual(float(alpha.max()),128/255,places=7)
        np.testing.assert_allclose(a[solid,:3],np.broadcast_to(linear([64,128,192]),(solid.sum(),3)),atol=2e-7,rtol=0)
        self.assertGreater(np.count_nonzero(~solid),1000)
        self.assertTrue(np.all(a[~solid,:3]==0))
        self.assertEqual(self.host.coverage_profile['max_code_error'],0)
        self.assertEqual(self.host.coverage_profile['codes_checked'],256)
        self.assertFalse(receipt['media_pixels_in_native_graph'])

    def test_box_shadow_border_and_fill_match_four_independent_coverage_rasters(self):
        palette={'boxcolor':'#32649660','shadowcolor':'#dc502080','bordercolor':'#2064dc90','fontcolor':'#4080c080'}
        a,_=self.sample(self.title(box=True,boxborderw=5,borderw=3,shadowx=5,shadowy=4,**palette))
        reference=np.zeros_like(a,dtype=np.float64)
        for key in ('boxcolor','shadowcolor','bordercolor','fontcolor'):
            rgba=[int(palette[key][i:i+2],16) for i in (1,3,5,7)]
            af=self.native_coverage(key,{})*rgba[3]/255;ab=reference[:,:,3]
            total=af+ab*(1-af)
            numerator=linear(rgba[:3])[None,None,:]*af[:,:,None]+reference[:,:,:3]*(ab*(1-af))[:,:,None]
            reference[:,:,:3]=np.divide(numerator,total[:,:,None],out=np.zeros_like(numerator),where=total[:,:,None]>0)
            reference[:,:,3]=total
        np.testing.assert_allclose(a,reference,atol=3e-7,rtol=0)

    def test_inline_text_preserves_sub_8bit_media_and_source_over_is_linear(self):
        p=self.project();c=p['sequences'][0]['tracks'][0]['clips'][0]
        c.pop('generator');c['asset_id']='media';p['sequences'][0]['tracks'][0]['kind']='video'
        sha='sha256:'+'b'*64;p['assets'].append({'id':'media','kind':'image','sha256':sha})
        media=np.ones((100,240,4),np.float32)
        media[:,:,:3]=np.arange(24000,dtype=np.float32).reshape(100,240,1)/30000
        source=TimedSurfaceSource([0],[0],'1/100',0,lambda i:media,signal=LINEAR,source_sha256=sha,still=True)
        actual,metadata=self.timeline(p,{'media':source}).render_frame(0)
        glyph,_=self.sample();alpha=glyph[:,:,3,None].astype(np.float64)
        expected=media.astype(np.float64);expected[:,:,:3]=glyph[:,:,:3]*alpha+media[:,:,:3]*(1-alpha)
        np.testing.assert_allclose(actual,expected,atol=2e-7,rtol=0)
        clear=glyph[:,:,3]==0
        np.testing.assert_array_equal(actual[clear],media[clear])
        self.assertGreater(len(np.unique(actual[clear,0])),256)
        self.assertEqual(metadata['layers'][0]['text']['placement'],'after-media-effects-before-clip-projection')

    def test_typewriter_exact_boundary_and_left_limit_use_prefix_not_CFR_movie(self):
        c=self.title('HHHH',fontcolor='white');c['subtitle']['animation']={'type':'typewriter','duration':1}
        a,r=self.sample(c,25);b,s=self.sample(c,25,left=True)
        self.assertEqual(r['layouts'][0]['typing']['revealed_graphemes'],2)
        self.assertEqual(s['layouts'][0]['typing']['revealed_graphemes'],1)
        self.assertGreater(np.count_nonzero(a[:,:,3]),np.count_nonzero(b[:,:,3]))
        self.assertEqual(r['layouts'][0]['typing']['command_count'],0)
        self.assertFalse(r['frame_grid_quantization'])

    def test_subframe_thirds_do_not_round_typewriter_to_nanoseconds(self):
        c=self.title('HHH');c['subtitle']['animation']={'type':'typing','duration':1}
        a,r=self.sample(c,F(100,3));b,s=self.sample(c,F(100,3),left=True)
        self.assertEqual(r['layouts'][0]['typing']['revealed_graphemes'],2)
        self.assertEqual(s['layouts'][0]['typing']['revealed_graphemes'],1)
        self.assertGreater(np.count_nonzero(a[:,:,3]),np.count_nonzero(b[:,:,3]))

    def test_animation_alpha_is_applied_once_after_component_source_over(self):
        c=self.title(box=True,boxcolor='#20406080',borderw=2,bordercolor='#c0602080')
        plain,_=self.sample(c)
        c['subtitle']['animation']={'type':'fade_in','duration':1}
        a,_=self.sample(c,50)
        np.testing.assert_allclose(a[:,:,3],plain[:,:,3]*.5,atol=1e-7,rtol=0)
        visible=a[:,:,3]>0
        np.testing.assert_array_equal(a[visible,:3],plain[visible,:3])

    def test_frozen_media_keeps_title_presentation_clock_running(self):
        c=self.title('HHHH');c['subtitle']['animation']={'type':'typing','duration':1}
        c['freeze']={'at_tick':20,'duration_tick':30}
        p=self.project(c);_,r=self.timeline(p).render_frame(4)
        self.assertEqual(r['layers'][0]['text']['clock_tick'],'40')
        self.assertEqual(r['layers'][0]['text']['layouts'][0]['typing']['revealed_graphemes'],2)

    def test_typewriter_complete_paragraph_anchor_and_graphemes(self):
        c=self.title('H\u0301H H\nHH',fontcolor='white',x='(w-text_w)/2',y='(h-text_h)/2')
        c['subtitle']['animation']={'type':'typing','duration':1}
        a,r=self.sample(c,0);b,s=self.sample(c,90)
        self.assertEqual(r['layouts'][0]['typing']['grapheme_count'],6)
        self.assertEqual(r['layouts'][0]['typing']['line_count'],2)
        self.assertTrue(np.all(b[a[:,:,3]>.99,3]>.99))

    def test_highlight_uses_two_linear_paragraphs_with_identical_alpha(self):
        c=self.title('HHHH HHHH',fontsize=24,fontcolor='#4080c080',active_color='#c0804080')
        c['subtitle']['word_timing']=[{'text':'HHHH','start':0,'end':.5},{'text':'HHHH','start':.5,'end':1}]
        a,r=self.sample(c,25);b,_=self.sample(c,75)
        np.testing.assert_array_equal(a[:,:,3],b[:,:,3])
        changed=np.any(a[:,:,:3]!=b[:,:,:3],axis=2)&(a[:,:,3]>0)
        self.assertGreater(changed.sum(),100)
        for v in (a,b):
            colors=v[v[:,:,3]>0,:3].astype(np.float64)
            distance=np.min(np.max(np.abs(colors[:,None,:]-linear([[64,128,192],[192,128,64]])[None,:,:]),axis=2),axis=1)
            self.assertLess(float(distance.max()),3e-7)
        self.assertEqual(r['layouts'][0]['color_selection'],'binary-whole-paragraph-paints')

    def test_highlight_and_typewriter_share_one_snapshot_clock(self):
        c=self.title('HH HH',fontsize=24)
        c['subtitle']['animation']={'type':'typing','duration':1}
        c['subtitle']['word_timing']=[{'text':'HH','start':0,'end':.5},{'text':'HH','start':.5,'end':1}]
        a,r=self.sample(c,40);b,s=self.sample(c,80)
        self.assertEqual(r['layouts'][0]['typing']['revealed_graphemes'],3)
        self.assertEqual(s['layouts'][0]['typing']['revealed_graphemes'],5)
        self.assertGreater(np.count_nonzero(b[:,:,3]),np.count_nonzero(a[:,:,3]))

    def test_plain_SRT_half_open_windows_and_clip_clock_offset(self):
        srt=self.root/'assets/test.srt';srt.write_text('1\n00:00:00,000 --> 00:00:00,500\nHH\n\n2\n00:00:00,500 --> 00:00:01,000\nHHHH\n',encoding='utf8')
        c=self.title();c['subtitle'].pop('text');c['subtitle']['asset_uri']='assets/test.srt'
        a,_=self.sample(c,50);b,_=self.sample(c,50,left=True);d,_=self.sample(c,100)
        self.assertGreater(np.count_nonzero(a[:,:,3]),np.count_nonzero(b[:,:,3]))
        self.assertFalse(np.any(d))
        c['subtitle'].update(asset_time_base='clip',asset_time_offset_tick=50)
        e,_=self.sample(c,0);np.testing.assert_array_equal(a,e)

    def test_nested_reverse_propagates_title_left_limit(self):
        c=self.title('HHHH',fontcolor='white');c['subtitle']['animation']={'type':'typing','duration':1}
        p=self.project(c);child=copy.deepcopy(p['sequences'][0]);child['id']='child'
        parent={'id':'parent','sequence_id':'child','timeline_start_tick':0,'duration_tick':100,
            'source_in_tick':0,'source_out_tick':100,'reverse':True}
        p['sequences'][0]['tracks']=[{'id':'nest','kind':'video','clips':[parent]}];p['sequences'].append(child)
        h=self.timeline(p);a,r=h.render_frame(5)
        expected,s=self.sample(c,50,left=True)
        np.testing.assert_array_equal(a,expected)
        self.assertEqual(r['layers'][0]['text']['layouts'][0]['typing']['revealed_graphemes'],2)
        self.assertEqual(s['author_frame_number'],4)

    def test_trim_window_keeps_original_presentation_clock(self):
        c=self.title('HHHH');c['subtitle']['animation']={'type':'typing','duration':1}
        c.update(duration_tick=50,presentation_window={'version':1,'authored_start_tick':0,'offset_tick':50,'authored_duration_tick':100})
        p=self.project(c);a,r=self.timeline(p).render_frame(0)
        expected,_=self.sample(self.title('HHHH'),50)
        self.assertEqual(r['layers'][0]['text']['clock_tick'],'50')
        self.assertEqual(r['layers'][0]['text']['layouts'][0]['typing']['revealed_graphemes'],3)
        self.assertGreater(np.count_nonzero(expected[:,:,3]),np.count_nonzero(a[:,:,3]))

    def test_text_rotation_and_clip_transform_are_additive(self):
        c=self.title();c['subtitle']['animation']={'type':'rotate','duration':1,'from':0,'to':90}
        p=self.project(c);p['settings']['timebase']['display_fps']={'num':2,'den':1}
        a,r=self.timeline(p).render_frame(1)
        c2=copy.deepcopy(c);c2['subtitle'].pop('animation');c2['transform']={'rotation':45,'opacity':.5}
        b,_=self.timeline(self.project(c2)).render_frame(0)
        np.testing.assert_allclose(a,b,atol=2e-7,rtol=0)
        self.assertEqual(r['layers'][0]['text']['rotation_degrees'],45)

    def test_LRU_copies_do_not_leak_mutations_and_eviction_is_bounded(self):
        host=FloatTextHost(self.root,self.assets,LINEAR,100,F(10),cache_bytes=240*100*16)
        plan=host.prepare(self.title(),independent=True)
        a,_=host.sample(plan,0,0,self.size);a[:]=7
        b,r=host.sample(plan,F(1,2),50,self.size)
        self.assertTrue(r['cache_hit']);self.assertLess(float(b.max()),1)
        plan2=host.prepare(self.title('HH'),independent=True);host.sample(plan2,0,0,self.size)
        self.assertEqual(len(host.cache),1);self.assertEqual(host.cached_bytes,240*100*16)

    def test_font_SHA_changes_and_runtime_changes_are_not_accepted(self):
        plan=self.host.prepare(self.title(),independent=True)
        self.font.write_bytes(self.font.read_bytes()+b'changed')
        with self.assertRaisesRegex(AppError,'发生变化'):self.host.verify()
        with self.assertRaisesRegex(AppError,'SHA'):self.host.prepare(self.title(),independent=True)

    def test_4K_native_text_admission_rejects_before_process_start(self):
        plan=self.host.prepare(self.title(),independent=True)
        with patch('ai_ad_editor.float_text._TextPipe') as native:
            with self.assertRaisesRegex(AppError,'预算'):self.host.sample(plan,0,0,(3840,2160))
            native.assert_not_called()

    def test_unsupported_fonts_styles_rich_captions_and_stateful_expressions_fail(self):
        cases=[]
        c=self.title();c['subtitle']['style'].pop('font_asset_id');cases.append(c)
        c=self.title(blur=3);cases.append(c)
        c=self.title(x='random(1)');cases.append(c)
        c=self.title(expansion='normal');cases.append(c)
        c=self.title();c['subtitle']['animation']={'type':'unknown'};cases.append(c)
        for c in cases:
            with self.subTest(clip=c),self.assertRaises(AppError):self.host.prepare(c,independent=True)
        srt=self.root/'assets/test.srt';srt.write_text('1\n00:00:00,000 --> 00:00:00,500\n<b>HH</b>\n',encoding='utf8')
        c=self.title();c['subtitle'].pop('text');c['subtitle']['asset_uri']='assets/test.srt'
        with self.assertRaises(AppError):self.host.prepare(c,independent=True)

    def test_cancellation_after_native_start_closes_owned_pipe_threads(self):
        from ai_ad_editor import float_text
        plan=self.host.prepare(self.title(),independent=True);self.host._coverage_conversion()
        original=float_text._TextPipe
        class CancelledPipe(original):
            def check(self):raise AppError('TEXT_TEST_CANCELLED','cancelled',exit_code=130)
        with patch.object(float_text,'_TextPipe',CancelledPipe),self.assertRaisesRegex(AppError,'cancelled'):
            self.host.sample(plan,0,0,self.size)
        self.assertFalse([t for t in threading.enumerate() if t.name.startswith('float-native-')])
