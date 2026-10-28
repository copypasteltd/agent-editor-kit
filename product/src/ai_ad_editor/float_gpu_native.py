"""Owned OpenCL 1.2 buffers for binary64 Float32-surface primitives.

This internal module is run by the per-render worker. No network, model server,
external Python package, integer media conversion or fast-math is involved.
"""
from __future__ import annotations

import ctypes as C
import hashlib
import math
import re

import numpy as np

from .errors import AppError
from .float_optics_kernel import SOURCE as OPTICAL_SOURCE
from .float_glow_kernel import SOURCE as GLOW_SOURCE

PROTOCOL = 'native-opencl-binary64-float32-primitives-v1'
MAX_PIXELS = 16777216

SOURCE = r'''
#pragma OPENCL EXTENSION cl_khr_fp64 : enable
#pragma OPENCL FP_CONTRACT OFF
double4 clean(float4 value) {
    double4 v = convert_double4(value);
    if (v.w == 0.0) v.xyz = (double3)(0.0);
    return v;
}
float4 over_value(double4 a, double4 b, double opacity) {
    double alpha = b.w * opacity;
    double total = a.w + alpha * (1.0-a.w);
    double3 numerator = b.xyz*alpha + a.xyz*a.w*(1.0-alpha);
    double3 rgb = total > 0.0 ? numerator/total : (double3)(0.0);
    return convert_float4_rte((double4)(rgb,total));
}
__kernel void over(__global const float4 *a, __global const float4 *b,
                   __global float4 *out, ulong count, double opacity, int text_order) {
    size_t i = get_global_id(0);
    if (i < count) {
        double4 bottom=clean(a[i]), top=clean(b[i]);
        float4 value;
        if(text_order) {
            double alpha=top.w*opacity, total=alpha+bottom.w*(1.0-alpha);
            double3 numerator=top.xyz*alpha+bottom.xyz*bottom.w*(1.0-alpha);
            value=convert_float4_rte((double4)(total>0.0?numerator/total:(double3)(0.0),total));
        } else value=over_value(bottom,top,opacity);
        out[i]=value;
    }
}
__kernel void affine(__global const float4 *src, __global float4 *out,
    int sw, int sh, int dw, int dh, double m00, double m01, double m02,
    double m10, double m11, double m12, int nearest) {
    size_t i = get_global_id(0);
    if (i >= (size_t)dw*dh) return;
    int x = i % dw, y = i / dw;
    double sx = (m00*x + m01*y) + m02, sy = (m10*x + m11*y) + m12;
    if (nearest) {
        long ix = (long)floor(sx+0.5), iy = (long)floor(sy+0.5);
        out[i] = ix>=0 && ix<sw && iy>=0 && iy<sh
            ? convert_float4_rte(clean(src[iy*sw+ix])) : (float4)(0.0f);
        return;
    }
    sx = clamp(sx,-2.0,(double)sw+1.0); sy = clamp(sy,-2.0,(double)sh+1.0);
    int x0 = (int)floor(sx), y0 = (int)floor(sy);
    double dx=sx-x0, dy=sy-y0;
    double weights[4]={(1.0-dx)*(1.0-dy),dx*(1.0-dy),(1.0-dx)*dy,dx*dy};
    double4 sum = (double4)(0.0);
    for (int j=0;j<4;j++) {
        int xx=x0+(j%2), yy=y0+(j/2);
        double4 v=convert_double4(src[clamp(yy,0,sh-1)*sw+clamp(xx,0,sw-1)]);
        v.xyz *= v.w;
        double weight=xx>=0 && xx<sw && yy>=0 && yy<sh ? weights[j] : 0.0;
        sum += v*weight;
    }
    if (sum.w>0.0) sum.xyz /= sum.w;
    out[i]=convert_float4_rte(sum);
}
__kernel void paint(__global const uchar *masks, __global const double4 *colors,
                    __global float4 *out, ulong count, int components, int has_base) {
    size_t i=get_global_id(0);
    if (i>=count) return;
    float4 current=has_base?out[i]:(float4)(0.0f);
    for (int j=0;j<components;j++) {
        double4 color=colors[j];
        // Match CPU's operation order: byte * (authored Float32 alpha / 255).
        color.w=(double)masks[(size_t)j*count+i]*(color.w/255.0);
        double4 previous=convert_double4(current);
        double total=color.w+previous.w*(1.0-color.w);
        double3 numerator=color.xyz*color.w+previous.xyz*previous.w*(1.0-color.w);
        current=convert_float4_rte((double4)(total>0.0?numerator/total:(double3)(0.0),total));
    }
    out[i]=current;
}
__kernel void select_words(__global float4 *normal, __global const float4 *active,
                            __global const uchar *selection, ulong count) {
    size_t i=get_global_id(0);
    if (i<count && selection[i]) normal[i]=active[i];
}
__kernel void particles(__global const float *scene, __global const uint *bins,
                       __global float4 *out, int w, int h) {
    size_t i=get_global_id(0); if(i>=(size_t)w*h)return;
    int x=i%w,y=i/w; uint tile=(y/32)*bins[0]+x/32;
    uint first=bins[3+tile],end=bins[4+tile],ids=3+bins[2];
    float4 sum=(float4)(0.0f);
    for(uint j=first;j<end;j++) {
        __global const float *p=scene+13*bins[ids+j];
        double support=(p[10]==1.0f?sqrt(2.0):1.0)*(1.0+(double)p[11]);
        double extent=fmax((double)p[2],(double)p[3])*fmax(p[12]!=0?4.0:0.0,support)+2.0;
        if(x<floor((double)p[0]-extent)||x>=ceil((double)p[0]+extent)+1.0||
           y<floor((double)p[1]-extent)||y>=ceil((double)p[1]+extent)+1.0)continue;
        float dx=(float)x-p[0],dy=(float)y-p[1];
        float a=(dx*p[4]+dy*p[5])/p[2],b=(-dx*p[5]+dy*p[4])/p[3];
        float radial=sqrt(a*a+b*b),distance=1.0f-radial;
        int shape=(int)p[10];
        if(shape==1)distance=1.0f-fmax(fabs(a),fabs(b));
        else if(shape==2)distance=1.0f-fabs(a)-fabs(b);
        else if(shape==3)distance=0.68f+0.32f*cos(5.0f*atan2(b,a))-radial;
        else if(shape==4)distance=0.16f-fabs(radial-0.82f);
        float divisor=(float)fmax((double)p[11],1.0/fmax((double)fmin(p[2],p[3]),0.0001));
        float coverage=clamp(0.5f+distance/divisor,0.0f,1.0f);
        if(p[12]!=0)coverage=1.0f-(1.0f-coverage)*(1.0f-exp(-radial*radial)*p[12]);
        float alpha=coverage*p[9],remain=1.0f-alpha;
        sum.xyz=sum.xyz*remain+(float3)(p[6],p[7],p[8])*alpha;
        sum.w=alpha+sum.w*remain;
    }
    if(sum.w>0.0f)sum.xyz/=sum.w; else sum.xyz=(float3)(0.0f);
    out[i]=sum;
}
''' + OPTICAL_SOURCE + GLOW_SOURCE


