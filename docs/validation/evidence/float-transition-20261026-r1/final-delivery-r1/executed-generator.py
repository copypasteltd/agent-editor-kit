"""Audit tested/installed bytes, actual registered workflow and complete docs."""
import ast,hashlib,json,re,subprocess,urllib.request,zipfile
from collections import Counter
from datetime import datetime,timezone
from pathlib import Path
from urllib.parse import unquote

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/validation/evidence/float-transition-20261026-r1'
BASELINE='b7b33c9b8319c5dfac814e6aba1076dd18ce5ccd'
GIT='C:/Users/carzy/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/git/cmd/git.exe'
INSTALL=ROOT/'local/agent-ffmpeg/v0.1.0-alpha.4-local.19/final-r1/installed'

def load(path):return json.loads(Path(path).read_bytes())
def sha(path):
    with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def git(*args):return subprocess.check_output([GIT,'--no-optional-locks','-c','core.fsmonitor=false','-c','gc.auto=0','-c','maintenance.auto=false',*args],cwd=ROOT,timeout=180)
def rows(text,prefix):return {m[1]:m[0] for m in re.finditer(r'^\| ('+prefix+r'\d{2,3})\s*\|.*$',text,re.M)}

def main():
    out=BASE/'final-delivery-r1';out.mkdir(exist_ok=False)
    (out/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    report=dict(status='running',at_utc=datetime.now(timezone.utc).isoformat(),native_windows=True,
        virtualization=False,browser_ui=False,new_renders_in_audit=0,new_model_forwards_in_audit=0,
        natural_audiovisual_acceptance=False,full_CapCut_parity=False)
    def save(name,value):(out/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    save('verification.json',report)
    try:
        assert git('rev-parse','HEAD').decode().strip()==BASELINE
        assert git('branch','--show-current').decode().strip()=='main'
        assert git('remote','get-url','origin').decode().strip()=='git@github.com:copypasteltd/agent-editor-kit.git'
        assert git('remote','get-url','--push','origin').decode().strip()=='git@github.com:copypasteltd/agent-editor-kit.git'
        assert not git('diff','--name-only','--','sources/')
        product={p.name:sha(p) for p in (ROOT/'product/src/ai_ad_editor').glob('*.py')}
        assert len(product)==211 and product=={p.name:sha(p) for p in (INSTALL/'site/ai_ad_editor').glob('*.py')}
        install=load(BASE/'installation-final-r1/verification.json')
        assert install['source_and_installed_equal'] and install['archive_sha256']==sha(install['archive'])
        assert {r['path']:r['sha256'] for r in install['source_files']}==product
        tests={}
        for name,count in [('kernel-installed-final-r1',25),('float-installed-r1',98),('audio-final-r1',64),('render-installed-r1',44),('legacy-installed-r1',191)]:
            result=load(BASE/name/'verification.json');assert result['status']=='passed' and result['tests']==count and result['skipped']==0
            assert result['frozen_equal'] and result['product_files']==product
            tests[name]=dict(methods=count,skipped=0,installed=result.get('installed'))
        for name in ('float_transitions_NOTICE.txt','COPYING.LGPLv2.1.txt'):
            assert (ROOT/'product/src/ai_ad_editor'/name).read_bytes()==(INSTALL/'site/ai_ad_editor'/name).read_bytes()
        assert sha(ROOT/'product/src/ai_ad_editor/COPYING.LGPLv2.1.txt')=='246041b6ecf9bc32d718a62c57877c78b5eb397b6467e74ed7ae2626ab189c30'
        assert sha(ROOT/'docs/research/ffmpeg-xfade-n8.0/vf_xfade.c')=='28d6d7c8518328d7eb3ba23c9fcb0b522a4da1947317a5b1b9bcacb4ad67a494'
        xfade=load(BASE/'xfade-r1/verification.json');assert xfade['status']=='passed' and len(xfade['calls'])==57
        assert sum(c['fixed_oracle_passed'] is True for c in xfade['calls'])==53
        assert all(c['max_code_error']<=1 for c in xfade['calls'] if not c['type'].endswith('wind'))
        fourk=load(BASE/'4k-r1/verification.json');assert fourk['status']=='passed' and len(fourk['patterns'])==3
        assert all(c['max_absolute_error']<=2e-7 for c in fourk['patterns'])
        manifest=load(ROOT/'agent-ffmpeg-local-install-manifest.json');assert manifest['release']=='v0.1.0-alpha.4-local.19'
        assert manifest['cli_version']=='0.1.21' and manifest['skill_count']==1 and manifest['module_count']==17 and len(manifest['files'])==70
        for row in manifest['files']:assert sha(ROOT/row['path'])==row['sha256'] and (ROOT/row['path']).stat().st_size==row['bytes']
        entry=Path('C:/Users/carzy/.codex/skills/agent-ffmpeg-local-editor')
        assert entry.resolve()==(ROOT/'skills/agent-ffmpeg-local-editor').resolve()
        runtime=load(ROOT/'local/agent-ffmpeg/runtime.json');assert Path(runtime['installed_directory']).resolve()==INSTALL.resolve()
        activation=load(BASE/'activation-final-r1/activation-and-registration.json');assert activation['status']=='passed'
        assert len(activation['activation']['verified_packs'])==4
        case=load(BASE/'case-r3/verification.json');assert case['status']=='passed' and case['registered_skill']
        assert case['actual_frames']==72 and case['max_pcm_error']<=3e-7 and all(c['ok'] for c in case['checks'])
        for call in case['calls']:
            assert sha(BASE/'case-r3'/(call['name']+'.stdout.log'))==call['stdout_sha256']
            assert sha(BASE/'case-r3'/(call['name']+'.stderr.log'))==call['stderr_sha256']
        for row in case['public_files']:assert sha(ROOT/row['path'])==row['sha256'] and (ROOT/row['path']).stat().st_size==row['bytes']
        assert load(BASE/'case-r3/visual-observation.json')['continuous_playback'] is False
        kit=load(ROOT/'docs/skills/community-unified-skill-package-0.1.21-r22.json')
        archive=ROOT/kit['archive'];assert sha(archive)==kit['sha256'] and archive.stat().st_size==kit['bytes']
        assert kit['files']==98 and kit['skill_count']==1 and kit['module_count']==17
        with zipfile.ZipFile(archive) as z:
            inventory=load_json=z.read('KIT-FILES.json');inventory=json.loads(inventory)
            assert len(z.namelist())==len(set(z.namelist()))==98
            assert sum(Path(n).name=='SKILL.md' for n in z.namelist())==1
            for row in inventory['files']:
                data=z.read(row['path']);assert hashlib.sha256(data).hexdigest()==row['sha256']
                if row['path'].startswith('skills/'):assert data==(ROOT/row['path']).read_bytes()
        kit_proof=load(BASE/'kit-r1/verification.json');assert kit_proof['status']=='passed' and not kit_proof['real_discovery_changed']
        capability=load(ROOT/'docs/product/float-transition-capabilities-cli-0.1.21.json')
        entries=capability['data']['capabilities'];assert len(entries)==75 and len(entries['transitions']['float32_native']['patterns'])==59
        counts=dict(Counter(v['status'] for v in entries.values()))
        assert counts==dict(implemented=20,implemented_with_limits=47,local_adapter_only=7,degraded=1)
        documents=[]
        for suffix,name in [('', 'README.md'),('.zh-TW','README.zh-TW.md'),('.en','README.en.md')]:
            text=(ROOT/name).read_text('utf-8-sig');old=git('show',BASELINE+':'+name).decode('utf-8-sig')
            before=rows(old,'R');after=rows(text,'R');assert len(before)==146 and len(after)==154
            assert all(after[k]==v for k,v in before.items())
            assert len(rows(text,'F'))==55 and len(rows(text,'S'))==20 and len(rows(text,'K'))==17
            manual=ROOT/('docs/product/CAPABILITIES'+suffix+'.md');m=manual.read_text('utf8')
            assert len(rows(m,'F'))==55 and len(rows(m,'S'))==20
            for key,value in entries.items():
                match=re.search(r'^### `'+re.escape(key)+r'`\s*\n\n```json\n(.*?)\n```',m,re.M|re.S)
                assert match and json.loads(match[1])==value,(name,key)
            documents.extend((ROOT/name,manual))
        goal=(ROOT/'docs/product/GOAL_GAPS_20261025.md').read_text('utf8')
        old=git('show',BASELINE+':docs/product/GOAL_GAPS_20261025.md').decode('utf-8-sig')
        assert len(rows(goal,'G'))==38 and all(rows(goal,'G')[k].split('|')[5]==v.split('|')[5] for k,v in rows(old,'G').items())
        documents.extend([ROOT/'docs/product'/n for n in ('FLOAT_TRANSITIONS.md','CASES.md','GOAL_GAPS_20261025.md','IMPLEMENTATION_PLAN_20261025.md','COMMUNITY_LOCAL_DELIVERY.md')])
        documents.extend([ROOT/'docs/releases/CLI_0.1.21_LOCAL.md',ROOT/'docs/validation/Float32转场实测_2026-10-26.md'])
        links=0
        for path in documents:
            for match in re.finditer(r'!?\[[^\]]*\]\(([^)]+)\)',path.read_text('utf-8-sig')):
                target=match[1].strip().strip('<>')
                if re.match(r'^[a-z][a-z0-9+.-]*:',target,re.I) or target.startswith('#'):continue
                assert (path.parent/unquote(target.split('#',1)[0])).exists(),(path,target)
                links+=1
        for path in [ROOT/'product/src/ai_ad_editor'/name for name in product]:ast.parse(path.read_text('utf-8-sig'))
        request=urllib.request.Request('https://api.github.com/repos/copypasteltd/agent-editor-kit/releases/latest',headers={'User-Agent':'agent-editor-kit-native-verification','Accept':'application/vnd.github+json'})
        with urllib.request.urlopen(request,timeout=30) as response:release=json.load(response)
        save('public-release.json',release);assert release['tag_name']=='v0.1.0-alpha.3'
        files=[dict(path=p.relative_to(ROOT).as_posix(),bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(set(documents))]
        report.update(status='passed',product_files=211,skill_files=70,registered_skills=1,internal_modules=17,
            test_groups=tests,patterns=59,independent_native_non_wind_patterns=53,wind_patterns_reported=4,
            readme_functions=55,readme_services=20,readme_rows=154,historical_rows_preserved=146,
            original_goal_closures_preserved=38,capability_count=75,capability_status_counts=counts,
            relative_document_links=links,public_latest_tag=release['tag_name'],kit_files=98,files=files)
        save('product-files.json',product);save('verification.json',report)
        print(json.dumps({k:v for k,v in report.items() if k not in {'files','test_groups'}},ensure_ascii=False),flush=True)
    except BaseException as exc:
        report.update(status='failed',error=repr(exc));save('verification.json',report);raise

if __name__=='__main__':main()
