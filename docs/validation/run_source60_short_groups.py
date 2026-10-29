"""Run source60 bootstrap, Windows control, selection and semantic groups serially."""
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[2]
C='C:/Python313/python.exe'
D='D:/dev/comfyui/ComfyUI_windows_portable_nvidia_0_30_0/ComfyUI_windows_portable/python_embeded/python.exe'

def main():
    for group in ['bootstrap','control','selection','semantic']:
        prefix=[C,'-I','-S','-B','-u','-X','utf8'] if group=='bootstrap' else [D,'-I','-B','-u','-X','utf8']
        subprocess.run([*prefix,str(ROOT/'docs/validation/run_source60_compatibility.py'),
            '--group',group,'--run','r1'],cwd=ROOT,check=True)

if __name__=='__main__':main()
