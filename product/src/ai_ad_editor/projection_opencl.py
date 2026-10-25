"""Native OpenCL projection with AVExpr-authored binary64 coefficient frames.

No shader reimplementation of keyframe clocks/Bezier/trigonometry is needed.
The area prefix preserves the CPU's left-to-right rows, then top-to-bottom
columns. Three Float32 texels retain each binary64 sum without a Float32 sum.
"""
from __future__ import annotations

import hashlib
import re
from pathlib import Path

from .errors import AppError
from .media import ffmpeg_path
from .utils import atomic_write_json, atomic_write_text, run_process, sha256_file

DEFAULTS = {'mode':'off','device':'0.0','max_working_bytes':1024**3,'probe_timeout_seconds':30}
CLI_FIELDS = {'projection_acceleration':'mode','projection_device':'device'}


def configuration(raw=None):
    if raw is None:
        return dict(DEFAULTS)
    if not isinstance(raw,dict) or set(raw)-set(DEFAULTS):
        raise AppError('PROJECTION_ACCELERATION_INVALID','projection_acceleration必须为严格对象',exit_code=2)
    value={**DEFAULTS,**raw}
    if value['mode'] not in ('off','prefer','require') or not isinstance(value['mode'],str):
        raise AppError('PROJECTION_ACCELERATION_INVALID','投影模式只允许off/prefer/require',exit_code=2)
    if not isinstance(value['device'],str) or not re.fullmatch(r'[0-9]{1,3}\.[0-9]{1,3}',value['device']):
        raise AppError('PROJECTION_ACCELERATION_INVALID','OpenCL设备必须为platform.device数字索引',exit_code=2)
    for name,low,high in [('max_working_bytes',1,64*1024**3),('probe_timeout_seconds',1,120)]:
        if type(value[name]) is not int or not low<=value[name]<=high:
            raise AppError('PROJECTION_ACCELERATION_INVALID','投影配额或探测超时无效',exit_code=2,path=name)
    return value


def apply_overrides(settings,values):
    patch={field:values[key] for key,field in CLI_FIELDS.items() if values.get(key) is not None}
    if values.get('projection_memory_mib') is not None:
        number=values['projection_memory_mib']
        if type(number) is not int or not 1<=number<=65536:
            raise AppError('PROJECTION_ACCELERATION_INVALID','projection_memory_mib必须为1..65536整数',exit_code=2)
        patch['max_working_bytes']=number*1024**2
    result=configuration(settings.get('projection_acceleration'))
    if patch:
        result=configuration({**result,**patch});settings['projection_acceleration']=result
    return result


def device_info(selection):
    """Read the selected native OpenCL ICD without creating a context."""
    import ctypes
    library=ctypes.WinDLL('OpenCL.dll')
    handle=ctypes.c_void_p;uint=ctypes.c_uint;size=ctypes.c_size_t
    library.clGetPlatformIDs.argtypes=[uint,ctypes.POINTER(handle),ctypes.POINTER(uint)]
    library.clGetDeviceIDs.argtypes=[handle,ctypes.c_ulonglong,uint,ctypes.POINTER(handle),ctypes.POINTER(uint)]
    library.clGetDeviceInfo.argtypes=[handle,uint,size,handle,ctypes.POINTER(size)]
    def checked(result):
        if result!=0:raise RuntimeError('OpenCL query error '+str(result))
    platforms=uint();checked(library.clGetPlatformIDs(0,None,ctypes.byref(platforms)))
    if not 1<=platforms.value<=1024:raise RuntimeError('OpenCL platform count outside admission limit')
    rows=(handle*platforms.value)();checked(library.clGetPlatformIDs(platforms,rows,None))
    p,d=map(int,selection.split('.'))
    if p>=len(rows):raise RuntimeError('OpenCL platform index unavailable')
    count=uint();checked(library.clGetDeviceIDs(rows[p],0xffffffff,0,None,ctypes.byref(count)))
    if not 1<=count.value<=1024:raise RuntimeError('OpenCL device count outside admission limit')
    devices=(handle*count.value)();checked(library.clGetDeviceIDs(rows[p],0xffffffff,count,devices,None))
    if d>=len(devices):raise RuntimeError('OpenCL device index unavailable')
    def raw(key):
        length=size();checked(library.clGetDeviceInfo(devices[d],key,0,None,ctypes.byref(length)))
        if length.value>1024**2:raise RuntimeError('OpenCL information exceeds admission limit')
        data=ctypes.create_string_buffer(length.value)
        checked(library.clGetDeviceInfo(devices[d],key,length,data,None))
        return data.raw
    result={'selection':selection}
    for name,key in [('name',0x102b),('vendor',0x102c),('driver',0x102d),('version',0x102f)]:
        result[name]=raw(key).rstrip(b'\0').decode('utf8','replace')
    for name,key in [('type',0x1000),('image_support',0x1016),('image_max_width',0x1011),
                     ('image_max_height',0x1012),('double_fp_config',0x1032),('global_memory_bytes',0x101f)]:
        result[name]=int.from_bytes(raw(key),'little')
    if not result['type']&4 or not result['image_support'] or result['double_fp_config']&7!=7:
        raise RuntimeError('Selected OpenCL device lacks GPU/images/required IEEE binary64 features')
    return result


