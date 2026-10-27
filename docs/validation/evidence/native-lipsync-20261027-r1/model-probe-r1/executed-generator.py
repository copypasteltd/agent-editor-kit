"""Actual CUDA forward probe; its real-person input/output remain private."""
from pathlib import Path
import argparse,hashlib,json,math,os,subprocess,sys,time
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'docs/validation/evidence/native-lipsync-20261027-r1'
ap=argparse.ArgumentParser();ap.add_argument('--run',required=True);a=ap.parse_args()
out=BASE/('model-probe-'+a.run);out.mkdir(exist_ok=False)
work=ROOT/'local/agent-ffmpeg'/('lipsync-model-probe-'+a.run);work.mkdir(exist_ok=False)
(out/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
sys.path.insert(0,str(ROOT/'product/src'));os.environ.update(HF_HUB_OFFLINE='1',TRANSFORMERS_OFFLINE='1',
    HF_HUB_DISABLE_TELEMETRY='1',CUBLAS_WORKSPACE_CONFIG=':4096:8')
from ai_ad_editor.media import ffmpeg_path
wav=ROOT/'local/agent-ffmpeg/lipsync-voice-probe-r1/assets/derived/synthetic-speech.wav'
audio=subprocess.check_output([ffmpeg_path(),'-v','error','-i',str(wav),'-af','apad=whole_len=16000',
    '-t','1','-ac','1','-ar','16000','-f','f32le','pipe:1'],timeout=60)
from ai_ad_editor.rvm_worker import install_network_guard
events=[];install_network_guard(events)
import numpy as np,cv2
from PIL import Image
from ai_ad_editor.lipsync_model import load_predictor
source=Path('D:/dev/comfyui/ComfyUI_windows_portable_nvidia_0_30_0/ComfyUI_windows_portable/python_embeded/Lib/site-packages/skimage/data/astronaut.png')
report={'status':'running','source':'local scikit-image public-domain NASA astronaut; private engineering probe only',
    'public_media':False,'source_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),'frames':25,'fps':25,'network_events':events}
def save():(out/'verification.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8',newline='\n')
save();started=time.monotonic()
try:
    predictor,metadata=load_predictor(ROOT/'product/.runtime/models/musetalk-v15-20261027',
        {'threads':4,'seed':17,'batch_size':2},phase=lambda s:print(s,flush=True))
    predictor.audio(np.frombuffer(audio,dtype='<f4').copy(),25)
    original=np.asarray(Image.open(source).convert('RGB'));crop=cv2.resize(original[65:185,173:285],(256,256),interpolation=cv2.INTER_LANCZOS4)
    latent,mask=predictor.source(crop,original[35:215,140:315]);Image.fromarray(mask).save(work/'semantic-mask.png')
    digest=hashlib.sha256();first=None;last=None
    for i in range(0,25,2):
        ids=list(range(i,min(i+2,25)));frames=predictor.predict([latent]*len(ids),ids)
        for index,frame in zip(ids,frames):
            digest.update(frame.tobytes())
            if first is None:first=frame.copy()
            last=frame.copy();Image.fromarray(frame).save(work/(str(index)+'.png'))
    report.update(status='passed',execution=predictor.finish(),output_rgb_sha256=digest.hexdigest(),
        first_last_mean_difference=float(np.abs(first.astype(float)-last).mean()),
        semantic_mask_pixels=int(np.count_nonzero(mask)),elapsed_seconds=time.monotonic()-started)
    assert not events and report['first_last_mean_difference']>0
    save();print(json.dumps({k:v for k,v in report.items() if k!='execution'}),flush=True)
except BaseException as exc:report.update(status='failed',error=repr(exc),elapsed_seconds=time.monotonic()-started);save();raise
