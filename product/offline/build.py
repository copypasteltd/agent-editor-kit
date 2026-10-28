"""Build a pinned native offline bundle using existing local wheels only."""
from __future__ import annotations
import argparse
import ast
import hashlib
import json
import os
import re
import runpy
from pathlib import Path
import shutil
import subprocess
import sys
import tomllib
import zipfile
from email.parser import BytesParser
from datetime import datetime,timezone

ROOT=Path(__file__).resolve().parents[2]
INSTALLER=runpy.run_path(str(Path(__file__).with_name('install.py')))


def sha(path):return 'sha256:'+hashlib.sha256(Path(path).read_bytes()).hexdigest()


def matching_product_version(metadata_text, source_text):
    metadata=tomllib.loads(metadata_text)['project']
    versions=[ast.literal_eval(n.value) for n in ast.parse(source_text).body if isinstance(n,ast.Assign)
        and any(isinstance(t,ast.Name) and t.id=='VERSION' for t in n.targets)]
    if len(versions)!=1 or metadata.get('version')!=versions[0]:
        raise ValueError('Product distribution version differs from source CLI VERSION')
    return versions[0]


def validate_product_wheel(path,version,project_text,source_root,expected_sha256):
    """Reuse only an explicitly pinned wheel with the exact current package payload."""
    if not isinstance(expected_sha256,str) or not re.fullmatch(r'sha256:[0-9a-f]{64}',expected_sha256):
        raise ValueError('Reused product wheel requires an explicit SHA256 pin')
    path=Path(path);INSTALLER['no_reparse'](path)
    if not path.is_file() or not path.name.endswith('.whl') or sha(path)!=expected_sha256:
        raise ValueError('Reused product wheel digest differs from its explicit pin')
    patterns=tomllib.loads(project_text)['tool']['setuptools']['package-data']['ai_ad_editor']
    expected={p.relative_to(source_root).as_posix():p for p in source_root.glob('*.py') if p.is_file()}
    for pattern in patterns:
        expected.update({p.relative_to(source_root).as_posix():p for p in source_root.glob(pattern) if p.is_file()})
    if not expected:raise ValueError('Empty source package payload')
    prefix='ai_ad_editor-'+version
    metadata_prefix=prefix+'.dist-info/'
    allowed_metadata={'METADATA','WHEEL','entry_points.txt','top_level.txt','RECORD'}
    payload={};metadata={}
    with zipfile.ZipFile(path) as archive:
        names=archive.namelist()
        if len(names)!=len(set(names)):raise ValueError('Duplicate product wheel members')
        for entry in archive.infolist():
            name=entry.filename
            if entry.is_dir() or '\\' in name or ':' in name or name.startswith('/') or '..' in name.split('/') or ((entry.external_attr>>16)&0o170000)==0o120000:
                raise ValueError('Unsafe product wheel member')
            if name.startswith(metadata_prefix) and name[len(metadata_prefix):] in allowed_metadata:
                metadata[name[len(metadata_prefix):]]=archive.read(entry);continue
            relative=None
            for base in ('ai_ad_editor/',prefix+'.data/purelib/ai_ad_editor/',prefix+'.data/platlib/ai_ad_editor/'):
                if name.startswith(base):relative=name[len(base):];break
            if relative is None or relative not in expected or relative in payload:
                raise ValueError('Unexpected or duplicate product payload: '+name)
            source=expected[relative];INSTALLER['no_reparse'](source)
            if entry.file_size!=source.stat().st_size:raise ValueError('Product wheel payload size differs: '+relative)
            with archive.open(entry) as stream:digest='sha256:'+hashlib.file_digest(stream,'sha256').hexdigest()
            if digest!=sha(source):raise ValueError('Product wheel payload bytes differ: '+relative)
            payload[relative]=digest
    if set(payload)!=set(expected) or not {'METADATA','WHEEL','RECORD'}<=metadata.keys():
        raise ValueError('Incomplete product wheel payload or metadata')
    info=BytesParser().parsebytes(metadata['METADATA'])
    if re.sub('[-_.]+','-',str(info['Name'])).lower()!='ai-ad-editor' or info['Version']!=version:
        raise ValueError('Reused product wheel metadata differs from source')
    if sha(path)!=expected_sha256:raise ValueError('Product wheel changed during verification')
    return {'sha256':expected_sha256,'payload_files':len(payload),'payload_byte_exact':True}