HEADER = r'''
#pragma OPENCL EXTENSION cl_khr_fp64 : enable
#pragma OPENCL FP_CONTRACT OFF
const sampler_t nearest = CLK_NORMALIZED_COORDS_FALSE | CLK_ADDRESS_CLAMP_TO_EDGE | CLK_FILTER_NEAREST;
double coefficient(read_only image2d_t p, int i) {
    double a = (double)read_imagef(p, nearest, (int2)(i, 0)).x;
    double b = (double)read_imagef(p, nearest, (int2)(i, 1)).x;
    double c = (double)read_imagef(p, nearest, (int2)(i, 2)).x;
    int exponent = (int)read_imagef(p, nearest, (int2)(i, 3)).x;
    if (exponent == 2048) return NAN;
    if (exponent == 2049) return a < 0.0 ? -INFINITY : INFINITY;
    if (exponent == 2050) return -0.0;
    return ldexp((a * 0x1.0p-20 + b * 0x1.0p-40) + c * 0x1.0p-60, exponent);
}
double pixel(read_only image2d_t s, int x, int y) {
    double value = (double)read_imagef(s, nearest, (int2)(x, y)).x;
#if INTEGER_SOURCE
    return rint(value * 255.0);
#else
    return value;
#endif
}
double sample_bilinear(read_only image2d_t s, double x, double y) {
    int width = get_image_width(s), height = get_image_height(s);
    x = clamp(x, 0.0, (double)(width - 1));
    y = clamp(y, 0.0, (double)(height - 1));
    int ix = (int)x, iy = (int)y;
    int nx = min(ix + 1, width - 1), ny = min(iy + 1, height - 1);
    x -= ix; y -= iy;
    return (1.0-y) * ((1.0-x)*pixel(s, ix, iy) + x*pixel(s, nx, iy))
         + y * ((1.0-x)*pixel(s, ix, ny) + x*pixel(s, nx, ny));
}
void emit(write_only image2d_t destination, int2 p, double value) {
#if INTEGER_SOURCE
    value = (double)convert_uchar_sat_rtz(value) / 255.0;
#endif
    write_imagef(destination, p, (float4)((float)value));
}
double prefix_value(read_only image2d_t s, int x, int y) {
    if (x < 0 || y < 0) return 0.0;
    x = min(x, get_image_width(s)/3 - 1);
    y = min(y, get_image_height(s) - 1);
    double a = (double)read_imagef(s, nearest, (int2)(3*x, y)).x;
    double b = (double)read_imagef(s, nearest, (int2)(3*x+1, y)).x;
    double c = (double)read_imagef(s, nearest, (int2)(3*x+2, y)).x;
    return (a+b)+c;
}
void prefix_store(write_only image2d_t s, int x, int y, double value) {
    float a = convert_float_rte(value);
    float b = convert_float_rte(value-(double)a);
    float c = convert_float_rte((value-(double)a)-(double)b);
    write_imagef(s, (int2)(3*x,y), (float4)(a));
    write_imagef(s, (int2)(3*x+1,y), (float4)(b));
    write_imagef(s, (int2)(3*x+2,y), (float4)(c));
}
double prefix_edge(read_only image2d_t s, double x, double y) {
    int ix = (int)floor(x), iy = (int)floor(y);
    double fx = x-ix, fy = y-iy;
    return (1.0-fx)*(1.0-fy)*prefix_value(s,ix-1,iy-1)
         + fx*(1.0-fy)*prefix_value(s,ix,iy-1)
         + (1.0-fx)*fy*prefix_value(s,ix-1,iy)
         + fx*fy*prefix_value(s,ix,iy);
}
__kernel void row_prefix(write_only image2d_t destination, uint index, read_only image2d_t source) {
    if (get_global_id(0) != 0) return;
    int y = get_global_id(1);
    double total = 0.0;
    for (int x=0; x<get_image_width(source); ++x) {
        total += pixel(source,x,y);
        prefix_store(destination,x,y,total);
    }
}
__kernel void column_prefix(write_only image2d_t destination, uint index, read_only image2d_t source) {
    if (get_global_id(1) != 0 || get_global_id(0)%3 != 0) return;
    int x = get_global_id(0)/3;
    double total = 0.0;
    for (int y=0; y<get_image_height(source); ++y) {
        total += prefix_value(source,x,y);
        prefix_store(destination,x,y,total);
    }
}
'''


