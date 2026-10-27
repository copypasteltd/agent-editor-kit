"""Original author-clock linear-light optical effects with a shared GPU contract."""
from dataclasses import dataclass
import json
import math

import numpy as np

from .errors import AppError
from .float_color_signal import ColorSignal
from .float_numeric_automation import number,compile_tracks,sample_tracks,raw_tracks,validate_duration
from .float_spatial_budget import admit_spatial,MAX_WORKING_BYTES

PROTOCOL='author-clock-linear-float32-optical-effects-v1'
ALIASES={'lens_flare':'lens_flare','lensflare':'lens_flare','light_leak':'light_leak',
         'lightleak':'light_leak','chromatic_aberration':'chromatic_aberration','rgb_split':'chromatic_aberration'}
COMMON={'intensity':(1.,0.,1.)}
LIGHT={'x':(.2,-1.,2.),'y':(.3,-1.,2.),'radius':(.12,.005,2.),
       'angle':(0.,-360.,360.),'red':(1.,0.,4.),'green':(.55,0.,4.),
       'blue':(.25,0.,4.),'brightness':(1.,0.,8.)}
SPECS={
    'lens_flare':{**COMMON,**LIGHT,'streak':(.5,0.,8.),'streak_width':(.008,.001,.25),
                  'halo':(.3,0.,4.),'ghost_spacing':(.55,.1,2.)},
    'light_leak':{**COMMON,**LIGHT,'aspect':(2.,.05,20.)},
    'chromatic_aberration':{**COMMON,'x':(.5,-1.,2.),'y':(.5,-1.,2.),
        'red_shift':(3.,-64.,64.),'blue_shift':(-3.,-64.,64.),'falloff':(1.,0.,4.)},
}
FIELDS=('intensity','x','y','radius','aspect','angle','red','green','blue','brightness',
        'streak','streak_width','halo','ghost_spacing','red_shift','blue_shift','falloff')
KINDS=('lens_flare','light_leak','chromatic_aberration')

def error(kind,message,**details):return AppError('FLOAT_OPTICS_'+kind,message,exit_code=2,diagnostics=details or None)
def bounds(kind):return {key:(v[1],v[2]) for key,v in SPECS[kind].items()}
def parameter_names(name):return frozenset(SPECS[ALIASES[name]])

@dataclass(frozen=True)
class OpticalPlan:
    effect_type:str
    values:tuple
    tracks_json:str
    ghosts:int
    edge:str

def validate_state(kind,values,ghosts,edge):
    if not isinstance(kind,str) or kind not in SPECS or not isinstance(values,dict) or values.keys()!=SPECS[kind].keys():
        raise error('ARGUMENT','光学效果类型或数值通道无效')
    values={k:number(v,*bounds(kind)[k]) for k,v in values.items()}
    if type(ghosts) is not int or not 0<=ghosts<=12 or kind!='lens_flare' and ghosts!=0:
        raise error('ARGUMENT','眩光ghosts须为0..12整数；其他效果不接受ghosts')
    if edge not in ('clamp','transparent') or kind!='chromatic_aberration' and edge!='clamp':
        raise error('ARGUMENT','仅色差接受clamp或transparent采样边界')
    return values

def compile_optics(effect):
    if not isinstance(effect,dict) or set(effect)-{'id','type','enabled','parameters','keyframes'}:
        raise error('ARGUMENT','光学效果含未知字段；参数须置于parameters')
    name=str(effect.get('type','')).strip().lower().replace('-','_')
    if name not in ALIASES or type(effect.get('enabled',True)) is not bool:raise error('ARGUMENT','光学效果类型或enabled无效')
    kind=ALIASES[name];p=effect.get('parameters',{})
    extras={'keyframes'}|({'ghosts'} if kind=='lens_flare' else {'edge'} if kind=='chromatic_aberration' else set())
    if not isinstance(p,dict) or set(p)-(set(SPECS[kind])|extras):raise error('ARGUMENT','光学效果参数未知')
    values={key:p.get(key,v[0]) for key,v in SPECS[kind].items()}
    ghosts=p.get('ghosts',6 if kind=='lens_flare' else 0);edge=p.get('edge','clamp')
    values=validate_state(kind,values,ghosts,edge)
    tracks=compile_tracks(raw_tracks(effect,p),bounds(kind),{},name)
    return OpticalPlan(kind,tuple(sorted(values.items())),tracks,ghosts,edge)

