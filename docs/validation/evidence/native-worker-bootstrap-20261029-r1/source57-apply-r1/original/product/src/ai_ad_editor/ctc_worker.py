"""Native, network-disabled Wav2Vec2 CTC forced alignment subprocess."""
from __future__ import annotations

import json
import os
import sys
import time
import traceback
import wave
from pathlib import Path

PROTOCOL = 'agent-video-ctc-align-v1'


def infer(request: dict, checkpoint) -> tuple[dict, dict]:
    import numpy as np
    import torch
    import transformers
    from transformers import Wav2Vec2FeatureExtractor, Wav2Vec2ForCTC
    from ai_ad_editor.ctc_alignment import (MAX_EMISSION_BYTES, MAX_STATES, SAMPLE_RATE,
        fail, frame_boundary, frame_windows, output_frames, timed_units, viterbi)
    from ai_ad_editor.local_ctc import _json
    adapter, prepared = request['adapter'], request['prepared']
    model_path = Path(adapter['model_path'])
    config = _json(model_path / 'config.json')
    blank = config['pad_token_id']
    torch.set_num_threads(adapter['threads'])
    if adapter['device'] == 'cuda':
        if not torch.cuda.is_available():
            raise RuntimeError('ALIGNMENT_CUDA_UNAVAILABLE')
        torch.cuda.reset_peak_memory_stats()
    with wave.open(request['input'], 'rb') as stream:
        if stream.getframerate() != SAMPLE_RATE or stream.getnchannels() != 1 or stream.getsampwidth() != 2:
            raise RuntimeError('ALIGNMENT_PCM_INVALID')
        raw_pcm = np.frombuffer(stream.readframes(stream.getnframes()), dtype='<i2')
        pcm = raw_pcm.astype(np.float32) / 32768.0
    stride, receptive = prepared['stride_samples'], prepared['receptive_samples']
    plans = []
    for segment in prepared['segments']:
        end = segment['end_sample'] or len(pcm)
        samples = end - segment['start_sample']
        windows = frame_windows(samples, stride, receptive, window_samples=round(request['window_seconds'] * SAMPLE_RATE),
                                context_samples=round(request['context_seconds'] * SAMPLE_RATE))
        frames = output_frames(samples, stride, receptive)
        columns = sorted({blank, *(t['token_id'] for t in segment['tokens'])})
        if frames * len(columns) * 4 > MAX_EMISSION_BYTES or frames * (2 * len(segment['tokens']) + 1) > MAX_STATES:
            raise fail('ALIGNMENT_DP_BUDGET_EXCEEDED', '声学输出或 CTC 回溯超出预算；请提供带明确窗口的 SRT')
        plans.append((segment, end, samples, windows, frames, columns))
    checkpoint()
    extractor = Wav2Vec2FeatureExtractor.from_pretrained(str(model_path), local_files_only=True)
    model = Wav2Vec2ForCTC.from_pretrained(str(model_path), local_files_only=True, trust_remote_code=False,
        use_safetensors=True, attn_implementation='eager', dtype=torch.float32).to(adapter['device']).eval()
    segments, calls = [], 0
    for segment, end, samples, windows, frames, columns in plans:
        emissions = np.empty((frames, len(columns)), dtype=np.float32)
        inverse = {v: i for i, v in enumerate(columns)}
        signal = pcm[segment['start_sample']:end]
        window_records = []
        for window in windows:
            checkpoint()
            piece = signal[window['sample_start']:min(samples, window['sample_end'])]
            if window['right_zero_pad']:
                piece = np.pad(piece, (0, window['right_zero_pad']))
            inputs = extractor(piece, sampling_rate=SAMPLE_RATE, return_tensors='pt')
            inputs = {k: v.to(adapter['device']) for k, v in inputs.items()}
            with torch.inference_mode():
                logits = model(**inputs).logits[0]
                expected = window['frame_end'] - window['frame_start']
                if logits.ndim != 2 or logits.shape[0] != expected or logits.shape[1] != config['vocab_size']:
                    raise RuntimeError('ALIGNMENT_MODEL_GRID_MISMATCH')
                a, b = window['core_start'], window['core_end']
                left = a - window['frame_start']
                selected = logits[left:left + b-a].float().log_softmax(-1)[:, columns].cpu().numpy()
                if not np.isfinite(selected).all():
                    raise RuntimeError('ALIGNMENT_MODEL_NONFINITE')
                emissions[a:b] = selected
            calls += 1
            window_records.append({**window, 'input_samples': len(piece), 'output_frames': expected,
                                   'retained_frames': b-a})
            del inputs, logits, selected
        token_ids = [inverse[t['token_id']] for t in segment['tokens']]
        aligned = viterbi(emissions, token_ids, inverse[blank], checkpoint=checkpoint)
        characters = []
        for token, timing in zip(segment['tokens'], aligned['tokens']):
            timing = {**timing, 'token_id': token['token_id']}
            timing['start_sample'] = segment['start_sample'] + frame_boundary(timing['start_frame'], frames, samples, stride, receptive)
            timing['end_sample'] = segment['start_sample'] + frame_boundary(timing['end_frame'], frames, samples, stride, receptive)
            characters.append({**token, **timing})
        units = timed_units(segment['text'], characters, offset=segment['start_char'], granularity=prepared['granularity'])
        activity = None
        if prepared.get('boundary_mode', 'ctc') == 'activity':
            from ai_ad_editor.ctc_activity import refine_units
            if prepared['granularity'] != 'whitespace':
                raise fail('ALIGNMENT_BOUNDARY_MODE_INVALID', 'activity 需要 whitespace 粒度')
            raw_units = units
            units, activity = refine_units(raw_pcm[segment['start_sample']:end], raw_units,
                                          offset=segment['start_sample'], checkpoint=checkpoint)
        segments.append({k: segment[k] for k in ('text', 'start_char', 'end_char', 'ignored')})
        segments[-1].update({'start_sample': segment['start_sample'], 'end_sample': end, 'frames': frames,
            'characters': characters, 'units': units, 'windows': window_records,
            'emission_bytes': int(emissions.nbytes), 'traceback_bytes': aligned['traceback_bytes'],
            'path_log_probability': aligned['path_log_probability'],
            'low_posterior_character_indices': [c['start_char'] for c in characters if c['posterior_geometric_mean'] < .1]})
        if activity is not None:
            segments[-1].update(raw_units=raw_units, activity=activity)
        del emissions
    checkpoint()
    return ({'format': 'agent-ctc-alignment-v1', 'sample_rate': SAMPLE_RATE, 'samples': len(pcm),
             'original_text': prepared['original_text'], 'original_file_text': prepared['original_file_text'],
             'index_basis': prepared['index_basis'], 'granularity': prepared['granularity'], 'case': prepared['case'],
             'boundary_mode': prepared.get('boundary_mode', 'ctc'),
             'stride_samples': stride, 'receptive_samples': receptive, 'segments': segments},
            {'model_forward_calls': calls, 'device': torch.cuda.get_device_name(0) if adapter['device'] == 'cuda' else 'cpu',
             'peak_cuda_bytes': torch.cuda.max_memory_allocated(0) if adapter['device'] == 'cuda' else None,
             'threads': adapter['threads'], 'versions': {'python': sys.version.split()[0],
                 'numpy': np.__version__, 'torch': torch.__version__, 'transformers': transformers.__version__},
             'module_paths': {'torch': str(torch.__file__), 'transformers': str(transformers.__file__)}})


