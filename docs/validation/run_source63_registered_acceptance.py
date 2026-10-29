"""Exercise the real C-drive registered CLI63 Skill after atomic activation."""
import hashlib,json,subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'docs/validation/evidence/job-enumeration-20261029-r1'
PYTHON='C:/Python313/python.exe'


def load(path):return json.loads(path.read_bytes())


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')


def main():
    activation_path=BASE/'skill63-activation-r1/verification.json'
    if not activation_path.exists():
        print(json.dumps(dict(status='pending',missing=['skill63-activation-r1'],mutated=False)),flush=True)
        return 2
    activation=load(activation_path);assert activation['status']=='activated-and-entry-verified'
    assert activation['cli_version']=='0.1.63' and activation['voice_auditions']['actual_voice_samples']==103 and activation['post_test_document_changes'] is False
    manifest_path=ROOT/'agent-ffmpeg-local-install-manifest.json';runtime_path=ROOT/'local/agent-ffmpeg/runtime.json'
    assert sha(manifest_path)==activation['namespace_sha256'] and sha(runtime_path)==activation['runtime_sha256']
    manifest=load(manifest_path);assert manifest['cli_version']=='0.1.63' and len(manifest['files'])==93
    installed=load(BASE/'installation-candidate-r1/verification.json')['installed']
    skill=Path('C:/Users/carzy/.codex/skills/agent-ffmpeg-local-editor')
    assert skill.resolve()==(ROOT/'skills/agent-ffmpeg-local-editor').resolve()
    out=BASE/'registered-controller-r1';out.mkdir(exist_ok=False)
    (out/'executed-runner.py').write_bytes(Path(__file__).read_bytes())
    prefix=[PYTHON,'-E','-B','-u','-X','utf8']
    cases=[('static',[*prefix,'C:/Users/carzy/.codex/skills/.system/skill-creator/scripts/quick_validate.py',str(skill)])]
    for name in ['loop','gpu','lipsync']:
        cases.append((name,[*prefix,str(ROOT/'docs/validation'/('run_registered63_'+name+'_case.py')),
                            '--run','r1','--installed',installed,'--skill',str(skill)]))
    calls=[]
    for phase,command in cases:
        print(json.dumps(dict(phase=phase,status='starting')),flush=True)
        result=subprocess.run(command,cwd=ROOT,capture_output=True,timeout=7200,creationflags=subprocess.CREATE_NO_WINDOW)
        (out/(phase+'.stdout')).write_bytes(result.stdout);(out/(phase+'.stderr')).write_bytes(result.stderr)
        calls.append(dict(phase=phase,command=command,exit_code=result.returncode));save(out/'calls.json',calls)
        print(json.dumps(dict(phase=phase,exit_code=result.returncode)),flush=True)
        if result.returncode:
            save(out/'verification.json',dict(status='failed',calls=calls,registered_skill_changed=False))
            return result.returncode
    assert sha(manifest_path)==activation['namespace_sha256'] and sha(runtime_path)==activation['runtime_sha256']
    assert all(sha(ROOT/row['path'])==row['sha256'] for row in manifest['files'])
    save(out/'verification.json',dict(status='passed',calls=calls,cli_version='0.1.63',
         actual_C_drive_entry=True,actual_loop_DF3_MuseTalk_passed=True,
         documentation_voice_samples=103,static_skill_validation_passed=True,
         registered_skill_files_frozen=93,discovery_unchanged=True,full_product_goal_closed=False))
    print(json.dumps(dict(status='passed',registered_cli='0.1.63',full_goal_closed=False)),flush=True)
    return 0


if __name__=='__main__':raise SystemExit(main())
