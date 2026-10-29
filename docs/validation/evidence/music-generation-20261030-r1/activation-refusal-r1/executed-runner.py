"""Confirm the real failed compatibility gate cannot change the registered Skill."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'docs/validation/evidence/music-generation-20261030-r1'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def state():
    namespace = ROOT / 'agent-ffmpeg-local-install-manifest.json'
    manifest = json.loads(namespace.read_bytes())
    assert manifest['cli_version'] == '0.1.63' and len(manifest['files']) == 93
    assert manifest['skill_count'] == 1 and manifest['module_count'] == 17
    files = {row['path']:sha(ROOT / row['path']) for row in manifest['files']}
    assert all(files[row['path']] == row['sha256'] for row in manifest['files'])
    files[namespace.relative_to(ROOT).as_posix()] = sha(namespace)
    runtime = ROOT / 'local/agent-ffmpeg/runtime.json'
    files[runtime.relative_to(ROOT).as_posix()] = sha(runtime)
    discovery = Path('C:/Users/carzy/.codex/skills/agent-ffmpeg-local-editor')
    assert discovery.resolve(strict=True) == (ROOT / 'skills/agent-ffmpeg-local-editor').resolve()
    return files


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run', required=True)
    args = parser.parse_args()
    assert args.run.isalnum() and sys.dont_write_bytecode
    actual_failure = json.loads((BASE / 'source64-contracts-r1/verification.json').read_bytes())
    assert actual_failure['status'] == 'failed' and actual_failure['failures'] == 1
    before = state()
    proof = BASE / ('activation-refusal-' + args.run)
    proof.mkdir()
    (proof / 'executed-runner.py').write_bytes(Path(__file__).read_bytes())
    command = [sys.executable, '-E', '-B', '-u', '-X', 'utf8',
        str(ROOT / 'docs/validation/activate_music64_skill.py'), '--run', 'refusal-' + args.run,
        '--source-case-run', 'piano4']
    began = time.monotonic()
    result = subprocess.run(command, capture_output=True, cwd=ROOT, timeout=180,
                            creationflags=subprocess.CREATE_NO_WINDOW)
    (proof / 'check.stdout').write_bytes(result.stdout)
    (proof / 'check.stderr').write_bytes(result.stderr)
    value = json.loads(result.stdout)
    after = state()
    assert result.returncode == 2 and value['status'] == 'rejected'
    assert value['failed']['source64_contracts']['status'] == 'failed'
    assert value['mutated'] is False and value['activated'] is False and before == after
    report = dict(status='passed', test='real failed prerequisite is reported before formal activation',
        exit_code=result.returncode, elapsed_seconds=time.monotonic() - began,
        rejection=value, apply_requested=False, registered_files_before=before, registered_files_after=after,
        formal_cli='0.1.63', formal_skill_files=93, formal_entry_unchanged=True,
        helper_sha256=sha(ROOT / 'docs/validation/activate_music64_skill.py'),
        missing_prerequisites_bypassed=False, GPU_model_executed=False,
        full_product_goal_closed=False)
    (proof / 'verification.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps({k:v for k,v in report.items() if k not in ('registered_files_before', 'registered_files_after')}), flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
