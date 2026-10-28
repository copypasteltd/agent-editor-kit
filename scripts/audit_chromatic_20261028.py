"""Audit the actual native-white delivery, staged bytes and ordinary main push."""
from pathlib import Path
import argparse,hashlib,json,re,subprocess,zipfile
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'docs/validation/evidence/native-chromatic-20261028-r1'
BASELINE='9ba52a7dee4d3f1d992c3c8a1cd137973ca2b4e0'
GIT='C:/Users/carzy/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/git/cmd/git.exe'
def git(*args):return subprocess.check_output([GIT,'--no-optional-locks','-c','core.fsmonitor=false','-c','gc.auto=0','-c','maintenance.auto=false',*args],cwd=ROOT)
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def load(p):return json.loads(Path(p).read_bytes())
def rows(s,p):return {m[1]:m[0] for m in re.finditer(r'^\| ('+p+r'\d+)\s*\|.*$',s,re.M)}
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--run',required=True);ap.add_argument('--staged',action='store_true');ap.add_argument('--postpush',action='store_true');a=ap.parse_args();assert a.run.replace('-','').isalnum()
    out=(ROOT/'local/agent-ffmpeg'/('native-chromatic-postpush-'+a.run) if a.postpush else BASE/(('staged-' if a.staged else 'final-')+a.run))
    out.mkdir(parents=True,exist_ok=False);(out/'executed-auditor.py').write_bytes(Path(__file__).read_bytes())
    report=dict(status='running',at_utc=datetime.now(timezone.utc).isoformat(),whole_goal_complete=False)
    try:
        install=load(BASE/'installation-final-r1/verification.json');installed=Path(install['installed'])
        assert install['cli_version']=='0.1.45' and install['status']=='installed-and-byte-verified'
        source=ROOT/'product/src/ai_ad_editor';pins={p.name:sha(p) for p in source.glob('*.py')}
        assert len(pins)==268 and pins=={p.name:sha(p) for p in (installed/'site/ai_ad_editor').glob('*.py')}
        test_counts={}
        for path in ('source-r3','installed-r1','installed-compat-r1'):
            test=load(BASE/path/'verification.json');assert test['status']=='passed' and test['failures']==test['errors']==test['skipped']==0
            assert test['product_files']==pins;test_counts[path]=test['tests']
            for name,digest in test['test_files'].items():assert sha(ROOT/'product/tests'/(name+'.py'))==digest
        assert test_counts['source-r3']==test_counts['installed-r1']==20 and test_counts['installed-compat-r1']>100
        assert sha(install['archive'])==install['archive_sha256'] and Path(install['archive']).stat().st_size==install['archive_bytes']
        assert 'sha256:'+sha(ROOT/'local/agent-ffmpeg/v0.1.0-alpha.4-local.43/unpacked-r1/manifest.json')==install['manifest_sha256']
        assert (source/'agent-project.schema.json').read_bytes()==(ROOT/'docs/specs/agent-project.schema.json').read_bytes()==(installed/'site/ai_ad_editor/agent-project.schema.json').read_bytes()
        case=load(BASE/'case-r3/verification.json');assert case['status']=='passed' and all(c['ok'] for c in case['checks'])
        assert case['independent_surface_pixels']==230400 and case['maximum_surface_error']<1.3e-7
        assert case['maximum_patch_luma_code_error']<1.6 and case['PCM_scalar_samples']==384000 and case['GPU_glow_calls_per_render']==48
        oracle=load(BASE/'case-r3/independent-every-frame-patches.json');assert oracle['status']=='passed' and oracle['comparisons']==384 and oracle['maximum_luma_code_error']<1.6
        assert not case['ICC_profile_parsed'] and not case['full_ACES_transform'] and not case['HDR_monitor_accepted']
        work=Path(case['project']).parent
        for x,y in [('original-all-video.bin','replayed-all-video.bin'),('original-all-PCM.bin','replayed-all-PCM.bin')]:assert sha(work/x)==sha(work/y)
        actual=load(BASE/'case-r3/edited.stdout.json')['data'];pixel=actual['delivery']['pixel_pipeline']
        assert pixel['working_signal']==dict(primaries='aces-ap1',transfer='linear',white_xy=[.32168,.33767])
        assert pixel['transport']['clipped_RGB_components']>0
        gpu=pixel['projection_acceleration'];assert gpu['operations']['glow']==48 and gpu['worker_closed'] and gpu['shared_handles_closed'] and gpu['control']['threads_closed'] and gpu['control']['streams_closed']
        for path in ('source-r1','case-r1','case-r2'):assert load(BASE/path/'verification.json')['status']=='failed'
        public=ROOT/'docs/assets/native-chromatic-20261028-r3';inventory=load(public/'media-manifest.json')
        assert {p.name for p in public.iterdir() if p.is_file() and p.name!='media-manifest.json'}=={r['path'] for r in inventory['files']}
        for row in inventory['files']:assert sha(public/row['path'])==row['sha256'] and (public/row['path']).stat().st_size==row['bytes']
        review=load(BASE/'static-review.json');assert review['status']=='static-image-inspected' and sha(public/'comparison.png')==review['sha256']
        namespace=load(ROOT/'agent-ffmpeg-local-install-manifest.json');assert namespace['cli_version']=='0.1.45' and len(namespace['files'])==84 and len(namespace['skills'])==1
        for row in namespace['files']:assert sha(ROOT/row['path'])==row['sha256'] and (ROOT/row['path']).stat().st_size==row['bytes']
        assert Path('C:/Users/carzy/.codex/skills/agent-ffmpeg-local-editor').resolve()==(ROOT/'skills/agent-ffmpeg-local-editor').resolve()
        activation=load(BASE/'activation-final-r1/activation-and-registration.json');reg=activation['registration']
        assert activation['status']=='passed' and reg['namespace_manifest_sha256']==sha(ROOT/'agent-ffmpeg-local-install-manifest.json') and reg['launcher_preflight_verified'] and reg['registered_cli_version']=='0.1.45'
        fresh=load(BASE/'kit-r1/verification.json');kit=load(ROOT/'docs/skills/community-unified-skill-package-0.1.45-r46.json')
        assert fresh['status']=='passed' and fresh['files']==136 and fresh['skill_files']==84 and not fresh['real_discovery_changed']
        assert sha(ROOT/kit['archive'])==kit['sha256']
        with zipfile.ZipFile(ROOT/kit['archive']) as z:
            assert len(z.namelist())==136 and 'docs/product/CHROMATIC_ADAPTATION.md' in z.namelist()
            item=json.loads(z.read('KIT-FILES.json'))
            for row in item['files']:assert hashlib.sha256(z.read(row['path'])).hexdigest()==row['sha256']
        caps=load(ROOT/'docs/product/chromatic-capabilities-cli-0.1.45.json')['data']['capabilities'];assert len(caps)==84
        documents=[]
        for suffix in ('','.zh-TW','.en'):
            name='README'+suffix+'.md';s=(ROOT/name).read_text('utf8');old=rows(git('show',BASELINE+':'+name).decode('utf8'),'R')
            assert len(old)==303 and len(rows(s,'R'))==309 and all(rows(s,'R')[k]==v for k,v in old.items())
            assert len(rows(s,'F'))==71 and len(rows(s,'S'))==26 and len(rows(s,'K'))==17
            assert 'CLI0.1.45 / alpha.4-local.43 / r46 kit' in s and 'local.43/final-r1/installed' in s;documents.append(ROOT/name)
            manual=ROOT/('docs/product/CAPABILITIES'+suffix+'.md');m=manual.read_text('utf8');documents.append(manual)
            assert len(rows(m,'F'))==71 and len(rows(m,'S'))==26
            for key,value in caps.items():
                section=re.search(r'^### `'+re.escape(key)+r'`\s*\n\n```json\n(.*?)\n```',m,re.M|re.S);assert section and json.loads(section[1])==value,key
            documents.extend([ROOT/('docs/product/SKILLS'+suffix+'.md'),ROOT/('docs/skills/UNIFIED_SKILL'+suffix+'.md')])
        p='docs/product/GOAL_GAPS_20261025.md';old=rows(git('show',BASELINE+':'+p).decode('utf8'),'G');now=rows((ROOT/p).read_text('utf8'),'G')
        assert len(old)==len(now)==38 and all(now[k].split('|')[5]==v.split('|')[5] for k,v in old.items())
        documents.extend(ROOT/p for p in ['docs/README.md','docs/product/CHROMATIC_ADAPTATION.md','docs/product/HDR_DISPLAY.md','docs/product/GOAL_GAPS_20261025.md','docs/product/CASES.md','docs/product/COMMUNITY_LOCAL_DELIVERY.md','docs/releases/CLI_0.1.45_LOCAL.md','docs/validation/明确白点色适应实测_2026-10-28.md'])
        links=[]
        for p in documents:
            for m in re.finditer(r'!?\[[^\]]*\]\(([^\n)]+)\)',p.read_text('utf8')):
                target=m[1].split('#')[0]
                if not target or re.match(r'^[a-zA-Z]+:',target):continue
                dest=(p.parent/target).resolve();assert dest.exists(),(p,target);links.append(dict(document=str(p.relative_to(ROOT)),target=m[1]))
        changes=[v.decode('utf8') for v in git('diff','--name-only','-z',BASELINE).split(b'\0') if v]
        if not a.postpush:changes+=[v.decode('utf8') for v in git('ls-files','--others','--exclude-standard','-z').split(b'\0') if v]
        checked=[]
        for name in sorted(set(changes)):
            path=ROOT/name;assert path.is_file(),name
            if path.resolve().is_relative_to(out.resolve()):continue
            if a.staged or a.postpush:assert hashlib.sha256(git('show',('HEAD:' if a.postpush else ':')+name)).hexdigest()==sha(path),name
            checked.append(dict(path=name,bytes=path.stat().st_size,sha256=sha(path)))
        assert git('branch','--show-current').decode().strip()=='main'
        assert git('remote','get-url','--push','origin').decode().strip()=='git@github.com:copypasteltd/agent-editor-kit.git'
        if a.postpush:
            head=git('rev-parse','HEAD').decode().strip();origin=git('rev-parse','origin/main').decode().strip();advertised=git('ls-remote','origin','refs/heads/main').decode().split()[0]
            assert head==origin==advertised and not git('status','--porcelain','--untracked-files=normal').strip();report.update(HEAD=head,origin_main=origin,advertised_main=advertised,clean=True)
        report.update(status='passed',product_files=268,capabilities=84,skill_files=84,public_skills=1,internal_modules=17,
            tests=test_counts,F=71,S=26,K=17,R=309,prior_R_retained=303,G_closure_cells_retained=38,
            local_links_checked=len(links),files_checked=len(checked),files=checked,installed=str(installed),staged=a.staged,postpush=a.postpush)
        (out/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
        print(json.dumps({k:v for k,v in report.items() if k!='files'},ensure_ascii=False),flush=True)
    except BaseException as e:
        report.update(status='failed',error=repr(e));(out/'verification.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8',newline='\n');raise
if __name__=='__main__':main()
