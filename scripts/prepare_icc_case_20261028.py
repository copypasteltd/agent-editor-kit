"""Derive C56 from the original C55 fixture, adding actual native ICC authoring."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
s=(ROOT/'scripts/run_chromatic_case_20261028.py').read_text('utf8')
for a,b in [('C55','C56'),('native-chromatic','native-icc'),('0.1.45','0.1.46'),('len(caps)==84','len(caps)==85'),
            ("caps['native_chromatic_adaptation']","caps['native_icc_source_profiles']"),('editable-chromatic','editable-icc'),
            ('ICC_profile_parsed=False','ICC_profile_parsed=True'),('Bradford white adaptation','ICC source management')]:s=s.replace(a,b)
s=s.replace("SOURCE=dict(primaries='prophoto-rgb',transfer='prophoto-rgb')","SOURCE=None")
s=s.replace("'AGENT EDITOR KIT / EXPLICIT REFERENCE WHITES'","'AGENT EDITOR KIT / NATIVE ICC SOURCE PROFILE'")
s=s.replace("'ProPhoto D50 > linear AP1 D60 > BT.709 D65'","'RGB ICC D50 > linear AP1 D60 > BT.709 D65'")
s=s.replace("def main():\n","def main():\n    global SOURCE\n",1)
needle="        for asset,path in [('chart',public/'source-prophoto-d50.mkv'),('tones',public/'source-stereo.wav')]:"
assert needle in s
helper='''from pathlib import Path
import ctypes as C,json,sys
installed=Path(sys.argv[1]);sys.path.insert(0,str(installed/'site'))
from ai_ad_editor import icc_profiles as icc
a=icc.api(icc.runtime_paths()[2]);p=C.c_void_p
for name,result,args in [('cmsSetProfileVersion',None,[p,C.c_double]),('cmsMLUalloc',p,[p,C.c_uint32]),('cmsMLUsetASCII',C.c_int,[p,C.c_char_p,C.c_char_p,C.c_char_p]),('cmsMLUfree',None,[p]),('cmsWriteTag',C.c_int,[p,C.c_uint32,p])]:
 f=getattr(a,name);f.restype=result;f.argtypes=args
ctx=a.cmsCreateContext(None,None);curve=a.cmsBuildGamma(ctx,1.8);white=icc.xyY(.3457,.3585,1)
prim=icc.Primaries(*(icc.xyY(x,y,1) for x,y in ((.7347,.2653),(.1596,.8404),(.0366,.0001))))
profile=None;mlu=None
try:
 profile=a.cmsCreateRGBProfileTHR(ctx,C.byref(white),C.byref(prim),(p*3)(curve,curve,curve));assert profile
 a.cmsSetProfileVersion(profile,4.3);mlu=a.cmsMLUalloc(ctx,1);assert mlu
 assert a.cmsMLUsetASCII(mlu,b'en',b'US',b'AEK original C56 ProPhoto D50 gamma1.8 diagnostic / CC0')
 assert a.cmsWriteTag(profile,int.from_bytes(b'desc','big'),mlu)
 n=C.c_uint32();assert a.cmsSaveProfileToMem(profile,None,C.byref(n));buffer=C.create_string_buffer(n.value)
 assert a.cmsSaveProfileToMem(profile,buffer,C.byref(n));Path(sys.argv[2]).write_bytes(buffer.raw[:n.value])
finally:
 if mlu:a.cmsMLUfree(mlu)
 if profile:a.cmsCloseProfile(profile)
 a.cmsFreeToneCurve(curve);a.cmsDeleteContext(ctx)
print(json.dumps(dict(profile=str(sys.argv[2]),sha256=icc.sha(sys.argv[2]),original_generated=True,native_handles_closed=True,product_module=str(icc.__file__))))
'''
insert="""        helper=out/'executed-profile-author.py';helper.write_text(PROFILE_AUTHOR,encoding='utf8',newline='\\n')
        installed=Path(load(ROOT/'local/agent-ffmpeg/runtime.json')['installed_directory'])
        run('original-ICC-author',['C:/Python313/python.exe','-I','-S','-B','-u','-X','utf8',helper,installed,public/'source.icc'])
        shutil.copyfile(public/'source.icc',project/'assets/source.icc')
        SOURCE=dict(icc_profile='assets/source.icc',sha256='sha256:'+sha(public/'source.icc'),intent='relative-colorimetric',black_point_compensation=False)
        inspection=invoke('inspect-ICC','surface','inspect-profile','--project',project,'--input','assets/source.icc')
        check('actual-native-ICC-inspection',inspection['CMM_encoded_version']==2190 and inspection['matrix_shaper'] and inspection['native_handles_closed'])
