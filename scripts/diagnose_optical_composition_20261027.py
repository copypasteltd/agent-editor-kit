"""Record isolated optical precision versus inherited particle-source precision."""
from pathlib import Path
import copy,hashlib,json,sys,tempfile
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'product/src'),str(ROOT/'product/tests')]
import test_float_optics as tests
from ai_ad_editor.float_gpu import FloatGPUSession
from ai_ad_editor.float_timeline import FloatTimeline
from ai_ad_editor.float_effect_chain import EffectCompiler
from ai_ad_editor.procedural_particles import ParticleSource
from ai_ad_editor.float_composite import composite_rgba
OUT=ROOT/'docs/validation/evidence/optical-effects-20261027-r1/composition-diagnostic-r1'
OUT.mkdir(exist_ok=False)
(OUT/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
f=tests.OpticalIntegrationTests('runTest');f.setUp()
try:
 p=f.f.p;s=f.f.s;cpu=FloatTimeline(p,s['id'],{},working_signal=tests.LINEAR)
 rows=[];source=ParticleSource(f.f.c['generator'])
 with tempfile.TemporaryDirectory(dir=ROOT/'local/agent-ffmpeg') as temp:
  with FloatGPUSession(temp,{'projection_acceleration':{'mode':'require','device':'0.0'}},max_pixels=96*64) as gpu:
   host=FloatTimeline(p,s['id'],{},working_signal=tests.LINEAR,gpu=gpu)
   compiler=EffectCompiler(resource_root=None,working_signal=tests.LINEAR,gpu=gpu)
   plans=compiler.compile(f.f.c['effects'])
   ref_compiler=EffectCompiler(resource_root=None,working_signal=tests.LINEAR)
   ref_plans=ref_compiler.compile(f.f.c['effects'])
   for i in range(24):
    a=source.frame(i);b=source.frame(i,gpu=gpu)
    opticalCPU,_=ref_compiler.apply(a,ref_plans,i*7500)
    opticalGPU,_=compiler.apply(a,plans,i*7500)
    inherited,_=ref_compiler.apply(b,ref_plans,i*7500)
    ca,cm=cpu.render_frame(i);ga,gm=host.render_frame(i)
    delta=np.abs(ca-ga);index=tuple(int(v) for v in np.unravel_index(np.argmax(delta),delta.shape))
    rows.append(dict(frame=i,source_straight_max=float(np.max(np.abs(a-b))),source_alpha_max=float(np.max(np.abs(a[:,:,3]-b[:,:,3]))),
     optical_same_input_max=float(np.max(np.abs(opticalCPU-opticalGPU))),
     inherited_optical_RGB_max=float(np.max(np.abs(opticalCPU[:,:,:3]*a[:,:,3:4]-inherited[:,:,:3]*b[:,:,3:4]))),
     full_pipeline_max=float(np.max(delta)),index=index,CPU_pixel=ca[index[:2]].tolist(),GPU_pixel=ga[index[:2]].tolist()))
  receipt=copy.deepcopy(gpu.evidence)
 result=dict(status='diagnostic-complete',frames=rows,GPU=receipt,
  max_errors={k:max(r[k] for r in rows) for k in rows[0] if k.endswith('_max')})
 (OUT/'verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
 print(json.dumps(result['max_errors']))
finally:f.doCleanups()
