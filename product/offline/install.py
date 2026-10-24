"""Native Windows wheel-only installation. Standard library; never downloads."""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path, PurePosixPath
import platform
import re
import shutil
import stat
import struct
import subprocess
import sys
import tempfile
import time
import zipfile
from email.parser import BytesParser

# The 500 hash-pinned, compressed creative LUTs make the application wheel
# larger than the first alpha. Keep a finite per-file bound; ZIP member and
# expanded-wheel limits still apply independently.
MAX_BYTES=384*1024**2
CORE_WHEELS={'ai-ad-editor','jsonschema','attrs','jsonschema-specifications','referencing','rpds-py'}
RUNTIME_PROFILES={
    'core-v1':CORE_WHEELS,
    'font-text-v1':CORE_WHEELS|{'pillow'},
    'media-analysis-v1':CORE_WHEELS|{'pillow','numpy'},
}


class InstallError(Exception):
    def __init__(self,code,message,exit_code=2):
        super().__init__(message);self.code=code;self.exit_code=exit_code


def sha(path):
    with Path(path).open('rb') as stream:return 'sha256:'+hashlib.file_digest(stream,'sha256').hexdigest()


def native_target():
    if sys.platform!='win32' or sys.prefix!=sys.base_prefix or platform.python_implementation()!='CPython' or sys.version_info[:2]!=(3,13) or struct.calcsize('P')!=8 or platform.machine().lower() not in {'amd64','x86_64'}:
        raise InstallError('PYTHON_TARGET_MISMATCH','Requires native Windows CPython 3.13 x64; no virtual environment is created')


def _drive_type(anchor):
    import ctypes
    function=ctypes.WinDLL('kernel32',use_last_error=True).GetDriveTypeW
    function.argtypes=[ctypes.c_wchar_p];function.restype=ctypes.c_uint
    return function(anchor)


def local_path(value):
    raw=os.fspath(value);normalized=raw.replace('\\','/')
    scheme=re.match(r'^([A-Za-z][A-Za-z0-9+.-]*):',raw)
    if normalized.startswith('//') or (scheme and len(scheme[1])!=1) or ':' in raw[2:]:
        raise InstallError('NETWORK_PATH_FORBIDDEN','Only local filesystem paths; no UNC, device paths or URI')
    path=Path(value).absolute()
    if _drive_type(path.anchor)==4:
        raise InstallError('NETWORK_PATH_FORBIDDEN','Mapped network drives are forbidden before file probing')
    return path


def safe_name(name):
    if not isinstance(name,str) or not name or '\\' in name or ':' in name or '%' in name:
        raise InstallError('BUNDLE_PATH_INVALID','Invalid bundle relative path')
    p=PurePosixPath(name)
    if p.is_absolute() or p.as_posix()!=name or any(x in {'.','..'} or x.rstrip(' .')!=x or x.split('.')[0].upper() in {'CON','PRN','AUX','NUL',*[f'COM{i}' for i in range(1,10)],*[f'LPT{i}' for i in range(1,10)]} for x in p.parts):
        raise InstallError('BUNDLE_PATH_INVALID','Noncanonical or reserved bundle path: '+name)
    return name


def no_reparse(path):
    current=Path(path).absolute()
    # Inspect each ancestor itself before entering any of its children. exists()
    # would follow a junction, so it must not precede the reparse check.
    for item in reversed((current,*current.parents)):
        try:details=item.stat(follow_symlinks=False)
        except FileNotFoundError:continue
        if stat.S_ISLNK(details.st_mode) or details.st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT:
            raise InstallError('REPARSE_PATH_FORBIDDEN','Reparse path forbidden: '+str(item))


def strict_object(items):
    result={}
    for key,value in items:
        if key in result:raise InstallError('MANIFEST_INVALID','Duplicate JSON key')
        result[key]=value
    return result


