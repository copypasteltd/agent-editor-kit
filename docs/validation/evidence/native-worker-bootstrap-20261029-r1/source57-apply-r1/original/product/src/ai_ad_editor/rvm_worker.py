"""Isolated offline RVM CPU worker. stdin/stdout carry binary RGBA only."""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path


def install_network_guard(events: list[str]) -> None:
    import socket
    socket.has_ipv6 = False
    def audit(event, args):
        if event in {'socket.connect', 'socket.connect_ex', 'socket.bind', 'socket.getaddrinfo', 'socket.gethostbyname', 'socket.gethostbyaddr', 'socket.sendto', 'urllib.Request', 'http.client.connect'}:
            events.append(event)
            raise RuntimeError('MATTING_NETWORK_DISABLED: ' + event)
    sys.addaudithook(audit)


def reject_external_tensors(message, onnx) -> None:
    if isinstance(message, onnx.TensorProto) and (message.external_data or message.data_location == onnx.TensorProto.EXTERNAL):
        raise ValueError('MATTING_ONNX_EXTERNAL_DATA_UNSUPPORTED')
    if isinstance(message, onnx.NodeProto) and message.domain not in {'', 'ai.onnx'}:
        raise ValueError('MATTING_ONNX_CUSTOM_DOMAIN_UNSUPPORTED')
    for field, value in message.ListFields():
        if field.message_type is not None:
            for child in value if field.is_repeated else [value]:
                reject_external_tensors(child, onnx)


def infer(request: dict, response: dict) -> None:
    from ai_ad_editor.local_matting import MATTING_ENGINE, MATTING_PROTOCOL, request_hash, verify_adapter
    from ai_ad_editor.matting_frames import process_frames
    from ai_ad_editor.runtime import configure_local_runtime
    from ai_ad_editor.utils import atomic_write_json, sha256_file
    if request.get('engine') != MATTING_ENGINE or request.get('protocol') != MATTING_PROTOCOL or request.get('network') != 'disabled' or request_hash(request) != request.get('request_sha256'):
        raise ValueError('MATTING_REQUEST_INVALID')
    adapter = request['adapter']
    if not verify_adapter(adapter)['ok']:
        raise ValueError('MATTING_ADAPTER_INTEGRITY_FAILED')
    os.environ['AI_AD_EDITOR_RUNTIME_DIR'] = request['runtime_root']
    configure_local_runtime()
    import numpy as np
    import onnx
    import onnxruntime as ort
    ort.disable_telemetry_events()
    model = onnx.load(adapter['model_path'], load_external_data=False)
    reject_external_tensors(model, onnx)
    del model
    options = ort.SessionOptions()
    options.intra_op_num_threads = adapter['settings']['threads']
    options.inter_op_num_threads = 1
    options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
    session = ort.InferenceSession(adapter['model_path'], sess_options=options, providers=['CPUExecutionProvider'])
    inputs = session.get_inputs()
    outputs = session.get_outputs()
    names = ['src', 'r1i', 'r2i', 'r3i', 'r4i', 'downsample_ratio']
    output_names = ['fgr', 'pha', 'r1o', 'r2o', 'r3o', 'r4o']
    if session.get_providers() != ['CPUExecutionProvider'] or [v.name for v in inputs] != names or [v.name for v in outputs] != output_names or any(v.type != 'tensor(float)' for v in inputs + outputs) or any(len(v.shape) != (1 if v.name == 'downsample_ratio' else 4) for v in inputs + outputs):
        raise ValueError('MATTING_ONNX_CONTRACT_INVALID')
    ratio = np.array([request['video']['downsample_ratio']], dtype=np.float32)
    def predict(rgb, states):
        return session.run(output_names, dict(zip(names, [rgb, *states, ratio])))
    last_progress = 0.
    def progress(frames):
        nonlocal last_progress
        if frames == request['video']['frames'] or time.monotonic() - last_progress >= .5:
            atomic_write_json(Path(request['progress']), {'frames': frames})
            last_progress = time.monotonic()
    info = request['video']
    metrics = process_frames(sys.stdin.buffer, sys.stdout.buffer, width=info['width'], height=info['height'], frames=info['frames'], infer=predict, progress=progress)
    if 'sha256:' + sha256_file(Path(request['source']['path'])) != request['source']['sha256'] or not verify_adapter(adapter)['ok']:
        raise ValueError('MATTING_INPUT_CHANGED_DURING_INFERENCE')
    response.update(status='succeeded', metrics=metrics, versions={'python': sys.version.split()[0], 'numpy': np.__version__, 'onnx': onnx.__version__, 'onnxruntime': ort.__version__}, providers=session.get_providers())


def main() -> int:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    request = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
    events: list[str] = []
    response = {'protocol': request.get('protocol'), 'engine': request.get('engine'), 'network': 'disabled', 'blocked_network_events': events,
                'request_sha256': request.get('request_sha256'), 'adapter_sha256': request.get('adapter', {}).get('sha256'), 'source_sha256': request.get('source', {}).get('sha256'), 'status': 'failed'}
    started = time.monotonic()
    install_network_guard(events)
    try:
        infer(request, response)
    except Exception as exc:
        response['error'] = type(exc).__name__ + ': ' + str(exc)
    response['elapsed_seconds'] = time.monotonic() - started
    from ai_ad_editor.utils import atomic_write_json
    atomic_write_json(Path(request['response']), response)
    return 0 if response['status'] == 'succeeded' else 1


if __name__ == '__main__':
    raise SystemExit(main())
