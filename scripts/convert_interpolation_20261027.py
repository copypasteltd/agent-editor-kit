"""One-time weights-only conversion and independent mirror tensor comparison."""
from pathlib import Path
import hashlib,json,sys
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'product/src'))
from ai_ad_editor.rvm_worker import install_network_guard
events=[];install_network_guard(events)
import torch,safetensors
from safetensors.torch import save_file,load_file
from ai_ad_editor.interpolation_graph import IFNet,IFBlock
BASE=ROOT/'docs/validation/evidence/native-interpolation-20261027-r1';MODEL=ROOT/'product/.runtime/models/rife-v4.25-20261027'
source=MODEL/'upstream/unpacked/train_log/flownet.pkl';target=MODEL/'model.safetensors';assert not target.exists()
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
state=torch.load(source,map_location='cpu',weights_only=True)
assert isinstance(state,dict) and all(isinstance(k,str) and isinstance(v,torch.Tensor) for k,v in state.items())
clean={}
for key,value in state.items():
    name=key.removeprefix('module.');assert name not in clean and value.dtype==torch.float32 and torch.isfinite(value).all();clean[name]=value.contiguous()
with torch.device('meta'):
    net=IFNet()
    teacher=IFBlock(31,c=64)
    caltime=torch.nn.Sequential(torch.nn.Conv2d(17,32,3,2,1),torch.nn.LeakyReLU(.2,True),
        torch.nn.Conv2d(32,64,3,2,1),torch.nn.LeakyReLU(.2,True),torch.nn.Conv2d(64,64,3,1,1),
        torch.nn.LeakyReLU(.2,True),torch.nn.Conv2d(64,64,3,1,1),torch.nn.LeakyReLU(.2,True),torch.nn.Conv2d(64,1,3,1,1),torch.nn.Sigmoid())
excluded={k:v for k,v in clean.items() if k.startswith(('teacher.','caltime.'))}
# The released checkpoint retains training-only graphs. Its older caltime
# head is17->32, while the commented example in the inference file is25->8.
# Validate the complete known released parameter sets/shapes, then omit them.
for module,prefix in ((teacher,'teacher.'),(caltime,'caltime.')):
    module.load_state_dict({k[len(prefix):]:v for k,v in excluded.items() if k.startswith(prefix)},strict=True,assign=True)
clean={k:v for k,v in clean.items() if k not in excluded}
net.load_state_dict(clean,strict=True,assign=True)
mirror=load_file(str(MODEL/'mirrors/simonri_saferife/rife-4.25.safetensors'),device='cpu')
mirror={k.removeprefix('module.'):v for k,v in mirror.items()}
assert clean.keys()==mirror.keys(),(len(clean),len(mirror))
assert all(torch.equal(v,mirror[k]) for k,v in clean.items())
save_file(clean,str(target),metadata={'source':'Practical-RIFE4.25','conversion':'weights-only-strict-independent-tensor-equality-v1'})
reload=load_file(str(target),device='cpu');assert reload.keys()==clean.keys() and all(torch.equal(v,reload[k]) for k,v in clean.items())
assert events==[]
config=dict(format='agent-native-rife425-model-v1',graph='Practical-RIFE4.25',precision='float32',scale_list=[16,8,4,2,1],
    tensor_count=len(clean),source_checkpoint_sha256=sha(source),independent_mirror_tensor_equality=True)
(MODEL/'config.json').write_text(json.dumps(config,sort_keys=True,indent=2)+'\n',encoding='utf8',newline='\n')
(MODEL/'LICENSE.txt').write_bytes((BASE/'upstream-code/LICENSE').read_bytes())
proof=dict(status='converted-and-byte-exact-tensor-verified',source_sha256=sha(source),target_sha256=sha(target),target_bytes=target.stat().st_size,
    tensors=len(clean),strict_complete_graph=True,weights_only=True,pickle_in_product_runtime=False,independent_mirror_tensor_equality=True,
    independent_mirror_scope='Every inference tensor; unused training graphs separately strict-shape-verified',training_only_excluded_keys=sorted(excluded),
    independent_mirror_sha256=sha(MODEL/'mirrors/simonri_saferife/rife-4.25.safetensors'),blocked_network_events=events,
    versions=dict(torch=torch.__version__,safetensors=safetensors.__version__),config_sha256=sha(MODEL/'config.json'))
for p in (BASE/'weight-conversion.json',MODEL/'conversion.json'):p.write_text(json.dumps(proof,indent=2)+'\n',encoding='utf8',newline='\n')
print(json.dumps(proof),flush=True)
