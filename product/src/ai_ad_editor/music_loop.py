"""Explicit sample-clock overlap repair of a local audio loop; no neural backend."""
from __future__ import annotations
import copy
from fractions import Fraction
import hashlib
import math
from pathlib import Path
import re
import shutil
import wave
import numpy as np

from .community_audio import source_asset
from .errors import AppError, argument_error
from .execution_control import checkpoint
from .material_project import append_audio, commit_asset, new_asset_id
from .media import ffmpeg_path, probe_media
from .rights import active_records, load_ledger
from .utils import atomic_write_json, ensure_inside, now_iso, run_process, sha256_file

ENGINE='agent-audio-loop-overlap-cpu-v1'
RATE=48000
MAX_FRAMES=600*RATE
CURVES=('linear','raised-cosine')

def fade_samples(milliseconds, curve):
    if type(milliseconds) not in (int,float) or not math.isfinite(milliseconds) or not 0<milliseconds<=5000:
        raise argument_error('crossfade-ms must be finite, positive and at most5000', 'crossfade_ms')
    count=round(Fraction(str(milliseconds))*RATE/1000)
    if count<2 or curve not in CURVES:
        raise argument_error('Crossfade needs at least2 samples and a supported curve','crossfade_ms/curve')
    return count

def read_recipe(payload):
    fields={'format','source_asset_id','source_sha256','crossfade_ms','curve'}
    if not isinstance(payload,dict) or set(payload)!=fields or payload.get('format')!='agent-audio-loop-v1':
        raise argument_error('Invalid or unknown loop recipe fields','input')
    if not isinstance(payload['source_asset_id'],str) or not isinstance(payload['source_sha256'],str) or not re.fullmatch(r'sha256:[0-9a-f]{64}',payload['source_sha256']):
        raise argument_error('Recipe requires source ID and exact source SHA256','input')
    fade_samples(payload['crossfade_ms'],payload['curve'])
    return dict(asset_id=payload['source_asset_id'],crossfade_ms=payload['crossfade_ms'],
                curve=payload['curve'],expected_sha256=payload['source_sha256'])

def repair_pcm(source, destination, frames, curve, *, block_size=4096):
    """Keep x[M:N-M] verbatim, then blend tail with head; cycle length N-M."""
    if type(frames) is not int or frames<2 or frames>5*RATE or curve not in CURVES or type(block_size) is not int or not 1<=block_size<=65536:
        raise argument_error('Invalid PCM repair parameters','crossfade/curve/block_size')
    digest=hashlib.sha256();square=0.;nonzero=0;peak=0;first=None;last=None;written=0
    with wave.open(str(source),'rb') as reader:
        n=reader.getnframes()
        if (reader.getframerate(),reader.getnchannels(),reader.getsampwidth())!=(RATE,2,2) or not 2*frames<n<=MAX_FRAMES:
            raise argument_error('Repair requires48kHz stereo16bit, <=600s and more than twice the overlap','source')
        raw_head=reader.readframes(frames)
        reader.setpos(n-frames)
        raw_tail=reader.readframes(frames)
        if len(raw_head)!=frames*4 or len(raw_tail)!=frames*4:
            raise AppError('MUSIC_LOOP_TRUNCATED','Truncated loop edge PCM',exit_code=6)
        head=np.frombuffer(raw_head,dtype='<i2').reshape(-1,2).astype(np.float64)
        tail=np.frombuffer(raw_tail,dtype='<i2').reshape(-1,2).astype(np.float64)
        t=np.arange(frames,dtype=np.float64)/(frames-1)
        weight=t if curve=='linear' else .5-.5*np.cos(np.pi*t)
        blend=np.rint(tail*(1-weight[:,None])+head*weight[:,None]).astype('<i2')
        reader.setpos(frames)
        with wave.open(str(destination),'wb') as writer:
            writer.setparams((2,2,RATE,0,'NONE','not compressed'))
            def emit(raw):
                nonlocal square,nonzero,peak,first,last,written
                checkpoint(force=True)
                data=np.frombuffer(raw,dtype='<i2').reshape(-1,2)
                if not len(data):raise AppError('MUSIC_LOOP_TRUNCATED','Truncated loop body',exit_code=6)
                if first is None:first=data[0].astype(np.int32)
                last=data[-1].astype(np.int32)
                normalized=data.astype(np.float64)/32768.
                square+=float(np.sum(normalized*normalized));nonzero+=int(np.count_nonzero(data))
                peak=max(peak,int(np.abs(data.astype(np.int32)).max(initial=0)))
                writer.writeframesraw(raw);digest.update(raw);written+=len(data)
            remaining=n-2*frames
            while remaining:
                count=min(block_size,remaining);raw=reader.readframes(count)
                if len(raw)!=count*4:raise AppError('MUSIC_LOOP_TRUNCATED','Truncated loop body',exit_code=6)
                emit(raw);remaining-=count
            for start in range(0,frames,block_size):emit(blend[start:start+block_size].tobytes())
    if written!=n-frames or not nonzero:
        raise AppError('MUSIC_LOOP_INVALID_PCM','Invalid or silent loop output',exit_code=6)
    return dict(source_frames=n,frames=written,overlap_frames=frames,shortened_frames=frames,
        sample_rate=RATE,channels=2,duration_seconds=written/RATE,PCM_bytes=written*4,
        PCM_sha256=digest.hexdigest(),rms=math.sqrt(square/(written*2)),sample_peak=peak/32768.,
        original_boundary_delta=float(np.max(np.abs(head[0]-tail[-1])))/32768.,
        repaired_boundary_delta=float(np.max(np.abs(first-last)))/32768.,
        overlap_rms=float(np.sqrt(np.mean((blend.astype(np.float64)/32768.)**2))),
        body_source_range=[frames,n-frames],body_PCM_unchanged=True,hidden_normalization=False,
        neural_model=False,model_forwards=0,true_peak_accepted=False,perceptual_seamlessness_accepted=False)

