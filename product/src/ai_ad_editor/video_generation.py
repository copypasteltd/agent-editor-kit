"""Local VACE generation from text and explicit first/last image conditions.

The existing guarded native VACE pipeline owns inference and its exact RGBA
roundtrip. This controller supplies a bounded, reproducible condition video:
grey/white means generate; a supplied image/black mask means condition. Known
endpoints are retained in the final output, not scored as generated quality.
"""
from __future__ import annotations

import copy
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import time

import numpy as np
from PIL import Image, ImageOps

from .errors import AppError, argument_error
from .local_vace import normalize_generation, buffer_budget
from .media import MAX_INPUT_BYTES, ffmpeg_path
from .native_audio_clock import cancel
from .policy import resolve_local_path
from .utils import sha256_file, run_process

PROTOCOL = 'local-vace-conditioned-video-generation-v1'
MODES = {'text-to-video': (), 'image-to-video': ('first',),
         'last-frame-to-video': ('last',), 'first-last-to-video': ('first', 'last')}
FITS = {'reject', 'contain', 'cover', 'stretch'}


def digest(value):
    return 'sha256:' + hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
        separators=(',', ':'), allow_nan=False).encode('utf8')).hexdigest()


def configuration(*, mode, width, height, frames, fps, image_fit, sampling, storage_budget_mib=2048):
    if mode not in MODES or image_fit not in FITS:
        raise argument_error('生成模式或图像适配方式无效', 'mode/image-fit')
    if any(type(v) is not int or not 64 <= v <= 2048 or v % 16 for v in (width, height)):
        raise argument_error('生成画布须为64..2048且可被16整除；不暗中缩放模型输入', 'width/height')
    if type(frames) is not int or not 5 <= frames <= 4097:
        raise argument_error('生成帧数须为5..4097', 'frames')
    try:
        rate = Fraction(fps)
        if type(fps) is bool or not 1 <= rate <= 60 or Fraction(frames, 1) / rate > 600:
            raise ValueError()
    except (ValueError, TypeError, ZeroDivisionError, OverflowError) as exc:
        raise argument_error('生成帧率须为1..60的整数或有理数，时长最多600秒', 'fps') from exc
    if type(storage_budget_mib) is not int or not 16 <= storage_budget_mib <= 65536:
        raise argument_error('生成磁盘预算须为16..65536MiB', 'storage-budget-mib')
    generation = normalize_generation(**sampling, frames=frames)
    if generation['model_input_scale'] != 1 or generation['scene_cut_frames']:
        raise argument_error('完整生成直接使用所选模型画布，不接受ROI放大或场景切点', 'sampling')
    storage = width * height * frames * 16 + 3 * 1024**2
    # Two condition MOVs plus raw encode headroom and generated MOV. Each file
    # also remains within the ordinary project media quota.
    if storage > storage_budget_mib * 1024**2 or width * height * frames * 5 > MAX_INPUT_BYTES:
        raise AppError('VIDEO_GENERATION_STORAGE_BUDGET', '完整生成条件与输出超过显式磁盘/单文件预算', exit_code=2)
    arrays = buffer_budget(width, height, generation, max(width, height))
    if arrays > 512 * 1024**2:
        raise AppError('VIDEO_GENERATION_BUFFER_BUDGET', '生成窗口数组超过512MiB；减小画布、窗口或重叠', exit_code=2)
    return dict(protocol=PROTOCOL, mode=mode, width=width, height=height, frames=frames,
        fps=str(rate), duration_seconds=float(Fraction(frames, 1) / rate), image_fit=image_fit,
        sampling=generation, storage_budget_mib=storage_budget_mib, estimated_storage_bytes=storage,
        estimated_window_array_bytes=arrays, GPU=True, network=False, audio_generated=False,
        endpoint_policy='known conditioned endpoints retained as preprocessed SDR RGB; interior is generated',
        quality_accepted=False)


