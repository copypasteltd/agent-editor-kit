"""Isolated, network-guarded native music worker, without a server or GUI."""
import json
import math
import os
from pathlib import Path
import shutil
import sys
import time
import traceback


def main():
    request_path = Path(sys.argv[1])
    request = json.loads(request_path.read_bytes())
    application = str(Path(__file__).resolve().parents[1])
    sys.path.insert(0, application)
    try:
        import ai_ad_editor
    finally:
        sys.path.remove(application)
    if Path(ai_ad_editor.__file__).resolve() != Path(__file__).resolve().with_name('__init__.py'):
        raise RuntimeError('NATIVE_WORKER_APPLICATION_CHANGED')
    from ai_ad_editor.rvm_worker import install_network_guard
    from ai_ad_editor.artifact_locks import verification_scope, artifact_entry
    from ai_ad_editor.local_music_generation import PROTOCOL, prepare_request, verify_adapter, error
    from ai_ad_editor.lipsync_plan import digest
    from ai_ad_editor.native_audio_clock import cancel
    from ai_ad_editor.utils import atomic_write_json, run_process, sha256_file
    work = request_path.parent
    marker = Path(request['cancel_file']) if request.get('cancel_file') else None
    events = []
    install_network_guard(events)
    started = time.monotonic()
    response = dict(protocol=PROTOCOL, status='failed', network='disabled', blocked_network_events=events)

    def check():
        cancel(marker)

    def phase(name, done=0, total=1):
        check()
        atomic_write_json(work / 'progress.json', dict(phase=name, done=done, total=total, worker_pid=os.getpid()))

    try:
        if request.get('protocol') != PROTOCOL or request.get('network') != 'disabled' or request['request_sha256'] != digest({k:v for k,v in request.items() if k != 'request_sha256'}):
            raise error('REQUEST', '神经音乐请求摘要无效')
        generation = prepare_request(request['generation'])
        if generation != request['generation']:
            raise error('REQUEST', '要求规范化且完整的神经音乐请求')
        with verification_scope():
            phase('verifying-music-artifacts')
            adapter = request['adapter']
            if not verify_adapter(adapter)['ok']:
                raise error('ADAPTER_CHANGED', '神经音乐模型或运行时代码已改变')
            ffmpeg = request['ffmpeg']['path']
            if artifact_entry(Path(ffmpeg), 'ffmpeg') != request['ffmpeg']:
                raise error('MEDIA_TOOL_CHANGED', 'FFmpeg字节已改变')
            for key, name in {'TEMP':'temp', 'TMP':'temp', 'TMPDIR':'temp', 'HF_HOME':'hf',
                              'TORCH_HOME':'torch', 'XDG_CACHE_HOME':'cache', 'CUDA_CACHE_PATH':'cuda',
                              'NUMBA_CACHE_DIR':'numba', 'MPLCONFIGDIR':'mpl'}.items():
                directory = work / 'runtime' / name
                directory.mkdir(parents=True, exist_ok=True)
                os.environ[key] = str(directory)
            os.environ.update(HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', HF_HUB_DISABLE_TELEMETRY='1',
                              DO_NOT_TRACK='1', PYTHONDONTWRITEBYTECODE='1')
            samples = round(generation['duration_seconds'] * 48000)
            estimate = samples * 2 * 4 * 3 + 64 * 1024**2
            if estimate > request['storage_budget_bytes'] or estimate + 64 * 1024**2 > shutil.disk_usage(work).free:
                raise error('STORAGE', '完整原生PCM与WAV输出超过存储预算', estimated_bytes=estimate)
            from ai_ad_editor.music_generation_model import generate
            output, model = generate(adapter, generation, work, phase=phase, check=check)
            import numpy as np
            if output.shape != (samples, 2) or output.dtype != np.float32 or not np.isfinite(output).all():
                raise error('OUTPUT', '模型输出样本、声道或Float32数据无效')
            peak = float(np.abs(output).max())
            rms = float(np.sqrt(np.square(output, dtype=np.float64).mean()))
            if peak <= 1e-8 or not math.isfinite(peak) or not math.isfinite(rms):
                raise error('SILENT', '模型输出静音或非有限音频，不能作为有效生成')
            phase('encoding-music-audio')
            raw = work / 'generated.f32'
            with raw.open('xb') as stream:
                for start in range(0, samples, 65536):
                    check()
                    stream.write(output[start:start + 65536].astype('<f4', copy=False).tobytes())
            del output
            wav = work / 'generated.wav'
            result = run_process([ffmpeg, '-nostdin', '-v', 'error', '-n', '-f', 'f32le', '-ar', '48000', '-ac', '2',
                                  '-i', str(raw), '-map_metadata', '-1', '-c:a', 'pcm_f32le', str(wav)],
                                 timeout=max(1, request['timeout_seconds'] - (time.monotonic() - started)), cancel_file=marker)
            if result.returncode:
                raise error('ENCODE', '神经音乐WAV编码失败', stderr=result.stderr[-2500:])
            if events or not verify_adapter(adapter)['ok']:
                raise error('INTEGRITY', '生成中出现被阻止的网络请求或依赖改变')
            response.update(status='succeeded', request_sha256=request['request_sha256'], adapter_sha256=adapter['sha256'],
                            sample_rate=48000, channels=2, samples=samples, output_bytes=samples * 8,
                            output_PCM_sha256='sha256:' + sha256_file(raw), output_sha256='sha256:' + sha256_file(wav),
                            output_wav_bytes=wav.stat().st_size, output_peak=peak, output_rms=rms, model=model,
                            estimated_storage_bytes=estimate, padded=False, looped=False, resampled=False,
                            normalized=False, service_started=False, shared_queue_touched=False, natural_quality_accepted=False)
    except BaseException as exc:
        response.update(error_type=type(exc).__name__, error=str(exc), traceback=traceback.format_exc()[-7000:])
    response['elapsed_seconds'] = time.monotonic() - started
    atomic_write_json(work / 'response.json', response)
    return 0 if response['status'] == 'succeeded' else 1


if __name__ == '__main__':
    raise SystemExit(main())
