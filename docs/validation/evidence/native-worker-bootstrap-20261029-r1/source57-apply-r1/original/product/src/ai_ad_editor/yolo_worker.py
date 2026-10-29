"""Isolated Windows ONNX/FFmpeg worker; no Ultralytics/cloud runtime."""
from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from pathlib import Path


def install_network_guard(events: list[str]) -> None:
    import socket
    socket.has_ipv6 = False
    def audit(event: str, args: tuple) -> None:
        if event in {'socket.connect','socket.connect_ex','socket.bind','socket.getaddrinfo','socket.gethostbyname','socket.gethostbyaddr','socket.sendto','urllib.Request','http.client.connect'}:
            events.append(event)
            raise RuntimeError('VISION_NETWORK_DISABLED: '+event)
    sys.addaudithook(audit)


def windows_job():
    """Kill the decoder if its owning worker is killed by the parent timeout."""
    import ctypes
    from ctypes import wintypes as w
    if os.name != 'nt':
        raise RuntimeError('VISION_NATIVE_WINDOWS_REQUIRED')
    class Basic(ctypes.Structure):
        _fields_ = [('process_time', ctypes.c_int64), ('job_time', ctypes.c_int64), ('flags', w.DWORD), ('min_ws', ctypes.c_size_t), ('max_ws', ctypes.c_size_t), ('active', w.DWORD), ('affinity', ctypes.c_size_t), ('priority', w.DWORD), ('scheduling', w.DWORD)]
    class IO(ctypes.Structure):
        _fields_ = [(name, ctypes.c_uint64) for name in ('read_ops','write_ops','other_ops','read_bytes','write_bytes','other_bytes')]
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
    info = Extended()
    info.basic.flags = 0x2000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE
    if not kernel.SetInformationJobObject(handle, 9, ctypes.byref(info), ctypes.sizeof(info)):
        error = ctypes.get_last_error()
        kernel.CloseHandle(handle)
        raise ctypes.WinError(error)
    return kernel, handle


def reject_external_tensors(message, onnx) -> None:
    """Inspect nested graphs/attributes before ORT may resolve external data."""
    if isinstance(message, onnx.TensorProto) and (message.external_data or message.data_location == onnx.TensorProto.EXTERNAL):
        raise ValueError('VISION_ONNX_EXTERNAL_DATA_UNSUPPORTED')
    if isinstance(message, onnx.NodeProto) and message.domain not in {'', 'ai.onnx'}:
        raise ValueError('VISION_ONNX_CUSTOM_DOMAIN_UNSUPPORTED')
    for field, value in message.ListFields():
        if field.message_type is not None:
            for child in value if field.is_repeated else [value]:
                reject_external_tensors(child, onnx)


