"""Actual native CMM, independent matrix/gamma, lifecycle and editable ICC sources."""
import copy,ctypes as C,hashlib,json,math,tempfile,unittest,zipfile
from pathlib import Path
import numpy as np
from PIL import Image,ImageCms
from ai_ad_editor.errors import AppError
from ai_ad_editor import icc_profiles as icc
from ai_ad_editor.float_color_signal import ColorSignal
from ai_ad_editor.float_chromatic import WhitePointSignal,WhitePointLuminanceSignal,D50,D60
from ai_ad_editor.float_hdr import LuminanceSignal
from ai_ad_editor.project import save_project,load_project,project_write_lock
from ai_ad_editor.render import render_project
from ai_ad_editor.media import ffmpeg_path
from ai_ad_editor.schema_contract import make_validator
from test_float_color_signal import XYZ,surface

RECEIPTS=[]

def create_profile(path,primaries='bt709',gamma=2.2,white=None,version=4.3):
    """Generate original test profile via CMM authoring,not product converter."""
    a=icc.api(icc.runtime_paths()[2]);a.cmsSetProfileVersion.argtypes=[C.c_void_p,C.c_double];a.cmsSetProfileVersion.restype=None
    ctx=a.cmsCreateContext(None,None);xy=white or icc.white_of(ColorSignal(primaries,'linear'))
    w=icc.xyY(*xy,1);prim=icc.Primaries(*(icc.xyY(x,y,1) for x,y in icc.PRIMARIES[primaries]));curve=a.cmsBuildGamma(ctx,gamma)
    p=None
    try:
        p=a.cmsCreateRGBProfileTHR(ctx,C.byref(w),C.byref(prim),(C.c_void_p*3)(curve,curve,curve));assert p
        a.cmsSetProfileVersion(p,version);n=C.c_uint32();assert a.cmsSaveProfileToMem(p,None,C.byref(n))
        b=C.create_string_buffer(n.value);assert a.cmsSaveProfileToMem(p,b,C.byref(n));path.write_bytes(b.raw[:n.value])
    finally:
        if p:a.cmsCloseProfile(p)
        a.cmsFreeToneCurve(curve);a.cmsDeleteContext(ctx)
    return dict(icc_profile=path.name,sha256=icc.sha(path),intent='relative-colorimetric')

class ICCNumericTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.path=self.root/'original.icc';self.signal=icc.parse_source_signal(create_profile(self.path))
    def test_actual_native_profile_and_context_close(self):
        with icc.ProfileTransform(self.root,self.signal,ColorSignal('bt709','linear')) as t:
            self.assertTrue(t.metadata['matrix_shaper']);self.assertEqual(t.metadata['CMM_encoded_version'],2190)
        self.assertTrue(t.metadata['native_handles_closed']);self.assertTrue(t.closed)
        with self.assertRaises(AppError):t.convert(surface([[.2,.3,.4]]))
    def test_gamma_matrix_matches_independent_double_precision_oracle(self):
        a=surface([[.02,.1,.5],[.3,.6,.8],[1,0,0]])
        with icc.ProfileTransform(self.root,self.signal,ColorSignal('bt2020','linear')) as t:b,m=t.convert(a)
        expected=np.einsum('ij,hwj->hwi',np.linalg.inv(XYZ['bt2020'])@XYZ['bt709'],a[...,:3].astype(float)**2.2)
        error=float(np.max(np.abs(b[...,:3]-expected)));self.assertLess(error,1.6e-4)
        self.assertEqual(a[...,3].tobytes(),b[...,3].tobytes());RECEIPTS.append(dict(test=self.id(),maximum_error=error,receipt=m))
    def test_v2_and_v4_actual_profiles_are_supported(self):
        for v in (2.1,4.3):
            p=self.root/('v'+str(v)+'.icc');signal=icc.parse_source_signal(create_profile(p,version=v))
            with icc.ProfileTransform(self.root,signal,ColorSignal('bt709','linear')) as t:
                b,_=t.convert(surface([[.5,.5,.5]]));self.assertAlmostEqual(float(b[0,0,0]),.5**2.2,places=4)
                self.assertEqual(t.metadata['header']['version_major'],int(v))
    def test_D50_and_D60_profiles_do_not_drop_white_adaptation(self):
        p=self.root/'D50.icc';s=icc.parse_source_signal(create_profile(p,'prophoto-rgb',1.8))
        a=surface([[.18,.18,.18],[.7,.7,.7]])
        for target in (ColorSignal('bt709','linear'),WhitePointSignal('aces-ap1','linear',D60)):
            with icc.ProfileTransform(self.root,s,target) as t:b,_=t.convert(a)
            np.testing.assert_allclose(b[...,:3],a[...,:3].astype(float)**1.8,rtol=0,atol=2e-4)
    def test_absolute_nits_are_separate_from_profile_white(self):
        signal=icc.ICCSourceSignal(self.signal.icc_profile,self.signal.sha256,self.signal.intent,reference_white_nits=100)
        with icc.ProfileTransform(self.root,signal,LuminanceSignal('bt709','linear',200)) as t:b,m=t.convert(surface([[1,1,1]]))
        np.testing.assert_allclose(b[...,:3],.5,rtol=0,atol=2e-4);self.assertEqual(m['linear_unit_scale'],.5)
    def test_all_four_intents_are_native_transforms(self):
        for intent in icc.INTENTS:
            signal=icc.ICCSourceSignal(self.signal.icc_profile,self.signal.sha256,intent,True)
            with icc.ProfileTransform(self.root,signal,ColorSignal('bt709','linear')) as t:b,m=t.convert(surface([[.4,.4,.4]]))
            self.assertTrue(np.isfinite(b).all());self.assertEqual(m['rendering_intent'],intent)
    def test_alpha_bits_signed_zero_and_subnormals_are_independent(self):
        a=surface([[.3,.5,.7],[.8,.2,.1]]);a[0,:,3]=np.array([0x80000000,1],np.uint32).view(np.float32)
        with icc.ProfileTransform(self.root,self.signal,ColorSignal('bt2020','linear')) as t:b,_=t.convert(a)
        self.assertEqual(a[...,3].tobytes(),b[...,3].tobytes())
    def test_out_of_gamut_working_RGB_is_not_silently_clipped(self):
        p=self.root/'wide.icc';s=icc.parse_source_signal(create_profile(p,'prophoto-rgb',1))
        with icc.ProfileTransform(self.root,s,ColorSignal('bt709','linear')) as t:b,_=t.convert(surface([[1,0,0]]))
        self.assertLess(float(b[...,:3].min()),0);self.assertGreater(float(b[...,:3].max()),1)
    def test_tiles_are_byte_identical_and_cancellation_closes_native_handles(self):
        a=np.random.default_rng(910).uniform(0,1,(13,17,4)).astype(np.float32);before=a.tobytes()
        with icc.ProfileTransform(self.root,self.signal,ColorSignal('bt2020','linear')) as t:
            values=[t.convert(a,tile_pixels=n)[0].tobytes() for n in (1,7,64,65536)]
        self.assertTrue(all(x==values[0] for x in values));count=[]
        def cancel():
            count.append(1)
            if len(count)>4:raise AppError('CANCELLED','actual tile cancellation')
        t=icc.ProfileTransform(self.root,self.signal,ColorSignal('bt709','linear'))
        t.poll=cancel
        with self.assertRaises(AppError):
            with t:t.convert(a,tile_pixels=7)
        self.assertTrue(t.metadata['native_handles_closed']);self.assertEqual(a.tobytes(),before)
    def test_invalid_surface_source_range_and_budget_are_rejected(self):
        with icc.ProfileTransform(self.root,self.signal,ColorSignal('bt709','linear')) as t:
            for a in (surface([[-.01,.5,.6]]),surface([[1.01,.5,.6]]),np.zeros((2,3,4),np.float64)):
                with self.assertRaises(AppError):t.convert(a)
            with self.assertRaises(AppError):t.convert(surface([[.1,.2,.3]]),max_working_bytes=1)
    def test_invalid_profile_header_hash_and_paths_fail_closed(self):
        for values in (dict(icc_profile='../out.icc'),dict(icc_profile='https://a/b.icc'),dict(sha256='wrong'),dict(intent='auto'),dict(black_point_compensation=1)):
            v=vars(self.signal)|values
            with self.assertRaises(AppError):icc.ICCSourceSignal(**v)
        wrong=icc.ICCSourceSignal(self.signal.icc_profile,'sha256:'+'0'*64,self.signal.intent)
        with self.assertRaises(AppError):icc.ProfileTransform(self.root,wrong,ColorSignal('bt709','linear'))
        for index,data in enumerate((b'bad',self.path.read_bytes()[:-1],self.path.read_bytes()[:16]+b'CMYK'+self.path.read_bytes()[20:])):
            p=self.root/('bad'+str(index)+'.icc');p.write_bytes(data);s=icc.ICCSourceSignal(p.name,icc.sha(p),self.signal.intent)
            with self.assertRaises(AppError):icc.ProfileTransform(self.root,s,ColorSignal('bt709','linear'))
    def test_profile_read_lock_blocks_replace_until_closed(self):
        with icc.ProfileTransform(self.root,self.signal,ColorSignal('bt709','linear')):
            with self.assertRaises(PermissionError):self.path.write_bytes(b'replaced')
        self.path.write_bytes(b'replaced');self.assertEqual(self.path.read_bytes(),b'replaced')
    def test_independent_Pillow_CMM_eight_bit_reference(self):
        # Different shipped LittleCMS build/Pillow binding is an independent
        # integration oracle. Product never invokes this 8-bit conversion.
        a=np.random.default_rng(99).integers(0,256,(13,17,3),dtype=np.uint8)
        source=ImageCms.ImageCmsProfile(str(self.path));target=ImageCms.createProfile('sRGB')
        reference=np.asarray(ImageCms.profileToProfile(Image.fromarray(a),source,target,outputMode='RGB',renderingIntent=1))
        rgba=np.concatenate((a.astype(np.float32)/255,np.ones((13,17,1),np.float32)),-1)
        with icc.ProfileTransform(self.root,self.signal,ColorSignal('bt709','linear')) as t:b,_=t.convert(rgba)
        linear=b[...,:3].astype(float);encoded=np.where(np.abs(linear)<=.0031308,12.92*linear,np.sign(linear)*(1.055*np.abs(linear)**(1/2.4)-.055))
        actual=np.rint(np.clip(encoded,0,1)*255).astype(int);maximum=int(np.max(np.abs(actual-reference.astype(int))))
        self.assertLessEqual(maximum,1);RECEIPTS.append(dict(test=self.id(),maximum_8bit_code_error=maximum,reference_CMM=ImageCms.versions()))

