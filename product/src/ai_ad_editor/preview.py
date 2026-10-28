"""Agent timeline previews from the author graph, with verified local artifacts.

No independent editor model, server, network or playback GUI. Callers hold the
project write lock. A cache hit verifies content; it never denotes inference.
"""
from __future__ import annotations

import copy
from contextlib import ExitStack
from fractions import Fraction
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import time

from .artifact_locks import artifact_entry, verification_entries, verification_scope
from .errors import AppError
from .lut_library import resolve_lut_path
from .media import ffmpeg_path, ffprobe_path, probe_media
from .policy import resolve_local_path
from .project import asset_map, project_file, ledger_file
from .queue_reuse import _objects, _runtime_paths, author_payload, canonical, SELF_CONTAINED_FORMATS
from .render import build_filter_graph, _execution_filter_graph, _execute_audio_stretch, _subtitle_font_path
from .sequence_canvas import sequence_canvas
from .utils import atomic_write_json, ensure_inside, load_json, new_id, run_process

ENGINE = 'agent-timeline-preview-v1'
MAX_ENTRIES = 256
MAX_FILES = 4096
KEY = re.compile(r'^[0-9a-f]{64}$')


def fail(code, message, path=None):
    return AppError(code, message, exit_code=6, path=str(path) if path else None)


def cancel(marker):
    if marker is not None and marker.exists():
        raise AppError('CANCELLED', '时间线预览已取消', exit_code=8, path=str(marker))


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def plain(root, path):
    """Validate the unresolved path before resolve can hide a junction."""
    root, path = root.resolve(), Path(os.path.abspath(path))
    ensure_inside(root, path)
    current = root
    for part in path.relative_to(root).parts:
        current /= part
        if current.is_symlink() or getattr(current, 'is_junction', lambda: False)():
            raise fail('PREVIEW_PATH_INVALID', '预览目录不能包含符号链接或目录联接', current)
    return path


def entry(path, marker=None):
    cancel(marker)
    path = Path(path)
    if path.is_symlink() or getattr(path, 'is_junction', lambda: False)() or not path.is_file():
        raise fail('PREVIEW_DEPENDENCY_MISSING', '预览依赖必须为本地普通文件', path)
    # Empty Python package files are valid runtime inputs.
    if path.stat().st_size == 0:
        return {'path': str(path.resolve()), 'bytes': 0, 'sha256': 'sha256:' + hashlib.sha256(b'').hexdigest()}
    value = artifact_entry(path, 'timeline-preview')
    cancel(marker)
    return {k: value[k] for k in ('path', 'bytes', 'sha256')}


def artifact_digest(path, marker=None):
    """Read output bytes without holding a handle across atomic publication."""
    value = hashlib.sha256()
    size = 0
    with path.open('rb') as stream:
        while chunk := stream.read(1024*1024):
            cancel(marker)
            value.update(chunk)
            size += len(chunk)
    cancel(marker)
    return {'bytes':size, 'sha256':'sha256:'+value.hexdigest()}


