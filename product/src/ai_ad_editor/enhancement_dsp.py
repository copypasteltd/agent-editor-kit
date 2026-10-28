"""Fixed full-band DF3 frontend and bounded independently processed channel OLA.

Analysis/window/normalization follow the reviewed pyDF/libDF algorithms.
The CPU frontend is separate from the actual CUDA neural graph.
"""
import math
from pathlib import Path

RATE=48000
HOP=480
FFT=960

def window():
    import numpy as np
    x=np.arange(FFT,dtype=np.float64)
    return np.sin(.5*np.pi*np.sin(np.pi*(x+.5)/FFT)**2).astype(np.float32)

def analysis(pcm):
    import numpy as np
    if pcm.dtype!=np.float32 or pcm.ndim!=2 or not 1<=pcm.shape[0]<=2 or not pcm.shape[1] or not np.isfinite(pcm).all():
        raise ValueError('ENHANCEMENT_FRONTEND_INPUT_INVALID')
    # pyDF.analysis consumes complete hops, starting with a zero history hop.
    padded=np.pad(pcm,((0,0),(HOP,FFT)))
    count=(pcm.shape[1]+FFT)//HOP
    framed=np.lib.stride_tricks.sliding_window_view(padded,FFT,axis=1)[:,::HOP][:,:count]
    return (np.fft.rfft(framed*window(),axis=-1)/FFT).astype(np.complex64)

def features(spec,bank):
    import numpy as np
    if spec.ndim!=3 or spec.shape[-1]!=481 or bank.shape!=(481,32):raise ValueError('ENHANCEMENT_FEATURE_SHAPE')
    energies=np.matmul(spec.real**2+spec.imag**2,bank)
    erb=(10*np.log10(energies+np.float32(1e-10))).astype(np.float32)
    low=spec[...,:96].copy()
    mean=np.broadcast_to(np.linspace(-60,-90,32,dtype=np.float32),(spec.shape[0],32)).copy()
    unit=np.broadcast_to(np.linspace(.001,.0001,96,dtype=np.float32),(spec.shape[0],96)).copy()
    alpha=np.float32(.99); decay=np.float32(1)-alpha
    for t in range(spec.shape[1]):
        mean=erb[:,t]*decay+mean*alpha
        erb[:,t]=(erb[:,t]-mean)/40
        unit=np.abs(low[:,t])*decay+unit*alpha
        low[:,t]/=np.sqrt(np.maximum(unit,np.finfo(np.float32).tiny))
    return erb[:,None],np.stack((low.real,low.imag),axis=-1)[:,None]

def synthesis(spec,samples):
    import numpy as np
    if spec.dtype!=np.complex64 or spec.ndim!=3 or spec.shape[-1]!=481 or not np.isfinite(spec).all():raise ValueError('ENHANCEMENT_SYNTHESIS_INPUT')
    frames=(np.fft.irfft(spec,n=FFT,axis=-1)*FFT).astype(np.float32)*window()
    result=np.zeros((spec.shape[0],spec.shape[1]*HOP+HOP),dtype=np.float32)
    # 50% overlap: two independent slices, no unbounded history array.
    result[:,:spec.shape[1]*HOP]+=frames[...,:HOP].reshape(spec.shape[0],-1)
    result[:,HOP:]+=frames[...,HOP:].reshape(spec.shape[0],-1)
    out=result[:,HOP:HOP+samples]
    if out.shape!=(spec.shape[0],samples):raise ValueError('ENHANCEMENT_SYNTHESIS_CLOCK')
    return out

