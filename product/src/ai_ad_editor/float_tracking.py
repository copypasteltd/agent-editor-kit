"""Saved source-clock observations projected through the actual Float32 geometry.

No model runs here. Sampling uses original PTS and the timeline's own retime,
window, freeze and reverse clock. Geometry is the inverse used by the sampler,
not a second CFR approximation of the visual source.
"""
from bisect import bisect_right
from fractions import Fraction
import math

from .animation import keyframe_value
from .bindings import BINDING_VERSION, find_sources, source_references, validate_binding
from .clip_windows import validate_window
from .errors import AppError
from .sequence_canvas import sequence_canvas

PROTOCOL='native-PTS-float32-tracking-bindings-v1'
MAX_BINDINGS=128
MAX_OBSERVATIONS=64000
MAX_DEPTH=16
MAX_SOURCE_REFERENCES=4096

def error(kind,message):return AppError('FLOAT_TRACKING_'+kind,message,exit_code=2)

def binding_plan(project,sequence,track,target):
    validate_binding(project,sequence,track,target,native_clock=True)
    binding=target['tracking_binding']
    return dict(coordinate_space=BINDING_VERSION,host_protocol=PROTOCOL,
        source_clip_id=binding['source_clip_id'],source_track_id=binding['source_track_id'],
        source_fragments=[dict(r) for r in source_references(binding)],
        canvas=sequence_canvas(project,sequence),sampled_frames=0,hidden_frames=None,keyframes=[],
        warnings=['tracking_observations_interpolated_at_selected_original_PTS',
            'native_binding_is_dynamic_not_baked_to_display_FPS',
            'source_masks_transitions_and_occlusion_visibility_require_review'])

def forward(inverse,x,y):
    a,b,c=inverse[0];d,e,f=inverse[1];det=a*e-b*d
    if not math.isfinite(det) or det==0:raise error('GEOMETRY','源投影矩阵不可逆')
    px,py=((x-c)*e-b*(y-f))/det,(a*(y-f)-d*(x-c))/det
    if not math.isfinite(px) or not math.isfinite(py):raise error('GEOMETRY','跟踪锚点投影非有限')
    return px,py

