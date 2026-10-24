"""Audit installed semantic delivery, all README history and optionally Git index bytes."""
from pathlib import Path
from datetime import datetime,timezone
from urllib.parse import unquote
import argparse,ast,collections,hashlib,json,re,subprocess,zipfile
from verify_semantic_20261025 import ROOT,TRUTH,TRUTH_SHA,sha,save
from run_frozen_regression import frozen

BASE=ROOT/'docs/validation/evidence/semantic-20261025-r1'
GIT='C:/Users/carzy/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/git/cmd/git.exe'


def load(name):return json.loads((BASE/name).read_bytes())
def git(*args):
    result=subprocess.run([GIT,'--no-optional-locks','-c','core.fsmonitor=false','-c','gc.auto=0','-c','maintenance.auto=false',*args],
        cwd=ROOT,capture_output=True,timeout=180,creationflags=subprocess.CREATE_NO_WINDOW)
    assert result.returncode==0,result.stderr
    return result.stdout


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True);parser.add_argument('--staged',action='store_true')
    args=parser.parse_args();assert not args.output.exists();checks={}
    assert sha(TRUTH)==TRUTH_SHA
    truth=json.loads(TRUTH.read_bytes())
    for row in truth['assets']:assert sha(ROOT/row['path'])==row['sha256']
    checks['frozen_truth_and_sources']=True
    phases=[('development-r1/setup',13),('development-r1/index',2),('development-r1/queries',5),
        ('development-controls-r1/controls',8),('installed-r1/setup',13),('installed-r1/index',2),
        ('skill-r1',9),('demo-development-r1',11),('demo-installed-r1-workflow',11)]
    newly_observed_streams=[]
    for name,count in phases:
        receipt=load(name+'/verification.json')
        assert receipt['status'].startswith('passed') and receipt['commands']==count,(name,receipt['status'])
        calls=load(name+'/calls.json');assert len(calls)==count
        for ordinal,row in enumerate(calls,1):
            for suffix,key in [('stdout.json','stdout_sha256'),('stderr.txt','stderr_sha256')]:
                file=BASE/name/f'{ordinal:02}.{suffix}'
                observed=sha(file)
                if key in row:
                    assert observed==row[key].removeprefix('sha256:'),(str(file),key)
                else:
                    newly_observed_streams.append(dict(path=file.relative_to(ROOT).as_posix(),sha256=observed,
                        scope='Current audit digest; original demonstration receipt pinned stdout only'))
    checks['real_cli_receipts_and_raw_streams']={name:count for name,count in phases}
    checks['newly_observed_stderr_digests']=newly_observed_streams
    current=frozen()
    for name,methods in [('contract-tests-r2',25),('installed-contract-tests-r1',25),('cli-regression-r1',122),('offline-regression-r1',34)]:
        record=load(name+'.json')
        assert record['exit_code']==0 and record['terminal_ok'] and record['frozen_equal'] and record['methods']==methods
        assert sha(BASE/(name+'.log'))==record['log_sha256'].removeprefix('sha256:')
        assert record['frozen_before']==current,'Product/test bytes differ from executed regression'
    checks['regressions_frozen_and_separate']=[25,25,122,34]
    assert load('development-r1/queries/verification.json')['quality_all_gates_passed']
    quality=load('development-r1/queries/quality.json');skill_quality=load('skill-r1/quality.json')
    assert len(quality['queries'])==len(skill_quality['queries'])==20
    for sample in (quality,quality['cpu'],skill_quality):
        assert sample['positive_top1']==sample['positive_mean_recall_at_3']==1.
        assert sample['negation_successes']==1 and sample['out_of_domain_queries_with_candidates']==2
    checks['all_20_queries_failures_retained']=True
    install=load('installation/verification.json');installed=Path(install['installed'])
    assert sha(Path(install['archive']))==install['archive_sha256']
    assert sha(Path(install['archive']).with_suffix('')/'manifest.json')==install['manifest_sha256']
    for row in install['python_source_files']:
        assert sha(ROOT/'product/src/ai_ad_editor'/row['path'])==sha(installed/'site/ai_ad_editor'/row['path'])==row['source_sha256']
    checks['installed_python_files_match']=len(install['python_source_files'])
    manifest=json.loads((ROOT/'agent-ffmpeg-local-install-manifest.json').read_bytes())
    runtime=json.loads((ROOT/'local/agent-ffmpeg/runtime.json').read_bytes())
    assert manifest['release']==runtime['release']=='v0.1.0-alpha.4-local.3' and manifest['cli_version']=='0.1.5'
    assert manifest['manifest_sha256']==runtime['manifest_sha256']=='sha256:'+install['manifest_sha256']
    assert sha(installed/'run.py')==runtime['launcher_sha256']
    assert manifest['skill_count']==1 and manifest['module_count']==17 and len(manifest['modules'])==17
    for row in manifest['files']:assert sha(ROOT/row['path'])==row['sha256'] and (ROOT/row['path']).stat().st_size==row['bytes']
    entry=Path('C:/Users/carzy/.codex/skills/agent-ffmpeg-local-editor')
    assert entry.resolve()==(ROOT/'skills/agent-ffmpeg-local-editor').resolve()
    assert Path(runtime['semantic_config']).exists()
    caps=json.loads((ROOT/'docs/product/semantic-capabilities-cli-0.1.5.json').read_bytes())['data']['capabilities']
    assert collections.Counter(r['status'] for r in caps.values())==dict(implemented=20,implemented_with_limits=45,local_adapter_only=7,degraded=1)
    checks['installed_pin_one_skill_17_modules_73_declarations']=True
    kit=ROOT/'docs/skills/agent-editor-kit-community-unified-skill-r4.zip'
    package=json.loads((ROOT/'docs/skills/community-unified-skill-package-0.1.5.json').read_bytes())
    assert sha(kit)==package['sha256']==load('kit-r1/verification.json')['kit_sha256']
    assert load('kit-r1/verification.json')['status']=='passed'
    with zipfile.ZipFile(kit) as zipped:
        inventory=json.loads(zipped.read('KIT-FILES.json'));assert len(zipped.namelist())==75
        for row in inventory['files']:
            data=zipped.read(row['path']);assert len(data)==row['bytes'] and hashlib.sha256(data).hexdigest()==row['sha256']
        for row in manifest['files']:assert zipped.read(row['path'])==(ROOT/row['path']).read_bytes()
    checks['r4_kit_pinned_and_independently_exercised']=True
    for old,digest in [('agent-editor-kit-community-unified-skill-r3.zip','db1bdcc024963aa7992caffa12ac849be0d627c9cf7f283910bc3ffb0625555d'),
                       ('agent-editor-kit-unified-skill-r1.zip','0650e83b2ac23004a631347ab2ea54ec819e338faa2d191c9e307da91ae4d950')]:
        assert sha(ROOT/'docs/skills'/old)==digest
    old_app=ROOT/'local/agent-ffmpeg/v0.1.0-alpha.4-local.2/agent-editor-kit-v0.1.0-alpha.4-local.2-cp313-win_amd64.zip'
    assert sha(old_app)=='4e406058e082d1c9d778e9c4665f307d5027f17542c6fabfbc9d8d72ac0a2333'
    checks['historical_bundles_unchanged']=True
    for name in ('demo-development-r1','demo-installed-r1-workflow'):
        record=load(name+'/verification.json')
        assert record['frames']==90 and record['full_video_decode'] and record['package_roundtrip_decoded_pixels_equal']
        for row in record['files']:assert sha(ROOT/row['path'])==row['sha256']
    assert load('installed-demo-audio.json')['silent_pcm']
    assert load('agent-static-review.json')['human_continuous_playback'] is False
    checks['media_hashes_roundtrip_silent_pcm_static_review']=True
    paths=[ROOT/name for name in ('README.md','README.en.md','README.zh-TW.md','docs/README.md',
        'docs/product/GOAL_GAPS_20261025.md','docs/product/IMPLEMENTATION_PLAN_20261025.md',
        'docs/product/SEMANTIC_RETRIEVAL.md','docs/product/COMMUNITY_LOCAL_DELIVERY.md','docs/product/CASES.md',
        'docs/validation/离线语义检索实测_2026-10-25.md','docs/specs/离线语义素材检索契约_v0.1_2026-10-25.md')]
    for stem in ('CAPABILITIES','SKILLS'):paths+=list((ROOT/'docs/product').glob(stem+'*.md'))
    paths+=list((ROOT/'skills/agent-ffmpeg-local-editor').rglob('*.md'))
    broken=[];links=0;readmes=[];commands=[]
    for path in paths:
        text=path.read_text('utf8')
        if path.parent==ROOT:
            ids={c:re.findall(r'^\| ('+c+r'\d\d)(?: /| \|)',text,re.M) for c in 'FSKR'}
            assert {c:len(v) for c,v in ids.items()}==dict(F=50,S=18,K=17,R=48),(path,ids)
            assert all(len(v)==len(set(v)) for v in ids.values())
            old=git('show','HEAD:'+path.name).decode('utf8')
            rows=re.findall(r'^\| R(?:0[1-9]|[1-3][0-9]|4[0-4]) \|.*$',old,re.M)
            assert len(rows)==44 and all(row in text for row in rows)
            commands.append(re.findall(r'```powershell\n(.*?)```',text,re.S))
            assert len(text)>35000 and len(text.encode())>=len(old.encode())
            readmes.append(dict(path=path.name,ids={c:len(v) for c,v in ids.items()},historical_R01_R44_unchanged=True,sha256=sha(path)))
        plain=re.sub(r'```[\s\S]*?```','',text);plain=re.sub(r'`[^`\n]+`','',plain)
        for target in re.findall(r'!?\[[^\]]*\]\(([^\n)]+)\)',plain):
            if re.match(r'^[a-zA-Z][a-zA-Z0-9+.-]*:',target) or target.startswith('#'):continue
            destination=(path.parent/unquote(target.split('#')[0].strip('<>'))).resolve()
            if not destination.exists():broken.append([str(path.relative_to(ROOT)),target])
            links+=1
    assert not broken,broken
    assert commands[0]==commands[1]==commands[2],'README command blocks differ by language'
    gaps=(ROOT/'docs/product/GOAL_GAPS_20261025.md').read_text('utf8')
    assert re.findall(r'^\| (G\d\d) \|',gaps,re.M)==['G'+str(i).zfill(2) for i in range(1,39)]
    checks['docs']=dict(readmes=readmes,local_links=links,broken=broken,powershell_blocks_identical=True,gap_groups=38)
    helpers=list((ROOT/'scripts').glob('*semantic*20261025.py'))
    for path in helpers:ast.parse(path.read_bytes())
    checks['helper_syntax']=len(helpers)
    raw=list((ROOT/'docs/assets/semantic-20261025-r1').rglob('*'))+list(BASE.rglob('*'))+list((ROOT/'sources/semantic-20261025').rglob('*'))
    raw=[p for p in raw if p.is_file()]
    assert max(p.stat().st_size for p in raw)<100_000_000
    checks['new_raw_files']=dict(count=len(raw),bytes=sum(p.stat().st_size for p in raw),maximum_bytes=max(p.stat().st_size for p in raw))
    if args.staged:
        index={}
        for item in git('ls-files','--stage','-z').split(b'\0'):
            if item:
                metadata,name=item.split(b'\t',1);index[name.decode('utf8')]=metadata.split()[1].decode()
        exact=raw+[ROOT/row['path'] for row in manifest['files']]+[ROOT/'product/src/ai_ad_editor'/r['path'] for r in install['python_source_files']]
        for path in exact:
            relative=path.relative_to(ROOT).as_posix()
            if relative==args.output.resolve().relative_to(ROOT).as_posix():continue
            data=path.read_bytes();blob=hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()
            assert index.get(relative)==blob,'Staged bytes differ: '+relative
        checks['staged_exact_raw_installed_and_skill_files']=len(exact)
    result=dict(status='passed',checks=checks,created_at_utc=datetime.now(timezone.utc).isoformat(),generator_sha256=sha(Path(__file__)))
    save(args.output,result)
    print(json.dumps(dict(status='passed',checks=len(checks),links=links,new_raw_files=len(raw),staged=args.staged)),flush=True)


if __name__=='__main__':main()
