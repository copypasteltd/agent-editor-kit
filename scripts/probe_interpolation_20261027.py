"""Private native CUDA graph probe; no environment/package installation."""
import json,sys,time,hashlib
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'product/src'))
from ai_ad_editor.rvm_worker import install_network_guard
events=[];install_network_guard(events)
import numpy as np
from ai_ad_editor.interpolation_model import load_predictor
from ai_ad_editor.local_interpolation import settings
out=ROOT/'docs/validation/evidence/native-interpolation-20261027-r1'
report={'status':'failed','network_events':events};started=time.monotonic()
try:
    h,w=128,192;y,x=np.mgrid[:h,:w]
    a=np.stack(((x*7+y*3)%256,(x*3-y*5)%256,(x*y)%256,np.where(x<20,0,np.where(x<60,128,255))),-1).astype('uint8')
    b=np.roll(a,12,axis=1)
    predictor,metadata=load_predictor(ROOT/'product/.runtime/models/rife-v4.25-20261027',settings(),width=w,height=h)
    frames=list(predictor.interpolate(a,b,[(1,3),(2,3),(1,2)]));execution=predictor.finish()
    assert len(frames)==3 and execution['flow_forwards']==3
    assert all(f.shape==a.shape and f.dtype==np.uint8 and (f[:,:,:3][f[:,:,3]==0]==0).all() for f in frames)
    assert not np.array_equal(frames[0],frames[1])
    from PIL import Image
    for i,f in enumerate(frames):Image.fromarray(f).save(out/f'private-probe-{i}.png')
    report.update(status='passed',execution=execution,shape=list(a.shape),frames=[{'sha256':hashlib.sha256(f.tobytes()).hexdigest(),'different_from_left':int(np.count_nonzero(f!=a))} for f in frames])
except Exception as exc:
    report['error']=repr(exc);raise
finally:
    report['seconds']=time.monotonic()-started;(out/'private-cuda-probe.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps({'status':report['status'],'seconds':report['seconds'],'error':report.get('error')}))