def process_pcm(source,output,*,channels,segment_seconds,overlap,strength,attenuation_limit_db,infer,check=lambda:None,progress=lambda *_:None):
    """Disk-backed symmetric OLA; network/feature state resets per segment.

    Channels are independent model batch rows, never collapsed to mono. No
    automatic level normalization, clipping, source projection or reverb claim.
    """
    import numpy as np
    from .separation_dsp import segment_ranges
    from .local_enhancement import options,settings
    options(strength=strength,attenuation_limit_db=attenuation_limit_db)
    settings(segment_seconds=segment_seconds,overlap=overlap)
    if type(channels)is not int or channels not in (1,2):raise ValueError('ENHANCEMENT_CHANNELS')
    source,output=Path(source),Path(output)
    if (source.resolve()==output.resolve() or output.exists() or not source.is_file()
            or not source.stat().st_size or source.stat().st_size%(channels*4)):
        raise ValueError('ENHANCEMENT_PCM_PATHS')
    count=source.stat().st_size//(channels*4)
    ranges=segment_ranges(count,round(segment_seconds*RATE),overlap)
    weight_path=output.with_suffix('.weights.f32')
    if weight_path.exists():raise ValueError('ENHANCEMENT_EXISTING_WEIGHTS')
    mixture=np.memmap(source,dtype='<f4',mode='r',shape=(count,channels));result=weights=None
    created=[];success=False;calls=0;silent=0;input_peak=output_peak=0.;input_power=output_power=0.
    try:
        output.touch(exist_ok=False);created.append(output)
        result=np.memmap(output,dtype='<f4',mode='w+',shape=(count,channels));result[:]=0
        weight_path.touch(exist_ok=False);created.append(weight_path)
        weights=np.memmap(weight_path,dtype='<f4',mode='w+',shape=(count,));weights[:]=0
        for i,(start,end) in enumerate(ranges):
            check();chunk=np.ascontiguousarray(mixture[start:end].T)
            if not np.isfinite(chunk).all():raise ValueError('ENHANCEMENT_NONFINITE_INPUT')
            if strength==0 or not np.any(chunk):estimate=chunk.copy();silent+=1
            else:
                estimate=np.asarray(infer(chunk),dtype=np.float32);calls+=1
                if estimate.shape!=chunk.shape or not np.isfinite(estimate).all():raise ValueError('ENHANCEMENT_MODEL_OUTPUT')
                wet=strength*(1-10**(-attenuation_limit_db/20)) if attenuation_limit_db is not None else strength
                estimate=chunk+(estimate-chunk)*np.float32(wet)
            n=end-start;indices=np.arange(n,dtype=np.float32)
            w=np.minimum(indices+1,n-indices);w/=w.max()
            result[start:end]+=estimate.T*w[:,None];weights[start:end]+=w
            progress(i+1,len(ranges));check()
        for start in range(0,count,65536):
            check();end=min(count,start+65536);w=np.asarray(weights[start:end])
            if not np.isfinite(w).all() or np.any(w<=0):raise ValueError('ENHANCEMENT_OLA_COVERAGE')
            # Explicit bypass must retain every original Float32 bit.
            if strength==0:result[start:end]=mixture[start:end]
            else:result[start:end]/=w[:,None]
            a=np.asarray(mixture[start:end]);b=np.asarray(result[start:end])
            if not np.isfinite(b).all():raise ValueError('ENHANCEMENT_NONFINITE_OUTPUT')
            input_peak=max(input_peak,float(np.abs(a).max()));output_peak=max(output_peak,float(np.abs(b).max()))
            input_power+=float(np.square(a,dtype=np.float64).sum());output_power+=float(np.square(b,dtype=np.float64).sum())
        result.flush();success=True
        return dict(samples=count,channels=channels,segments=len(ranges),model_calls=calls,bypass_segments=silent,
            input_peak=input_peak,output_peak=output_peak,input_rms=math.sqrt(input_power/(count*channels)),
            output_rms=math.sqrt(output_power/(count*channels)),segment_state='reset-per-segment',
            channel_mode='independent-model-batch-rows',ola='symmetric-positive-triangle-normalized',
            clipping=False,normalization=False,strength=strength,attenuation_limit_db=attenuation_limit_db)
    finally:
        for mapping in (mixture,result,weights):
            if mapping is not None:mapping._mmap.close()
        for path in created:
            if path==weight_path or not success:path.unlink(missing_ok=True)
