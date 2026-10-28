"""Compile pinned MIT LittleCMS with an existing native Windows toolchain."""
from pathlib import Path
from datetime import datetime,timezone
import ctypes,hashlib,json,os,shutil,subprocess
ROOT=Path(__file__).resolve().parents[1]
source=ROOT/'sources/littlecms-2.19.1/source';origin=json.loads((source.parent/'source.json').read_bytes())
assert origin['commit']=='21c582a594fe5279f90c0b93437c398f93bf62b0'
assert origin['archive_sha256']=='24c57a21fb055f7de81907b111b11726b486ab923e96e168336b71f6addd236b'
compiler=next((ROOT/'product/.runtime/materials-20261024/toolchains/llvm-mingw').glob('*/bin/x86_64-w64-mingw32-clang.exe'))
work=ROOT/'product/.runtime/native-icc-build-r1';work.mkdir(exist_ok=False)
out=ROOT/'docs/validation/evidence/native-icc-20261028-r1/native-build-r1';out.mkdir(parents=True,exist_ok=False)
(out/'executed-builder.py').write_bytes(Path(__file__).read_bytes())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
inputs=sorted((source/'src').glob('cms*.c'));assert len(inputs)>20
binary=work/'avk_lcms.dll'
argv=[str(compiler),'-O2','-std=c99','-DCMS_DLL_BUILD','-shared','-Wl,--no-insert-timestamp','-static-libgcc',
    '-I',str(source/'include'),*map(str,inputs),'-o',str(binary)]
env={**os.environ,'PATH':str(compiler.parent)+os.pathsep+os.environ['PATH'],'TEMP':str(work),'TMP':str(work),'TMPDIR':str(work)}
r=subprocess.run(argv,cwd=work,env=env,capture_output=True,timeout=300,creationflags=subprocess.CREATE_NO_WINDOW)
(out/'stdout.txt').write_bytes(r.stdout);(out/'stderr.txt').write_bytes(r.stderr)
report=dict(status='failed',at_utc=datetime.now(timezone.utc).isoformat(),command=argv,exit_code=r.returncode,
    compiler=str(compiler),compiler_sha256=sha(compiler),source=origin,source_files={p.relative_to(source).as_posix():sha(p) for p in sorted(source.rglob('*')) if p.is_file()},
    native_windows=True,virtualization=False,runtime_compilation=False,network_during_build=False)
if r.returncode==0:
    library=ctypes.CDLL(str(binary),winmode=0x1100);library.cmsGetEncodedCMMversion.restype=ctypes.c_int
    version=library.cmsGetEncodedCMMversion();assert version==2190
    name='avk_lcms_'+sha(binary)[:16]+'.dll';package=ROOT/'product/src/ai_ad_editor';target=package/name
    assert not target.exists();shutil.copyfile(binary,target);shutil.copyfile(source/'LICENSE',package/'LITTLECMS_LICENSE.txt')
    manifest=dict(format='agent-native-icc-cmm-v1',platform='win32-amd64',binary_filename=name,binary_sha256=sha(target),
        source_repository=origin['repository'],source_commit=origin['commit'],source_tag=origin['tag'],source_archive_sha256=origin['archive_sha256'],
        license='LITTLECMS_LICENSE.txt',license_sha256=sha(package/'LITTLECMS_LICENSE.txt'),encoded_version=version,
        compiler='llvm-mingw 20261020 ucrt x86_64 clang -O2 -std=c99 -shared',runtime_compilation=False)
    (package/'native_icc_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf8',newline='\n')
    report.update(status='compiled-and-loaded',binary_manifest=manifest)
(out/'verification.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8',newline='\n')
print(json.dumps({k:v for k,v in report.items() if k not in ('source_files','command')}));assert report['status']=='compiled-and-loaded',r.stderr.decode('utf8','replace')[-2000:]