def quote(value: str) -> str:
    """Escape a literal through the graph and filter-option parsing layers."""
    return "'"+value.replace('\\', '\\\\').replace(':', '\\:').replace("'", "'\\''")+"'"


def coefficient_expression(expressions: list[str]) -> str:
    """Transport a binary64 via exact 20/20/remaining-bit integer chunks.

    Exponents are clamped before normalization so every finite binary64,
    including subnormals and DBL_MAX, has a representable mantissa. Zero and
    nonfinite sentinels have explicit representations. AVExpr performs all
    authoring arithmetic before the tiny frame's Float32 storage edge.
    """
    value = '0'
    for index, expression in reversed(list(enumerate(expressions))):
        value = f'if(eq(X,{index}),({expression}),{value})'
    return (
        f'st(0,{value});'
        'st(1,if(eq(ld(0),0),0,clip(floor(log(abs(ld(0)))/log(2)),-1022,1023)));'
        'st(2,ld(0)*pow(2,-ld(1)));'
        'st(3,trunc(ld(2)*1048576));'
        'st(4,trunc((ld(2)-ld(3)/1048576)*1099511627776));'
        'st(5,(ld(2)-ld(3)/1048576-ld(4)/1099511627776)*1152921504606846976);'
        'if(isnan(ld(0)),if(eq(Y,3),2048,0),'
        'if(isinf(ld(0)),if(eq(Y,3),2049,if(lt(ld(0),0),-1,1)),'
        'if(eq(Y,0),ld(3),if(eq(Y,1),ld(4),if(eq(Y,2),ld(5),'
        'if(eq(ld(0),0)*gt(atan2(0,ld(0)),0),2050,ld(1)))))))'
    )


def kernel_source(body: str, *, area: bool = False, integer: bool = False) -> str:
    extra = ', read_only image2d_t integral' if area else ''
    return ('#define INTEGER_SOURCE '+str(int(integer))+'\n'+HEADER+
            '__kernel void project(write_only image2d_t destination, uint index, '
            'read_only image2d_t source, read_only image2d_t parameters'+extra+') {\n'
            '  const int2 p = (int2)(get_global_id(0),get_global_id(1));\n'
            '  const double X = p.x, Y = p.y;\n'+body+'\n}\n')