def state_at(plan,tick):
    if not isinstance(plan,OpticalPlan) or not isinstance(plan.values,tuple):raise error('ARGUMENT','光学效果须为不可变编译计划')
    if any(not isinstance(row,tuple) or len(row)!=2 or not isinstance(row[0],str) for row in plan.values):
        raise error('ARGUMENT','光学计划通道格式无效')
    values=dict(plan.values)
    if len(values)!=len(plan.values):raise error('ARGUMENT','光学计划通道重复')
    values=validate_state(plan.effect_type,values,plan.ghosts,plan.edge)
    values.update(sample_tracks(plan.tracks_json,bounds(plan.effect_type),{},plan.effect_type,tick))
    return validate_state(plan.effect_type,values,plan.ghosts,plan.edge)

def validate_optics(effect,*,duration_tick=None):
    if effect.get('enabled',True) is False:return []
    try:
        plan=compile_optics(effect);validate_duration(plan.tracks_json,duration_tick)
    except AppError as exc:return [{'code':exc.code,'message':str(exc),'suffix':'.parameters'}]
    return []

def _sample_channel(source,x,y,channel,edge):
    """Bilinear premultiplied channel/coverage; hidden RGB contributes nothing."""
    h,w=source.shape[:2]
    if edge=='clamp':x=np.clip(x,0,w-1);y=np.clip(y,0,h-1)
    else:x=np.clip(x,-2,w+1);y=np.clip(y,-2,h+1)
    ix=np.floor(x).astype(np.int64);iy=np.floor(y).astype(np.int64);dx=x-ix;dy=y-iy
    color=np.zeros(len(x),np.float64);alpha=np.zeros(len(x),np.float64)
    for ox,oy,weight in ((0,0,(1-dx)*(1-dy)),(1,0,dx*(1-dy)),(0,1,(1-dx)*dy),(1,1,dx*dy)):
        xx,yy=ix+ox,iy+oy
        coverage=source[np.clip(yy,0,h-1),np.clip(xx,0,w-1),3].astype(np.float64)
        if edge=='transparent':coverage*=((xx>=0)&(xx<w)&(yy>=0)&(yy<h))
        coverage*=weight
        color+=source[np.clip(yy,0,h-1),np.clip(xx,0,w-1),channel].astype(np.float64)*coverage
        alpha+=coverage
    np.divide(color,alpha,out=color,where=alpha>0);color[alpha==0]=0
    return color

def cpu_tile(source,start,stop,kind,v,ghosts,edge):
    h,w=source.shape[:2];index=np.arange(start,stop,dtype=np.int64)
    xx=index%w;yy=index//w;short=min(w,h)
    dx=(xx+.5-v['x']*w)/short;dy=(yy+.5-v['y']*h)/short
    original=source.reshape(-1,4)[start:stop];result=original.copy();rgb=original[:,:3].astype(np.float64)
    if kind=='chromatic_aberration':
        distance=np.sqrt(dx*dx+dy*dy);factor=np.power(np.minimum(distance*2,4.),v['falloff'])
        unit_x=np.divide(dx,distance,out=np.zeros_like(dx),where=distance>0)
        unit_y=np.divide(dy,distance,out=np.zeros_like(dy),where=distance>0)
        for channel,amount in ((0,v['red_shift']),(2,v['blue_shift'])):
            shifted=_sample_channel(source,xx+unit_x*factor*amount,yy+unit_y*factor*amount,channel,edge)
            rgb[:,channel]+=v['intensity']*(shifted-rgb[:,channel])
    else:
        angle=math.radians(v['angle']);c,s=math.cos(angle),math.sin(angle)
        rx=c*dx+s*dy;ry=-s*dx+c*dy
        if kind=='light_leak':
            energy=np.exp(-.5*((rx/v['radius'])**2+(ry/(v['radius']*v['aspect']))**2))
            light=energy[:,None]*np.array([v['red'],v['green'],v['blue']],np.float64)
        else:
            r=np.sqrt(dx*dx+dy*dy)/v['radius']
            energy=np.exp(-.5*r*r)
            energy+=v['streak']*np.exp(-np.abs(ry)/v['streak_width'])*np.exp(-np.abs(rx)/(v['radius']*8))
            energy+=v['halo']*np.exp(-.5*((r-2.7)/.22)**2)
            light=energy[:,None]*np.array([v['red'],v['green'],v['blue']],np.float64)
            for i in range(1,ghosts+1):
                gx=(xx+.5-(v['x']+(.5-v['x'])*i*v['ghost_spacing'])*w)/short
                gy=(yy+.5-(v['y']+(.5-v['y'])*i*v['ghost_spacing'])*h)/short
                rr=np.sqrt(gx*gx+gy*gy)/(v['radius']*(.35+.12*i))
                amount=np.exp(-.5*((rr-.8)/.23)**2)*(.18/(1+.3*i))
                light+=amount[:,None]*np.array([v['red']*(1-.04*i),v['green']*(.6+.025*i),v['blue']*(.9-.035*i)])
        rgb+=light*(v['brightness']*v['intensity'])
    result[:,:3]=rgb;result[result[:,3]==0,:3]=0
    return result

