"""Owned native music jobs, cancellation and independent full-PCM verification."""
import contextlib
from fractions import Fraction
import json
from pathlib import Path
import re
import subprocess
import time

from .artifact_locks import artifact_entry
from .enhancement_pipeline import workspace_bytes
from .lipsync_plan import digest
from .local_music_generation import PROTOCOL, error, prepare_request, recipe, verify_adapter
from .media import ffmpeg_path, ffprobe_path, probe_media
from .native_audio_clock import cancel
from .native_process_job import NativeProcessJob
from .pipeline_diagnostics import Session, _limited_json, SUMMARY_LIMIT
from .utils import atomic_write_json, run_process, sha256_file

PHASES = {'verifying-music-artifacts', 'admitting-music-text', 'loading-music-text', 'encoding-music-request',
          'releasing-music-text', 'admitting-music-diffusion', 'loading-music-diffusion', 'generating-music',
          'releasing-music-diffusion', 'decoding-music-audio', 'encoding-music-audio'}


class MusicDiagnosticSession(Session):
    def __init__(self, root, plan, adapter, operation_id=None):
        super().__init__(root, plan, adapter, operation_id)
        lyrics = plan.get('generation', {}).get('lyrics')
        if lyrics:
            self.literals = (*self.literals, lyrics)

    def read_progress(self):
        value, metadata = _limited_json(self.prepared_directory, 'progress.json', SUMMARY_LIMIT)
        if not isinstance(value, dict):
            return metadata
        if (value.get('phase') not in PHASES or type(value.get('done')) is not int or type(value.get('total')) is not int
                or not 0 <= value['done'] <= value['total'] <= 65536 or value['total'] < 1
                or type(value.get('worker_pid')) is not int or value['worker_pid'] < 1):
            return dict(state='invalid_music_progress')
        return dict(state='read', **value)


def validate_response(response, request):
    try:
        if (not isinstance(response, dict) or response.get('status') != 'succeeded' or response.get('protocol') != PROTOCOL
                or response.get('network') != 'disabled' or response.get('blocked_network_events') != []
                or response.get('request_sha256') != request['request_sha256'] or response.get('adapter_sha256') != request['adapter']['sha256']):
            raise ValueError('Protocol, request or adapter mismatch')
        generation = prepare_request(request['generation'])
        samples = round(generation['duration_seconds'] * 48000)
        if any(type(response[k]) is not int for k in ('sample_rate', 'channels', 'samples', 'output_bytes')):
            raise ValueError('Sample clock must use integers')
        if (response['sample_rate'], response['channels'], response['samples'], response['output_bytes']) != (48000, 2, samples, samples * 8):
            raise ValueError('Native output clock mismatch')
        if any(response[k] is not False for k in ('padded', 'looped', 'resampled', 'normalized', 'service_started', 'shared_queue_touched')):
            raise ValueError('Output was changed or a shared service was used')
        model = response['model']
        if model['neural_backend'] != 'cuda' or model['CPU_fallback'] is not False or model['forwards']['diffusion'] < generation['steps']:
            raise ValueError('CUDA diffusion was not observed')
        for label in ('text', 'vae', 'diffusion'):
            if type(model['forwards'][label]) is not int or model['forwards'][label] < 1 or model['forward_output_devices'][label] != ['cuda:0']:
                raise ValueError('CUDA forward evidence missing: ' + label)
        expected_lm = generation['generate_audio_codes']
        if (type(model['forwards']['language_model']) is not int
                or expected_lm and (model['forwards']['language_model'] < 1 or model['forward_output_devices']['language_model'] != ['cuda:0'])
                or not expected_lm and (model['forwards']['language_model'] != 0 or model['forward_output_devices']['language_model'] != [])):
            raise ValueError('Language model execution does not match the request')
        for key in ('output_PCM_sha256', 'output_sha256'):
            if not re.fullmatch(r'sha256:[0-9a-f]{64}', response[key]):
                raise ValueError('Output digest missing')
        from math import isfinite
        if any(type(response[k]) not in (int, float) or not isfinite(response[k]) or response[k] <= 0 for k in ('output_peak', 'output_rms')):
            raise ValueError('Invalid or silent signal')
    except (ValueError, TypeError, KeyError) as exc:
        raise error('WORKER_RESPONSE', '神经音乐工作进程响应或真实CUDA证据无效', cause=str(exc)) from exc


