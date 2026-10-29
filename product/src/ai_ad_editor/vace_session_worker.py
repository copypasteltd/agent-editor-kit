"""Owned native resident process. Only one leased inference may execute at once."""
from __future__ import annotations

import copy
import json
import os
from pathlib import Path
import sys
import threading
import time
import uuid


class PredictorCache:
    def __init__(self, identity):
        self.identity = identity; self.predictor = None; self.metadata = None
        self.prompt = None; self.jobs = 0; self.loads = 0; self.torch_configured = False

    def accepts(self, generation):
        from ai_ad_editor.vace_model import prompt_identity
        return self.prompt is None or self.prompt == prompt_identity(generation)

    def predictor_for(self, adapter, generation, progress):
        from ai_ad_editor.vace_model import load_predictor, prompt_identity
        if not self.accepts(generation): raise ValueError('MODEL_SESSION_PROMPT_MISMATCH')
        reused = self.predictor is not None
        if reused:
            self.metadata = self.predictor.begin_generation(generation, progress=progress)
        else:
            self.predictor, self.metadata = load_predictor(adapter['model_path'], adapter['settings'], generation, progress=progress)
            self.prompt = prompt_identity(generation); self.loads += 1
        self.jobs += 1
        self.metadata['resident_model'] = dict(session_id=self.identity, inference_job=self.jobs,
            predictor_loads=self.loads, text_encoder_loads=self.loads, reused=reused,
            weights_read_this_job=not reused, prompt_embeddings_reused=reused, scheduler_reset=True,
            previous_frame_state_reset=True, new_prompt_requires_new_session=True)
        return self.predictor, self.metadata


