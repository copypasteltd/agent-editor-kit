"""Actual ACES author delivery, preview clocks and independently invoked OCIO reference."""
import copy,hashlib,shutil,unittest
from pathlib import Path
from unittest.mock import patch
import numpy as np
from ai_ad_editor import ocio_runtime as ocio
from ai_ad_editor.aces_pipeline import dependency_paths
from ai_ad_editor.errors import AppError
from ai_ad_editor.float_color_signal import _to_linear
from ai_ad_editor.float_standard_render import configuration,FloatRenderContext
from ai_ad_editor.media import ffmpeg_path
from ai_ad_editor.project import save_project,load_project,project_write_lock
from ai_ad_editor.render import output_settings,render_project
from test_float_standard_render import FloatStandardRenderTests
from test_ocio_runtime import selection

RECEIPTS=[]
class ACESPipelineTests(unittest.TestCase):
    def setUp(self):
        self.f=FloatStandardRenderTests('runTest');self.f.setUp();self.addCleanup(self.f.doCleanups)
        self.s=self.f.p['settings'];self.p=self.s['pixel_pipeline']
        self.p.update(working_signal=dict(primaries='aces-ap1',transfer='linear'),
            output_signal=dict(primaries='bt709',transfer='srgb',reference_white_nits=100),aces_display=selection(),range_policy='clip')
        self.s['color'].update(primaries='bt709',transfer='iec61966-2-1',matrix='bt709')

    def visual(self,h=16,w=32,frames=8):
        self.f.s['duration_tick']=frames*9000
        source=np.zeros((frames,h,w,4),np.float32);source[:,:,:,3]=1
        levels=np.array([.01,.04,.18,.5,.9,.04,.7,.1],np.float32)
        for i in range(frames):
            source[i,:,:,0]=np.tile(levels,w//len(levels))
            source[i,:,:,1]=np.roll(source[i,:,:,0],i%5,axis=1)*.7+.01
            source[i,:,:,2]=.1+i*.02
        self.f.visual(source)
        self.p['sources']['picture']['source_signal']=copy.deepcopy(self.p['working_signal'])
        self.samples=self.f.audio()
        from ai_ad_editor.rights import load_ledger,save_ledger,add_record
        audio=self.f.p['assets'][-1];audio['rights_ref']='rights_audio'
        ledger=load_ledger(self.f.root)
        add_record(ledger,dict(record_id='rights_audio',asset_id='sound',verification_status='verified',source_type='generated',
            source_url=str(self.f.root/'assets/audio.wav'),license_spdx='CC0-1.0',permitted_uses=['all'],
            commercial_use_allowed=True,modification_allowed=True,attribution_required=False,sha256=audio['sha256'],evidence='Original stereo numeric tones.'))
        save_ledger(self.f.root,ledger)
        self.f.s['tracks'][1]['clips'][0].update(id='audio_clip',duration_tick=frames*9000,source_out_tick=frames*9000)
        save_project(self.f.root,self.f.p)
        return (np.rint(source.astype(np.float64)*65535)/65535).astype(np.float32)

    def native_reference(self,source,value=None):
        value=value or self.p['aces_display'];out=source.copy()
        out[:,:,:3]=(out[:,:,:3].astype(np.float64)*2**value['exposure_stops']).astype(np.float32)
        o=ocio.native();c=ocio.config(value['config'])
        c.getProcessor(o.DisplayViewTransform(src='ACEScg',display=value['display'],view=value['view'])).getDefaultCPUProcessor().applyRGBA(out.reshape(-1,4))
        out[:,:,3]=source[:,:,3];return out

    def pcm(self,path):return self.f.native([ffmpeg_path(),'-nostdin','-v','error','-i',path,'-map','0:a:0','-vn','-c:a','pcm_f32le','-f','f32le','pipe:1'])

    def test_actual_SDR_transport_native_reference_and_complete_package_replay(self):
        source=self.visual();f=self.f;first=f.execute('aces.mkv');meta=first['delivery']['pixel_pipeline']
        expected=b''
        for a in source:
            out=self.native_reference(a);codes=np.rint(np.clip(out.astype(np.float64),0,1)*65535).astype('<u2')
            expected+=np.moveaxis(codes[:,:,[1,2,0,3]],2,0).tobytes()
        self.assertEqual(meta['transport']['video_input_sha256'],'sha256:'+hashlib.sha256(expected).hexdigest())
        self.assertEqual(meta['aces_display']['frames'],8);self.assertTrue(meta['ACES_processors_closed'])
        code,meter=f.invoke('surface','measure','--project',f.root,'--sequence-id',f.s['id'])
        self.assertEqual(code,0,meter)
        self.assertEqual(meter['data']['encoder_RGB16_input_sha256'],meta['transport']['video_input_sha256'])
        self.assertEqual(meter['data']['frames'],8)
        archive=f.root/'exports/aces.zip';code,value=f.invoke('convert','export','--project',f.root,'--output',archive,'--target-format','package');self.assertEqual(code,0,value)
        restored=f.base/'restored';code,value=f.invoke('convert','import','--input',archive,'--output',restored);self.assertEqual(code,0,value)
        _,p=load_project(restored);self.assertEqual(p['settings']['pixel_pipeline'],self.p)
        with project_write_lock(restored):second=render_project(restored,p,p['sequences'][0],restored/'renders/again.mkv')
        self.assertEqual(f.decode_y(first['path'],32,16).tobytes(),f.decode_y(second['path'],32,16).tobytes())
        self.assertEqual(self.pcm(first['path']),self.pcm(second['path']));self.assertEqual(self.pcm(first['path']),self.samples[:38400].tobytes())
        f.assert_clean();RECEIPTS.append(dict(scope='SDR-8-frame-transport-package-pixels-complete-PCM',first=first,second=second,meter=meter['data'],transport_reference_sha256=hashlib.sha256(expected).hexdigest()))

    def test_actual_preview_maps_once_before_display_linear_resize(self):
        source=self.visual(128,96,2);f=self.f;before=(f.root/'project.json').read_bytes()
        code,v=f.invoke('preview','frame','--project',f.root,'--frame','1','--height','128');self.assertEqual(code,0,v)
        frame=v['data'];raw=f.native([ffmpeg_path(),'-nostdin','-v','error','-i',frame['path'],'-an','-pix_fmt','rgba64le','-f','rawvideo','pipe:1'])
        actual=np.frombuffer(raw,'<u2').reshape(128,96,4)
        expected=np.rint(np.clip(self.native_reference(source[1]).astype(np.float64),0,1)*65535)
        self.assertLessEqual(float(np.max(abs(actual.astype(np.float64)-expected))),2)
        code,v=f.invoke('preview','range','--project',f.root,'--start-frame','0','--end-frame','2','--height','64');self.assertEqual(code,0,v)
        window=v['data'];raw=f.native([ffmpeg_path(),'-nostdin','-v','error','-i',window['master'],'-map','0:v:0','-an','-pix_fmt','gbrapf32le','-f','rawvideo','pipe:1'])
        actual=np.frombuffer(raw,'<f4').reshape(2,4,64,48)
        for i in range(2):
            linear=_to_linear(self.native_reference(source[i])[:,:,:3].astype(np.float64),'srgb')
            expected=linear.reshape(64,2,48,2,3).mean(axis=(1,3))
            np.testing.assert_allclose(actual[i,:3],np.moveaxis(expected[:,:,[1,2,0]],2,0),rtol=4e-6,atol=6e-7)
        self.assertEqual(window['pixel_pipeline']['aces_display']['frames'],2)
        self.assertEqual((f.root/'project.json').read_bytes(),before);f.assert_clean()
        RECEIPTS.append(dict(scope='actual-SDR-frame-and-two-frame-display-linear-range',frame=frame,window=window))

    def hdr(self,transfer):
        self.p['working_signal']['reference_white_nits']=100
        self.p['output_signal']=dict(primaries='bt2020',transfer=transfer,reference_white_nits=203)
        if transfer=='hlg-bt2100':self.p['output_signal'].update(display_peak_nits=1000,system_gamma=1.2)
        self.s['color'].update(primaries='bt2020',matrix='bt2020nc',transfer='smpte2084' if transfer=='pq-st2084' else 'arib-std-b67')
        display='Rec.2100-PQ - Display' if transfer=='pq-st2084' else 'Rec.2100-HLG - Display'
        c=ocio.config('aces-2.1');view=next(v for v in c.getViews(display) if v.startswith('ACES ') and '1000 nits' in v)
        self.p['aces_display']={**selection(), 'display':display,'view':view}
        self.p['aces_preview']=selection()

    def test_actual_PQ_and_HLG_delivery_and_separate_SDR_view(self):
        for transfer in ('pq-st2084','hlg-bt2100'):
            with self.subTest(transfer=transfer):
                if transfer=='hlg-bt2100':self.setUp()
                self.hdr(transfer);self.visual(64,64,2);result=self.f.execute(transfer+'.mkv');m=result['delivery']['pixel_pipeline']
                self.assertEqual(m['aces_display']['frames'],2);self.assertEqual(m['aces_preview']['frames'],0)
                code,v=self.f.invoke('preview','frame','--project',self.f.root,'--frame','1','--height','64');self.assertEqual(code,0,v)
                p=v['data']['pixel_pipeline'];self.assertEqual(p['aces_display']['frames'],0);self.assertEqual(p['aces_preview']['frames'],1)
                self.assertEqual(v['data']['request']['aces_display_source'],'aces_preview')
                RECEIPTS.append(dict(scope='actual-'+transfer+'-and-independent-SDR-view',result=result,preview=v['data']))

    def test_invalid_working_and_conflicting_mappings(self):
        from test_float_gamut import MAPPING
        for change in [dict(working_signal=dict(primaries='bt709',transfer='linear')),
                       dict(display_mapping=MAPPING),dict(aces_preview=selection(),preview_mapping=MAPPING),
                       dict(aces_display={**selection(),'view':'Raw'}),dict(aces_display={**selection(),'display':'Display P3 - Display'})]:
            p={**copy.deepcopy(self.p),**change}
            with self.subTest(change=change),self.assertRaises(AppError):configuration(p,self.s,output_settings(self.s))

    def test_HDR_HLG_conditions_are_not_silently_reinterpreted(self):
        self.hdr('hlg-bt2100')
        for field,value in [('display_peak_nits',2000),('system_gamma',1.1),('display_black_nits',.01)]:
            p=copy.deepcopy(self.p);p['output_signal'][field]=value
            with self.subTest(field=field),self.assertRaises(AppError):configuration(p,self.s,output_settings(self.s))

    def test_Rec1886_and_Gamma22_delivery_decode_native_display_transfer(self):
        from ai_ad_editor.float_color_signal import _from_linear
        a=np.array([[[.04,.18,.9,1],[2,.2,.01,1]]],np.float32)
        for display,transfer in [('Rec.1886 Rec.709 - Display','gamma24'),('Gamma 2.2 Rec.709 - Display','gamma22')]:
            value={**selection(),'display':display};self.p['aces_display']=value
            ctx=FloatRenderContext(self.f.root,self.f.p,self.f.s,output_settings(self.s))
            with ocio.DisplayTransform(value) as transform:
                ctx.aces_transforms={'aces_display':transform}
                actual,_=ctx.delivery_surface(a,stats={})
                ref=self.native_reference(a,value)
                expected=_from_linear(_to_linear(ref[:,:,:3].astype(np.float64),transfer),'srgb')
                np.testing.assert_allclose(actual[:,:,:3],expected,rtol=3e-6,atol=4e-7)

    def test_HDR_preview_requires_explicit_SDR_view(self):
        from ai_ad_editor.float_preview import reference_plan
        self.hdr('pq-st2084');self.p.pop('aces_preview')
        with self.assertRaises(AppError):reference_plan(self.f.p,'frame')

    def test_meter_accepts_relative_scene_ACES_only_with_explicit_output_nits(self):
        from ai_ad_editor import hdr_measure
        recipe=hdr_measure.prepare(self.f.p,self.f.s['id'])
        self.assertIn('recipe_sha256',recipe)
        without=copy.deepcopy(self.f.p);without['settings']['pixel_pipeline'].pop('aces_display')
        with self.assertRaises(AppError):hdr_measure.prepare(without,self.f.s['id'])
        without=copy.deepcopy(self.f.p);without['settings']['pixel_pipeline']['output_signal'].pop('reference_white_nits')
        with self.assertRaises(AppError):hdr_measure.prepare(without,self.f.s['id'])

    def test_actual_dependency_snapshots_and_corrupt_runtime_refusal(self):
        from ai_ad_editor.preview import plan,identity
        from ai_ad_editor.queue_reuse import _dependency_paths
        self.visual(64,64,1);f=self.f;request=plan(f.p,f.s,start_frame=0,end_frame=1,height=64,mode='frame')
        deps=dependency_paths(self.p);self.assertEqual(len(deps),7)
        self.assertTrue(deps<=_dependency_paths(f.root,f.p,self.s))
        snap=identity(f.root,f.p,f.s,request,None)
        self.assertTrue({str(p) for p in deps}<={d['path'] for d in snap['dependencies']})
        copyroot=f.base/'bad-runtime';copyroot.mkdir();shutil.copy(ocio.__file__,copyroot/'ocio_runtime.py')
        for path in ocio.runtime_paths()[1:]:
            relative=path.relative_to(Path(ocio.__file__).parent);dest=copyroot/relative;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copy(path,dest)
        binary=copyroot/'native_ocio/PyOpenColorIO.pyd';data=bytearray(binary.read_bytes());data[-1]^=1;binary.write_bytes(data)
        with patch.object(ocio,'__file__',str(copyroot/'ocio_runtime.py')):
            with self.assertRaises(AppError):identity(f.root,f.p,f.s,request,None)
            with self.assertRaises(AppError):_dependency_paths(f.root,f.p,self.s)
            with self.assertRaises(AppError):
                with FloatRenderContext(f.root,f.p,f.s,output_settings(self.s)):pass
        f.assert_clean()

if __name__=='__main__':unittest.main()