def repair(root, project, *, asset_id, crossfade_ms=100., curve='raised-cosine',
           expected_sha256=None, new_id=None, placement=None, dry_run=False):
    overlap=fade_samples(crossfade_ms,curve)
    source,path,probe=source_asset(root,project,asset_id)
    if expected_sha256 is not None and source['sha256']!=expected_sha256:
        raise AppError('MUSIC_LOOP_SOURCE_CHANGED','Recipe source hash does not match',exit_code=3)
    duration=float(probe['duration_seconds'])
    if not math.isfinite(duration) or duration>600:
        raise argument_error('Loop source must be at most600 seconds','asset_id')
    parent_ref=source.get('rights_ref') or source['id']
    parent=next((r for r in active_records(load_ledger(root)) if r['asset_id']==parent_ref),None)
    if not parent or parent.get('sha256')!=source['sha256']:
        raise AppError('RIGHTS_RECORD_MISSING','Source rights record missing or mismatched',exit_code=7)
    if parent.get('takedown_status')!='clear':
        raise AppError('MUSIC_LOOP_RIGHTS_BLOCKED','Source rights record is not clear',exit_code=7)
    ident=new_asset_id(project,new_id,'asset_loop')
    directory=ensure_inside(root/'assets',root/'assets/music-loops'/('loop_'+hashlib.sha256(ident.encode()).hexdigest()[:24]))
    if directory.exists():raise argument_error('Loop output already exists','new_asset_id')
    placement=placement or dict(apply=False,sequence_id=None,track_id=None,start=0.)
    # Placement can be rejected before decoding; exact output length is known after decode.
    append_audio(root,copy.deepcopy(project),dict(id=ident,kind='audio',probe=dict(duration_seconds=duration)),**placement)
    recipe=dict(format='agent-audio-loop-v1',source_asset_id=asset_id,source_sha256=source['sha256'],
                crossfade_ms=crossfade_ms,curve=curve)
    if dry_run:
        return dict(engine=ENGINE,asset_id=ident,recipe=recipe,overlap_frames=overlap,
            exact_sample_count_requires_decode=True,duration_changes=True,shortened_frames=overlap,
            device=dict(selected='cpu',backend='numpy-overlap'),network='disabled')
    directory.mkdir(parents=True,exist_ok=False)
    try:
        decoded=directory/'decoded.wav';output=directory/'master.wav'
        argv=[ffmpeg_path(),'-hide_banner','-v','error','-nostdin','-n','-i',str(path),
            '-map','0:a:0','-vn','-af',f'aresample={RATE},atrim=end_sample={MAX_FRAMES+1}',
            '-ar',str(RATE),'-ac','2','-c:a','pcm_s16le',str(decoded)]
        result=run_process(argv,cwd=root,timeout=min(3600.,120+duration*12))
        if result.returncode:raise AppError('MUSIC_LOOP_DECODE_FAILED','Loop decode failed',exit_code=6,cause=result.stderr[-2000:])
        decoded_sha=sha256_file(decoded)
        stats=repair_pcm(decoded,output,overlap,curve)
        decoded.unlink();checkpoint(force=True)
        if 'sha256:'+sha256_file(path)!=source['sha256']:
            raise AppError('MUSIC_LOOP_SOURCE_CHANGED','Source changed during repair',exit_code=3)
        atomic_write_json(directory/'recipe.json',recipe)
        evidence=(directory/'SOURCE.json').relative_to(root).as_posix()
        record=dict(engine=ENGINE,recipe=recipe,audio=stats,decoded_WAV_sha256=decoded_sha,
            decoding=dict(sample_rate=RATE,channels=2,sample_format='pcm_s16le',stream='0:a:0'),
            parent_rights=parent,lossless_original_conversion=False,review_required=True)
        atomic_write_json(directory/'SOURCE.json',record)
        digest='sha256:'+sha256_file(output)
        asset=dict(id=ident,kind='audio',uri=output.relative_to(root).as_posix(),sha256=digest,
            probe=probe_media(output),rights_ref=ident,source=dict(source_url='local://'+evidence,
            source_version=ENGINE,retrieved_at=now_iso(),original_name=output.name,derived_from=[parent_ref]))
        verified=parent.get('verification_status')=='verified'
        rights=dict(asset_id=ident,kind='audio',sha256=digest,source_url='local://'+evidence,
            source_version=ENGINE,retrieved_at=now_iso(),creator=parent.get('creator',''),
            license_spdx='LicenseRef-Derived-Audio',license_url=evidence,
            attribution=parent.get('attribution',''),permitted_uses=copy.deepcopy(parent.get('permitted_uses',['internal'])),
            permitted_channels=copy.deepcopy(parent.get('permitted_channels',[])),
            restrictions=copy.deepcopy(parent.get('restrictions',[])),derived_from=[parent_ref],evidence=evidence,
            verification_status='verified' if verified else 'unverified',verified_by=ENGINE if verified else '',
            takedown_status='clear',notes='Overlap shortens the cycle. Parent permissions survive; listening approval is separate.')
        result=commit_asset(root,project,asset,rights,command='music.repair-loop',
            report=dict(engine=ENGINE,recipe=recipe,audio_stats=stats),**placement)
        return dict(result,engine=ENGINE,recipe=recipe,recipe_uri=(directory/'recipe.json').relative_to(root).as_posix(),
                    audio_stats=stats,device=dict(selected='cpu',backend='numpy-overlap'),review_required=True)
    except BaseException:
        if directory.resolve().is_relative_to((root/'assets/music-loops').resolve()):shutil.rmtree(directory)
        raise