"""
s=s.replace(needle,insert+needle,1)
s=s.replace("def main():\n",'PROFILE_AUTHOR='+repr(helper)+'\n\ndef main():\n',1)
s=s.replace("'--source-primaries','prophoto-rgb','--source-transfer','prophoto-rgb','--working-primaries','aces-ap1','--working-transfer','linear',",
    "'--source-icc-profile','assets/source.icc','--source-icc-sha256',SOURCE['sha256'],'--source-icc-intent','relative-colorimetric','--working-primaries','aces-ap1','--working-transfer','linear',")
s=s.replace('error<1.3e-7','error<2e-4')
s=s.replace("        first,manifest=render('edited',project);master=Path(first['path']);video=decoded('original-all-video',master)",
    "        first,manifest=render('edited',project);master=Path(first['path']);video=decoded('original-all-video',master)\n"
    "        cmm=manifest['delivery']['pixel_pipeline']['source_receipts']['chart']['ICC_transform']\n"
    "        check('actual-render-native-CMM',cmm['native_handles_closed'] and cmm['source_profile']==SOURCE|dict(reference_white_nits=None) and cmm['rendering_intent']=='relative-colorimetric')")
s=s.replace("check('package-preserves-all-signals',load(restored/'project.json')['settings']['pixel_pipeline']==authored)",
    "check('package-preserves-all-signals',load(restored/'project.json')['settings']['pixel_pipeline']==authored)\n"
    "        check('package-preserves-exact-ICC',sha(restored/'assets/source.icc')==sha(public/'source.icc'))")
s=s.replace('Explicit reference whites; not full ACES or ICC','Native LittleCMS ICC; not full ACES output')
s=s.replace('ACTUAL ENGINE / D50 > D60 > D65 + GPU Bloom','ACTUAL ENGINE / ICC D50 > D60 > D65 + GPU Bloom')
s=s.replace('ProPhoto D50 code values are declared in signals.json,not inferred from video metadata.',
    'Original RGB ICC v4.3 gamma1.8 ProPhoto D50 profile generated by installed LittleCMS; CC0 diagnostic data. All source code values exceed the ProPhoto toe. Profile is explicit,not inferred from embedded metadata.')
s=s.replace('RGB reference-white conversion is not automatic physical white balance,ICC parsing or full ACES output transform.',
    'Actual native ICC source conversion to linear AP1 D60. No arbitrary output ICC,softproof,CMYK,automatic embedded-profile/physical-white inference or full ACES output transform.')
s=s.replace("            independent_surface_pixels=W*H,maximum_surface_error=error,maximum_patch_luma_code_error=max(patch_errors),",
    "            independent_surface_pixels=W*H,maximum_surface_error=error,maximum_patch_luma_code_error=max(patch_errors),original_ICC_sha256=sha(public/'source.icc'),")
p=ROOT/'scripts/run_icc_case_20261028.py';assert not p.exists();p.write_text(s,encoding='utf8',newline='\n')
s=(ROOT/'scripts/verify_chromatic_pixels_20261028.py').read_text('utf8').replace('C55','C56').replace('native-chromatic','native-icc').replace('case-r3','case-r1').replace('-case-r3','-case-r1')
# Explicit source code values in this fixture are above the ProPhoto toe;
# independent gamma1.8 + published D50 matrix includes ICC tag quantization error.
p=ROOT/'scripts/verify_icc_pixels_20261028.py';assert not p.exists();p.write_text(s,encoding='utf8',newline='\n')
print('Prepared C56 native ICC media/profile authoring and independent oracle.')