def error(code, message, **details):
    return AppError('FLOAT_GPU_'+code, message, exit_code=6, diagnostics=details or None)


class NativeGPU:
    """One owned context/queue/program; at most three retained device buffers."""

    def __init__(self, device='0.0', max_device_bytes=1024**3):
        if not isinstance(device,str) or not re.fullmatch(r'\d{1,3}\.\d{1,3}',device):
            raise error('DEVICE','OpenCL设备必须为platform.device数字索引')
        if type(max_device_bytes) is not int or not 1<=max_device_bytes<=64*1024**3:
            raise error('BUDGET','GPU工作区配额无效')
        self.limit=max_device_bytes;self.buffers=[];self.capacity=0;self.context=self.queue=self.program=None;self.kernels={}
        self.lib=C.WinDLL('OpenCL.dll')
        self._bind()
        try:
            self.device,self.info=self._device(device)
            code=C.c_int();one=(C.c_void_p*1)(self.device)
            self.context=self.lib.clCreateContext(None,1,one,None,None,C.byref(code));self._check(code.value,'context')
            self.queue=self.lib.clCreateCommandQueue(self.context,self.device,0,C.byref(code));self._check(code.value,'queue')
            data=SOURCE.encode('ascii');strings=(C.c_char_p*1)(data);length=(C.c_size_t*1)(len(data))
            self.program=self.lib.clCreateProgramWithSource(self.context,1,strings,length,C.byref(code));self._check(code.value,'program')
            result=self.lib.clBuildProgram(self.program,1,one,b'-cl-std=CL1.2',None,None)
            if result:
                size=C.c_size_t();self.lib.clGetProgramBuildInfo(self.program,self.device,0x1183,0,None,C.byref(size))
                log=C.create_string_buffer(min(size.value,65536))
                if len(log):self.lib.clGetProgramBuildInfo(self.program,self.device,0x1183,len(log),log,None)
                raise error('BUILD','OpenCL浮点内核编译失败',native_code=result,log=log.value.decode('utf8','replace'))
            for name in ('over','affine','paint','select_words','particles','optics','glow_bright','glow_blur','glow_merge'):
                self.kernels[name]=self.lib.clCreateKernel(self.program,name.encode(),C.byref(code));self._check(code.value,'kernel')
            self.metadata={'protocol':PROTOCOL,'device':self.info,'kernel_sha256':hashlib.sha256(data).hexdigest(),
                'build_options':'-cl-std=CL1.2;FP_CONTRACT OFF;no fast math',
                'arithmetic':'binary64 affine/over/text/optics/highlight-FIR-glow; binary32 particle coverage and ordered accumulation; Float32 surfaces',
                'device_quota_bytes':self.limit,'retained_device_bytes':0,'operations':{},'integer_media_conversion':False}
        except BaseException:
            self.close();raise

    def _bind(self):
        h,u,i,z,q=C.c_void_p,C.c_uint,C.c_int,C.c_size_t,C.c_ulonglong
        p=lambda t:C.POINTER(t)
        signatures={
            'clGetPlatformIDs':(i,[u,p(h),p(u)]),'clGetDeviceIDs':(i,[h,q,u,p(h),p(u)]),
            'clGetDeviceInfo':(i,[h,u,z,h,p(z)]),'clCreateContext':(h,[h,u,p(h),h,h,p(i)]),
            'clCreateCommandQueue':(h,[h,h,q,p(i)]),'clCreateProgramWithSource':(h,[h,u,p(C.c_char_p),p(z),p(i)]),
            'clBuildProgram':(i,[h,u,p(h),C.c_char_p,h,h]),'clGetProgramBuildInfo':(i,[h,h,u,z,h,p(z)]),
            'clCreateKernel':(h,[h,C.c_char_p,p(i)]),'clCreateBuffer':(h,[h,q,z,h,p(i)]),
            'clSetKernelArg':(i,[h,u,z,h]),'clEnqueueWriteBuffer':(i,[h,h,u,z,z,h,u,h,h]),
            'clEnqueueReadBuffer':(i,[h,h,u,z,z,h,u,h,h]),
            'clEnqueueNDRangeKernel':(i,[h,h,u,p(z),p(z),p(z),u,h,h]),'clFinish':(i,[h]),
        }
        for name in ('MemObject','Kernel','Program','CommandQueue','Context'):signatures['clRelease'+name]=(i,[h])
        for name,(result,args) in signatures.items():
            fn=getattr(self.lib,name);fn.restype=result;fn.argtypes=args

    def _check(self, code, stage):
        if code:raise error('NATIVE','OpenCL浮点操作失败',stage=stage,native_code=code)

    def _device(self, selection):
        count=C.c_uint();self._check(self.lib.clGetPlatformIDs(0,None,C.byref(count)),'platform count')
        if not 1<=count.value<=1024:raise error('DEVICE','OpenCL平台数量无效')
        platforms=(C.c_void_p*count.value)();self._check(self.lib.clGetPlatformIDs(count,platforms,None),'platforms')
        a,b=map(int,selection.split('.'))
        if a>=len(platforms):raise error('DEVICE','OpenCL平台不存在')
        self._check(self.lib.clGetDeviceIDs(platforms[a],0xffffffff,0,None,C.byref(count)),'device count')
        if not 1<=count.value<=1024:raise error('DEVICE','OpenCL设备数量无效')
        devices=(C.c_void_p*count.value)();self._check(self.lib.clGetDeviceIDs(platforms[a],0xffffffff,count,devices,None),'devices')
        if b>=len(devices):raise error('DEVICE','OpenCL设备不存在')
        handle=devices[b]
        def raw(key):
            length=C.c_size_t();self._check(self.lib.clGetDeviceInfo(handle,key,0,None,C.byref(length)),'info size')
            if not 1<=length.value<=65536:raise error('DEVICE','OpenCL设备信息超过预算')
            value=C.create_string_buffer(length.value);self._check(self.lib.clGetDeviceInfo(handle,key,length,value,None),'info')
            return value.raw
        info={'selection':selection}
        for name,key in [('name',0x102b),('vendor',0x102c),('driver',0x102d),('version',0x102f)]:info[name]=raw(key).rstrip(b'\0').decode('utf8','replace')
        for name,key in [('type',0x1000),('double_fp_config',0x1032),('global_memory_bytes',0x101f),('max_allocation_bytes',0x1010)]:info[name]=int.from_bytes(raw(key),'little')
        if not info['type']&4 or info['double_fp_config']&7!=7:raise error('DEVICE','需要支持IEEE binary64的GPU')
        return handle,info

    def _reserve(self, size):
        size=max(256,int(size))
        if size*3>self.limit or size>self.info['max_allocation_bytes'] or size*3>self.info['global_memory_bytes']:
            raise error('BUDGET','GPU三个缓冲区超过明确配额或设备上限',required_bytes=size*3,limit=self.limit)
        if size<=self.capacity:return
        for buffer in self.buffers:self.lib.clReleaseMemObject(buffer)
        self.buffers=[];self.capacity=0
        self.metadata['retained_device_bytes']=0
        try:
            for _ in range(3):
                code=C.c_int();buffer=self.lib.clCreateBuffer(self.context,1,size,None,C.byref(code));self._check(code.value,'buffer')
                self.buffers.append(buffer)
            self.capacity=size;self.metadata['retained_device_bytes']=size*3
        except BaseException:
            for buffer in self.buffers:self.lib.clReleaseMemObject(buffer)
            self.buffers=[];raise

    def _write(self, index, value):
        self._check(self.lib.clEnqueueWriteBuffer(self.queue,self.buffers[index],1,0,value.nbytes,C.c_void_p(value.ctypes.data),0,None,None),'upload')

    def _run(self, name, arguments, count, output, *, buffer=2):
        kernel=self.kernels[name]
        for index,value in enumerate(arguments):self._check(self.lib.clSetKernelArg(kernel,index,C.sizeof(value),C.byref(value)),'argument')
        size=(C.c_size_t*1)(count)
        self._check(self.lib.clEnqueueNDRangeKernel(self.queue,kernel,1,None,size,None,0,None,None),'enqueue')
        if output is not None:
            self._check(self.lib.clEnqueueReadBuffer(self.queue,self.buffers[buffer],1,0,output.nbytes,C.c_void_p(output.ctypes.data),0,None,None),'download')
        self.metadata['operations'][name]=self.metadata['operations'].get(name,0)+1

    @staticmethod
    def surface(value):
        if not isinstance(value,np.ndarray) or value.dtype!=np.float32 or value.ndim!=3 or value.shape[-1]!=4 or not value.flags.c_contiguous:
            raise error('SURFACE','GPU输入须为连续H×W×4 Float32')
        if min(value.shape[:2])<1 or max(value.shape[:2])>16384 or value.shape[0]*value.shape[1]>MAX_PIXELS:
            raise error('BUDGET','GPU表面超过尺寸预算')
        rows=value.reshape(-1,4)
        for start in range(0,len(rows),65536):
            tile=rows[start:start+65536]
            if not np.isfinite(tile).all() or np.any(tile[:,3]<0) or np.any(tile[:,3]>1):raise error('SURFACE','RGB须有限，alpha须在0..1')

    @staticmethod
    def output(value):
        if (not isinstance(value,np.ndarray) or value.dtype!=np.float32 or value.ndim!=3 or value.shape[-1]!=4
                or not value.flags.c_contiguous or not value.flags.writeable or min(value.shape[:2])<1
                or max(value.shape[:2])>16384 or value.shape[0]*value.shape[1]>MAX_PIXELS):
            raise error('SURFACE','GPU输出须为可写连续H×W×4 Float32，且在尺寸预算内')

    def over(self, a, b, output, opacity=1., *, text_order=False):
        self.surface(a);self.surface(b);self.output(output)
        if a.shape!=b.shape or output.shape!=a.shape:raise error('SURFACE','GPU合成尺寸不一致')
        if isinstance(opacity,(bool,np.bool_)) or not math.isfinite(float(opacity)) or not 0<=opacity<=1:raise error('ALPHA','GPU透明度无效')
        if type(text_order) is not bool:raise error('ALPHA','GPU alpha顺序须为布尔值')
        self._reserve(a.nbytes);self._write(0,a);self._write(1,b)
        self._run('over',[C.c_void_p(self.buffers[0]),C.c_void_p(self.buffers[1]),C.c_void_p(self.buffers[2]),C.c_ulonglong(a.shape[0]*a.shape[1]),C.c_double(opacity),C.c_int(text_order)],a.shape[0]*a.shape[1],output)

    def affine(self, source, output, inverse, nearest=False):
        self.surface(source);self.output(output)
        matrix=np.asarray(inverse)
        if matrix.shape!=(2,3) or matrix.dtype.kind not in 'fiu' or not np.isfinite(matrix).all() or np.max(np.abs(matrix))>1e9:
            raise error('GEOMETRY','GPU逆矩阵须为2×3有限数值')
        matrix=matrix.astype(np.float64)
        if matrix[0,0]*matrix[1,1]-matrix[0,1]*matrix[1,0]==0:raise error('GEOMETRY','GPU逆矩阵不可退化')
        if type(nearest) is not bool:raise error('GEOMETRY','GPU nearest须为布尔值')
        h,w=source.shape[:2];dh,dw=output.shape[:2]
        if output.dtype!=np.float32 or output.shape!=(dh,dw,4) or not output.flags.c_contiguous or min(dw,dh)<1 or max(dw,dh)>16384 or dw*dh>MAX_PIXELS:
            raise error('SURFACE','GPU输出尺寸或表示无效')
        self._reserve(max(source.nbytes,output.nbytes));self._write(0,source)
        args=[C.c_void_p(self.buffers[0]),C.c_void_p(self.buffers[2]),*(C.c_int(v) for v in (w,h,dw,dh)),*(C.c_double(v) for v in matrix.ravel()),C.c_int(bool(nearest))]
        self._run('affine',args,dw*dh,output)

    def paint(self, masks, colors, output, *, base=None):
        self.output(output)
        if not isinstance(masks,np.ndarray) or masks.dtype!=np.uint8 or masks.ndim!=3 or not masks.flags.c_contiguous or not 1<=len(masks)<=4 or tuple(masks.shape[1:])!=tuple(output.shape[:2]):
            raise error('MASK','GPU组件需要1..4张同尺寸字节覆盖率')
        colors=np.ascontiguousarray(colors,dtype=np.float64)
        if colors.shape!=(len(masks),4) or not np.isfinite(colors).all() or np.any(colors[:,3]<0) or np.any(colors[:,3]>1):raise error('COLOR','GPU组件颜色无效')
        self._reserve(max(output.nbytes,masks.nbytes,colors.nbytes));self._write(0,masks);self._write(1,colors)
        if base is not None:
            self.surface(base)
            if base.shape!=output.shape:raise error('SURFACE','GPU文字底图尺寸不一致')
            self._write(2,base)
        count=output.shape[0]*output.shape[1]
        self._run('paint',[C.c_void_p(self.buffers[0]),C.c_void_p(self.buffers[1]),C.c_void_p(self.buffers[2]),C.c_ulonglong(count),C.c_int(len(masks)),C.c_int(base is not None)],count,output)

    def select(self, normal, active, selection, output):
        self.surface(normal);self.surface(active);self.output(output)
        if active.shape!=normal.shape or output.shape!=normal.shape or not isinstance(selection,np.ndarray) or selection.dtype!=np.uint8 or selection.shape!=normal.shape[:2] or not selection.flags.c_contiguous or np.any((selection!=0)&(selection!=255)):
            raise error('MASK','GPU逐词选择需要同尺寸表面及0/255蒙版')
        self._reserve(normal.nbytes);self._write(0,normal);self._write(1,active);self._write(2,selection)
        count=normal.shape[0]*normal.shape[1]
        self._run('select_words',[C.c_void_p(self.buffers[0]),C.c_void_p(self.buffers[1]),C.c_void_p(self.buffers[2]),C.c_ulonglong(count)],count,output,buffer=0)

    def particles(self, scene, tiles, output):
        from .procedural_particles import validate_scene
        self.output(output); h,w=output.shape[:2]
        validate_scene(scene,tiles,(w,h))
        self._reserve(max(scene.nbytes,tiles.nbytes,output.nbytes));self._write(0,scene);self._write(1,tiles)
        self._run('particles',[C.c_void_p(self.buffers[0]),C.c_void_p(self.buffers[1]),
            C.c_void_p(self.buffers[2]),C.c_int(w),C.c_int(h)],w*h,output)

    def optics(self, source, output, kind, values, ghosts=0, edge='clamp'):
        from .float_optics import validate_state,FIELDS,KINDS
        values=validate_state(kind,values,ghosts,edge)
        self.surface(source);self.output(output)
        if source.shape!=output.shape:raise error('SURFACE','GPU光学输入输出尺寸不一致')
        params=np.array([values.get(k,0.) for k in FIELDS],np.float64)
        self._reserve(max(source.nbytes,params.nbytes));self._write(0,source);self._write(1,params)
        h,w=source.shape[:2]
        self._run('optics',[C.c_void_p(self.buffers[0]),C.c_void_p(self.buffers[1]),C.c_void_p(self.buffers[2]),
            C.c_int(w),C.c_int(h),C.c_int(KINDS.index(kind)),C.c_int(ghosts),C.c_int(edge=='transparent')],w*h,output)

    def glow(self, source, output, kind, values, edge, primaries,*,white_xy=None):
        from .float_glow import validate_state,luma_coefficients,admit_neighborhood
        values=validate_state(kind,values,edge)
        coefficients=luma_coefficients(primaries,white_xy)
        self.surface(source);self.output(output)
        if source.shape!=output.shape:raise error('SURFACE','GPU高光扩散输入输出尺寸不一致')
        h,w=source.shape[:2];count=w*h
        support,_,norm,_=admit_neighborhood(count,values['radius'])
        self._reserve(source.nbytes);self._write(0,source)
        pointer=lambda i:C.c_void_p(self.buffers[i])
        signal=[C.c_double(v) for v in (values['threshold'],values['knee'],*coefficients)]
        # Keep source in buffer 0; all intermediates stay on device. In-order
        # queue semantics make the single final blocking read sufficient.
        self._run('glow_bright',[pointer(0),pointer(1),C.c_ulonglong(count),*signal],count,None)
        for axis,src,dest in ((1,1,2),(0,2,1)):
            self._run('glow_blur',[pointer(src),pointer(dest),C.c_int(w),C.c_int(h),C.c_int(axis),
                C.c_int(support),C.c_double(values['radius']),C.c_double(norm),C.c_int(edge=='transparent')],count,None)
        self._run('glow_merge',[pointer(0),pointer(1),pointer(2),C.c_ulonglong(count),C.c_int(kind=='halation'),
            *signal,*(C.c_double(values[k]) for k in ('intensity','gain','red','green','blue')),
            C.c_double(values.get('core_suppression',0.))],count,output)

    def close(self):
        if not hasattr(self,'lib'):return
        for buffer in self.buffers:self.lib.clReleaseMemObject(buffer)
        self.buffers=[]
        for kernel in self.kernels.values():self.lib.clReleaseKernel(kernel)
        self.kernels={}
        for field,name in [('program','Program'),('queue','CommandQueue'),('context','Context')]:
            value=getattr(self,field,None)
            if value:getattr(self.lib,'clRelease'+name)(value);setattr(self,field,None)

    def __enter__(self):return self
    def __exit__(self,*_):self.close()
