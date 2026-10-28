"""Compare actual CUDA output to independently released native Rust/ONNX CLI."""
from pathlib import Path
import json,subprocess,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'product/src'))
from ai_ad_editor.media import ffmpeg_path
import numpy as np
BASE=ROOT/'docs/validation/evidence/native-speech-enhancement-20261027-r1/probe-r1'
MODEL=ROOT/'product/.runtime/models/deepfilternet3-20261027'
exe=MODEL/'reference/deep-filter-0.5.6-x86_64-pc-windows-msvc.exe'
out=BASE/'official-r2';out.mkdir(exist_ok=False)
argv=[str(exe),'-D','--min-db-thresh=-100','--max-db-erb-thresh=100','--max-db-df-thresh=100','-o',str(out),str(BASE/'source.wav')]
run=subprocess.run(argv,capture_output=True,timeout=90)
(BASE/'official-r2.stdout.txt').write_bytes(run.stdout);(BASE/'official-r2.stderr.txt').write_bytes(run.stderr)
assert run.returncode==0,run.stderr.decode('utf8','replace')
wav=next(out.glob('*.wav'));raw=out/'official.f32'
subprocess.run([ffmpeg_path(),'-nostdin','-v','error','-n','-i',str(wav),'-c:a','pcm_f32le','-f','f32le',str(raw)],check=True,timeout=30)
x=np.fromfile(BASE/'cuda-output.f32',dtype='<f4');y=np.fromfile(raw,dtype='<f4')
count=min(len(x),len(y));difference=x[:count]-y[:count]
records=[]
for offset in range(-1440,1441):
    a=x[max(0,offset):min(len(x),len(y)+offset)];b=y[max(0,-offset):min(len(y),len(x)-offset)]
    records.append((float(np.mean(np.square(a-b,dtype=np.float64))),offset))
best=min(records)
report=dict(status='independent-reference-compared',argv=argv,cuda_samples=len(x),official_samples=len(y),
    max_abs_error=float(np.abs(difference).max()),rms_error=float(np.sqrt(np.mean(np.square(difference,dtype=np.float64)))),
    official_peak=float(np.abs(y).max()),cuda_peak=float(np.abs(x).max()),best_sample_offset=best[1],best_mse=best[0],
    independent_runtime='official-Rust-Tract-ONNX-native-Windows-v0.5.6',not_bit_exact=True)
(BASE/'independent-reference.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
print(json.dumps(report),flush=True)
