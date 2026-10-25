"""Explicit offline CTC inventory and isolated native worker protocol."""
from __future__ import annotations

import json
import math
import time
import wave
from pathlib import Path
from typing import Any

from .artifact_locks import artifact_entry
from .ctc_alignment import (MAX_SAMPLES, MAX_TOKENS, SAMPLE_RATE, conv_grid, fail,
                            frame_boundary, map_text, output_frames, timed_units)
from .media import ffmpeg_path, probe_media
from .utils import atomic_write_json, new_id, run_process, sha256_file

ENGINE = 'transformers-wav2vec2-ctc-local-v1'
PROTOCOL = 'agent-video-ctc-align-v1'


def implementation_files() -> list[Path]:
    return [Path(__file__).with_name(name) for name in (
        'local_ctc.py', 'ctc_alignment.py', 'ctc_activity.py', 'ctc_worker.py', 'ctc_cli.py', 'local_asr.py',
        'artifact_locks.py', 'whisper_worker.py', 'utils.py', 'policy.py')]


def _json(path: Path) -> dict[str, Any]:
    def pairs(items):
        out = {}
        for key, value in items:
            if key in out:
                raise ValueError('Duplicate JSON keys')
            out[key] = value
        return out
    if path.stat().st_size > 4 * 1024 * 1024:
        raise ValueError('Model configuration exceeds 4 MiB')
    value = json.loads(path.read_text(encoding='utf-8'), object_pairs_hook=pairs)
    if not isinstance(value, dict) or value.get('auto_map') or value.get('custom_pipelines'):
        raise ValueError('Invalid configuration or custom model code')
    return value


def model_files(model: Path) -> list[Path]:
    try:
        if model.is_symlink() or getattr(model, 'is_junction', lambda: False)():
            raise ValueError('Model root cannot be a link')
        all_paths = list(model.rglob('*'))
        if len(all_paths) > 512 or any(p.is_symlink() or getattr(p, 'is_junction', lambda: False)() for p in all_paths):
            raise ValueError('Linked or excessive model components')
        files = sorted(p for p in all_paths if p.is_file())
        if any(p.suffix.lower() not in {'.json', '.txt', '.md', '.safetensors'} for p in files):
            raise ValueError('Only safetensors and plain configuration/documentation are permitted')
        for path in files:
            artifact_entry(path, 'model')
        required = {'config.json', 'preprocessor_config.json', 'vocab.json', 'tokenizer_config.json', 'special_tokens_map.json'}
        if not required.issubset({p.name for p in files if p.parent == model}):
            raise ValueError('Incomplete local CTC processor/model bundle')
        for path in files:
            if path.suffix == '.json':
                _json(path)
        config = _json(model / 'config.json')
        preprocessor = _json(model / 'preprocessor_config.json')
        vocab = _json(model / 'vocab.json')
        if config.get('model_type') != 'wav2vec2' or config.get('architectures') != ['Wav2Vec2ForCTC']:
            raise ValueError('Only standard Wav2Vec2ForCTC is supported')
        if preprocessor.get('sampling_rate') != SAMPLE_RATE or preprocessor.get('feature_extractor_type') != 'Wav2Vec2FeatureExtractor':
            raise ValueError('CTC requires the explicit 16 kHz Wav2Vec2 extractor')
        if not vocab or len(vocab) > 65536 or any(type(i) is not int for i in vocab.values()) or set(vocab.values()) != set(range(len(vocab))):
            raise ValueError('Vocab IDs must be unique, dense and bounded')
        if config.get('vocab_size') != len(vocab) or type(config.get('pad_token_id')) is not int or config['pad_token_id'] not in vocab.values():
            raise ValueError('Vocabulary/CTC head/blank mismatch')
        conv_grid(config)
        index = model / 'model.safetensors.index.json'
        weights = set(_json(index)['weight_map'].values()) if index.is_file() else {'model.safetensors'}
        if not weights:
            raise ValueError('Empty safetensors inventory')
        for name in weights:
            if not isinstance(name, str) or Path(name).name != name or Path(name).suffix != '.safetensors' or not (model / name).is_file():
                raise ValueError('Invalid safetensors shard')
        if {p.name for p in files if p.suffix == '.safetensors'} != weights:
            raise ValueError('Unreferenced safetensors in model root')
        return files
    except (ValueError, TypeError, OSError, KeyError, AttributeError) as exc:
        raise fail('ALIGNMENT_MODEL_INVALID', '本地 CTC 模型/词表不完整或不安全: ' + str(exc), exit_code=10) from exc