def infer(request: dict, response: dict) -> None:
    from ai_ad_editor.local_vision import YOLO_ENGINE, YOLO_PROTOCOL, request_hash, verify_adapter
    from ai_ad_editor.utils import sha256_file
    from ai_ad_editor.vision_tracker import MotionTracker, decode_detections
    if request.get('engine') != YOLO_ENGINE or request.get('protocol') != YOLO_PROTOCOL or request.get('network') != 'disabled' or request_hash(request) != request.get('request_sha256'):
        raise ValueError('VISION_REQUEST_INVALID')
    native = request['native']
    adapter, video = native['adapter'], native['video']
    if not verify_adapter(adapter)['ok']:
        raise ValueError('VISION_ADAPTER_INTEGRITY_FAILED')
    source, ffmpeg = Path(request['source']['path']), Path(native['ffmpeg']['path'])
    def verify_inputs():
        if 'sha256:'+sha256_file(source) != request['source']['sha256'] or 'sha256:'+sha256_file(ffmpeg) != native['ffmpeg']['sha256']:
            raise ValueError('VISION_INPUT_HASH_MISMATCH')
    verify_inputs()
    import numpy as np
    import onnx
    import onnxruntime as ort
    ort.disable_telemetry_events()
    from PIL import Image
    import PIL
    import subprocess
    graph = onnx.load(adapter['model_path'], load_external_data=False)
    reject_external_tensors(graph, onnx)
    del graph
    config = adapter['settings']
    options = ort.SessionOptions()
    options.intra_op_num_threads, options.inter_op_num_threads = config['threads'], 1
    options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
    session = ort.InferenceSession(adapter['model_path'], sess_options=options, providers=['CPUExecutionProvider'])
    import ast
    names = ast.literal_eval(session.get_modelmeta().custom_metadata_map.get('names', '{}'))
    coco = 'person|bicycle|car|motorcycle|airplane|bus|train|truck|boat|traffic light|fire hydrant|stop sign|parking meter|bench|bird|cat|dog|horse|sheep|cow|elephant|bear|zebra|giraffe|backpack|umbrella|handbag|tie|suitcase|frisbee|skis|snowboard|sports ball|kite|baseball bat|baseball glove|skateboard|surfboard|tennis racket|bottle|wine glass|cup|fork|knife|spoon|bowl|banana|apple|sandwich|orange|broccoli|carrot|hot dog|pizza|donut|cake|chair|couch|potted plant|bed|dining table|toilet|tv|laptop|mouse|remote|keyboard|cell phone|microwave|oven|toaster|sink|refrigerator|book|clock|vase|scissors|teddy bear|hair drier|toothbrush'.split('|')
    if not isinstance(names, dict) or names != dict(enumerate(coco)):
        raise ValueError('VISION_COCO_CLASS_METADATA_UNSUPPORTED')
    inputs, outputs = session.get_inputs(), session.get_outputs()
    if len(inputs) != 1 or inputs[0].type != 'tensor(float)' or inputs[0].shape != [1,3,640,640] or len(outputs) != 1 or outputs[0].type != 'tensor(float)' or len(outputs[0].shape) != 3 or outputs[0].shape[0] != 1 or outputs[0].shape[-1] != 6 or not isinstance(outputs[0].shape[1], int) or not 1 <= outputs[0].shape[1] <= 300 or session.get_providers() != ['CPUExecutionProvider']:
        raise ValueError('VISION_YOLOV10_CONTRACT_UNSUPPORTED')
    tracker = MotionTracker(confidence=config['confidence'], match_iou=config['match_iou'], max_gap_seconds=config['max_gap_seconds'], max_objects=request['limits']['max_objects'])
    dw, dh = video['decode_width'], video['decode_height']
    ratio = min(640/dw, 640/dh)
    resized = max(1, round(dw*ratio)), max(1, round(dh*ratio))
    padding = (640-resized[0])//2, (640-resized[1])//2
    start, end = request['range']['start_seconds'], request['range']['end_seconds']
    interval, expected = video['sample_interval_seconds'], video['expected_samples']
    command = [str(ffmpeg), '-nostdin', '-hide_banner', '-loglevel', 'error', '-protocol_whitelist', 'file,pipe', '-noautorotate', '-ss', str(start), '-i', str(source), '-t', str(end-start), '-map', '0:v:0', '-an', '-sn', '-dn', '-vf', f'setpts=PTS-STARTPTS,fps={1/interval:.12f}:start_time=0:round=near:eof_action=pass,scale={dw}:{dh}', '-frames:v', str(expected), '-pix_fmt', 'rgb24', '-f', 'rawvideo', 'pipe:1']
    sampled, detected_frames = 0, 0
    kernel, job = windows_job()
    process = None
    try:
        with tempfile.TemporaryFile() as errors:
            process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=errors, stdin=subprocess.DEVNULL, creationflags=subprocess.CREATE_NO_WINDOW)
            if not kernel.AssignProcessToJobObject(job, int(process._handle)):
                raise OSError('VISION_DECODER_JOB_ASSIGNMENT_FAILED')
            while sampled < expected:
                raw = process.stdout.read(dw*dh*3)
                if not raw:
                    break
                if len(raw) != dw*dh*3:
                    raise ValueError('VISION_DECODER_PARTIAL_FRAME')
                frame = Image.frombytes('RGB', (dw, dh), raw)
                canvas = Image.new('RGB', (640,640), (114,114,114))
                canvas.paste(frame.resize(resized, Image.Resampling.BILINEAR), padding)
                tensor = np.asarray(canvas, dtype=np.float32).transpose(2,0,1)[None] / np.float32(255)
                rows = session.run([outputs[0].name], {inputs[0].name: tensor})[0]
                if rows.shape != (1,outputs[0].shape[1],6):
                    raise ValueError('VISION_YOLO_OUTPUT_SHAPE_CHANGED')
                detections = decode_detections(rows[0], dw, dh, resized, padding, threshold=config['low_confidence'], classes=config['class_ids'], roi=request['roi'])
                at = start + sampled*interval
                tracker.update(detections, at)
                sampled += 1
                detected_frames += bool(detections)
            process.stdout.close()
            code = process.wait(timeout=30)
            if code:
                errors.seek(0)
                raise RuntimeError('VISION_DECODER_FAILED: '+errors.read(2000).decode('utf-8', errors='replace'))
    finally:
        kernel.CloseHandle(job)
        if process is not None:
            if process.poll() is None:
                process.kill()
            process.wait(timeout=30)
            if process.stdout is not None:
                process.stdout.close()
    if sampled < max(1, expected-1):
        raise ValueError('VISION_SAMPLING_INCOMPLETE')
    if not tracker.tracks:
        raise ValueError('TRACK_OBJECT_NOT_FOUND')
    verify_inputs()
    if not verify_adapter(adapter)['ok']:
        raise ValueError('VISION_ADAPTER_CHANGED_DURING_INFERENCE')
    if response['blocked_network_events']:
        raise RuntimeError('VISION_NETWORK_ATTEMPT_REJECTED')
    objects = []
    for track in tracker.tracks:
        objects.append({'object_id': track['object_id'], 'label': coco[track['class_id']], 'frames': [{k:round(v,9) if isinstance(v,float) else v for k,v in frame.items() if k != 'class_id'} for frame in track['frames']], 'metadata': {'class_id': track['class_id'], 'observations': len(track['frames']), 'max_observation_gap_seconds': round(track['max_observation_gap_seconds'],6)}})
    response.update({'status':'ok', 'engine':YOLO_ENGINE, 'request_sha256':request['request_sha256'], 'adapter_sha256':adapter['sha256'], 'source_sha256':request['source']['sha256'], 'objects':objects, 'range':request['range'], 'metadata': {'sampled_frames':sampled, 'detected_frames':detected_frames, 'observation_count':tracker.observations, 'video':video, 'device':'cpu', 'providers':session.get_providers(), 'onnxruntime_telemetry_disabled':True, 'settings':config, 'identity_model':'motion-only-no-appearance-reid', 'missing_observations':'not_fabricated; editor_interpolates_between_observations', 'last_sample_missing': sampled < expected, 'versions':{'python':sys.version.split()[0], 'numpy':np.__version__, 'onnx':onnx.__version__, 'onnxruntime':ort.__version__, 'pillow':PIL.__version__}}})


