"""Audit actual installed relocation evidence, documentation, Skill and release state."""
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
from urllib.parse import unquote
import urllib.request
import zipfile

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/validation/evidence/motion-pack-20261025-r1'
BASELINE='c8eab913b88c59632d910eef08c73e534dab419a'
GIT='C:/Users/carzy/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/git/cmd/git.exe'


def sha(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def load(path):return json.loads(path.read_bytes())


def git(*args):
    return subprocess.check_output([GIT,'--no-optional-locks','-c','core.fsmonitor=false','-c','gc.auto=0',
        '-c','maintenance.auto=false',*args],cwd=ROOT,timeout=120)


def rows(text,prefix):return {m[1]:m[0] for m in re.finditer(r'^\| ('+prefix+r'\d{2,3})\s*\|.*$',text,re.M)}


def main():
    out=BASE/'final-delivery-r1';out.mkdir(exist_ok=False)
    (out/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    def save(name,value):(out/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    report=dict(status='running',started_at_utc=datetime.now(timezone.utc).isoformat(),native_windows=True,
        virtualization=False,browser_ui=False,new_model_forwards_in_audit=0,new_renders_in_audit=0,
        independent_agent_benchmark=False,human_quality_acceptance=False)
    save('verification.json',report)
    try:
        assert git('rev-parse','HEAD').decode().strip()==BASELINE
        assert git('branch','--show-current').decode().strip()=='main'
        assert git('remote','get-url','origin').decode().strip()=='git@github.com:copypasteltd/agent-editor-kit.git'
        runtime=load(ROOT/'local/agent-ffmpeg/runtime.json');installed=Path(runtime['installed_directory'])
        installation=load(BASE/'installation-r1/verification.json')
        assert installation['status']=='installed-and-byte-verified' and runtime['release']=='v0.1.0-alpha.4-local.14'
        assert installed.resolve()==Path(installation['installed']).resolve()
        assert sha(Path(installation['archive']))==installation['archive_sha256']
        assert Path(installation['archive']).stat().st_size==installation['archive_bytes']
        assert load(installed/'receipt.json')['manifest_sha256']==runtime['manifest_sha256']==installation['manifest_sha256']
        source={p.name:sha(p) for p in (ROOT/'product/src/ai_ad_editor').glob('*.py')}
        assert len(source)==208 and source=={p.name:sha(p) for p in (installed/'site/ai_ad_editor').glob('*.py')}
        manifest=load(ROOT/'agent-ffmpeg-local-install-manifest.json')
        assert manifest['cli_version']=='0.1.16' and manifest['skill_count']==1 and manifest['module_count']==17
        assert manifest['manifest_sha256']==runtime['manifest_sha256'] and len(manifest['files'])==68
        for row in manifest['files']:assert sha(ROOT/row['path'])==row['sha256'] and (ROOT/row['path']).stat().st_size==row['bytes']
        discovery=Path('C:/Users/carzy/.codex/skills/agent-ffmpeg-local-editor')
        assert discovery.resolve()==(ROOT/'skills/agent-ffmpeg-local-editor').resolve()
        kit=load(ROOT/'docs/skills/community-unified-skill-package-0.1.16.json')
        assert sha(ROOT/kit['archive'])==kit['sha256'] and kit['files']==92
        with zipfile.ZipFile(ROOT/kit['archive']) as archive:
            inventory=json.loads(archive.read('KIT-FILES.json'))
            assert inventory['cli_version']=='0.1.16' and inventory['skill_count']==1 and inventory['module_count']==17
            assert len(archive.namelist())==len(set(archive.namelist()))==92
            for row in inventory['files']:
                data=archive.read(row['path']);assert len(data)==row['bytes'] and hashlib.sha256(data).hexdigest()==row['sha256']
                if row['path'].startswith('skills/'):assert data==(ROOT/row['path']).read_bytes()
        proof=load(BASE/'kit-r1/verification.json')
        assert proof['status']=='passed' and proof['process_calls']==8 and proof['skill_files']==68
        assert proof['kit_sha256']==kit['sha256'] and not proof['real_discovery_changed']
        validator=subprocess.run(['C:/Python313/python.exe','-E','-B','-u','-X','utf8',
            'C:/Users/carzy/.codex/skills/.system/skill-creator/scripts/quick_validate.py',str(discovery)],
            cwd=ROOT,capture_output=True,timeout=60,creationflags=subprocess.CREATE_NO_WINDOW)
        (out/'skill-validation.stdout.txt').write_bytes(validator.stdout);(out/'skill-validation.stderr.txt').write_bytes(validator.stderr)
        assert validator.returncode==0 and b'Skill is valid!' in validator.stdout
        responses={};calls=[]
        for parameters in (['version'],['doctor'],['capabilities'],['schema','show'],['gpu','inspect'],['model-pack','list']):
            name='-'.join(parameters);argv=['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',str(discovery/'scripts/run.ps1'),*parameters]
            process=subprocess.run(argv,cwd=ROOT,capture_output=True,timeout=180,creationflags=subprocess.CREATE_NO_WINDOW)
            stdout,stderr=out/(name+'.stdout.json'),out/(name+'.stderr.txt');stdout.write_bytes(process.stdout);stderr.write_bytes(process.stderr)
            value=json.loads(process.stdout.decode('utf-8-sig'));assert process.returncode==0 and value['ok'];responses[name]=value
            calls.append(dict(argv=argv,exit_code=process.returncode,stdout_sha256=sha(stdout),stderr_sha256=sha(stderr)));save('calls.json',calls)
            print(json.dumps(dict(id=name,status='passed')),flush=True)
        assert responses['version']['data']['cli_version']=='0.1.16'
        capabilities=responses['capabilities']['data']['capabilities']
        assert capabilities==load(ROOT/'docs/product/motion-pack-capabilities-cli-0.1.16.json')['data']['capabilities']
        counts=dict(Counter(row['status'] for row in capabilities.values()))
        assert len(capabilities)==75 and counts==dict(implemented=20,implemented_with_limits=47,local_adapter_only=7,degraded=1)
        for run,count in (('development-r2',20),('native-development-r2',5),('installed-contracts-r1',20),('installed-native-r1',5),('installed-cli-r1',122)):
            proof=load(BASE/'tests'/run/'verification.json')
            assert proof['status']=='passed' and proof['result']==dict(methods=count,skipped=0,failures=0,errors=0,success=True)
            assert proof['frozen_equal'] and proof['installed_frozen_equal'] and load(BASE/'tests'/run/'product-files.json')==source
        for phase in ('setup-continue-r1','render-r1','reuse-r1','skill-r1'):
            assert load(BASE/phase/'verification.json')['status']=='passed',phase
        assert load(BASE/'tests/development-r1/verification.json')['status']=='failed'
        assert load(BASE/'setup-r1/verification.json')['status']=='failed'
        reuse=load(BASE/'reuse-r1/verification.json')
        for flag in ('dry_run_unchanged','captured_reuse_pixels_equal','package_project_json_equal','asset_bytes_equal',
                     'original_project_unavailable','external_recipes_unavailable_during_render','imported_pixels_equal'):
            assert reuse[flag],flag
        assert reuse['compared_frames']==120 and load(BASE/'skill-r1/verification.json')['skill_pixels_equal']
        workspace=ROOT/'workspace/motion-pack-20261025-installed-r1'
        assert not (workspace/'原工程').exists()
        assert sha(workspace/'editable-motion.aevpkg.zip')==reuse['package_sha256']
        media=load(ROOT/'docs/assets/motion-pack-20261025-r1/media-manifest.json')
        for row in media['files']:
            path=ROOT/row['path'];assert sha(path)==row['sha256'] and path.stat().st_size==row['bytes']
        old=ROOT/'local/agent-ffmpeg/v0.1.0-alpha.4-local.13/final-r3/installed/site/ai_ad_editor'
        contract=(ROOT/'product/src/ai_ad_editor/semantic_contract.py').read_text('utf8').split('def implementation_files()',1)[1].split('def adapter_fingerprint',1)[0]
        semantic_names=re.findall(r"'([^']+\.py)'",contract);assert len(semantic_names)==19
        unchanged_semantic=[dict(name=name,sha256=sha(old/name)) for name in semantic_names]
        assert all(row['sha256']==source[row['name']] for row in unchanged_semantic)
        save('unchanged-semantic-modules.json',unchanged_semantic)
        files=[ROOT/'docs/product/GOAL_GAPS_20261025.md',ROOT/'docs/product/IMPLEMENTATION_PLAN_20261025.md']
        old=rows(git('show',BASELINE+':docs/product/GOAL_GAPS_20261025.md').decode('utf-8-sig'),'G');current=rows(files[0].read_text('utf8'),'G')
        assert len(old)==len(current)==38 and all(value.split('|')[5]==current[key].split('|')[5] for key,value in old.items())
        for name in ('README.md','README.zh-TW.md','README.en.md'):
            path=ROOT/name;text=path.read_text('utf8');old=rows(git('show',BASELINE+':'+name).decode('utf-8-sig'),'R');current=rows(text,'R')
            assert len(old)==117 and len(current)==124 and all(current[key]==value for key,value in old.items())
            for prefix,count in (('F',54),('S',20),('K',17)):assert len(rows(text,prefix))==count
            files.append(path)
        files+=[ROOT/name for name in ('docs/README.md','docs/product/COMMUNITY_LOCAL_DELIVERY.md','docs/product/MOTION_PACKS.md',
            'docs/product/CASES.md','docs/validation/可复用运镜包实测_2026-10-25.md')]
        files+=[ROOT/('docs/product/'+name+suffix+'.md') for name in ('CAPABILITIES','SKILLS') for suffix in ('','.zh-TW','.en')]
        links=0
        for path in files:
            text=path.read_text('utf-8-sig')
            if path.name.startswith('CAPABILITIES'):
                blocks=re.findall(r'^### `([^`]+)`\s*\n+```json\n(.*?)\n```',text,re.M|re.S)
                assert {key:json.loads(value) for key,value in blocks}==capabilities
                assert len(rows(text,'F'))==54 and len(rows(text,'S'))==20
            if path.name.startswith('SKILLS'):assert len(rows(text,'K'))==17
            for match in re.finditer(r'!?\[[^\]]*\]\(([^)]+)\)',text):
                target=match[1].strip().strip('<>')
                if re.match(r'^[a-z][a-z0-9+.-]*:',target,re.I) or target.startswith('#'):continue
                assert (path.parent/unquote(target.split('#',1)[0])).exists(),(path,target)
                links+=1
        request=urllib.request.Request('https://api.github.com/repos/copypasteltd/agent-editor-kit/releases?per_page=10',headers={'User-Agent':'agent-editor-kit-delivery-audit','Accept':'application/vnd.github+json'})
        with urllib.request.urlopen(request,timeout=30) as remote:raw,status=remote.read(4*1024*1024+1),remote.status
        assert status==200 and len(raw)<=4*1024*1024;(out/'github-releases.raw.json').write_bytes(raw)
        latest=max((r for r in json.loads(raw) if not r['draft']),key=lambda r:r['published_at'])['tag_name'];assert latest=='v0.1.0-alpha.3'
        report.update(status='passed',finished_at_utc=datetime.now(timezone.utc).isoformat(),baseline_commit=BASELINE,
            cli_version='0.1.16',installed=str(installed),actual_read_only_cli_calls=6,source_and_installed_files=208,
            skill_files=68,kit_files=92,kit_sha256=kit['sha256'],capability_count=75,capability_status_counts=counts,
            original_goal_closure_conditions_preserved=38,historical_readme_rows_preserved_per_language=117,current_readme_rows_per_language=124,
            local_links_checked=links,public_release=latest,public_api_status=status,preserved_real_failed_phases=2,unchanged_semantic_modules=19,
            files=[dict(path=p.relative_to(ROOT).as_posix(),sha256=sha(p)) for p in files])
        save('verification.json',report);print(json.dumps({k:v for k,v in report.items() if k!='files'},ensure_ascii=False))
    except BaseException as exc:
        report.update(status='failed',error=repr(exc));save('verification.json',report);raise


if __name__=='__main__':main()
