"""Explicit, source-clock-pinned semantic thumbnails for local images/videos."""
from __future__ import annotations

from bisect import bisect_right
from fractions import Fraction
import math
from pathlib import Path
import re
import struct
import time

from .artifact_locks import artifact_entry
from .errors import AppError, argument_error
from .media import ffmpeg_path, ffprobe_path
from .reverse_video_clock import probe_frames
from .semantic_contract import sample_times
from .utils import run_process, sha256_file

PROFILE = 'native-pts-floor-frame-ffmpeg-autorotate-rgb8-max512-v1'


def remaining(deadline: float, marker: Path | None) -> float:
    if marker is not None and marker.exists():
        raise AppError('CANCELLED','语义任务已取消',exit_code=8,path=str(marker))
    value=deadline-time.monotonic()
    if value<=0:
        raise AppError('PROCESS_TIMEOUT','语义任务已超时',exit_code=6,retryable=True)
    return value


def owned(root: Path, path: Path) -> Path:
    # Check lexical ancestry before resolve: reject ancestor junctions as well.
    from .native_video_index import owned as checked
    return checked(root,path)


def png_probe(path: Path) -> dict:
    with path.open('rb') as stream:
        prefix=stream.read(33)
    if len(prefix)!=33 or prefix[:8]!=b'\x89PNG\r\n\x1a\n' or prefix[12:16]!=b'IHDR':
        raise AppError('SEMANTIC_FRAME_INVALID','语义缩略图不是有效 PNG',exit_code=6,path=str(path))
    width,height=struct.unpack('>II',prefix[16:24])
    if not 1<=width<=512 or not 1<=height<=512 or prefix[24]!=8 or prefix[25]!=2:
        raise AppError('SEMANTIC_FRAME_INVALID','语义缩略图须为最大 512px 的 RGB8 PNG',exit_code=6,path=str(path))
    return {'duration_seconds':0,'video':{'codec':'png','width':width,'height':height,'pix_fmt':'rgb24'}}


def choose_video_frames(pts, durations, stream: dict, format_info: dict, *, interval: float, per_asset: int):
    """Choose presentation frames using exact native timestamps, including VFR.

    Sample the actual visible video interval in the container-relative clock.
    Frames present until the next PTS; the last frame needs a known duration.
    Several bins inside a held frame share one embedding and retain every bin.
    """
    try:
        native=Fraction(stream['time_base'])
        raw=format_info.get('start_time','0')
        origin=Fraction('0' if raw in (None,'','N/A') else raw)
        if native<=0 or not pts or len(pts)!=len(durations) or durations[-1]<=0:
            raise ValueError('Invalid native clock or unknown final frame duration')
        if any(b<=a for a,b in zip(pts,pts[1:])):
            raise ValueError('Non-monotone native PTS')
        start=max(Fraction(0),Fraction(pts[0])*native-origin)
        end=Fraction(pts[-1]+durations[-1])*native-origin
        if end<=start:raise ValueError('No visible video interval')
        offsets=sample_times(end-start,interval=interval,per_asset=per_asset)
        selected={}
        for bin_index in range(len(offsets)):
            target=start+bin_index*Fraction(str(interval))
            index=bisect_right(pts,(target+origin)/native)-1
            if index<0:raise ValueError('Sample precedes first actual frame')
            actual=Fraction(pts[index])*native-origin
            row=selected.setdefault(index,dict(native_frame_index=index,native_pts=int(pts[index]),
                    native_time_base=str(native),container_start_seconds=str(origin),
                    sample_seconds=float(actual),sample_seconds_rational=str(actual),requested_seconds=[]))
            row['requested_seconds'].append(float(target))
        return list(selected.values()),dict(profile=PROFILE,interval_seconds=interval,
            window_start_seconds=float(start),window_end_seconds=float(end),
            requested_bins=len(offsets),unique_frames=len(selected),
            frame_selection='frame presenting at each bin; held-frame duplicates retain all requested bins',
            native_frame_count=len(pts),native_time_base=str(native),container_start_seconds=str(origin))
    except (KeyError,ValueError,TypeError,ZeroDivisionError,OverflowError) as exc:
        raise AppError('SEMANTIC_VIDEO_CLOCK_INVALID','原生视频采样时钟无效或末帧时长未知',exit_code=3,cause=str(exc)) from exc


def plan(source: Path, kind: str, *, interval: float, per_asset: int, deadline: float, marker: Path | None):
    remaining(deadline,marker)
    if kind=='image':
        return [dict(native_frame_index=0,native_pts=None,native_time_base=None,
                     sample_seconds=0.,sample_seconds_rational='0',requested_seconds=[0.])],dict(profile=PROFILE,requested_bins=1,unique_frames=1)
    if kind!='video':raise argument_error('语义索引只接受 image/video','asset_id')
    pts,durations,stream,format_info=probe_frames(source,timeout=remaining(deadline,marker),cancel_file=marker)
    return choose_video_frames(pts,durations,stream,format_info,interval=interval,per_asset=per_asset)


def extract(source: Path, kind: str, rows: list[dict], directory: Path, *, deadline: float, marker: Path | None):
    directory.mkdir(parents=True,exist_ok=False)
    indices=[r['native_frame_index'] for r in rows]
    selection='+'.join(f'eq(n\\,{index})' for index in indices)
    graph=f'select={selection},scale=512:512:force_original_aspect_ratio=decrease,format=rgb24,showinfo'
    command=[ffmpeg_path(),'-nostdin','-hide_banner','-v','info','-protocol_whitelist','file,pipe',
             '-copyts','-i',str(source),'-map','0:v:0','-an','-sn','-dn','-vf',graph,
             '-frames:v',str(len(rows)),'-fps_mode','passthrough','-start_number','0','-n',str(directory/'%06d.png')]
    result=run_process(command,timeout=remaining(deadline,marker),cancel_file=marker)
    if result.returncode:
        raise AppError('SEMANTIC_FRAME_EXTRACTION_FAILED','语义帧解码失败',exit_code=6,cause=result.stderr[-4000:])
    files=sorted(directory.glob('*.png'))
    if len(files)!=len(rows) or any(p.name!=f'{i:06}.png' for i,p in enumerate(files)):
        raise AppError('SEMANTIC_FRAME_EXTRACTION_FAILED','语义帧数/名称与原生采样计划不一致',exit_code=6)
    shown=re.findall(r'\bn:\s*\d+\s+pts:\s*(-?\d+)\s+pts_time:',result.stderr)
    if kind=='video' and ([int(p) for p in shown]!=[r['native_pts'] for r in rows]):
        raise AppError('SEMANTIC_FRAME_CLOCK_MISMATCH','实际解码帧 PTS 与原生索引不一致',exit_code=6,
                       diagnostics={'expected':[r['native_pts'] for r in rows],'observed':shown})
    result_rows=[]
    for row,path in zip(rows,files):
        remaining(deadline,marker)
        probe=png_probe(path)
        result_rows.append({**row,'preview_path':str(path),'preview_sha256':'sha256:'+sha256_file(path),
                            'preview_probe':probe})
    return result_rows,dict(command=command,actual_frames=len(files),native_pts_checked=kind=='video',
                            thumbnail_profile=PROFILE,video_color_acceptance='display-oriented RGB8 retrieval evidence; not HDR grading')