def plan(project, sequence, *, start_frame, end_frame, height=360, mode='range', budget_mib=512):
    if mode not in {'frame', 'range'} or any(type(v) is not int for v in (start_frame, end_frame, height, budget_mib)):
        raise fail('PREVIEW_ARGUMENT_INVALID', '帧号、高度和预算必须为整数')
    fps_value = project['settings']['timebase']['display_fps']
    fps = Fraction(fps_value['num'], fps_value['den'])
    duration = Fraction(sequence['duration_tick'], project['settings']['timebase']['ticks_per_second'])
    total = math.ceil(duration * fps)
    if not 0 <= start_frame < end_frame <= total or (mode == 'frame' and end_frame != start_frame + 1):
        raise fail('PREVIEW_RANGE_INVALID', '预览要求有效的半开输出帧区间')
    if not 64 <= height <= 2160 or height % 2 or not 8 <= budget_mib <= 8192:
        raise fail('PREVIEW_ARGUMENT_INVALID', '高度为 64..2160 偶数；预算为 8..8192 MiB')
    canvas = sequence_canvas(project, sequence)
    scale = min(Fraction(1), Fraction(height, canvas['height']))
    width = max(2, int(canvas['width'] * scale) // 2 * 2)
    out_height = max(2, int(canvas['height'] * scale) // 2 * 2)
    first_sample = math.ceil(Fraction(start_frame * 48000, 1) / fps)
    last_sample = min(math.ceil(Fraction(end_frame * 48000, 1) / fps), math.ceil(duration * 48000))
    # Conservative space admission includes master, delivery and staging.
    reference = {}
    if project['settings'].get('pixel_pipeline') is not None:
        from .float_preview import reference_plan
        reference = reference_plan(project, mode)
    bytes_per_pixel = reference.get('reference_bytes_per_pixel', 4)
    estimate = 2 * ((end_frame-start_frame)*width*out_height*bytes_per_pixel + max(0, last_sample-first_sample)*8) + 1024*1024
    if end_frame-start_frame > 3600 or estimate > budget_mib*1024*1024:
        raise fail('PREVIEW_BUDGET', '区间超过 3600 帧或保守工作空间预算；缩短区间或降低高度')
    return {'engine': ENGINE, 'mode': mode, 'sequence_id': sequence['id'], **reference,
            'start_frame': start_frame, 'end_frame': end_frame, 'frames': end_frame-start_frame,
            'fps': dict(fps_value), 'author_start_seconds': str(Fraction(start_frame, 1)/fps),
            'author_end_seconds': str(min(Fraction(end_frame, 1)/fps, duration)),
            'audio_start_sample_48000': first_sample, 'audio_end_sample_48000': last_sample,
            'audio_samples_48000': max(0, last_sample-first_sample),
            'width': width, 'height': out_height, 'budget_bytes': budget_mib*1024*1024,
            'estimated_working_bytes': estimate, 'full_author_graph_before_output_trim': True}


def _paths_from_objects(root, value):
    found = set()
    for obj in _objects(value):
        for key, raw in obj.items():
            if key in {'path', 'uri', 'file', 'lut', 'lut_uri', 'fontfile', 'report', 'report_path', 'executable', 'license_path'} and isinstance(raw, str):
                candidate = resolve_local_path(root, raw, field='preview.dependency')
                if candidate.is_file():
                    found.add(candidate)
    return found


def identity(root, project, sequence, request, marker):
    assets = asset_map(project)
    paths = _paths_from_objects(root, project)
    for obj in _objects(project):
        subtitle = obj.get('subtitle')
        if isinstance(subtitle, dict) and subtitle.get('text') is not None:
            font = _subtitle_font_path(root, subtitle.get('style') or {}, assets)
            if font:
                paths.add(font)
        params = obj.get('parameters', obj)
        if isinstance(params, dict) and params.get('lut_id'):
            value = resolve_lut_path(root, str(params['lut_id']))
            if value:
                paths.add(value[0])
    for path in (ledger_file(root), root/'assets/lut-library.json'):
        if path.is_file():
            paths.add(path)
    runtime = _runtime_paths()
    if project['settings'].get('pixel_pipeline') is not None:
        from .float_preview import runtime_paths
        runtime.update(runtime_paths())
        from .aces_pipeline import dependency_paths
        runtime.update(dependency_paths(project['settings']['pixel_pipeline']))
    runtime.update(p for p in Path(__file__).resolve().parent.iterdir() if p.is_file() and p.suffix in {'.c', '.dll'})
    if len(paths | runtime) > MAX_FILES:
        raise fail('PREVIEW_BUDGET', '预览依赖超过 4096 个文件')
    # Admission budget is operational, not picture identity.
    semantic_request = {k:v for k,v in request.items() if k not in {'budget_bytes', 'estimated_working_bytes'}}
    return {'engine': ENGINE, **author_payload(project, sequence, project['settings']),
            'request': semantic_request, 'dependencies': [entry(p, marker) for p in sorted(paths | runtime)],
            'hsl_backend': os.environ.get('AI_AD_EDITOR_HSL_BACKEND', 'auto')}


def cache_root(root):
    return plain(root, root/'cache/timeline-previews')


def _tree_files(root, directory):
    plain(root, directory)
    files = []
    if not directory.exists():
        return files
    for parent, dirs, names in os.walk(directory, followlinks=False):
        for name in [*dirs, *names]:
            path = plain(root, Path(parent)/name)
            if path.is_file():
                files.append(path)
            if len(files) > MAX_FILES:
                raise fail('PREVIEW_BUDGET', '预览目录文件过多', directory)
    return files


def cache_list(root):
    base = cache_root(root)
    directories = sorted(base.iterdir()) if base.exists() else []
    if len(directories) > MAX_ENTRIES*4:
        raise fail('PREVIEW_BUDGET', '预览目录条目过多', base)
    result = []
    for path in directories:
        plain(root, path)
        if not path.is_dir() or not (KEY.fullmatch(path.name) or path.name.startswith('.tmp-preview_')):
            raise fail('PREVIEW_CACHE_INVALID', '缓存包含未知条目', path)
        files = _tree_files(root, path)
        result.append({'key':path.name, 'path':str(path), 'bytes':sum(p.stat().st_size for p in files),
                       'temporary':path.name.startswith('.tmp-'), 'mtime_ns':path.stat().st_mtime_ns})
    return {'engine':ENGINE, 'entries':result, 'bytes':sum(x['bytes'] for x in result), 'max_entries':MAX_ENTRIES}


def cache_prune(root, *, keep_bytes=0, dry_run=False, protect=None):
    if type(keep_bytes) is not int or keep_bytes < 0:
        raise fail('PREVIEW_ARGUMENT_INVALID', '缓存保留预算必须为非负整数')
    inventory = cache_list(root)
    protected = set([protect] if isinstance(protect,str) else (protect or []))
    # A user may have explicitly linked a preview as a current project asset.
    # Evicting it would remove an authored input, so keep that entry alive.
    for path in _paths_from_objects(root, load_json(project_file(root))):
        if path.is_relative_to(cache_root(root)):
            parts = path.relative_to(cache_root(root)).parts
            if parts:
                protected.add(parts[0])
    remaining = inventory['bytes']
    removed = []
    for item in sorted(inventory['entries'], key=lambda v:(v['mtime_ns'], v['key'])):
        if remaining <= keep_bytes:
            break
        if item['key'] in protected:
            continue
        path = Path(item['path'])
        _tree_files(root, path)  # Validate the entire owned tree before deletion.
        if not dry_run:
            try:
                shutil.rmtree(path)
            except OSError as exc:
                raise fail('PREVIEW_PRUNE_FAILED', '不能完整清理预览缓存', path) from exc
        remaining -= item['bytes']
        removed.append(item['key'])
    return {'engine':ENGINE, 'removed':removed, 'before_bytes':inventory['bytes'],
            'remaining_bytes':remaining, 'protected_reference_keys':sorted(protected), 'dry_run':dry_run}


def _receipt(root, directory):
    path = plain(root, directory/'preview.json')
    try:
        if path.stat().st_size > 8*1024*1024:
            raise ValueError('oversized receipt')
        value = load_json(path)
        payload = {k:v for k,v in value.items() if k != 'key'}
        if value.get('engine') != ENGINE or value.get('key') != directory.name or digest(payload) != directory.name:
            raise ValueError('receipt digest')
        allowed = {'frame.png'} if value['request']['mode'] == 'frame' else {'master.nut', 'preview.mp4'}
        if set(value['files']) != allowed:
            raise ValueError('artifact names')
        if {p.name for p in _tree_files(root, directory)} != allowed | {'preview.json'}:
            raise ValueError('unexpected cache files')
        return value
    except (OSError, KeyError, ValueError, TypeError) as exc:
        raise fail('PREVIEW_CACHE_CORRUPT', '预览缓存收据无效；请显式清理后重建', directory) from exc


def _artifacts(root, directory, receipt, marker):
    for name, expected in receipt['files'].items():
        actual = artifact_digest(plain(root, directory/name), marker)
        if actual != expected:
            raise fail('PREVIEW_CACHE_CORRUPT', '预览产物字节不匹配；请显式清理后重建', directory/name)


def _cacheable(project, actual_formats):
    reasons = []
    for obj in _objects(project):
        if isinstance(obj.get('effects'),list) and any(isinstance(v,str) and v.lower().replace('-','_') in {'noise','film_grain'} for v in obj['effects']):
            reasons.append('stochastic-effect')
        if isinstance(obj.get('subtitle'), dict) and obj['subtitle'].get('asset_uri'):
            reasons.append('external-subtitle-font-fallback')
        if str(obj.get('type', '')).lower().replace('-','_') in {'noise','film_grain'}:
            reasons.append('stochastic-effect')
        for value in obj.values():
            if isinstance(value,str) and ('random(' in value.lower() or value.lower() in {'random','bikeshed','noise','film_grain'}):
                reasons.append('stochastic-expression')
    if any(not set(value.split(',')) <= SELF_CONTAINED_FORMATS for value in actual_formats):
        reasons.append('non-self-contained-media')
    return sorted(set(reasons))


def _copy_result(root, directory, receipt, output, marker):
    if output is None:
        return directory
    output = plain(root, output)
    if output == root or output.exists() or output.is_relative_to(cache_root(root)):
        raise fail('PREVIEW_OUTPUT_EXISTS', '预览导出要求缓存以外的项目内新目录', output)
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = plain(root, output.parent/('.tmp-'+new_id('preview')))
    temporary.mkdir()
    try:
        for name in [*receipt['files'], 'preview.json']:
            cancel(marker)
            shutil.copyfile(directory/name, temporary/name)
        _artifacts(root, temporary, receipt, marker)
        cancel(marker)
        os.replace(temporary, output)
    except OSError as exc:
        raise fail('PREVIEW_EXPORT_FAILED', '预览新目录导出失败', output) from exc
    finally:
        if temporary.exists():
            _tree_files(root, temporary)
            shutil.rmtree(temporary)
    return output


@verification_scope()
def preview_project(root, project, sequence, *, request, output=None, cancel_file=None, dry_run=False):
    with ExitStack() as contexts:
        return _preview_project(root, project, sequence, request=request, output=output,
            cancel_file=cancel_file, dry_run=dry_run, contexts=contexts)


def _preview_project(root, project, sequence, *, request, output, cancel_file, dry_run, contexts):
    started = time.monotonic()
    cancel(cancel_file)
    if project['settings'].get('pixel_pipeline') is not None:
        from .float_preview import reference_plan
        reference = reference_plan(project, request.get('mode'))
        if any(request.get(k) != v for k, v in reference.items()):
            raise fail('PREVIEW_ARGUMENT_INVALID', '浮点预览请求必须使用匹配作者信号及精度的plan结果')
    base = cache_root(root)
    if output is not None:
        output = plain(root, output)
        if output.exists() or output == root or output.is_relative_to(base):
            raise fail('PREVIEW_OUTPUT_EXISTS', '预览导出要求缓存以外的项目内新目录', output)
    before = identity(root, project, sequence, request, cancel_file)
    signature = digest(before)
    inventory = cache_list(root)
    hit = None
    for item in inventory['entries']:
        if item['temporary']:
            continue
        directory = Path(item['path'])
        receipt = _receipt(root, directory)
        if receipt['base_signature'] != signature or not receipt['cacheable']:
            continue
        valid = True
        for expected in receipt['derived_dependencies']:
            try:
                if entry(Path(expected['path']), cancel_file) != expected:
                    valid = False
            except AppError as exc:
                if exc.code == 'CANCELLED':
                    raise
                valid = False
        if valid:
            _artifacts(root, directory, receipt, cancel_file)
            hit = (directory, receipt)
            break
    if dry_run:
        return {'status':'planned', 'request':request, 'base_signature':signature,
                'cache_hit':hit is not None, 'output':str(output) if output else None,
                'would_build_author_graph':hit is None}
    if hit:
        directory, receipt = hit
        result_dir = _copy_result(root, directory, receipt, output, cancel_file)
        return _result(result_dir, receipt, True, started)
    if shutil.disk_usage(root).free < request['estimated_working_bytes']:
        raise fail('PREVIEW_BUDGET', '磁盘剩余空间低于保守工作空间预算', root)
    if len(inventory['entries']) >= MAX_ENTRIES:
        raise fail('PREVIEW_BUDGET', '预览缓存达到 256 条；请先清理')
    allowance = request['budget_bytes']-request['estimated_working_bytes']
    evicted = cache_prune(root, keep_bytes=allowance)
    if evicted['remaining_bytes'] > allowance:
        raise fail('PREVIEW_BUDGET', '当前工程引用的缓存受保护；剩余缓存预算不足')
    base.mkdir(parents=True, exist_ok=True)
    temporary = plain(root, base/('.tmp-'+new_id('preview')))
    temporary.mkdir()
    try:
        effective = copy.deepcopy(project)
        float_preview = None
        if effective['settings'].get('pixel_pipeline') is not None:
            from .float_preview import FloatPreviewContext
            float_preview = contexts.enter_context(FloatPreviewContext(root, effective, sequence, request, cancel_file=cancel_file))
            inputs, graph, metadata, warnings = float_preview.graph()
        else:
            inputs, graph, metadata, warnings = build_filter_graph(root, effective, sequence,
                _persist_video_index=True,_cancel_file=cancel_file)
        from .reverse_cache import materialize as materialize_reverse, verify_materialized as verify_reverse
        reverse_jobs=materialize_reverse(root,metadata,temporary,cancel_file=cancel_file)
        for obj in metadata:
            if job := obj.get('audio_stretch'):
                job['execution'] = _execute_audio_stretch(root, job, temporary, cancel_file=cancel_file)
        from .native_audio_clock import verify_materialized as verify_audio_clocks
        verify_audio_clocks(root,metadata,cancel_file=cancel_file)
        cancel(cancel_file)
        actual_formats = [str(probe_media(resolve_local_path(root, asset['uri'], field='preview.asset')).get('format',''))
                          for asset in project.get('assets',[]) if asset.get('kind') in {'image','audio','video'}]
        reasons = _cacheable(project, actual_formats)
        dependencies = _paths_from_objects(root, metadata)
        for i, value in enumerate(inputs):
            if i and inputs[i-1] == '-i':
                path = Path(value)
                path = path if path.is_absolute() else root/path
                if path.is_file():
                    dependencies.add(resolve_local_path(root, value, field='preview.input'))
        dependencies.update(Path(v['path']) for v in verification_entries())
        dependencies = {p for p in dependencies if not p.is_relative_to(temporary)}
        if len(dependencies) > MAX_FILES:
            raise fail('PREVIEW_BUDGET', '派生依赖超过 4096 个文件')
        derived = [entry(p, cancel_file) for p in sorted(dependencies)]
        s, e = request['start_frame'], request['end_frame']
        # Materialize the same lossless BGRA surface as a full reference first.
        # A combined YUV-to-RGB scale, even at the same dimensions, changes
        # chroma interpolation compared with the complete graph output.
        raster = 'format=bgra'
        canvas = sequence_canvas(project, sequence)
        if (request['width'],request['height']) != (canvas['width'],canvas['height']):
            raster += f",scale={request['width']}:{request['height']}:flags=lanczos,format=bgra"
        if float_preview is not None:
            command, name = float_preview.command(inputs, graph, temporary)
        elif request['mode'] == 'frame':
            graph += f";[vout]trim=start_frame={s}:end_frame={e},setpts=PTS-STARTPTS,{raster}[preview_v]"
            graph += ';[aout]anullsink'
            name = 'frame.png'
            output_args = ['-map','[preview_v]','-frames:v','1','-c:v','png','-pix_fmt','rgba','-update','1',str(temporary/name)]
        else:
            graph += f";[vout]trim=start_frame={s}:end_frame={e},setpts=PTS-STARTPTS,{raster}[preview_v]"
            graph += f";[aout]atrim=start_sample={request['audio_start_sample_48000']}:end_sample={request['audio_end_sample_48000']},asetpts=N/SR/TB[preview_a]"
            name = 'master.nut'
            output_args = ['-map','[preview_v]','-map','[preview_a]','-c:v','ffv1','-level','3','-pix_fmt','bgra','-c:a','pcm_f32le','-f','nut',str(temporary/name)]
        if float_preview is None:
            command = [ffmpeg_path(),'-hide_banner','-y','-loglevel','error',*inputs,'-filter_complex',graph,*output_args]
        command, transport = _execution_filter_graph(root, command, graph, write=True)
        if float_preview is not None:
            float_preview.run(command)
        else:
            result = run_process(command, cwd=root, timeout=3600, cancel_file=cancel_file)
            if result.returncode:
                raise AppError('PREVIEW_RENDER_FAILED', '时间线预览失败', exit_code=6, cause=result.stderr[-6000:])
        names = [name]
        if request['mode'] == 'range':
            delivery_command = [ffmpeg_path(),'-hide_banner','-y','-loglevel','error','-i',str(temporary/name),
                '-c:v','libx264','-preset','ultrafast','-crf','23','-pix_fmt','yuv420p','-c:a','aac','-b:a','128k','-movflags','+faststart',str(temporary/'preview.mp4')]
            if float_preview is not None:
                delivery_command = float_preview.delivery_command(temporary)
            result = run_process(delivery_command, cwd=root, timeout=3600, cancel_file=cancel_file)
            if result.returncode:
                raise AppError('PREVIEW_ENCODE_FAILED', 'MP4 预览编码失败', exit_code=6, cause=result.stderr[-6000:])
            names.append('preview.mp4')
        else:
            delivery_command = None
        for file in names:
            inspected = probe_media(temporary/file)
            if inspected.get('video',{}).get('width') != request['width'] or inspected.get('video',{}).get('height') != request['height']:
                raise fail('PREVIEW_OUTPUT_INVALID', '预览输出尺寸不匹配', temporary/file)
        cancel(cancel_file)
        disk = load_json(project_file(root))
        if author_payload(disk, sequence, disk['settings']) != author_payload(project, sequence, project['settings']):
            raise fail('PREVIEW_INPUT_CHANGED', '预览期间作者工程发生变化')
        if identity(root, project, sequence, request, cancel_file) != before:
            raise fail('PREVIEW_INPUT_CHANGED', '预览期间依赖发生变化')
        for expected in derived:
            if entry(Path(expected['path']), cancel_file) != expected:
                raise fail('PREVIEW_INPUT_CHANGED', '预览期间派生依赖发生变化')
        if reverse_jobs:verify_reverse(root,reverse_jobs,cancel_file=cancel_file)
        from .native_video_index import verify_materialized as verify_native_indexes
        verify_native_indexes(root,metadata,cancel_file=cancel_file)
        verify_audio_clocks(root,metadata,cancel_file=cancel_file)
        if float_preview is not None:
            float_preview.finish_sources()
        clock = _verify_clock(temporary/name, request, cancel_file)
        files = {name:artifact_digest(temporary/name, cancel_file) for name in names}
        receipt = {'engine':ENGINE, 'base_signature':signature, 'identity':before, 'request':request,
                   'cacheable':not reasons, 'cache_bypass_reasons':reasons, 'derived_dependencies':derived,
                   'files':files, 'command':command, 'delivery_command':delivery_command,
                   'filter_graph_transport':transport, 'inputs':metadata, 'warnings':warnings,
                   'verified_clock':clock,
                   'quality_accepted':False, 'model_inference_proven_by_preview':False}
        if float_preview is not None:
            receipt['pixel_pipeline'] = float_preview.metadata
        key = digest(receipt)
        receipt['key'] = key
        if len(canonical(receipt)) > 8*1024*1024:
            raise fail('PREVIEW_BUDGET', '预览收据超过 8 MiB')
        atomic_write_json(temporary/'preview.json', receipt)
        if sum(p.stat().st_size for p in _tree_files(root, temporary)) > request['estimated_working_bytes']:
            raise fail('PREVIEW_BUDGET', '实际预览产物超过预留预算')
        directory = plain(root, base/key)
        cancel(cancel_file)
        if directory.exists():
            existing = _receipt(root, directory)
            _artifacts(root, directory, existing, cancel_file)
        else:
            os.replace(temporary, directory)
        result_dir = _copy_result(root, directory, receipt, output, cancel_file)
        return _result(result_dir, receipt, False, started)
    except OSError as exc:
        raise fail('PREVIEW_IO_FAILED', '预览工作文件操作失败', temporary) from exc
    finally:
        if temporary.exists():
            _tree_files(root, temporary)
            shutil.rmtree(temporary)


def _result(directory, receipt, hit, started):
    name = 'frame.png' if receipt['request']['mode'] == 'frame' else 'preview.mp4'
    return {'status':'succeeded', 'engine':ENGINE, 'cache_hit':hit, 'cache_key':receipt['key'],
            **({'pixel_pipeline':receipt['pixel_pipeline']} if 'pixel_pipeline' in receipt else {}),
            'cacheable':receipt['cacheable'], 'cache_bypass_reasons':receipt['cache_bypass_reasons'],
            'path':str(directory/name), 'manifest':str(directory/'preview.json'),
            'master':str(directory/'master.nut') if name == 'preview.mp4' else None,
            'request':receipt['request'], 'wall_seconds':time.monotonic()-started,
            'verified_clock':receipt['verified_clock'],
            'quality_accepted':False, 'warnings':receipt['warnings']}


def _verify_clock(path, request, marker):
    result = run_process([ffprobe_path(),'-v','error','-show_frames','-show_streams',
        '-show_entries','frame=media_type,best_effort_timestamp,nb_samples:stream=codec_type,time_base',
        '-of','json',str(path)], timeout=600, cancel_file=marker)
    if result.returncode:
        raise fail('PREVIEW_OUTPUT_INVALID', '不能解码核对预览时钟', path)
    payload = json.loads(result.stdout)
    video = [v for v in payload['frames'] if v.get('media_type') == 'video']
    audio = [v for v in payload['frames'] if v.get('media_type') == 'audio']
    if len(video) != request['frames']:
        raise fail('PREVIEW_OUTPUT_INVALID', '实际解码视频帧数不匹配', path)
    samples = sum(int(v.get('nb_samples',0)) for v in audio)
    if request['mode'] == 'range':
        if samples != request['audio_samples_48000']:
            raise fail('PREVIEW_OUTPUT_INVALID', '实际解码 PCM 样本数不匹配', path)
        tb = Fraction(next(v['time_base'] for v in payload['streams'] if v['codec_type'] == 'video'))
        fps = Fraction(request['fps']['num'],request['fps']['den'])
        for i, value in enumerate(video):
            if abs(int(value['best_effort_timestamp'])*tb-Fraction(i,1)/fps) > tb:
                raise fail('PREVIEW_OUTPUT_INVALID', '实际解码视频 PTS 不匹配', path)
        audio_tb = Fraction(next(v['time_base'] for v in payload['streams'] if v['codec_type'] == 'audio')) if audio else None
        offset = 0
        for value in audio:
            if abs(int(value['best_effort_timestamp'])*audio_tb-Fraction(offset,48000)) > audio_tb:
                raise fail('PREVIEW_OUTPUT_INVALID', '实际解码音频 PTS 不匹配', path)
            offset += int(value['nb_samples'])
    return {'decoded_video_frames':len(video),'decoded_pcm_samples_48000':samples,
            'lossless_reference':request['mode']=='range', 'video_pts_rebased':True,
            'audio_pts_rebased':request['mode']=='range'}