def build(output,wheelhouse,product_wheel=None,product_wheel_sha256=None):
    INSTALLER['native_target']()
    output=INSTALLER['local_path'](output);wheelhouse=INSTALLER['local_path'](wheelhouse)
    INSTALLER['no_reparse'](output);INSTALLER['no_reparse'](wheelhouse)
    wheelhouse=wheelhouse.resolve(strict=True)
    if output.exists():raise ValueError('Existing output is preserved')
    lock=json.loads((wheelhouse/'lock.json').read_bytes(),object_pairs_hook=INSTALLER['strict_object'])
    if lock['target']!='cp313-win_amd64':raise ValueError('Wrong wheelhouse target')
    profile=lock.get('runtime_profile','font-text-v1')
    if profile not in INSTALLER['RUNTIME_PROFILES']:raise ValueError('Unknown offline runtime profile')
    project_text=(ROOT/'product/pyproject.toml').read_text('utf8')
    version=matching_product_version(project_text,(ROOT/'product/src/ai_ad_editor/__init__.py').read_text('utf8'))
    dependencies=tomllib.loads(project_text)['project'].get('dependencies',[])
    if any(re.match(r'(?i)^numpy\b',item) for item in dependencies) and profile!='media-analysis-v1':
        raise ValueError('Product requires NumPy; use the complete media-analysis-v1 wheelhouse')
    pinned=[];names=set()
    for entry in lock['artifacts']:
        if entry['runtime_dependency'] is not True:continue
        filename=INSTALLER['safe_name'](entry['filename'])
        if '/' in filename or not filename.endswith('.whl'):raise ValueError('Dependency filename must be a local wheel basename')
        source=wheelhouse/filename;INSTALLER['no_reparse'](source)
        if source.stat().st_size!=entry['bytes'] or sha(source)!=entry['sha256']:raise ValueError('Dependency source changed: '+filename)
        if entry['name'] in names:raise ValueError('Duplicate dependency wheel')
        names.add(entry['name']);pinned.append(entry)
    if names!=INSTALLER['RUNTIME_PROFILES'][profile]-{'ai-ad-editor'}:
        raise ValueError('Incomplete '+profile+' pinned dependency wheelhouse; NumPy is required for media-analysis-v1')
    reused=None
    if product_wheel is not None:
        product_wheel=INSTALLER['local_path'](product_wheel)
        reused=validate_product_wheel(product_wheel,version,project_text,ROOT/'product/src/ai_ad_editor',product_wheel_sha256)
    elif product_wheel_sha256 is not None:raise ValueError('Product wheel pin requires --product-wheel')
    # Setuptools can retain removed package-data files in product/build/lib.
    # Rebuild this generated directory so a removed LUT is not redistributed.
    generated=ROOT/'product/build'
    INSTALLER['no_reparse'](generated)
    if generated.resolve().parent!=(ROOT/'product').resolve():raise ValueError('Generated build directory escaped product')
    if product_wheel is None and generated.exists():shutil.rmtree(generated)
    output.mkdir(parents=True);wheels=output/'wheels';wheels.mkdir()
    work=ROOT/'product/.runtime/offline-build';work.mkdir(parents=True,exist_ok=True)
    env=dict(os.environ);env.update(TEMP=str(work),TMP=str(work),TMPDIR=str(work),PIP_CONFIG_FILE=os.devnull,PIP_NO_INDEX='1',PIP_NO_CACHE_DIR='1',PIP_DISABLE_PIP_VERSION_CHECK='1',PYTHONDONTWRITEBYTECODE='1')
    command=[sys.executable,'-I','-B','-m','pip','wheel','--no-index','--no-deps','--no-build-isolation','--wheel-dir',str(wheels),str(ROOT/'product')]
    if reused is not None:
        shutil.copyfile(product_wheel,wheels/product_wheel.name)
        validate_product_wheel(wheels/product_wheel.name,version,project_text,ROOT/'product/src/ai_ad_editor',product_wheel_sha256)
        (output/'build.log').write_text(json.dumps({'mode':'verified-existing-product-wheel',**reused})+'\n',encoding='utf-8')
    else:
        with (output/'build.log').open('wb') as stream:
            result=subprocess.run(command,cwd=work,env=env,stdout=stream,stderr=subprocess.STDOUT,timeout=900)
        if result.returncode:raise RuntimeError((output/'build.log').read_text(encoding='utf-8',errors='replace'))
    product=next(wheels.glob('*.whl'))
    with zipfile.ZipFile(product) as archive:
        info=BytesParser().parsebytes(archive.read(next(n for n in archive.namelist() if n.endswith('.dist-info/METADATA'))))
    if info['Version']!=version:raise ValueError('Built wheel version differs from source CLI VERSION')
    rows=[{'name':'ai-ad-editor','version':info['Version'],'path':'wheels/'+product.name}]
    for entry in pinned:
        source=wheelhouse/entry['filename']
        if source.stat().st_size!=entry['bytes'] or sha(source)!=entry['sha256']:raise ValueError('Dependency source changed: '+entry['filename'])
        shutil.copyfile(source,wheels/source.name)
        if sha(wheels/source.name)!=entry['sha256']:raise ValueError('Dependency source changed during copy: '+source.name)
        rows.append({'name':entry['name'],'version':entry['version'],'path':'wheels/'+source.name})
    # Redistribute unmodified original notices from every shipped wheel.
    for row in rows:
        with zipfile.ZipFile(output/row['path']) as archive:
            for entry in archive.namelist():
                if entry.endswith('/') or not any(x in Path(entry).name.upper() for x in ('LICENSE','COPYING','NOTICE')):continue
                target=output/'licenses'/row['name']/entry;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(archive.read(entry))
    shutil.copyfile(Path(__file__).with_name('install.py'),output/'install.py')
    (output/'requirements.lock').write_text(''.join('./'+row['path']+' --hash='+sha(output/row['path'])+'\n' for row in rows),encoding='utf-8',newline='\n')
    files=[{'path':file.relative_to(output).as_posix(),'bytes':file.stat().st_size,'sha256':sha(file)} for file in sorted(output.rglob('*')) if file.is_file()]
    contract=ROOT/'product/src/ai_ad_editor/agent-project.schema.json'
    if contract.read_bytes()!=(ROOT/'docs/specs/agent-project.schema.json').read_bytes():raise ValueError('Source and packaged schemas differ')
    manifest={'format':'agent-video-kit-offline-v1','target':'cp313-win_amd64','created_at_utc':datetime.now(timezone.utc).isoformat(),'schema_sha256':sha(contract),'wheels':rows,'files':files,'python_included':False,'ffmpeg_included':False,'network':'disabled','author_signature':False}
    manifest['runtime_profile']=profile
    if {r['name'] for r in rows}!=INSTALLER['RUNTIME_PROFILES'][profile]:
        raise ValueError('Release wheel set differs from its runtime profile')
    (output/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    archive_path=output.with_suffix('.zip')
    if archive_path.exists():raise ValueError('Existing archive is preserved')
    with zipfile.ZipFile(archive_path,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
        for file in sorted(output.rglob('*')):
            if file.is_file():archive.write(file,file.relative_to(output).as_posix())
    return {'bundle':str(output),'archive':str(archive_path),'archive_sha256':sha(archive_path),'manifest_sha256':sha(output/'manifest.json'),'wheels':len(rows),'files':len(files)}


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True);parser.add_argument('--wheelhouse',type=Path,default=ROOT/'sources/python-runtime/cp313-win_amd64-media')
    parser.add_argument('--product-wheel',type=Path,help='Reuse an explicitly pinned, byte-verified current product wheel')
    parser.add_argument('--product-wheel-sha256',help='Required sha256:<64 lowercase hex> pin for --product-wheel')
    args=parser.parse_args();print(json.dumps(build(args.output,args.wheelhouse,args.product_wheel,args.product_wheel_sha256),ensure_ascii=False))
