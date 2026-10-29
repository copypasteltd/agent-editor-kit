"""Run native installed59 gates and the actual source/installed music case."""
import json
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'docs/validation/evidence/music-score-20261029-r1'
C='C:/Python313/python.exe'
D='D:/dev/comfyui/ComfyUI_windows_portable_nvidia_0_30_0/ComfyUI_windows_portable/python_embeded/python.exe'

def main():
    installation=json.loads((BASE/'installation-candidate-r1/verification.json').read_bytes())
    assert installation['status']=='installed-and-byte-verified'
    installed=installation['installed']
    runner=ROOT/'docs/validation/run_source59_installed_regressions.py'
    for group in ['bootstrap','score','control','selection','semantic']:
        prefix=[C,'-I','-S','-B','-u','-X','utf8'] if group=='bootstrap' else [
            C if group=='score' else D,'-E' if group=='score' else '-I','-B','-u','-X','utf8']
        command=[*prefix,str(runner),'--group',group,'--run','r1','--installed',installed]
        subprocess.run(command,cwd=ROOT,check=True)
    subprocess.run([C,'-E','-B','-u','-X','utf8',str(ROOT/'docs/validation/run_installed59_score_case.py'),
        '--run','r1','--installed',installed],cwd=ROOT,check=True)

if __name__=='__main__': main()