def validate_bundle(bundle,expected_manifest):
    bundle=local_path(bundle);no_reparse(bundle)
    path=bundle/'manifest.json'
    if not re.fullmatch(r'sha256:[0-9a-f]{64}',expected_manifest or '') or not path.is_file() or path.stat().st_size>2*1024**2 or sha(path)!=expected_manifest:
        raise InstallError('MANIFEST_DIGEST_MISMATCH','Supply the separately reviewed manifest SHA-256')
    manifest=json.loads(path.read_bytes(),object_pairs_hook=strict_object)
    if manifest.get('format')!='agent-video-kit-offline-v1' or manifest.get('target')!='cp313-win_amd64':raise InstallError('MANIFEST_INVALID','Unknown bundle format/target')
    inventory={};folded=set()
    for row in manifest['files']:
        name=safe_name(row['path'])
        if name.casefold() in folded or name=='manifest.json':raise InstallError('MANIFEST_INVALID','Duplicate inventory entry')
        folded.add(name.casefold());inventory[name]=row
        file=bundle/name;no_reparse(file)
        if not file.is_file() or type(row['bytes']) is not int or not 0<=row['bytes']<=MAX_BYTES or file.stat().st_size!=row['bytes'] or sha(file)!=row['sha256']:
            raise InstallError('BUNDLE_DIGEST_MISMATCH','Bundle file mismatch: '+name)
    actual=set()
    for file in bundle.rglob('*'):
        no_reparse(file)
        if file.is_file():actual.add(file.relative_to(bundle).as_posix())
    if actual!=set(inventory)|{'manifest.json'}:raise InstallError('BUNDLE_INVENTORY_MISMATCH','Extra or missing bundle files')
    wheels=manifest['wheels'];names=set();requirements=[]
    profile=manifest.get('runtime_profile','core-v1')
    if profile not in RUNTIME_PROFILES:raise InstallError('WHEEL_SET_INVALID','Unknown offline runtime profile')
    expected_names=RUNTIME_PROFILES[profile]
    if len(wheels)!=len(expected_names):raise InstallError('WHEEL_SET_INVALID','Pinned wheel count differs from declared runtime profile')
    for row in wheels:
        name=safe_name(row['path'])
        if name not in inventory or not name.startswith('wheels/') or not name.endswith('.whl'):raise InstallError('WHEEL_SET_INVALID','Wheel missing from inventory')
        with zipfile.ZipFile(bundle/name) as archive:
            entries=archive.infolist();seen=set();total=0
            for entry in entries:
                item=safe_name(entry.filename.rstrip('/'))
                if item.casefold() in seen or stat.S_ISLNK(entry.external_attr>>16):raise InstallError('WHEEL_INVALID','Duplicate/symlink wheel member')
                seen.add(item.casefold());total+=entry.file_size
                if total>512*1024**2:raise InstallError('WHEEL_INVALID','Oversized wheel')
            metadata=[x for x in entries if x.filename.endswith('.dist-info/METADATA')]
            tags=[x for x in entries if x.filename.endswith('.dist-info/WHEEL')]
            if len(metadata)!=1 or len(tags)!=1:raise InstallError('WHEEL_INVALID','Missing wheel metadata')
            info=BytesParser().parsebytes(archive.read(metadata[0]));wheel_info=BytesParser().parsebytes(archive.read(tags[0]))
            normalized=re.sub(r'[-_.]+','-',info['Name']).lower()
            if normalized!=row['name'] or info['Version']!=row['version'] or normalized in names:raise InstallError('WHEEL_INVALID','Wheel name/version mismatch')
            names.add(normalized)
            if normalized=='ai-ad-editor' and profile=='core-v1' and any(re.match(r'(?i)^pillow\b',r) for r in info.get_all('Requires-Dist',[])):
                raise InstallError('WHEEL_SET_INVALID','Product declares Pillow; font-text-v1 profile is required')
            if normalized=='ai-ad-editor' and profile!='media-analysis-v1' and any(re.match(r'(?i)^numpy\b',r) for r in info.get_all('Requires-Dist',[])):
                raise InstallError('WHEEL_SET_INVALID','Product declares NumPy; media-analysis-v1 profile is required')
            if not set(wheel_info.get_all('Tag',[])) & {'py3-none-any','py3-none-win_amd64','cp313-cp313-win_amd64'}:raise InstallError('WHEEL_INVALID','Unsupported wheel ABI')
        requirements.append('./'+name+' --hash='+inventory[name]['sha256'])
    if names!=expected_names:raise InstallError('WHEEL_SET_INVALID','Unexpected wheel set for declared runtime profile')
    if (bundle/'requirements.lock').read_bytes()!=('\n'.join(requirements)+'\n').encode():raise InstallError('REQUIREMENTS_INVALID','Lock differs from hashed wheel inventory')
    return manifest


def remove_owned(staging,parent):
    # Validate absolute deletion target immediately before recursive cleanup.
    checked=Path(staging).resolve();base=Path(parent).resolve()
    if checked.parent!=base or not checked.name.startswith('.agent-video-kit-install-'):
        raise InstallError('CLEANUP_TARGET_INVALID','Refuse cleanup outside owned staging')
    no_reparse(checked)
    if checked.exists():shutil.rmtree(checked)


