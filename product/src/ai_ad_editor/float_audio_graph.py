"""Reuse the existing authored audio engine beside a Float32 video producer.

The detached graph retains temporal/nested/audio controls, prunes visual
leaves and consumes its synthetic video output. It is not a second audio
engine or a completed default-renderer integration.
"""
from fractions import Fraction
import copy,hashlib,json,math
from pathlib import Path
from .errors import AppError
from .native_audio_clock import cancel,verify_materialized
from .render import build_filter_graph
from .source_transitions import compile_for_render

PROTOCOL='authored-audio-graph-for-float-video-v1'
VISUAL_FIELDS={'transform','mask','blend','crop','effects','tracking_binding','generator','subtitle','transition_in','transition_out'}

def project_digest(project):
    return 'sha256:'+hashlib.sha256(json.dumps(project,sort_keys=True,ensure_ascii=False,
        separators=(',',':'),allow_nan=False).encode('utf8')).hexdigest()

def prepare(root,project,sequence_id,*,cancel_file=None,persist_clock=True):
    root=Path(root).resolve();marker=Path(cancel_file) if cancel_file is not None else None;cancel(marker)
    detached=copy.deepcopy(project);detached['settings'].pop('adjustments',None);pruned=0;audio_containers=0
    source_plans=[]
    # Resolve handles and paired audio envelopes while the original visual
    # endpoint references still exist. Declarations are compiler input only;
    # the common audio engine receives the already extended private IR.
    compiled={}
    for original in project['sequences']:
        if original.get('source_transitions'):
            cancel(marker)
            _,sequence,plan=compile_for_render(project,original['id'])
            sequence.pop('source_transitions',None)
            compiled[sequence['id']]=sequence;source_plans.append({'sequence_id':sequence['id'],**plan})
    detached['sequences']=[compiled.get(s['id'],s) for s in detached['sequences']]
    for sequence in detached['sequences']:
        kept=[]
        for track in sequence['tracks']:
            if track['kind'] not in ('audio','video','overlay'):continue
            clips=[]
            for clip in track['clips']:
                if track['kind']!='audio' and not clip.get('sequence_id'):pruned+=1;continue
                for field in VISUAL_FIELDS:clip.pop(field,None)
                # The common engine also accepts its documented short aliases.
                clip['keyframes']=[row for row in clip.get('keyframes',[]) if
                    str(row.get('property','')).startswith('audio.') or row.get('property') in {'volume','pan'}]
                clips.append(clip)
            # Nested visual containers still own child sound, windows and buses.
            # Represent these as audio containers only in the detached compiler
            # project so recursive window/freeze builders allow an empty picture.
            # IDs, order, mute and routing references stay on the same tracks.
            if track['kind'] in ('video','overlay'):
                audio_containers+=len(clips);track['kind']='audio'
            track['clips']=clips;kept.append(track)
        sequence['tracks']=kept
    sequence=next((s for s in detached['sequences'] if s['id']==sequence_id),None)
    if sequence is None:raise AppError('FLOAT_AUDIO_SEQUENCE','目标作者序列不存在',exit_code=2)
    inputs,graph,metadata,warnings=build_filter_graph(root,detached,sequence,_allow_audio_only=True,
        _persist_video_index=persist_clock,_cancel_file=marker)
    cancel(marker);ticks=project['settings']['timebase']['ticks_per_second']
    return {'protocol':PROTOCOL,'inputs':inputs,'filter_complex':graph+';[vout]nullsink','output_label':'aout',
        'project_sha256':project_digest(project),'sequence_id':sequence_id,'project_root':str(root),
        'metadata':metadata,'warnings':warnings,'expected_samples_48000':max(1,math.ceil(Fraction(sequence['duration_tick']*48000,ticks))),
        'pruned_visual_leaves':pruned,'nested_visual_containers_compiled_as_audio':audio_containers,
        'source_transition_plans':source_plans,
        'original_project_rewritten':False,'synthetic_video_discarded':True,
        'real_video_decoded_by_adapter':False,'default_float_renderer_integrated':False,'network':False}

def verify(root,plan,*,cancel_file=None):
    if plan.get('protocol')!=PROTOCOL:raise AppError('FLOAT_AUDIO_PLAN','音频适配计划协议不一致',exit_code=2)
    verify_materialized(Path(root).resolve(),plan['metadata'],cancel_file=cancel_file)
