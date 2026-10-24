"""Explicit GPU selection for community inference; never download dependencies."""
from pathlib import Path
import csv
import io
import json
import os
import subprocess

from .errors import AppError, argument_error
from .policy import require_local_reference


def configure(args, task):
    value = os.environ.get('AEK_COMMUNITY_DEVICE_CONFIG')
    settings = {}
    if value:
        require_local_reference(value, field='community_device_config')
        path = Path(value).expanduser().resolve()
        if not path.is_file() or path.stat().st_size > 65536:
            raise argument_error('本地 GPU/CPU 配置不存在或过大', 'community_device_config')
        settings = json.loads(path.read_text('utf-8-sig')).get(task, {})
    args.pack = args.pack or settings.get('cpu_pack')
    args.gpu_pack = args.gpu_pack or settings.get('gpu_pack')
    args.cuda_library_directory = args.cuda_library_directory or settings.get('cuda_library_directory')
    if not args.pack:
        raise argument_error('需要显式 --pack 或已登记本地 CPU/GPU 配置；不自动下载模型', 'pack')


def inspect():
    try:
        p = subprocess.run(['nvidia-smi', '--query-gpu=index,name,driver_version,memory.total,memory.free,compute_cap',
                            '--format=csv,noheader,nounits'], capture_output=True, text=True, timeout=15,
                           creationflags=subprocess.CREATE_NO_WINDOW)
        if p.returncode:
            return dict(available=False, gpus=[], reason='nvidia_smi_failed')
        gpus = [dict(index=int(r[0]), name=r[1].strip(), driver=r[2].strip(), total_mib=int(r[3]),
                     free_mib=int(r[4]), compute_capability=r[5].strip()) for r in csv.reader(io.StringIO(p.stdout))]
        return dict(available=bool(gpus), gpus=gpus, reason=None if gpus else 'no_nvidia_device')
    except (OSError, ValueError, subprocess.TimeoutExpired):
        return dict(available=False, gpus=[], reason='nvidia_driver_query_unavailable')


def select(requested, gpu_pack, *, minimum_mib=2048, device_index=0):
    if requested == 'cpu':
        return dict(requested='cpu', selected='cpu', fallback_reason=None)
    if not gpu_pack:
        if requested == 'cuda':
            raise AppError('GPU_PACK_REQUIRED', '显式 CUDA 推理需要已安装的 --gpu-pack', exit_code=10)
        return dict(requested=requested, selected='cpu', fallback_reason='gpu_pack_not_supplied')
    require_local_reference(gpu_pack, field='gpu_pack')
    status = inspect()
    gpu = next((g for g in status['gpus'] if g['index'] == device_index), None)
    reason = ('gpu_not_available' if gpu is None else 'insufficient_free_vram' if gpu['free_mib'] < minimum_mib else None)
    if reason:
        if requested == 'cuda':
            raise AppError('GPU_UNAVAILABLE', 'CUDA 显卡不可用或空闲显存不足', exit_code=10, cause=reason)
        return dict(requested=requested, selected='cpu', fallback_reason=reason, gpu=gpu)
    return dict(requested=requested, selected='cuda', fallback_reason=None, gpu=gpu, device_index=device_index,
                minimum_free_mib=minimum_mib, existing_gpu_processes_untouched=True)


def library_directory(value):
    if not value:
        return None
    require_local_reference(value, field='cuda_library_directory')
    path = Path(value).expanduser().resolve()
    if not path.is_dir():
        raise argument_error('CUDA 运行库目录不存在', 'cuda_library_directory')
    return str(path)
