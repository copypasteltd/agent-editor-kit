"""Isolated local SAM2 worker; binary RGBA pipes and explicit prompt events."""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path


def prune_session(session, index: int, window: int) -> None:
    # Streaming forward uses explicit frame_idx. No old decoded raster is needed.
    if session.processed_frames is not None:
        for key in list(session.processed_frames):
            if key != index:
                del session.processed_frames[key]
    for outputs in session.output_dict_per_obj.values():
        recent = outputs['non_cond_frame_outputs']
        for key in list(recent):
            if key < index - window + 1:
                del recent[key]
    for history in session.frames_tracked_per_obj.values():
        for key in list(history):
            if key < index - window + 1:
                del history[key]


def session_state_bytes(session, torch) -> int:
    storages = set()
    def visit(value):
        if torch.is_tensor(value):
            storage = value.untyped_storage()
            storages.add((str(value.device), storage.data_ptr(), storage.nbytes()))
        elif isinstance(value, dict):
            for child in value.values():
                visit(child)
        elif isinstance(value, (list, tuple)):
            for child in value:
                visit(child)
    for name in ('processed_frames', 'point_inputs_per_obj', 'mask_inputs_per_obj', 'output_dict_per_obj'):
        visit(getattr(session, name))
    visit(session.cache._vision_features)
    return sum(n for _, _, n in storages)