def prepare_text(transcript: dict[str, Any], adapter: dict[str, Any], *, case: str, granularity: str,
                 boundary_mode: str = 'ctc') -> dict[str, Any]:
    if boundary_mode not in {'ctc', 'activity'} or (boundary_mode == 'activity' and granularity != 'whitespace'):
        raise fail('ALIGNMENT_BOUNDARY_MODE_INVALID', 'activity 边界估计需要显式 whitespace 粒度；字符/连续语音仍使用 ctc')
    model = Path(adapter['model_path'])
    config, vocab = _json(model / 'config.json'), _json(model / 'vocab.json')
    prepared = {**transcript, 'case': case, 'granularity': granularity, 'boundary_mode': boundary_mode,
                'stride_samples': conv_grid(config)[0], 'receptive_samples': conv_grid(config)[1]}
    prepared['segments'] = [{**segment, **map_text(segment['text'], vocab, config['pad_token_id'],
        case=case, offset=segment['start_char'])} for segment in transcript['segments']]
    if sum(len(s['tokens']) for s in prepared['segments']) > MAX_TOKENS:
        raise fail('ALIGNMENT_TOKEN_BUDGET_EXCEEDED', '逐字稿总声学 token 超过 8192')
    # Validate display granularity even in dry-run, without allocating audio.
    timed_units('', [], offset=0, granularity=granularity)
    return prepared


def validate_alignment(value: Any, prepared: dict[str, Any], samples: int, *, pcm_path: Path | None = None,
                       checkpoint=lambda: None) -> dict[str, Any]:
    if not isinstance(value, dict) or value.get('sample_rate') != SAMPLE_RATE or value.get('samples') != samples or value.get('original_text') != prepared['original_text'] or not isinstance(value.get('segments'), list) or len(value['segments']) != len(prepared['segments']):
        raise fail('ALIGNMENT_RESULT_INVALID', 'CTC 返回的原文或采样时钟不匹配', exit_code=6)
    expected_fields = {'format': 'agent-ctc-alignment-v1', **{k: prepared[k] for k in (
        'original_file_text', 'index_basis', 'granularity', 'case', 'stride_samples', 'receptive_samples')}}
    if any(value.get(k) != v for k, v in expected_fields.items()):
        raise fail('ALIGNMENT_RESULT_INVALID', 'CTC 返回的原文件、粒度或模型时钟不匹配', exit_code=6)
    boundary_mode = prepared.get('boundary_mode', 'ctc')
    if value.get('boundary_mode', 'ctc') != boundary_mode or boundary_mode not in {'ctc', 'activity'}:
        raise fail('ALIGNMENT_RESULT_INVALID', 'CTC 返回的边界模式与请求不匹配', exit_code=6)
    if boundary_mode == 'activity' and (prepared['granularity'] != 'whitespace' or pcm_path is None):
        raise fail('ALIGNMENT_RESULT_INVALID', '活动边界必须使用 whitespace 与同一解码 PCM 验证', exit_code=6)
    stride, receptive = prepared['stride_samples'], prepared['receptive_samples']
    for actual, expected in zip(value['segments'], prepared['segments']):
        if not isinstance(actual, dict):
            raise fail('ALIGNMENT_RESULT_INVALID', 'CTC 段落无效', exit_code=6)
        start, end = expected['start_sample'], expected['end_sample'] or samples
        frames = output_frames(end - start, stride, receptive)
        for key in ('text', 'start_char', 'end_char', 'ignored'):
            if actual.get(key) != expected[key]:
                raise fail('ALIGNMENT_RESULT_INVALID', 'CTC 返回的原文索引/忽略项不匹配', exit_code=6)
        if actual.get('start_sample') != start or actual.get('end_sample') != end or end > samples or actual.get('frames') != frames:
            raise fail('ALIGNMENT_RESULT_INVALID', 'CTC 段落的源时间窗口不匹配', exit_code=6)
        chars = actual.get('characters')
        if not isinstance(chars, list) or len(chars) != len(expected['tokens']):
            raise fail('ALIGNMENT_RESULT_INVALID', 'CTC 字符未完整覆盖原文', exit_code=6)
        previous = 0
        for char, token in zip(chars, expected['tokens']):
            if not isinstance(char, dict) or any(char.get(k) != v for k, v in token.items()):
                raise fail('ALIGNMENT_RESULT_INVALID', 'CTC token/原文引用不匹配', exit_code=6)
            a, b, posterior = char.get('start_frame'), char.get('end_frame'), char.get('posterior_geometric_mean')
            if type(a) is not int or type(b) is not int or not previous <= a < b <= frames or type(posterior) not in (int, float) or not math.isfinite(posterior) or not 0 <= posterior <= 1:
                raise fail('ALIGNMENT_RESULT_INVALID', 'CTC 字符时码或后验无效', exit_code=6)
            sa = start + frame_boundary(a, frames, end - start, stride, receptive)
            sb = start + frame_boundary(b, frames, end - start, stride, receptive)
            if sa >= sb or type(char.get('start_sample')) is not int or type(char.get('end_sample')) is not int or char.get('start_sample') != sa or char.get('end_sample') != sb:
                raise fail('ALIGNMENT_RESULT_INVALID', 'CTC 字符时码未使用声明的采样网格', exit_code=6)
            previous = b
        units = timed_units(expected['text'], chars, offset=expected['start_char'], granularity=prepared['granularity'])
        if boundary_mode == 'activity':
            from .ctc_activity import refine_units
            import numpy as np
            if actual.get('raw_units') != units:
                raise fail('ALIGNMENT_RESULT_INVALID', '原始 CTC 词时间与字符时间不一致', exit_code=6)
            checkpoint()
            try:
                with wave.open(str(pcm_path), 'rb') as stream:
                    if (stream.getframerate() != SAMPLE_RATE or stream.getnchannels() != 1
                            or stream.getsampwidth() != 2 or stream.getnframes() != samples):
                        raise ValueError('PCM format/sample clock changed')
                    stream.setpos(start)
                    pcm = np.frombuffer(stream.readframes(end - start), dtype='<i2')
                if len(pcm) != end - start:
                    raise ValueError('Incomplete PCM')
            except (OSError, ValueError, EOFError, wave.Error) as exc:
                raise fail('ALIGNMENT_RESULT_INVALID', '活动边界无法核验同一 PCM: ' + str(exc), exit_code=6) from exc
            refined, report = refine_units(pcm, units, offset=start, checkpoint=checkpoint)
            if actual.get('units') != refined or actual.get('activity') != report:
                raise fail('ALIGNMENT_RESULT_INVALID', '活动边界/决定与源 PCM 独立重算不一致', exit_code=6)
        elif actual.get('units') != units:
            raise fail('ALIGNMENT_RESULT_INVALID', 'CTC 词时间与字符时间不一致', exit_code=6)
    return value


