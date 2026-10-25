"""Installed 4K full-frame alpha/blur/wipe checks under a declared allocation quota."""
import argparse,hashlib,json,sys,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--run',required=True);args=parser.parse_args()
    assert args.run.replace('-','').isalnum()
    out=ROOT/'docs/validation/evidence/float-transition-20261026-r1'/('4k-'+args.run)
    out.mkdir(parents=True,exist_ok=False);(out/'executed-runner.py').write_bytes(Path(__file__).read_bytes())
    sys.path.insert(0,str(ROOT/'local/agent-ffmpeg/v0.1.0-alpha.4-local.19/final-r1/installed/site'))
    import numpy as np
    from ai_ad_editor.float_transitions import transition_rgba
    w,h=3840,2160;x=np.arange(w,dtype=np.float64)/(w-1)
    a=np.empty((h,w,4),np.float32);b=np.empty_like(a)
    a[:]=np.stack((x,np.full(w,.15),1-x,np.full(w,.25)),1)
    b[:]=np.stack((1-x,np.full(w,.7),x,np.full(w,.75)),1)
    rows=[];report=dict(status='running',width=w,height=h,checked_pixels_per_pattern=w*h,
        max_working_bytes=512*1024**2,peak_RSS_measured=False,realtime_claimed=False,patterns=rows)
    def save():(out/'verification.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8',newline='\n')
    try:
        for kind in ('fade','hblur','wipeleft'):
            start=time.perf_counter()
            value,metadata=transition_rgba(a,b,.375,kind=kind,max_working_bytes=512*1024**2)
            elapsed=time.perf_counter()-start
            if kind=='wipeleft':
                expected=np.where((np.arange(w)<=2400)[:,None],a[0],b[0])
            else:
                alpha=.25*.625+.75*.375
                xx=x
                if kind=='hblur':
                    size=1441;begin=np.arange(w);end=np.minimum(w,begin+size)
                    xx=(begin+end-1)/2/(w-1)
                first=np.stack((xx,np.full(w,.15),1-xx),1)
                second=np.stack((1-xx,np.full(w,.7),xx),1)
                expected=np.c_[(first*.25*.625+second*.75*.375)/alpha,np.full(w,alpha)].astype(np.float32)
            maximum=0.
            for y in range(h):maximum=max(maximum,float(np.abs(value[y]-expected).max()))
            assert maximum<=2e-7,(kind,maximum)
            assert metadata['estimated_working_bytes']<=512*1024**2
            rows.append(dict(type=kind,seconds=elapsed,max_absolute_error=maximum,
                surface_sha256=hashlib.sha256(value.tobytes()).hexdigest(),metadata=metadata))
            save();print(json.dumps({k:rows[-1][k] for k in ('type','seconds','max_absolute_error')}),flush=True)
            del value
        report['status']='passed';save()
    except BaseException as exc:
        report.update(status='failed',error=repr(exc));save();raise

if __name__=='__main__':main()