def main() -> int:
    response = {'protocol':'agent-video-object-tracking-v2', 'status':'failed', 'network':'disabled', 'blocked_network_events':[]}
    started = time.monotonic()
    try:
        request = json.loads(sys.stdin.read(2*1024*1024))
        install_network_guard(response['blocked_network_events'])
        runtime = Path(request['native']['runtime_root']).resolve()
        for key in ('TEMP','TMP','TMPDIR','XDG_CACHE_HOME'):
            os.environ[key] = str(runtime/'temp')
        (runtime/'temp').mkdir(parents=True, exist_ok=True)
        tempfile.tempdir = str(runtime/'temp')
        sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
        infer(request, response)
    except Exception as exc:
        response.update({'status':'failed', 'error_type':type(exc).__name__, 'message':str(exc)[:3000]})
    response['elapsed_seconds'] = round(time.monotonic()-started,3)
    payload = json.dumps(response, ensure_ascii=True, allow_nan=False)
    if len(payload) > 10*1024*1024:
        payload = json.dumps({'protocol':response['protocol'], 'status':'failed', 'message':'VISION_OUTPUT_LIMIT_EXCEEDED'})
    print(payload)
    return 0 if response['status'] == 'ok' else 1


if __name__ == '__main__':
    raise SystemExit(main())
