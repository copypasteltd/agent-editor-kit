"""Transport source point footprints through the actual transition kernels.

Private linear lanes carry point density beside real premultiplied RGBA.
Colour-dependent decisions still read the real four colour/alpha channels.
Generated matte pixels have zero source density. No surrogate RGB image or
second implementation of wipe/warp/noise formulae is used.
"""
import math
from numbers import Real
import numpy as np

from .float_transitions import _tile, mix, premultiply, resolve, MAX_WORKING_BYTES
from .errors import AppError

PROTOCOL = 'native-transition-point-footprint-v1'
TILE = 16384
MAX_POINTS = 3


def error(message, code='ARGUMENT'):
    return AppError('FLOAT_TRACKING_TRACE_'+code, message, exit_code=2)


def trace(a, b, progress, *, kind, branch, points=None, density=None,
          retain=False, cut_fraction=.5, max_working_bytes, cancel):
    """Return mass/centroid per point and optional fields for a following edge.

    A point starts as a bilinear tent on its projected input canvas, multiplied
    by the actual input alpha. A retained field is already alpha weighted.
    Public source arrays are untouched. Private density uses Float64; geometry
    is a mass centroid and does not assert identity of a naturally occluded ROI.
    """
    if not callable(cancel):raise error('来源追溯需要取消轮询回调')
    cancel(); kind=resolve({'type':kind})
    if any(not isinstance(v,np.ndarray) or v.ndim!=3 or v.dtype!=np.float32 or
           v.shape[-1]!=4 or not v.flags.c_contiguous for v in (a,b)) or a.shape!=b.shape:
        raise error('来源追溯需要匹配的实际Float32图层')
    h,w=a.shape[:2]
    if min(h,w)<1 or max(h,w)>16384 or h*w>16777216:raise error('来源追溯画布超限','BUDGET')
    if (points is None)==(density is None):raise error('需要且只能提供初始点或传递密度')
    if points is not None:
        if not isinstance(points,(list,tuple)) or not 1<=len(points)<=MAX_POINTS:raise error('来源点数量无效')
        if any(not isinstance(p,(tuple,list)) or len(p)!=2 or any(isinstance(v,(bool,np.bool_)) or
            not isinstance(v,(int,float,np.integer,np.floating)) or not math.isfinite(v) for v in p) for p in points):
            raise error('来源点必须为有限像素坐标')
        n=len(points)
    else:
        if not isinstance(density,np.ndarray) or density.ndim!=3:raise error('传递密度格式不符')
        n=density.shape[2]
    if type(branch) is not int or branch not in (0,1) or not 1<=n<=MAX_POINTS:
        raise error('来源追溯参数超限')
    for value in (progress,cut_fraction):
        if isinstance(value,(bool,np.bool_)) or not isinstance(value,Real) or not math.isfinite(value) or not 0<=value<=1:
            raise error('来源追溯进度无效')
    if density is not None and (density.shape!=(h,w,n) or density.dtype!=np.float64):
        raise error('传递密度格式不符')
    if type(retain) is not bool or type(max_working_bytes) is not int or not 1<=max_working_bytes<=MAX_WORKING_BYTES:
        raise error('来源追溯预算无效','BUDGET')
    fixed=a.nbytes+b.nbytes+(0 if density is None else density.nbytes)
    if retain:fixed+=h*w*n*8
    scratch=max(1048576,(w+1)*(4+n)*8*8)
    capacity=(max_working_bytes-fixed-scratch)//(512*(4+n))
    if capacity<1:raise error('真实图层与来源追溯工作区超出预算','BUDGET')
    tile=min(TILE,capacity,w*h)
    output=np.empty((h*w,n),np.float64) if retain else None
    src=(a.reshape(-1,4),b.reshape(-1,4)); saved=None if density is None else density.reshape(-1,n)
    for first in range(0,h*w,tile):
        cancel()
        for value in src:
            v=value[first:first+tile]
            if not np.isfinite(v).all() or np.any(v[:,3]<0) or np.any(v[:,3]>1):raise error('实际图层包含无效像素','VALUES')
            if kind in ('fadefast','fadeslow') and np.any(((v[:,:3]<0)|(v[:,:3]>1))&(v[:,3:4]>0)):
                raise error('该转场需要可见RGB处于0..1','DOMAIN')
        if saved is not None and (not np.isfinite(saved[first:first+tile]).all() or np.any(saved[first:first+tile]<0)):
            raise error('传递密度包含无效值','VALUES')
    def fetch(which,x,y):
        rgba=premultiply(src[which][y*w+x])
        aux=np.zeros((len(x),n),np.float64)
        if which==branch:
            if saved is not None:aux[:]=saved[y*w+x]
            else:
                for j,(px,py) in enumerate(points):
                    aux[:,j]=np.maximum(0,1-np.abs(x-px))*np.maximum(0,1-np.abs(y-py))*rgba[:,3]
        return np.concatenate((rgba,aux),axis=1)
    mass=np.zeros(n,np.float64);sx=mass.copy();sy=mass.copy();blur_row=None
    p=1.-float(progress)
    def blur(which,row,size):
        xx=np.arange(w,dtype=np.int64);yy=np.full(w,row,np.int64)
        values=fetch(which,xx,yy)
        sums=np.empty((w+1,4+n),np.float64);sums[0]=0
        np.cumsum(values,axis=0,out=sums[1:])
        end=np.minimum(w,xx+size)
        return (sums[end]-sums[xx])/(end-xx)[:,None]
    for first in range(0,w*h,tile):
        cancel();indices=np.arange(first,min(w*h,first+tile),dtype=np.int64);y,x=np.divmod(indices,w)
        aa,bb=fetch(0,x,y),fetch(1,x,y)
        if progress in (0.,1.):values=(aa,bb)[int(progress)]
        elif kind=='hblur':
            values=np.empty_like(aa);size=1+int((w//2)*2*min(p,1.-p))
            for row in np.unique(y):
                cancel()
                if blur_row is None or blur_row[0]!=row:
                    blur_row=(row,mix(blur(0,int(row),size),blur(1,int(row),size),p))
                chosen=y==row;values[chosen]=blur_row[1][x[chosen]]
        else:values=_tile(kind,aa,bb,x,y,w,h,p,float(cut_fraction),fetch,float(progress))
        field=values[:,4:]
        if not np.isfinite(field).all() or np.any(field<0):raise error('转场来源密度无效','VALUES')
        mass+=field.sum(axis=0);sx+=(field*x[:,None]).sum(axis=0);sy+=(field*y[:,None]).sum(axis=0)
        if retain:output[first:first+len(x)]=field
    rows=[dict(mass=float(m),coverage=min(1.,float(m)),
               x=float(sx[j]/m) if m>0 else None,y=float(sy[j]/m) if m>0 else None)
          for j,m in enumerate(mass)]
    cancel()
    return rows,output.reshape(h,w,n) if retain else None,dict(protocol=PROTOCOL,type=kind,
        progress=float(progress),branch=branch,points=n,canvas_pixels=w*h,
        generated_matte_has_source=False,real_RGBA_controls_colour_dependent_decisions=True,
        footprint='bilinear tent; alpha weighted; Float64 transported density; mass centroid',
        retained_density=retain,estimated_working_bytes=fixed+scratch+tile*(512*(4+n)),GPU=False)