def run_owned(command,*,cwd,env,log,cancel_file,deadline):
    # Wheel-only pip cannot run build hooks; it is one owned process, no shell.
    with Path(log).open('wb') as output:
        child=subprocess.Popen(command,cwd=cwd,env=env,stdin=subprocess.DEVNULL,stdout=output,stderr=subprocess.STDOUT,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        try:
            while child.poll() is None:
                if cancel_file and Path(cancel_file).exists():raise InstallError('INSTALL_CANCELLED','Cancelled during installation',8)
                if time.monotonic()>=deadline:raise InstallError('INSTALL_TIMEOUT','Installation deadline exceeded',8)
                time.sleep(0.05)
            if child.returncode:raise InstallError('INSTALL_PROCESS_FAILED',Path(log).read_text(encoding='utf-8',errors='replace')[-8000:])
        finally:
            if child.poll() is None:
                child.terminate()
                try:child.wait(timeout=5)
                except subprocess.TimeoutExpired:child.kill();child.wait(timeout=5)


def install(bundle,target,expected_manifest,*,dry_run=False,cancel_file=None,timeout_seconds=180):
    native_target()
    bundle=local_path(bundle);target=local_path(target)
    if cancel_file is not None:cancel_file=local_path(cancel_file)
    no_reparse(target)
    if target.exists():raise InstallError('INSTALL_TARGET_EXISTS','Existing target is preserved')
    if cancel_file and Path(cancel_file).exists():raise InstallError('INSTALL_CANCELLED','Cancelled before installation',8)
    if not 0<float(timeout_seconds)<=600:raise InstallError('INSTALL_TIMEOUT_INVALID','Timeout must be 0..600 seconds')
    manifest=validate_bundle(bundle,expected_manifest);bundle=Path(bundle).resolve()
    if target==bundle or target.is_relative_to(bundle):raise InstallError('INSTALL_TARGET_INVALID','Target must be outside bundle')
    if dry_run:return {'status':'planned','target':str(target),'manifest_sha256':expected_manifest,'wheels':len(manifest['wheels'])}
    if importlib.util.find_spec('pip') is None:raise InstallError('PIP_REQUIRED','Existing native Python must include pip; no bootstrap downloads')
    target.parent.mkdir(parents=True,exist_ok=True);no_reparse(target.parent)
    staging=Path(tempfile.mkdtemp(prefix='.agent-video-kit-install-',dir=target.parent));deadline=time.monotonic()+float(timeout_seconds)
    try:
        runtime=staging/'runtime';temp=runtime/'temp';temp.mkdir(parents=True)
        env=dict(os.environ);env.update(TEMP=str(temp),TMP=str(temp),TMPDIR=str(temp),PIP_CONFIG_FILE=os.devnull,PIP_NO_INDEX='1',PIP_NO_CACHE_DIR='1',PIP_DISABLE_PIP_VERSION_CHECK='1',PYTHONDONTWRITEBYTECODE='1')
        inventory={row['path']:row for row in manifest['files']};requirements=[]
        for wheel in manifest['wheels']:
            source=bundle/wheel['path'];copy=staging/wheel['path'];copy.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(source,copy)
            if sha(copy)!=inventory[wheel['path']]['sha256']:raise InstallError('BUNDLE_DIGEST_MISMATCH','Wheel changed during copy')
            requirements.append('./'+wheel['path']+' --hash='+inventory[wheel['path']]['sha256'])
        # Use an owned lock reconstructed from the reviewed manifest, never a
        # mutable external requirements file after its integrity check.
        (staging/'requirements.lock').write_text('\n'.join(requirements)+'\n',encoding='utf-8',newline='\n')
        command=[sys.executable,'-I','-B','-m','pip','install','--no-index','--no-deps','--require-hashes','--only-binary=:all:','--no-compile','--target',str(staging/'site'),'--requirement',str(staging/'requirements.lock')]
        run_owned(command,cwd=staging,env=env,log=staging/'install.log',cancel_file=cancel_file,deadline=deadline)
        # Fresh-process audit forbids a core module falling through to host site.
        modules=[('ai_ad_editor','ai-ad-editor'),('jsonschema','jsonschema'),('attrs','attrs'),('jsonschema_specifications','jsonschema-specifications'),('referencing','referencing'),('rpds','rpds-py')]
        if manifest.get('runtime_profile') in {'font-text-v1','media-analysis-v1'}:modules.append(('PIL','pillow'))
        if manifest.get('runtime_profile')=='media-analysis-v1':modules.append(('numpy','numpy'))
        audit='MODULES='+repr(modules)+'\n'+"""import sys,json,pathlib,importlib,importlib.metadata
site=pathlib.Path(sys.argv[1]).resolve();sys.path[:]=[str(site),*[p for p in sys.path if not {'site-packages','dist-packages'} & set(pathlib.Path(p).parts)]];items={}
for module,dist in MODULES:
 m=importlib.import_module(module);p=pathlib.Path(m.__file__).resolve();assert p.is_relative_to(site),(module,str(p));items[dist]={'version':importlib.metadata.version(dist),'path':str(p.relative_to(site))}
from ai_ad_editor.schema_contract import probe
check=probe();assert check['ok'],check
native=None
if 'numpy' in items:
 import numpy as np
 vector=np.arange(10,dtype=np.float64);dot=float(vector@vector);assert dot==285.0,dot
 solution=np.linalg.solve(np.array([[3.,1.],[1.,2.]]),np.array([9.,8.]));assert float(np.max(np.abs(solution-np.array([2.,3.]))))<=1e-12,solution
 spectrum=np.fft.rfft(np.array([1.,0.,0.,0.]));assert np.array_equal(spectrum,np.ones(3,dtype=np.complex128)),spectrum
 extensions={}
 for module in ('numpy._core._multiarray_umath','numpy.linalg._umath_linalg'):
  extension=pathlib.Path(importlib.import_module(module).__file__).resolve();assert extension.is_relative_to(site) and extension.suffix.lower()=='.pyd',(module,str(extension));extensions[module]=str(extension.relative_to(site))
 native={'dot':dot,'solve':solution.tolist(),'fft_impulse_real':spectrum.real.tolist(),'fft_impulse_imag':spectrum.imag.tolist(),'extensions':extensions}
print(json.dumps({'modules':items,'schema':{k:v for k,v in check.items() if k!='path'},'numpy_native':native}))
"""
        run_owned([sys.executable,'-I','-S','-B','-X','utf8','-c',audit,str(staging/'site')],cwd=staging,env=env,log=staging/'dependency-audit.json',cancel_file=cancel_file,deadline=deadline)
        audit_result=json.loads((staging/'dependency-audit.json').read_bytes())
        if manifest.get('runtime_profile')=='media-analysis-v1' and not audit_result.get('numpy_native'):
            raise InstallError('INSTALL_NATIVE_AUDIT_MISSING','Native NumPy audit is required for media-analysis-v1')
        if audit_result['schema']['sha256']!=manifest['schema_sha256']:raise InstallError('INSTALL_SCHEMA_MISMATCH','Installed contract differs from release')
        actual={k:v['version'] for k,v in audit_result['modules'].items()}
        if actual!={x['name']:x['version'] for x in manifest['wheels']}:raise InstallError('INSTALL_VERSION_MISMATCH','Installed versions differ from release')
        launcher="""from pathlib import Path
import os,sys
root=Path(__file__).resolve().parent
sys.path[:]=[str(root/'site'),*[p for p in sys.path if not {'site-packages','dist-packages'} & set(Path(p).parts)]]
os.environ.setdefault('AI_AD_EDITOR_RUNTIME_DIR',str(root/'runtime'))
from ai_ad_editor.cli import main
raise SystemExit(main())
"""
        (staging/'run.py').write_text(launcher,encoding='utf-8',newline='\n')
        executable=str(Path(sys.executable).resolve()).replace("'","''")
        (staging/'agent-video-kit.ps1').write_text("& '"+executable+"' '-I' '-S' '-B' '-X' 'utf8' (Join-Path $PSScriptRoot 'run.py') @args\nexit $LASTEXITCODE\n",encoding='utf-8',newline='\n')
        (staging/'receipt.json').write_text(json.dumps({'manifest_sha256':expected_manifest,'python':str(Path(sys.executable).resolve()),'target':str(target),'audit':audit_result,'network':'disabled','virtual_environment':False},ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        if cancel_file and Path(cancel_file).exists():raise InstallError('INSTALL_CANCELLED','Cancelled before atomic publication',8)
        if time.monotonic()>=deadline:raise InstallError('INSTALL_TIMEOUT','Deadline before publication',8)
        # Windows rename refuses an existing destination, including an empty dir.
        os.rename(staging,target)
        return {'status':'installed','target':str(target),'manifest_sha256':expected_manifest,'wheels':len(manifest['wheels']),'audit':audit_result}
    finally:
        if staging.exists():remove_owned(staging,target.parent)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--bundle',type=Path,default=Path(__file__).resolve().parent)
    p.add_argument('--target',type=Path,required=True);p.add_argument('--manifest-sha256',required=True)
    p.add_argument('--dry-run',action='store_true');p.add_argument('--cancel-file',type=Path);p.add_argument('--timeout-seconds',type=float,default=180)
    args=p.parse_args()
    try:
        result=install(args.bundle,args.target,args.manifest_sha256,dry_run=args.dry_run,cancel_file=args.cancel_file,timeout_seconds=args.timeout_seconds)
        print(json.dumps({'ok':True,**result},ensure_ascii=False));return 0
    except (InstallError,OSError,ValueError,KeyError,TypeError,zipfile.BadZipFile) as exc:
        print(json.dumps({'ok':False,'code':getattr(exc,'code','INSTALL_FAILED'),'message':str(exc)},ensure_ascii=False));return getattr(exc,'exit_code',2)


if __name__=='__main__':raise SystemExit(main())
