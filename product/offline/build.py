"""Build a pinned native offline bundle using existing local wheels only."""
from __future__ import annotations
import argparse
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


def build(output,wheelhouse):
    INSTALLER['native_target']()
    output=INSTALLER['local_path'](output);wheelhouse=INSTALLER['local_path'](wheelhouse)
    INSTALLER['no_reparse'](output);INSTALLER['no_reparse'](wheelhouse)
    wheelhouse=wheelhouse.resolve(strict=True)
    if output.exists():raise ValueError('Existing output is preserved')
    lock=json.loads((wheelhouse/'lock.json').read_bytes(),object_pairs_hook=INSTALLER['strict_object'])
    if lock['target']!='cp313-win_amd64':raise ValueError('Wrong wheelhouse target')
    profile=lock.get('runtime_profile','font-text-v1')
    if profile not in INSTALLER['RUNTIME_PROFILES']:raise ValueError('Unknown offline runtime profile')
    dependencies=tomllib.loads((ROOT/'product/pyproject.toml').read_text('utf8'))['project'].get('dependencies',[])
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
    # Setuptools can retain removed package-data files in product/build/lib.
    # Rebuild this generated directory so a removed LUT is not redistributed.
    generated=ROOT/'product/build'
    INSTALLER['no_reparse'](generated)
    if generated.resolve().parent!=(ROOT/'product').resolve():raise ValueError('Generated build directory escaped product')
    if generated.exists():shutil.rmtree(generated)
    output.mkdir(parents=True);wheels=output/'wheels';wheels.mkdir()
    work=ROOT/'product/.runtime/offline-build';work.mkdir(parents=True,exist_ok=True)
    env=dict(os.environ);env.update(TEMP=str(work),TMP=str(work),TMPDIR=str(work),PIP_CONFIG_FILE=os.devnull,PIP_NO_INDEX='1',PIP_NO_CACHE_DIR='1',PIP_DISABLE_PIP_VERSION_CHECK='1',PYTHONDONTWRITEBYTECODE='1')
    command=[sys.executable,'-I','-B','-m','pip','wheel','--no-index','--no-deps','--no-build-isolation','--wheel-dir',str(wheels),str(ROOT/'product')]
    with (output/'build.log').open('wb') as stream:
        result=subprocess.run(command,cwd=work,env=env,stdout=stream,stderr=subprocess.STDOUT,timeout=900)
    if result.returncode:raise RuntimeError((output/'build.log').read_text(encoding='utf-8',errors='replace'))
    product=next(wheels.glob('*.whl'))
    with zipfile.ZipFile(product) as archive:
        info=BytesParser().parsebytes(archive.read(next(n for n in archive.namelist() if n.endswith('.dist-info/METADATA'))))
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
    args=parser.parse_args();print(json.dumps(build(args.output,args.wheelhouse),ensure_ascii=False))
