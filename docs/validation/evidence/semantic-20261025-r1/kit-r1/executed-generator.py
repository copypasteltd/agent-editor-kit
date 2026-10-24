"""Verify r4 bytes and exercise its isolated native configuration/registration."""
from pathlib import Path
import argparse,json,subprocess,sys,zipfile
from verify_semantic_20261025 import ROOT,sha,save


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--kit',type=Path,required=True);args=parser.parse_args()
    evidence=ROOT/'docs/validation/evidence/semantic-20261025-r1/kit-r1'
    evidence.mkdir(parents=True,exist_ok=False)
    (evidence/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    output=ROOT/'local/agent-ffmpeg/semantic-kit-r1/独立工具 包';output.mkdir(parents=True,exist_ok=False)
    with zipfile.ZipFile(args.kit) as archive:
        inventory=json.loads(archive.read('KIT-FILES.json'))
        assert inventory['cli_version']=='0.1.5' and inventory['skill_count']==1 and inventory['module_count']==17
        names=[row['path'] for row in inventory['files']]
        assert len(set(archive.namelist()))==len(archive.namelist())==len(names)+1
        assert set(archive.namelist())==set(names)|{'KIT-FILES.json'}
        for row in inventory['files']:
            relative=Path(row['path'])
            assert not relative.is_absolute() and '..' not in relative.parts and ':' not in row['path']
            data=archive.read(row['path'])
            import hashlib
            assert len(data)==row['bytes'] and hashlib.sha256(data).hexdigest()==row['sha256']
            target=output/relative;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
    runtime=json.loads((ROOT/'local/agent-ffmpeg/runtime.json').read_bytes())
    devices=json.loads(Path(runtime['community_config']).read_bytes())
    calls=[];ps=['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File']
    original=Path('C:/Users/carzy/.codex/skills/agent-ffmpeg-local-editor').resolve()
    def run(name,command,cli=False):
        command=list(map(str,command));completed=subprocess.run(command,cwd=ROOT,capture_output=True,timeout=900,creationflags=subprocess.CREATE_NO_WINDOW)
        stdout=evidence/(name+'.stdout.txt');stderr=evidence/(name+'.stderr.txt')
        stdout.write_bytes(completed.stdout);stderr.write_bytes(completed.stderr)
        calls.append(dict(id=name,command=command,exit_code=completed.returncode,stdout_sha256=sha(stdout),stderr_sha256=sha(stderr),cli=cli))
        save(evidence/'calls.json',calls)
        print(json.dumps(dict(id=name,exit=completed.returncode)),flush=True)
        assert completed.returncode==0,completed.stderr.decode('utf8','replace')[-3000:]
        if cli:
            response=json.loads(completed.stdout.decode('utf-8-sig'))
            assert response['ok'] and response['status']=='succeeded'
            return response['data']
    result=dict(kit=str(args.kit.resolve()),kit_sha256=sha(args.kit),source_fallback=False,native_windows=True,
        virtualization=False,registered_skills=1,internal_modules=17,real_discovery_changed=False,new_model_forwards=0)
    try:
        run('configure',[sys.executable,'-I','-B','-u','-X','utf8',output/'scripts/activate_community_runtime.py',
            '--installed',runtime['installed_directory'],'--packs',Path(devices['voice']['cpu_pack']).parent,
            '--voice-cuda-lib',devices['voice']['cuda_library_directory'],
            '--translation-cuda-lib',devices['translation']['cuda_library_directory'],'--semantic-config',runtime['semantic_config']])
        run('register',[*ps,output/'register-agent-ffmpeg-local-skills.ps1',
            '-SkillsDirectory',output.parent/'isolated-discovery','-ReceiptPath',evidence/'registration.json'])
        entry=output.parent/'isolated-discovery/agent-ffmpeg-local-editor'
        assert entry.resolve()==(output/'skills/agent-ffmpeg-local-editor').resolve()
        launcher=entry/'scripts/run.ps1'
        assert run('version',[*ps,launcher,'version'],True)['cli_version']=='0.1.5'
        project=ROOT/'workspace/semantic-20261025-installed-r1'
        run('index-list',[*ps,launcher,'semantic','index-list','--project',project],True)
        checked=run('verify-index',[*ps,launcher,'semantic','verify','--project',project,'--index-id','natural-gpu'],True)
        assert checked['rows']==15 and checked['source_assets']==10
        assert Path('C:/Users/carzy/.codex/skills/agent-ffmpeg-local-editor').resolve()==original
        result.update(status='passed',process_calls=len(calls),cli_calls=sum(row['cli'] for row in calls),
            files=len(names)+1,generator_sha256=sha(Path(__file__)))
        save(evidence/'verification.json',result);print(json.dumps(result,ensure_ascii=False),flush=True)
    except BaseException as exc:
        result.update(status='failed',message=str(exc)[:5000],process_calls=len(calls));save(evidence/'failure.json',result);raise


if __name__=='__main__':main()
