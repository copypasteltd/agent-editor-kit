"""Audit concrete native text delivery without changing target closure conditions."""
import argparse,hashlib,json,re,subprocess,urllib.request,zipfile
from pathlib import Path
from urllib.parse import unquote

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/validation/evidence/float-text-20261026-r1'
INSTALL=ROOT/'local/agent-ffmpeg/v0.1.0-alpha.4-local.20/final-r2/installed'
BASELINE='15c8561d9bd2a1536f34ee79d6cd035db8351335'
GIT='C:/Users/carzy/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/git/cmd/git.exe'

def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def load(p):return json.loads(Path(p).read_bytes())
def git(*a):return subprocess.check_output([GIT,'--no-optional-locks','-c','core.fsmonitor=false','-c','gc.auto=0','-c','maintenance.auto=false',*a],cwd=ROOT)
def rows(s,p):return {m[1]:m[0] for m in re.finditer(r'^\| ('+p+r'\d{2,3})\s*\|.*$',s,re.M)}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--run',required=True);a=ap.parse_args();assert re.fullmatch('r[1-9][0-9]*',a.run)
    out=BASE/('final-delivery-'+a.run);out.mkdir(exist_ok=False)
    (out/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    report={'status':'running','virtualization':False,'browser_tabs_opened':0,'goal_closed':False}
    def save(name,v):(out/name).write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    save('verification.json',report)
    try:
        assert git('rev-parse','HEAD').decode().strip()==BASELINE
        assert git('branch','--show-current').decode().strip()=='main'
        git('diff','--check')
        for a in [('remote','get-url','origin'),('remote','get-url','--push','origin')]:
            assert git(*a).decode().strip()=='git@github.com:copypasteltd/agent-editor-kit.git'
        assert not git('diff','--name-only','--','sources/')
        files={p.name:sha(p) for p in (ROOT/'product/src/ai_ad_editor').glob('*.py')}
        save('product-files.json',files)
        assert len(files)==213 and files=={p.name:sha(p) for p in (INSTALL/'site/ai_ad_editor').glob('*.py')}
        install=load(BASE/'installation-final-r2/verification.json')
        assert install['source_and_installed_equal'] and install['archive_sha256']==sha(install['archive'])
        assert {r['path']:r['sha256'] for r in install['source_files']}==files
        groups={}
        for g in ('text','float','audio','render','legacy','text-legacy'):
            r=load(BASE/(g+'-installed-final-r1')/'verification.json')
            assert r['status']=='passed' and r['skipped']==0 and r['frozen_equal'] and r['product_files']==files
            assert Path(r['installed']).resolve()==INSTALL.resolve()
            groups[g]=r['tests']
        assert groups['text']==19 and groups['float']==98 and groups['audio']==64 and groups['render']==44 and groups['legacy']==191
        manifest=load(ROOT/'agent-ffmpeg-local-install-manifest.json')
        assert manifest['release']=='v0.1.0-alpha.4-local.20' and manifest['cli_version']=='0.1.22'
        assert manifest['skill_count']==1 and manifest['module_count']==17 and len(manifest['files'])==71
        for r in manifest['files']:assert sha(ROOT/r['path'])==r['sha256'] and (ROOT/r['path']).stat().st_size==r['bytes']
        entry=Path('C:/Users/carzy/.codex/skills/agent-ffmpeg-local-editor')
        assert entry.resolve()==(ROOT/'skills/agent-ffmpeg-local-editor').resolve()
        runtime=load(ROOT/'local/agent-ffmpeg/runtime.json');assert Path(runtime['installed_directory']).resolve()==INSTALL.resolve()
        activation=load(BASE/'activation-final-r1/activation-and-registration.json')
        assert activation['status']=='passed' and len(activation['activation']['verified_packs'])==4
        case=load(BASE/'case-r3/verification.json')
        assert case['status']=='passed' and case['registered_skill'] and case['actual_frames']==72 and case['max_pcm_error']<=3e-7
        assert all(c['ok'] for c in case['checks'])
        for c in case['calls']:
            assert sha(BASE/'case-r3'/(c['name']+'.stdout.log'))==c['stdout_sha256']
            assert sha(BASE/'case-r3'/(c['name']+'.stderr.log'))==c['stderr_sha256']
        for r in case['public_files']:assert sha(ROOT/r['path'])==r['sha256'] and (ROOT/r['path']).stat().st_size==r['bytes']
        text=load(BASE/'case-r3/native-text-receipt.json')
        assert len(text['plans'])==4 and text['native_snapshots']>30 and text['coverage_conversion']['max_code_error']==0
        package=load(BASE/'package-r1/verification.json')
        assert package['status']=='passed' and package['font_license_preserved'] and len(package['checked_frames'])==3
        assert all(r['equal'] for r in package['checked_frames'])
        observation=load(BASE/'case-r3/visual-observation.json');assert not observation['continuous_playback'] and not observation['human_listening']
        kit=load(ROOT/'docs/skills/community-unified-skill-package-0.1.22-r23.json')
        assert kit['files']==100 and kit['skill_count']==1 and kit['module_count']==17
        archive=ROOT/kit['archive'];assert archive.stat().st_size==kit['bytes'] and sha(archive)==kit['sha256']
        with zipfile.ZipFile(archive) as z:
            assert len(z.namelist())==len(set(z.namelist()))==100
            assert sum(Path(n).name=='SKILL.md' for n in z.namelist())==1
            inventory=json.loads(z.read('KIT-FILES.json'))
            for r in inventory['files']:
                data=z.read(r['path']);assert hashlib.sha256(data).hexdigest()==r['sha256'] and len(data)==r['bytes']
                if r['path'].startswith('skills/'):assert data==(ROOT/r['path']).read_bytes()
        proof=load(BASE/'kit-r1/verification.json');assert proof['status']=='passed' and not proof['real_discovery_changed']
        caps=load(ROOT/'docs/product/float-text-capabilities-cli-0.1.22.json')['data']['capabilities']
        assert len(caps)==75 and caps['subtitles']['float32_native']['protocol']=='native-glyph-linear-float32-paint-v1'
        for name in ('README.md','README.zh-TW.md','README.en.md'):
            old=git('show',BASELINE+':'+name).decode('utf-8-sig');text=(ROOT/name).read_text('utf-8-sig')
            historic=rows(old,'R');current=rows(text,'R');assert len(historic)==154 and len(current)==162
            assert all(current[k]==v for k,v in historic.items())
            assert len(rows(text,'F'))==56 and len(rows(text,'S'))==20 and len(rows(text,'K'))==17
        for suffix in ('','.zh-TW','.en'):
            m=(ROOT/('docs/product/CAPABILITIES'+suffix+'.md')).read_text('utf-8-sig')
            assert len(rows(m,'F'))==56 and len(rows(m,'S'))==20
            for key,value in caps.items():
                match=re.search(r'^### `'+re.escape(key)+r'`\s*\n\s*```json\n(.*?)\n```',m,re.M|re.S)
                assert match and json.loads(match[1])==value,key
        name='docs/product/GOAL_GAPS_20261025.md';old=rows(git('show',BASELINE+':'+name).decode('utf-8-sig'),'G');new=rows((ROOT/name).read_text('utf-8-sig'),'G')
        assert len(new)==38 and all(new[k].split('|')[5]==v.split('|')[5] for k,v in old.items())
        guide_paths=['README.md','README.zh-TW.md','README.en.md','docs/product/FLOAT_TEXT.md',
            'docs/releases/CLI_0.1.22_LOCAL.md','docs/product/CASES.md','docs/product/COMMUNITY_LOCAL_DELIVERY.md',
            'docs/validation/Float32文字字幕实测_2026-10-26.md']
        missing=[]
        for name in guide_paths:
            path=ROOT/name
            for target in re.findall(r'!?\[[^\]]*\]\(([^\n)]+)\)',path.read_text('utf-8-sig')):
                if re.match(r'^[a-z]+:',target,re.I) or target.startswith('#'):continue
                local=(path.parent/unquote(target.split('#')[0])).resolve()
                if not local.exists():missing.append([name,target])
        assert not missing,missing
        request=urllib.request.Request('https://api.github.com/repos/copypasteltd/agent-editor-kit/releases?per_page=10',headers={'User-Agent':'agent-editor-kit-delivery-audit'})
        with urllib.request.urlopen(request,timeout=30) as response:
            releases=json.load(response);assert response.status==200
        save('public-releases.json',releases);assert releases and releases[0]['tag_name']=='v0.1.0-alpha.3'
        changed=set(git('diff','--name-only','-z').decode('utf8').split('\0'))|set(git('ls-files','--others','--exclude-standard','-z').decode('utf8').split('\0'))
        inventory=[]
        for name in sorted(changed):
            if not name or (ROOT/name).is_relative_to(out):continue
            path=ROOT/name;assert path.is_file() and path.stat().st_size<95*1024**2,name
            inventory.append({'path':name,'sha256':sha(path),'bytes':path.stat().st_size})
        report.update(status='passed',product_files=213,skill_files=71,registered_skills=1,modules=17,
            test_groups=groups,readme_history_rows_preserved=154,readme_rows=162,functions=56,services=20,
            capability_fields=75,goal_closures_preserved=38,public_release='v0.1.0-alpha.3',
            archive_sha256=install['archive_sha256'],kit_sha256=kit['sha256'],goal_closed=False,files=inventory)
        save('verification.json',report);print(json.dumps({k:v for k,v in report.items() if k!='files'}),flush=True)
    except BaseException as exc:
        report.update(status='failed',error=repr(exc));save('verification.json',report);raise

if __name__=='__main__':main()