def image_reference(root, asset):
    if not asset or asset.get('kind') != 'image':
        raise argument_error('首尾帧须为已登记的本地image资产', 'first-asset-id/last-asset-id')
    path = resolve_local_path(root, asset['uri'], field='generation.image')
    if not path.is_file() or path.stat().st_size > MAX_INPUT_BYTES or 'sha256:' + sha256_file(path) != asset.get('sha256'):
        raise AppError('VIDEO_GENERATION_IMAGE_CHANGED', '首尾图与登记摘要不符', exit_code=10)
    streams = asset.get('probe', {}).get('streams', [])
    stream = next((s for s in streams if s.get('codec_type') == 'video'), {})
    if stream.get('color_transfer') in {'smpte2084', 'arib-std-b67'}:
        raise argument_error('首尾图当前要求SDR；HDR须先明确转换', 'image')
    try:
        with Image.open(path) as image:
            if image.width * image.height > 16_777_216 or max(image.size) > 16384 or getattr(image, 'n_frames', 1) != 1:
                raise argument_error('首尾图须为最多16M像素的单张图像', 'image')
            if image.mode not in {'1', 'L', 'LA', 'P', 'RGB', 'RGBA'}:
                raise argument_error('首尾图当前接受明确8bit SDR图像；其他精度须先显式转换', 'image')
            if image.info.get('icc_profile'):
                raise argument_error('首尾图含ICC，须先显式转换为sRGB并去除配置后登记', 'image')
    except (OSError, Image.DecompressionBombError) as exc:
        raise argument_error('首尾图无法作为有界的本地SDR图像读取', 'image') from exc
    return dict(asset_id=asset['id'], sha256=asset['sha256'], path=str(path))


def prepared_image(path, config):
    with Image.open(path) as opened:
        image = ImageOps.exif_transpose(opened).convert('RGBA')
        # Transparent input is explicitly flattened on black. Generated video
        # is opaque; never describe this as preservation of physical matte.
        base = Image.new('RGBA', image.size, (0, 0, 0, 255)); base.alpha_composite(image)
        image = base.convert('RGB')
    size = config['width'], config['height']; fit = config['image_fit']
    if fit == 'reject' and image.size != size:
        raise argument_error('图像尺寸与画布不一致，选择明确image-fit', 'image-fit')
    if fit == 'cover': image = ImageOps.fit(image, size, Image.Resampling.LANCZOS)
    elif fit == 'contain': image = ImageOps.pad(image, size, Image.Resampling.LANCZOS, color=(0, 0, 0))
    elif fit == 'stretch': image = image.resize(size, Image.Resampling.LANCZOS)
    result = np.empty((size[1], size[0], 4), np.uint8); result[:, :, :3] = np.asarray(image); result[:, :, 3] = 255
    return result


def condition_frame(index, config, endpoints):
    width, height = config['width'], config['height']
    image = endpoints.get('first') if index == 0 else endpoints.get('last') if index == config['frames'] - 1 else None
    known = image is not None
    if not known:
        image = np.full((height, width, 4), 127, np.uint8); image[:, :, 3] = 255
    mask = np.full((height, width, 4), 0 if known else 255, np.uint8)
    # The pipeline consumes luma, independent from the mask's opaque alpha.
    mask[:, :, 3] = 255
    return image, mask


def recipe(config, references):
    public = {name: {k: v for k, v in row.items() if k != 'path'} for name, row in references.items()}
    value = dict(protocol=PROTOCOL, configuration=copy.deepcopy(config), images=public)
    return {**value, 'sha256': digest(value)}