def affine_body() -> str:
    return r'''
    double width=get_image_width(source), height=get_image_height(source);
    double cosine=coefficient(parameters,0), sine=coefficient(parameters,1);
    double dx=X+0.5-coefficient(parameters,2)*width;
    double dy=Y+0.5-coefficient(parameters,3)*height;
    double scale=coefficient(parameters,4);
    double x=coefficient(parameters,5)*width+(dx*cosine+dy*sine)/scale-0.5;
    double y=coefficient(parameters,6)*height+(-dx*sine+dy*cosine)/scale-0.5;
    double v=(x>=-0.5 && x<width-0.5 && y>=-0.5 && y<height-0.5)
        ? sample_bilinear(source,clamp(x,0.0,width-1.0),clamp(y,0.0,height-1.0)) : 0.0;
    emit(destination,p,v);
'''


def sequence_body(*, area: bool) -> str:
    prefix = r'''
    double w=coefficient(parameters,0), h=coefficient(parameters,1);
    double cx=coefficient(parameters,2), cy=coefficient(parameters,3);
    double fx=coefficient(parameters,4), fy=coefficient(parameters,5);
    double cosine=coefficient(parameters,6), sine=coefficient(parameters,7);
    double dx=X+0.5-coefficient(parameters,8), dy=Y+0.5-coefficient(parameters,9);
    double scale=coefficient(parameters,10);
    double x=cx+coefficient(parameters,11)*w+(dx*cosine+dy*sine)/(scale*fx)-0.5;
    double y=cy+coefficient(parameters,12)*h+(-dx*sine+dy*cosine)/(scale*fy)-0.5;
'''
    if not area:
        return prefix+r'''
    double v=(x>=cx-0.5 && x<cx+w-0.5 && y>=cy-0.5 && y<cy+h-0.5)
        ? sample_bilinear(source,clamp(x,cx,cx+w-1.0),clamp(y,cy,cy+h-1.0)) : 0.0;
    emit(destination,p,v);
'''
    return prefix+r'''
    double kw=coefficient(parameters,13), kh=coefficient(parameters,14);
    double left=clamp(x+0.5-kw/2.0,cx,cx+w), right=clamp(x+0.5+kw/2.0,cx,cx+w);
    double top=clamp(y+0.5-kh/2.0,cy,cy+h), bottom=clamp(y+0.5+kh/2.0,cy,cy+h);
    double v=(prefix_edge(integral,right,bottom)-prefix_edge(integral,left,bottom)
             -prefix_edge(integral,right,top)+prefix_edge(integral,left,top))/(kw*kh);
    emit(destination,p,v);
'''


def crop_body(canvas: tuple[int, int], *, normalized: bool, fit: str) -> str:
    width, height = canvas
    body = r'''
    double width=get_image_width(source), height=get_image_height(source);
    double w=coefficient(parameters,0), h=coefficient(parameters,1);
    double cx=coefficient(parameters,2), cy=coefficient(parameters,3);
'''
    if normalized:
        body += 'w=width*w;h=height*h;cx=width*cx;cy=height*cy;\n'
    body += 'w=fmin(width,fmax(2.0,w));h=fmin(height,fmax(2.0,h));\n'
    body += 'cx=clamp(cx,0.0,width-w);cy=clamp(cy,0.0,height-h);\n'
    if fit == 'stretch':
        body += 'double x=cx+(X+0.5)*w/width-0.5,y=cy+(Y+0.5)*h/height-0.5;int inside=1;\n'
    else:
        function = 'fmax' if fit == 'fill' else 'fmin'
        body += f'double scale={function}({width}.0/w,{height}.0/h);\n'
        body += f'double ox=({width}.0-w*scale)/2.0,oy=({height}.0-h*scale)/2.0;\n'
        body += f'double dx=(X+0.5)*{width}.0/width,dy=(Y+0.5)*{height}.0/height;\n'
        body += 'double x=cx+(dx-ox)/scale-0.5,y=cy+(dy-oy)/scale-0.5;\n'
        body += ('int inside=1;\n' if fit == 'fill' else
                 'int inside=dx>=ox && dx<ox+w*scale && dy>=oy && dy<oy+h*scale;\n')
    return body+'''
    double v=inside ? sample_bilinear(source,clamp(x,cx,cx+w-1.0),clamp(y,cy,cy+h-1.0))
                    : coefficient(parameters,4);
    emit(destination,p,v);
'''


