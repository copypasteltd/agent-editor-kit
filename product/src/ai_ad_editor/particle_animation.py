"""Source-clock emitter curves and integrated, seekable particle birth schedules."""
from __future__ import annotations

from bisect import bisect_left
from collections import OrderedDict
import copy
from dataclasses import dataclass
from fractions import Fraction as F
import math

from .animation import bezier_samples
from .errors import AppError

PROTOCOL = 'source-anchored-emitter-keyframes-v1'
INTERPOLATIONS = ('hold', 'linear', 'ease_in', 'ease_out', 'ease_in_out', 'bezier')
BIRTH = frozenset(('lifetime','position','spread','velocity','acceleration','rotation','spin','sway','twinkle'))
LIVE = frozenset(('size','size_end','aspect','shape','softness','glow','colors','color_end','opacity','fade_in','fade_out'))
PROPERTIES = BIRTH | LIVE | {'rate'}
MAX_POINTS = 64


def fail(message, **details):
    return AppError('PARTICLE_ANIMATION', message, exit_code=2, diagnostics=details or None)


def normalize_tracks(raw, duration, parameter):
    if not isinstance(raw, list) or not 1 <= len(raw) <= len(PROPERTIES):
        raise fail('发射器关键帧要求非空且有界的属性轨道列表')
    tracks=[];seen=set()
    for track in raw:
        if not isinstance(track, dict) or set(track)!={'property','keyframes'}:
            raise fail('发射器动画轨道只接受property和keyframes')
        key=track['property']
        if not isinstance(key,str) or key not in PROPERTIES or key in seen:
            raise fail('发射器动画属性未知或重复',property=key)
        seen.add(key);points=track['keyframes']
        if not isinstance(points,list) or not 1<=len(points)<=MAX_POINTS:
            raise fail('每个发射器属性需要1..64个关键帧',property=key)
        values=[]
        for point in points:
            if (not isinstance(point,dict) or set(point)-{'at_tick','value','interpolation','control_points'}
                    or not {'at_tick','value'}<=set(point)):
                raise fail('发射器关键帧字段不支持',property=key)
            tick=point['at_tick']
            if type(tick) is not int or not 0<=tick<=duration:
                raise fail('发射器关键帧必须在原始源时钟范围内',property=key)
            mode=point.get('interpolation','hold' if key=='shape' else 'linear')
            if mode not in INTERPOLATIONS:
                raise fail('发射器关键帧插值不支持',property=key)
            item={'at_tick':tick,'value':parameter(key,copy.deepcopy(point['value'])),'interpolation':mode}
            controls=point.get('control_points')
            if mode=='bezier':
                if (not isinstance(controls,list) or len(controls) not in (2,4) or
                        any(type(v) not in (int,float) or not math.isfinite(v) or not 0<=v<=1 for v in controls)):
                    raise fail('粒子bezier要求2或4个0..1控制数，避免资源参数超调',property=key)
                item['control_points']=[float(v) for v in controls]
            elif controls is not None:
                raise fail('只有bezier插值可声明control_points',property=key)
            values.append(item)
        values.sort(key=lambda v:v['at_tick'])
        if len({p['at_tick'] for p in values})!=len(values):
            raise fail('同一发射器属性的关键帧时刻不能重复',property=key)
        for left,right in zip(values,values[1:]):
            if left['interpolation']=='hold':continue
            if key=='shape' or (key=='color_end' and (left['value'] is None or right['value'] is None)):
                raise fail('形状和空颜色端点切换要求hold插值',property=key)
            if key=='colors' and len(left['value'])!=len(right['value']):
                raise fail('连续调色板动画要求相同颜色数量；改数量须使用hold',property=key)
        tracks.append({'property':key,'keyframes':values})
    return sorted(tracks,key=lambda t:t['property'])


def maximum(emitter, key, component=None):
    track=next((t for t in emitter.get('keyframes',[]) if t['property']==key),None)
    values=[p['value'] for p in track['keyframes']] if track else [emitter[key]]
    return max(v[component] if component is not None else v for v in values)


