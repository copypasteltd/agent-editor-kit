"""Bounded diagnostic of the existing native Torch/CUDA runtime; no model inference."""
import json
import os
from pathlib import Path
import subprocess
import time

ROOT=Path(__file__).resolve().parents[2]

def main():
    out=ROOT/'docs/validation/evidence/music-loop-20261029-r1/native-cuda-probe-r1';out.mkdir(exist_ok=False)
    work=ROOT/'local/agent-ffmpeg/source60-native-cuda-probe-r1';work.mkdir(exist_ok=False)
    env=dict(os.environ)
    for key,name in [('TEMP','temp'),('TMP','temp'),('TMPDIR','temp'),('TORCH_HOME','torch'),('HF_HOME','hf'),('XDG_CACHE_HOME','cache')]:
        p=work/name;p.mkdir(exist_ok=True);env[key]=str(p)
    env.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',HF_HUB_DISABLE_TELEMETRY='1',PYTHONDONTWRITEBYTECODE='1')
    code='''import json,time
start=time.monotonic()
def mark(stage,**info):print(json.dumps(dict(stage=stage,seconds=time.monotonic()-start,**info)),flush=True)
mark('started')
import numpy as np
mark('numpy',version=np.__version__)
import torch
mark('torch',version=torch.__version__)
import safetensors
mark('safetensors',version=safetensors.__version__)
available=torch.cuda.is_available();mark('cuda-availability',available=available)
assert available
torch.set_num_threads(4);mark('threads')
torch.set_num_interop_threads(1);mark('interop')
torch.manual_seed(0);mark('seed')
torch.cuda.reset_peak_memory_stats();mark('context',device=torch.cuda.get_device_name(0))
mark('completed',model_forwards=0)
'''
    argv=['D:/dev/comfyui/ComfyUI_windows_portable_nvidia_0_30_0/ComfyUI_windows_portable/python_embeded/python.exe',
        '-I','-B','-u','-X','utf8','-c',code]
    started=time.monotonic()
    try:
        p=subprocess.run(argv,cwd=work,env=env,capture_output=True,timeout=90,creationflags=subprocess.CREATE_NO_WINDOW)
        stdout,stderr=p.stdout,p.stderr;status='passed' if p.returncode==0 else 'failed';exit_code=p.returncode
    except subprocess.TimeoutExpired as error:
        stdout,stderr=error.stdout or b'',error.stderr or b'';status='timeout';exit_code=None
    (out/'stdout').write_bytes(stdout);(out/'stderr').write_bytes(stderr)
    report=dict(status=status,exit_code=exit_code,seconds=time.monotonic()-started,model_forwards=0,
        diagnostic_only=True,actual_enhancement_case_accepted=False,original_worker_restarted=False,
        stdout=stdout.decode('utf-8','replace'),stderr=stderr.decode('utf-8','replace'))
    (out/'verification.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report),flush=True)

if __name__=='__main__':main()