def infer(request: dict, response: dict) -> None:
    from ai_ad_editor.local_matting import request_hash
    from ai_ad_editor.local_segmentation import SEGMENTATION_ENGINE, SEGMENTATION_PROTOCOL, normalize_prompts, verify_adapter, verify_prompt_source
    from ai_ad_editor.runtime import configure_local_runtime
    from ai_ad_editor.segmentation_frames import process_frames
    from ai_ad_editor.utils import atomic_write_json, sha256_file
    if request.get('engine') != SEGMENTATION_ENGINE or request.get('protocol') != SEGMENTATION_PROTOCOL or request.get('network') != 'disabled' or request_hash(request) != request.get('request_sha256'):
        raise ValueError('SEGMENTATION_REQUEST_INVALID')
    adapter, prompts = request['adapter'], request['prompt_plan']
    if not verify_adapter(adapter)['ok'] or not verify_prompt_source(request):
        raise ValueError('SEGMENTATION_INPUT_INTEGRITY_FAILED')
    canonical = normalize_prompts({k: prompts[k] for k in ('version', 'coordinate_space', 'frames')}, frames=request['video']['frames'], object_ids=prompts['object_ids'], mask_mode=prompts['mask_mode'], threshold=prompts['logit_threshold'])
    if canonical != prompts:
        raise ValueError('SEGMENTATION_PROMPT_PLAN_INVALID')
    os.environ['AI_AD_EDITOR_RUNTIME_DIR'] = request['runtime_root']
    configure_local_runtime()
    os.environ['HF_HUB_DISABLE_PROGRESS_BARS'] = '1'
    import numpy as np
    import torch
    import transformers
    from transformers import Sam2VideoModel, Sam2VideoProcessor
    device = adapter['settings']['device']
    if device == 'cuda' and not torch.cuda.is_available():
        raise ValueError('SEGMENTATION_CUDA_UNAVAILABLE_NO_FALLBACK')
    torch.set_num_threads(adapter['settings']['threads'])
    torch.set_num_interop_threads(1)
    if device == 'cuda':
        torch.backends.cuda.matmul.allow_tf32 = False
        torch.backends.cudnn.allow_tf32 = False
        torch.cuda.reset_peak_memory_stats()
    model, loading = Sam2VideoModel.from_pretrained(adapter['model_path'], local_files_only=True, trust_remote_code=False, use_safetensors=True, dtype=torch.float32, output_loading_info=True)
    if any(loading.get(k) for k in ('missing_keys', 'unexpected_keys', 'mismatched_keys', 'error_msgs')):
        raise ValueError('SEGMENTATION_MODEL_LOADING_INCOMPLETE')
    model = model.to(device).eval()
    if any(p.device.type != device or p.is_floating_point() and p.dtype != torch.float32 for p in model.parameters()):
        raise ValueError('SEGMENTATION_DEVICE_OR_PRECISION_MISMATCH')
    processor = Sam2VideoProcessor.from_pretrained(adapter['model_path'], local_files_only=True, trust_remote_code=False)
    window = max(model.config.num_maskmem, model.config.max_object_pointers_in_encoder)
    session = None
    def new_session():
        return processor.init_video_session(inference_device=device, inference_state_device='cpu', video_storage_device='cpu', dtype=torch.float32, max_vision_features_cache_size=1)
    def predict(rgb, index, event):
        nonlocal session
        if session is None or event and event['reset']:
            session = new_session()
        inputs = processor(images=np.ascontiguousarray(rgb), return_tensors='pt').to(device)
        if event:
            ids, points, labels = [], [], []
            h, w = rgb.shape[:2]
            for item in event['objects']:
                ids.append(item['object_id'])
                xy, lab = [], []
                # SAM2 represents box corners using its native prompt labels 2/3.
                # A single batched call preserves all object updates; sequential
                # add_inputs calls overwrite obj_with_new_inputs in Transformers.
                if item['box'] is not None:
                    x1, y1, x2, y2 = item['box']
                    xy.extend([[x1 * w, y1 * h], [x2 * w, y2 * h]])
                    lab.extend([2, 3])
                xy.extend([[min(w - 1, p['x'] * w), min(h - 1, p['y'] * h)] for p in item['points']])
                lab.extend([p['label'] for p in item['points']])
                points.append(xy); labels.append(lab)
            processor.add_inputs_to_inference_session(inference_session=session, frame_idx=index, obj_ids=ids, input_points=[points], input_labels=[labels], original_size=inputs.original_sizes[0], clear_old_inputs=True)
        with torch.inference_mode():
            output = model(inference_session=session, frame=inputs.pixel_values[0], frame_idx=index)
            masks = processor.post_process_masks([output.pred_masks], original_sizes=inputs.original_sizes, binarize=False)[0]
        if not torch.isfinite(output.object_score_logits).all() or masks.shape != (len(session.obj_ids), 1, rgb.shape[0], rgb.shape[1]):
            raise ValueError('SEGMENTATION_OUTPUT_INVALID')
        prune_session(session, index, window)
        state_bytes = session_state_bytes(session, torch)
        return masks[:, 0].detach().cpu().float().numpy(), list(session.obj_ids), state_bytes
    last_progress = 0.
    def progress(frame):
        nonlocal last_progress
        if frame == request['video']['frames'] or time.monotonic() - last_progress >= .5:
            atomic_write_json(Path(request['progress']), {'frames': frame})
            last_progress = time.monotonic()
    info = request['video']
    metrics = process_frames(sys.stdin.buffer, sys.stdout.buffer, width=info['width'], height=info['height'], frames=info['frames'], prompts=prompts,
                             infer=predict, state_budget=adapter['settings']['state_budget_bytes'], progress=progress)
    if not verify_adapter(adapter)['ok'] or not verify_prompt_source(request) or 'sha256:' + sha256_file(Path(request['source']['path'])) != request['source']['sha256']:
        raise ValueError('SEGMENTATION_INPUT_CHANGED_DURING_INFERENCE')
    response.update(status='succeeded', metrics=metrics, prompt_sha256=prompts['sha256'], object_ids=prompts['object_ids'], mask_mode=prompts['mask_mode'], providers=['torch-' + device],
                    versions={'python': sys.version.split()[0], 'torch': torch.__version__, 'transformers': transformers.__version__, 'numpy': np.__version__},
                    memory_window_frames=window, cached_rasters=len(session.processed_frames),
                    cuda_peak_allocated_bytes=torch.cuda.max_memory_allocated() if device == 'cuda' else None)


def main() -> int:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from ai_ad_editor.rvm_worker import install_network_guard
    request = json.loads(Path(sys.argv[1]).read_text(encoding='utf-8'))
    events = []
    response = {'protocol': request.get('protocol'), 'engine': request.get('engine'), 'network': 'disabled', 'blocked_network_events': events,
                'request_sha256': request.get('request_sha256'), 'adapter_sha256': request.get('adapter', {}).get('sha256'), 'source_sha256': request.get('source', {}).get('sha256'), 'status': 'failed'}
    install_network_guard(events)
    started = time.monotonic()
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