def pieces(point):
    """Return exact rational polynomials matching the common easing lookup."""
    mode=point['interpolation']
    if mode=='hold':return [(F(0),F(1),(F(0),))]
    if mode=='linear':return [(F(0),F(1),(F(0),F(1)))]
    if mode=='ease_in':return [(F(0),F(1),(F(0),F(0),F(1)))]
    if mode=='ease_out':return [(F(0),F(1),(F(0),F(2),F(-1)))]
    if mode=='ease_in_out':return [(F(0),F(1,2),(F(0),F(0),F(2))),
                                  (F(1,2),F(1),(F(-1),F(4),F(-2)))]
    samples=bezier_samples(point['control_points']);result=[]
    for i in range(32):
        start=F(f'{samples[i]:.8f}');slope=F(f'{(samples[i+1]-samples[i])*32:.8f}')
        lo,hi=F(i,32),F(i+1,32);offset=start-slope*lo;cuts={lo,hi}
        if slope:
            cuts.update(p for p in ((-offset)/slope,(1-offset)/slope) if lo<p<hi)
        ordered=sorted(cuts)
        for a,b in zip(ordered,ordered[1:]):
            middle=offset+slope*(a+b)/2
            result.append((a,b,(F(0),) if middle<0 else (F(1),) if middle>1 else (offset,slope)))
    return result


def primitive(coefficients,p):
    return sum(c*p**(i+1)/(i+1) for i,c in enumerate(coefficients))


@dataclass(frozen=True)
class Segment:
    origin: F
    span: F
    low: F
    high: F
    coefficients: tuple
    phase: F
    end_phase: F


class BirthSchedule:
    """Integral phases use rationals; inverse roots have a bounded local cache."""
    def __init__(self,emitter,tps,duration,*,cancel=None):
        self.poll=cancel or (lambda:None)
        self.cache_limit=max(2,min(8192,2*(math.ceil(maximum(emitter,'rate')*maximum(emitter,'lifetime',1))+1)))
        points=next((t['keyframes'] for t in emitter.get('keyframes',[]) if t['property']=='rate'),
                    [{'at_tick':0,'value':emitter['rate'],'interpolation':'hold'}])
        self.rate_zero=F(str(points[0]['value']));self.segments=[];self.phase_ends=[];self.cache=OrderedDict()
        phase=F(0)
        def append(origin,span,lo,hi,coefficients):
            nonlocal phase
            coefficients=tuple(coefficients)
            end=phase+span*(primitive(coefficients,hi)-primitive(coefficients,lo))
            if end<phase:raise fail('发射率曲线出现负积分')
            self.segments.append(Segment(origin,span,lo,hi,coefficients,phase,end))
            self.phase_ends.append(end);phase=end
        if points[0]['at_tick']:
            append(F(0),F(points[0]['at_tick'],tps),F(0),F(1),(self.rate_zero,))
        for left,right in zip(points,points[1:]):
            origin=F(left['at_tick'],tps);span=F(right['at_tick']-left['at_tick'],tps)
            a,b=F(str(left['value'])),F(str(right['value']))
            for lo,hi,poly in pieces(left):
                coeff=[(b-a)*v for v in poly];coeff[0]+=a
                append(origin,span,lo,hi,coeff)
        if points[-1]['at_tick']<duration:
            append(F(points[-1]['at_tick'],tps),F(duration-points[-1]['at_tick'],tps),F(0),F(1),
                   (F(str(points[-1]['value'])),))
        self.first_positive=next((s.origin+s.span*s.low for s in self.segments if s.end_phase>s.phase),None)
        self.time_ends=[s.origin+s.span*s.high for s in self.segments]
        self.key_roots={}
        self.event_times=[];self.event_phases=[]
        for tick in sorted({p['at_tick'] for t in emitter.get('keyframes',[]) for p in t['keyframes']}):
            point=F(tick,tps);phase_at_key=self.phase_at(point)
            self.event_times.append(point);self.event_phases.append(phase_at_key)
            if phase_at_key>0 and phase_at_key.denominator==1:
                self.key_roots.setdefault(int(phase_at_key),point)

    def phase_at(self,at):
        at=F(at)
        if at<0:return at*self.rate_zero
        index=min(len(self.segments)-1,bisect_left(self.time_ends,at))
        s=self.segments[index];p=(at-s.origin)/s.span
        return s.phase+s.span*(primitive(s.coefficients,p)-primitive(s.coefficients,s.low))

    def birth_at(self,number):
        if number<0:return F(number)/self.rate_zero if self.rate_zero else None
        if number==0:return self.first_positive
        if number in self.cache:
            self.cache.move_to_end(number);return self.cache[number]
        index=bisect_left(self.phase_ends,number)
        if index==len(self.segments):return None
        s=self.segments[index]
        if number==s.end_phase:result=s.origin+s.span*s.high
        elif number==s.phase:result=s.origin+s.span*s.low
        elif number in self.key_roots:result=self.key_roots[number]
        elif len(s.coefficients)==1:
            result=s.origin+s.span*s.low+(F(number)-s.phase)/s.coefficients[0]
        else:
            # Rational inverse brackets never move a birth past an exact frame
            # or authored step. Return a deterministic lower bound (<=2^-64
            # of this segment); no answer depends on the requested frame time.
            low,high=s.low,s.high
            # The approximation must stay on the correct side of every authored
            # hold/step, even for a birth arbitrarily close to that exact tick.
            event=bisect_left(self.event_phases,number)
            if event:low=max(low,(self.event_times[event-1]-s.origin)/s.span)
            if event<len(self.event_times):high=min(high,(self.event_times[event]-s.origin)/s.span)
            target=(F(number)-s.phase)/s.span+primitive(s.coefficients,s.low)
            for step in range(64):
                if step%8==0:self.poll()
                mid=(low+high)/2
                value=primitive(s.coefficients,mid)
                if value==target:low=high=mid;break
                if value<target:low=mid
                else:high=mid
            result=s.origin+s.span*low
        self.cache[number]=result
        if len(self.cache)>self.cache_limit:self.cache.popitem(last=False)
        return result

    def births(self,at,max_lifetime,prewarm):
        low=math.ceil(self.phase_at(at-F(str(max_lifetime))))
        if not prewarm:low=max(0,low)
        high=math.floor(self.phase_at(at))
        for number in range(low,high+1):
            birth=self.birth_at(number)
            if birth is not None and birth<=at:yield number,birth


