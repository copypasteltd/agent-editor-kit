"""Commit full installed403 and real103-voice auditions; keep live Skill cases separate."""
import hashlib,json,os,subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'docs/validation/evidence/lipsync-timeout-20261029-r1'
VOICE=ROOT/'docs/validation/evidence/voice-auditions-20261029-r1'
GIT=Path('C:/Users/carzy/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/git/cmd/git.exe')


def load(path):return json.loads(path.read_bytes())


def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def main():
    publication=load(VOICE/'publication-r1/verification.json')
    assert publication['status']=='passed' and publication['README_rows']==494
    overlay_publication=load(BASE/'voice-overlay-publication-r1/verification.json')
    assert overlay_publication['status']=='passed' and overlay_publication['README_rows']==496
    pins={**publication['file_hashes'],**overlay_publication['file_hashes']}
    assert all(sha(ROOT/p)==h for p,h in pins.items())
    installation=load(BASE/'installation-candidate-r1/verification.json')
    assert all(sha(p)==h for p,h in installation['registered_skill_file_hashes'].items())
    full=load(BASE/'installed61-contracts-r1/verification.json')
    assert full['status']=='passed' and full['tests']==403 and full['frozen_equal']
    assert all(sha(ROOT/p)==h for p,h in full['file_hashes'].items())
    voice=load(VOICE/'r2/verification.json');assert voice['status']=='passed' and voice['voices']==103
    assert load(VOICE/'r1/verification.json')['status']=='failed'
    preview=load(VOICE/'gallery-screenshot-r1/verification.json')
    assert preview['status']=='passed' and sha(ROOT/preview['screenshot'])==preview['screenshot_sha256']
    assert preview['owned_browser_processes_remaining']==0
    scripts=['run_installed61_voice_auditions','screenshot_source61_voice_gallery',
             'run_source61_skill_acceptance','publish_source61_voice_delivery','commit_source61_voice_delivery',
             'source61_voice_skill_overlay','prepare_source61_voice_skill_overlay','check_source61_voice_skill_overlay',
             'activate_source61_skill','run_registered61_loop_case','run_registered61_gpu_case',
             'run_registered61_lipsync_case','check_source61_activation_gate_r2',
             'check_source61_registered_delivery_gate_r2','publish_source61_voice_skill_overlay']
    files=list(pins)
    for name in scripts:
        p=ROOT/'docs/validation'/(name+'.py');compile(p.read_text(encoding='utf-8'),str(p),'exec')
        files.append(p.relative_to(ROOT).as_posix())
    directories=[BASE/'installed61-contracts-r1',VOICE/'r1',VOICE/'r2',VOICE/'gallery-screenshot-r1',
                 VOICE/'publication-r1',ROOT/'docs/assets/voice-gallery61-20261029-r1',
                 BASE/'voice-skill-overlay-preflight-r1',BASE/'voice-skill-overlay-r1',
                 BASE/'activation-gate-check-r2',BASE/'registered-delivery-gate-check-r2',
                 BASE/'staged-actual-case-r1',BASE/'staged61-gpu-r1',BASE/'voice-overlay-publication-r1']
    for directory in directories:
        if directory.name!='voice-skill-overlay-preflight-r1':
            receipt=directory/'verification.json'
            if receipt.exists():assert load(receipt)['status'] in ('passed','failed')
    for directory in directories:
        files.extend(p.relative_to(ROOT).as_posix() for p in directory.iterdir() if p.is_file())
    files=sorted(set(files));assert all((ROOT/p).is_file() for p in files)
    assert not any(p.endswith(('.wav','.zip')) for p in files)
    out=ROOT/'local/agent-ffmpeg/source61-voice-delivery-commit-r3';out.mkdir(exist_ok=False)
    spec=out/'paths.nul';spec.write_bytes(b'\0'.join(p.encode('utf-8') for p in files)+b'\0')
    (out/'paths.json').write_text(json.dumps(files,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    env=dict(os.environ);env['PATH']=str(GIT.parent)+os.pathsep+env.get('PATH','')
    git=[str(GIT),'--no-optional-locks','-c','core.fsmonitor=false','-c','gc.auto=0','-c','maintenance.auto=0']
    def get(args):return subprocess.check_output([*git,*args],cwd=ROOT,env=env).decode().strip()
    assert get(['branch','--show-current'])=='main'
    assert get(['rev-parse','HEAD'])=='001a5a5ae82657df02b5710344ee337e491981e3'
    assert get(['remote','get-url','origin'])=='git@github.com:copypasteltd/agent-editor-kit.git'
    steps=[('add',['add','--pathspec-from-file='+str(spec),'--pathspec-file-nul'])]
    steps += [('check-'+str(i//60),['diff','--cached','--check','--',*files[i:i+60]]) for i in range(0,len(files),60)]
    steps += [('commit',['commit','--only','-m','feat: generate all 103 local CUDA voice auditions and accept installed CLI61 contracts',
                        '--pathspec-from-file='+str(spec),'--pathspec-file-nul'])]
    for phase,args in steps:
        result=subprocess.run([*git,*args],cwd=ROOT,env=env,capture_output=True)
        (out/(phase+'.stdout')).write_bytes(result.stdout);(out/(phase+'.stderr')).write_bytes(result.stderr)
        print(json.dumps(dict(phase=phase,exit_code=result.returncode)),flush=True)
        if result.returncode:return result.returncode
    refs=dict(head=get(['rev-parse','HEAD']),origin=get(['rev-parse','origin/main']),
              remote=get(['ls-remote','origin','refs/heads/main']).split()[0])
    assert len(set(refs.values()))==1
    result=dict(status='passed',refs=refs,files=len(files),source='0.1.61',candidate='0.1.61',
                formal='0.1.59',README_rows=496,installed403_passed=True,actual_voice_auditions=103,
                audio_published=False,formal_activation=False,live_Skill_cases_excluded=True,full_goal_closed=False)
    (out/'verification.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result),flush=True)
    return 0


if __name__=='__main__':raise SystemExit(main())