def validate_recipe(value, *, asset, assets=None):
    try:
        if not isinstance(value, dict) or set(value) != {'protocol', 'configuration', 'images', 'sha256'} or value['protocol'] != PROTOCOL:
            raise ValueError('generation recipe fields')
        c = value['configuration']; rebuilt = configuration(**{k: c[k] for k in
            ('mode', 'width', 'height', 'frames', 'fps', 'image_fit', 'sampling', 'storage_budget_mib')})
        if c != rebuilt or set(value['images']) != set(MODES[c['mode']]) or digest({k: v for k, v in value.items() if k != 'sha256'}) != value['sha256']:
            raise ValueError('generation recipe digest/configuration')
        stream = next(s for s in asset['probe']['streams'] if s.get('codec_type') == 'video')
        if asset['kind'] != 'video' or (int(stream['width']), int(stream['height']), int(stream['nb_frames'])) != (c['width'], c['height'], c['frames']):
            raise ValueError('generation recipe raster/frame mismatch')
        if Fraction(stream['avg_frame_rate']) != Fraction(c['fps']): raise ValueError('generation recipe frame rate')
        import re
        for row in value['images'].values():
            if set(row) != {'asset_id', 'sha256'} or not re.fullmatch(r'sha256:[0-9a-f]{64}', row['sha256']):
                raise ValueError('generation recipe image')
            if not isinstance(row['asset_id'], str) or not row['asset_id']:
                raise ValueError('generation recipe image identity')
            if assets is not None and (row['asset_id'] not in assets or assets[row['asset_id']].get('kind') != 'image' or assets[row['asset_id']]['sha256'] != row['sha256']):
                raise ValueError('generation recipe image reference')
        if asset['source'].get('derived_from') != list(dict.fromkeys(row['asset_id'] for row in value['images'].values())):
            raise ValueError('generation recipe parent assets')
    except (AppError, KeyError, TypeError, ValueError, StopIteration, ZeroDivisionError) as exc:
        raise AppError('VIDEO_GENERATION_RECIPE_INVALID', '生成配方、首尾图引用或实际视频不一致', exit_code=2, cause=str(exc)) from exc


def rebind_recipe(value, *, mapping, asset, assets):
    validate_recipe(value, asset=asset, assets=assets)
    rebound = copy.deepcopy(value)
    for row in rebound['images'].values():
        row['asset_id'] = mapping[row['asset_id']]
    rebound['sha256'] = digest({k: v for k, v in rebound.items() if k != 'sha256'})
    return rebound