class Service:
    def __init__(self, config, work, verification):
        self.config = config; self.work = work; self.verification = verification
        self.lock = threading.RLock(); self.shutdown = threading.Event(); self.cache = PredictorCache(config['session_id'])
        self.active = None; self.executing = False; self.job_done = False
        self.completed = 0; self.failed = 0; self.started = time.monotonic(); self.last_idle = self.started
        self.reason = None; self.failed_shutdown = False
        self.state = dict(protocol=config['protocol'], session_id=config['session_id'], pid=os.getpid(), status='ready', live=True,
            adapter_id=config['adapter']['adapter_id'], adapter_sha256=config['adapter']['sha256'], network='disabled',
            transport='authenticated-windows-named-pipe-json-and-raw-bytes', pickle=False,
            idle_seconds=config['idle_seconds'], lifetime_seconds=config['lifetime_seconds'], max_jobs=config['max_jobs'],
            model_loaded=False, completed_jobs=0, failed_jobs=0, artifact_verification=verification.summary())

    def save(self):
        from ai_ad_editor.utils import atomic_write_json
        with self.lock:
            self.state.update(model_loaded=self.cache.predictor is not None, completed_jobs=self.completed, failed_jobs=self.failed,
                              active_lease=self.active is not None, active_inference=self.executing)
            atomic_write_json(self.work / 'state.json', self.state)

    def retire(self, reason, *, failed=False):
        with self.lock:
            if not self.shutdown.is_set(): self.reason = reason; self.failed_shutdown = failed
            self.shutdown.set()

    def acquire(self, connection, request):
        from ai_ad_editor.artifact_locks import locked_attestation
        from ai_ad_editor.model_session import send_json, receive_json
        import math
        with self.lock:
            if self.shutdown.is_set(): raise ValueError('MODEL_SESSION_STOPPING')
            if self.active is not None: raise ValueError('MODEL_SESSION_BUSY')
            if request.get('adapter_sha256') != self.config['adapter']['sha256']: raise ValueError('MODEL_SESSION_ADAPTER_MISMATCH')
            generation = request.get('generation')
            from ai_ad_editor.local_vace import normalize_generation
            if not isinstance(generation, dict) or normalize_generation(**generation) != generation:
                raise ValueError('MODEL_SESSION_GENERATION_INVALID')
            if not self.cache.accepts(generation): raise ValueError('MODEL_SESSION_PROMPT_MISMATCH')
            timeout = request.get('timeout')
            if type(timeout) not in (int, float) or not math.isfinite(timeout) or not 0 < timeout <= 604800:
                raise ValueError('MODEL_SESSION_TIMEOUT_INVALID')
            identity = str(uuid.uuid4())
            self.active = dict(lease_id=identity, generation=copy.deepcopy(generation), deadline=time.monotonic() + timeout)
            self.job_done = False; self.state['status'] = 'leased'; self.save()
        success = False
        try:
            send_json(connection, dict(ok=True, lease_id=identity, artifacts=locked_attestation()))
            release = receive_json(connection, timeout=timeout + 30)
            if release.get('command') != 'release' or release.get('lease_id') != identity:
                raise ValueError('MODEL_SESSION_RELEASE_INVALID')
            success = release.get('success') is True
            with self.lock:
                if self.executing: success = False
                self.active = None; self.last_idle = time.monotonic(); self.state['status'] = 'ready'; self.save()
            send_json(connection, dict(ok=True, released=True, session_retired=not success))
        finally:
            if not success: self.retire('lease-cancelled-or-owner-disconnected', failed=True)
            elif self.completed >= self.config['max_jobs']: self.retire('max-jobs-reached')

    def execute(self, connection, message):
        from ai_ad_editor.model_session import send_json, PipeReader, PipeWriter
        from ai_ad_editor.vace_worker import infer
        from ai_ad_editor.utils import atomic_write_json
        request = message.get('request', {}); descriptor = request.get('model_session', {})
        with self.lock:
            if (self.active is None or self.executing or self.job_done or descriptor.get('lease_id') != self.active['lease_id']
                    or descriptor.get('session_id') != self.config['session_id']
                    or descriptor.get('project_root') != self.config['project_root']
                    or request.get('adapter') != self.config['adapter'] or request.get('generation') != self.active['generation']
                    or request.get('runtime_root') != self.config['runtime_root']):
                raise ValueError('MODEL_SESSION_LEASE_REQUEST_MISMATCH')
            self.executing = True; self.state['status'] = 'running'; self.save()
        send_json(connection, dict(ok=True, status='accepted'))
        started = time.monotonic()
        response = dict(protocol=request.get('protocol'), engine=request.get('engine'), network='disabled', blocked_network_events=[],
            request_sha256=request.get('request_sha256'), adapter_sha256=request['adapter']['sha256'],
            source_sha256=request.get('source', {}).get('sha256'), mask_sha256=request.get('mask', {}).get('sha256'),
            mask_plan_sha256=request.get('mask', {}).get('plan_sha256'), inpainting=request.get('inpainting'),
            generation=request.get('generation'), model_session=descriptor, status='failed')
        if 'outpainting' in request: response['outpainting'] = request['outpainting']
        try:
            infer(request, response, source=PipeReader(connection), sink=PipeWriter(connection), model_cache=self.cache)
            response['artifact_verification'] = self.verification.summary()
        except Exception as exc:
            response['status'] = 'failed'; response['error'] = type(exc).__name__ + ': ' + str(exc)
            from ai_ad_editor.cuda_admission import CudaAdmissionError
            if isinstance(exc, CudaAdmissionError): response['gpu_admission_failure'] = exc.report
        response['elapsed_seconds'] = time.monotonic() - started
        atomic_write_json(Path(request['response']), response)
        with self.lock:
            self.executing = False; self.job_done = True
            if response['status'] == 'succeeded': self.completed += 1
            else: self.failed += 1
            self.state['status'] = 'leased'; self.save()
        connection.send_bytes(b''); send_json(connection, dict(ok=True, response=response))
        if response['status'] != 'succeeded': self.retire('inference-failed', failed=True)

    def handle(self, connection):
        from ai_ad_editor.model_session import PROTOCOL, send_json, receive_json
        from ai_ad_editor.artifact_locks import shared_verification_scope
        action = None; request = {}
        try:
            with shared_verification_scope(self.verification):
                request = receive_json(connection)
                if request.get('protocol') != PROTOCOL: raise ValueError('MODEL_SESSION_PROTOCOL_INVALID')
                action = request.get('command')
                if action == 'status':
                    with self.lock: send_json(connection, dict(ok=True, state=copy.deepcopy(self.state)))
                elif action == 'stop':
                    send_json(connection, dict(ok=True, stopping=True, session_id=self.config['session_id'], pid=os.getpid()))
                    self.retire('explicit-stop')
                elif action == 'acquire': self.acquire(connection, request)
                elif action == 'execute': self.execute(connection, request)
                else: raise ValueError('MODEL_SESSION_COMMAND_INVALID')
        except Exception as exc:
            try: send_json(connection, dict(ok=False, code=str(exc).split(':')[0], message=str(exc)))
            except (OSError, EOFError): pass
            descriptor = request.get('request', {}).get('model_session', {})
            if action == 'execute' and self.active is not None and descriptor.get('lease_id') == self.active['lease_id']:
                self.retire('stream-or-worker-failed', failed=True)
        finally:
            connection.close()


