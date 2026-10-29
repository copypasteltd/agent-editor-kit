"""Prepare real C-drive entry checks, gated by completed activation and installed400."""
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]

def write(name,text):
    p=ROOT/'docs/validation'/name;assert not p.exists()
    compile(text,str(p),'exec');p.write_text(text,encoding='utf-8')

def main():
    text=(ROOT/'docs/validation/run_staged60_loop_case.py').read_text(encoding='utf-8')
    text=text.replace('    skill=a.skill.resolve()', '''    skill=Path('C:/Users/carzy/.codex/skills/agent-ffmpeg-local-editor')
    assert a.skill==skill and skill.resolve()==(ROOT/'skills/agent-ffmpeg-local-editor').resolve()
    activation=load(BASE/'skill60-activation-r1/verification.json')
    assert activation['status']=='activated-and-entry-verified'
    assert load(BASE/'installed60-contracts-r1/verification.json')['status']=='passed'
'''.rstrip())
    text=text.replace("    assert skill.is_relative_to((ROOT/'local/agent-ffmpeg').resolve())\n",'')
    text=text.replace("    stage=load(skill.parents[1]/'STAGING.json')", "    stage=load(ROOT/'local/agent-ffmpeg/music60-skill-stage-r1/STAGING.json')")
    text=text.replace("'music-loop60-staged-case-'", "'music-loop60-registered-case-'")
    text=text.replace("('staged-actual-case-'+a.run)","('registered-actual-case-'+a.run)")
    text=text.replace("assert manifest['cli_version']=='0.1.59'", "assert manifest['cli_version']=='0.1.60'\n    assert sha(namespace)==activation['namespace_sha256'] and sha(runtime)==activation['runtime_sha256']")
    text=text.replace('candidate_registered=False,','candidate_registered=True,actual_C_drive_entry=True,activated=True,')
    text=text.replace("installed400_accepted=stage.get('installed400_accepted',True)", "installed400_accepted=True")
    text=text.replace("registered_skill_cli='0.1.59'", "registered_skill_cli='0.1.60'")
    write('run_registered60_loop_case.py',text)
    text=(ROOT/'docs/validation/run_staged60_gpu_case.py').read_text(encoding='utf-8')
    text=text.replace("mode = 'staged60'", "mode = 'registered60'")
    text=text.replace('    skill=args.skill.resolve()', '''    skill=Path('C:/Users/carzy/.codex/skills/agent-ffmpeg-local-editor')
    assert args.skill==skill and skill.resolve()==(ROOT/'skills/agent-ffmpeg-local-editor').resolve()
    activation=load(BASE/'skill60-activation-r1/verification.json')
    assert activation['status']=='activated-and-entry-verified'
    assert load(BASE/'installed60-contracts-r1/verification.json')['status']=='passed'
'''.rstrip())
    text=text.replace("    assert skill.is_relative_to((ROOT/'local/agent-ffmpeg').resolve())\n",'')
    text=text.replace("stage=load(skill.parents[1]/'STAGING.json')", "stage=load(ROOT/'local/agent-ffmpeg/music60-skill-stage-r1/STAGING.json')")
    text=text.replace("case=load(BASE/'staged-actual-case-r1/verification.json')", "case=load(BASE/'registered-actual-case-r1/verification.json')")
    text=text.replace('candidate_registered=False,','candidate_registered=True,actual_C_drive_entry=True,activated=True,')
    text=text.replace("installed400_accepted=stage.get('installed400_accepted',True)", "installed400_accepted=True")
    text=text.replace('    namespace_pin = sha(namespace)', "    namespace_pin = sha(namespace)\n    assert namespace_pin==activation['namespace_sha256']")
    write('run_registered60_gpu_case.py',text)
    print('Prepared registered C-drive loop/GPU checks; activation and installed400 required.')

if __name__=='__main__':main()