class ICCIntegrationTests(unittest.TestCase):
    def setUp(self):
        from test_float_standard_render import FloatStandardRenderTests
        self.f=FloatStandardRenderTests('runTest');self.f.setUp();self.addCleanup(self.f.doCleanups)
        f=self.f;f.s['duration_tick']=72000
        a=np.ones((8,16,32,4),np.float32);a[...,:3]=[.35,.4,.45];f.visual(a)
        path=f.root/'assets/source.icc';signal=create_profile(path);signal['icc_profile']='assets/source.icc'
        f.p['settings']['pixel_pipeline']['sources']['picture']['source_signal']=signal
    def test_actual_encoded_profile_source_matches_independent_gamma(self):
        f=self.f;r=f.execute();y=f.decode_y(r['path'],32,16)
        v=np.rint(np.array([.35,.4,.45],np.float32).astype(float)*65535).astype(np.float32)/65535
        expected=64+876*((v.astype(float)**2.2)@np.array([.2126,.7152,.0722]))
        self.assertLess(abs(float(y[:,0].mean())-expected),1.6)
        m=r['delivery']['pixel_pipeline']['source_receipts']['picture']['ICC_transform'];self.assertTrue(m['native_handles_closed'])
        RECEIPTS.append(dict(test=self.id(),expected_luma=expected,actual_luma=float(y[:,0].mean()),result=r));f.assert_clean()
    def test_real_cli_inspection_is_read_only_and_schema_accepts_profile(self):
        f=self.f;save_project(f.root,f.p);before=(f.root/'project.json').read_bytes()
        self.assertEqual(list(make_validator().iter_errors(f.p)),[])
        code,v=f.invoke('surface','inspect-profile','--project',f.root,'--input','assets/source.icc');self.assertEqual(code,0,v)
        self.assertTrue(v['data']['read_only']);self.assertTrue(v['data']['native_handles_closed']);self.assertEqual(before,(f.root/'project.json').read_bytes())
        code,v=f.invoke('validate','--project',f.root);self.assertEqual(code,0,v)
        RECEIPTS.append(dict(test=self.id(),inspection=v))
    def test_actual_previews_preserve_profile_and_author(self):
        f=self.f;save_project(f.root,f.p);before=(f.root/'project.json').read_bytes()
        code,v=f.invoke('preview','range','--project',f.root,'--start-frame','0','--end-frame','3','--height','64');self.assertEqual(code,0,v)
        self.assertEqual(before,(f.root/'project.json').read_bytes());f.assert_clean()
    def test_changed_profile_refuses_stale_preview_or_final_publication(self):
        f=self.f;save_project(f.root,f.p)
        code,v=f.invoke('preview','frame','--project',f.root,'--frame','0','--height','64');self.assertEqual(code,0,v)
        create_profile(f.root/'assets/source.icc',gamma=1.8)
        code,v=f.invoke('preview','frame','--project',f.root,'--frame','0','--height','64');self.assertNotEqual(code,0,v)
        output=f.root/'renders/keep.mkv';output.write_bytes(b'prior-good-movie')
        with self.assertRaises(AppError):f.execute('keep.mkv')
        self.assertEqual(output.read_bytes(),b'prior-good-movie');f.assert_clean()
    def test_portable_package_keeps_profile_complete_video_and_PCM(self):
        f=self.f;f.audio();first=f.execute('before.mkv');archive=f.root/'exports/icc.zip'
        code,v=f.invoke('convert','export','--project',f.root,'--output',archive,'--target-format','package');self.assertEqual(code,0,v)
        with zipfile.ZipFile(archive) as z:self.assertEqual(z.read('assets/source.icc'),(f.root/'assets/source.icc').read_bytes())
        restored=f.base/'restored';code,v=f.invoke('convert','import','--input',archive,'--output',restored);self.assertEqual(code,0,v)
        _,p=load_project(restored)
        with project_write_lock(restored):second=render_project(restored,p,p['sequences'][0],restored/'renders/after.mkv')
        self.assertEqual(f.decode_y(first['path'],32,16).tobytes(),f.decode_y(second['path'],32,16).tobytes())
        def pcm(path):return f.native([ffmpeg_path(),'-nostdin','-v','error','-i',path,'-map','0:a:0','-vn','-c:a','pcm_f32le','-f','f32le','pipe:1'])
        self.assertEqual(pcm(first['path']),pcm(second['path']));f.assert_clean()
        RECEIPTS.append(dict(test=self.id(),first=first,second=second))

if __name__=='__main__':unittest.main()
