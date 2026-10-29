"""Execute missing frozen source gates and real cases serially on native Windows."""
import json,subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'docs/validation/evidence/lipsync-timeout-20261029-r1'
C='C:/Python313/python.exe'
D='D:/dev/comfyui/ComfyUI_windows_portable_nvidia_0_30_0/ComfyUI_windows_portable/python_embeded/python.exe'

def main():
    out=BASE/'delivery-checks-controller-r1';out.mkdir(exist_ok=False)
    (out/'executed-runner.py').write_bytes(Path(__file__).read_bytes())
    calls=[]
    commands=[([D,'-I','-B','-u','-X','utf8',str(ROOT/'docs/validation/run_source61_regressions.py'),
                '--group',g,'--run','r1'],g) for g in ['control','selection','semantic']]
    commands += [([C,'-E','-B','-u','-X','utf8',str(ROOT/'docs/validation'/f),'--run','r1'],f)
        for f in ['run_source61_loop_case.py','run_source61_gpu_case.py']]
    for command,name in commands:
        print(json.dumps(dict(phase=name,status='starting')),flush=True)
        with (out/(name+'.stdout')).open('wb') as stdout,(out/(name+'.stderr')).open('wb') as stderr:
            p=subprocess.run(command,cwd=ROOT,stdout=stdout,stderr=stderr)
        calls.append(dict(phase=name,exit_code=p.returncode))
        (out/'calls.json').write_text(json.dumps(calls,indent=2)+'\n',encoding='utf-8')
        print(json.dumps(calls[-1]),flush=True)
        if p.returncode:
            (out/'verification.json').write_text(json.dumps(dict(status='failed',calls=calls))+'\n',encoding='utf-8')
            return p.returncode
    (out/'verification.json').write_text(json.dumps(dict(status='passed',calls=calls,
        full403_separate=True,formal_skill_activated=False),indent=2)+'\n',encoding='utf-8')
    return 0

if __name__=='__main__':raise SystemExit(main())
