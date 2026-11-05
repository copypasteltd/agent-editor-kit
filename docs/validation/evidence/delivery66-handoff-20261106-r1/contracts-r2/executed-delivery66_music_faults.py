"""Actual native music failure cases through the staged PowerShell Skill.

No worker/model mocks or patched product functions. Cancellation waits for a
real diffusion callback; timeout uses the product deadline; publication failure
is an exclusive foreign output file created only inside a fresh harness project.
"""
from __future__ import annotations

import argparse
import importlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

import delivery66_handoff as handoff
from run_delivery66_native import process_identity, same_process


def observe(project):
    jobs = sorted((project / 'cache/managed-jobs').glob('job-*'))
    handoff.require(len(jobs) <= 16, 'Unexpected managed-job count in a fresh case')
    result = []
    for job in jobs:
        if not (job / 'job.json').is_file():
            continue
        try:
            identity = handoff.load(job / 'job.json')
            if identity.get('kind') != 'music-generation':
                continue
            progress = handoff.load(job / 'progress.json', 16 * 1024) if (job / 'progress.json').is_file() else None
            result.append((job, progress))
        except (FileNotFoundError, json.JSONDecodeError):
            continue  # Files may be atomically replaced or retired between polls.
    return result


def case(context, out, work, name, timeout_seconds, maximum_seconds):
    prefix = handoff.ps(context['home'])
    case_out, folder = out / name, work / name
    case_out.mkdir()
    folder.mkdir()
    package = handoff.load(handoff.ROUND / ('package-replay-' + context['args'].package_run) / 'verification.json')
    music = handoff.load(handoff.ROUND / ('native-music-' + context['args'].music_run) / 'verification.json')
    project = folder / 'project'
    handoff.execute(case_out, 'import', [*prefix, 'convert', 'import', '--input', package['project_package'], '--output', project], cli=True)
    registry = handoff.execute(case_out, 'adapters', [*prefix, 'music', 'generator-adapter', 'list', '--project', project], cli=True)['data']
    adapter = next(row for row in registry['adapters'] if row['sha256'] == music['adapter_sha256'])
    inspected = handoff.execute(case_out, 'adapter-inspect', [*prefix, 'music', 'generator-adapter', 'inspect',
        '--project', project, '--adapter-id', adapter['adapter_id']], cli=True)['data']
    handoff.require(inspected['verification']['ok'] is True, 'Imported project cannot verify the actual adapter')
    before = {path.name: handoff.sha(path) for path in project.glob('*.json')}
    request = Path(music['request_file']['path'])
    handoff.require(handoff.sha(request) == music['request_file']['sha256'], 'Actual generation request changed')
    asset_id = 'fault_' + name.replace('-', '_')
    marker, output = folder / 'cancel.marker', project / 'assets/derived' / (asset_id + '.wav')
    sentinel = b'agent-editor-kit-owned-publication-conflict-case\n'
    command = [*prefix, 'music', 'generate', '--project', project, '--adapter-id', adapter['adapter_id'],
        '--input', request, '--new-asset-id', asset_id, '--cancel-file', marker,
        '--timeout-seconds', str(timeout_seconds if name == 'timeout' else 3600)]
    native = importlib.import_module('ai_ad_editor.native_process_job').NativeProcessJob()
    worker, history, copied_response = None, [], None
    injected, forced_cleanup = False, False
    started = time.monotonic()
    env = dict(os.environ, TEMP=str(folder), TMP=str(folder), TMPDIR=str(folder), PYTHONDONTWRITEBYTECODE='1')
    process = None
    try:
        with (case_out / 'generate.stdout').open('xb') as stdout, (case_out / 'generate.stderr').open('xb') as stderr:
            process = subprocess.Popen(list(map(str, command)), cwd=handoff.ROOT, env=env,
                stdin=subprocess.DEVNULL, stdout=stdout, stderr=stderr,
                creationflags=subprocess.CREATE_NO_WINDOW | native.creationflags)
            native.attach_and_resume(process)
            handoff.save(case_out / 'owner.json', dict(root=process_identity(process.pid), command=list(map(str, command))))
            while process.poll() is None:
                handoff.require(time.monotonic() - started <= maximum_seconds, 'Harness deadline exceeded; case is not accepted')
                for job, progress in observe(project):
                    if progress:
                        if worker is None:
                            worker = process_identity(progress['worker_pid'])
                            handoff.require(worker is not None and Path(worker['executable']).resolve()
                                == Path(adapter['executable']).resolve(), 'Unexpected native worker identity')
                        handoff.require(progress['worker_pid'] == worker['pid'], 'Worker identity changed inside a case')
                        point = {key: progress[key] for key in ('phase', 'done', 'total')}
                        if not history or history[-1] != point:
                            history.append(point)
                            handoff.require(len(history) <= 128, 'Progress history budget exceeded')
                            handoff.save(case_out / 'observed-progress.json', dict(worker=worker, history=history))
                        if not injected and progress['phase'] == 'generating-music' and progress['done'] >= 1:
                            if name == 'cancel':
                                with marker.open('xb') as stream:
                                    stream.write(b'cancel actual diffusion\n')
                                injected = True
                            elif name == 'publication-conflict':
                                output.parent.mkdir(parents=True, exist_ok=True)
                                with output.open('xb') as stream:
                                    stream.write(sentinel)
                                    stream.flush()
                                    os.fsync(stream.fileno())
                                injected = True
                    response_path = job / 'response.json'
                    if name == 'publication-conflict' and copied_response is None and response_path.is_file():
                        response = handoff.load(response_path, 1024**2)
                        if response.get('status') == 'succeeded':
                            wav = job / 'generated.wav'
                            handoff.require(wav.is_file() and wav.stat().st_size == response['output_wav_bytes']
                                and 'sha256:' + handoff.sha(wav) == response['output_sha256'], 'Worker WAV does not match its response')
                            shutil.copyfile(wav, folder / 'internal-generated.wav')
                            copied_response = response
                            handoff.save(case_out / 'actual-worker-response.json', response)
                time.sleep(.25)
            exit_code = process.wait(timeout=10)
        worker_exited_before_harness_cleanup = worker is not None and not same_process(worker)
    finally:
        if process is not None and process.poll() is None:
            forced_cleanup = True
            if not marker.exists():
                marker.write_bytes(b'harness failure: request owned cancellation\n')
        native.close()  # Only this newly owned native job, never numeric PID traversal.
        if process is not None:
            process.wait(timeout=15)
    handoff.require(not forced_cleanup and exit_code != 0, 'The product must reach its own failure terminal')
    envelope = handoff.load(case_out / 'generate.stdout')
    handoff.require(envelope.get('ok') is False and envelope['provenance']['cli_version'] == handoff.VERSION
                    and envelope.get('status') == 'failed', 'Failure must be a structured installed CLI response')
    codes = [row['code'] for row in envelope['errors']]
    if name == 'cancel':
        handoff.require(injected and 'CANCELLED' in codes, 'Cancellation did not follow an actual diffusion callback')
    elif name == 'timeout':
        handoff.require(worker is not None and history and any(code.endswith('_TIMEOUT') for code in codes),
                        'No actual native-worker timeout was observed')
    else:
        handoff.require(injected and 'MUSIC_GENERATION_OUTPUT_CONFLICT' in codes and copied_response is not None,
                        'Actual inference must finish and the exclusive output conflict must be reported')
        model = copied_response['model']
        handoff.require(model['neural_backend'] == 'cuda' and model['CPU_fallback'] is False
            and set(model['forwards']) == {'text', 'language_model', 'diffusion', 'vae'}
            and all(type(count) is int and count > 0 for count in model['forwards'].values())
            and all(model['forward_output_devices'][key] == ['cuda:0'] for key in model['forwards']),
            'Publication fault lacks actual four-component CUDA evidence')
        ffmpeg = importlib.import_module('ai_ad_editor.media').ffmpeg_path()
        pcm = handoff.execute(case_out, 'independent-full-PCM', [ffmpeg, '-nostdin', '-v', 'error',
            '-i', folder / 'internal-generated.wav', '-map', '0:a:0', '-vn', '-c:a', 'pcm_f32le',
            '-f', 'hash', '-hash', 'sha256', 'pipe:1'])
        handoff.require('sha256:' + pcm.decode().strip().split('=', 1)[1].lower()
                        == copied_response['output_PCM_sha256'], 'Full generated PCM mismatch')
    handoff.require(worker_exited_before_harness_cleanup, 'The product left its native worker alive')
    handoff.require(before == {path.name: handoff.sha(path) for path in project.glob('*.json')}, 'Failure changed project metadata')
    handoff.require(not any(row['id'] == asset_id for row in handoff.load(project / 'project.json')['assets']), 'Failed asset was registered')
    handoff.require(not list((project / 'cache/managed-jobs').glob('job-*')), 'Owned job workspace was not cleaned')
    if name == 'publication-conflict':
        handoff.require(output.read_bytes() == sentinel, 'Foreign output was overwritten or deleted')
    else:
        handoff.require(not output.exists(), 'Failed generation left a public output')
    row = dict(passed=True, case=name, exit_code=exit_code, error_codes=codes, worker_identity=worker,
        elapsed_seconds=time.monotonic() - started, progress_history=history,
        diffusion_callback_observed=any(point['phase'] == 'generating-music' and point['done'] >= 1 for point in history),
        worker_exited_before_harness_cleanup=True, metadata_unchanged=True, failed_asset_not_registered=True,
        managed_workspace_cleaned=True, foreign_output_preserved=name == 'publication-conflict',
        model_functions_mocked=False, product_code_patched=False)
    handoff.save(case_out / 'verification.json', row)
    return row


