"""Pinned native four-stem HDemucs registration and bounded execution."""
from __future__ import annotations

import json
import math
from pathlib import Path
import shutil
import time

from .artifact_locks import artifact_entry, verification_scope
from .errors import AppError, argument_error
from .media import ffmpeg_path, probe_media
from .policy import require_local_reference
from .job_workspaces import managed_workspace
from .stem_separation_dsp import ROLES
from .utils import assert_id, atomic_write_json, now_iso, run_process, sha256_bytes, sha256_file

ENGINE = 'torchaudio-hdemucs-four-stem-local-v1'
PROTOCOL = 'agent-hdemucs-four-stems-v1'
CONTRACT = 'four_independent_stereo_float_wav_v1'
MAX_SECONDS = 1800
RATE = 44100


def fingerprint(value):
    return 'sha256:'+sha256_bytes(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8'))


def local_file(value, root=None):
    require_local_reference(str(value), field='four-stem local file')
    path = Path(value).expanduser()
    if root and not path.is_absolute(): path = root/path
    for candidate in (path.absolute(), *path.absolute().parents):
        if candidate.is_symlink() or getattr(candidate, 'is_junction', lambda:False)():
            raise argument_error('四轨资源不能穿越链接目录', str(candidate))
    if not path.is_file() or not path.stat().st_size:
        raise AppError('FOUR_STEM_FILE_MISSING', '需要已存在的非空本地文件', exit_code=3, path=str(path))
    return path.resolve()


def settings(*, device='auto', threads=4, segment_seconds=6., overlap=.25):
    if (device not in ('auto', 'cpu', 'cuda') or type(threads) is not int or not 1 <= threads <= 32
            or any(type(v) not in (int,float) or not math.isfinite(v) for v in (segment_seconds,overlap))
            or not 1 <= segment_seconds <= 20 or not 0 <= overlap <= .75):
        raise argument_error('四轨分离要求 auto/cpu/cuda、threads 1..32、segment-seconds 1..20、overlap 0..0.75', 'settings')
    return dict(device=device, threads=threads, segment_seconds=float(segment_seconds), overlap=float(overlap),
                sample_rate=RATE, architecture='torchaudio.models.hdemucs_high', sources=list(ROLES), mixture_projection='none')


def implementation_files():
    return [Path(__file__).with_name(name) for name in ('stem_separation.py', 'stem_separation_worker.py',
        'stem_separation_dsp.py', 'stem_separation_cli.py', 'separation_dsp.py', 'demucs_worker.py',
        'artifact_locks.py', 'community_device.py', 'job_workspaces.py', 'native_process_job.py', 'utils.py', 'project.py')]


def manifest_hash(record):
    return fingerprint({key:record.get(key) for key in ('adapter_id','engine','protocol','output_contract',
        'model_path','model_sha256','executable','executable_sha256','settings','artifacts','rights_ref','network')})


def prepare_adapter(root, *, adapter_id, model_path, executable, evidence, creator, license_spdx,
                    license_url, permitted_uses, verification_status, options=None):
    assert_id(adapter_id, 'adapter_id')
    if verification_status not in ('unverified','verified','restricted'):
        raise argument_error('未知核验状态', 'verification_status')
    model = local_file(model_path,root); python = local_file(executable,root); proof = local_file(evidence,root)
    if model.suffix.lower() not in ('.pt','.pth') or python.suffix.lower() != '.exe' or proof.stat().st_size > 2*1024**2:
        raise argument_error('需要 .pt/.pth、原生 Python .exe 和不超过 2MiB 的本地 evidence', 'adapter')
    with verification_scope():
        entries = [artifact_entry(path,role) for path,role in ((model,'model'),(python,'python'),(proof,'evidence'))]
        entries += [artifact_entry(path,'implementation') for path in implementation_files()]
    record = dict(adapter_id=adapter_id, kind='audio-separation', engine=ENGINE, protocol=PROTOCOL,
        output_contract=CONTRACT, model_path=str(model), model_sha256=entries[0]['sha256'], model_kind='file',
        model_file_count=1, executable=str(python), executable_sha256=entries[1]['sha256'], settings=settings(**(options or {})),
        artifacts=entries, rights_ref='audio_adapter_'+adapter_id, network='disabled', registered_at=now_iso(),
        verification_status=verification_status)
    record['sha256'] = manifest_hash(record)
    rights = dict(asset_id=record['rights_ref'], kind='model-adapter', sha256=record['sha256'],
        source_url='local://audio-adapter/'+adapter_id, source_version=ENGINE, retrieved_at=record['registered_at'],
        creator=creator, license_spdx=license_spdx, license_url=license_url, attribution='',
        permitted_uses=list(dict.fromkeys(permitted_uses)), permitted_channels=[], restrictions=[], derived_from=[],
        evidence=str(proof), verification_status=verification_status,
        verified_by='ai-ad-editor' if verification_status == 'verified' else '', takedown_status='clear',
        notes='Four neural sources; registration does not establish checkpoint licensing, dependency portability or listening acceptance')
    return record, rights


def verify_adapter(record):
    try:
        with verification_scope():
            if (record.get('engine') != ENGINE or record.get('protocol') != PROTOCOL or record.get('output_contract') != CONTRACT
                    or record.get('network') != 'disabled' or record.get('sha256') != manifest_hash(record)
                    or settings(**{k:record['settings'][k] for k in ('device','threads','segment_seconds','overlap')}) != record['settings']):
                raise ValueError('Four-stem adapter manifest invalid')
            expected = [(local_file(record['model_path']),'model'), (local_file(record['executable']),'python')]
            evidence = [entry for entry in record['artifacts'] if entry.get('role') == 'evidence']
            if len(evidence) != 1: raise ValueError('Missing evidence')
            expected += [(local_file(evidence[0]['path']),'evidence')]
            expected += [(path,'implementation') for path in implementation_files()]
            actual = [artifact_entry(path,role) for path,role in expected]
            if (actual != record['artifacts'] or record['model_sha256'] != actual[0]['sha256']
                    or record['executable_sha256'] != actual[1]['sha256']):
                raise ValueError('Four-stem artifact bytes or paths changed')
        return dict(adapter_id=record['adapter_id'], engine=ENGINE, ok=True, network='disabled', findings=[])
    except (AppError, KeyError, ValueError, TypeError, OSError) as exc:
        return dict(adapter_id=record.get('adapter_id'), engine=ENGINE, ok=False, network='disabled',
                    findings=[dict(code='FOUR_STEM_ADAPTER_INTEGRITY_FAILED', message=str(exc))])


def execution(root, *, timeout=600., cancel_file=None, device=None, device_index=0):
    if (type(timeout) not in (int,float) or not math.isfinite(timeout) or not 0 < timeout <= 7200
            or device not in (None,'auto','cpu','cuda') or type(device_index) is not int or not 0 <= device_index <= 31):
        raise argument_error('timeout-seconds 须为 0..7200 正数，device-index 为 0..31', 'execution')
    marker = None
    if cancel_file:
        require_local_reference(str(cancel_file), field='cancel_file')
        marker = Path(cancel_file).expanduser()
        if not marker.is_absolute(): marker = root/marker
    deadline = time.monotonic()+timeout
    remaining(deadline, marker)
    return deadline, marker


def remaining(deadline, marker):
    if marker and marker.exists(): raise AppError('CANCELLED', '四轨分离已取消', exit_code=8, path=str(marker))
    left = deadline-time.monotonic()
    if left <= 0: raise AppError('PROCESS_TIMEOUT', '四轨分离超过总时间预算', exit_code=6, retryable=True)
    return left


def separate(root, source, destinations, *, adapter, sample_rate=RATE, device=None, device_index=0, timeout=600., cancel_file=None):
    from .audio_separation import _validate_sample_rate
    from .community_device import select
    rate = _validate_sample_rate(sample_rate) or RATE
    deadline, marker = execution(root, timeout=timeout, cancel_file=cancel_file, device=device, device_index=device_index)
    with verification_scope():
        if not verify_adapter(adapter)['ok']:
            raise AppError('MODEL_ADAPTER_HASH_INVALID', '四轨模型登记完整性检查失败', exit_code=10)
        source = local_file(source)
        source_entry = artifact_entry(source, 'source')
        if (set(destinations) != set(ROLES) or len({source, *(p.resolve() for p in destinations.values())}) != 5
                or any(p.exists() or p.suffix.lower() != '.wav' for p in destinations.values())):
            raise argument_error('四轨输出必须是四个不同且不存在的 .wav', 'output')
        probe = probe_media(source); duration = float(probe.get('duration_seconds') or 0)
        if not probe.get('audio') or not math.isfinite(duration) or not 0 < duration <= MAX_SECONDS:
            raise argument_error('四轨分离需要有效音频，单次不超过 1800 秒', 'input')
        required = math.ceil((duration+1)*RATE)*8*10+256*1024**2
        if shutil.disk_usage(root).free < required:
            raise AppError('FOUR_STEM_DISK_BUDGET', '四轨分离磁盘余量不足', exit_code=6, cause=str(required))
        decision = select(device or adapter['settings']['device'], adapter['model_path'], minimum_mib=2048, device_index=device_index)
        with managed_workspace(root, 'four-stem-separation') as workspace:
            job = workspace.path; pcm = job/'input.f32'; response = job/'response.json'
            decoded = run_process([ffmpeg_path(),'-nostdin','-hide_banner','-loglevel','error','-protocol_whitelist','file,pipe','-n',
                '-i',str(source),'-vn','-ac','2','-ar',str(RATE),'-f','f32le',str(pcm)], timeout=remaining(deadline,marker), cancel_file=marker)
            if decoded.returncode or not pcm.is_file() or not pcm.stat().st_size or pcm.stat().st_size % 8 or pcm.stat().st_size//8 > MAX_SECONDS*RATE:
                raise AppError('FOUR_STEM_DECODE_FAILED', '四轨输入解码失败或超过预算', exit_code=6, cause=decoded.stderr[-2000:])
            count = pcm.stat().st_size//8
            outputs = {role:job/(role+'.f32') for role in ROLES}
            request = dict(protocol=PROTOCOL, network='disabled', adapter=adapter, input=str(pcm),
                input_sha256='sha256:'+sha256_file(pcm), source_sha256=source_entry['sha256'], samples=count,
                outputs={k:str(v) for k,v in outputs.items()}, response=str(response), runtime_root=str(job/'runtime'),
                device=decision['selected'], device_index=device_index, cancel_file=str(marker) if marker else None)
            request['request_sha256'] = fingerprint(request)
            request_path = job/'request.json'; atomic_write_json(request_path,request)
            completed = run_process([adapter['executable'],'-I','-B','-u','-X','utf8',str(Path(__file__).with_name('stem_separation_worker.py')),str(request_path)],
                                    timeout=remaining(deadline,marker), cancel_file=marker)
            try:
                if response.stat().st_size > 1024**2: raise ValueError('Oversize response')
                payload = json.loads(response.read_text('utf-8'))
                if not isinstance(payload,dict): raise ValueError('Response must be object')
            except (OSError,ValueError) as exc:
                raise AppError('FOUR_STEM_WORKER_FAILED', '四轨进程未返回有效响应', exit_code=6, cause=completed.stderr[-2000:]) from exc
            expected = {k:request[k] for k in ('protocol','request_sha256','input_sha256','source_sha256','samples','device','device_index')}
            if (completed.returncode or any(payload.get(k) != v for k,v in expected.items())
                    or payload.get('status') != 'succeeded' or payload.get('network') != 'disabled'
                    or payload.get('blocked_network_events') != [] or payload.get('adapter_sha256') != adapter['sha256']
                    or set(payload.get('outputs',{})) != set(ROLES)):
                raise AppError('FOUR_STEM_WORKER_FAILED', '四轨进程协议或推理失败', exit_code=6, cause=json.dumps(payload,ensure_ascii=False)[-4000:])
            metrics = payload.get('metrics') or {}
            values = [metrics.get(key) for key in ('normalization_mean','normalization_std','raw_sum_max_abs_error','raw_sum_rms_error','input_rms','input_peak')]
            peaks = metrics.get('peaks') or {}
            if (metrics.get('samples') != count or metrics.get('channels') != 2 or metrics.get('source_order') != list(ROLES)
                    or metrics.get('estimate_method') != 'four_independent_model_sources' or metrics.get('mixture_projection') != 'none'
                    or set(peaks) != set(ROLES) or any(type(v) not in (int,float) or not math.isfinite(v) for v in [*values,*peaks.values()])
                    or metrics['normalization_std'] <= 0 or min(*values[2:],*peaks.values()) < 0):
                raise AppError('FOUR_STEM_OUTPUT_INVALID', '四轨响应信号指标无效', exit_code=6)
            target_samples = max(1,round(count*rate/RATE)); stems = {}
            for role in ROLES:
                source_pcm = outputs[role]; details = payload['outputs'][role]
                if (not source_pcm.is_file() or source_pcm.stat().st_size != count*8 or details.get('bytes') != count*8
                        or details.get('sha256') != 'sha256:'+sha256_file(source_pcm)):
                    raise AppError('FOUR_STEM_OUTPUT_INVALID', '四轨输出字节或摘要不符', exit_code=6, path=role)
                encoded = job/(role+'.wav')
                result = run_process([ffmpeg_path(),'-nostdin','-hide_banner','-loglevel','error','-n','-f','f32le','-ar',str(RATE),'-ac','2',
                    '-i',str(source_pcm),'-af',f'aresample={rate},apad=whole_len={target_samples},atrim=end_sample={target_samples}',
                    '-ar',str(rate),'-c:a','pcm_f32le',str(encoded)], timeout=remaining(deadline,marker), cancel_file=marker)
                output_probe = probe_media(encoded) if result.returncode == 0 else {}
                audio = output_probe.get('audio') or {}
                if (audio.get('channels') != 2 or audio.get('sample_rate') != rate
                        or abs(float(output_probe.get('duration_seconds') or 0)-target_samples/rate) > 2/rate):
                    raise AppError('FOUR_STEM_OUTPUT_INVALID', '四轨 WAV 编码/时长/采样率无效', exit_code=6, path=role)
                # The public probe names the durable artifact, not its removed stage.
                if 'path' in output_probe: output_probe['path'] = str(destinations[role])
                stems[role] = dict(output=str(destinations[role]),role=role,sha256='sha256:'+sha256_file(encoded),
                                   probe=output_probe,samples=target_samples)
            if artifact_entry(source,'source') != source_entry or not verify_adapter(adapter)['ok']:
                raise AppError('FOUR_STEM_INTEGRITY_FAILED', '四轨输入或依赖发生变化', exit_code=10)
            for role in ROLES:
                remaining(deadline,marker)
                destination = destinations[role]; destination.parent.mkdir(parents=True,exist_ok=True)
                # Durable identity/hash intent precedes a same-volume exclusive rename.
                workspace.publish(job/(role+'.wav'), destination)
                if 'sha256:'+sha256_file(destination) != stems[role]['sha256']:
                    raise AppError('FOUR_STEM_OUTPUT_INVALID','四轨复制完整性失败',exit_code=6,path=role)
            remaining(deadline,marker)
            return dict(engine=ENGINE,protocol=PROTOCOL,method='hdemucs-four-stems',network='disabled',
                source=str(source),source_sha256=source_entry['sha256'],adapter_id=adapter['adapter_id'],
                adapter_sha256=adapter['sha256'],checkpoint_sha256=adapter['model_sha256'],stems=stems,worker=payload,
                device_selection=decision,estimated_disk_bytes=required,workspace_id=job.name,
                warnings=[dict(code='FOUR_STEM_MODEL_REVIEW',message='四条均为独立模型估计；原始估计之和未强制等于原音，未独立归一化或限幅。需复核泄漏、伪影、峰值、听感和模型/素材许可。')])
