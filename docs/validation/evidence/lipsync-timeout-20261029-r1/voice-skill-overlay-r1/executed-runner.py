"""Actually validate the doc-only overlay and reject executable/audio mismatches."""
import hashlib
import json
from pathlib import Path
import subprocess
from source61_voice_skill_overlay import prepare,validate_registered,VOICE,REFERENCE

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'docs/validation/evidence/lipsync-timeout-20261029-r1'


def load(path):return json.loads(path.read_bytes())


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    stage_root=ROOT/'local/agent-ffmpeg/music61-skill-stage-r1'
    stage=load(stage_root/'STAGING.json');folder=Path(stage['skill'])
    original=stage['candidate_files'];assert len(original)==93
    installation=load(BASE/'installation-candidate-r1/verification.json');guard=installation['registered_skill_file_hashes']
    assert all(sha(p)==h for p,h in guard.items())
    proof=load(VOICE)
    contents,registered,overlay=prepare(folder,original,proof)
    assert {name for name in original if original[name]!=registered[name]}=={REFERENCE}
    fake=dict(tested_candidate_files=original,registered_files=registered,documentation_overlay=overlay)
    assert validate_registered(stage,fake)['candidate_files']==registered
    rejected=[]
    for name,action in [('wrong-voice-count',lambda:prepare(folder,original,{**proof,'voices':102})),
                        ('wrong-audio-hash',lambda:prepare(folder,original,{**proof,'voice_records':[
                            {**proof['voice_records'][0],'WAV_sha256':'0'*64},*proof['voice_records'][1:]]})),
                        ('changed-executable',lambda:validate_registered(stage,{**fake,'registered_files':{
                            **registered,'scripts/run.py':'0'*64}})),
                        ('unknown-doc-path',lambda:validate_registered(stage,{**fake,'documentation_overlay':{
                            **overlay,'changed_paths':['SKILL.md']}}))]:
        try:action()
        except AssertionError:rejected.append(name)
        else:raise AssertionError('Mismatch accepted: '+name)
    out=BASE/'voice-skill-overlay-r1';out.mkdir(exist_ok=False)
    (out/'executed-runner.py').write_bytes(Path(__file__).read_bytes())
    (out/'executed-overlay.py').write_bytes((ROOT/'docs/validation/source61_voice_skill_overlay.py').read_bytes())
    target=ROOT/'local/agent-ffmpeg/voice-skill-doc-check-r1/skills/agent-ffmpeg-local-editor'
    assert not target.exists()
    for name,content in contents.items():
        destination=target/name;destination.parent.mkdir(parents=True,exist_ok=True);destination.write_bytes(content)
    command=['C:/Python313/python.exe','-E','-B','-u','-X','utf8',
             'C:/Users/carzy/.codex/skills/.system/skill-creator/scripts/quick_validate.py',str(target)]
    result=subprocess.run(command,cwd=ROOT,capture_output=True,timeout=120,
                          creationflags=subprocess.CREATE_NO_WINDOW)
    (out/'static.stdout').write_bytes(result.stdout);(out/'static.stderr').write_bytes(result.stderr)
    assert result.returncode==0,result.stderr
    assert original=={p.relative_to(folder).as_posix():sha(p) for p in folder.rglob('*') if p.is_file()}
    assert registered=={p.relative_to(target).as_posix():sha(p) for p in target.rglob('*') if p.is_file()}
    assert all(sha(p)==h for p,h in guard.items())
    report=dict(status='passed',static_validation_exit_code=0,changed_files=[REFERENCE],
                other92_tested_files_byte_equal=True,actual_voice_samples=103,negative_checks=rejected,
                original_tested_stage_unchanged=True,protected_files_unchanged=95,
                activation_performed=False,overlay=overlay,registered_files=registered)
    (out/'verification.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='registered_files'}),flush=True)


if __name__=='__main__':main()
