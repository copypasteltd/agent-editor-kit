"""Author-clock Float32 sequence evaluation over explicitly supplied surfaces.

This frame host is a library boundary for the upcoming streaming renderer.
It does not invoke the legacy graph, decode files, render audio or silently
approximate unsupported effects. The authored project is never rewritten.
"""
from __future__ import annotations
from bisect import bisect_left,bisect_right
import copy,math,re
from fractions import Fraction
from typing import Callable
import numpy as np
from .animation import keyframe_value
from .clip_windows import validate_window
from .errors import AppError
from .float_color_signal import ColorSignal,convert_rgba
from .float_composite import composite_rgba
from .float_geometry import resample_rgba
from .float_mask import compile_mask, apply_mask
from .float_crop import compile_crop, project_crop
from .float_effect_chain import EffectCompiler
from .float_transitions import transition_rgba, PROTOCOL as TRANSITION_PROTOCOL, TYPES as TRANSITION_TYPES
from .float_transition_plan import compile_track
from .float_text import FloatTextHost
from .source_transitions import compile_for_render
from .float_raster import mode_name
from .sequence_canvas import sequence_canvas
from .speed_curves import compile_curve
from .time_mapping import make_map,unmap_time

PROTOCOL='author-clock-float32-frame-host-v1'
MAX_CLIPS=4096
MAX_DEPTH=16
MAX_LAYERS_PER_FRAME=128
MAX_SURFACE_BYTES=256*1024**2
TRANSFORM_PROPERTIES={'transform.scale','scale','transform.rotation','rotation','transform.opacity','opacity',
    'transform.position.x','position.x','position_x','transform.position.y','position.y','position_y',
    'transform.anchor.x','anchor.x','anchor_x','transform.anchor.y','anchor.y','anchor_y','blend.opacity','blend_opacity'}
MASK_PROPERTIES={'rectangle':{'mask.x','mask.position.x','mask.y','mask.position.y','mask.width','mask.w','mask.height','mask.h'},
    'circle':{'mask.cx','mask.center_x','mask.cy','mask.center_y','mask.radius'},
    'ellipse':{'mask.cx','mask.center_x','mask.cy','mask.center_y','mask.rx','mask.radius_x','mask.ry','mask.radius_y'}}

def error(code,message,**details):return AppError('FLOAT_TIMELINE_'+code,message,exit_code=2,diagnostics=details or None)

def integer(value,minimum=0):
    if type(value) is not int or value<minimum:raise error('CLOCK','作者时钟必须为范围内整数，不能使用布尔值或浮点数')
    return value

