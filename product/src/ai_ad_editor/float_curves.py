"""Continuous RGB splines in explicit signals, on the original author clock.

The implementation solves spline derivatives directly. It never constructs an
integer lookup table. `all` supplies missing channels; `post_master` is the
separate, optional curve after the independent channels.
"""
from dataclasses import dataclass
from fractions import Fraction
import json
import math
import re

import numpy as np

from .errors import AppError
from .float_color_signal import ColorSignal, convert_rgba

PROTOCOL = 'explicit-signal-continuous-float32-rgb-curves-v1'
ALIASES = frozenset(('curves','curve','rgb_curves','rgb_curve','channel_curves'))
CHANNELS = ('red','green','blue')
MAX_POINTS = 256
MAX_PIXELS = 16_777_216
MAX_WORKING_BYTES = 768*1024*1024
_NUMBER = re.compile(r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?')
PARAMETER_NAMES = frozenset({'intensity'} | {
    f'{c}.{i}.{a}' for c in ('all','master',*CHANNELS,'post_master')
    for i in range(MAX_POINTS) for a in ('x','y')})


def error(kind, message):
    return AppError('FLOAT_CURVES_'+kind,message,exit_code=2)


def number(value, low=None, high=None):
    if isinstance(value,(bool,np.bool_)) or not isinstance(value,(int,float,np.integer,np.floating)):
        raise error('ARGUMENT','曲线坐标和强度须为有限数字')
    try: value = float(value)
    except (OverflowError,ValueError): raise error('ARGUMENT','曲线数字超出有限范围')
    if not math.isfinite(value) or (low is not None and value<low) or (high is not None and value>high):
        raise error('ARGUMENT','曲线数字超出声明范围')
    return value


def geometry(points):
    if any(a[0]>=b[0] for a,b in zip(points,points[1:])):
        raise error('POINTS','曲线横坐标须严格递增；作者采样时刻不可交叉或重合')


def parse_points(raw):
    if not isinstance(raw,str) or len(raw)>65536:
        raise error('POINTS','曲线须为有界x/y字符串')
    tokens = raw.split()
    if not 1<=len(tokens)<=MAX_POINTS:
        raise error('POINTS','每条曲线须有1到256个固定控制点')
    result = []
    for token in tokens:
        pair = token.split('/')
        if len(pair)!=2 or any(_NUMBER.fullmatch(v) is None for v in pair):
            raise error('POINTS','曲线只接受有限x/y坐标，不接受表达式或文件')
        result.append(tuple(number(float(v),0,1) for v in pair))
    geometry(result)
    return tuple(result)


def signal(value):
    from .float_hdr import parse_signal
    return parse_signal(value)


@dataclass(frozen=True)
class CurvePlan:
    points: tuple
    tracks_json: str
    input_signal: ColorSignal
    output_signal: ColorSignal
    interpolation: str
    intensity: float


def compile_curves(effect):
    if not isinstance(effect,dict) or set(effect)-{'type','id','enabled','parameters','keyframes'}:
        raise error('ARGUMENT','曲线包含未知字段；参数须置于parameters')
    name = str(effect.get('type','')).strip().lower().replace('-','_')
    if name not in ALIASES: raise error('ARGUMENT','未知RGB曲线类型')
    p = effect.get('parameters',{})
    allowed = {'all','master',*CHANNELS,'post_master','input_signal','output_signal','interpolation','intensity','keyframes'}
    if not isinstance(p,dict) or set(p)-allowed: raise error('ARGUMENT','曲线参数包含未知字段')
    if name in ('curves','curve') and any(p.get(c) not in (None,'') for c in CHANNELS):
        raise error('ARGUMENT','独立RGB通道须使用rgb_curves类型')
    if 'all' in p and p.get('master') not in (None,'',p['all']):
        raise error('ARGUMENT','all与旧master别名冲突；后置总曲线使用post_master')
    base = {'all':parse_points(p.get('all',p.get('master') or '0/0 1/1'))}
    for c in (*CHANNELS,'post_master'):
        if p.get(c) not in (None,''): base[c] = parse_points(p[c])
    method = p.get('interpolation','natural')
    if method not in ('natural','pchip'): raise error('ARGUMENT','曲线空间插值须为natural或pchip')
    strength = number(p.get('intensity',1),0,1)
    incoming,outgoing = signal(p.get('input_signal')),signal(p.get('output_signal'))
    if 'keyframes' in effect and 'keyframes' in p: raise error('ARGUMENT','曲线关键帧只能声明在一个层级')
    raw = effect.get('keyframes',p.get('keyframes',[]))
    if not isinstance(raw,list) or len(raw)>2561: raise error('BUDGET','曲线轨道数量超限')
    tracks,seen,total = [],set(),0
    for t in raw:
        if not isinstance(t,dict) or set(t)!={'property','keyframes'} or not isinstance(t['property'],str):
            raise error('ARGUMENT','曲线关键帧轨道格式无效')
        prop = t['property'].strip().lower().replace('-','_')
        for prefix in ('effect.','parameters.',name+'.'):
            if prop.startswith(prefix): prop = prop[len(prefix):]; break
        if prop.startswith('master.'): prop = 'all.'+prop[7:]
        if prop in seen or prop not in PARAMETER_NAMES: raise error('ARGUMENT','曲线轨道重复或属性未知')
        seen.add(prop)
        if prop!='intensity':
            c,i,a = prop.split('.')
            if c in CHANNELS and name in ('curves','curve'): raise error('ARGUMENT','独立RGB关键帧须使用rgb_curves')
            if c not in base: base[c] = tuple(base['all']) if c in CHANNELS else ((0.,0.),(1.,1.))
            if int(i)>=len(base[c]): raise error('POINTS','曲线关键帧控制点不存在；不动态插入或删除点')
        keys = t['keyframes']
        if not isinstance(keys,list) or not 1<=len(keys)<=1024: raise error('BUDGET','曲线每轨道须有1到1024个关键帧')
        total += len(keys)
        if total>65536: raise error('BUDGET','曲线关键帧总数超过65536')
        previous = -1
        for k in keys:
            if not isinstance(k,dict) or set(k)-{'at_tick','value','interpolation','control_points'}:
                raise error('ARGUMENT','曲线关键帧包含未知字段')
            if type(k.get('at_tick')) is not int or k['at_tick']<=previous: raise error('ARGUMENT','曲线关键帧时钟须为递增非负整数')
            previous = k['at_tick']; number(k.get('value'),0,1)
            mode = k.get('interpolation','linear')
            if mode not in ('linear','hold','ease_in','ease_out','ease_in_out','bezier'): raise error('ARGUMENT','曲线时间插值未知')
            if mode=='bezier':
                cp = k.get('control_points')
                if not isinstance(cp,list) or len(cp) not in (2,4): raise error('ARGUMENT','Bezier须提供2或4个有限控制值')
                cp = [number(v) for v in cp]
                if len(cp)==4 and not (0<=cp[0]<=1 and 0<=cp[2]<=1): raise error('ARGUMENT','Bezier横向控制值须在0到1')
        tracks.append({'property':prop,'keyframes':keys})
    return CurvePlan(tuple(sorted(base.items())),json.dumps({'keyframes':tracks},sort_keys=True,allow_nan=False,separators=(',',':')),
        incoming,outgoing,method,strength)


def validate_curves(effect, *, duration_tick=None):
    if effect.get('enabled',True) is False: return []
    try:
        plan = compile_curves(effect)
        if duration_tick is not None and any(k['at_tick']>duration_tick for t in json.loads(plan.tracks_json)['keyframes'] for k in t['keyframes']):
            raise error('ARGUMENT','曲线关键帧超过原作者时长')
    except AppError as exc:
        return [{'code':exc.code,'message':str(exc),'suffix':'.parameters'}]
    return []


def state_at(plan, tick):
    if isinstance(tick,Fraction):
        if tick<0: raise error('ARGUMENT','曲线作者时钟须非负')
    else: number(tick,0)
    state = {c:[list(p) for p in points] for c,points in plan.points}
    authored = json.loads(plan.tracks_json)
    strength = plan.intensity
    for t in authored['keyframes']:
        prop = t['property']
        if prop=='intensity': default = plan.intensity
        else:
            c,i,a = prop.split('.'); default = state[c][int(i)][a=='y']
        value = min(1.,max(0.,number(author_value(t['keyframes'],tick))))
        if prop=='intensity': strength = value
        else: state[c][int(i)][a=='y'] = value
    for points in state.values(): geometry(points)
    return state,strength


def author_value(keys, tick):
    """Evaluate the authored easing directly, retaining rational tick offsets."""
    if tick<keys[0]['at_tick']: return float(keys[0]['value'])
    for left,right in zip(keys,keys[1:]):
        if tick>=right['at_tick']: continue
        p = float((tick-left['at_tick'])/(right['at_tick']-left['at_tick']))
        mode = left.get('interpolation','linear')
        if mode=='hold': p = 0.
        elif mode=='ease_in': p *= p
        elif mode=='ease_out': p = 1-(1-p)**2
        elif mode=='ease_in_out': p = 2*p*p if p<.5 else 1-(-2*p+2)**2/2
        elif mode=='bezier' and 0<p<1:
            cp = left['control_points']
            if len(cp)==2:
                p = 3*(1-p)**2*p*cp[0]+3*(1-p)*p*p*cp[1]+p**3
            else:
                low,high = 0.,1.
                for _ in range(48):
                    u = (low+high)/2; x = 3*(1-u)**2*u*cp[0]+3*(1-u)*u*u*cp[2]+u**3
                    if x<p: low = u
                    else: high = u
                u = (low+high)/2
                p = 3*(1-u)**2*u*cp[1]+3*(1-u)*u*u*cp[3]+u**3
        return float(left['value'])+(float(right['value'])-float(left['value']))*p
    return float(keys[-1]['value'])


def coefficients(points, method):
    """O(n) natural-spline solve or shape-preserving weighted harmonic slopes."""
    p = np.asarray(points,np.float64); x,y = p[:,0],p[:,1]; n = len(p)
    if n==1: return x,y,np.empty((0,4),np.float64)
    with np.errstate(over='ignore',divide='ignore',invalid='ignore'):
        h = np.diff(x); delta = np.diff(y)/h
        if method=='natural':
            diagonal = 2*(h[:-1]+h[1:]); rhs = 6*np.diff(delta)
            for i in range(1,len(diagonal)):
                factor = h[i]/diagonal[i-1]; diagonal[i] -= factor*h[i]; rhs[i] -= factor*rhs[i-1]
            second = np.zeros(n,np.float64)
            for i in range(n-3,-1,-1): second[i+1] = (rhs[i]-(h[i+1]*second[i+2] if i<n-3 else 0))/diagonal[i]
            result = np.column_stack((y[:-1],delta-h*(2*second[:-1]+second[1:])/6,second[:-1]/2,np.diff(second)/(6*h)))
        else:
            slope = np.zeros(n,np.float64)
            if n==2: slope[:] = delta[0]
            else:
                for i in range(1,n-1):
                    if delta[i-1]*delta[i]>0:
                        w1,w2 = 2*h[i]+h[i-1],h[i]+2*h[i-1]
                        slope[i] = (w1+w2)/(w1/delta[i-1]+w2/delta[i])
                for j,a,b in ((0,0,1),(-1,-1,-2)):
                    endpoint = ((2*h[a]+h[b])*delta[a]-h[a]*delta[b])/(h[a]+h[b])
                    if endpoint*delta[a]<=0: endpoint = 0.
                    elif delta[a]*delta[b]<0 and abs(endpoint)>abs(3*delta[a]): endpoint = 3*delta[a]
                    slope[j] = endpoint
            result = np.column_stack((y[:-1],slope[:-1],(3*delta-2*slope[:-1]-slope[1:])/h,(slope[:-1]+slope[1:]-2*delta)/(h*h)))
    if not np.isfinite(result).all(): raise error('VALUES','曲线控制点病态或系数超出有限精度')
    return x,y,result


def evaluate(values, compiled):
    x,y,c = compiled
    if len(x)==1: return np.full(values.shape,y[0],np.float64)
    q = np.clip(values,x[0],x[-1]); index = np.clip(np.searchsorted(x,q,side='right')-1,0,len(c)-1)
    d = q-x[index]; k = c[index]
    with np.errstate(over='ignore',invalid='ignore'):
        result = ((k[:,3]*d+k[:,2])*d+k[:,1])*d+k[:,0]
    if not np.isfinite(result).all(): raise error('VALUES','曲线求值产生非有限值')
    # Constant endpoint extension and a bounded display-curve output are
    # explicit curve semantics, rather than an implicit working-RGB clamp.
    return np.clip(np.where(q==x[-1],y[-1],result),0,1)


def apply_curves(surface, plan, author_tick, *, working_signal, tile_pixels=65536,
                 retained_table_bytes=0, max_working_bytes=MAX_WORKING_BYTES, cancel=None):
    def poll():
        if cancel and cancel(): raise AppError('RENDER_CANCELLED','浮点曲线已取消',exit_code=6)
    poll()
    if not isinstance(plan,CurvePlan) or not isinstance(working_signal,ColorSignal) or working_signal.transfer!='linear':
        raise error('SIGNAL','曲线须使用编译计划和明确线性工作信号')
    if not isinstance(surface,np.ndarray) or surface.dtype!=np.float32 or surface.ndim!=3 or surface.shape[-1]!=4 or not surface.flags.c_contiguous:
        raise error('SURFACE','曲线输入须为连续H×W×4 Float32')
    h,w = surface.shape[:2]; pixels = h*w
    if min(h,w)<1 or max(h,w)>16384 or pixels>MAX_PIXELS: raise error('BUDGET','曲线表面超过尺寸预算')
    if type(tile_pixels) is not int or not 1<=tile_pixels<=262144: raise error('BUDGET','曲线分块大小无效')
    if type(max_working_bytes) is not int or not 1<=max_working_bytes<=MAX_WORKING_BYTES or type(retained_table_bytes) is not int or retained_table_bytes<0:
        raise error('BUDGET','曲线工作区预算无效')
    actual_tile = min(tile_pixels,16384)
    estimate = 3*surface.nbytes+retained_table_bytes+min(pixels,actual_tile)*1536+len(plan.tracks_json.encode('utf8'))+524288
    if estimate>max_working_bytes: raise error('BUDGET','曲线输入/输出、保留LUT及分块工作区估算超限')
    state,strength = state_at(plan,author_tick)
    compiled = {c:coefficients(points,plan.interpolation) for c,points in state.items()}
    source = surface.reshape(-1,4); output = np.empty_like(source)
    for start in range(0,pixels,actual_tile):
        poll(); value = source[start:start+actual_tile]; target = output[start:start+len(value)]
        if not np.isfinite(value).all() or np.any(value[:,3]<0) or np.any(value[:,3]>1): raise error('VALUES','曲线RGB须有限且alpha须在0到1')
        target[:] = value
        if strength==0: continue
        encoded,_ = convert_rgba(value.reshape(1,len(value),4),working_signal,plan.input_signal,
            tile_pixels=tile_pixels,max_working_bytes=max_working_bytes,cancel=cancel)
        flat = encoded.reshape(-1,4)
        for i,c in enumerate(CHANNELS):
            mapped = evaluate(flat[:,i].astype(np.float64),compiled.get(c,compiled['all']))
            if 'post_master' in compiled: mapped = evaluate(mapped,compiled['post_master'])
            flat[:,i] = mapped.astype(np.float32)
        graded,_ = convert_rgba(encoded,plan.output_signal,working_signal,tile_pixels=tile_pixels,max_working_bytes=max_working_bytes,cancel=cancel)
        rgb = graded.reshape(-1,4)[:,:3]
        with np.errstate(over='ignore',invalid='ignore'):
            target[:,:3] = rgb if strength==1 else (value[:,:3].astype(np.float64)*(1-strength)+rgb.astype(np.float64)*strength)
        if not np.isfinite(target).all(): raise error('VALUES','曲线输出超出Float32有限范围')
    poll()
    return output.reshape(surface.shape),{'protocol':PROTOCOL,'spatial_interpolation':plan.interpolation,
        'author_tick':str(author_tick),'intensity':strength,'points':state,
        'all_semantics':'fallback-not-post-master','post_master':'explicit-after-channels',
        'input_signal':vars(plan.input_signal),'output_signal':vars(plan.output_signal),'working_signal':vars(working_signal),
        'coordinate_precision':'binary64-no-integer-grid','curve_output_boundary':'clamp-zero-one-constant-endpoints',
        'mix_domain':'linear-working-straight-RGB','alpha':'input-bits-preserved','integer_intermediate':False,
        'estimated_working_bytes':estimate,'estimated_bytes_are_peak_RSS':False,
        'actual_tile_pixels_limit':actual_tile,'natural_quality_accepted':False,'HDR_accepted':False}
