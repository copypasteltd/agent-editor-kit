"""Bounded streaming frame pairs; anchors, cuts and final interval are explicit."""
import hashlib

def read_frame(source,size):
    result=bytearray()
    while len(result)<size:
        part=source.read(size-len(result))
        if not part:raise ValueError('INTERPOLATION_TRUNCATED_SOURCE')
        result.extend(part)
    return result

def process_frames(source,sink,*,width,height,frames,factor,predictor,options,budget,progress=lambda _:None):
    import numpy as np
    from .interpolation_plan import normalize_options
    options=normalize_options(**options)
    if any(type(v)is not int for v in (width,height,frames,factor,budget)) or not 32<=width<=4096 or not 32<=height<=4096 or not 1<=frames<=15000 or not 2<=factor<=8:raise ValueError('INTERPOLATION_FRAME_CONTRACT')
    explicit=options['cut_after_frame']
    if any(v>=frames-1 for v in explicit):raise ValueError('INTERPOLATION_CUT_RANGE')
    raster=width*height*4;peak=raster*18+16*1024**2
    if peak>budget:raise ValueError('INTERPOLATION_ARRAY_BUDGET')
    original=hashlib.sha256();encoded=hashlib.sha256();anchors=hashlib.sha256()
    emitted=0;generated=0;cuts=[];static=[];score_summary=[];queries={}
    def emit(image,anchor=False):
        nonlocal emitted
        if not isinstance(image,np.ndarray) or image.shape!=(height,width,4) or image.dtype!=np.uint8:raise ValueError('INTERPOLATION_NEURAL_FRAME_CONTRACT')
        raw=image.tobytes();encoded.update(raw)
        if anchor:anchors.update(raw)
        offset=0
        while offset<len(raw):
            count=sink.write(raw[offset:])
            if count is None:count=len(raw)-offset
            if type(count)is not int or not 0<count<=len(raw)-offset:raise ValueError('INTERPOLATION_SHORT_OUTPUT_WRITE')
            offset+=count
        emitted+=1;progress(emitted)
    left=np.frombuffer(read_frame(source,raster),dtype=np.uint8).reshape(height,width,4)
    for i in range(frames):
        original.update(left.tobytes());emit(left,True)
        if i==frames-1:
            for _ in range(factor-1):emit(left)
            break
        right=np.frombuffer(read_frame(source,raster),dtype=np.uint8).reshape(height,width,4)
        score=float(np.abs(left[:,:,:3].astype(np.int16)-right[:,:,:3].astype(np.int16)).mean()/255)
        cut=i in explicit or options['scene_cut_threshold'] is not None and score>=options['scene_cut_threshold']
        if cut:
            cuts.append(i);score_summary.append(dict(after_frame=i,mean_RGB_difference=score,explicit=i in explicit))
        equal=np.array_equal(left,right)
        if equal:static.append(i)
        if cut or equal:
            for _ in range(factor-1):emit(left)
        else:
            count=0
            for image in predictor.interpolate(left,right,[(k,factor) for k in range(1,factor)]):
                if count>=factor-1:raise ValueError('INTERPOLATION_EXTRA_NEURAL_FRAME')
                emit(image);count+=1;generated+=1
                key=str(count)+'/'+str(factor);queries[key]=queries.get(key,0)+1
            if count!=factor-1:raise ValueError('INTERPOLATION_MISSING_NEURAL_FRAME')
        left=right
    if source.read(1):raise ValueError('INTERPOLATION_SOURCE_EXTRA_FRAMES')
    if hasattr(sink,'flush'):sink.flush()
    return dict(width=width,height=height,source_frames=frames,frames=emitted,factor=factor,rgba_bytes=emitted*raster,
        source_rgba_sha256='sha256:'+original.hexdigest(),anchor_rgba_sha256='sha256:'+anchors.hexdigest(),rgba_sha256='sha256:'+encoded.hexdigest(),
        flow_forwards=generated,generated_frames=generated,time_queries=queries,cut_after_frames=cuts,static_pairs=static,cut_scores=score_summary,
        held_inserted_frames=(len(set(cuts+static))+1)*(factor-1),final_interval='hold-last-source-frame',
        anchors='bit-exact-decoded-RGBA',synthesized_alpha='flow-mask-premultiplied-RGBA-zero-hidden-RGB',
        owned_array_peak_bytes=peak,owned_array_budget_bytes=budget)