class TimedSurfaceSource:
    """Native clock plus a supplied bounded random-access frame callback.

    Points are absolute native PTS; source selection is demux-relative. Holds
    run to the next PTS, and the final duration establishes known video EOF.
    A missing final duration is not inferred from average FPS. Right-edge
    sampling implements reversed half-open display intervals exactly.
    """
    def __init__(self,pts,durations,time_base,demux_origin,fetch:Callable,*,signal:ColorSignal,
                 source_sha256:str,verify=None,still=False,source_frame_start=0):
        if not callable(fetch) or not isinstance(signal,ColorSignal):raise error('SOURCE','帧源须提供明确取帧函数和RGB信号')
        if not isinstance(source_sha256,str) or not re.fullmatch('sha256:[0-9a-f]{64}',source_sha256):raise error('SOURCE','帧源须绑定原始资产SHA')
        if type(still) is not bool or type(source_frame_start) is not int or source_frame_start<0:raise error('SOURCE','图片标记或原始帧偏移无效')
        self.still=still;self.source_frame_start=source_frame_start
        self.pts=tuple(pts);self.durations=tuple(durations)
        if not self.pts or len(self.pts)!=len(self.durations) or len(self.pts)>1000000:raise error('CLOCK','原生时钟数组无效或超限')
        if any(type(v) is not int or not -(2**63)<=v<2**63 for v in (*self.pts,*self.durations)):
            raise error('CLOCK','原生PTS/时长须为signed int64')
        if any(v<0 for v in self.durations) or any(a>=b for a,b in zip(self.pts,self.pts[1:])):raise error('CLOCK','原生PTS须严格递增且时长非负')
        if still and len(self.pts)!=1:raise error('SOURCE','静态图片必须只有一个原始表面')
        try:self.time_base=Fraction(time_base);self.origin=Fraction(demux_origin)
        except (ValueError,TypeError,ZeroDivisionError) as caught:raise error('CLOCK','须提供明确有理数时间基和容器起点') from caught
        if self.time_base<=0:raise error('CLOCK','原生时间基必须为正')
        if verify is not None and not callable(verify):raise error('SOURCE','源验证回调无效')
        self.fetch=fetch;self.signal=signal;self.sha256=source_sha256;self.verify_callback=verify

    def index_at(self,source_time,*,right_edge=False):
        try:point=(Fraction(source_time)+self.origin)/self.time_base
        except (ValueError,TypeError,ZeroDivisionError) as caught:raise error('CLOCK','取帧时间必须是有理数') from caught
        if self.still:return 0
        index=(bisect_left(self.pts,point) if right_edge else bisect_right(self.pts,point))-1
        if index<0:return None
        last=self.pts[-1];duration=self.durations[-1]
        if index==len(self.pts)-1:
            if duration==0:raise error('EOF_UNKNOWN','末帧原生duration未知，不能推测EOF或补帧')
            end=last+duration
            if point>end or (point==end and not right_edge):return None
        return index

    def sample(self,source_time,*,right_edge=False):
        index=self.index_at(source_time,right_edge=right_edge)
        if index is None:return None,None
        value=self.fetch(index)
        if not isinstance(value,np.ndarray) or value.dtype!=np.float32 or value.ndim!=3 or value.shape[-1]!=4 or not value.flags.c_contiguous:
            raise error('SURFACE','取帧函数必须返回连续H×W×4 Float32')
        if value.nbytes>MAX_SURFACE_BYTES:raise error('BUDGET','单帧RGBA超过256MiB')
        if not min(value.shape[:2]):raise error('SURFACE','帧表面不能为空')
        return value,index+self.source_frame_start

    def verify(self):
        if self.verify_callback is not None:self.verify_callback()