def execute(root, job, config, references, adapter, *, timeout, cancel_file=None, progress=None, operation_id=None):
    from .float_stream import _EncoderPipe, CHUNK_BYTES
    from .local_matting import prepare_plan, matte_native
    from .local_inpainting import prepare_mask, normalize_options
    started = time.monotonic()
    def remaining():
        cancel(cancel_file); left = timeout - (time.monotonic() - started)
        if left <= 0: raise AppError('TIMEOUT', '视频生成超过完整时间预算', exit_code=8)
        return left
    endpoints = {name: prepared_image(row['path'], config) for name, row in references.items()}
    for row in references.values():
        if 'sha256:' + sha256_file(Path(row['path'])) != row['sha256']:
            raise AppError('VIDEO_GENERATION_IMAGE_CHANGED', '准备条件时首尾图变化', exit_code=10)
    condition_hashes = {name: 'sha256:' + hashlib.sha256(image.tobytes()).hexdigest() for name, image in endpoints.items()}
    inputs = [job.path / 'conditions.mov', job.path / 'mask.mov']; raw_hashes = []
    for column, destination in enumerate(inputs):
        remaining()
        command = [ffmpeg_path(), '-nostdin', '-v', 'error', '-n', '-f', 'rawvideo', '-pixel_format', 'rgba',
            '-video_size', f"{config['width']}x{config['height']}", '-framerate', config['fps'], '-i', 'pipe:0',
            '-an', '-c:v', 'qtrle', '-pix_fmt', 'argb', '-frames:v', str(config['frames']), str(destination)]
        pipe = _EncoderPipe(command, cwd=root, cancel_file=cancel_file, timeout=remaining()); hasher = hashlib.sha256()
        try:
            for index in range(config['frames']):
                remaining(); values = condition_frame(index, config, endpoints)[column].tobytes(); hasher.update(values)
                for start in range(0, len(values), CHUNK_BYTES): pipe.put(values[start:start + CHUNK_BYTES])
            pipe.finish()
        finally: pipe.close()
        raw_hashes.append('sha256:' + hasher.hexdigest())
        checked = run_process([ffmpeg_path(), '-nostdin', '-v', 'error', '-i', str(destination), '-an', '-pix_fmt', 'rgba',
            '-f', 'hash', '-hash', 'sha256', 'pipe:1'], timeout=remaining(), cancel_file=cancel_file)
        if checked.returncode or checked.stdout.strip().lower() != 'sha256=' + hasher.hexdigest():
            raise AppError('VIDEO_GENERATION_CONDITION_ROUNDTRIP', '条件视频RGBA编码往返不一致', exit_code=6)
    plan = prepare_plan(inputs[0], adapter, end_seconds=config['duration_seconds'], fps=config['fps'],
        max_frames=config['frames'], preserve_audio=False)
    plan['mask'] = prepare_mask(root, str(inputs[1]), kind='video', video=plan['video'], channel='luma')
    plan['inpainting'] = normalize_options(threshold=.5, grow=0, feather=0, context=0, model_max_edge=max(config['width'], config['height']))
    plan['generation'] = copy.deepcopy(config['sampling'])
    from .local_vace import window_plan
    from .repair_blend import joint_blend_overhead, blend_budget_plan
    plan['windows'] = window_plan(config['frames'], plan['generation'])
    if any(plan['video'][k] != config[k] for k in ('width', 'height', 'frames', 'fps')):
        raise AppError('VIDEO_GENERATION_CONDITION_CLOCK', '实际条件视频与请求画布、帧数或时钟不一致', exit_code=6)
    plan['owned_array_budget_bytes'] = config['estimated_window_array_bytes'] + joint_blend_overhead(
        config['width'], config['height'], plan['inpainting'])
    if plan['owned_array_budget_bytes'] > adapter['settings']['state_budget_bytes']:
        raise AppError('VACE_WINDOW_BUFFER_BUDGET_EXCEEDED', '生成窗口超过已登记模型的数组预算', exit_code=2)
    plan['blend_budget'] = blend_budget_plan(config['width'], config['height'], plan['inpainting'],
        adapter['settings']['state_budget_bytes'], plan['owned_array_budget_bytes'])
    plan['video'].pop('downsample_ratio', None)
    output = job.path / 'generated.mov'
    result = matte_native(root, output, adapter=adapter, plan=plan, timeout=remaining(), cancel_file=cancel_file,
        progress=progress, operation_id=operation_id, workspace=job)
    for row in references.values():
        remaining()
        if 'sha256:' + sha256_file(Path(row['path'])) != row['sha256']:
            raise AppError('VIDEO_GENERATION_IMAGE_CHANGED', '生成期间首尾图变化，未发布结果', exit_code=10)
    endpoint_checks = {}
    for name, expected in condition_hashes.items():
        index = 0 if name == 'first' else config['frames'] - 1
        checked = run_process([ffmpeg_path(), '-nostdin', '-v', 'error', '-i', str(output), '-an',
            '-vf', f'select=eq(n\\,{index})', '-fps_mode', 'passthrough', '-frames:v', '1', '-pix_fmt', 'rgba',
            '-f', 'hash', '-hash', 'sha256', 'pipe:1'], timeout=remaining(), cancel_file=cancel_file)
        actual = 'sha256:' + checked.stdout.strip().lower().removeprefix('sha256=')
        if checked.returncode or actual != expected:
            raise AppError('VIDEO_GENERATION_ENDPOINT_CHANGED', '生成视频未保留明确的首尾条件图', exit_code=6)
        endpoint_checks[name] = dict(frame=index, expected_rgba_sha256=expected, actual_rgba_sha256=actual, equal=True)
    remaining()
    return output, dict(protocol=PROTOCOL, recipe=recipe(config, references), result=result,
        condition_rgba_sha256=raw_hashes[0], mask_rgba_sha256=raw_hashes[1], endpoint_rgba_sha256=condition_hashes,
        endpoint_checks=endpoint_checks, conditioned_endpoint_policy=config['endpoint_policy'], elapsed_seconds=time.monotonic() - started,
        audio_generated=False, generated_quality_accepted=False)
