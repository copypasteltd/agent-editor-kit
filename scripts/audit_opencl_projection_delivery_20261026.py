"""Audit frozen installed GPU delivery, actual evidence, docs and release state."""
from collections import Counter
from datetime import datetime, timezone
import ast
import hashlib
import json
from pathlib import Path
import re
import subprocess
from urllib.parse import unquote
import urllib.request
import zipfile

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/validation/evidence/opencl-projection-20261026-r1'
BASELINE='394b0607e847d27478b460755f3d0965c097a17c'
GIT='C:/Users/carzy/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/git/cmd/git.exe'

def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
def load(path):return json.loads(Path(path).read_bytes())
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
        assert git('branch','--show-current').strip()==b'main'
        assert git('remote','get-url','origin').strip()==b'git@github.com:copypasteltd/agent-editor-kit.git'
        runtime=load(ROOT/'local/agent-ffmpeg/runtime.json');installed=Path(runtime['installed_directory'])
        installation=load(BASE/'installation-final-r2/verification.json')
        assert installation['status']=='installed-and-byte-verified' and runtime['release']=='v0.1.0-alpha.4-local.18'
        assert installed.resolve()==Path(installation['installed']).resolve()
        assert sha(installation['archive'])==installation['archive_sha256']
        assert Path(installation['archive']).stat().st_size==installation['archive_bytes']
        assert load(installed/'receipt.json')['manifest_sha256']==runtime['manifest_sha256']==installation['manifest_sha256']
        source={p.name:sha(p) for p in (ROOT/'product/src/ai_ad_editor').glob('*.py')}
        assert len(source)==209 and source=={p.name:sha(p) for p in (installed/'site/ai_ad_editor').glob('*.py')}
        schema=ROOT/'product/src/ai_ad_editor/agent-project.schema.json'
        assert schema.read_bytes()==(ROOT/'docs/specs/agent-project.schema.json').read_bytes()==(installed/'site/ai_ad_editor/agent-project.schema.json').read_bytes()
        manifest=load(ROOT/'agent-ffmpeg-local-install-manifest.json')
        assert manifest['cli_version']=='0.1.20' and manifest['skill_count']==1 and manifest['module_count']==17
        assert manifest['manifest_sha256']==runtime['manifest_sha256'] and len(manifest['files'])==69
        for row in manifest['files']:
            assert sha(ROOT/row['path'])==row['sha256'] and (ROOT/row['path']).stat().st_size==row['bytes']
        discovery=Path('C:/Users/carzy/.codex/skills/agent-ffmpeg-local-editor')
        assert discovery.resolve()==(ROOT/'skills/agent-ffmpeg-local-editor').resolve()
        kit=load(ROOT/'docs/skills/community-unified-skill-package-0.1.20-r21.json')
        assert sha(ROOT/kit['archive'])==kit['sha256'] and kit['files']==96
        with zipfile.ZipFile(ROOT/kit['archive']) as archive:
            inventory=json.loads(archive.read('KIT-FILES.json'))
            assert inventory['cli_version']=='0.1.20' and inventory['skill_count']==1 and inventory['module_count']==17
            assert len(archive.namelist())==len(set(archive.namelist()))==96
            for row in inventory['files']:
                data=archive.read(row['path'])
                assert len(data)==row['bytes'] and hashlib.sha256(data).hexdigest()==row['sha256']
                if row['path'].startswith('skills/'):assert data==(ROOT/row['path']).read_bytes()
        isolated=load(BASE/'kit-r2/verification.json')
        assert isolated['status']=='passed' and isolated['skill_files']==69 and isolated['files']==96
        assert isolated['kit_sha256']==kit['sha256'] and not isolated['real_discovery_changed']
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
        assert responses['version']['data']['cli_version']=='0.1.20'
        capabilities=responses['capabilities']['data']['capabilities']
        assert capabilities==load(ROOT/'docs/product/opencl-projection-capabilities-cli-0.1.20.json')['data']['capabilities']
        counts=dict(Counter(row['status'] for row in capabilities.values()))
        assert len(capabilities)==75 and counts==dict(implemented=20,implemented_with_limits=47,local_adapter_only=7,degraded=1)
        for run,count in (('native-final-r1',18),('sequence-final-r1',63),('queue-schema-final-r1',47),('regression-final-r1',119),('cli-development-r1',122)):
            proof=load(BASE/'tests'/run/'verification.json')
            assert proof['status']=='passed' and proof['result']==dict(methods=count,skipped=0,failures=0,errors=0,success=True)
            assert proof['frozen_equal'] and proof['installed_frozen_equal'] and load(BASE/'tests'/run/'product-files.json')==source
            assert sha(BASE/'tests'/run/'tests.log')==proof['log_sha256']
        for phase in ('benchmark-r2','controls-r1','skill-r2','preview-r2'):
            assert load(BASE/phase/'verification.json')['status']=='passed',phase
            for row in load(BASE/phase/'calls.json'):
                assert sha(BASE/phase/(row['id']+'.stdout'))==row['stdout_sha256']
                assert sha(BASE/phase/(row['id']+'.stderr'))==row['stderr_sha256']
        bench=load(BASE/'benchmark-r2/verification.json')
        assert bench['frames_and_clock_equal_all_six'] and bench['audio_pcm_equal_all_six'] and bench['timeline_settings_assets_rights_unchanged']
        assert len(bench['renders'])==6 and all(len(values)==3 for values in bench['timings_seconds'].values())
        for row in bench['renders']:
            assert sha(row['path'])==row['sha256'] and row['fingerprint']['frame_count']==120
        controls=load(BASE/'controls-r1/verification.json')
        assert all(controls[name] for name in ('required_failure_preserved','cancel_before_gpu','resume_actual_opencl',
            'queued_actual_opencl','full_frames_and_pcm_equal','combined_projection_nvenc','combined_full_decode','combined_pcm_equal'))
        skill=load(BASE/'skill-r2/verification.json')
        assert skill['real_registered_skill'] and skill['frames_equal'] and skill['audio_pcm_equal'] and skill['compared_frames']==120
        diagnostic_count=0
        for folder in [*(BASE/'benchmark-r2').glob('*-diagnostics'),BASE/'skill-r2/projection-diagnostics']:
            evidence=load(folder/'report.json');assert evidence['status']=='verified'
            assert evidence['coefficient_probe']['all_binary64_bits_equal']
            for node in evidence['nodes']:
                assert node['selected']=='opencl' and sha(folder/Path(node['kernel']).name)==node['kernel_sha256']
            for probe in evidence['probes']:
                assert probe['status']=='completed' and probe['exit_code']==0
                for stream in ('stdout','stderr'):
                    assert sha(folder/Path(probe[stream]['path']).name)==probe[stream]['sha256']
            diagnostic_count+=1
        assert diagnostic_count==4
        media=load(ROOT/'docs/assets/opencl-projection-20261026-r1/media-manifest.json')
        assert media['mp4_frames']==120 and media['gif_frames']==40
        for row in media['files']:
            path=ROOT/row['path'];assert sha(path)==row['sha256'] and path.stat().st_size==row['bytes']
        assert load(BASE/'coefficient-failure-r1/failure.json')['code']=='PROJECTION_COEFFICIENT_MISMATCH'
        assert load(BASE/'tests/policy-development-r1/verification.json')['status']=='failed'
        assert load(BASE/'benchmark-r1/verification.json')['status']=='passed'
        original=rows(git('show',BASELINE+':docs/product/GOAL_GAPS_20261025.md').decode('utf-8-sig'),'G')
        current=rows((ROOT/'docs/product/GOAL_GAPS_20261025.md').read_text('utf8'),'G')
        assert len(original)==len(current)==38 and all(value.split('|')[5]==current[key].split('|')[5] for key,value in original.items())
        files=[ROOT/('docs/product/'+name) for name in ('GOAL_GAPS_20261025.md','IMPLEMENTATION_PLAN_20261025.md',
            'COMMUNITY_LOCAL_DELIVERY.md','OPENCL_PROJECTION.md','CASES.md','PROJECTION_RENDERING.md','AFFINE_RENDERING.md','MOTION_PACKS.md')]
        for name in ('README.md','README.zh-TW.md','README.en.md'):
            path=ROOT/name;text=path.read_text('utf8');old=rows(git('show',BASELINE+':'+name).decode('utf-8-sig'),'R');current=rows(text,'R')
            assert len(old)==138 and len(current)==146 and all(current[key]==value for key,value in old.items())
            for prefix,count in (('F',54),('S',20),('K',17)):assert len(rows(text,prefix))==count
            files.append(path)
        # Preserve the independent pre-optimization CPU oracle verbatim.
        oracle=(ROOT/'product/tests/projection_legacy_oracle.py').read_text('utf8')
        oracle_nodes={node.name:ast.get_source_segment(oracle,node) for node in ast.parse(oracle).body if isinstance(node,ast.FunctionDef)}
        for module,names in [('render.py',('_dynamic_crop_filters','_sequence_raster_filters')),('sequence_sampling.py',('area_rectangle',))]:
            text=git('show','2a78657b20b41c849dde5ebe347671d562f46cf2:product/src/ai_ad_editor/'+module).decode('utf8')
            for node in ast.parse(text).body:
                if isinstance(node,ast.FunctionDef) and node.name in names:
                    frozen=ast.get_source_segment(text,node);key=('legacy'+node.name) if module=='render.py' else node.name
                    if module=='render.py':frozen=frozen.replace('def '+node.name+'(', 'def '+key+'(',1)
                    assert oracle_nodes[key]==frozen,key
        tracked={Path(line.split('\t',1)[1]).name for line in git('ls-tree','-r',BASELINE,'product/src/ai_ad_editor').decode('utf8').splitlines()}
        changed={Path(name).name for name in git('diff','--name-only',BASELINE,'--','product/src/ai_ad_editor').decode('utf8').splitlines() if name.endswith('.py')}
        changed=sorted(changed | (set(source)-tracked))
        save('changed-product-modules.json',changed)
        files += [ROOT/'docs/README.md',ROOT/'docs/specs/OpenCL原生投影实现契约_20261026.md',
            ROOT/'docs/validation/OpenCL原生投影实测_2026-10-26.md',ROOT/'docs/releases/CLI_0.1.20_LOCAL.md']
        files += [ROOT/('docs/product/'+name+suffix+'.md') for name in ('CAPABILITIES','SKILLS','EFFECTS') for suffix in ('','.zh-TW','.en')]
        files += [ROOT/('docs/skills/UNIFIED_SKILL'+suffix+'.md') for suffix in ('','.zh-TW','.en')]
        files += [ROOT/'skills/agent-ffmpeg-local-editor'/name for name in ('SKILL.md','references/runtime.md',
            'references/projection-gpu.md','references/motion-packs.md','references/modules/timeline/module.md')]
        note=(ROOT/'docs/releases/CLI_0.1.20_LOCAL.md').read_text('utf8')
        assert all(value in note for value in (installation['archive_sha256'],installation['manifest_sha256'].removeprefix('sha256:'),kit['sha256']))
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
        request=urllib.request.Request('https://api.github.com/repos/copypasteltd/agent-editor-kit/releases?per_page=10',
            headers={'User-Agent':'agent-editor-kit-delivery-audit','Accept':'application/vnd.github+json'})
        with urllib.request.urlopen(request,timeout=30) as remote:raw,status=remote.read(4*1024*1024+1),remote.status
        assert status==200 and len(raw)<=4*1024*1024;(out/'github-releases.raw.json').write_bytes(raw)
        latest=max((r for r in json.loads(raw) if not r['draft']),key=lambda r:r['published_at'])['tag_name']
        assert latest=='v0.1.0-alpha.3'
        report.update(status='passed',finished_at_utc=datetime.now(timezone.utc).isoformat(),baseline_commit=BASELINE,
            cli_version='0.1.20',installed=str(installed),actual_read_only_cli_calls=6,source_and_installed_files=209,
            skill_files=69,kit_files=96,kit_sha256=kit['sha256'],capability_count=75,capability_status_counts=counts,
            original_goal_closure_conditions_preserved=38,historical_readme_rows_preserved_per_language=138,
            current_readme_rows_per_language=146,local_links_checked=links,public_release=latest,public_api_status=status,
            gpu_diagnostics_verified=diagnostic_count,paired_render_median_ratio=bench['median_ratio'],
            files=[dict(path=p.relative_to(ROOT).as_posix(),sha256=sha(p)) for p in files])
        save('verification.json',report);print(json.dumps({k:v for k,v in report.items() if k!='files'},ensure_ascii=False))
    except BaseException as exc:
        report.update(status='failed',error=repr(exc));save('verification.json',report);raise

if __name__=='__main__':main()
