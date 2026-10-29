"""Actually invoke registered-entry/package runners before activation; require no mutation."""
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT/'docs/validation/evidence/lipsync-timeout-20261029-r1'
PYTHON = 'D:/dev/comfyui/ComfyUI_windows_portable_nvidia_0_30_0/ComfyUI_windows_portable/python_embeded/python.exe'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    assert not (BASE/'skill61-activation-r1/verification.json').exists()
    namespace = ROOT/'agent-ffmpeg-local-install-manifest.json'
    runtime = ROOT/'local/agent-ffmpeg/runtime.json'
    manifest = json.loads(namespace.read_bytes())
    assert manifest['cli_version'] == '0.1.59'
    pins = {str(namespace): sha(namespace), str(runtime): sha(runtime)}
    pins.update({str(ROOT/row['path']): row['sha256'] for row in manifest['files']})
    assert len(pins) == 95 and all(sha(Path(p)) == h for p,h in pins.items())
    out = BASE/'registered-delivery-gate-check-r1'
    out.mkdir(exist_ok=False)
    (out/'executed-runner.py').write_bytes(Path(__file__).read_bytes())
    installed = json.loads((BASE/'installation-candidate-r1/verification.json').read_bytes())['installed']
    results = []
    for name in ['run_registered61_loop_case.py', 'run_registered61_gpu_case.py',
                 'run_registered61_lipsync_case.py', 'build_source61_final_kit.py']:
        script = ROOT/'docs/validation'/name
        (out/name).write_bytes(script.read_bytes())
        args = [PYTHON, '-I', '-B', '-u', '-X', 'utf8', str(script), '--run', 'gatecheckr1']
        if name.startswith('run_'):
            args += ['--installed', installed, '--skill', 'C:/Users/carzy/.codex/skills/agent-ffmpeg-local-editor']
        result = subprocess.run(args, cwd=ROOT, capture_output=True, timeout=180,
                                creationflags=subprocess.CREATE_NO_WINDOW)
        (out/(name+'.stdout')).write_bytes(result.stdout)
        (out/(name+'.stderr')).write_bytes(result.stderr)
        assert result.returncode != 0, name
        stderr = result.stderr.decode('utf-8', errors='replace')
        assert ('skill61-activation-r1' in stderr and 'FileNotFoundError' in stderr
                if name.startswith('run_') else "manifest['cli_version'] == '0.1.61'" in stderr), stderr[-1800:]
        assert all(sha(Path(p)) == h for p,h in pins.items()), name
        results.append(dict(runner=name, exit_code=result.returncode, SHA256=sha(script), rejected_before_case=True))
    forbidden = [BASE/'registered-actual-case-gatecheckr1', BASE/'registered61-gpu-gatecheckr1',
                 BASE/'registered61-lipsync-cuda-gatecheckr1', BASE/'formal-kit-build-gatecheckr1',
                 ROOT/'local/agent-ffmpeg/music61-kit-gatecheckr1']
    assert not any(p.exists() for p in forbidden)
    report = dict(status='passed', checks=results, protected_files=95,
                  protected_files_unchanged=True, no_case_or_archive_created=True,
                  activation_performed=False, positive_registered_cases_accepted=False)
    (out/'verification.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
