"""Freeze the complete operational code, then prepare pinned baseline artifacts."""
import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import zipfile


ROOT = Path(__file__).resolve().parent
PROJECT = ROOT.parents[2]
CODE = ('case.py','remote_baseline.py','remote_control.py','transfer_server.py','prepare_transfer.py')
DOCS = PROJECT / 'docs/validation/cross_machine63_20261106_r2'
EVIDENCE = PROJECT / 'docs/validation/evidence/delivery66-cross-machine-20261106-r1'
TOOLS = Path('C:/Users/carzy/AppData/Local/Microsoft/WinGet/Packages/Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe/ffmpeg-8.1-full_build')
APPLICATION = PROJECT / 'local/agent-ffmpeg/v0.1.0-alpha.4-local.61/candidate-r1/bundle.zip'
SKILL = PROJECT / 'docs/skills/agent-editor-kit-community-unified-skill-r58.zip'
MANIFEST = 'sha256:65e94e4ed549d065175a31b891f7890fc4e23cece74733710a21629b8f06bdca'


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream,'sha256').hexdigest()


def save(path, value):
    with Path(path).open('x',encoding='utf-8',newline='\n') as stream:
        json.dump(value,stream,ensure_ascii=False,indent=2)
        stream.write('\n')


def freeze():
    assert not DOCS.exists()
    for name in CODE:
        compile((ROOT / name).read_bytes(),name,'exec')
    DOCS.mkdir(parents=True)
    for name in CODE:
        shutil.copyfile(ROOT / name,DOCS / name)
    records = [{'path':str((DOCS / name).relative_to(PROJECT)).replace('\\','/'),
                'bytes':(DOCS / name).stat().st_size,'sha256':sha(DOCS / name)} for name in CODE]
    output = EVIDENCE / 'baseline-code-phase-r2'
    output.mkdir(parents=True,exist_ok=False)
    value = dict(status='complete-operational-code-frozen-before-functional-validation',files=records,
                 operational_run=ROOT.name,
                 observed_at_utc=dt.datetime.now(dt.timezone.utc).isoformat(),
                 cli_version='0.1.63',cli66_accepted=False,formal_files_modified=False,
                 functional_tests_executed=False,model_inference=False,docker_wsl_vm_used=False)
    save(output / 'verification.json',value)
    print(json.dumps(value,ensure_ascii=False))


def assert_frozen():
    records=json.loads((EVIDENCE / 'baseline-code-phase-r2/verification.json').read_bytes())['files']
    for row in records:
        assert sha(PROJECT / row['path']) == row['sha256']
        assert sha(ROOT / Path(row['path']).name) == row['sha256']


def tools():
    assert_frozen()
    archive=ROOT / 'native-tools.zip'
    records=[]
    paths=[('ffmpeg.exe',TOOLS/'bin/ffmpeg.exe'),('ffprobe.exe',TOOLS/'bin/ffprobe.exe'),
           ('LICENSE',TOOLS/'LICENSE'),('README.txt',TOOLS/'README.txt')]
    with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=1,allowZip64=False) as zipped:
        for name,path in paths:
            assert path.is_file()
            records.append(dict(name=name,source=str(path),bytes=path.stat().st_size,sha256=sha(path)))
            zipped.write(path,name)
    value=dict(status='pinned-existing-native-tools-archived',files=records,archive_sha256=sha(archive),
               archive_bytes=archive.stat().st_size,public_release_asset=False,
               primary_tools_reconfigured=False,remote_global_PATH_changed=False)
    save(ROOT/'native-tools.json',value)
    print(json.dumps({k:v for k,v in value.items() if k!='files'},ensure_ascii=False))


def parcels():
    assert_frozen()
    expected=ROOT/'primary/expected.json'
    accepted=json.loads((ROOT/'primary/verification.json').read_bytes())
    assert accepted['status']=='primary-baseline-passed' and accepted['cli_version']=='0.1.63'
    pins={APPLICATION:'c9151896fe28de8446adfe35633b18956e3e390bac0ccaa038f713be233e9727',
          SKILL:'bc19f2b64ae88997e4ca5fae1a3c59b016541d1c9bae0393b8f37cb522c19c0a'}
    for path,pin in pins.items():
        assert sha(path)==pin
    paths=[('application.zip',APPLICATION),('skill.zip',SKILL),('tools.zip',ROOT/'native-tools.zip'),
           ('baseline.aevpkg.zip',ROOT/'primary/baseline.aevpkg.zip'),('expected.json',expected),('case.py',ROOT/'case.py'),
           ('remote_baseline.py',ROOT/'remote_baseline.py')]
    value=dict(remote_ip='192.168.196.209',remote_hostname='DESKTOP-TE44HE1',manifest_sha256=MANIFEST,
               files=[dict(name=name,path=str(path),bytes=path.stat().st_size,sha256=sha(path)) for name,path in paths])
    save(ROOT/'parcels.json',value)
    print(json.dumps(dict(status='seven-pinned-transfer-roles-prepared',files=len(value['files']),
                         total_bytes=sum(row['bytes'] for row in value['files'])),ensure_ascii=False))


if __name__=='__main__':
    assert os.name=='nt' and sys.dont_write_bytecode and sys.prefix==sys.base_prefix
    parser=argparse.ArgumentParser()
    parser.add_argument('action',choices=('freeze','tools','parcels'))
    {'freeze':freeze,'tools':tools,'parcels':parcels}[parser.parse_args().action]()
