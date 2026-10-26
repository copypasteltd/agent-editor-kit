"""Native offline human matting with a bounded three-process RGBA pipeline."""
from __future__ import annotations

import contextlib
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
import time
from fractions import Fraction
from pathlib import Path
from typing import Any, Callable

from .errors import AppError, argument_error
from .media import MAX_INPUT_BYTES, ffmpeg_path, probe_media
from .policy import resolve_local_path
from .utils import assert_id, atomic_write_json, now_iso, run_process, sha256_bytes, sha256_file
from .pipeline_diagnostics import Session as DiagnosticSession

MATTING_ENGINE = 'rvm-onnx-cpu-matting-v1'
MATTING_PROTOCOL = 'agent-video-rvm-matting-v1'


def _verify_pipeline_adapter(adapter: dict) -> dict:
    if adapter.get('engine') == MATTING_ENGINE:
        return verify_adapter(adapter)
    if adapter.get('engine') == 'torchscript-lama-local-v1':
        from .local_inpainting import verify_adapter as verify_inpainting
        return verify_inpainting(adapter)
    if adapter.get('engine') == 'diffusers-wan-vace-local-v1':
        from .local_vace import verify_adapter as verify_vace
        return verify_vace(adapter)
    from .local_segmentation import verify_adapter as verify_segmentation
    return verify_segmentation(adapter)


def _prompt_unchanged(plan: dict) -> bool:
    if plan.get('engine') == MATTING_ENGINE:
        return True
    if plan.get('engine') in {'torchscript-lama-local-v1', 'diffusers-wan-vace-local-v1'}:
        from .local_inpainting import mask_unchanged
        return mask_unchanged(plan)
    from .local_segmentation import verify_prompt_source
    return verify_prompt_source(plan)


def settings(*, threads: int = 4, downsample_ratio: float | None = None) -> dict:
    if type(threads) is not int or not 1 <= threads <= 32:
        raise argument_error('RVM threads 必须是 1..32 的整数', 'threads')
    if downsample_ratio is not None and (isinstance(downsample_ratio, bool) or not math.isfinite(downsample_ratio) or not 0 < downsample_ratio <= 1):
        raise argument_error('RVM downsample-ratio 必须为 0..1（不含 0）', 'downsample_ratio')
    return {'threads': threads, 'downsample_ratio': downsample_ratio, 'device': 'cpu', 'provider': 'CPUExecutionProvider', 'precision': 'float32'}


def _entry(path: Path, role: str) -> dict:
    if path.is_symlink() or not path.is_file() or str(path).startswith('\\\\') or path.stat().st_size < 1:
        raise AppError('MATTING_LOCAL_ARTIFACT_INVALID', '抠像依赖必须是非空本地普通文件', exit_code=10, path=str(path))
    return {'path': str(path.resolve()), 'role': role, 'bytes': path.stat().st_size, 'sha256': 'sha256:' + sha256_file(path)}


