"""One paired complete native-4K CPU/GPU render; no extrapolated throughput."""
import argparse
import ctypes
from ctypes import wintypes
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT/'docs/validation/evidence/float-gpu-20261026-r1'
OLD = ROOT/'local/agent-ffmpeg/v0.1.0-alpha.4-local.21/final-r2/installed'
NEW = ROOT/'local/agent-ffmpeg/v0.1.0-alpha.4-local.22/final-r4/installed'


def sha(p):
    with Path(p).open('rb') as stream: return hashlib.file_digest(stream, 'sha256').hexdigest()


def content(project):
    values = {k: project[k] for k in ('settings', 'assets', 'sequences')}
    values['settings'] = {k: v for k, v in values['settings'].items() if k != 'projection_acceleration'}
    return values


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--run', required=True); ap.add_argument('--source', type=Path, required=True)
    a = ap.parse_args(); assert a.run.replace('-', '').isalnum()
    out = BASE/('benchmark-'+a.run); out.mkdir(exist_ok=False)
    work = ROOT/'workspace'/('float-gpu-20261026-benchmark-'+a.run); work.mkdir(exist_ok=False)
    (out/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    report = {'status': 'running', 'calls': [], 'rounds': [], 'source_fallback': False,
        'virtualization': False, 'exclusive_host': False, 'new_model_forwards': 0,
        'comparison': 'one pair, CPU CLI0.1.23 then GPU CLI0.1.24; not a median or general speed guarantee',
        'cache_policy': 'fresh owned project and empty project cache per render; OS page cache uncontrolled',
        'other_owned_test_or_build_jobs_during_timing': False, 'peak_RSS_measured': False}
    def save(): (out/'verification.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf8', newline='\n')
    def run(name, argv, timeout=1800):
        start = time.perf_counter()
        r = subprocess.run(list(map(str, argv)), cwd=ROOT, capture_output=True, timeout=timeout, creationflags=subprocess.CREATE_NO_WINDOW)
        stdout, stderr = out/(name+'.stdout.log'), out/(name+'.stderr.log'); stdout.write_bytes(r.stdout); stderr.write_bytes(r.stderr)
        report['calls'].append(dict(name=name, argv=list(map(str, argv)), seconds=time.perf_counter()-start,
            exit_code=r.returncode, stdout_sha256=sha(stdout), stderr_sha256=sha(stderr)))
        save(); print(json.dumps({k: report['calls'][-1][k] for k in ('name', 'seconds', 'exit_code')}), flush=True)
        assert r.returncode == 0, (name, r.stdout[-3000:], r.stderr[-3000:])
        return r.stdout
    try:
        kernel = ctypes.WinDLL('kernel32', use_last_error=True); kernel.GetCurrentProcess.restype = wintypes.HANDLE
        kernel.GetProcessAffinityMask.argtypes = [wintypes.HANDLE, ctypes.POINTER(ctypes.c_size_t), ctypes.POINTER(ctypes.c_size_t)]
        kernel.SetProcessAffinityMask.argtypes = [wintypes.HANDLE, ctypes.c_size_t]
        handle = kernel.GetCurrentProcess(); process, system = ctypes.c_size_t(), ctypes.c_size_t()
        assert kernel.GetProcessAffinityMask(handle, ctypes.byref(process), ctypes.byref(system))
        cpus = [i for i in range(8*ctypes.sizeof(process)) if process.value & (1 << i)][:4]; assert len(cpus) == 4
        assert kernel.SetProcessAffinityMask(handle, sum(1 << i for i in cpus)); report['logical_CPU_affinity'] = cpus
        source = a.source.resolve(); authored = json.loads((source/'project.json').read_bytes()); expected = content(authored)
        assert expected['settings']['canvas']['width'] == 3840 and expected['settings']['canvas']['height'] == 2160
        report['authoring_without_device_policy_SHA256'] = hashlib.sha256(json.dumps(expected, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        sys.path.insert(0, str(NEW/'site'))
        from ai_ad_editor.runtime import configure_local_runtime
        from ai_ad_editor.media import ffmpeg_path
        configure_local_runtime(); native = ffmpeg_path()
        versions = {}
        for label, installed, version in [('CPU', OLD, '0.1.23'), ('GPU', NEW, '0.1.24')]:
            prefix = [sys.executable, '-I', '-S', '-B', '-u', '-X', 'utf8', installed/'run.py']
            value = json.loads(run(label+'-version', [*prefix, 'version'])); assert value['data']['cli_version'] == version
            versions[label] = version
            project = work/label; project.mkdir(exist_ok=False)
            for name in ('project.json', 'rights-ledger.json'): shutil.copyfile(source/name, project/name)
            for folder in ('assets', 'fonts'): shutil.copytree(source/folder, project/folder)
            p = json.loads((project/'project.json').read_bytes())
            p['settings']['projection_acceleration'] = {'mode': 'off' if label == 'CPU' else 'require', 'device': '0.0', 'max_working_bytes': 1024**3}
            assert content(p) == expected
            (project/'project.json').write_text(json.dumps(p, ensure_ascii=False, indent=2)+'\n', encoding='utf8', newline='\n')
            output = project/'renders/result.mp4'
            value = json.loads(run(label+'-render', [*prefix, 'render', '--project', project, '--output', output]))
            assert value['ok'] and content(json.loads((project/'project.json').read_bytes())) == expected
            receipt = value['data']['delivery']['pixel_pipeline']; assert receipt['transport']['frames'] == 8
            if label == 'GPU':
                evidence = value['data']['projection_acceleration']
                assert evidence['status'] == 'verified' and evidence['worker_closed'] and evidence['shared_handles_closed']
                assert evidence['operations']['affine'] > 0 and evidence['operations']['paint'] > 0
                report['actual_GPU_receipt'] = evidence
            report['rounds'].append(dict(label=label, project=str(project), output=str(output),
                seconds=report['calls'][-1]['seconds'], SHA256=sha(output), frames=8, authoring_unchanged=True))
            save()
        decoded = []
        for row in report['rounds']:
            label = row['label']; project = Path(row['project']); yuv, pcm = project/'decoded.yuv', project/'decoded.f32'
            run(label+'-decode-video', [native, '-nostdin', '-v', 'error', '-n', '-i', row['output'], '-map', '0:v:0', '-pix_fmt', 'yuv420p', '-f', 'rawvideo', yuv])
            run(label+'-decode-audio', [native, '-nostdin', '-v', 'error', '-n', '-i', row['output'], '-map', '0:a:0', '-c:a', 'pcm_f32le', '-f', 'f32le', pcm])
            clocks = run(label+'-clocks', [native, '-nostdin', '-v', 'error', '-i', row['output'], '-map', '0:v:0', '-f', 'framemd5', '-'])
            clocks = [','.join(line.split(',')[:5]) for line in clocks.decode().splitlines() if line and not line.startswith('#')]
            assert len(clocks) == 8 and yuv.stat().st_size == 8*3840*2160*3//2
            decoded.append((yuv, sha(pcm), clocks))
        first = np.memmap(decoded[0][0], dtype=np.uint8, mode='r'); second = np.memmap(decoded[1][0], dtype=np.uint8, mode='r')
        maximum = changed = 0
        for start in range(0, len(first), 4*1024**2):
            difference = np.abs(first[start:start+4*1024**2].astype(np.int16)-second[start:start+4*1024**2].astype(np.int16))
            maximum = max(maximum, int(difference.max())); changed += int(np.count_nonzero(difference))
        del first, second
        assert maximum <= 1 and decoded[0][1:] == decoded[1][1:]
        cpu, gpu = [row['seconds'] for row in report['rounds']]
        report.update(status='passed', versions=versions, CPU_seconds=cpu, GPU_seconds=gpu, observed_speedup=cpu/gpu,
            maximum_decoded_8bit_code_error=maximum, different_codes=changed, all_8_frame_clocks_equal=True,
            full_decoded_PCM_equal=True, actual_renders=2, width=3840, height=2160, frames_per_render=8,
            fps=4, duration_seconds=2, natural_quality_accepted=False, continuous_playback=False, human_listening=False)
        save(); print(json.dumps({k: report[k] for k in ('status', 'CPU_seconds', 'GPU_seconds', 'observed_speedup', 'maximum_decoded_8bit_code_error')}), flush=True)
    except BaseException as exc:
        report.update(status='failed', error=repr(exc)); save(); raise


if __name__ == '__main__': main()
