"""Compare staged blobs with the tested source and pinned single Skill."""
from pathlib import Path
from datetime import datetime,timezone
import argparse,hashlib,json,subprocess,re

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/validation/evidence/native-interpolation-20261027-r1'
GIT='C:/Users/carzy/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/git/cmd/git.exe'
BASELINE='656d136f2677d7ce07c4bb9734370cc7f9147e50'

def git(*args,data=None):return subprocess.check_output([GIT,'--no-optional-locks','-c','core.fsmonitor=false','-c','gc.auto=0','-c','maintenance.auto=false',*args],cwd=ROOT,input=data,timeout=600)
def load(p):return json.loads(Path(p).read_bytes())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--run',required=True);a=ap.parse_args();assert re.fullmatch('r[1-9][0-9]*',a.run)
    out=BASE/('staged-byte-'+a.run);out.mkdir(exist_ok=False)
    (out/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    assert git('rev-parse','HEAD').decode().strip()==BASELINE and git('branch','--show-current').strip()==b'main'
    assert git('remote','get-url','origin').strip()==b'git@github.com:copypasteltd/agent-editor-kit.git'
    assert not git('diff','--cached','--name-only','--diff-filter=D')
    git('diff','--cached','--check')
    staged=[name for name in git('diff','--cached','--name-only','-z').decode('utf8').split('\0') if name]
    assert staged and not any(name.startswith(('sources/','local/','workspace/')) for name in staged)
    tested=load(BASE/'final-delivery-r1/product-files.json');manifest=load(ROOT/'agent-ffmpeg-local-install-manifest.json')
    assert len(tested)==257 and len(manifest['files'])==81
    pins={'product/src/ai_ad_editor/'+n:d for n,d in tested.items()}
    pins.update({r['path']:r['sha256'] for r in manifest['files']})
    names=set(staged)|set(pins)
    # One index read; Git blob IDs include the blob header and raw byte count.
    entries={}
    for record in git('ls-files','--stage','-z').split(b'\0'):
        if not record:continue
        meta,name=record.split(b'\t',1);mode,oid,stage=meta.split()
        if name.decode('utf8') in names:
            assert stage==b'0';entries[name.decode('utf8')]=oid.decode('ascii')
    assert entries.keys()==names
    records=[]
    for name in sorted(names):
        data=(ROOT/name).read_bytes();checksum=hashlib.sha256(data).hexdigest()
        assert hashlib.sha1(b'blob '+str(len(data)).encode('ascii')+b'\0'+data).hexdigest()==entries[name],name
        if name in pins:assert checksum==pins[name],name
        records.append({'path':name,'bytes':len(data),'sha256':checksum,'staged_change':name in staged})
    final=load(BASE/'final-delivery-r1/verification.json');assert final['status']=='passed'
    for row in load(BASE/'final-delivery-r1/files.json'):assert sha(ROOT/row['path'])==row['sha256'],row['path']
    report={'status':'passed','at_utc':datetime.now(timezone.utc).isoformat(),'baseline_commit':BASELINE,
        'staged_files':len(staged),'compared_files':len(names),'tested_product_files':257,'skill_files':81,
        'staged_bytes_equal_disk':True,'historical_goal_conditions_preserved':38,'goal_complete':False,
        'files':records,'scope':'Byte verification only; no new render, model inference or human quality acceptance.'}
    (out/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    git('add','--',out.relative_to(ROOT).as_posix())
    for path in out.iterdir():assert git('show',':'+path.relative_to(ROOT).as_posix())==path.read_bytes()
    git('diff','--cached','--check');assert not git('diff','--name-only')
    assert not git('ls-files','--others','--exclude-standard')
    print(json.dumps({k:v for k,v in report.items() if k!='files'},ensure_ascii=False))

if __name__=='__main__':main()
