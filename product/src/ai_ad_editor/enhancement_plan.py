"""Portable exact-sample speech-enhancement recipes and project rebinding."""
import copy,math,re
from fractions import Fraction
from .local_enhancement import ENGINE,PROTOCOL,error,options,settings
from .lipsync_plan import digest

def selection(*,start_seconds=0.,end_seconds=None):
    if type(start_seconds)not in (int,float) or not math.isfinite(start_seconds) or start_seconds<0:raise error('RANGE','起点须为有限非负秒数')
    if end_seconds is not None and (type(end_seconds)not in (int,float) or not math.isfinite(end_seconds) or end_seconds<=start_seconds):raise error('RANGE','终点须有限且晚于起点')
    return dict(start_seconds=float(start_seconds),end_seconds=float(end_seconds) if end_seconds is not None else None)

def sample_range(selection,rate,count):
    selection=globals()['selection'](**selection)
    first=round(selection['start_seconds']*rate);last=round(selection['end_seconds']*rate) if selection['end_seconds'] is not None else count
    if not 0<=first<last<=count or last-first>600*rate:raise error('RANGE','所选区间须位于原生音频时钟内且不超过600秒',samples=count)
    return dict(start_sample=first,end_sample=last,samples=last-first,sample_rate=rate)

def recipe(source,adapter,range_,*,channels,selection_,options_):
    value=dict(protocol=PROTOCOL,engine=ENGINE,source_asset_id=source['asset_id'],source_sha256=source['sha256'],
        model_sha256=adapter['model_sha256'],range=copy.deepcopy(range_),channels=channels,
        selection=copy.deepcopy(selection_),options=copy.deepcopy(options_),
        model_settings={k:adapter['settings'][k] for k in ('threads','segment_seconds','overlap')})
    value['sha256']=digest(value);return value

def validate_recipe(value,*,asset,assets=None):
    try:
        required={'protocol','engine','source_asset_id','source_sha256','model_sha256','range','channels','selection','options','model_settings','sha256'}
        if not isinstance(value,dict) or set(value)!=required or value['protocol']!=PROTOCOL or value['engine']!=ENGINE or digest(value)!=value['sha256']:raise ValueError('recipe protocol/digest')
        r=value['range'];rate=r['sample_rate'];channels=value['channels']
        if set(r)!={'start_sample','end_sample','samples','sample_rate'} or any(type(v)is not int for v in r.values()) or not 8000<=rate<=96000 or not 0<=r['start_sample']<r['end_sample'] or r['samples']!=r['end_sample']-r['start_sample'] or r['samples']>600*rate:raise ValueError('native sample clock')
        if type(channels)is not int or channels not in (1,2):raise ValueError('channel count')
        if value['selection']!=selection(**value['selection']) or value['options']!=options(**value['options']):raise ValueError('recipe selection/options')
        if set(value['model_settings'])!={'threads','segment_seconds','overlap'}:raise ValueError('model settings fields')
        settings(**value['model_settings'])
        if round(value['selection']['start_seconds']*rate)!=r['start_sample'] or value['selection']['end_seconds'] is not None and round(value['selection']['end_seconds']*rate)!=r['end_sample']:raise ValueError('selection/sample consistency')
        ident=value['source_asset_id']
        if not isinstance(ident,str) or ident==asset['id'] or any(not isinstance(value[k],str) or not re.fullmatch(r'sha256:[0-9a-f]{64}',value[k]) for k in ('source_sha256','model_sha256')):raise ValueError('source/model reference')
        if assets is not None and (ident not in assets or assets[ident]['kind'] not in {'audio','video'} or assets[ident]['sha256']!=value['source_sha256']):raise ValueError('source identity')
        if asset['kind']!='audio' or asset.get('source',{}).get('derived_from')!=[ident]:raise ValueError('asset/parents')
        stream=next(s for s in asset['probe']['streams'] if s.get('codec_type')=='audio')
        if (int(stream['sample_rate']),int(stream['channels']))!=(rate,channels) or int(stream['duration_ts'])*Fraction(stream['time_base'])*rate!=r['samples'] or stream['codec_name']!='pcm_f32le':raise ValueError('generated PCM clock/format')
    except (ValueError,TypeError,KeyError,StopIteration,ZeroDivisionError,OverflowError) as exc:raise error('RECIPE','对白增强配方、原生时钟或依赖引用无效',cause=str(exc)) from exc
    return value

def rebind_recipe(value,*,mapping,asset,assets):
    validate_recipe(value,asset=asset,assets=assets);result=copy.deepcopy(value)
    result['source_asset_id']=mapping.get(result['source_asset_id'],result['source_asset_id']);result['sha256']=digest(result);return result
