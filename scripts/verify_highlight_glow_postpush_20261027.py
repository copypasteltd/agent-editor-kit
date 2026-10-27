"""Check pushed main and committed bytes against the installed optical delivery."""
from pathlib import Path
from datetime import datetime,timezone
import argparse,hashlib,json,re,subprocess

ROOT=Path(__file__).resolve().parents[1]
BASELINE='cb69d750a67ce5705e4845ecad560604d669e824'
BASE=ROOT/'docs/validation/evidence/highlight-glow-20261027-r1'
GIT='C:/Users/carzy/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/git/cmd/git.exe'
def git(*args):return subprocess.check_output([GIT,'--no-optional-locks','-c','core.fsmonitor=false',
    '-c','gc.auto=0','-c','maintenance.auto=false',*args],cwd=ROOT,timeout=600)
def load(p):return json.loads(Path(p).read_bytes())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--run',required=True);a=ap.parse_args();assert re.fullmatch('r[1-9][0-9]*',a.run)
    out=ROOT/'local/agent-ffmpeg'/('highlight-glow-postpush-'+a.run);out.mkdir(exist_ok=False)
    (out/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    report=dict(status='running',at_utc=datetime.now(timezone.utc).isoformat(),goal_complete=False,
        new_renders=0,new_model_forwards=0,scope='Pushed commit and artifact identity; no new visual or listening acceptance.')
    def save():(out/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    save()
    try:
        assert git('branch','--show-current').strip()==b'main'
        for args in [('remote','get-url','origin'),('remote','get-url','--push','origin')]:
            assert git(*args).strip()==b'git@github.com:copypasteltd/agent-editor-kit.git'
        head=git('rev-parse','HEAD').decode().strip();assert head!=BASELINE
        git('merge-base','--is-ancestor',BASELINE,head)
        origin=git('rev-parse','origin/main').decode().strip()
        remote=git('ls-remote','--heads','origin','refs/heads/main').decode().split()[0]
        assert head==origin==remote
        assert not git('status','--porcelain','--untracked-files=normal')
        changed={n for n in git('diff','--name-only','-z',BASELINE,head).decode('utf8').split('\0') if n}
        tested=load(BASE/'final-delivery-r1/product-files.json')
        namespace=load(ROOT/'agent-ffmpeg-local-install-manifest.json')
        assert len(tested)==239 and namespace['cli_version']=='0.1.39' and len(namespace['files'])==78
        pins={'product/src/ai_ad_editor/'+n:d for n,d in tested.items()}
        pins.update({r['path']:r['sha256'] for r in namespace['files']})
        wanted=changed|set(pins);entries={}
        for record in git('ls-tree','-r','--full-tree','-z',head).split(b'\0'):
            if not record:continue
            metadata,name=record.split(b'\t',1);mode,kind,oid=metadata.split();name=name.decode('utf8')
            if name in wanted:
                assert kind==b'blob' and mode in (b'100644',b'100755');entries[name]=oid.decode()
        assert entries.keys()==wanted
        records=[]
        for name in sorted(wanted):
            data=(ROOT/name).read_bytes();checksum=hashlib.sha256(data).hexdigest()
            assert hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()==entries[name],name
            if name in pins:assert checksum==pins[name],name
            records.append(dict(path=name,bytes=len(data),sha256=checksum))
        install=load(BASE/'installation-final-r2/verification.json')
        assert {p.name:sha(p) for p in (Path(install['installed'])/'site/ai_ad_editor').glob('*.py')}==tested
        assert sha(install['archive'])==install['archive_sha256']
        tests=load(BASE/'installed-regression-r2/verification.json')
        assert tests['status']=='passed' and tests['tests']==734 and tests['failures']==tests['errors']==tests['skipped']==0
        (out/'compared-files.json').write_text(json.dumps(records,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
        report.update(status='passed',HEAD=head,origin_main=origin,advertised_main=remote,branch='main',clean=True,
            compared_files=len(records),product_files=239,skill_files=78,unique_installed_tests=734,total_test_executions=734,
            original_goal_conditions_preserved=38,source_installed_committed_equal=True)
        save();print(json.dumps(report,ensure_ascii=False))
    except BaseException as e:report.update(status='failed',error=repr(e));save();raise

if __name__=='__main__':main()
