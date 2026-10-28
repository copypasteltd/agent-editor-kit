"""Prove the isolated installed process loads its pinned native OCIO DLL."""
import argparse,ctypes,hashlib,json,sys
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def main():
    p=argparse.ArgumentParser();p.add_argument('--installed',required=True,type=Path);p.add_argument('--run',required=True);a=p.parse_args()
    assert sys.flags.isolated and sys.flags.no_site and a.run.replace('-','').isalnum()
    site=a.installed.resolve()/'site';sys.path.insert(0,str(site))
    import numpy as np
    import ai_ad_editor
    from ai_ad_editor import ocio_runtime as ocio
    package=site/'ai_ad_editor'
    assert Path(ai_ad_editor.__file__).resolve().parent==package
    assert Path(np.__file__).resolve().is_relative_to(site)
    manifest=json.loads((package/'native_ocio_manifest.json').read_bytes())
    assert sha(package/'native_ocio_manifest.json')==ocio.MANIFEST_SHA256
    module=ocio.native();binary=Path(module.__file__).resolve()
    assert binary==package/'native_ocio/PyOpenColorIO.pyd'
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.GetModuleHandleW.argtypes=[ctypes.c_wchar_p];kernel.GetModuleHandleW.restype=ctypes.c_void_p
    kernel.GetModuleFileNameW.argtypes=[ctypes.c_void_p,ctypes.c_wchar_p,ctypes.c_uint];kernel.GetModuleFileNameW.restype=ctypes.c_uint
    handle=kernel.GetModuleHandleW('OpenColorIO_2_6.dll');assert handle
    buffer=ctypes.create_unicode_buffer(32768)
    size=kernel.GetModuleFileNameW(handle,buffer,len(buffer));assert 0<size<len(buffer)
    dll=Path(buffer.value).resolve();assert dll==package/'native_ocio/OpenColorIO_2_6.dll'
    for row in manifest['files']:
        target=package/row['path'];assert target.stat().st_size==row['bytes'] and sha(target)==row['sha256']
    c=ocio.config('aces-2.1');display='sRGB - Display';view='ACES 2.0 - SDR 100 nits (Rec.709)'
    assert display in list(c.getDisplays()) and view in list(c.getViews(display))
    selection=dict(config='aces-2.1',display=display,view=view,exposure_stops=0,input_interpretation='scene-linear-ACEScg')
    source=np.array([[[.18,.18,.18,.375],[.9,.1,.01,1.]]],np.float32)
    with ocio.DisplayTransform(selection) as processor:
        actual,metadata=processor.apply(source)
        reference=source.copy()
        c.getProcessor(module.DisplayViewTransform(src='ACEScg',display=display,view=view)).getDefaultCPUProcessor().applyRGBA(reference.reshape(-1,4))
        assert np.array_equal(actual,reference) and np.array_equal(actual[:,:,3],source[:,:,3])
    assert processor.closed
    out=ROOT/'docs/validation/evidence/aces-delivery-20261029-r1'/a.run;out.mkdir(parents=True,exist_ok=False)
    (out/'executed-runner.py').write_bytes(Path(__file__).read_bytes())
    report=dict(status='passed',isolated=True,no_site=True,source_fallback=False,actual_pyd=str(binary),actual_DLL=str(dll),
        actual_pyd_sha256=sha(binary),actual_DLL_sha256=sha(dll),native_version=module.__version__,
        actual_native_transform=True,direct_native_reference_equal=True,alpha_bit_exact=True,processor_closed=True,
        selection=selection,output=actual.tolist(),metadata=metadata)
    (out/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False))

if __name__=='__main__':main()
