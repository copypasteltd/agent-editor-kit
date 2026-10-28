"""Pin the unified Skill only after matching frozen source/installed CLI53 gates."""
import argparse,hashlib,json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'docs/validation/evidence/aces-delivery-20261029-r1'
SOURCE=ROOT/'docs/validation/evidence/aces-pipeline-20261029-r1'
def load(p):return json.loads(Path(p).read_bytes())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,value):p.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')

def main():
    p=argparse.ArgumentParser();p.add_argument('--run',required=True);p.add_argument('--installation-run',default='r2');a=p.parse_args();assert a.run.replace('-','').isalnum() and a.installation_run.replace('-','').isalnum()
    installation=load(BASE/('installation-final-'+a.installation_run)/'verification.json')
    assert installation['status']=='installed-and-byte-verified' and installation['cli_version']=='0.1.53'
    package=Path(installation['installed'])/'site/ai_ad_editor';source=ROOT/'product/src/ai_ad_editor'
    pins={p.name:sha(p) for p in source.glob('*.py')};assert len(pins)==280
    assert pins=={p.name:sha(p) for p in package.glob('*.py')}
    for name,n in [('special-r4',18),('meter-r4',46),('compat-r5',373)]:
        v=load(SOURCE/(name+'.json'))
        assert v['status']=='passed' and v['tests']==n and v['skipped']==0 and v['frozen_equal']
        assert all(sha(ROOT/name)==digest for name,digest in v['source_files'].items())
    for name,n in [('installed-special-r1',18),('installed-meter-r1',46),('installed-compat-r1',373)]:
        v=load(BASE/name/'verification.json')
        assert v['status']=='passed' and v['tests']==n and v['skipped']==0 and v['frozen_equal']
        assert v['source_fallback'] is False and v['isolated'] and v['no_site']
        assert all(sha(source/name)==digest==sha(package/name) for name,digest in v['files'].items())
        assert all(sha(ROOT/'product/tests'/name)==digest for name,digest in v['test_files'].items())
    native=load(BASE/'installed-native-r1/verification.json');assert native['status']=='passed' and native['actual_native_transform']
    assert native['actual_DLL']==str((package/'native_ocio/OpenColorIO_2_6.dll').resolve())
    ns=ROOT/'agent-ffmpeg-local-install-manifest.json';manifest=load(ns)
    assert manifest['cli_version']=='0.1.52' and len(manifest['files'])==91
    for row in manifest['files']:assert sha(ROOT/row['path'])==row['sha256']
    stage=ROOT/'local/agent-ffmpeg/aces-skill-stage51/skills/agent-ffmpeg-local-editor'
    folder=ROOT/'skills/agent-ffmpeg-local-editor'
    assert len([p for p in stage.rglob('*') if p.is_file()])==92
    changes={}
    for p in stage.rglob('*'):
        if p.is_file() and (not (folder/p.relative_to(stage)).is_file() or sha(p)!=sha(folder/p.relative_to(stage))):
            changes[p.relative_to(stage).as_posix()]=p.read_bytes()
    runner=(stage/'scripts/run.py').read_text('utf-8')
    runner,n=re.subn(r"^MANIFEST = '[^']+'$",'MANIFEST = '+repr(installation['manifest_sha256']),runner,count=1,flags=re.M);assert n==1
    runner,n=re.subn(r"^RELEASE = '[^']+'$","RELEASE = 'v0.1.0-alpha.4-local.51'",runner,count=1,flags=re.M);assert n==1
    changes['scripts/run.py']=runner.encode('utf-8')
    out=BASE/('skill-pin-'+a.run);out.mkdir(exist_ok=False)
    (out/'executed-runner.py').write_bytes(Path(__file__).read_bytes());(out/'previous-namespace.json').write_bytes(ns.read_bytes())
    for name,content in changes.items():
        target=folder/name
        if target.exists():
            backup=out/'previous-skill'/name;backup.parent.mkdir(parents=True,exist_ok=True);backup.write_bytes(target.read_bytes())
        target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(content)
    manifest.update(release='v0.1.0-alpha.4-local.51',cli_version='0.1.53',manifest_sha256=installation['manifest_sha256'])
    manifest['skills'][0]['skill_md_sha256']=sha(folder/'SKILL.md')
    manifest['files']=[dict(path=p.relative_to(ROOT).as_posix(),bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(folder.rglob('*')) if p.is_file()]
    assert len(manifest['files'])==92 and sum(Path(row['path']).name=='SKILL.md' for row in manifest['files'])==1
    save(ns,manifest)
    report=dict(status='pinned-for-runtime-activation',cli_version='0.1.53',public_entries=1,modules=17,skill_files=92,
        source_special=18,source_meter=46,source_compatibility=373,installed_special=18,installed_meter=46,installed_compatibility=373,
        actual_installed_native_DLL=True,source_fallback=False,namespace_manifest_sha256=sha(ns),changed_files=sorted(changes))
    save(out/'verification.json',report);print(json.dumps(report))

if __name__=='__main__':main()