def manifest_hash(record: dict) -> str:
    keys = ('adapter_id', 'kind', 'engine', 'protocol', 'output_contract', 'model_path', 'model_sha256', 'executable', 'executable_sha256', 'rights_ref', 'capabilities', 'settings', 'artifacts', 'network')
    return 'sha256:' + sha256_bytes(json.dumps({k: record.get(k) for k in keys}, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode('utf-8'))


def prepare_adapter(root: Path, *, adapter_id: str, model_path: str, executable: str, evidence: str,
                    creator: str, license_spdx: str, license_url: str, permitted_uses: list[str], verification_status: str, options: dict) -> tuple[dict, dict]:
    assert_id(adapter_id, 'adapter_id')
    if verification_status not in {'unverified', 'verified', 'restricted'}:
        raise argument_error('未知模型核验状态', 'verification_status')
    model = resolve_local_path(root, model_path, field='model_path')
    python = resolve_local_path(root, executable, field='executable')
    proof = resolve_local_path(root, evidence, field='evidence') if evidence else None
    if model.suffix.lower() != '.onnx' or python.suffix.lower() != '.exe' or proof is None:
        raise argument_error('RVM 需要本地 .onnx、原生 Python .exe 和证据文件', 'model_path/executable/evidence')
    artifacts = [_entry(model, 'model'), _entry(python, 'python'), _entry(proof, 'evidence')]
    artifacts.extend(_entry(Path(__file__).with_name(name), role) for name, role in [('rvm_worker.py', 'worker'), ('matting_frames.py', 'frames'), ('local_matting.py', 'controller'), ('pipeline_diagnostics.py', 'diagnostics'), ('errors.py', 'error_contract'), ('policy.py', 'local_policy')])
    record = {'adapter_id': adapter_id, 'kind': 'video-matting', 'engine': MATTING_ENGINE, 'protocol': MATTING_PROTOCOL, 'output_contract': 'rgba_video_v1',
              'model_path': str(model), 'model_sha256': artifacts[0]['sha256'], 'model_kind': 'file', 'model_file_count': 1,
              'executable': str(python), 'executable_sha256': artifacts[1]['sha256'], 'rights_ref': 'visual_adapter_' + adapter_id,
              'capabilities': ['human_video_alpha', 'native_onnx_cpu'], 'settings': settings(**options), 'artifacts': artifacts,
              'network': 'disabled', 'registered_at': now_iso(), 'verification_status': verification_status}
    record['sha256'] = manifest_hash(record)
    rights = {'asset_id': record['rights_ref'], 'kind': 'model-adapter', 'sha256': record['sha256'], 'source_url': 'local://visual-adapter/' + adapter_id,
              'source_version': MATTING_ENGINE, 'retrieved_at': record['registered_at'], 'creator': creator, 'license_spdx': license_spdx, 'license_url': license_url,
              'attribution': '', 'permitted_uses': list(dict.fromkeys(permitted_uses)), 'permitted_channels': [], 'restrictions': [], 'derived_from': [],
              'evidence': str(proof), 'verification_status': verification_status, 'verified_by': 'ai-ad-editor' if verification_status == 'verified' else '',
              'takedown_status': 'clear', 'notes': 'Explicit local RVM FP32 CPU model; code license does not establish weight or output rights'}
    return record, rights


def verify_adapter(record: dict) -> dict:
    findings = []
    try:
        if record.get('engine') != MATTING_ENGINE or record.get('kind') != 'video-matting' or record.get('protocol') != MATTING_PROTOCOL or record.get('output_contract') != 'rgba_video_v1' or record.get('network') != 'disabled' or record.get('capabilities') != ['human_video_alpha', 'native_onnx_cpu']:
            raise ValueError('MATTING_REGISTRY_CONTRACT_INVALID')
        config = record['settings']
        if settings(threads=config['threads'], downsample_ratio=config['downsample_ratio']) != config:
            raise ValueError('MATTING_SETTINGS_INVALID')
        if manifest_hash(record) != record.get('sha256') or record['rights_ref'] != 'visual_adapter_' + record['adapter_id']:
            raise ValueError('MATTING_MANIFEST_HASH_MISMATCH')
        roles = {item['role']: item for item in record['artifacts']}
        if len(roles) != 9 or len(record['artifacts']) != 9 or set(roles) != {'model', 'python', 'evidence', 'worker', 'frames', 'controller', 'diagnostics', 'error_contract', 'local_policy'}:
            raise ValueError('MATTING_MANIFEST_INCOMPLETE')
        for role, expected in [('model', record['model_path']), ('python', record['executable']), ('worker', Path(__file__).with_name('rvm_worker.py')), ('frames', Path(__file__).with_name('matting_frames.py')), ('controller', Path(__file__)), ('diagnostics', Path(__file__).with_name('pipeline_diagnostics.py')), ('error_contract', Path(__file__).with_name('errors.py')), ('local_policy', Path(__file__).with_name('policy.py'))]:
            if Path(roles[role]['path']).resolve() != Path(expected).resolve():
                raise ValueError('MATTING_MANIFEST_PATH_MISMATCH')
        if roles['model']['sha256'] != record['model_sha256'] or roles['python']['sha256'] != record['executable_sha256']:
            raise ValueError('MATTING_ARTIFACT_HASH_MISMATCH')
        if any(_entry(Path(item['path']), item['role']) != item for item in record['artifacts']):
            raise ValueError('MATTING_ARTIFACT_HASH_MISMATCH')
    except (AppError, OSError, ValueError, KeyError, TypeError) as exc:
        findings.append({'code': getattr(exc, 'code', 'MATTING_REGISTRY_INVALID'), 'message': str(exc)})
    return {'adapter_id': record.get('adapter_id'), 'engine': record.get('engine'), 'network': 'disabled', 'ok': not findings, 'findings': findings}


def prepare_plan(source: Path, adapter: dict, *, start_seconds: float = 0, end_seconds: float | None = None,
                 fps: str | None = None, max_edge: int = 0, max_frames: int = 18000, preserve_audio: bool = True) -> dict:
    if not _verify_pipeline_adapter(adapter)['ok']:
        raise AppError('MODEL_ADAPTER_HASH_INVALID', 'RVM 登记完整性检查失败', exit_code=10)
    probe = probe_media(source)
    stream = next((s for s in probe.get('streams', []) if s.get('codec_type') == 'video' and not s.get('disposition', {}).get('attached_pic')), {})
    try:
        width, height = int(stream['width']), int(stream['height'])
        rate = Fraction(fps if fps is not None else (stream.get('avg_frame_rate') or stream.get('r_frame_rate') or '0'))
        duration = float(stream.get('duration') or probe['duration_seconds'])
        start = float(start_seconds)
        end = duration if end_seconds is None else float(end_seconds)
        rotation = float(next((s['rotation'] for s in stream.get('side_data_list', []) if 'rotation' in s), stream.get('tags', {}).get('rotate', 0)))
        sar_text = stream.get('sample_aspect_ratio')
        sar = Fraction(sar_text.replace(':', '/')) if sar_text not in (None, 'N/A', '0:1') else Fraction(1)
        if not all(math.isfinite(v) for v in (duration, start, end, rotation)) or not 0 < rate <= 240 or not 0 < duration <= 7200 or not 0 <= start < end <= duration + .001 or min(width, height) < 1 or max(width, height) > 8192 or sar <= 0 or rotation % 90:
            raise ValueError('unsupported range or raster')
        if type(max_edge) is not int or not 0 <= max_edge <= 8192 or type(max_frames) is not int or not 1 <= max_frames <= 1_728_000:
            raise ValueError('invalid frame or edge budget')
        display_w, display_h = width * float(sar), float(height)
        if abs(rotation) % 180 == 90:
            display_w, display_h = display_h, display_w
        scale = min(1., max_edge / max(display_w, display_h)) if max_edge else 1.
        dw, dh = max(1, round(display_w * scale)), max(1, round(display_h * scale))
        frames = max(1, math.ceil((end - start) * float(rate) - 1e-8))
        if frames > max_frames or dw * dh > 16_777_216 or max(dw, dh) > 8192:
            raise AppError('MATTING_FRAME_BUDGET_EXCEEDED', '抠像帧数或画幅超预算；显式调整范围、max-frames 或 max-edge', exit_code=2)
        if stream.get('color_transfer') in {'smpte2084', 'arib-std-b67'}:
            raise AppError('MATTING_HDR_UNSUPPORTED', 'RVM 当前按 SDR RGB 推理；HDR 源须先显式 tone map', exit_code=4)
    except (ValueError, TypeError, KeyError, ZeroDivisionError, OverflowError) as exc:
        raise argument_error('抠像需要有效视频、已知时长/帧率、有效范围、90 度倍数旋转和合法资源预算', 'source/range/fps') from exc
    audio = next((s for s in probe.get('streams', []) if s.get('codec_type') == 'audio'), None)
    audio_offset = float(audio.get('start_time') or 0) - float(stream.get('start_time') or 0) if audio else 0.
    if not math.isfinite(audio_offset):
        raise argument_error('音视频起点不是有限时间戳', 'source')
    ratio = adapter['settings'].get('downsample_ratio') or min(1., 512 / max(dw, dh))
    if adapter['engine'] == MATTING_ENGINE and min(dw, dh) * ratio < 16:
        raise argument_error('模型内部短边须至少 16 像素；调整 downsample-ratio 或输入尺寸', 'downsample_ratio')
    warnings = [{'code': 'MATTING_MODEL_REVIEW_REQUIRED', 'message': '人物模型需复核头发、运动、遮挡、镜头切换和许可；未证明通用物体或广告广泛质量'},
                {'code': 'MATTING_CFR_CLOCK', 'message': '输出使用显式 CFR，尾部不足一帧按末帧补齐，源时钟与输出时长见报告'}]
    if adapter['engine'] != MATTING_ENGINE:
        warnings[0] = {'code': 'SEGMENTATION_MODEL_REVIEW_REQUIRED', 'message': '对象分割须复核提示、遮挡、边缘、商品与镜头切换；概率不等于物理 alpha'}
    if adapter['engine'] == 'torchscript-lama-local-v1':
        warnings[0] = {'code': 'INPAINT_MODEL_REVIEW_REQUIRED', 'message': '逐帧 LaMa 补全须复核纹理、物体残留、闪烁与许可；没有跨帧联合修复或生成填充保证'}
    if adapter['engine'] == 'diffusers-wan-vace-local-v1':
        warnings[0] = {'code': 'VACE_MODEL_REVIEW_REQUIRED', 'message': '联合窗口生成须复核提示词、纹理、物体/身份、遮挡、窗口接缝与许可；未验收全视频时序或完整剪映效果'}
    return {'engine': adapter['engine'], 'protocol': adapter['protocol'], 'network': 'disabled',
            'source': {'path': str(source.resolve()), 'sha256': 'sha256:' + sha256_file(source)}, 'input_probe': probe,
            'range': {'start_seconds': start, 'end_seconds': end},
            'video': {'width': dw, 'height': dh, 'fps': str(rate), 'frames': frames, 'duration_seconds': frames / float(rate),
                      'source_stream_index': int(stream.get('index', 0)),
                      'downsample_ratio': ratio, 'source_width': width, 'source_height': height, 'source_sar': str(sar), 'source_rotation': rotation,
                      'clock': 'ffmpeg-fps-resampled-source-seconds', 'alpha_mode': 'straight', 'codec': 'qtrle', 'pix_fmt': 'argb'},
            'audio': {'preserve': bool(audio and preserve_audio), 'source_offset_seconds': audio_offset, 'codec': 'pcm_s24le' if audio and preserve_audio else None},
            'warnings': warnings}


def request_hash(request: dict) -> str:
    return 'sha256:' + sha256_bytes(json.dumps({k: v for k, v in request.items() if k != 'request_sha256'}, ensure_ascii=True, sort_keys=True, separators=(',', ':')).encode('utf-8'))


@contextlib.contextmanager
def _windows_job():
    """All pipeline children die when the parent handle closes, including crashes."""
    import ctypes
    from ctypes import wintypes as w
    if os.name != 'nt':
        raise AppError('MATTING_NATIVE_WINDOWS_REQUIRED', 'RVM 管道要求原生 Windows', exit_code=10)
    class Basic(ctypes.Structure):
        _fields_ = [('process_time', ctypes.c_int64), ('job_time', ctypes.c_int64), ('flags', w.DWORD), ('min_ws', ctypes.c_size_t), ('max_ws', ctypes.c_size_t), ('active', w.DWORD), ('affinity', ctypes.c_size_t), ('priority', w.DWORD), ('scheduling', w.DWORD)]
    class IO(ctypes.Structure):
        _fields_ = [(name, ctypes.c_uint64) for name in ('read_ops', 'write_ops', 'other_ops', 'read_bytes', 'write_bytes', 'other_bytes')]
    class Extended(ctypes.Structure):
        _fields_ = [('basic', Basic), ('io', IO), ('process_memory', ctypes.c_size_t), ('job_memory', ctypes.c_size_t), ('peak_process', ctypes.c_size_t), ('peak_job', ctypes.c_size_t)]
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.CreateJobObjectW.argtypes, kernel.CreateJobObjectW.restype = [ctypes.c_void_p, w.LPCWSTR], w.HANDLE
    kernel.SetInformationJobObject.argtypes, kernel.SetInformationJobObject.restype = [w.HANDLE, ctypes.c_int, ctypes.c_void_p, w.DWORD], w.BOOL
    kernel.AssignProcessToJobObject.argtypes, kernel.AssignProcessToJobObject.restype = [w.HANDLE, w.HANDLE], w.BOOL
    kernel.CloseHandle.argtypes, kernel.CloseHandle.restype = [w.HANDLE], w.BOOL
    handle = kernel.CreateJobObjectW(None, None)
    if not handle:
        raise ctypes.WinError(ctypes.get_last_error())
    try:
        info = Extended()
        info.basic.flags = 0x2000
        if not kernel.SetInformationJobObject(handle, 9, ctypes.byref(info), ctypes.sizeof(info)):
            raise ctypes.WinError(ctypes.get_last_error())
        def assign(process):
            if not kernel.AssignProcessToJobObject(handle, int(process._handle)):
                # Very short failing children may already have exited.
                if process.poll() is None:
                    raise ctypes.WinError(ctypes.get_last_error())
        yield assign
    finally:
        kernel.CloseHandle(handle)


def _worker_command(adapter: dict, request_path: Path) -> list[str]:
    name = 'rvm_worker.py' if adapter['engine'] == MATTING_ENGINE else 'lama_worker.py' if adapter['engine'] == 'torchscript-lama-local-v1' else 'vace_worker.py' if adapter['engine'] == 'diffusers-wan-vace-local-v1' else 'sam2_worker.py'
    return [adapter['executable'], '-I', '-B', '-X', 'utf8', str(Path(__file__).with_name(name)), str(request_path)]


def validate_response(response: dict, request: dict) -> None:
    joint = request['engine'] == 'diffusers-wan-vace-local-v1'
    inpainting = request['engine'] in {'torchscript-lama-local-v1', 'diffusers-wan-vace-local-v1'}
    segmentation = request['engine'] == 'transformers-sam2-video-local-v1'
    providers = ['torch-' + request['adapter']['settings']['device']] if segmentation or inpainting else ['CPUExecutionProvider']
    expected = {'status': 'succeeded', 'protocol': request['protocol'], 'engine': request['engine'], 'network': 'disabled', 'blocked_network_events': [],
                'request_sha256': request['request_sha256'], 'adapter_sha256': request['adapter']['sha256'], 'source_sha256': request['source']['sha256'], 'providers': providers}
    if 'outpainting' in request:
        expected['outpainting'] = request['outpainting']
    if segmentation:
        expected.update(prompt_sha256=request['prompt_plan']['sha256'], object_ids=request['prompt_plan']['object_ids'], mask_mode=request['prompt_plan']['mask_mode'])
    if inpainting:
        expected.update(mask_sha256=request['mask']['sha256'], mask_plan_sha256=request['mask']['plan_sha256'], inpainting=request['inpainting'])
    if joint:
        expected['generation'] = request['generation']
    if any(response.get(key) != value for key, value in expected.items()):
        raise AppError('MATTING_WORKER_INTEGRITY_INVALID', '抠像 worker 协议或输入/模型/网络/设备不符', exit_code=6)
    info, metrics = request['video'], response.get('metrics')
    state_reset = 'per-joint-window-and-scene' if joint else 'per-frame' if inpainting else 'per-job-and-explicit-frames' if segmentation else 'per-job'
    if not isinstance(metrics, dict) or any(type(metrics.get(k)) is not int or metrics[k] != info[k] for k in ('frames', 'width', 'height')) or metrics.get('state_updates') != info['frames'] or metrics.get('rgba_bytes') != info['frames'] * info['width'] * info['height'] * 4 or metrics.get('alpha_mode') != 'straight' or metrics.get('input_alpha') != ('preserve' if inpainting else 'multiply') or metrics.get('state_reset') != state_reset:
        raise AppError('MATTING_WORKER_OUTPUT_INVALID', '抠像帧数、画幅、字节数或状态传递无效', exit_code=6)
    digest = metrics.get('rgba_sha256', '')
    if not isinstance(digest, str) or len(digest) != 71 or not digest.startswith('sha256:') or any(c not in '0123456789abcdef' for c in digest[7:]):
        raise AppError('MATTING_WORKER_OUTPUT_INVALID', '抠像原始 RGBA 摘要无效', exit_code=6)
    pixels = info['width'] * info['height'] * info['frames']
    try:
        budget = request['adapter']['settings']['state_budget_bytes'] if segmentation or inpainting else 256 * 1024 * 1024
        if type(metrics['state_updates']) is not int or type(metrics['state_peak_bytes']) is not int or not 0 < metrics['state_peak_bytes'] <= budget:
            raise ValueError('state budget')
        if any(type(metrics[k]) is not int or not 0 <= metrics[k] <= pixels for k in ('transparent_pixels', 'opaque_pixels', 'soft_alpha_pixels')) or sum(metrics[k] for k in ('transparent_pixels', 'opaque_pixels', 'soft_alpha_pixels')) != pixels:
            raise ValueError('alpha counts')
        if any(type(metrics[k]) is not int or not 0 <= metrics[k] <= 255 for k in ('alpha_min', 'alpha_max')) or metrics['alpha_min'] > metrics['alpha_max'] or not math.isfinite(metrics['alpha_mean']) or not 0 <= metrics['alpha_mean'] <= 1:
            raise ValueError('alpha range')
        if segmentation and (type(metrics.get('prompt_events')) is not int or metrics['prompt_events'] != len(request['prompt_plan']['frames']) or type(metrics.get('explicit_resets')) is not int or metrics['explicit_resets'] != sum(e['reset'] for e in request['prompt_plan']['frames'])):
            raise ValueError('prompt event counters')
        if inpainting:
            for name in ('model_calls', 'empty_mask_frames'):
                if type(metrics.get(name)) is not int or not 0 <= metrics[name] <= info['frames']:
                    raise ValueError('inpainting frame counters')
            if not joint and (type(metrics.get('resized_model_frames')) is not int or not 0 <= metrics['resized_model_frames'] <= metrics['model_calls'] or metrics['model_calls'] + metrics['empty_mask_frames'] != info['frames']):
                raise ValueError('framewise inpainting counters')
            if type(metrics.get('mask_pixels')) is not int or not 0 <= metrics['mask_pixels'] <= pixels or metrics.get('outside_mask_changed_pixels') != 0:
                raise ValueError('inpainting mask counters')
            from .repair_blend import validate_blend_report, joint_blend_overhead
            validate_blend_report(metrics, request['inpainting'], width=info['width'], height=info['height'], frames=info['frames'])
            base_peak = metrics.get('base_state_peak_bytes')
            blend_peak = metrics['blend']['owned_array_peak_bytes']
            if type(base_peak) is not int or not max(base_peak, blend_peak) <= metrics['state_peak_bytes'] <= base_peak + blend_peak or base_peak < info['width']*info['height']*21:
                raise ValueError('repair blend combined owned-array budget')
            if not joint:
                w,h=info['width'],info['height'];edge=request['inpainting']['model_max_edge']
                mw=max(64,min((w+7)//8*8,(edge+7)//8*8));mh=max(64,min((h+7)//8*8,(edge+7)//8*8))
                maximum=w*h*(125 if request['inpainting']['blend_mode']=='harmonic' else 53)+mw*mh*28+(w+h)*8
                if base_peak>maximum:raise ValueError('framewise repair base array estimate')
            if joint:
                from .local_vace import window_plan, buffer_budget, plan_digest
                conditioning='masked-rgb-127-and-previous-generated-context' if request['generation'].get('temporal_context')=='previous' else 'masked-rgb-127-before-and-after-resize'
                if metrics.get('conditioning') != conditioning:
                    raise ValueError('joint inpainting conditioning mismatch')
                verification = response.get('artifact_verification', {})
                artifacts = {a['path']: a['bytes'] for a in request['adapter']['artifacts']}
                if not isinstance(verification, dict) or verification.get('mode') != 'windows-read-lock-command-scope' or verification.get('write_and_delete_sharing') is not False or verification.get('persists_across_commands') is not False:
                    raise ValueError('joint artifact verification scope')
                if type(verification.get('files_hashed')) is not int or verification['files_hashed'] != len(artifacts) or type(verification.get('bytes_hashed')) is not int or verification['bytes_hashed'] != sum(artifacts.values()) or type(verification.get('digest_reuses_while_locked')) is not int or verification['digest_reuses_while_locked'] < len(request['adapter']['artifacts']):
                    raise ValueError('joint artifact verification counters')
                windows = window_plan(info['frames'], request['generation'])
                if request['windows'] != windows or type(metrics.get('window_count')) is not int or metrics.get('window_count') != len(windows) or metrics.get('window_plan_sha256') != plan_digest(windows):
                    raise ValueError('joint window plan mismatch')
                bounds = {'empty_windows':len(windows), 'padded_frames':3*len(windows), 'overlap_frames_blended':info['frames'],
                          'resized_model_frames':sum(w['end']-w['start'] for w in windows)}
                if any(type(metrics.get(k)) is not int or not 0 <= metrics[k] <= maximum for k,maximum in bounds.items()) or metrics['model_calls'] + metrics['empty_windows'] != len(windows):
                    raise ValueError('joint window counters')
                expected_base=buffer_budget(info['width'],info['height'],request['generation'],request['inpainting']['model_max_edge'])+joint_blend_overhead(info['width'],info['height'],request['inpainting'])
                if base_peak!=expected_base or metrics['state_peak_bytes']!=expected_base+blend_peak:
                    raise ValueError('joint window buffer estimate')
                if (metrics['mask_pixels']==0)!=(metrics['model_calls']==0) or (metrics['empty_mask_frames']==info['frames'])!=(metrics['mask_pixels']==0) or response.get('model_loaded') is not (metrics['model_calls']>0):
                    raise ValueError('joint model/empty-mask execution mismatch')
                if metrics['model_calls']:
                    execution=response.get('model_execution',{})
                    if not isinstance(execution,dict) or execution.get('prompt_truncated') is not False or execution.get('prompt_extension') is not False or execution.get('text_encoder_released_before_generation') is not True or execution.get('transformer_precision')!='bfloat16-with-declared-float32-stability-modules' or execution.get('vae_precision')!='float32':
                        raise ValueError('joint model/prompt execution contract')
                    if type(execution.get('flow_shift')) not in {float,int} or execution['flow_shift']!=request['generation']['flow_shift'] or type(execution.get('model_input_scale')) is not int or execution['model_input_scale']!=request['generation']['model_input_scale']:
                        raise ValueError('joint sampling configuration mismatch')
                    from .vace_model import validate_weight_reads
                    validate_weight_reads(execution.get('local_weight_reads'))
                    from .cuda_admission import validate_execution
                    if execution.get('text_offload_hooks_removed_before_generation') is not True:
                        raise ValueError('text offload hooks were not released')
                    validate_execution(execution,text_gpu_budget_mib=request['adapter']['settings']['text_gpu_budget_mib'],model_calls=metrics['model_calls'])
                    shapes=execution.get('window_input_shapes')
                    factor=request['generation']['model_input_scale']
                    edge=max(64,(request['inpainting']['model_max_edge']+15)//16*16)*factor
                    if not isinstance(shapes,list) or len(shapes)!=metrics['model_calls'] or any(not isinstance(shape,list) or len(shape)!=3 or any(type(v) is not int for v in shape) or not 1<=shape[0]<=request['generation']['window_frames'] or shape[0]%4!=1 or any(not 64*factor<=v<=edge or v%(16*factor) for v in shape[1:]) for shape in shapes):
                        raise ValueError('joint model input shape invalid')
                    if max(shape[0]*shape[1]*shape[2] for shape in shapes)!=metrics['model_peak_pixels']:
                        raise ValueError('joint model input raster mismatch')
                    tokens=execution.get('prompt_token_counts',{});seconds=execution.get('window_seconds',[])
                    if not isinstance(tokens,dict) or set(tokens)!={'prompt','negative_prompt'} or any(type(v) is not int or not 1<=v<=request['generation']['prompt_max_tokens'] for v in tokens.values()) or not isinstance(seconds,list) or len(seconds)!=metrics['model_calls'] or any(type(v) not in {int,float} or not math.isfinite(v) or v<0 for v in seconds):
                        raise ValueError('joint prompt/window execution metrics')
                from .vace_context import validate_context_report
                validate_context_report(metrics,response.get('model_execution',{}),request['generation'],
                    width=info['width'],height=info['height'],windows=windows)
            if metrics.get('input_alpha_sha256') != metrics.get('output_alpha_sha256'):
                raise ValueError('source alpha changed')
            for name in ('input_alpha_sha256', 'output_alpha_sha256', 'source_rgba_sha256', 'decoded_mask_rgba_sha256'):
                value = metrics.get(name, '')
                if not isinstance(value, str) or len(value) != 71 or not value.startswith('sha256:') or any(c not in '0123456789abcdef' for c in value[7:]):
                    raise ValueError('inpainting input digests')
            raster_bound = (((request['inpainting']['model_max_edge']+15)//16*16)**2 * request['generation']['window_frames'] * request['generation']['model_input_scale']**2) if joint else ((request['inpainting']['model_max_edge'] + 7) // 8 * 8)**2
            if type(metrics.get('model_peak_pixels')) is not int or not 0 <= metrics['model_peak_pixels'] <= raster_bound:
                raise ValueError('inpainting model raster budget')
    except (KeyError, TypeError, ValueError) as exc:
        raise AppError('MATTING_WORKER_OUTPUT_INVALID', '抠像循环状态或 alpha 统计不合法', exit_code=6) from exc


@contextlib.contextmanager
def _pipeline_workspace(cache: Path, on_failure=None):
    cache = cache.resolve()
    work = Path(tempfile.mkdtemp(prefix='rgba-', dir=cache)).resolve()
    primary = None
    try:
        yield work
    except BaseException as exc:
        primary = exc
        if on_failure:
            try:
                on_failure(work, exc)
            except Exception:
                exc.diagnostics = {'status': 'unavailable', 'warnings': [{'code': 'DIAGNOSTIC_CALLBACK_FAILED'}]}
        raise
    finally:
        # Windows scanners/readers can briefly retain a file after a child exits.
        # Retry sharing/access races within a fixed budget; never hide leftovers.
        try:
            for attempt in range(6):
                if work.resolve() != work or work.parent != cache or work.is_symlink() or getattr(work, 'is_junction', lambda: False)():
                    raise AppError('MATTING_CACHE_CLEANUP_FAILED', '临时目录边界变化，拒绝递归清理', exit_code=6, path=str(work))
                try:
                    shutil.rmtree(work)
                    break
                except FileNotFoundError:
                    break
                except OSError as exc:
                    if getattr(exc, 'winerror', None) not in {5, 32, 33, 145} or attempt == 5:
                        raise AppError('MATTING_CACHE_CLEANUP_FAILED', '临时目录未清理，保留路径供恢复', exit_code=6, path=str(work), cause=str(exc)) from exc
                    time.sleep(.05 * 2**attempt)
        except AppError as cleanup:
            if primary is None:
                if on_failure:
                    on_failure(work, cleanup)
                raise
            reference = getattr(primary, 'diagnostics', None) or {'status': 'unavailable', 'warnings': []}
            reference.setdefault('warnings', []).append({'code': cleanup.code, 'cache_kind': cache.name, 'cache_subdirectory': work.name})
            primary.diagnostics = reference


def matte_native(root: Path, output: Path, *, adapter: dict, plan: dict, timeout: float = 3600,
                 cancel_file: Path | None = None, progress: Callable | None = None, operation_id: str | None = None, workspace=None) -> dict:
    if not math.isfinite(timeout) or not 0 < timeout <= 604800:
        raise argument_error('timeout-seconds 必须为 0..604800（不含 0）', 'timeout')
    if output.exists() or output.suffix.lower() != '.mov':
        raise argument_error('抠像输出必须为尚不存在的 .mov', 'output')
    if cancel_file and cancel_file.exists():
        raise AppError('CANCELLED', '抠像在启动前取消', exit_code=8)
    source = Path(plan['source']['path'])
    if plan.get('engine') != adapter.get('engine') or plan.get('protocol') != adapter.get('protocol') or not _verify_pipeline_adapter(adapter)['ok'] or not _prompt_unchanged(plan) or 'sha256:' + sha256_file(source) != plan['source']['sha256']:
        raise AppError('MATTING_INTEGRITY_FAILED', '源或模型在计划之后变化', exit_code=10)
    from .runtime import configure_local_runtime
    runtime = configure_local_runtime()['root']
    cache = root / 'cache' / ('inpainting' if adapter['engine'] in {'torchscript-lama-local-v1', 'diffusers-wan-vace-local-v1'} else 'matting')
    if workspace is not None:
        from .job_workspaces import Workspace
        if not isinstance(workspace, Workspace) or workspace.root != Path(root).resolve() or workspace.record['kind'] != 'video-generation':
            raise argument_error('生成管道须使用同工程持有租约的受管工作区', 'workspace')
        cache = workspace.path / 'pipeline'
    cache.mkdir(parents=True, exist_ok=True)
    output.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg = Path(ffmpeg_path()).resolve()
    ffmpeg_hash = 'sha256:' + sha256_file(ffmpeg)
    started = time.monotonic()
    published = False
    diagnostic = DiagnosticSession(root, plan, adapter, operation_id)
    try:
        with _pipeline_workspace(cache, on_failure=diagnostic.capture) as temporary:
            work = Path(temporary)
            staged = work / 'foreground.mov'
            request = {**plan, 'adapter': adapter, 'runtime_root': runtime, 'response': str(work / 'response.json'), 'progress': str(work / 'progress.json'),
                       'ffmpeg': {'path': str(ffmpeg), 'sha256': ffmpeg_hash}}
            request['request_sha256'] = request_hash(request)
            request_path = work / 'request.json'
            atomic_write_json(request_path, request)
            diagnostic.prepare(work, request)
            info = plan['video']
            start, end = plan['range']['start_seconds'], plan['range']['end_seconds']
            duration = info['duration_seconds']
            base = [str(ffmpeg), '-nostdin', '-hide_banner', '-loglevel', 'error', '-protocol_whitelist', 'file,pipe']
            source_raster = plan.get('outpainting') or {'source_width': info['width'], 'source_height': info['height']}
            vf = f"setpts=PTS-STARTPTS,trim=start={start:.12f}:end={end:.12f},setpts=PTS-STARTPTS,scale={source_raster['source_width']}:{source_raster['source_height']}:flags=lanczos,setsar=1,fps=fps={info['fps']}:start_time=0:round=near,tpad=stop_mode=clone:stop_duration={1 / float(Fraction(info['fps'])):.12f},format=rgba"
            decoder = [*base, '-i', str(source), '-map', f"0:{info['source_stream_index']}", '-an', '-sn', '-dn', '-vf', vf, '-frames:v', str(info['frames']), '-f', 'rawvideo', '-pix_fmt', 'rgba', 'pipe:1']
            if adapter['engine'] in {'torchscript-lama-local-v1', 'diffusers-wan-vace-local-v1'}:
                from .local_inpainting import decoder_command
                decoder = decoder_command(base, source, plan, vf)
            encoder = [*base, '-n', '-f', 'rawvideo', '-pixel_format', 'rgba', '-video_size', f"{info['width']}x{info['height']}", '-framerate', info['fps'], '-i', 'pipe:0']
            if plan['audio']['preserve']:
                offset = plan['audio']['source_offset_seconds']
                encoder += ['-protocol_whitelist', 'file,pipe', '-i', str(source), '-map', '0:v:0', '-map', '1:a:0', '-af',
                            f'asetpts=PTS-STARTPTS+({offset:.12f})/TB,atrim=start={start:.12f}:end={end:.12f},asetpts=PTS-({start:.12f})/TB,aresample=async=1:first_pts=0,apad=whole_dur={duration:.12f},atrim=end={duration:.12f}', '-c:a', 'pcm_s24le']
            else:
                encoder += ['-map', '0:v:0', '-an']
            encoder += ['-c:v', 'qtrle', '-pix_fmt', 'argb', '-fps_mode', 'passthrough', '-t', f'{duration:.12f}', '-map_metadata', '-1', str(staged)]
            processes = []
            with contextlib.ExitStack() as stack:
                assign = stack.enter_context(_windows_job())
                logs = [stack.enter_context((work / (name + '.log')).open('w+b')) for name in ('decoder', 'worker', 'encoder')]
                try:
                    diagnostic.start_failure_role = 'decoder'
                    decode = subprocess.Popen(decoder, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=logs[0])
                    diagnostic.processes.started('decoder', decode)
                    diagnostic.start_failure_role = None
                    processes.append(decode); assign(decode)
                    diagnostic.start_failure_role = 'worker'
                    worker = subprocess.Popen(_worker_command(adapter, request_path), stdin=decode.stdout, stdout=subprocess.PIPE, stderr=logs[1])
                    diagnostic.processes.started('worker', worker)
                    diagnostic.start_failure_role = None
                    processes.append(worker); assign(worker)
                    decode.stdout.close()
                    diagnostic.start_failure_role = 'encoder'
                    encode = subprocess.Popen(encoder, stdin=worker.stdout, stdout=subprocess.DEVNULL, stderr=logs[2])
                    diagnostic.processes.started('encoder', encode)
                    diagnostic.start_failure_role = None
                    processes.append(encode); assign(encode)
                    worker.stdout.close()
                    diagnostic.start_failure_role = None
                    diagnostic.stage = 'running'
                    last_frame = -1
                    while any(p.poll() is None for p in processes):
                        diagnostic.observe()
                        if cancel_file and cancel_file.exists():
                            raise AppError('CANCELLED', '抠像已取消', exit_code=8)
                        if time.monotonic() - started > timeout:
                            raise AppError('TIMEOUT', '抠像超过显式时间预算', exit_code=8)
                        if staged.exists() and staged.stat().st_size > MAX_INPUT_BYTES:
                            raise AppError('MATTING_OUTPUT_TOO_LARGE', '透明中间素材超过项目单文件预算，请调整范围或画幅', exit_code=3)
                        if diagnostic.processes.first_failure_roles or any(p.poll() not in (None, 0) for p in processes):
                            break
                        if progress:
                            with contextlib.suppress(OSError, ValueError, KeyError, TypeError):
                                frame = diagnostic.read_progress().get('frames')
                                if type(frame) is int and 0 <= frame <= info['frames'] and frame != last_frame:
                                    progress(min(frame, info['frames']), info['frames'])
                                    last_frame = frame
                                    diagnostic.last_reported_frame = frame
                        time.sleep(.05)
                    if any(p.poll() not in (0,) for p in processes):
                        raise AppError('MATTING_PIPELINE_FAILED', '离线视频管道失败，全部子进程将停止', exit_code=6, cause=diagnostic.failure_text())
                finally:
                    primary_error = sys.exc_info()[1]
                    if diagnostic.start_failure_role:
                        diagnostic.processes.start_failed(diagnostic.start_failure_role)
                    diagnostic.processes.before_cleanup()
                    for process in processes:
                        if process.poll() is None:
                            try:
                                process.kill()
                            except OSError:
                                diagnostic.cleanup_warnings.append({'code': 'DIAGNOSTIC_CHILD_KILL_FAILED', 'pid': process.pid})
                    for process in processes:
                        try:
                            process.wait(timeout=10)
                        except (OSError, subprocess.TimeoutExpired):
                            diagnostic.cleanup_warnings.append({'code': 'DIAGNOSTIC_CHILD_WAIT_FAILED', 'pid': process.pid})
                        finally:
                            if process.stdout:
                                try:
                                    process.stdout.close()
                                except OSError:
                                    diagnostic.cleanup_warnings.append({'code': 'DIAGNOSTIC_PIPE_CLOSE_FAILED', 'pid': process.pid})
                    diagnostic.processes.finished()
                    if diagnostic.cleanup_warnings and primary_error is None:
                        raise AppError('MATTING_PIPELINE_FAILED', '原生视频管道回收未完成', exit_code=6)
                diagnostic.stage = 'validating-response'
                try:
                    response_bytes, _ = diagnostic.prepared_directory.read('response.json', 128 * 1024)
                    if response_bytes is None:
                        raise ValueError('response exceeds budget')
                    response = json.loads(response_bytes)
                    if not isinstance(response, dict):
                        raise ValueError('response is not an object')
                except (ValueError, OSError) as exc:
                    raise AppError('MATTING_WORKER_OUTPUT_INVALID', '抠像报告格式或大小无效', exit_code=6) from exc
                validate_response(response, request)
            diagnostic.stage = 'probing-output'
            result_probe = probe_media(staged)
            video = result_probe.get('video') or {}
            audio = result_probe.get('audio') or {}
            output_stream = next((s for s in result_probe.get('streams', []) if s.get('codec_type') == 'video'), {})
            if video.get('codec') != 'qtrle' or video.get('pix_fmt') != 'argb' or (video.get('width'), video.get('height')) != (info['width'], info['height']) or abs(float(Fraction(video.get('fps') or '0')) - float(Fraction(info['fps']))) > .00001 or int(output_stream.get('nb_frames', -1)) != info['frames'] or abs(float(video.get('duration_seconds') or 0) - duration) > .001 or bool(audio.get('codec')) != plan['audio']['preserve']:
                raise AppError('MATTING_OUTPUT_INVALID', '抠像编码格式、画幅、帧率、时长或音频不符', exit_code=6)
            if plan['audio']['preserve'] and abs(float(audio.get('duration_seconds') or 0) - duration) > max(.002, 2 / float(audio.get('sample_rate') or 48000)):
                raise AppError('MATTING_AUDIO_CLOCK_INVALID', '抠像音频未覆盖实际输出时长', exit_code=6)
            diagnostic.stage = 'verifying-rgba'
            checked = run_process([*base, '-i', str(staged), '-map', '0:v:0', '-an', '-pix_fmt', 'rgba', '-fps_mode', 'passthrough', '-f', 'hash', '-hash', 'sha256', 'pipe:1'], timeout=max(.01, timeout - (time.monotonic() - started)), cancel_file=cancel_file)
            expected_hash = response['metrics']['rgba_sha256']
            if checked.returncode or checked.stdout.strip().lower() != 'sha256=' + expected_hash[7:]:
                raise AppError('MATTING_ALPHA_ROUNDTRIP_FAILED', '编码后的 RGBA 与推理原始字节不一致', exit_code=6)
            if not _verify_pipeline_adapter(adapter)['ok'] or not _prompt_unchanged(plan) or 'sha256:' + sha256_file(source) != plan['source']['sha256'] or 'sha256:' + sha256_file(ffmpeg) != ffmpeg_hash:
                raise AppError('MATTING_INTEGRITY_FAILED', '抠像过程中源、模型或 FFmpeg 发生变化', exit_code=10)
            output_hash = 'sha256:' + sha256_file(staged)
            if cancel_file and cancel_file.exists():
                raise AppError('CANCELLED', '抠像发布前取消', exit_code=8)
            if time.monotonic() - started > timeout:
                raise AppError('TIMEOUT', '抠像校验超过显式时间预算', exit_code=8)
            # Windows rename refuses an existing destination, including one
            # created by an external editor after preflight. Never delete it.
            diagnostic.stage = 'publishing-output'
            staged.rename(output)
            published = True
            from .artifact_locks import verification_summary
            verification = verification_summary()
            return {'version': '0.1.0', **plan, 'output': str(output), 'sha256': output_hash, 'probe': result_probe,
                    'adapter_id': adapter['adapter_id'], 'adapter_sha256': adapter['sha256'], 'checkpoint_sha256': adapter['model_sha256'],
                    'rgba_roundtrip_verified': True, 'ffmpeg': request['ffmpeg'], 'worker': response, 'elapsed_seconds': time.monotonic() - started,
                    **({'artifact_verification': verification} if verification else {})}
    except BaseException:
        if published:
            output.unlink(missing_ok=True)
        raise