def main():
    parser = handoff.arguments(argparse.ArgumentParser(description=__doc__))
    parser.add_argument('--timeout-seconds', type=float, default=120)
    parser.add_argument('--maximum-case-seconds', type=float, default=5200)
    args = parser.parse_args()
    handoff.require(os.name == 'nt' and sys.dont_write_bytecode and 10 <= args.timeout_seconds <= 600
                    and 3600 <= args.maximum_case_seconds <= 10800, 'Use native bounded failure budgets')
    context = handoff.ready(args)
    context['args'] = args
    out = handoff.begin('music-faults', args.run)
    work = handoff.local(handoff.LOCAL / ('faults-' + args.run))
    handoff.require(not work.exists(), 'Preserve previous actual failure projects')
    work.mkdir(parents=True)
    rows = {}
    try:
        for name in ('cancel', 'timeout', 'publication-conflict'):
            rows[name] = case(context, out, work, name, args.timeout_seconds, args.maximum_case_seconds)
        handoff.source_unchanged(context['freeze'])
        handoff.require(handoff.guards_equal(context['freeze']['formal_guard']), 'Actual faults changed formal entry')
        handoff.save(out / 'verification.json', dict(status='passed', cli_version=handoff.VERSION,
            application_files=context['candidate']['application_files'], skill_files=context['staged']['skill_files'],
            cases=rows, actual_PowerShell_entry=True, source_fallback=False, model_functions_mocked=False,
            formal_activation=False, human_listening=False, generated_audio_publication_approved=False))
    except BaseException as exc:
        handoff.save(out / 'verification.json', dict(status='failed', cli_version=handoff.VERSION,
            completed_cases=rows, error=repr(exc), formal_activation=False))
        raise


if __name__ == '__main__':
    main()
