"""One-time weights-only conversion; product inference consumes safetensors only."""
from pathlib import Path
import hashlib,json,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'product/src'))
from ai_ad_editor.rvm_worker import install_network_guard
events=[];install_network_guard(events)
import torch,safetensors
from safetensors.torch import save_file,load_file
from ai_ad_editor.enhancement_graph import DfNet
BASE=ROOT/'docs/validation/evidence/native-speech-enhancement-20261027-r1'
MODEL=ROOT/'product/.runtime/models/deepfilternet3-20261027'
source=MODEL/'upstream/unpacked/DeepFilterNet3/checkpoints/model_120.ckpt.best'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
state=torch.load(source,map_location='cpu',weights_only=True)
assert len(state)==133 and all(isinstance(k,str) and torch.is_tensor(v) and v.dtype in (torch.float32,torch.int64) and torch.isfinite(v).all() for k,v in state.items())
net=DfNet(torch.zeros(481,32),torch.zeros(32,481));net.load_state_dict(state,strict=True)
target=MODEL/'model.safetensors'
if target.exists():
    loaded=load_file(str(target));assert loaded.keys()==state.keys() and all(torch.equal(v,loaded[k]) for k,v in state.items())
else:save_file({k:v.contiguous() for k,v in state.items()},str(target),metadata={'source':'DeepFilterNet3','conversion':'weights-only-strict-full-graph-v1'})
loaded=load_file(str(target));assert loaded.keys()==state.keys() and all(torch.equal(v,loaded[k]) for k,v in state.items())
config=dict(format='agent-native-deepfilternet3-model-v1',graph='DeepFilterNet3',sample_rate=48000,fft_size=960,hop_size=480,
    features='pyDF-analysis-ERB-and-unit-norm-v1',normalization_alpha=.99,precision='float32',tensor_count=133,
    source_checkpoint_sha256=sha(source))
(MODEL/'config.json').write_text(json.dumps(config,sort_keys=True,indent=2)+'\n',encoding='utf8',newline='\n')
for name in ('LICENSE-MIT','LICENSE-APACHE'):(MODEL/(name+'.txt')).write_bytes((BASE/'upstream-code'/name).read_bytes())
report=dict(status='converted-strict-tensor-equality',source_sha256=sha(source),target_sha256=sha(target),target_bytes=target.stat().st_size,
    config_sha256=sha(MODEL/'config.json'),tensor_count=len(state),tensor_dtypes=sorted({str(v.dtype) for v in state.values()}),
    weights_only_development_conversion=True,pickle_in_product_runtime=False,strict_full_graph=True,blocked_network_events=events,
    versions=dict(torch=torch.__version__,safetensors=safetensors.__version__))
for p in (BASE/'conversion.json',MODEL/'conversion.json'):p.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8',newline='\n')
assert not events
print(json.dumps(report),flush=True)
