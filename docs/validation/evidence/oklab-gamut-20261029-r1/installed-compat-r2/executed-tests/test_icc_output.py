"""Real native output/profile simulation and independent PNG decoding checks."""
import copy,ctypes as C,hashlib,io,struct,tempfile,unittest,zlib
from pathlib import Path
import numpy as np
from PIL import Image
from ai_ad_editor import icc_profiles as icc,icc_output as out,png_icc
from ai_ad_editor.errors import AppError
from ai_ad_editor.float_color_signal import ColorSignal
from ai_ad_editor.float_hdr import LuminanceSignal
from test_icc_profiles import create_profile
from test_float_color_signal import surface,XYZ

RECEIPTS=[]

def create_clut(path,*,output=True):
    """Original bidirectional RGB/XYZ test table; not a vendor profile."""
    a=icc.api(icc.runtime_paths()[2]);p=C.c_void_p;u=C.c_uint32
    signatures=[('cmsCreateProfilePlaceholder',p,[p]),('cmsSetProfileVersion',None,[p,C.c_double]),
        ('cmsSetColorSpace',None,[p,u]),('cmsSetPCS',None,[p,u]),('cmsSetDeviceClass',None,[p,u]),
        ('cmsWriteTag',C.c_int,[p,u,p]),('cmsPipelineAlloc',p,[p,u,u]),('cmsPipelineFree',None,[p]),
        ('cmsStageAllocToneCurves',p,[p,u,p]),('cmsStageAllocCLut16bit',p,[p,u,u,u,C.POINTER(C.c_uint16)]),
        ('cmsPipelineInsertStage',C.c_int,[p,C.c_int,p])]
    for name,result,args in signatures:f=getattr(a,name);f.restype=result;f.argtypes=args
    grid=np.moveaxis(np.mgrid[0:17,0:17,0:17],0,-1)/16
    ctx=a.cmsCreateContext(None,None);profile=a.cmsCreateProfilePlaceholder(ctx)
    try:
        a.cmsSetProfileVersion(profile,2.1);a.cmsSetDeviceClass(profile,int.from_bytes(b'prtr','big'))
        a.cmsSetColorSpace(profile,int.from_bytes(b'RGB ','big'));a.cmsSetPCS(profile,int.from_bytes(b'XYZ ','big'))
        white=(C.c_double*3)(.9642,1.,.8249);assert a.cmsWriteTag(profile,int.from_bytes(b'wtpt','big'),white)
        tables=[(b'A2B0',grid*32768),(b'A2B1',grid*32768)]
        if output:tables += [(b'B2A0',(.05+.12*(2*grid)**2)*65535),(b'B2A1',(.05+.12*(2*grid)**2)*65535)]
        for tag,values in tables:
            table=np.rint(values).astype(np.uint16).ravel();pipeline=a.cmsPipelineAlloc(ctx,3,3)
            try:
                for stage in (a.cmsStageAllocToneCurves(ctx,3,None),a.cmsStageAllocCLut16bit(ctx,17,3,3,table.ctypes.data_as(C.POINTER(C.c_uint16))),a.cmsStageAllocToneCurves(ctx,3,None)):
                    assert stage and a.cmsPipelineInsertStage(pipeline,1,stage)
                assert a.cmsWriteTag(profile,int.from_bytes(tag,'big'),pipeline)
            finally:a.cmsPipelineFree(pipeline)
        n=u();assert a.cmsSaveProfileToMem(profile,None,C.byref(n));buffer=C.create_string_buffer(n.value)
        assert a.cmsSaveProfileToMem(profile,buffer,C.byref(n));path.write_bytes(buffer.raw[:n.value])
    finally:a.cmsCloseProfile(profile);a.cmsDeleteContext(ctx)
    return out.parse_output_profile(dict(icc_profile=path.name,sha256=icc.sha(path),intent='relative-colorimetric'))