def expand_definitions(definitions: dict[str, str]) -> list[str]:
    expanded: dict[str, str] = {}
    token = re.compile(r'@\{([a-z_]+)\}')
    for key, value in definitions.items():
        expanded[key] = token.sub(lambda m: '('+expanded[m[1]]+')', value)
    return list(expanded.values())


def projection_chain(*, prefix: list[str], suffix: list[str], expressions: list[str],
                     alpha_expressions: list[str] | None = None, source: tuple[int,int],
                     target: tuple[int,int], kernel: Path, label: str, area: bool = False,
                     pixel_format: str = 'gbrapf32le', native_target: bool = False) -> list[str]:
    """A single chain can contain named split/framesync branches and rejoin."""
    source_label, params_label = label+'_source', label+'_parameters'
    texture_label, coefficients_label = label+'_texture', label+'_coefficients'
    shader = quote(kernel.as_posix())
    expression = quote(coefficient_expression(expressions))
    alpha = quote(coefficient_expression(alpha_expressions)) if alpha_expressions is not None else expression
    branches = 3 if area else 2
    split = (f'split={branches}[{source_label}][{params_label}]'+(f'[{label}_sum]' if area else '')+
             f';[{params_label}]scale={len(expressions)}:4:flags=neighbor,format=gbrapf32le,'
             f'geq=r={expression}:g={expression}:b={expression}:a={alpha},hwupload[{coefficients_label}]'
             f';[{source_label}]hwupload[{texture_label}]')
    integral = ''
    if area:
        width, height = source
        split += (f';[{label}_sum]hwupload,program_opencl=source={shader}:kernel=row_prefix:inputs=1:size={3*width}x{height},'
                  f'program_opencl=source={shader}:kernel=column_prefix:inputs=1:size={3*width}x{height}[{label}_integral]')
        integral = f'[{label}_integral]'
    split += (f';[{texture_label}][{coefficients_label}]'+integral+
              f'program_opencl=source={shader}:kernel=project:inputs={branches}'+
              ('' if native_target else f':size={target[0]}x{target[1]}'))
    return prefix+[split,'hwdownload','format='+pixel_format]+suffix


def source_digest(source: str) -> str:
    return hashlib.sha256(source.encode('utf8')).hexdigest()


