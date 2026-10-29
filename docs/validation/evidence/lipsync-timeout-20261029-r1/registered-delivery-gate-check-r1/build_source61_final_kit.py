"""Build the CLI61/r58 unified kit after the actual registered CUDA case."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT/'docs/validation/evidence/lipsync-timeout-20261029-r1'


def load(path):
    return json.loads(path.read_bytes())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', required=True)
    args = parser.parse_args()
    assert args.run.replace('-', '').isalnum()
    namespace = ROOT/'agent-ffmpeg-local-install-manifest.json'
    runtime = ROOT/'local/agent-ffmpeg/runtime.json'
    manifest = load(namespace)
    assert manifest['cli_version'] == '0.1.61' and manifest['skill_count'] == 1
    assert manifest['module_count'] == 17 and len(manifest['files']) == 93
    for row in manifest['files']:
        assert sha(ROOT/row['path']) == row['sha256']
    activation = load(BASE/'skill61-activation-r1/verification.json')
    assert activation['status'] == 'activated-and-entry-verified'
    assert sha(namespace) == activation['namespace_sha256']
    assert sha(runtime) == activation['runtime_sha256']
    for pin in activation['gates'].values():
        assert sha(ROOT/pin['path']) == pin['sha256']
    case_path = BASE/'registered61-gpu-r1/verification.json'
    case = load(case_path)
    assert case['status'] == 'passed' and case['cli_version'] == '0.1.61'
    for flag in ['actual_C_drive_entry', 'actual_CUDA_model', 'actual_PowerShell_entry',
                 'complete_PCM_replay_equal', 'complete_source_installed_PCM_equal', 'frozen_equal']:
        assert case[flag] is True, flag
    assert case['source_fallback'] is False and case['complete_PCM_bytes'] == 1124160
    assert Path(load(runtime)['installed_directory']).resolve() == Path(case['installed']).resolve()
    assert Path('C:/Users/carzy/.codex/skills/agent-ffmpeg-local-editor').resolve() == (ROOT/'skills/agent-ffmpeg-local-editor').resolve()
    loop=load(BASE/'registered-actual-case-r1/verification.json')
    assert loop['status']=='passed' and loop['actual_C_drive_entry'] and loop['actual_PowerShell_entry']
    assert loop['complete_package_recipe_repair_PCM_equal'] and loop['complete_repaired_PCM_bytes']==2557440
    lipsync=load(BASE/'registered61-lipsync-cuda-r1/verification.json')
    assert lipsync['status']=='passed' and lipsync['cli_version']=='0.1.61'
    for flag in ['actual_C_drive_entry','actual_PowerShell_entry','actual_MuseTalk_CUDA',
                 'complete_source_installed_master_and_render_equal',
                 'complete_package_rendered_RGBA_PCM_equal','owned_process_cleanup_passed']:
        assert lipsync[flag] is True,flag
    assert lipsync['frames']==133 and lipsync['complete_master_RGBA_bytes']==139460608
    assert not lipsync['model_execution']['CPU_fallback']
    out = BASE/('formal-kit-build-'+args.run)
    out.mkdir(exist_ok=False)
    (out/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    output = ROOT/'local/agent-ffmpeg'/('music61-kit-'+args.run)
    argv = [sys.executable, '-I', '-S', '-B', '-u', '-X', 'utf8',
            str(ROOT/'scripts/package_community_skill.py'), '--output', str(output),
            '--archive-name', 'agent-editor-kit-community-unified-skill-r58.zip']
    result = subprocess.run(argv, cwd=ROOT, capture_output=True, timeout=180,
                            creationflags=subprocess.CREATE_NO_WINDOW)
    (out/'package.stdout').write_bytes(result.stdout)
    (out/'package.stderr').write_bytes(result.stderr)
    assert result.returncode == 0, result.stderr
    package = json.loads(result.stdout)
    assert package['cli_version'] == '0.1.61' and package['files'] == 161
    assert package['skill_count'] == 1 and package['module_count'] == 17
    assert sha(Path(package['archive'])) == package['sha256']
    assert sha(namespace) == activation['namespace_sha256'] and sha(runtime) == activation['runtime_sha256']
    report = dict(status='built-awaiting-independent-verification', package=package,
                  registered_case_sha256=sha(case_path), public_entries=1, modules=17,
                  skill_files=93, actual_registered_GPU_case_accepted=True,actual_registered_loop_case_accepted=True,actual_registered_MuseTalk_case_accepted=True, independent_kit_accepted=False)
    (out/'verification.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