class OutputTests(unittest.TestCase):
    def setUp(self):
        base=Path(__file__).resolve().parents[1]/'.runtime/temp';base.mkdir(parents=True,exist_ok=True)
        temp=tempfile.TemporaryDirectory(dir=base);self.addCleanup(temp.cleanup);self.root=Path(temp.name)
        self.path=self.root/'output.icc';self.signal=out.parse_output_profile(create_profile(self.path))
        self.working=ColorSignal('bt709','linear')
    def test_inverse_gamma_matches_independent_oracle_and_alpha_bits(self):
        a=surface([[.02,.1,.5],[.3,.6,.8]])
        a[0,:,3]=np.array([0x80000000,1],np.uint32).view(np.float32)
        with out.OutputProfileTransform(self.root,self.signal,self.working) as t:b,m=t.convert(a)
        error=float(np.max(np.abs(b[...,:3]-a[...,:3].astype(float)**(1/2.2))))
        # Persisted ICC XYZ/chromatic-adaptation coefficients are s15Fixed16;
        # this oracle uses ideal double precision BT709 instead of those tags.
        self.assertLess(error,8e-5);self.assertEqual(a[...,3].tobytes(),b[...,3].tobytes())
        self.assertTrue(t.metadata['native_handles_closed']);RECEIPTS.append(dict(test=self.id(),maximum_error=error,receipt=m))
    def test_working_gamut_matrix_before_output_gamma(self):
        a=surface([[.1,.12,.13],[.6,.61,.62]])
        with out.OutputProfileTransform(self.root,self.signal,ColorSignal('bt2020','linear')) as t:b,_=t.convert(a)
        linear=np.einsum('ij,hwj->hwi',np.linalg.inv(XYZ['bt709'])@XYZ['bt2020'],a[...,:3].astype(float))
        np.testing.assert_allclose(b[...,:3],linear**(1/2.2),rtol=0,atol=8e-5)
    def test_nits_conversion_is_before_encoding(self):
        s=out.ICCOutputSignal(**(vars(self.signal)|{'reference_white_nits':100}))
        with out.OutputProfileTransform(self.root,s,LuminanceSignal('bt709','linear',200)) as t:b,m=t.convert(surface([[.1,.2,.3]]))
        np.testing.assert_allclose(b[0,0,:3],(np.array([.1,.2,.3])*2)**(1/2.2),rtol=0,atol=8e-5)
        self.assertEqual(m['linear_input_unit_scale'],2)
        with self.assertRaises(AppError):out.OutputProfileTransform(self.root,s,self.working)
    def test_range_is_explicit_and_clipping_counted(self):
        with out.OutputProfileTransform(self.root,self.signal,self.working) as t:
            a=surface([[-.1,1.1,.4]])
            with self.assertRaises(AppError):t.convert(a)
            b,m=t.convert(a,range_policy='clip')
            # This actual gamma profile maps negative linear inputs to zero
            # inside the CMM; only the remaining superwhite is OUR clipping.
            self.assertEqual(m['encoded_output_components_clipped'],1)
            self.assertEqual(m['negative_working_components'],1)
            self.assertEqual(float(b.min()),0);self.assertEqual(float(b.max()),1)
    def test_tiles_match_and_budget_cancellation_closes(self):
        a=np.random.default_rng(301).uniform(.1,.9,(9,13,4)).astype(np.float32)
        with out.OutputProfileTransform(self.root,self.signal,self.working) as t:
            self.assertEqual(t.convert(a,tile_pixels=1)[0].tobytes(),t.convert(a,tile_pixels=65)[0].tobytes())
            with self.assertRaises(AppError):t.convert(a,max_working_bytes=1)
        t=out.OutputProfileTransform(self.root,self.signal,self.working)
        def stop():raise AppError('CANCELLED','explicit fixture cancellation')
        t.poll=stop
        with self.assertRaises(AppError):
            with t:t.convert(a)
        self.assertTrue(t.metadata['native_handles_closed'])
    def test_softproof_is_native_and_returns_linear_with_exact_alpha(self):
        a=surface([[.02,.2,.4],[.3,.5,.8]])
        for intent in icc.INTENTS:
            with out.SoftProofTransform(self.root,self.signal,self.working,intent) as t:b,m=t.convert(a)
            np.testing.assert_allclose(b[...,:3],a[...,:3],rtol=0,atol=2e-4)
            self.assertEqual(a[...,3].tobytes(),b[...,3].tobytes());self.assertTrue(m['SOFTPROOFING_flag'])
            self.assertTrue(t.metadata['native_handles_closed'])
    def test_actual_CLUT_output_uses_B2A_and_independent_PCS_oracle(self):
        signal=create_clut(self.root/'nonlinear.icc')
        a=np.random.default_rng(402).uniform(.03,.8,(11,13,4)).astype(np.float32)
        matrix=np.array([[.4360747,.3850649,.1430804],[.2225045,.7168786,.0606169],[.0139322,.0971045,.7141733]])
        expected=.05+.12*np.einsum('ij,hwj->hwi',matrix,a[...,:3].astype(float))**2
        with out.OutputProfileTransform(self.root,signal,self.working) as t:b,m=t.convert(a)
        self.assertFalse(m['matrix_shaper']);maximum=float(np.max(np.abs(b[...,:3]-expected)));self.assertLess(maximum,.0006)
        with out.SoftProofTransform(self.root,signal,self.working,'relative-colorimetric') as t:proof,receipt=t.convert(a)
        self.assertGreater(float(np.max(np.abs(proof[...,:3]-a[...,:3]))),.1)
        self.assertEqual(proof[...,3].tobytes(),a[...,3].tobytes())
        RECEIPTS.append(dict(test=self.id(),maximum_output_error=maximum,output=m,proof=receipt))
    def test_input_only_CLUT_cannot_be_silently_used_as_output_or_proof(self):
        signal=create_clut(self.root/'input-only.icc',output=False)
        with self.assertRaises(AppError):out.OutputProfileTransform(self.root,signal,self.working)
        with self.assertRaises(AppError):out.SoftProofTransform(self.root,signal,self.working,'relative-colorimetric')
    def test_all_output_intents_and_BPC_are_native(self):
        for intent in icc.INTENTS:
            signal=out.ICCOutputSignal(**(vars(self.signal)|{'intent':intent,'black_point_compensation':True}))
            with out.OutputProfileTransform(self.root,signal,self.working) as t:b,m=t.convert(surface([[.1,.3,.6]]))
            self.assertTrue(np.isfinite(b).all());self.assertEqual(m['rendering_intent'],intent);self.assertTrue(m['flags']&0x2000)
    def test_png_corrupt_CRC_truncation_and_wrong_profile_rejected(self):
        p=self.root/'bad.png';png_icc.write(p,surface([[.1,.2,.3]]),self.path.read_bytes(),max_bytes=2**20);data=p.read_bytes()
        for v in (data[:-2],data[:40]+bytes([data[40]^1])+data[41:],data+b'extra'):
            p.write_bytes(v)
            with self.assertRaises(AppError):png_icc.inspect(p,self.path.read_bytes(),1,1)
        p.write_bytes(data)
        with self.assertRaises(AppError):png_icc.inspect(p,self.path.read_bytes()+b'bad',1,1)
    def test_invalid_descriptors_and_paths_rejected(self):
        for v in (None,{},dict(vars(self.signal),intent='automatic'),dict(vars(self.signal),icc_profile='../outside.icc')):
            with self.assertRaises(AppError):
                s=out.parse_output_profile(v)
                with out.OutputProfileTransform(self.root,s,self.working):pass
        with self.assertRaises(AppError):out.proof_configuration({'profile':vars(self.signal)})
    def test_png_all_alpha_codes_profile_identity_crc_and_independent_pixels(self):
        a=np.empty((256,256,4),np.float32);a[...,:3]=[.1,.3,.7];a[...,3]=np.arange(65536,dtype=np.float32).reshape(256,256)/65535
        p=self.root/'output.png';m=png_icc.write(p,a,self.path.read_bytes(),max_bytes=2**20)
        data=p.read_bytes();self.assertEqual(data[:8],png_icc.SIGNATURE);offset=8;chunks=[];compressed=[]
        while offset<len(data):
            n=struct.unpack('>I',data[offset:offset+4])[0];kind=data[offset+4:offset+8];v=data[offset+8:offset+8+n]
            self.assertEqual(struct.unpack('>I',data[offset+8+n:offset+12+n])[0],zlib.crc32(kind+v)&0xffffffff)
            chunks.append(kind)
            if kind==b'IDAT':compressed.append(v)
            offset+=n+12
        raw=zlib.decompress(b''.join(compressed));rows=np.frombuffer(raw,np.uint8).reshape(256,1+256*8)
        self.assertFalse(rows[:,0].any());pixels=np.frombuffer(rows[:,1:].tobytes(),dtype='>u2').reshape(256,256,4)
        np.testing.assert_array_equal(pixels,np.rint(a.astype(float)*65535).astype(np.uint16))
        np.testing.assert_array_equal(pixels[...,3].ravel(),np.arange(65536))
        with Image.open(p) as im:self.assertEqual(im.info['icc_profile'],self.path.read_bytes())
        self.assertEqual(set(chunks),{b'IHDR',b'iCCP',b'IDAT',b'IEND'});self.assertEqual(m['bytes'],len(data))
        inspected=png_icc.inspect(p,self.path.read_bytes(),256,256)
        self.assertEqual(inspected['RGBA16BE_sha256'],'sha256:'+hashlib.sha256(pixels.tobytes()).hexdigest())
    def test_png_failed_write_preserves_existing_and_removes_own_partial(self):
        p=self.root/'image.png';p.write_bytes(b'old')
        with self.assertRaises(FileExistsError):png_icc.write(p,surface([[.1,.2,.3]]),self.path.read_bytes(),max_bytes=2**20)
        self.assertEqual(p.read_bytes(),b'old');p.unlink()
        with self.assertRaises(AppError):png_icc.write(p,surface([[1.1,.2,.3]]),self.path.read_bytes(),max_bytes=2**20)
        self.assertFalse(p.exists())

