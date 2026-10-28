"""Probe real CUDA graph, frontend identity and independent upstream CPU output."""
from pathlib import Path
import json,sys,subprocess
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'product/src'))
BASE=ROOT/'docs/validation/evidence/native-speech-enhancement-20261027-r1/probe-r1'
MODEL=ROOT/'product/.runtime/models/deepfilternet3-20261027'
BASE.mkdir(parents=True,exist_ok=True)
import numpy as np
from ai_ad_editor.rvm_worker import install_network_guard
from ai_ad_editor.enhancement_dsp import analysis,synthesis
from ai_ad_editor.enhancement_model import load_predictor
from ai_ad_editor.media import ffmpeg_path
rng=np.random.default_rng(17);x=rng.normal(0,.03,(1,48000*3+137)).astype(np.float32)
x[:,1000:2000]+=.1*np.sin(np.arange(1000,dtype=np.float32)*.15)
y=synthesis(analysis(x),x.shape[-1]);identity=float(np.abs(x-y).max())
source=BASE/'source.f32';source.write_bytes(x.T.tobytes())
ff=ffmpeg_path()
subprocess.run([ff,'-nostdin','-v','error','-n','-f','f32le','-ar','48000','-ac','1','-i',str(source),'-c:a','pcm_f32le',str(BASE/'source.wav')],check=True,timeout=30)
exe=MODEL/'reference/deep-filter-0.5.6-x86_64-pc-windows-msvc.exe'
help_run=subprocess.run([str(exe),'--help'],capture_output=True,text=True,encoding='utf8',timeout=30)
(BASE/'official-help.txt').write_text(help_run.stdout+help_run.stderr,encoding='utf8')
events=[];install_network_guard(events)
predictor,metadata=load_predictor(MODEL,dict(threads=4))
z=predictor(x);metadata=predictor.finish();(BASE/'cuda-output.f32').write_bytes(z.T.tobytes())
record=dict(status='actual-cuda-probed',identity_max_abs_error=identity,samples=x.shape[-1],output_shape=list(z.shape),
    metadata=metadata,blocked_network_events=events)
(BASE/'probe.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf8')
assert identity<2e-7 and z.shape==x.shape and not events
print(json.dumps(record),flush=True)
