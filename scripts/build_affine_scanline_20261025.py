"""Build, verify, unpack and install a new native bundle, preserving prior releases."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path, PurePosixPath
import subprocess
import zipfile

ROOT=Path(__file__).resolve().parents[1]
PYTHON='C:/Python313/python.exe'


def sha(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',required=True)
    args=parser.parse_args();assert args.run.replace('-','').isalnum()
    base=ROOT/'local/agent-ffmpeg/v0.1.0-alpha.4-local.15'
    bundle=base/('candidate-'+args.run)/'bundle'
    unpacked=base/('unpacked-'+args.run)
    installed=base/('final-'+args.run)/'installed'
    evidence=ROOT/'docs/validation/evidence/affine-scanline-20261025-r1'/('installation-'+args.run)
    evidence.mkdir(parents=True,exist_ok=False)
    (evidence/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    def save(name,value):
        (evidence/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    calls=[]
    def run(name,arguments,timeout=900):
        started=datetime.now(timezone.utc).isoformat()
        result=subprocess.run([*map(str,arguments)],cwd=ROOT,capture_output=True,timeout=timeout,
                              creationflags=subprocess.CREATE_NO_WINDOW)
        stdout=evidence/(name+'.stdout.json');stderr=evidence/(name+'.stderr.txt')
        stdout.write_bytes(result.stdout);stderr.write_bytes(result.stderr)
        calls.append(dict(name=name,argv=list(map(str,arguments)),exit_code=result.returncode,
                          started_at_utc=started,stdout_sha256=sha(stdout),stderr_sha256=sha(stderr)))
        save('calls.json',calls);print(json.dumps(dict(name=name,exit_code=result.returncode)),flush=True)
        assert result.returncode==0,result.stderr.decode('utf-8','replace')[-4000:]
        return json.loads(result.stdout.decode('utf-8-sig'))
    source=ROOT/'product/src/ai_ad_editor'
    before={p.name:sha(p) for p in source.glob('*.py')}
    result=dict(status='running',started_at_utc=datetime.now(timezone.utc).isoformat(),
                native_windows=True,virtualization=False,source_fallback=False)
    try:
        built=run('build',[PYTHON,'-E','-B','-u','-X','utf8',ROOT/'product/offline/build.py','--output',bundle])
        archive=bundle.with_suffix('.zip');assert built['archive_sha256']=='sha256:'+sha(archive)
        expected=built['manifest_sha256']
        unpacked.mkdir(parents=True,exist_ok=False)
        with zipfile.ZipFile(archive) as zipped:
            names=zipped.namelist();assert len(names)==len(set(names)) and len(names)<256
            total=0
            for info in zipped.infolist():
                relative=PurePosixPath(info.filename)
                assert not relative.is_absolute() and '..' not in relative.parts and ':' not in info.filename
                assert '\\' not in info.filename and not info.is_dir() and info.file_size<1024**3
                assert not ((info.external_attr>>16)&0o170000)==0o120000
                total+=info.file_size;assert total<2*1024**3
                destination=unpacked/Path(*relative.parts)
                assert destination.resolve().is_relative_to(unpacked.resolve())
                destination.parent.mkdir(parents=True,exist_ok=True)
                with zipped.open(info) as reader,destination.open('xb') as writer:
                    while chunk:=reader.read(1024**2):writer.write(chunk)
        assert expected=='sha256:'+sha(unpacked/'manifest.json')
        installed_result=run('install',[PYTHON,'-E','-B','-u','-X','utf8',unpacked/'install.py',
            '--bundle',unpacked,'--target',installed,'--manifest-sha256',expected,'--timeout-seconds','600'])
        assert installed_result['ok']
        prefix=[PYTHON,'-I','-S','-B','-u','-X','utf8',installed/'run.py']
        version=run('version',[*prefix,'version']);assert version['data']['cli_version']=='0.1.17'
        capabilities=run('capabilities',[*prefix,'capabilities']);assert capabilities['ok']
        entries=[]
        for name,digest in sorted(before.items()):
            target=installed/'site/ai_ad_editor'/name
            assert sha(target)==digest==sha(source/name),name
            entries.append(dict(path=name,sha256=digest))
        assert {p.name:sha(p) for p in source.glob('*.py')}==before
        result.update(status='installed-and-byte-verified',installed=str(installed),archive=str(archive),
            archive_bytes=archive.stat().st_size,archive_sha256=sha(archive),manifest_sha256=expected,
            cli_version='0.1.17',source_file_count=len(entries),source_and_installed_equal=True,
            source_files=entries,capability_count=len(capabilities['data']['capabilities']),
            new_renders=0,new_model_forwards=0,finished_at_utc=datetime.now(timezone.utc).isoformat())
        save('verification.json',result)
        print(json.dumps({k:v for k,v in result.items() if k!='source_files'},ensure_ascii=False),flush=True)
    except BaseException as exc:
        result.update(status='failed',error=repr(exc));save('verification.json',result);raise


if __name__=='__main__':main()
