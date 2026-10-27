"""Fixed MuseTalk 1.5 CUDA graph, explicit local weights and bounded batches.

MuseTalk inference equations adapted under MIT; see LIPSYNC_LICENSES.txt.
No model hub, remote Python, pickle, automatic CPU fallback or face identity model.
"""
from pathlib import Path
import hashlib
import json
import math
import time


def read_tensors(path, *, prefix=None):
    import safetensors
    state={}
    with safetensors.safe_open(str(path),framework='pt',device='cpu',backend='pread') as stream:
        for key in stream.keys():
            if prefix is None or key.startswith(prefix):state[key[len(prefix):] if prefix else key]=stream.get_tensor(key)
    if not state:raise ValueError('LIPSYNC_WEIGHT_KEYS_MISSING')
    return state


def convert_legacy_vae_attention(state):
    """Rename the pinned 2022 SD VAE graph; keep every tensor strict-loaded."""
    result={}
    replacements={'.query.':'.to_q.','.key.':'.to_k.','.value.':'.to_v.',
                  '.proj_attn.':'.to_out.0.'}
    for key,value in state.items():
        target=key
        if '.mid_block.attentions.' in key:
            for old,new in replacements.items():target=target.replace(old,new)
            if target.endswith('.weight') and value.ndim in (3,4):
                if any(size!=1 for size in value.shape[2:]):
                    raise ValueError('LIPSYNC_VAE_ATTENTION_SHAPE_INVALID')
                value=value.reshape(value.shape[:2])
        if target in result:raise ValueError('LIPSYNC_VAE_ATTENTION_KEY_COLLISION')
        result[target]=value
    return result


