"""Actual fixed RIFE4.25 CUDA flow and premultiplied-alpha transport."""
from pathlib import Path
import math,time
def load_predictor(model_path,settings,*,width,height,phase=lambda _:None):
    import numpy as np
    import torch,safetensors
    from .interpolation_graph import IFNet,warp
    from .cuda_admission import admit_cuda
    if not torch.cuda.is_available():raise ValueError('INTERPOLATION_CUDA_UNAVAILABLE_NO_FALLBACK')
    started=time.monotonic();torch.set_num_threads(settings['threads']);torch.set_num_interop_threads(1)
    torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False
    torch.backends.cudnn.benchmark=False;torch.backends.cudnn.deterministic=True
    torch.manual_seed(0);torch.cuda.reset_peak_memory_stats()
    multiple=int(64/settings['scale']);pw=math.ceil(width/multiple)*multiple;ph=math.ceil(height/multiple)*multiple
    admission=admit_cuda(torch,1024**3+math.ceil(pw*ph*(256+384*settings['scale']**2)),'interpolation-load')
    phase('loading-local-rife425')
    with torch.device('meta'):net=IFNet()
    with safetensors.safe_open(str(Path(model_path)/'model.safetensors'),framework='pt',device='cpu',backend='pread') as reader:
        state={k:reader.get_tensor(k) for k in reader.keys()}
    if len(state)!=158 or any(v.dtype!=torch.float32 for v in state.values()):raise ValueError('INTERPOLATION_WEIGHT_CONTRACT')
    net.load_state_dict(state,strict=True,assign=True);del state
    net.to('cuda').eval().requires_grad_(False)
    metadata=dict(engine='rife425-native-cuda-v1',device=torch.cuda.get_device_name(0),precision='float32',network='disabled',CPU_fallback=False,
        versions=dict(torch=torch.__version__,numpy=np.__version__,safetensors=safetensors.__version__),weight_reader='safetensors-pread',model_loads=1,
        load_seconds=time.monotonic()-started,CUDA_admission=admission,scale=settings['scale'],padded_raster=[pw,ph],padding='replicate',
        flow_forwards=0,generated_frames=0,alpha_transport='same-flow-mask-premultiplied-RGBA',time_queries={})
    class Predictor:
        def interpolate(self,a,b,timesteps):
            for image in (a,b):
                if not isinstance(image,np.ndarray) or image.dtype!=np.uint8 or image.shape!=(height,width,4):raise ValueError('INTERPOLATION_MODEL_INPUT')
            with torch.inference_mode():
                def tensor(image):
                    result=torch.from_numpy(image.copy()).to(device='cuda',dtype=torch.float32).permute(2,0,1).unsqueeze(0)/255.
                    return torch.nn.functional.pad(result,(0,pw-width,0,ph-height),mode='replicate')
                x0=tensor(a);x1=tensor(b);images=torch.cat((x0[:,:3],x1[:,:3]),1)
                p0=torch.cat((x0[:,:3]*x0[:,3:],x0[:,3:]),1);p1=torch.cat((x1[:,:3]*x1[:,3:],x1[:,3:]),1)
                for numerator,denominator in timesteps:
                    if type(numerator)is not int or type(denominator)is not int or not 0<numerator<denominator:raise ValueError('INTERPOLATION_MODEL_TIME')
                    flow,mask_logits,unused=net(images,numerator/denominator,[v/settings['scale'] for v in (16,8,4,2,1)])
                    final=flow[-1];mask=torch.sigmoid(mask_logits)
                    if not torch.isfinite(final).all() or not torch.isfinite(mask).all():raise ValueError('INTERPOLATION_NONFINITE_FLOW')
                    w0=warp(p0,final[:,:2]);w1=warp(p1,final[:,2:]);merged=w0*mask+w1*(1-mask)
                    alpha=merged[:,3:].clamp(0,1);color=torch.where(alpha>1e-8,merged[:,:3]/alpha.clamp_min(1e-8),0)
                    rgba=torch.cat((color,alpha),1)[:,:,:height,:width]
                    if not torch.isfinite(rgba).all():raise ValueError('INTERPOLATION_NONFINITE_FRAME')
                    result=(rgba.clamp(0,1)*255).round().to(torch.uint8).squeeze(0).permute(1,2,0).contiguous().cpu().numpy()
                    result[:,:,:3][result[:,:,3]==0]=0
                    metadata['flow_forwards']+=1;metadata['generated_frames']+=1
                    label=str(numerator)+'/'+str(denominator);metadata['time_queries'][label]=metadata['time_queries'].get(label,0)+1
                    yield result
                    del flow,mask_logits,unused,final,mask,w0,w1,merged,alpha,color,rgba,result
        def finish(self):
            torch.cuda.synchronize();metadata['cuda_peak_allocated_bytes']=torch.cuda.max_memory_allocated();return metadata
    return Predictor(),metadata