def _align_registered(root: Path, source: Path, *, adapter: dict[str, Any], prepared: dict[str, Any], job: Path,
                     window_seconds: float, context_seconds: float, timeout: float,
                     cancel_file: Path | None) -> dict[str, Any]:
    from .local_asr import verify_adapter
    from .ctc_alignment import frame_windows
    started = time.monotonic()
    def remaining() -> float:
        if cancel_file and cancel_file.exists():
            raise fail('CANCELLED', '对齐任务已取消', exit_code=8)
        left = timeout - (time.monotonic() - started)
        if left <= 0:
            raise fail('PROCESS_TIMEOUT', '对齐任务超过显式总超时', exit_code=6)
        return left
    if adapter.get('engine') != ENGINE or not verify_adapter(adapter)['ok']:
        raise fail('ALIGNMENT_INTEGRITY_FAILED', 'CTC 引擎或登记摘要无效', exit_code=10)
    source_hash = artifact_entry(source, 'alignment-source')['sha256']
    duration = float(probe_media(source).get('duration_seconds') or 0)
    if not math.isfinite(duration) or not 0 < duration <= 1800:
        raise fail('ALIGNMENT_AUDIO_BUDGET_EXCEEDED', '源音频时长须为 0–1800 秒，不进行静默截断')
    pcm, response = job / 'input.wav', job / 'response.json'
    result = run_process([ffmpeg_path(), '-hide_banner', '-loglevel', 'error', '-nostdin', '-n',
        '-i', str(source), '-vn', '-ar', str(SAMPLE_RATE), '-ac', '1', '-c:a', 'pcm_s16le', str(pcm)],
        timeout=remaining(), cancel_file=cancel_file)
    if result.returncode:
        raise fail('ALIGNMENT_AUDIO_DECODE_FAILED', result.stderr[-1500:], exit_code=6)
    with wave.open(str(pcm), 'rb') as stream:
        samples = stream.getnframes()
        if stream.getframerate() != SAMPLE_RATE or stream.getnchannels() != 1 or stream.getsampwidth() != 2 or not 0 < samples <= MAX_SAMPLES:
            raise fail('ALIGNMENT_PCM_INVALID', '实际 PCM 格式或样本数超出契约', exit_code=6)
    for segment in prepared['segments']:
        end = segment['end_sample'] or samples
        if not 0 <= segment['start_sample'] < end <= samples:
            raise fail('ALIGNMENT_TRANSCRIPT_WINDOW_INVALID', 'SRT 时间窗口超出实际解码样本')
        frame_windows(end - segment['start_sample'], prepared['stride_samples'], prepared['receptive_samples'],
                      window_samples=round(window_seconds * SAMPLE_RATE), context_samples=round(context_seconds * SAMPLE_RATE))
    request_path = job / 'request.json'
    request = {'protocol': PROTOCOL, 'network': 'disabled', 'adapter': adapter, 'input': str(pcm),
               'input_sha256': artifact_entry(pcm, 'alignment-pcm')['sha256'], 'source_sha256': source_hash,
               'prepared': prepared, 'window_seconds': window_seconds, 'context_seconds': context_seconds,
               'response': str(response), 'runtime_root': str(job / 'runtime'),
               'cancel_file': str(cancel_file) if cancel_file else None}
    atomic_write_json(request_path, request)
    request_hash = artifact_entry(request_path, 'alignment-request')['sha256']
    worker = Path(__file__).with_name('ctc_worker.py')
    result = run_process([adapter['python_executable'], '-I', '-B', '-X', 'utf8', str(worker), str(request_path)],
                         timeout=remaining(), cancel_file=cancel_file)
    try:
        if response.stat().st_size > 32 * 1024 * 1024:
            raise ValueError('Oversized response')
        payload = json.loads(response.read_text(encoding='utf-8'))
    except (OSError, ValueError) as exc:
        raise fail('ALIGNMENT_WORKER_FAILED', '离线对齐 worker 未返回有效结果: ' + result.stderr[-1500:], exit_code=6) from exc
    bindings = {'protocol': PROTOCOL, 'status': 'succeeded', 'network': 'disabled', 'blocked_network_events': [],
                'request_sha256': request_hash, 'input_sha256': request['input_sha256'],
                'source_sha256': source_hash, 'adapter_sha256': adapter['sha256']}
    if result.returncode or not isinstance(payload, dict) or any(payload.get(k) != v for k, v in bindings.items()):
        raise fail('ALIGNMENT_WORKER_FAILED', '离线 CTC 协议/推理失败: ' + json.dumps(payload, ensure_ascii=False)[-3500:], exit_code=6)
    remaining()
    if artifact_entry(source, 'alignment-source')['sha256'] != source_hash or not verify_adapter(adapter)['ok']:
        raise fail('ALIGNMENT_INTEGRITY_FAILED', '推理过程中源或模型发生变化', exit_code=10)
    if artifact_entry(pcm, 'alignment-pcm')['sha256'] != request['input_sha256']:
        raise fail('ALIGNMENT_INTEGRITY_FAILED', '推理过程中解码 PCM 发生变化', exit_code=10)
    value = validate_alignment(payload.get('alignment'), prepared, samples, pcm_path=pcm, checkpoint=remaining)
    value.update({'protocol': PROTOCOL, 'engine': ENGINE, 'adapter_id': adapter['adapter_id'],
                  'model_sha256': adapter['sha256'], 'source_sha256': source_hash,
                  'request_sha256': request_hash, 'worker': {k: v for k, v in payload.items() if k != 'alignment'},
                  'diagnostic_directory': str(job), 'review_required': True,
                  'warnings': ['ALIGNMENT_REVIEW_REQUIRED'], 'elapsed_seconds': round(time.monotonic() - started, 3)})
    return value


def align_registered(root: Path, source: Path, **options) -> dict[str, Any]:
    """Retain diagnostics even when cancellation terminates the native worker."""
    job = root / 'cache' / 'alignment' / new_id('run')
    job.mkdir(parents=True, exist_ok=False)
    try:
        return _align_registered(root, source, job=job, **options)
    except BaseException as exc:
        atomic_write_json(job / 'failure.json', {'status': 'failed', 'protocol': PROTOCOL,
            'network': 'disabled', 'error_type': type(exc).__name__, 'message': str(exc),
            'error_code': getattr(exc, 'code', None), 'registered_output_assets': False})
        raise