def main():
    application_root = str(Path(__file__).resolve().parents[1])
    sys.path.insert(0, application_root)
    try:
        import ai_ad_editor
    finally:
        sys.path.remove(application_root)
    if Path(ai_ad_editor.__file__).resolve() != Path(__file__).resolve().with_name('__init__.py'):
        raise RuntimeError('NATIVE_WORKER_APPLICATION_CHANGED')
    from multiprocessing.connection import Listener
    from ai_ad_editor.model_session import read_config
    from ai_ad_editor.rvm_worker import install_network_guard
    from ai_ad_editor.artifact_locks import verification_scope
    from ai_ad_editor.local_vace import verify_adapter
    from ai_ad_editor.utils import atomic_write_json
    config_path = Path(sys.argv[1]).resolve(strict=True); work = config_path.parent
    untrusted = json.loads(config_path.read_bytes())
    config = read_config(untrusted['project_root'], untrusted['session_id'])
    if config_path != Path(config['project_root']) / 'cache/model-sessions' / config['session_id'] / 'private.json':
        raise ValueError('MODEL_SESSION_WORKSPACE_MISMATCH')
    events = []; install_network_guard(events)
    os.environ['AI_AD_EDITOR_RUNTIME_DIR'] = config['runtime_root']
    os.environ.update(HF_HUB_OFFLINE='1', TRANSFORMERS_OFFLINE='1', HF_HUB_DISABLE_TELEMETRY='1', TOKENIZERS_PARALLELISM='false')
    try:
        with verification_scope(session=True) as verification:
            if verification is None or not verify_adapter(config['adapter'])['ok']:
                raise ValueError('MODEL_SESSION_ADAPTER_INTEGRITY_FAILED')
            listener = Listener(config['address'], family='AF_PIPE', authkey=bytes.fromhex(config['auth']))
            service = Service(config, work, verification)
            def accept():
                while not service.shutdown.is_set():
                    try: connection = listener.accept()
                    except Exception:
                        if service.shutdown.is_set(): return
                        continue
                    threading.Thread(target=service.handle, args=(connection,), daemon=True).start()
            threading.Thread(target=accept, daemon=True).start(); service.save()
            while not service.shutdown.wait(.1):
                now = time.monotonic()
                with service.lock:
                    if now - service.started >= config['lifetime_seconds']: service.retire('lifetime-budget')
                    elif service.active is not None and now >= service.active['deadline']: service.retire('job-timeout', failed=True)
                    elif service.active is None and now - service.last_idle >= config['idle_seconds']: service.retire('idle-budget')
            with service.lock:
                service.state.update(status='stopped', live=False, stop_reason=service.reason, process_exit_releases_gpu=True,
                    active_task_interrupted=service.executing, blocked_network_events=events)
                service.save()
            # CUDA work can be blocked in a native call. Terminate this owned
            # process, never any other GPU process; the OS releases all handles.
            os._exit(1 if service.failed_shutdown else 0)
    except Exception as exc:
        atomic_write_json(work / 'state.json', dict(protocol=config['protocol'], session_id=config['session_id'],
            status='failed', live=False, error=type(exc).__name__ + ': ' + str(exc)))
        raise


if __name__ == '__main__': main()
