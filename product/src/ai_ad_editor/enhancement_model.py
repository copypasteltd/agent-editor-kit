"""Actual fixed 48 kHz DeepFilterNet3 CUDA model, with explicit CPU frontend."""
from pathlib import Path
import time

def load_predictor(model_path,settings,*,phase=lambda _:None):
    import numpy as np
    import torch,safetensors
    from .enhancement_graph import DfNet
    from .enhancement_dsp import analysis,features,synthesis
    from .cuda_admission import admit_cuda
    if not torch.cuda.is_available():raise ValueError('ENHANCEMENT_CUDA_UNAVAILABLE_NO_FALLBACK')
    torch.set_num_threads(settings['threads']);torch.set_num_interop_threads(1)
    torch.backends.cuda.matmul.allow_tf32=False;torch.backends.cudnn.allow_tf32=False
    torch.backends.cudnn.benchmark=False;torch.backends.cudnn.deterministic=True
    torch.manual_seed(0);torch.cuda.reset_peak_memory_stats()
    admission=admit_cuda(torch,1024**3,'speech-enhancement-load')
    started=time.monotonic();phase('loading-fixed-deepfilternet3')
    with torch.device('meta'):net=DfNet(torch.zeros(481,32),torch.zeros(32,481))
    with safetensors.safe_open(str(Path(model_path)/'model.safetensors'),framework='pt',device='cpu',backend='pread') as reader:
        state={k:reader.get_tensor(k) for k in reader.keys()}
    if len(state)!=133 or any(v.dtype not in (torch.float32,torch.int64) or not torch.isfinite(v).all() for v in state.values()):raise ValueError('ENHANCEMENT_WEIGHT_CONTRACT')
    net.load_state_dict(state,strict=True,assign=True);del state
    bank=net.erb_fb.numpy().copy()
    expected=np.zeros((481,32),dtype=np.float32);inverse=net.mask.erb_inv_fb.numpy()
    if not np.isin(inverse,[0.,1.]).all() or not np.all(inverse.sum(axis=0)==1):raise ValueError('ENHANCEMENT_FIXED_ERB_BANK')
    for i in range(32):expected[:,i]=inverse[i]/inverse[i].sum()
    if not np.array_equal(expected,bank):raise ValueError('ENHANCEMENT_FIXED_ERB_NORMALIZATION')
    net.to('cuda').eval().requires_grad_(False)
    metadata=dict(engine='deepfilternet3-native-cuda-v1',device=torch.cuda.get_device_name(0),precision='float32',CPU_fallback=False,
        neural_backend='cuda',frontend_backend='numpy-cpu',sample_rate=48000,model_loads=1,model_forwards=0,channel_forwards=0,
        CUDA_admission=admission,load_seconds=time.monotonic()-started,weight_reader='safetensors-pread',
        versions=dict(torch=torch.__version__,numpy=np.__version__,safetensors=safetensors.__version__))
    class Predictor:
        def __call__(self,chunk):
            spec=analysis(chunk);erb,low=features(spec,bank)
            pair=np.stack((spec.real,spec.imag),axis=-1)[:,None]
            with torch.inference_mode():
                inputs=[torch.from_numpy(np.ascontiguousarray(v)).to('cuda') for v in (pair,erb,low)]
                result=net(*inputs)[0]
                if result.shape!=inputs[0].shape or not torch.isfinite(result).all():raise ValueError('ENHANCEMENT_NONFINITE_MODEL_OUTPUT')
                output=torch.view_as_complex(result.squeeze(1).contiguous()).cpu().numpy()
            metadata['model_forwards']+=1;metadata['channel_forwards']+=chunk.shape[0]
            return synthesis(output,chunk.shape[-1])
        def finish(self):
            torch.cuda.synchronize();metadata['cuda_peak_allocated_bytes']=torch.cuda.max_memory_allocated();return metadata
    return Predictor(),metadata