class FloatTracking:
    def __init__(self,host):
        self.host=host;self.plans={};self.cache={};self.references={};count=0;reference_count=0
        self.clips={s['id']+'/'+c['id']:(s,t,c) for s in host.sequences.values() for t in s['tracks'] for c in t['clips']}
        rows=[]
        for path,(sequence,track,clip) in self.clips.items():
            if not clip.get('tracking_binding') or path not in host.effect_plans:continue
            host.poll();plan=binding_plan(host.project,sequence,track,clip)
            count+=len(clip['tracking_binding']['observations'])
            if len(self.plans)>=MAX_BINDINGS or count>MAX_OBSERVATIONS:
                raise error('BUDGET','原生绑定超过128项或64000条总观测')
            sources=find_sources(sequence,clip['tracking_binding']);reference_count+=len(sources)
            if reference_count>MAX_SOURCE_REFERENCES:raise error('BUDGET','原生绑定超过4096个总源分片引用')
            candidates=[dict(source_track=t,source=c,source_path=sequence['id']+'/'+c['id'],
                author_offset_tick=r.get('author_offset_tick',0)) for (t,c),r in zip(sources,source_references(clip['tracking_binding']))]
            self.plans[path]=dict(sequence=sequence,track=track,target=clip,binding=clip['tracking_binding'],
                sources=candidates,
                times=tuple(Fraction(str(p['at_seconds'])) for p in clip['tracking_binding']['observations']))
            rows.append(dict(target=path,source=candidates[0]['source_path'] if candidates else None,**plan))
        completed=set()
        def visit(path,stack):
            if path in stack or len(stack)>=MAX_DEPTH:raise error('CYCLE','绑定存在循环或超过16层')
            if path in completed:return
            if path in self.plans:
                for source in self.plans[path]['sources']:visit(source['source_path'],(*stack,path))
            completed.add(path)
        for path in self.plans:visit(path,())
        self.metadata=dict(protocol=PROTOCOL,plans=rows,bindings=len(rows),observations=count,
            clock='selected original PTS * native time base minus recorded demux origin; no CFR resnap',
            geometry='same crop/fit/TRS inverse as rendered source; integer pixel centres and half-pixel edges',
            ROI_reference='source geometry at target original author start; first observation if no native frame covers reference',
            scale_policy='existing binding clamp 0.01..20; source projected ROI-width ratio',
            alpha='binding base opacity automation times source transform and blend opacity',
            visibility='source clip coverage/range/crop/mute; masks/transitions/occlusion need separate review',
            model_inference=False,display_keyframes_baked=False,integer_intermediate=False,
            evaluations=0,hidden_evaluations=0,cache_hits=0,source_references=reference_count,
            edit_lineage='native-tracking-edit-lineage-v1; empty route is hidden',
            pinned_reference_clock='reference_output_tick on original complete source output')

    def reset_frame(self):self.cache.clear()

    def _source(self,plan,at,*,left_limit,stack,reference=False,pinned_reference=False):
        h=self.host;candidates=plan['sources']
        if not candidates:return dict(active=False,reason='source-route-empty-after-edit')
        def covered(candidate):
            c=candidate['source'];begin=Fraction(c['timeline_start_tick'],h.tps);end=begin+Fraction(c['duration_tick'],h.tps)
            return begin<at<=end if left_limit else begin<=at<end
        selected=next((c for c in candidates if covered(c)),None)
        if reference:
            selected=selected or min(candidates,key=lambda c:(max(Fraction(c['source']['timeline_start_tick'],h.tps)-at,
                at-Fraction(c['source']['timeline_start_tick']+c['source']['duration_tick'],h.tps),0),c['source']['timeline_start_tick'],c['source']['id']))
        if selected is None:return dict(active=False,reason='source-fragment-gap')
        source=selected['source'];track=selected['source_track'];path=selected['source_path']
        start=Fraction(source['timeline_start_tick'],h.tps);end=start+Fraction(source['duration_tick'],h.tps)
        covered=start<at<=end if left_limit else start<=at<end
        if track.get('muted') or not covered and not reference:
            return dict(active=False,reason='source-muted-or-outside-clip')
        if reference:
            window=source.get('presentation_window') or {}
            author_start=start-Fraction(int(window.get('offset_tick',0)),h.tps)
            author_end=author_start+Fraction(validate_window(source,allow_tracking=True),h.tps)
            if pinned_reference and 'reference_output_tick' in plan['binding']:
                at=author_start+Fraction(plan['binding']['reference_output_tick']+selected['author_offset_tick'],h.tps)
            at=max(author_start,min(author_end,at));left_limit=at==author_end
        local=at*h.tps-source['timeline_start_tick']
        source_time,tick,right=h._source_time(source,local,path,left_limit=left_limit)
        first,last=Fraction(source['source_in_tick'],h.tps),Fraction(source['source_out_tick'],h.tps)
        if not reference and not (first<=source_time<=last and (source_time!=last or right)):
            return dict(active=False,reason='source-outside-authored-source-window')
        provider=h.sources.get(source['asset_id'])
        if provider is None:raise error('SOURCE','绑定源缺少原生浮点提供器')
        frame,index=provider.sample(source_time,right_edge=right)
        fallback=frame is None and reference
        if fallback:
            frame,index=provider.sample(provider.pts[0]*provider.time_base-provider.origin)
        if frame is None:return dict(active=False,reason='source-native-coverage-missing')
        h.poll();native_tick=provider.pts[index-provider.source_frame_start]
        native_time=native_tick*provider.time_base-provider.origin
        b=plan['binding'];times=plan['times'];observations=b['observations']
        i=bisect_right(times,native_time);lo=max(0,i-1);hi=min(i,len(times)-1)
        left,right_ob=observations[lo],observations[hi]
        q=0. if hi==lo else max(0.,min(1.,float((native_time-times[lo])/(times[hi]-times[lo]))))
        point={k:left[k]+(right_ob[k]-left[k])*q for k in ('x','y','width','height','confidence')}
        if fallback:point={k:observations[0][k] for k in point}
        nested=self._evaluate(path,at,left_limit=left_limit,stack=stack,record=not reference) if path in self.plans else None
        canvas=sequence_canvas(h.project,plan['sequence']);height,width=frame.shape[:2]
        inverse,opacity,crop=h.projection(source,(width,height),canvas,tick,path,
            overrides=nested['values'] if nested else None)
        x,y=point['x']*width-.5,point['y']*height-.5
        px,py=forward(inverse,x,y);rx,ry=forward(inverse,x+point['width']*width,y)
        roi=math.hypot(rx-px,ry-py)
        if not math.isfinite(roi) or roi<=0:raise error('GEOMETRY','投影ROI宽度须为有限正数')
        inside=True
        if crop:
            cx,cy,cw,ch=crop['window'];inside=cx-.5<=x<cx+cw-.5 and cy-.5<=y<cy+ch-.5
        begin,finish=(Fraction(str(b['range'][k])) for k in ('start_seconds','end_seconds'))
        active=covered and begin<=native_time<finish and inside
        blend=source.get('blend') or {}
        opacity*=keyframe_value(source,('blend.opacity','blend_opacity'),float(blend.get('opacity',1)),float(tick))
        if not math.isfinite(opacity) or not 0<=opacity<=1:raise error('ALPHA','源绑定透明度须为有限0..1')
        return dict(active=active,reason=None if active else 'source-outside-observed-range-or-crop',
            source_fragment=path,
            x=(px+.5)/canvas['width'],y=(py+.5)/canvas['height'],roi_width_pixels=roi,
            rotation=math.degrees(math.atan2(ry-py,rx-px)),opacity=opacity,
            native_frame_index=index,native_pts=native_tick,native_time=str(native_time),
            source_author_tick=str(tick),source_time=str(source_time),inside_crop=inside,
            confidence=point['confidence'],held_observation=i==0 or i==len(times) and native_time>times[-1],
            reference_fallback=fallback)

    def _reference(self,path,plan,stack):
        if path not in self.references:
            target=plan['target'];h=self.host
            origin=target['timeline_start_tick']-int((target.get('presentation_window') or {}).get('offset_tick',0))
            origin+=int((target.get('_source_handle') or {}).get('head_tick',0))
            value=self._source(plan,Fraction(origin,h.tps),left_limit=False,stack=stack,reference=True,pinned_reference=True)
            if 'roi_width_pixels' not in value:raise error('REFERENCE','ROI绑定基准不可用')
            self.references[path]=value
        return self.references[path]

    def _evaluate(self,path,at,*,left_limit=False,stack=(),record=True):
        self.host.poll()
        if path in stack or len(stack)>=MAX_DEPTH:raise error('CYCLE','绑定求值循环或超过16层')
        key=(path,at,left_limit,record)
        if key in self.cache:
            if record:self.metadata['cache_hits']+=1
            return self.cache[key]
        plan=self.plans[path];h=self.host;target=plan['target'];b=plan['binding']
        state=self._source(plan,at,left_limit=left_limit,stack=(*stack,path),reference=not record)
        values={'opacity':0.}
        if 'x' in state:
            local=at*h.tps-target['timeline_start_tick']
            _,tick,_=h._source_time(target,local,path,left_limit=left_limit)
            base=b['base'];alpha=keyframe_value({'keyframes':[dict(property='opacity',keyframes=base['opacity_keyframes'])]},
                ('opacity',),base['opacity'],float(tick))
            if not math.isfinite(alpha) or not 0<=alpha<=1:raise error('ALPHA','目标绑定透明度须为有限0..1')
            values.update({'position.x':state['x']+b['offset']['x'],'position.y':state['y']+b['offset']['y'],
                'opacity':alpha*state['opacity'] if state['active'] else 0.})
            if b['scale_mode']=='roi' or b['rotation_mode']=='source':
                reference=self._reference(path,plan,(*stack,path))
                if b['scale_mode']=='roi':
                    raw=base['scale']*b['scale_multiplier']*state['roi_width_pixels']/reference['roi_width_pixels']
                    values['scale']=max(.01,min(20.,raw));state['scale_clamped']=raw!=values['scale']
                if b['rotation_mode']=='source':values['rotation']=base['rotation']+state['rotation']-reference['rotation']
        result=dict(protocol=PROTOCOL,source=state.get('source_fragment'),values=values,**state)
        self.cache[key]=result
        if record:
            self.metadata['evaluations']+=1
            self.metadata['hidden_evaluations']+=not state['active']
        return result

    def evaluate(self,path,at,*,left_limit=False):
        return self._evaluate(path,at,left_limit=left_limit) if path in self.plans else None