class ProjectionSession:
    def __init__(self,root,settings,operation_id,*,cancel_file=None):
        self.root=Path(root).resolve()
        self.config=configuration(settings.get('projection_acceleration'))
        self.enabled=self.config['mode']!='off'
        self.directory=self.root/'renders/diagnostics'/('projection_'+operation_id)
        self.path=self.directory/'report.json'
        self.cancel_file=cancel_file
        self.programs={};self.replacements=[]
        self.evidence={'engine':'opencl-binary64-projection-v1','request':dict(self.config),
            'status':'planned','nodes':[],'probes':[], 'estimated_working_bytes':0,
            'quota_scope':'projection-raster-admission-not-total-ram-or-vram',
            'report':str(self.path) if self.enabled else None,
            'other_filters':'unchanged-cpu','hardware_encoding':'separate-policy'}

    def save(self):
        if self.enabled:atomic_write_json(self.path,self.evidence)

    def reject_node(self,kind,reason,**details):
        self.evidence['nodes'].append({'kind':kind,'selected':'cpu','reason':reason,**details})
        if self.config['mode']=='require':
            raise AppError('PROJECTION_REQUIRED_UNAVAILABLE','要求的GPU投影条件未满足',exit_code=6,
                           cause=reason,diagnostics=details or None)

    def select(self,cpu,*,kind,expressions,source,target,body,prefix,suffix,pure=True,
               area=False,integer=False,alpha_expressions=None,native_target=False):
        if not self.enabled:return cpu
        if not pure or min(*source,*target)<1:
            self.reject_node(kind,'pixel/stateful expression or unknown raster');return cpu
        components={'source_uploads_and_slots':source[0]*source[1]*16*6,
            'destination_slots':target[0]*target[1]*16*3,
            'parameter_slots':len(expressions)*4*16*3,
            'prefix_two_pass_slots':source[0]*source[1]*3*16*4 if area else 0}
        estimate=sum(components.values())
        cumulative=self.evidence['estimated_working_bytes']+estimate
        if cumulative>self.config['max_working_bytes']:
            self.reject_node(kind,'explicit projection raster admission quota exceeded',
                estimated_working_bytes=estimate,cumulative_working_bytes=cumulative)
            return cpu
        label='aek_projection_'+str(len(self.replacements))
        kernel=self.directory/(label+'.cl')
        code=kernel_source(body,area=area,integer=integer)
        gpu=projection_chain(prefix=prefix,suffix=suffix,expressions=expressions,
            alpha_expressions=alpha_expressions,source=source,target=target,
            kernel=kernel.relative_to(self.root),label=label,area=area,
            pixel_format='gbrap' if integer else 'gbrapf32le',native_target=native_target)
        node={'id':label,'kind':kind,'selected':'opencl','status':'planned',
            'source':list(source),'target':list(target),'sampling':'area' if area else 'bilinear',
            'texture_format':'gbrap' if integer else 'gbrapf32le','coefficient_count':len(expressions),
            'kernel':str(kernel),'kernel_sha256':source_digest(code),
            'components_bytes':components,'estimated_working_bytes':estimate,
            'image_extents':[list(source),list(target),[len(expressions),4]]+
                ([[3*source[0],source[1]]] if area else [])}
        self.programs[kernel]=code
        self.replacements.append((','.join(gpu),','.join(cpu)))
        self.evidence['nodes'].append(node)
        self.evidence['estimated_working_bytes']=cumulative
        return gpu

    def write_programs(self):
        for path,code in self.programs.items():
            if path.exists():
                raise AppError('PROJECTION_PROGRAM_EXISTS','拒绝覆盖已有投影程序',exit_code=6,path=str(path))
            atomic_write_text(path,code)
        self.verify_programs()

    def verify_programs(self):
        for path,code in self.programs.items():
            if sha256_file(path)!=source_digest(code):
                raise AppError('PROJECTION_PROGRAM_CHANGED','投影程序摘要改变',exit_code=6,path=str(path))

    def command(self,name,args):
        record={'id':name,'command':list(map(str,args)),'status':'running'}
        self.evidence['probes'].append(record);self.save()
        try:
            result=run_process(record['command'],cwd=self.root,
                timeout=self.config['probe_timeout_seconds'],cancel_file=self.cancel_file)
        except AppError as exc:
            record.update(status='interrupted',error=exc.as_dict());self.save();raise
        for key in ('stdout','stderr'):
            path=self.directory/(name+'.'+key+'.log')
            atomic_write_text(path,getattr(result,key) or '')
            record[key]={'path':str(path),'sha256':sha256_file(path)}
        record.update(status='completed',exit_code=result.returncode);self.save()
        if result.returncode:
            raise AppError('PROJECTION_PROBE_FAILED','原生GPU投影探测未通过',exit_code=6,
                           path=str(self.path),cause=result.stderr[-3000:])
        return result

    def preflight(self):
        import math
        import struct
        info=device_info(self.config['device']);self.evidence['device']=info;self.save()
        for node in self.evidence['nodes']:
            for w,h in node.get('image_extents',[]):
                if w>info['image_max_width'] or h>info['image_max_height']:
                    raise AppError('PROJECTION_DEVICE_LIMIT','投影纹理超过设备实际尺寸限制',exit_code=6)
        self.write_programs()
        # Echo all binary64 bits, not merely their Float32-rounded values.
        values=[0.,-0.,math.pi,1.+2.**-52,1e-8,-.50000000001,1e-300,
                float.fromhex('0x1.fffffffffffffp+1023'),float.fromhex('0x0.0000000000001p-1022')]
        expressions=[format(v,'.17g') for v in values]
        program=kernel_source('''
    ulong bits=as_ulong(coefficient(source,p.x));
    uint chunk=(uint)((bits>>(16*p.y)) & 65535UL);
    write_imagef(destination,p,(float4)((float)chunk));
''')
        probe=self.directory/'coefficient_probe.cl'
        expression=quote(coefficient_expression(expressions))
        graph=(f'format=gbrapf32le,geq=r={expression}:g={expression}:b={expression}:a={expression},hwupload,'
               f'program_opencl=source={quote(probe.relative_to(self.root).as_posix())}:kernel=project:inputs=1:'
               f'size={len(values)}x4,hwdownload,format=gbrapf32le')
        # The generic entry has two image arguments. The probe uses its own
        # one-input entry signature; this keeps frame clocks out of uniforms.
        program=program.replace('read_only image2d_t source, read_only image2d_t parameters)',
                                'read_only image2d_t source)')
        atomic_write_text(probe,program)
        raw=self.directory/'coefficient_probe.gbrapf32le'
        args=[ffmpeg_path(),'-hide_banner','-v','error','-nostdin','-n',
            '-init_hw_device','opencl=aek_projection:'+self.config['device'],
            '-filter_hw_device','aek_projection','-f','lavfi','-i',f'nullsrc=s={len(values)}x4:r=1:d=1,format=gbrapf32le',
            '-vf',graph,'-frames:v','1','-f','rawvideo',str(raw)]
        self.command('binary64-coefficients',args)
        data=raw.read_bytes()
        if len(data)!=len(values)*4*4*4:
            raise AppError('PROJECTION_PROBE_FAILED','投影系数探测输出长度错误',exit_code=6)
        floats=struct.unpack('<'+'f'*(len(data)//4),data)
        for plane in range(4):
            for x,value in enumerate(values):
                bits=sum(int(floats[plane*len(values)*4+y*len(values)+x])<<(16*y) for y in range(4))
                if bits!=struct.unpack('<Q',struct.pack('<d',value))[0]:
                    raise AppError('PROJECTION_COEFFICIENT_MISMATCH','GPU双精度系数传输不一致',exit_code=6,
                                   diagnostics={'plane':plane,'coefficient':x})
        self.evidence['coefficient_probe']={'values':len(values),'planes':4,
            'all_binary64_bits_equal':True,'includes_negative_zero_and_extreme_exponents':True,
            'raw_path':str(raw),'sha256':sha256_file(raw)}
        self.save()
        # Texture capabilities differ by ICD/format. Read back real samples
        # before admitting any authoring render, including Float32 denormals.
        for pixel_format,integer in [('gbrapf32le',False),('gbrap',True)]:
            width,height,frames=16,8,2
            if integer:
                expected=bytes((i*73+i//17)%256 for i in range(width*height*4*frames))
            else:
                choices=[0.,-0.,-.25,.5,1.,1.25,1e-40,1e-45,3.4e38,-3.4e38]
                samples=[choices[(i*7+i//19)%len(choices)] for i in range(width*height*4*frames)]
                expected=struct.pack('<'+'f'*len(samples),*samples)
            input_path=self.directory/('texture-'+pixel_format+'.input')
            output_path=self.directory/('texture-'+pixel_format+'.output')
            kernel=self.directory/('texture-'+pixel_format+'.cl')
            with input_path.open('xb') as stream:stream.write(expected)
            code=kernel_source('emit(destination,p,pixel(source,p.x,p.y));',integer=integer)
            code=code.replace('read_only image2d_t source, read_only image2d_t parameters)',
                              'read_only image2d_t source)')
            atomic_write_text(kernel,code)
            graph=(f'format={pixel_format},hwupload,program_opencl=source='
                f'{quote(kernel.relative_to(self.root).as_posix())}:kernel=project:inputs=1,'
                f'hwdownload,format={pixel_format}')
            args=[ffmpeg_path(),'-hide_banner','-v','error','-nostdin','-n',
                '-init_hw_device','opencl=aek_projection:'+self.config['device'],
                '-filter_hw_device','aek_projection','-f','rawvideo','-pixel_format',pixel_format,
                '-video_size',f'{width}x{height}','-framerate','4','-i',str(input_path),
                '-vf',graph,'-frames:v',str(frames),'-fps_mode','passthrough','-f','rawvideo',str(output_path)]
            self.command('texture-'+pixel_format,args)
            actual=output_path.read_bytes()
            if actual!=expected:
                raise AppError('PROJECTION_TEXTURE_MISMATCH','GPU纹理上传/采样/回读不一致',exit_code=6,
                               diagnostics={'pixel_format':pixel_format,'expected_bytes':len(expected),'actual_bytes':len(actual)})
            self.evidence.setdefault('texture_probes',[]).append({'format':pixel_format,'frames':frames,
                'planes':4,'all_sample_bits_equal':True,'output':str(output_path),'sha256':sha256_file(output_path)})
            self.save()

    def prepare(self,args,graph):
        if not self.enabled:return args,graph
        if not self.replacements:
            self.evidence['status']='not_applicable';self.save()
            if self.config['mode']=='require':
                raise AppError('PROJECTION_NOT_APPLICABLE','工程没有适用的投影算子',exit_code=6,path=str(self.path))
            return args,graph
        try:
            self.evidence['status']='probing';self.save();self.preflight()
        except (AppError,OSError,RuntimeError,AttributeError) as exc:
            if isinstance(exc,AppError) and exc.code in ('CANCELLED','PROCESS_TIMEOUT'):raise
            self.evidence['status']='preflight_failed';self.evidence['error']=str(exc);self.save()
            if self.config['mode']=='require':
                raise AppError('PROJECTION_REQUIRED_UNAVAILABLE','必须GPU投影，但设备或精度探测未通过',
                               exit_code=6,path=str(self.path),cause=str(exc)) from exc
            for gpu,cpu in self.replacements:
                if graph.count(gpu)!=1:
                    raise AppError('PROJECTION_GRAPH_INVALID','无法唯一恢复CPU投影段',exit_code=6)
                graph=graph.replace(gpu,cpu,1)
            for node in self.evidence['nodes']:
                if node['selected']=='opencl':
                    node.update(selected='cpu',status='fallback',reason='native OpenCL preflight failed')
            self.evidence['status']='cpu_fallback';self.save()
            result=list(args);result[result.index('-filter_complex')+1]=graph
            return result,graph
        self.evidence['status']='prepared'
        for node in self.evidence['nodes']:
            if node['selected']=='opencl':node['status']='prepared'
        self.save()
        result=list(args)
        result[1:1]=['-init_hw_device','opencl=aek_projection:'+self.config['device'],
                     '-filter_hw_device','aek_projection']
        return result,graph

    def finish(self,result):
        if not self.enabled:return
        for key in ('stdout','stderr'):
            path=self.directory/('render.'+key+'.log');atomic_write_text(path,getattr(result,key) or '')
            self.evidence[key]={'path':str(path),'sha256':sha256_file(path)}
        self.evidence['render_exit_code']=result.returncode
        if self.evidence['status']=='prepared':
            self.evidence['status']='encoded_pending_quality' if result.returncode==0 else 'render_failed'
        self.save()
