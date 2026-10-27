"""Bounded RGBA streaming with neural mouth patches and protected pixels."""
import hashlib,math

from .local_lipsync import box_at


def expanded_box(box,width,height):
    x0,y0,x1,y1=box;cx=(x0+x1)/2;cy=(y0+y1)/2;half=max(x1-x0,y1-y0)*.75
    return max(0,math.floor(cx-half)),max(0,math.floor(cy-half)),min(width,math.ceil(cx+half)),min(height,math.ceil(cy+half))


def process_frames(source,sink,*,width,height,frames,boxes,options,predictor,batch_size,budget,progress=lambda _:None):
    import cv2
    import numpy as np
    source_digest=hashlib.sha256();output_digest=hashlib.sha256();alpha_digest=hashlib.sha256();output_alpha=hashlib.sha256()
    changed=0;mask_pixels=0;calls=0;peak=0;minimum=width*height;maximum=0
    raster=width*height*4
    if (batch_size+3)*raster+width*height*16+16*1024**2>budget:
        raise ValueError('LIPSYNC_ARRAY_BUDGET_EXCEEDED')
    for start in range(0,frames,batch_size):
        records=[];latents=[];indices=[]
        for index in range(start,min(start+batch_size,frames)):
            raw=source.read(raster)
            if len(raw)<raster:
                remaining=raster-len(raw);pieces=[raw]
                while remaining:
                    part=source.read(remaining)
                    if not part:break
                    pieces.append(part);remaining-=len(part)
                raw=b''.join(pieces)
            if len(raw)!=raster:raise ValueError('LIPSYNC_SOURCE_TRUNCATED')
            source_digest.update(raw);image=np.frombuffer(raw,dtype=np.uint8).reshape(height,width,4).copy()
            alpha_digest.update(image[:,:,3].tobytes());box=box_at(boxes,index);x0,y0,x1,y1=box
            left,top,right,bottom=expanded_box(box,width,height)
            crop=cv2.resize(image[y0:y1,x0:x1,:3],(256,256),interpolation=cv2.INTER_LANCZOS4)
            latent,semantic=predictor.source(crop,image[top:bottom,left:right,:3])
            semantic=np.asarray(semantic)
            if semantic.dtype!=np.uint8 or semantic.shape!=(512,512):raise ValueError('LIPSYNC_SEMANTIC_MASK_INVALID')
            mask=cv2.resize(semantic,(right-left,bottom-top),interpolation=cv2.INTER_LINEAR)[y0-top:y1-top,x0-left:x1-left].astype(np.float32)/255
            mask[:round(mask.shape[0]*options['mask_top'])]=0
            if options['feather_pixels']:
                sigma=options['feather_pixels'];kernel=math.ceil(3*sigma)*2+1
                mask=cv2.GaussianBlur(mask,(kernel,kernel),sigmaX=sigma,borderType=cv2.BORDER_CONSTANT)
            # Invisible source RGB and all alpha samples remain unmodified.
            mask*=image[y0:y1,x0:x1,3]>0
            count=int(np.count_nonzero(mask));minimum=min(minimum,count);maximum=max(maximum,count);mask_pixels+=count
            records.append((image,box,mask));latents.append(latent);indices.append(index)
            allocated=sum(r[0].nbytes+r[2].nbytes for r in records)+raster*2+(right-left)*(bottom-top)*16+16*1024**2
            peak=max(peak,allocated)
            if peak>budget:raise ValueError('LIPSYNC_ARRAY_BUDGET_EXCEEDED')
        generated=predictor.predict(latents,indices);calls+=1
        if not isinstance(generated,np.ndarray) or generated.dtype!=np.uint8 or generated.shape!=(len(records),256,256,3):
            raise ValueError('LIPSYNC_NEURAL_FRAME_CONTRACT_INVALID')
        for frame,(image,box,mask),index in zip(generated,records,indices):
            x0,y0,x1,y1=box;original=image[y0:y1,x0:x1,:3].copy()
            patch=cv2.resize(frame,(x1-x0,y1-y0),interpolation=cv2.INTER_LANCZOS4)
            alpha=mask[:,:,None].astype(np.float64)
            blended=np.rint(original.astype(np.float64)*(1-alpha)+patch.astype(np.float64)*alpha).clip(0,255).astype(np.uint8)
            changed+=int(np.count_nonzero(np.any(blended!=original,axis=-1)))
            image[y0:y1,x0:x1,:3]=blended
            output_alpha.update(image[:,:,3].tobytes());raw=image.tobytes();output_digest.update(raw)
            written=sink.write(raw)
            if written is not None and written!=len(raw):raise ValueError('LIPSYNC_SHORT_OUTPUT_WRITE')
            progress(index+1)
    if source.read(1):raise ValueError('LIPSYNC_SOURCE_EXTRA_FRAMES')
    if hasattr(sink,'flush'):sink.flush()
    return dict(frames=frames,width=width,height=height,rgba_bytes=raster*frames,source_rgba_sha256='sha256:'+source_digest.hexdigest(),
        rgba_sha256='sha256:'+output_digest.hexdigest(),input_alpha_sha256='sha256:'+alpha_digest.hexdigest(),
        output_alpha_sha256='sha256:'+output_alpha.hexdigest(),changed_RGB_pixels=changed,semantic_mask_pixels=mask_pixels,
        minimum_mask_pixels=minimum,maximum_mask_pixels=maximum,batches=calls,model_frames=frames,
        owned_array_peak_bytes=peak,owned_array_budget_bytes=budget,alpha_mode='straight',outside_region_RGB='preserve',
        blend_domain='encoded-8bit-SDR-RGB',source_alpha='bit-exact')