def apply_optics(surface,plan,author_tick,*,working_signal,retained_table_bytes=0,
                 max_working_bytes=MAX_WORKING_BYTES,tile_pixels=16384,cancel=None,gpu=None):
    if cancel is not None and not callable(cancel):raise error('ARGUMENT','取消回调须可调用')
    def poll():
        if cancel and cancel():raise AppError('RENDER_CANCELLED','光学效果已取消',exit_code=6)
    poll();values=state_at(plan,author_tick)
    if not isinstance(working_signal,ColorSignal) or working_signal.transfer!='linear':raise error('SIGNAL','光学效果要求明确线性RGB工作域')
    if not isinstance(surface,np.ndarray) or surface.dtype!=np.float32 or surface.ndim!=3 or surface.shape[-1]!=4 or not surface.flags.c_contiguous:
        raise error('SURFACE','光学效果输入须为连续H×W×4 Float32')
    h,w=surface.shape[:2];pixels=h*w
    if min(h,w)<1 or max(h,w)>16384 or pixels>16777216:raise error('BUDGET','光学表面超过尺寸预算')
    tile,estimate,admission=admit_spatial(surface_bytes=int(surface.nbytes),pixels=pixels,tile_pixels=tile_pixels,
        tracks_bytes=len(plan.tracks_json.encode('utf8')),retained_table_bytes=retained_table_bytes,
        max_working_bytes=max_working_bytes,error=error)
    flat=surface.reshape(-1,4)
    for start in range(0,pixels,tile):
        poll();part=flat[start:start+tile]
        if not np.isfinite(part).all() or np.any(part[:,3]<0) or np.any(part[:,3]>1):raise error('VALUES','RGB须有限且alpha须为0..1')
    active=values['intensity']!=0
    if plan.effect_type=='chromatic_aberration':active&=bool(values['red_shift'] or values['blue_shift'])
    else:active&=bool(values['brightness']) and any(values[c] for c in ('red','green','blue'))
    used_gpu=bool(active and gpu is not None and gpu.active)
    if not active:result=surface.copy()
    elif used_gpu:result=gpu.optics(surface,plan.effect_type,values,plan.ghosts,plan.edge)
    else:
        result=np.empty_like(surface);out=result.reshape(-1,4)
        for start in range(0,pixels,tile):
            poll();out[start:start+tile]=cpu_tile(surface,start,min(start+tile,pixels),plan.effect_type,values,plan.ghosts,plan.edge)
    poll()
    if not np.isfinite(result).all():raise error('OVERFLOW','光学效果产生非有限Float32像素')
    metadata=dict(protocol=PROTOCOL,effect_type=plan.effect_type,author_tick=str(author_tick),parameters=values,
        ghosts=plan.ghosts,edge=plan.edge,alpha='input-bits-preserved',zero_alpha_RGB='zero-when-active',
        working_primaries=working_signal.primaries,light_transfer='linear',color_parameters='linear-working-RGB',
        active=bool(active),GPU=used_gpu,backend='OpenCL' if used_gpu else 'CPU',integer_intermediate=False,
        HDR_accepted=False,estimated_working_bytes=estimate,**admission)
    return result,metadata
