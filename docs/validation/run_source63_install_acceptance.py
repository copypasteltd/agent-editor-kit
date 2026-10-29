"""Verify the new native CLI63 candidate; full406 is a separate mandatory gate."""
import json,subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'docs/validation/evidence/job-enumeration-20261029-r1'
C='C:/Python313/python.exe'
D='D:/dev/comfyui/ComfyUI_windows_portable_nvidia_0_30_0/ComfyUI_windows_portable/python_embeded/python.exe'

def main():
    receipt=BASE/'installation-candidate-r1/verification.json'
    if not receipt.is_file():
        print(json.dumps(dict(status='pending',ready=False,missing=['installation-candidate-r1'],mutated=False)),flush=True)
        return 2
    installation=json.loads(receipt.read_bytes())
    assert installation['status']=='installed-and-byte-verified' and installation['cli_version']=='0.1.63'
    installed=installation['installed'];out=BASE/'installed-controller-r1';out.mkdir(exist_ok=False)
    (out/'executed-runner.py').write_bytes(Path(__file__).read_bytes())
    calls=[]
    for group in ['bootstrap','loop','control','selection','semantic','contracts']:
        prefix=[C,'-I','-S','-B','-u','-X','utf8'] if group=='bootstrap' else [
            C if group=='loop' else D,'-E' if group=='loop' else '-I','-B','-u','-X','utf8']
        command=[*prefix,str(ROOT/'docs/validation/run_source63_regressions.py'),
            '--group',group,'--run','r1','--installed',installed]
        print(json.dumps(dict(phase=group,status='starting')),flush=True)
        p=subprocess.run(command,cwd=ROOT)
        calls.append(dict(phase=group,exit_code=p.returncode))
        (out/'calls.json').write_text(json.dumps(calls,indent=2)+'\n',encoding='utf-8')
        if p.returncode:
            (out/'verification.json').write_text(json.dumps(dict(status='failed',calls=calls))+'\n',encoding='utf-8')
            return p.returncode
    for name in ['run_source63_gpu_case.py','run_installed63_loop_case.py','run_installed63_lipsync_case.py']:
        print(json.dumps(dict(phase=name,status='starting')),flush=True)
        p=subprocess.run([C,'-E','-B','-u','-X','utf8',str(ROOT/'docs/validation'/name),
            '--run','r1','--installed',installed],cwd=ROOT)
        calls.append(dict(phase=name,exit_code=p.returncode))
        (out/'calls.json').write_text(json.dumps(calls,indent=2)+'\n',encoding='utf-8')
        if p.returncode:
            (out/'verification.json').write_text(json.dumps(dict(status='failed',calls=calls))+'\n',encoding='utf-8')
            return p.returncode
    (out/'verification.json').write_text(json.dumps(dict(status='passed',calls=calls,
        full406_separate=False,full406_mandatory=True,formal_activation=False),indent=2)+'\n',encoding='utf-8')
    return 0

if __name__=='__main__':raise SystemExit(main())