class FloatTimeline:
    def __init__(self,project,sequence_id,sources,*,working_signal,background_signal=ColorSignal('bt709','srgb'),cancel=None,
                 max_working_bytes=768*1024*1024,resource_root=None,gpu=None):
        if not isinstance(working_signal,ColorSignal) or not isinstance(background_signal,ColorSignal):raise error('SIGNAL','工作与背景RGB信号须明确')
        if cancel is not None and not callable(cancel):raise error('ARGUMENT','取消回调无效')
        self.project=copy.deepcopy(project);self.sources=dict(sources);self.working=working_signal;self.background_signal=background_signal
        if type(max_working_bytes) is not int or not 1<=max_working_bytes<=768*1024*1024:
            raise error('BUDGET','浮点投影/合成的单次工作区配额须在1字节到768MiB')
        self.max_working_bytes=max_working_bytes
        self.gpu=gpu
        self.poll=cancel if cancel is not None else lambda:None;self.poll()
        self.effects=EffectCompiler(resource_root=resource_root,working_signal=self.working,
            max_working_bytes=self.max_working_bytes,cancel=self.poll)
        self.settings=self.project['settings'];base=self.settings['timebase'];fps=base['display_fps']
        self.tps=integer(base['ticks_per_second'],1);self.fps=Fraction(integer(fps['num'],1),integer(fps['den'],1))
        if self.tps<1 or self.fps<=0 or self.fps>1000:raise error('CLOCK','作者时间基或帧率无效')
        self.sequences={s['id']:s for s in self.project['sequences']};self.sequence_id=sequence_id
        if len(self.sequences)!=len(self.project['sequences']):raise error('SEQUENCE','序列ID重复')
        if sequence_id not in self.sequences:raise error('SEQUENCE','目标作者序列不存在')
        self.assets={a['id']:a for a in self.project['assets']};self.maps={};self.effect_plans={};self.mask_plans={};self.crop_plans={};self.clip_count=0
        self.source_transition_plans={};self.transition_plans={};self.text_plans={}
        self.text_host=FloatTextHost(resource_root,self.assets,self.working,self.tps,self.fps,
            cancel=self.poll,max_working_bytes=self.max_working_bytes,gpu=gpu)
        if len(self.assets)!=len(self.project['assets']):raise error('SOURCE','资产ID重复')
        self._validate(sequence_id,());sequence=self.sequences[sequence_id]
        self.frame_count=math.ceil(Fraction(int(sequence['duration_tick']),self.tps)*self.fps)
        self.metadata={'protocol':PROTOCOL,'sequence_id':sequence_id,'display_fps':str(self.fps),'frames':self.frame_count,
            'working_signal':{'primaries':working_signal.primaries,'transfer':working_signal.transfer},
            'scalar_clock':'exact rational source/display intervals','curve_clock':'existing adaptive Float64 author clock;see compilation certificate',
            'native_holds':'original PTS to next PTS;last native duration establishes EOF',
            'nested_clock':'continuous author time;exact left/right limits propagated through reversal',
            'transitions':{'protocol':TRANSITION_PROTOCOL,'patterns':sorted(TRANSITION_TYPES),
                'source_handle_plans':[p for p in self.source_transition_plans.values() if p],
                'double_source_over_crossfade':False,'group_spatial_edges':True,'GPU':False},
            'text':self.text_host.metadata,'GPU':gpu.evidence if gpu is not None else {'status':'off'},
            'input_contract':'validated Agent Project IR;registered SHA and explicit common working RGB signal',
            'audio_rendered':False,'legacy_render_preview_cache_integrated':False,'HDR_accepted':False,'network':False}

    def _validate(self,sequence_id,stack):
        if sequence_id in stack or len(stack)>=MAX_DEPTH:raise error('NESTING','嵌套循环或超过16层')
        sequence=self.sequences[sequence_id];canvas=sequence_canvas(self.project,sequence)
        integer(sequence['duration_tick'],1)
        if sequence_id not in self.source_transition_plans:
            _,sequence,plan=compile_for_render(self.project,sequence_id)
            self.source_transition_plans[sequence_id]=plan
            self.sequences[sequence_id]=sequence
        if canvas['width']*canvas['height']*16>MAX_SURFACE_BYTES:raise error('BUDGET','作者画布超过256MiB表面')
        ids=set()
        for track in sequence['tracks']:
            if track.get('muted') or track['kind']=='audio':continue
            if track['kind'] not in ('video','subtitle') and track.get('clips'):raise error('UNSUPPORTED','该帧宿主尚未接入此轨道类型',track=track['id'],kind=track['kind'])
            self.transition_plans[sequence_id+'/'+track['id']]=compile_track(track,self.tps,self.source_transition_plans[sequence_id])
            for clip in track['clips']:
                self.clip_count+=1
                if self.clip_count>MAX_CLIPS:raise error('BUDGET','展开作者片段数超过4096')
                path=sequence_id+'/'+str(clip['id'])
                if clip['id'] in ids:raise error('SEQUENCE','轨道内片段ID重复',clip=path)
                ids.add(clip['id'])
                if clip.get('tracking_binding'):raise error('UNSUPPORTED','该作者操作尚未连接浮点宿主，不进行旧路径回落',clip=path,operation='tracking_binding')
                independent_text=track['kind']=='subtitle'
                if clip.get('generator') and (not independent_text or clip['generator']!={'type':'text'}):
                    raise error('UNSUPPORTED','浮点生成器仅支持字幕轨道的明确type=text',clip=path,operation='generator')
                if independent_text or clip.get('subtitle') or clip.get('generator'):
                    self.text_plans[path]=self.text_host.prepare(clip,independent=independent_text)
                self.effect_plans[path]=self.effects.compile(clip.get('effects',[]))
                if self.effect_plans[path] and self.working.transfer!='linear':raise error('SIGNAL','浮点效果链要求线性光工作域',clip=path)
                integer(clip['timeline_start_tick']);integer(clip['duration_tick'],1);integer(clip['source_in_tick']);integer(clip['source_out_tick'],1)
                if clip['source_out_tick']<=clip['source_in_tick']:
                    raise error('CLOCK','作者片段范围无效',clip=path)
                authored=validate_window(clip);freeze=clip.get('freeze') or {};freeze_duration=integer(freeze.get('duration_tick',0));freeze_at=integer(freeze.get('at_tick',0))
                if freeze_duration>=authored or freeze_at>authored-freeze_duration:
                    raise error('FREEZE','冻结区间无效',clip=path)
                mode_name((clip.get('blend') or {}).get('mode','normal'))
                self.mask_plans[path]=compile_mask(clip)
                self.crop_plans[path]=compile_crop(clip)
                allowed=TRANSFORM_PROPERTIES|(self.mask_plans[path].properties if self.mask_plans[path] else set())|(self.crop_plans[path].properties if self.crop_plans[path] else set())
                properties=[frame.get('property') for frame in clip.get('keyframes',[])]
                if any(p not in allowed for p in properties) or len(set(properties))!=len(properties):raise error('UNSUPPORTED','关键帧属性尚未接入或重复',clip=path)
                if (clip.get('transform') or {}).get('opacity_keyframes'):raise error('UNSUPPORTED','独立透明度轨道尚未接入',clip=path)
                try:speed=Fraction(str(clip.get('speed',1)))
                except (ValueError,ZeroDivisionError) as caught:raise error('CLOCK','速度必须为正有限数字') from caught
                if speed<=0:raise error('CLOCK','速度必须为正有限数字')
                if clip.get('sequence_id'):
                    child=clip['sequence_id']
                    if child not in self.sequences:raise error('SEQUENCE','子序列不存在',clip=path)
                    self._validate(child,(*stack,sequence_id))
                elif not independent_text:
                    asset_id=clip.get('asset_id');asset=self.assets.get(asset_id);source=self.sources.get(asset_id)
                    if not asset or asset.get('kind') not in ('video','image') or not isinstance(source,TimedSurfaceSource):raise error('SOURCE','片段需要已登记本地视频/图片及对应浮点源',clip=path)
                    if source.sha256!=asset.get('sha256') or source.signal!=self.working:raise error('SOURCE','源SHA或共同工作RGB信号不一致',clip=path)
                    if (asset['kind']=='image')!=source.still:raise error('SOURCE','静态图片/视频源类型不一致',clip=path)
                raw=copy.deepcopy(clip);raw['timeline_start_tick']=0;raw['duration_tick']=authored-freeze_duration
                if clip.get('speed_curve'):
                    span=int(clip['source_out_tick'])-int(clip['source_in_tick']);segments=compile_curve(raw,span,self.tps)
                    self.maps[path]=make_map(raw,segments,self.tps)

    def _source_time(self,clip,local_tick,path,*,left_limit=False):
        window=clip.get('presentation_window') or {};elapsed=local_tick+int(window.get('offset_tick',0))
        animation_tick=elapsed-int((clip.get('_source_handle') or {}).get('head_tick',0))
        freeze=clip.get('freeze') or {};at=int(freeze.get('at_tick',0));duration=int(freeze.get('duration_tick',0))
        held=duration and ((at<elapsed<=at+duration) if left_limit else (at<=elapsed<at+duration))
        if held:elapsed=Fraction(at)
        elif duration and elapsed>=at+duration:elapsed-=duration
        start,end=Fraction(int(clip['source_in_tick']),self.tps),Fraction(int(clip['source_out_tick']),self.tps)
        reverse=bool(clip.get('reverse'))
        if path in self.maps:
            if elapsed==0:result=end if reverse else start
            elif elapsed==validate_window(clip)-duration:result=start if reverse else end
            else:result=Fraction.from_float(unmap_time(self.maps[path],float(elapsed/self.tps)))
        else:
            speed=Fraction(str(clip.get('speed',1)))
            if speed<=0:raise error('CLOCK','速度必须为正',clip=path)
            result=(end-elapsed/self.tps*speed) if reverse else (start+elapsed/self.tps*speed)
        right_edge=reverse if held else reverse!=left_limit
        if held and result==start:right_edge=False
        if held and result==end:right_edge=True
        if left_limit:animation_tick=math.nextafter(float(animation_tick),-math.inf)
        return result,animation_tick,right_edge

    def _project(self,clip,surface,canvas,tick,path,*,extra_rotation=0.):
        transform=clip.get('transform') or {};position=transform.get('position') or {};anchor=transform.get('anchor') or {}
        def value(names,default):return keyframe_value(clip,names,float(default),float(tick))
        scale=value(('transform.scale','scale'),transform.get('scale',1));angle=value(('transform.rotation','rotation'),transform.get('rotation',0))+extra_rotation
        opacity=value(('transform.opacity','opacity'),transform.get('opacity',1))
        px=value(('transform.position.x','position.x','position_x'),position.get('x',transform.get('position_x',.5)));py=value(('transform.position.y','position.y','position_y'),position.get('y',transform.get('position_y',.5)))
        ax=value(('transform.anchor.x','anchor.x','anchor_x'),anchor.get('x',transform.get('anchor_x',.5)))
        ay=value(('transform.anchor.y','anchor.y','anchor_y'),anchor.get('y',transform.get('anchor_y',.5)))
        if not all(math.isfinite(v) for v in (scale,angle,opacity,px,py,ax,ay)) or scale<=0 or not 0<=opacity<=1:raise error('GEOMETRY','变换包含无效值')
        height,width=surface.shape[:2];cw,ch=canvas['width'],canvas['height']
        if self.crop_plans[path] is not None:
            result,crop_metadata=project_crop(surface,self.crop_plans[path],tick,(cw,ch),scale=scale,rotation=angle,
                position=(px,py),anchor=(ax,ay),max_working_bytes=self.max_working_bytes,cancel=self.poll)
            mask_metadata=None
            if self.mask_plans[path] is not None:
                result,mask_metadata=apply_mask(result,self.mask_plans[path],tick,max_working_bytes=self.max_working_bytes,cancel=self.poll)
            return result,opacity,crop_metadata['inverse'],mask_metadata,crop_metadata
        zoom=min(cw/width,ch/height)*scale;c,s=math.cos(math.radians(angle))/zoom,math.sin(math.radians(angle))/zoom
        anchor_x,anchor_y=width*ax-.5,height*ay-.5;dest_x,dest_y=cw*px-.5,ch*py-.5
        inverse=[[c,s,anchor_x-c*dest_x-s*dest_y],[-s,c,anchor_y+s*dest_x-c*dest_y]]
        mask_metadata=None
        if self.mask_plans[path] is not None:
            surface,mask_metadata=apply_mask(surface,self.mask_plans[path],tick,max_working_bytes=self.max_working_bytes,cancel=self.poll)
        result,_=self.resample(surface,(cw,ch),inverse)
        return result,opacity,inverse,mask_metadata,None

    def resample(self,surface,size,inverse):
        if self.gpu is not None and self.gpu.active:
            return self.gpu.resample(surface,size,inverse)
        return resample_rgba(surface,size,inverse,max_working_bytes=self.max_working_bytes,cancel=self.poll)

    def composite(self,a,b,*,mode='normal',opacity=1.):
        if mode=='normal' and self.gpu is not None and self.gpu.active:
            return self.gpu.over(a,b,opacity),{'GPU':True,'mode':mode,'opacity':opacity}
        return composite_rgba(a,b,mode=mode,opacity=opacity,max_working_bytes=self.max_working_bytes,cancel=self.poll)

    def _layer(self,sequence_id,clip,at,canvas,rows,depth,left_limit):
        self.poll()
        if len(rows)>=MAX_LAYERS_PER_FRAME:raise error('BUDGET','同帧片段数超过128')
        path=sequence_id+'/'+str(clip['id'])
        local_tick=at*self.tps-int(clip['timeline_start_tick'])
        source_time,tick,right=self._source_time(clip,local_tick,path,left_limit=left_limit)
        text_plan=self.text_plans.get(path);text_metadata=None;extra_rotation=0.
        text_tick=local_tick+int((clip.get('presentation_window') or {}).get('offset_tick',0))-int((clip.get('_source_handle') or {}).get('head_tick',0))
        frame_index=None;source=None
        start,end=Fraction(int(clip['source_in_tick']),self.tps),Fraction(int(clip['source_out_tick']),self.tps)
        if text_plan and text_plan['independent']:
            source,text_metadata=self.text_host.sample(text_plan,at,text_tick,(canvas['width'],canvas['height']),left_limit=left_limit)
            extra_rotation=self.text_host.rotation(text_plan,tick)
        elif start<=source_time<=end and (source_time!=end or right):
            if clip.get('sequence_id'):
                source=self._sequence(clip['sequence_id'],source_time,rows,depth=depth+1,left_limit=right)
            else:
                source,frame_index=self.sources[clip['asset_id']].sample(source_time,right_edge=right)
        if source is None:
            if clip.get('_source_handle'):
                raise error('SOURCE_HANDLE_COVERAGE','真实源句柄缺少原生帧覆盖；未补帧或替换为透明',clip=path,source_time=str(source_time))
            layer=np.zeros((canvas['height'],canvas['width'],4),np.float32)
            row={'clip':path,'source_time':str(source_time),'empty_native_coverage':True,'author_animation_tick':str(tick)}
            rows.append(row)
            return layer,'normal',tick,row
        if len(rows)>=MAX_LAYERS_PER_FRAME:raise error('BUDGET','同帧片段数超过128')
        effect_metadata=None
        if self.effect_plans[path]:source,effect_metadata=self.effects.apply(source,self.effect_plans[path],tick)
        if text_plan and not text_plan['independent']:
            h,w=source.shape[:2]
            text,text_metadata=self.text_host.sample(text_plan,at,text_tick,(w,h),left_limit=left_limit)
            angle=self.text_host.rotation(text_plan,tick)
            if angle:
                c,s=math.cos(math.radians(angle)),math.sin(math.radians(angle));x,y=(w-1)/2,(h-1)/2
                text,_=self.resample(text,(w,h),[[c,s,x-c*x-s*y],[-s,c,y+s*x-c*y]])
            source,_=self.composite(source,text)
        layer,opacity,inverse,mask_metadata,crop_metadata=self._project(clip,source,canvas,tick,path,extra_rotation=extra_rotation)
        blend=clip.get('blend') or {}
        opacity*=keyframe_value(clip,('blend.opacity','blend_opacity'),float(blend.get('opacity',1)),float(tick))
        if not math.isfinite(opacity) or not 0<=opacity<=1:raise error('GEOMETRY','合并后的图层透明度须为有限0..1数值')
        row={'clip':path,'source_time':str(source_time),'native_frame_index':frame_index,'right_edge':right,
            'author_animation_tick':str(tick),'inverse_affine':inverse,'opacity':opacity,'effects':effect_metadata,'mask':mask_metadata,'crop':crop_metadata}
        if clip.get('_source_handle'):row['source_handle']=copy.deepcopy(clip['_source_handle'])
        if text_metadata is not None:row['text']={**text_metadata,'independent':text_plan['independent'],
            'clock_tick':str(text_tick),'placement':'after-media-effects-before-clip-projection' if not text_plan['independent'] else 'sequence-canvas-before-clip-effects-and-projection',
            'rotation_degrees':self.text_host.rotation(text_plan,tick)}
        rows.append(row)
        return layer,blend.get('mode','normal'),tick,row

    @staticmethod
    def _transition_opacity(layer,row):
        opacity=row.get('opacity',1.)
        if opacity!=1.:
            layer=layer.copy();layer[:,:,3]*=opacity
        return layer

    def _edge_transitions(self,layer,envelopes,tick,row):
        for edge in envelopes:
            d=edge['duration'];duration=edge['authored_duration']
            q=(tick/d) if edge['edge']=='in' else (tick-(duration-d))/d
            if edge['edge']=='in' and q>=1 or edge['edge']=='out' and q<0:continue
            q=max(0.,min(1.,float(q)));empty=np.zeros_like(layer)
            a,b=(empty,layer) if edge['edge']=='in' else (layer,empty)
            layer,metadata=transition_rgba(a,b,q,kind=edge['type'],max_working_bytes=self.max_working_bytes,cancel=self.poll)
            row.setdefault('edge_transitions',[]).append({**metadata,'edge':edge['edge'],'target':'transparent canvas'})
        return layer

    def _sequence(self,sequence_id,at,rows,*,root=False,depth=0,left_limit=False):
        self.poll();sequence=self.sequences[sequence_id];canvas=sequence_canvas(self.project,sequence);w,h=canvas['width'],canvas['height']
        result=np.zeros((h,w,4),dtype=np.float32)
        if root:
            text=str(self.settings['canvas'].get('background','#000000'))
            if text=='transparent':text='#00000000'
            if not re.fullmatch('#[0-9a-fA-F]{6}(?:[0-9a-fA-F]{2})?',text):raise error('BACKGROUND','背景当前要求明确RGB/RGBA十六进制')
            channels=[int(text[i:i+2],16)/255 for i in range(1,len(text),2)]
            if len(channels)==3:channels.append(1.)
            colour,_=convert_rgba(np.array([[channels]],np.float32),self.background_signal,self.working,max_working_bytes=self.max_working_bytes,cancel=self.poll)
            result[:]=colour[0,0]
        duration=Fraction(int(sequence['duration_tick']),self.tps)
        if not ((0<at<=duration) if left_limit else (0<=at<duration)):return result
        for _,track in sorted(enumerate(sequence['tracks']),key=lambda pair:(pair[1].get('order',pair[0]),pair[0])):
            if track.get('muted') or track['kind'] not in ('video','subtitle'):continue
            plan=self.transition_plans[sequence_id+'/'+track['id']]
            at_tick=at*self.tps
            active_pairs=[p for p in plan['pairs'] if ((p['start']<at_tick<=p['end']) if left_limit else (p['start']<=at_tick<p['end']))]
            pair_for={cid:p for p in active_pairs for cid in (p['from'],p['to'])}
            by_id={c['id']:c for c in track['clips']};done=set()
            for clip in track['clips']:
                if clip['id'] in done:continue
                local_tick=at*self.tps-int(clip['timeline_start_tick'])
                if not ((0<local_tick<=clip['duration_tick']) if left_limit else (0<=local_tick<clip['duration_tick'])):continue
                pair=pair_for.get(clip['id'])
                if pair:
                    left,right=by_id[pair['from']],by_id[pair['to']]
                    a,_,ta,ra=self._layer(sequence_id,left,at,canvas,rows,depth,left_limit)
                    a=self._transition_opacity(a,ra)
                    a=self._edge_transitions(a,plan['edges'][left['id']],ta,ra)
                    b,_,tb,rb=self._layer(sequence_id,right,at,canvas,rows,depth,left_limit)
                    b=self._transition_opacity(b,rb)
                    b=self._edge_transitions(b,plan['edges'][right['id']],tb,rb)
                    q=(at_tick-pair['start'])/(pair['end']-pair['start'])
                    progress=math.nextafter(float(q),-math.inf) if left_limit and q>0 else float(q)
                    layer,metadata=transition_rgba(a,b,max(0.,min(1.,progress)),kind=pair['type'],cut_fraction=pair['cut_fraction'],
                        max_working_bytes=self.max_working_bytes,cancel=self.poll)
                    metadata.update(id=pair['id'],author_progress=str(q),real_source_handles=pair['real_source_handles'],
                        start_tick=str(pair['start']),end_tick=str(pair['end']),left_limit=left_limit)
                    ra['paired_transition']=metadata;rb['paired_transition']=metadata
                    mode='normal';opacity=1.;done.update((left['id'],right['id']))
                else:
                    layer,mode,tick,row=self._layer(sequence_id,clip,at,canvas,rows,depth,left_limit)
                    envelopes=plan['edges'][clip['id']]
                    opacity=row.get('opacity',1.)
                    if envelopes:
                        layer=self._transition_opacity(layer,row)
                        layer=self._edge_transitions(layer,envelopes,tick,row);opacity=1.
                result,_=self.composite(result,layer,mode=mode,opacity=opacity)
        return result

    def render_frame(self,index):
        if type(index) is not int or not 0<=index<self.frame_count:raise error('RANGE','输出帧索引越界')
        rows=[];at=Fraction(index,1)/self.fps;result=self._sequence(self.sequence_id,at,rows,root=True)
        return result,{'protocol':PROTOCOL,'frame':index,'author_time':str(at),'layers':rows,'encoded_movie':False,'legacy_render_integrated':False}

    def verify_sources(self):
        for source in self.sources.values():self.poll();source.verify()
        self.effects.verify(self.effect_plans.values())
        self.text_host.verify()
