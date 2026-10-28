"""Actual 4K operator admission/full-pixel oracle; not long-form throughput."""
from pathlib import Path
import argparse,hashlib,json,sys,time
import numpy as np
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'docs/validation/evidence/oklab-gamut-20261029-r1'
sys.path[:0]=[str(ROOT/'product/src'),str(ROOT/'product/tests'),str(ROOT/'scripts')]
from ai_ad_editor.float_hdr import map_display,LuminanceSignal
from test_float_gamut import oracle,MAPPING
from run_oklab_gamut_case_20261029 import matrix


def main():
 ap=argparse.ArgumentParser();ap.add_argument('--run',required=True);a=ap.parse_args();out=BASE/('4k-'+a.run);out.mkdir(exist_ok=False)
 (out/'executed-probe.py').write_bytes(Path(__file__).read_bytes());pins={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'product/src/ai_ad_editor').glob('*.py')}
 colors=np.vstack([np.eye(3),1-np.eye(3),np.zeros((1,3)),np.ones((1,3)),np.random.default_rng(62).random((4,3))]).astype(np.float32)
 surface=np.ones((2160,3840,4),np.float32)
 for i,c in enumerate(colors):surface[:,i*320:(i+1)*320,:3]=c
 before=hashlib.sha256(surface.tobytes()).hexdigest();start=time.perf_counter()
 actual,signal,meta=map_display(surface,LuminanceSignal('bt2020','linear',203),MAPPING)
 elapsed=time.perf_counter()-start
 target=matrix([(.64,.33),(.30,.60),(.15,.06)]);source=matrix([(.708,.292),(.170,.797),(.131,.046)])
 transform=np.linalg.solve(target,source);maximum=0.;mapped=0
 for i,c in enumerate(colors):
  rgb=(c.astype(np.float64)@transform.T*2.03).astype(np.float32).astype(np.float64);y=float(rgb@target[1]);shoulder=y*(1+y/100)/(1+y)
  toned=rgb*(shoulder/y if y>0 else 0);reference=np.array(oracle(toned))
  maximum=max(maximum,float(np.max(np.abs(actual[:,i*320:(i+1)*320,:3]-reference))))
  if np.any((toned<0)|(toned>1)):mapped+=2160*320
 assert maximum<1e-6 and np.isfinite(actual).all() and np.all((actual>=0)&(actual<=1))
 assert meta['perceptual_gamut']['gamut_pixels_mapped']==mapped
 assert before==hashlib.sha256(surface.tobytes()).hexdigest() and np.array_equal(actual[:,:,3],surface[:,:,3])
 assert pins=={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'product/src/ai_ad_editor').glob('*.py')}
 report=dict(status='passed',scope='one 3840x2160 CPU operator surface; not an encoded 4K movie or long-form/real-time benchmark',
  pixels=3840*2160,all_pixels_compared=True,maximum_linear_RGB_error=maximum,input_and_alpha_unchanged=True,
  mapped_pixels=mapped,operator_elapsed_seconds=elapsed,timing_is_exclusive=False,owned_workspace_estimate_bytes=meta['estimated_working_bytes'],
  estimate_is_peak_RSS=False,source_files=pins,metadata=meta,new_renders=0,new_model_forwards=0)
 (out/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n');print(json.dumps({k:v for k,v in report.items() if k not in ['source_files','metadata']},ensure_ascii=False))
if __name__=='__main__':main()
