from pathlib import Path
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
