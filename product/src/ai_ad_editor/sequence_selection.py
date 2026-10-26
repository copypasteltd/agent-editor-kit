"""Select one authored output while retaining its shared tracking context.

The Float32 host evaluates the selected layer with its original external blend
deferred to its parent. Audio compiles private, filtered sequence instances;
the saved author graph and its references are never filtered or rewritten.
"""
import copy

from .bindings import native_clock_project
from .errors import AppError
from .utils import ID_RE

PROTOCOL = 'shared-author-selected-output-v1'
MAX_INSTANCES = 4096


def selected(project, clip):
    cid = clip.get('sequence_clip_id')
    if 'sequence_clip_id' not in clip:
        return None
    if not native_clock_project(project):
        raise AppError('SEQUENCE_SELECTION_PIPELINE_REQUIRED', '单片段作者输出需要 float32-native-v1', exit_code=2)
    if not isinstance(cid, str) or not ID_RE.fullmatch(cid) or not clip.get('sequence_id') or clip.get('asset_id'):
        raise AppError('SEQUENCE_SELECTION_INVALID', 'sequence_clip_id 必须引用明确子序列内的一个片段', exit_code=2)
    child = next((s for s in project['sequences'] if s['id'] == clip['sequence_id']), None)
    matches = [(t, c) for t in (child or {}).get('tracks', []) for c in t['clips'] if c['id'] == cid]
    if len(matches) != 1:
        raise AppError('SEQUENCE_SELECTION_MISSING', '找不到唯一的作者输出片段', exit_code=2)
    track, target = matches[0]
    # A paired transition is a two-output operation, not a selectable leaf.
    if any(cid in {d['from_clip_id'], d['to_clip_id'],
                   *(v for pair in d.get('audio_pairs', []) for v in pair.values())}
           for d in child.get('source_transitions', [])):
        raise AppError('SEQUENCE_SELECTION_TRANSITION', '不能拆选真实源转场端点；请选择完整上级容器', exit_code=2)
    if any(isinstance(target.get(k), dict) and target[k].get('type') not in (None, '', 'fade', 'fade_in', 'fade_out')
           for k in ('transition_in', 'transition_out')):
        raise AppError('SEQUENCE_SELECTION_TRANSITION', '不能拆选旧式跨片段转场端点', exit_code=2)
    return child, track, target


def specialize_audio(project):
    """Private instances prevent selected video/audio wrappers duplicating sound."""
    detached = copy.deepcopy(project)
    originals = list(detached['sequences'])
    used = {s['id'] for s in originals}
    instances = {}
    for sequence in originals:
        for track in sequence['tracks']:
            for clip in track['clips']:
                value = selected(project, clip)
                if value is None:
                    continue
                child, lane, target = value
                key = child['id'], target['id']
                if key not in instances:
                    if len(instances) >= MAX_INSTANCES:
                        raise AppError('SEQUENCE_SELECTION_BUDGET', '音频作者输出实例超过4096', exit_code=2)
                    sid = '__selected_audio_' + str(len(instances))
                    while sid in used:
                        sid += '_'
                    used.add(sid)
                    private = copy.deepcopy(child)
                    private['id'] = sid
                    private['tracks'] = [{**copy.deepcopy(lane), 'clips': [copy.deepcopy(target)]}]
                    private.pop('source_transitions', None)
                    private.pop('audio_routing', None)
                    detached['sequences'].append(private)
                    instances[key] = sid
                clip['sequence_id'] = instances[key]
                clip.pop('sequence_clip_id')
    # Instances may select a container that itself selects a prior shared graph.
    # Reuse the original wrapper rewrites rather than leaving a selector in the
    # common FFmpeg compiler or recursively copying a dependency graph.
    replacements = {c['id']: c for s in originals for t in s['tracks'] for c in t['clips']}
    for sequence in detached['sequences'][len(originals):]:
        for track in sequence['tracks']:
            for clip in track['clips']:
                if 'sequence_clip_id' in clip:
                    replacement = replacements[clip['id']]
                    clip['sequence_id'] = replacement['sequence_id']
                    clip.pop('sequence_clip_id')
    return detached
