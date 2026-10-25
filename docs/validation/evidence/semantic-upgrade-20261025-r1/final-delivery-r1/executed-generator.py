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
BASE=ROOT/'docs/validation/evidence/semantic-upgrade-20261025-r1'
BASELINE='5bb2555d04bb91364623f8c468b1062bf06007d9'
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
        installation=load(BASE/'installation-r3/verification.json')
        assert installation['status']=='installed-and-byte-verified' and runtime['release']=='v0.1.0-alpha.4-local.13'
        assert installed.resolve()==Path(installation['installed']).resolve()
        assert sha(Path(installation['archive']))==installation['archive_sha256']
        assert Path(installation['archive']).stat().st_size==installation['archive_bytes']
        assert load(installed/'receipt.json')['manifest_sha256']==runtime['manifest_sha256']==installation['manifest_sha256']
        source={p.name:sha(p) for p in (ROOT/'product/src/ai_ad_editor').glob('*.py')}
        assert len(source)==206 and source=={p.name:sha(p) for p in (installed/'site/ai_ad_editor').glob('*.py')}
        manifest=load(ROOT/'agent-ffmpeg-local-install-manifest.json')
        assert manifest['cli_version']=='0.1.15' and manifest['skill_count']==1 and manifest['module_count']==17
        assert manifest['manifest_sha256']==runtime['manifest_sha256'] and len(manifest['files'])==66
        for row in manifest['files']:assert sha(ROOT/row['path'])==row['sha256'] and (ROOT/row['path']).stat().st_size==row['bytes']
        discovery=Path('C:/Users/carzy/.codex/skills/agent-ffmpeg-local-editor')
        assert discovery.resolve()==(ROOT/'skills/agent-ffmpeg-local-editor').resolve()
        kit=load(ROOT/'docs/skills/community-unified-skill-package-0.1.15.json')
        assert sha(ROOT/kit['archive'])==kit['sha256'] and kit['files']==89
        with zipfile.ZipFile(ROOT/kit['archive']) as archive:
            inventory=json.loads(archive.read('KIT-FILES.json'))
            assert inventory['cli_version']=='0.1.15' and inventory['skill_count']==1 and inventory['module_count']==17
            assert len(archive.namelist())==len(set(archive.namelist()))==89
            for row in inventory['files']:
                data=archive.read(row['path']);assert len(data)==row['bytes'] and hashlib.sha256(data).hexdigest()==row['sha256']
                if row['path'].startswith('skills/'):assert data==(ROOT/row['path']).read_bytes()
        proof=load(BASE/'kit-r1/verification.json')
        assert proof['status']=='passed' and proof['process_calls']==8 and proof['skill_files']==66
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
        assert responses['version']['data']['cli_version']=='0.1.15'
        capabilities=responses['capabilities']['data']['capabilities']
        assert capabilities==load(ROOT/'docs/product/semantic-upgrade-capabilities-cli-0.1.15.json')['data']['capabilities']
        counts=dict(Counter(row['status'] for row in capabilities.values()))
        assert len(capabilities)==75 and counts==dict(implemented=20,implemented_with_limits=47,local_adapter_only=7,degraded=1)
        for run,count in (('development-r6',122),('installed-contracts-r3',122),('installed-cli-r3',122)):
            proof=load(BASE/'tests'/run/'verification.json')
            assert proof['status']=='passed' and proof['result']==dict(methods=count,skipped=0,failures=0,errors=0,success=True)
            assert proof['frozen_equal'] and proof['installed_frozen_equal'] and load(BASE/'tests'/run/'product-files.json')==source
        for phase in ('setup-r2','upgrade-r2','roundtrip-r2','faults-r3'):
            assert load(BASE/phase/'verification.json')['status']=='passed',phase
        upgrade=load(BASE/'upgrade-r2/verification.json')
        assert upgrade['new_model_forwards']==0 and upgrade['index_count']==1 and upgrade['profile_count']==2
        for flag in ('old_isolated_installation_unavailable','old_index_refusal_preserved','dry_run_unchanged','original_records_and_assets_preserved','idempotent_replay_unchanged','original_19_implementation_sha_equal'):assert upgrade[flag]
        for phase in ('before-cpu','before-cuda','after-cpu','after-cuda','skill-cuda'):
            proof=load(BASE/(phase+'-r2')/'verification.json')
            assert proof['status']=='passed-with-known-quality-errors' and proof['query_count']==80
            assert proof['known_error_ids']==['hout00zh','hout08zh','q14'] and proof['decisions_and_order_identical'] and proof['maximum_score_error']<=1e-6
        assert load(BASE/'before-cuda-r1/verification.json')['status']=='failed'
        assert load(BASE/'before-cuda-r1/query80.stdout.json')['errors'][0]['code']=='SEMANTIC_RUNTIME_CHANGED'
        workspace=ROOT/'workspace/semantic-upgrade-20261025-installed-r2'
        assert not (workspace/'project').exists() and not (workspace/'isolated-native/installed').exists()
        package=load(BASE/'roundtrip-r2/verification.json')
        assert package['all_asset_bytes_and_semantic_metadata_identical'] and sha(workspace/'upgraded.aevpkg.zip')==package['package_sha256']
        faults=load(BASE/'faults-r3/verification.json');assert len(faults['cases'])==4
        for case in faults['cases']:
            if case['require_integrity_read']:
                assert case['error']['diagnostics']['phase']=='integrity-read' and case['error']['diagnostics']['partial_digest_discarded']
            assert (case['cancel_to_exit_seconds']<=3 if case['cancel_to_exit_seconds'] is not None else case['elapsed_seconds']<=case['wall_gate_seconds'])
        files=[ROOT/'docs/product/GOAL_GAPS_20261025.md',ROOT/'docs/product/IMPLEMENTATION_PLAN_20261025.md']
        old=rows(git('show',BASELINE+':docs/product/GOAL_GAPS_20261025.md').decode('utf-8-sig'),'G');current=rows(files[0].read_text('utf8'),'G')
        assert len(old)==len(current)==38 and all(value.split('|')[5]==current[key].split('|')[5] for key,value in old.items())
        for name in ('README.md','README.zh-TW.md','README.en.md'):
            path=ROOT/name;text=path.read_text('utf8');old=rows(git('show',BASELINE+':'+name).decode('utf-8-sig'),'R');current=rows(text,'R')
            assert len(old)==109 and len(current)==117 and all(current[key]==value for key,value in old.items())
            for prefix,count in (('F',53),('S',20),('K',17)):assert len(rows(text,prefix))==count
            files.append(path)
        files+=[ROOT/name for name in ('docs/README.md','docs/product/COMMUNITY_LOCAL_DELIVERY.md','docs/product/SEMANTIC_RUNTIME_UPGRADE.md',
            'docs/product/SEMANTIC_PROJECT_PACKAGE.md','docs/product/CASES.md','docs/validation/语义运行时升级实测_2026-10-25.md')]
        files+=[ROOT/('docs/product/'+name+suffix+'.md') for name in ('CAPABILITIES','SKILLS') for suffix in ('','.zh-TW','.en')]
        links=0
        for path in files:
            text=path.read_text('utf-8-sig')
            if path.name.startswith('CAPABILITIES'):
                blocks=re.findall(r'^### `([^`]+)`\s*\n+```json\n(.*?)\n```',text,re.M|re.S)
                assert {key:json.loads(value) for key,value in blocks}==capabilities
                assert len(rows(text,'F'))==53 and len(rows(text,'S'))==20
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
            cli_version='0.1.15',installed=str(installed),actual_read_only_cli_calls=6,source_and_installed_files=206,
            skill_files=66,kit_files=89,kit_sha256=kit['sha256'],capability_count=75,capability_status_counts=counts,
            original_goal_closure_conditions_preserved=38,historical_readme_rows_preserved_per_language=109,current_readme_rows_per_language=117,
            local_links_checked=links,public_release=latest,public_api_status=status,preserved_real_failed_phases=1,
            files=[dict(path=p.relative_to(ROOT).as_posix(),sha256=sha(p)) for p in files])
        save('verification.json',report);print(json.dumps({k:v for k,v in report.items() if k!='files'},ensure_ascii=False))
    except BaseException as exc:
        report.update(status='failed',error=repr(exc));save('verification.json',report);raise


if __name__=='__main__':main()