def load_predictor(model_path, settings, *, phase=lambda _:None):
    import numpy as np
    import torch
    import diffusers,transformers,safetensors
    from diffusers import AutoencoderKL,UNet2DConditionModel
    from transformers import WhisperConfig,WhisperFeatureExtractor
    from transformers.models.whisper.modeling_whisper import WhisperEncoder
    from .lipsync_parser import BiSeNet
    from .cuda_admission import admit_cuda
    model=Path(model_path);started=time.monotonic()
    if not torch.cuda.is_available():raise ValueError('LIPSYNC_CUDA_UNAVAILABLE_NO_FALLBACK')
    torch.set_num_threads(settings['threads']);torch.set_num_interop_threads(1)
    torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False
    torch.cuda.reset_peak_memory_stats();torch.manual_seed(settings['seed'])
    memory=admit_cuda(torch,(4096+settings['batch_size']*256)*1024**2,'lipsync-load')
    phase('loading-musetalk-local-weights')
    with torch.device('meta'):
        unet=UNet2DConditionModel.from_config(json.loads((model/'unet/config.json').read_bytes()))
        vae=AutoencoderKL.from_config(json.loads((model/'vae/config.json').read_bytes()))
        whisper=WhisperEncoder(WhisperConfig.from_json_file(str(model/'whisper/config.json')))
        parser=BiSeNet()
    for net,name,prefix,dtype in [(unet,'unet/diffusion_pytorch_model.safetensors',None,torch.float16),
            (vae,'vae/diffusion_pytorch_model.safetensors',None,torch.float32),
            (whisper,'whisper/model.safetensors','model.encoder.',torch.float16),
            (parser,'parser/model.safetensors',None,torch.float32)]:
        state=read_tensors(model/name,prefix=prefix)
        if net is vae:state=convert_legacy_vae_attention(state)
        net.load_state_dict(state,strict=True,assign=True);del state
        net.to(device='cuda',dtype=dtype).eval().requires_grad_(False)
    extractor=WhisperFeatureExtractor.from_dict(json.loads((model/'whisper/preprocessor_config.json').read_bytes()))
    # Upstream creates positional values on CPU and casts to the feature dtype.
    # Pin this CPU construction too, avoiding platform-specific GPU sin rounding.
    position_cpu=torch.arange(200,dtype=torch.float32).unsqueeze(1)
    scale_cpu=torch.exp(torch.arange(0,384,2,dtype=torch.float32)*(-math.log(10000.)/384))
    pe=torch.zeros((1,200,384),dtype=torch.float32)
    pe[0,:,0::2]=torch.sin(position_cpu*scale_cpu);pe[0,:,1::2]=torch.cos(position_cpu*scale_cpu)
    positional=pe.to('cuda',torch.float16)
    metadata={'engine':'musetalk-v15-native-cuda-v1','versions':{'torch':torch.__version__,'numpy':np.__version__,
        'diffusers':diffusers.__version__,'transformers':transformers.__version__,'safetensors':safetensors.__version__},
        'weight_reader':'safetensors-pread','CUDA_admission':memory,'precision':{'unet':'float16','vae':'float32','whisper':'float16','parser':'float32'},
        'device':torch.cuda.get_device_name(0),'load_seconds':time.monotonic()-started,'model_loads':1,
        'calls':{'audio_encoder':0,'vae_encoder':0,'unet':0,'vae_decoder':0,'face_parser':0},
        'cache_hits':0,'batch_frames':[],'CPU_fallback':False,'network':'disabled','trained_face_raster':[256,256],
        'attention_backend':'torch-SDPA-math','seed':settings['seed']}
    class Predictor:
        cache_key=None;cache_latents=None;cache_mask=None

        def audio(self,samples,frames):
            if samples.dtype!=np.float32 or samples.ndim!=1 or len(samples)!=frames*640 or not np.isfinite(samples).all():
                raise ValueError('LIPSYNC_AUDIO_CLOCK_INVALID')
            chunks=[]
            with torch.inference_mode():
                for start in range(0,len(samples),480000):
                    phase('encoding-local-audio')
                    part=samples[start:start+480000]
                    mel=extractor(part,sampling_rate=16000,return_tensors='pt').input_features.to('cuda',torch.float16)
                    with torch.nn.attention.sdpa_kernel(torch.nn.attention.SDPBackend.MATH):
                        hidden=whisper(mel,output_hidden_states=True).hidden_states
                    encoded=torch.stack(hidden,dim=2)[0,:len(part)//320].contiguous().cpu()
                    chunks.append(encoded);metadata['calls']['audio_encoder']+=1
            feature=torch.cat(chunks,dim=0)
            zeros=torch.zeros((4,5,384),dtype=torch.float16)
            self.features=torch.cat((zeros,feature,torch.zeros((12,5,384),dtype=torch.float16)),dim=0)
            metadata['audio_feature_bytes']=self.features.numel()*self.features.element_size()

        def source(self,crop,parse_crop):
            import cv2
            # Source conditioning is independent of execution batch and repeated
            # source frames; retain one content-addressed entry, not a video cache.
            key=hashlib.sha256(str(parse_crop.shape).encode()+crop.tobytes()+parse_crop.tobytes()).hexdigest()
            if key==self.cache_key:
                metadata['cache_hits']+=1;return self.cache_latents,self.cache_mask
            with torch.inference_mode():
                picture=torch.from_numpy(crop.copy()).to('cuda',torch.float32).permute(2,0,1).unsqueeze(0)/255
                masked=picture.clone();masked[:,:,128:]=0
                generator=torch.Generator(device='cuda').manual_seed((settings['seed']^int(key[:16],16))%(2**63))
                parts=[]
                for image in (masked,picture):
                    parts.append(vae.encode(image*2-1).latent_dist.sample(generator=generator)*vae.config.scaling_factor)
                    metadata['calls']['vae_encoder']+=1
                latent=torch.cat(parts,dim=1).to(torch.float16)
                source=cv2.resize(parse_crop,(512,512),interpolation=cv2.INTER_LINEAR)
                tensor=torch.from_numpy(source.copy()).to('cuda',torch.float32).permute(2,0,1)/255
                mean=torch.tensor([.485,.456,.406],device='cuda')[:,None,None]
                std=torch.tensor([.229,.224,.225],device='cuda')[:,None,None]
                labels=parser(((tensor-mean)/std).unsqueeze(0))[0].argmax(dim=1)[0].cpu().numpy()
                mask=np.isin(labels,(1,11,12,13)).astype(np.uint8)*255
                if np.count_nonzero(mask)<64:raise ValueError('LIPSYNC_SELECTED_REGION_HAS_NO_SEMANTIC_FACE')
                metadata['calls']['face_parser']+=1
            self.cache_key=key;self.cache_latents=latent;self.cache_mask=mask
            return latent,mask

        def predict(self,latents,indices):
            if not 1<=len(indices)<=settings['batch_size']:raise ValueError('LIPSYNC_BATCH_BUDGET')
            feature=torch.stack([self.features[2*i:2*i+10].reshape(50,384) for i in indices]).to('cuda',torch.float16)
            with torch.inference_mode(),torch.nn.attention.sdpa_kernel(torch.nn.attention.SDPBackend.MATH):
                predicted=unet(torch.cat(latents,dim=0),torch.zeros(1,device='cuda',dtype=torch.long),
                    encoder_hidden_states=feature+positional[:,:50]).sample
                if not bool(torch.isfinite(predicted).all()):raise ValueError('LIPSYNC_NONFINITE_PREDICTION')
                decoded=vae.decode(predicted.to(torch.float32)/vae.config.scaling_factor).sample
                if not bool(torch.isfinite(decoded).all()):raise ValueError('LIPSYNC_NONFINITE_DECODE')
                result=((decoded/2+.5).clamp(0,1)*255).round().to(torch.uint8).permute(0,2,3,1).cpu().numpy()
            metadata['calls']['unet']+=1;metadata['calls']['vae_decoder']+=1;metadata['batch_frames'].append(len(indices))
            if not np.isfinite(result).all():raise ValueError('LIPSYNC_NONFINITE_RESULT')
            return result

        def finish(self):
            torch.cuda.synchronize();metadata['cuda_peak_allocated_bytes']=torch.cuda.max_memory_allocated()
            return metadata
    return Predictor(),metadata
