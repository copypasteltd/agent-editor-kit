"""Convert hash-verified official tensors to fixed local safetensors files."""
from pathlib import Path
import hashlib,json,sys
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'docs/validation/evidence/native-lipsync-20261027-r1'
MODEL=ROOT/'product/.runtime/models/musetalk-v15-20261027'
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
import torch
from safetensors.torch import save_file,load_file
rows=[]
for source,dest,expected,precision in [
    ('upstream/unet.pth','unet/diffusion_pytorch_model.safetensors','7ebf6c98c181e20838e4c0054e96e944ac60d5d692cc01db42839fe11b787007',torch.float16),
    ('upstream/face-parser.pth','parser/model.safetensors','468e13ca13a9b43cc0881a9f99083a430e9c0a38abd935431d1c28ee94b26567',None)]:
    p=MODEL/source;target=MODEL/dest;assert sha(p)==expected
    assert not target.exists();target.parent.mkdir(parents=True,exist_ok=True)
    state=torch.load(str(p),map_location='cpu',weights_only=True)
    assert isinstance(state,dict) and all(isinstance(k,str) and isinstance(v,torch.Tensor) for k,v in state.items())
    original=state
    if precision:state={k:v.to(precision).contiguous() if v.is_floating_point() else v.contiguous() for k,v in state.items()}
    save_file(state,str(target),metadata={'source_sha256':expected,'format':'pt','conversion':'float32-to-float16' if precision else 'unchanged-tensors'})
    restored=load_file(str(target),device='cpu')
    assert set(restored)==set(state) and all(torch.equal(state[k],restored[k]) for k in state)
    rows.append(dict(source=source,source_sha256=expected,path=dest,sha256=sha(target),bytes=target.stat().st_size,
        tensors=len(state),precision='float16' if precision else 'source-precision',safetensors_exact=True,weights_only=True))
    del state,original,restored
    import gc;gc.collect()
save=MODEL/'conversion.json';save.write_text(json.dumps(rows,indent=2)+'\n',encoding='utf8',newline='\n')
(BASE/'weight-conversion.json').write_bytes(save.read_bytes())
print(json.dumps(rows),flush=True)