def main() -> int:
    request_path = Path(sys.argv[1])
    request = json.loads(request_path.read_text(encoding='utf-8'))
    response = {'protocol': PROTOCOL, 'status': 'failed', 'network': 'disabled', 'blocked_network_events': []}
    started = time.monotonic()
    try:
        if request.get('protocol') != PROTOCOL or request.get('network') != 'disabled':
            raise ValueError('Invalid offline CTC request')
        # This module is loaded from the same installed package, without model code.
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        from ai_ad_editor.whisper_worker import install_network_guard
        install_network_guard(response['blocked_network_events'])
        runtime = Path(request['runtime_root'])
        for key, name in {'TEMP': 'temp', 'TMP': 'temp', 'TMPDIR': 'temp', 'HF_HOME': 'hf',
            'HF_HUB_CACHE': 'hf/hub', 'TORCH_HOME': 'torch', 'XDG_CACHE_HOME': 'cache'}.items():
            path = runtime / name
            path.mkdir(parents=True, exist_ok=True)
            os.environ[key] = str(path)
        os.environ.update({'HF_HUB_OFFLINE': '1', 'TRANSFORMERS_OFFLINE': '1', 'HF_HUB_DISABLE_TELEMETRY': '1',
                           'DO_NOT_TRACK': '1', 'TOKENIZERS_PARALLELISM': 'false', 'TQDM_DISABLE': '1'})
        sys.dont_write_bytecode = True
        from ai_ad_editor.artifact_locks import artifact_entry, verification_scope, verification_summary
        from ai_ad_editor.local_asr import verify_adapter
        from ai_ad_editor.local_ctc import ENGINE
        def checkpoint():
            if request.get('cancel_file') and Path(request['cancel_file']).exists():
                raise RuntimeError('CANCELLED')
        with verification_scope():
            checkpoint()
            response['request_sha256'] = artifact_entry(request_path, 'alignment-request')['sha256']
            adapter = request['adapter']
            if adapter.get('engine') != ENGINE or not verify_adapter(adapter)['ok']:
                raise ValueError('ALIGNMENT_INTEGRITY_FAILED')
            if artifact_entry(Path(request['input']), 'alignment-pcm')['sha256'] != request['input_sha256']:
                raise ValueError('ALIGNMENT_INPUT_HASH_MISMATCH')
            alignment, metrics = infer(request, checkpoint)
            if response['blocked_network_events']:
                raise RuntimeError('ALIGNMENT_NETWORK_ATTEMPT_REJECTED')
            response.update({'status': 'succeeded', 'alignment': alignment, **metrics,
                'input_sha256': request['input_sha256'], 'source_sha256': request['source_sha256'],
                'adapter_sha256': adapter['sha256'], 'verification': verification_summary()})
    except Exception as exc:
        response.update({'error_type': type(exc).__name__, 'message': str(exc), 'traceback': traceback.format_exc()[-4000:]})
    response['elapsed_seconds'] = round(time.monotonic() - started, 3)
    Path(request['response']).write_text(json.dumps(response, ensure_ascii=False, indent=2, allow_nan=False) + '\n', encoding='utf-8')
    return 0 if response['status'] == 'succeeded' else 1


if __name__ == '__main__':
    raise SystemExit(main())