def execute(root, job, adapter, generation, *, storage_budget_bytes, timeout, cancel_file, operation_id, progress=lambda *_:None):
    work = job.path
    started = time.monotonic()
    def remaining():
        cancel(cancel_file)
        left = timeout - (time.monotonic() - started)
        if left <= 0:
            raise error('TIMEOUT', '神经音乐工作超过总超时预算')
        return left
    request = dict(protocol=PROTOCOL, network='disabled', adapter=adapter, generation=prepare_request(generation),
                   storage_budget_bytes=storage_budget_bytes, timeout_seconds=timeout,
                   cancel_file=str(cancel_file) if cancel_file else None,
                   ffmpeg=artifact_entry(Path(ffmpeg_path()), 'ffmpeg'), ffprobe=artifact_entry(Path(ffprobe_path()), 'ffprobe'))
    request['request_sha256'] = digest(request)
    atomic_write_json(work / 'request.json', request)
    diagnostic = MusicDiagnosticSession(root, request, adapter, operation_id)
    diagnostic.prepare(work, request)
    owned = None
    process = None
    try:
        remaining()
        owned = NativeProcessJob()
        with (work / 'worker.log').open('w+b') as log:
            argv = [adapter['executable'], '-I', '-B', '-u', '-X', 'utf8', str(Path(__file__).with_name('music_generation_worker.py')), str(work / 'request.json')]
            diagnostic.start_failure_role = 'worker'
            process = subprocess.Popen(argv, cwd=work, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=log,
                                       creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0) | owned.creationflags)
            diagnostic.processes.started('worker', process)
            diagnostic.start_failure_role = None
            try:
                owned.attach_and_resume(process)
                diagnostic.stage = 'running'
                last = None
                while process.poll() is None:
                    remaining()
                    diagnostic.observe()
                    if workspace_bytes(work) > storage_budget_bytes:
                        raise error('STORAGE', '神经音乐工作目录超过实际存储预算')
                    with contextlib.suppress(OSError, ValueError, KeyError, TypeError):
                        info = json.loads((work / 'progress.json').read_bytes())
                        value = (info['phase'], info['done'], info['total'])
                        if value != last and value[0] in PHASES and type(value[1]) is int and type(value[2]) is int and 0 <= value[1] <= value[2] and value[2] > 0:
                            progress(*value)
                            last = value
                    time.sleep(.1)
            finally:
                diagnostic.processes.before_cleanup()
                owned.close()
                owned = None
                if process.poll() is None:
                    process.kill()
                process.wait(timeout=10)
                diagnostic.processes.finished()
        cleanup = dict(worker_pid=process.pid, returncode=process.returncode, worker_exited=process.poll() is not None,
                       owner_job_closed=True, process_tree='native-Windows-KILL_ON_JOB_CLOSE-before-worker-code')
        remaining()
        diagnostic.stage = 'validating-response'
        path = work / 'response.json'
        if not path.is_file() or path.stat().st_size > 1024**2:
            raise error('WORKER_RESPONSE', '神经音乐工作进程没有有界响应', returncode=process.returncode)
        response = json.loads(path.read_bytes())
        if process.returncode:
            raise error('WORKER_FAILED', '神经音乐模型执行失败', response=response)
        validate_response(response, request)
        diagnostic.stage = 'verifying-output'
        staged = work / 'generated.wav'
        if not staged.is_file() or staged.stat().st_size != response['output_wav_bytes'] or 'sha256:' + sha256_file(staged) != response['output_sha256']:
            raise error('OUTPUT_CHANGED', '神经音乐输出字节或尺寸改变')
        probe = probe_media(staged)
        stream = next(s for s in probe['streams'] if s['codec_type'] == 'audio')
        if ((stream['codec_name'], int(stream['sample_rate']), int(stream['channels'])) != ('pcm_f32le', 48000, 2)
                or int(stream['duration_ts']) * Fraction(stream['time_base']) * 48000 != response['samples']):
            raise error('OUTPUT_CLOCK', '编码后的原生48000Hz双声道时钟不符')
        decoded = run_process([request['ffmpeg']['path'], '-nostdin', '-v', 'error', '-i', str(staged), '-map', '0:a:0',
                               '-c:a', 'pcm_f32le', '-f', 'hash', '-hash', 'sha256', 'pipe:1'], timeout=remaining(), cancel_file=cancel_file)
        if decoded.returncode or 'sha256:' + decoded.stdout.strip().lower().removeprefix('sha256=') != response['output_PCM_sha256']:
            raise error('ROUNDTRIP', '完整生成PCM与编码后解码结果不一致')
        if not verify_adapter(adapter)['ok'] or any(artifact_entry(Path(request[k]['path']), k) != request[k] for k in ('ffmpeg', 'ffprobe')):
            raise error('ADAPTER_CHANGED', '发布前模型、运行时或媒体工具改变')
        remaining()
        return staged, dict(protocol=PROTOCOL, sha256=response['output_sha256'], probe=probe, worker=response,
                            cleanup=cleanup, complete_PCM_roundtrip_verified=True,
                            recipe=recipe(request['generation'], adapter, samples=response['samples'],
                                          pcm_sha256=response['output_PCM_sha256'], wav_sha256=response['output_sha256']),
                            elapsed_seconds=time.monotonic() - started, natural_quality_accepted=False)
    except BaseException as exc:
        if diagnostic.start_failure_role:
            diagnostic.processes.start_failed(diagnostic.start_failure_role)
        diagnostic.capture(work, exc)
        raise
    finally:
        if owned is not None:
            owned.close()
