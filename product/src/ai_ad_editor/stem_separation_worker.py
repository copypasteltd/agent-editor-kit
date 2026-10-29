"""Native offline HDemucs four-source worker; no bundle downloads."""
from __future__ import annotations

import json
import os
from pathlib import Path
import sys
import time
import traceback


def main():
    request = json.loads(Path(sys.argv[1]).read_text('utf-8'))
    response = dict(protocol='agent-hdemucs-four-stems-v1', status='failed', network='disabled', blocked_network_events=[])
    started = time.monotonic()
    try:
        if request.get('protocol') != response['protocol'] or request.get('network') != 'disabled':
            raise ValueError('Invalid offline four-stem request')
        application_root = str(Path(__file__).resolve().parents[1])
        sys.path.insert(0, application_root)
        try:
            import ai_ad_editor
        finally:
            sys.path.remove(application_root)
        if Path(ai_ad_editor.__file__).resolve() != Path(__file__).resolve().with_name('__init__.py'):
            raise RuntimeError('NATIVE_WORKER_APPLICATION_CHANGED')
        from ai_ad_editor.demucs_worker import install_network_guard
        install_network_guard(response['blocked_network_events'])
        runtime = Path(request['runtime_root'])
        for key, name in {'TEMP':'temp', 'TMP':'temp', 'TMPDIR':'temp', 'HF_HOME':'hf', 'TORCH_HOME':'torch', 'XDG_CACHE_HOME':'cache'}.items():
            path = runtime/name; path.mkdir(parents=True, exist_ok=True); os.environ[key] = str(path)
        os.environ.update(HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', HF_HUB_DISABLE_TELEMETRY='1',
                          DO_NOT_TRACK='1', CUBLAS_WORKSPACE_CONFIG=':4096:8')
        from ai_ad_editor.artifact_locks import verification_scope
        from ai_ad_editor.stem_separation import PROTOCOL, fingerprint, verify_adapter, local_file
        from ai_ad_editor.stem_separation_dsp import ROLES, separate_pcm
        from ai_ad_editor.utils import sha256_file
        with verification_scope():
            adapter = request['adapter']
            if (request['protocol'] != PROTOCOL or not verify_adapter(adapter)['ok']
                    or fingerprint({k:v for k,v in request.items() if k != 'request_sha256'}) != request['request_sha256']):
                raise ValueError('FOUR_STEM_REQUEST_INTEGRITY_FAILED')
            source = local_file(request['input'])
            if source.stat().st_size != request['samples']*8 or 'sha256:'+sha256_file(source) != request['input_sha256']:
                raise ValueError('FOUR_STEM_INPUT_HASH_MISMATCH')
            paths = {key:Path(value) for key,value in request['outputs'].items()}
            if (set(paths) != set(ROLES) or len({source.resolve(), *(p.resolve() for p in paths.values())}) != 5
                    or any(p.exists() or p.parent != source.parent for p in paths.values())):
                raise ValueError('FOUR_STEM_OUTPUT_PATH_INVALID')
            import numpy as np
            import torch
            import torchaudio
            options = adapter['settings']; device = request['device']; index = request['device_index']
            if device not in ('cpu', 'cuda') or type(index) is not int or not 0 <= index <= 31:
                raise ValueError('FOUR_STEM_DEVICE_INVALID')
            torch.set_num_threads(options['threads']); torch.manual_seed(0)
            torch.use_deterministic_algorithms(True); torch.backends.cudnn.benchmark = False
            target = f'cuda:{index}' if device == 'cuda' else 'cpu'
            if device == 'cuda':
                if not torch.cuda.is_available() or index >= torch.cuda.device_count():
                    raise RuntimeError('FOUR_STEM_CUDA_UNAVAILABLE')
                torch.cuda.set_device(index); torch.cuda.reset_peak_memory_stats(index)
            marker = Path(request['cancel_file']) if request.get('cancel_file') else None
            def check_cancel():
                if marker and marker.exists(): raise RuntimeError('FOUR_STEM_CANCELLED')
            check_cancel()
            model = torchaudio.models.hdemucs_high(sources=list(ROLES))
            state = torch.load(adapter['model_path'], map_location='cpu', weights_only=True)
            if not isinstance(state, dict) or not state or any(not isinstance(k,str) or not torch.is_tensor(v) for k,v in state.items()):
                raise ValueError('FOUR_STEM_STATE_DICT_INVALID')
            model.load_state_dict(state, strict=True); del state
            model.eval().to(target)
            def infer(chunk):
                check_cancel()
                with torch.inference_mode():
                    output = model(torch.from_numpy(chunk).unsqueeze(0).to(target))
                if tuple(output.shape) != (1, 4, 2, chunk.shape[1]) or not torch.isfinite(output).all():
                    raise ValueError('FOUR_STEM_MODEL_OUTPUT_INVALID')
                check_cancel()
                return output[0].float().cpu().numpy()
            metrics = separate_pcm(source, paths, window=round(options['segment_seconds']*44100), overlap=options['overlap'], infer=infer)
            check_cancel()
            if response['blocked_network_events']: raise RuntimeError('FOUR_STEM_NETWORK_ATTEMPT_REJECTED')
            response.update(status='succeeded', request_sha256=request['request_sha256'], adapter_sha256=adapter['sha256'],
                input_sha256=request['input_sha256'], source_sha256=request['source_sha256'], samples=request['samples'],
                outputs={key:dict(sha256='sha256:'+sha256_file(path), bytes=path.stat().st_size) for key,path in paths.items()},
                metrics=metrics, device=device, device_index=index, dtype='float32',
                device_name=torch.cuda.get_device_name(index) if device == 'cuda' else 'cpu',
                peak_cuda_bytes=torch.cuda.max_memory_allocated(index) if device == 'cuda' else None,
                versions=dict(python=sys.version.split()[0], numpy=np.__version__, torch=torch.__version__, torchaudio=torchaudio.__version__),
                module_paths=dict(numpy=str(np.__file__), torch=str(torch.__file__), torchaudio=str(torchaudio.__file__)))
    except Exception as exc:
        response.update(error_type=type(exc).__name__, message=str(exc), traceback=traceback.format_exc()[-4000:])
    response['elapsed_seconds'] = round(time.monotonic()-started, 3)
    Path(request['response']).write_text(json.dumps(response, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    return 0 if response['status'] == 'succeeded' else 1


if __name__ == '__main__': raise SystemExit(main())
