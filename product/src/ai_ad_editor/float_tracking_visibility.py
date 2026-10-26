"""Tracking visibility from actual rendered leaves and transition footprints.

This is source contribution, before higher track occlusion. It runs no model,
does not rewrite observations, and shares every mask/transition pixel kernel.
"""
import math
import numpy as np

from .errors import AppError
from .float_transition_plan import active_pair, edge_progress, pair_progress
from .float_transition_trace import PROTOCOL, trace
from .sequence_canvas import sequence_canvas


def alpha_at(layer, x, y):
    """Bilinear canvas alpha, with transparent samples outside the raster."""
    h,w=layer.shape[:2];ix,iy=math.floor(x),math.floor(y);result=0.
    for xx in (ix,ix+1):
        for yy in (iy,iy+1):
            if 0<=xx<w and 0<=yy<h:
                result+=max(0.,1.-abs(xx-x))*max(0.,1.-abs(yy-y))*float(layer[yy,xx,3])
    if not math.isfinite(result) or not 0<=result<=1:
        raise AppError('FLOAT_TRACKING_ALPHA','实际图层锚点alpha无效',exit_code=2)
    return result


def sample(host, sequence, track, clip, path, at, tick, points, *, left_limit):
    """Follow an alpha-weighted point through own edge then a paired window.

    An unobservable ROI endpoint does not become an invented motion estimate.
    The caller decides whether the requested ROI/rotation requires that probe.
    Density remains a full field between consecutive sampling operations.
    """
    host.poll();canvas=sequence_canvas(host.project,sequence)
    layer,_,_,row=host._layer(sequence['id'],clip,at,canvas,[],0,left_limit)
    plan=host.transition_plans[sequence['id']+'/'+track['id']]
    edges=[(e,edge_progress(e,tick)) for e in plan['edges'][clip['id']]]
    edges=[(e,q) for e,q in edges if q is not None]
    pair=active_pair(plan,clip['id'],at*host.tps,left_limit=left_limit)
    input_alpha=alpha_at(layer,*points[0]);opacity=row.get('opacity',1.)
    metadata=dict(protocol=PROTOCOL,input_canvas_alpha=input_alpha,scalar_opacity=opacity,
        source_masks_and_effect_alpha=True,source_higher_track_occlusion=False,
        natural_identity_inference=False,steps=[],point_footprints=[])
    if not edges and pair is None:
        return dict(opacity=input_alpha*opacity,points=points,geometry_visible=True,metadata=metadata)
    # Identical scalar-alpha Float32 boundary to the actual edge/pair renderer.
    layer=host._transition_opacity(layer,row);density=None;results=None
    for index,(edge,q) in enumerate(edges):
        empty=np.zeros_like(layer);branch=1 if edge['edge']=='in' else 0
        a,b=(empty,layer) if branch else (layer,empty)
        results,density,step=trace(a,b,q,kind=edge['type'],branch=branch,
            points=points if density is None else None,density=density,
            retain=index+1<len(edges) or pair is not None,
            max_working_bytes=host.max_working_bytes,cancel=host.poll)
        metadata['steps'].append({**step,'edge':edge['edge']})
        if index+1<len(edges) or pair is not None:
            layer=host._edge_transitions(layer,[edge],tick,{})
    if pair is not None:
        branch=0 if clip['id']==pair['from'] else 1
        peer_id=pair['to'] if branch==0 else pair['from']
        peer=next(c for c in track['clips'] if c['id']==peer_id)
        other,_,peer_tick,peer_row=host._layer(sequence['id'],peer,at,canvas,[],0,left_limit)
        other=host._transition_opacity(other,peer_row)
        other=host._edge_transitions(other,plan['edges'][peer_id],peer_tick,{})
        a,b=(layer,other) if branch==0 else (other,layer)
        q,progress=pair_progress(pair,at*host.tps,left_limit=left_limit)
        results,_,step=trace(a,b,progress,kind=pair['type'],branch=branch,
            points=points if density is None else None,density=density,cut_fraction=pair['cut_fraction'],
            max_working_bytes=host.max_working_bytes,cancel=host.poll)
        metadata['steps'].append({**step,'pair':pair['id'],'author_progress':str(q),
            'real_source_handles':pair['real_source_handles']})
    metadata['point_footprints']=results
    moved=[(p['x'],p['y']) if p['mass']>0 else None for p in results]
    return dict(opacity=results[0]['coverage'],points=moved,
        geometry_visible=all(p is not None for p in moved),metadata=metadata)