class TimelineTests(unittest.TestCase):
    def setUp(self):
        import test_float_standard_render as fixture
        self.fixture=fixture.FloatStandardRenderTests(next(n for n in dir(fixture.FloatStandardRenderTests) if n.startswith('test_')))
        # Instantiate only fixture methods; unittest discovery never loads its
        # class as a global alias or counts the imported suite a second time.
        self.fixture.setUp();self.addCleanup(self.fixture.doCleanups)
        self.root=self.fixture.root;self.p=self.fixture.p;self.sequence=self.fixture.s
        self.sequence['duration_tick']=90000
        pixels=np.broadcast_to(np.array([.25,.5,.75,1],np.float32),(10,16,32,4)).copy()
        self.original=self.fixture.visual(pixels);self.audio=self.fixture.audio()
        next(a for a in self.p['assets'] if a['id']=='sound')['rights_ref']='rights_sound'
        self.sequence['duration_tick']=90000
        self.profile=create_profile(self.root/'delivery.icc')
    def test_actual_timeline_all_frames_embedded_profile_and_authored_pcm(self):
        from ai_ad_editor import icc_sequence
        plan=icc_sequence.prepare(self.root,self.p,self.sequence['id'],'renders/icc-sequence',self.profile)
        result=icc_sequence.export(self.root,self.p,plan)
        output=Path(result['output']);manifest=__import__('json').loads((output/'sequence.json').read_bytes())
        inspected=icc_sequence.inspect(self.root,output)
        self.assertTrue(inspected['all_png_pixels_and_CRC_verified']);self.assertEqual(inspected['audio_scalars'],96000)
        self.assertEqual(result['frames'],10);self.assertEqual(result['audio_sample_frames'],48000)
        self.assertEqual((output/'audio.f32le').read_bytes(),self.audio.tobytes())
        for row in manifest['files']:
            path=output/row['name'];self.assertEqual('sha256:'+hashlib.sha256(path.read_bytes()).hexdigest(),row['sha256'])
            if path.suffix=='.png':
                with Image.open(path) as im:
                    self.assertEqual(im.info['icc_profile'],(self.root/'delivery.icc').read_bytes())
                    expected=np.rint(np.array([.25,.5,.75])**(1/2.2)*255)
                    np.testing.assert_allclose(np.array(im)[0,0,:3],expected,rtol=0,atol=1)
        self.assertTrue(manifest['CMM']['native_handles_closed']);self.assertTrue(manifest['timeline']['providers_closed_before_publish'])
        RECEIPTS.append(dict(test=self.id(),result=result,CMM=manifest['CMM'],audio_sha256=manifest['files'][-1]['sha256']))
    def test_partial_clock_pcm_and_cancellation_preserves_no_partial_output(self):
        from ai_ad_editor import icc_sequence
        plan=icc_sequence.prepare(self.root,self.p,self.sequence['id'],'renders/partial',self.profile,start_frame=2,stop_frame=5)
        result=icc_sequence.export(self.root,self.p,plan);output=Path(result['output'])
        self.assertEqual((output/'audio.f32le').read_bytes(),self.audio[9600:24000].tobytes())
        marker=self.root/'cancel';marker.write_text('cancel')
        plan=icc_sequence.prepare(self.root,self.p,self.sequence['id'],'renders/cancelled',self.profile)
        with self.assertRaises(AppError):icc_sequence.export(self.root,self.p,plan,cancel_file=marker)
        self.assertFalse((self.root/'renders/cancelled').exists());self.assertFalse(list((self.root/'renders').glob('.icc-sequence-*')))
    def test_softproof_common_render_and_source_profile_packaging(self):
        from ai_ad_editor.schema_contract import make_validator
        from ai_ad_editor.convert import _package_icc_profiles
        self.p['settings']['pixel_pipeline']['proofing']={'profile':dict(self.profile),'simulation_intent':'absolute-colorimetric'}
        errors=list(make_validator().iter_errors(self.p));self.assertFalse(errors,repr(errors[:2]))
        before=copy.deepcopy(self.p);pack=copy.deepcopy(self.p);files={}
        snapshots=_package_icc_profiles(self.root,pack,files)
        target='assets/color-profiles/'+self.profile['sha256'][7:]+'.icc'
        self.assertEqual(snapshots[target],(self.root/'delivery.icc').read_bytes());self.assertEqual(self.p,before)
        self.assertEqual(pack['settings']['pixel_pipeline']['proofing']['profile']['icc_profile'],target)
        result=self.fixture.execute('proof.mkv')
        # Actual common encoding must have traversed the proof transform.
        RECEIPTS.append(dict(test=self.id(),result=result))
        self.fixture.assert_clean()
    def test_dry_run_budget_and_complete_CLI_descriptor(self):
        from ai_ad_editor import icc_sequence
        with self.assertRaises(AppError):icc_sequence.prepare(self.root,self.p,self.sequence['id'],'renders/tiny',self.profile,max_output_bytes=100)
        from ai_ad_editor.project import save_project
        save_project(self.root,self.p);p=self.root/'target.json';p.write_text(__import__('json').dumps(self.profile))
        code,result=self.fixture.invoke('surface','render','--project',self.root,'--sequence-id',self.sequence['id'],
            '--output','renders/planned','--output-profile-json',p,'--dry-run')
        self.assertEqual(code,0,repr(result));self.assertEqual(result['status'],'planned');self.assertFalse((self.root/'renders/planned').exists())
        code,result=self.fixture.invoke('surface','render','--project',self.root,'--sequence-id',self.sequence['id'],
            '--output','renders/cli-real','--output-profile-json',p)
        self.assertEqual(code,0,repr(result));self.assertEqual(result['data']['frames'],10)
        before={str(p.relative_to(self.root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in self.root.rglob('*') if p.is_file()}
        code,result=self.fixture.invoke('surface','inspect-output','--project',self.root,'--input','renders/cli-real')
        self.assertEqual(code,0,repr(result));self.assertTrue(result['data']['all_png_pixels_and_CRC_verified'])
        after={str(p.relative_to(self.root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in self.root.rglob('*') if p.is_file()}
        self.assertEqual(before,after)

if __name__=='__main__':unittest.main()