def blend(left,right,p):
    if isinstance(left,list):return [blend(a,b,p) for a,b in zip(left,right)]
    return left+(right-left)*p


class EmitterAnimation:
    def __init__(self,emitter,tps,duration,color_linear,*,cancel=None):
        self.emitter=emitter;self.tps=tps
        self.tracks={t['property']:copy.deepcopy(t['keyframes']) for t in emitter['keyframes']}
        self.bases={key:copy.deepcopy(emitter[key]) for key in PROPERTIES if key!='rate'}
        def convert(key,value):
            if key=='colors':return [color_linear(v).tolist() for v in value]
            if key=='color_end':return color_linear(value).tolist() if value is not None else None
            return value
        for key in self.bases:
            self.bases[key]=convert(key,self.bases[key])
            for p in self.tracks.get(key,[]):p['value']=convert(key,p['value'])
        self.schedule=BirthSchedule(emitter,tps,duration,cancel=cancel)
        self.birth_cache=OrderedDict()
        self.max_lifetime=maximum(emitter,'lifetime',1)
        self.metadata={'protocol':PROTOCOL,'clock':'original-generator-ticks','properties':sorted(self.tracks),
            'birth_sampled':sorted(BIRTH&self.tracks.keys()),'live_sampled':sorted(LIVE&self.tracks.keys()),
            'birth_rate':'exact-rational-integral;monotone-inverse;stable-integer-birth-ID',
            'inverse_cache_limit':self.schedule.cache_limit,'birth_cache_limit':self.schedule.cache_limit,
            'inverse_precision':'64_rational_bisections;lower_bound_error_le_segment_seconds/2^64',
            'max_keyframes_per_property':MAX_POINTS}

    def value(self,key,tick):
        points=self.tracks.get(key)
        if not points:return self.bases[key]
        if tick<points[0]['at_tick']:return points[0]['value']
        for left,right in zip(points,points[1:]):
            if tick>=right['at_tick']:continue
            if left['interpolation']=='hold':return left['value']
            p=float((tick-left['at_tick'])/(right['at_tick']-left['at_tick']))
            # Same serialized easing samples/polynomials as the shared renderer.
            lo,hi,coeff=next(v for v in pieces(left) if v[0]<=p<v[1] or p==1 and v[1]==1)
            weight=sum(float(c)*p**i for i,c in enumerate(coeff))
            return blend(left['value'],right['value'],max(0.,min(1.,weight)))
        return points[-1]['value']

    def live(self,seconds):return {key:self.value(key,seconds*self.tps) for key in LIVE}
    def born(self,seconds):
        if seconds in self.birth_cache:
            self.birth_cache.move_to_end(seconds);return self.birth_cache[seconds]
        values={key:self.value(key,seconds*self.tps) for key in BIRTH}
        self.birth_cache[seconds]=values
        if len(self.birth_cache)>self.schedule.cache_limit:self.birth_cache.popitem(last=False)
        return values
