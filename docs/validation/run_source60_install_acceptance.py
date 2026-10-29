"""Execute native installed60 short gates, then real CUDA and full-PCM loop case."""
import json
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'docs/validation/evidence/music-loop-20261029-r1'
C='C:/Python313/python.exe'
D='D:/dev/comfyui/ComfyUI_windows_portable_nvidia_0_30_0/ComfyUI_windows_portable/python_embeded/python.exe'

def main():
    installation=json.loads((BASE/'installation-candidate-r1/verification.json').read_bytes())
    assert installation['status']=='installed-and-byte-verified' and installation['cli_version']=='0.1.60'
    installed=installation['installed'];runner=ROOT/'docs/validation/run_source60_installed_regressions.py'
    for group in ['bootstrap','loop','control','selection','semantic']:
        prefix=[C,'-I','-S','-B','-u','-X','utf8'] if group=='bootstrap' else [
            C if group=='loop' else D,'-E' if group=='loop' else '-I','-B','-u','-X','utf8']
        subprocess.run([*prefix,str(runner),'--group',group,'--run','r1','--installed',installed],cwd=ROOT,check=True)
    for name in ['run_source60_gpu_case.py','run_installed60_loop_case.py']:
        subprocess.run([C,'-E','-B','-u','-X','utf8',str(ROOT/'docs/validation'/name),
            '--run','r1','--installed',installed],cwd=ROOT,check=True)

if __name__=='__main__':main()
