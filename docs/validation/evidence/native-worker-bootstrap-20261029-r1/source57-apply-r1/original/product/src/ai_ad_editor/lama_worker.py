"""Isolated local TorchScript LaMa worker; paired RGBA input and RGBA output."""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path


def infer(request: dict, response: dict) -> None:
    from ai_ad_editor.local_matting import request_hash
    from ai_ad_editor.local_inpainting import INPAINT_ENGINE, INPAINT_PROTOCOL, mask_unchanged, normalize_options, verify_adapter
    from ai_ad_editor.inpainting_frames import process_frames
    from ai_ad_editor.runtime import configure_local_runtime
    from ai_ad_editor.utils import atomic_write_json, sha256_file
    if request.get('engine') != INPAINT_ENGINE or request.get('protocol') != INPAINT_PROTOCOL or request.get('network') != 'disabled' or request_hash(request) != request.get('request_sha256'):
        raise ValueError('INPAINT_REQUEST_INVALID')
    adapter = request['adapter']
    if not verify_adapter(adapter)['ok'] or not mask_unchanged(request) or normalize_options(**request['inpainting']) != request['inpainting']:
        raise ValueError('INPAINT_INPUT_INTEGRITY_FAILED')
    if 'sha256:' + sha256_file(Path(request['source']['path'])) != request['source']['sha256']:
        raise ValueError('INPAINT_SOURCE_CHANGED')
    os.environ['AI_AD_EDITOR_RUNTIME_DIR'] = request['runtime_root']
    configure_local_runtime()
    import numpy as np
    import torch
    device = adapter['settings']['device']
    if device == 'cuda' and not torch.cuda.is_available():
        raise ValueError('INPAINT_CUDA_UNAVAILABLE_NO_FALLBACK')
    torch.set_num_threads(adapter['settings']['threads']); torch.set_num_interop_threads(1)
    if device == 'cuda':
        torch.backends.cuda.matmul.allow_tf32 = False; torch.backends.cudnn.allow_tf32 = False
        torch.cuda.reset_peak_memory_stats()
    model = None
    def predict(image, mask):
        nonlocal model
        if model is None:
            # Load only after the frame/mask-dependent resource admission check.
            with Path(adapter['model_path']).open('rb') as handle:
                model = torch.jit.load(handle, map_location='cpu').to(device).eval()
            if any(p.device.type != device or p.is_floating_point() and p.dtype != torch.float32 for p in model.parameters()):
                raise ValueError('INPAINT_DEVICE_OR_PRECISION_MISMATCH')
        with torch.inference_mode():
            result = model(torch.from_numpy(image).to(device), torch.from_numpy(mask).to(device))
        if not torch.is_tensor(result) or result.dtype != torch.float32 or result.device.type != device:
            raise ValueError('INPAINT_TENSOR_OUTPUT_INVALID')
        return result.detach().cpu().numpy()
    last = 0.
    def progress(frame):
        nonlocal last
        if frame == request['video']['frames'] or time.monotonic() - last >= .5:
            atomic_write_json(Path(request['progress']), {'frames': frame}); last = time.monotonic()
    info = request['video']
    metrics = process_frames(sys.stdin.buffer, sys.stdout.buffer, width=info['width'], height=info['height'], frames=info['frames'],
                             infer=predict, options=request['inpainting'], channel=request['mask']['channel'], budget=adapter['settings']['state_budget_bytes'], progress=progress)
    if not verify_adapter(adapter)['ok'] or not mask_unchanged(request) or 'sha256:' + sha256_file(Path(request['source']['path'])) != request['source']['sha256']:
        raise ValueError('INPAINT_INPUT_CHANGED_DURING_INFERENCE')
    response.update(status='succeeded', metrics=metrics, model_loaded=model is not None, providers=['torch-' + device],
                    versions={'python': sys.version.split()[0], 'numpy': np.__version__, 'torch': torch.__version__})
    if device == 'cuda': response['cuda_peak_allocated_bytes'] = torch.cuda.max_memory_allocated()


def main() -> int:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from ai_ad_editor.rvm_worker import install_network_guard
    from ai_ad_editor.utils import atomic_write_json
    request = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
    events = []
    response = {'protocol': request.get('protocol'), 'engine': request.get('engine'), 'network': 'disabled', 'blocked_network_events': events,
                'request_sha256': request.get('request_sha256'), 'adapter_sha256': request.get('adapter', {}).get('sha256'),
                'source_sha256': request.get('source', {}).get('sha256'), 'mask_sha256': request.get('mask', {}).get('sha256'),
                'mask_plan_sha256': request.get('mask', {}).get('plan_sha256'), 'inpainting': request.get('inpainting'), 'status': 'failed'}
    if 'outpainting' in request: response['outpainting'] = request['outpainting']
    started = time.monotonic(); install_network_guard(events)
    try:
        infer(request, response)
    except Exception as exc:
        response['error'] = type(exc).__name__ + ': ' + str(exc)
    response['elapsed_seconds'] = time.monotonic() - started
    atomic_write_json(Path(request['response']), response)
    return 0 if response['status'] == 'succeeded' else 1


if __name__ == '__main__':
    raise SystemExit(main())
