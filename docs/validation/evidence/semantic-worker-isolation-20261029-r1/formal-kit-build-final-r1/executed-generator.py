"""Build a new formal CLI56 Skill kit only after actual registered GPU acceptance."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT/'docs/validation/evidence/semantic-worker-isolation-20261029-r1'


def load(path):
    return json.loads(path.read_bytes())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', required=True)
    parser.add_argument('--activation-run', default='r1')
    parser.add_argument('--registered-case-run', default='registered-r1')
    args = parser.parse_args()
    for value in (args.run, args.activation_run, args.registered_case_run):
        assert value.replace('-', '').isalnum()
    manifest_path = ROOT/'agent-ffmpeg-local-install-manifest.json'
    manifest = load(manifest_path)
    assert manifest['cli_version'] == '0.1.56' and manifest['skill_count'] == 1
    assert manifest['module_count'] == 17 and len(manifest['files']) == 93
    for row in manifest['files']:
        assert sha(ROOT/row['path']) == row['sha256']
    activation = load(BASE/('activation-'+args.activation_run)/'activation-and-registration.json')
    assert activation['status'] == 'passed' and activation['cli_version'] == '0.1.56'
    assert activation['verified_model_packs'] == 4 and activation['source_fallback'] is False
    case_path = BASE/('installed-case-'+args.registered_case_run)/'verification.json'
    case = load(case_path)
    assert case['status'] == 'passed' and case['cli_version'] == '0.1.56'
    for flag in ('actual_PowerShell_entry', 'actual_GPU_semantic_search', 'full_project_replay_equal',
                 'project_unchanged_by_selection', 'frozen_equal', 'non_silent_finite_PCM'):
        assert case[flag] is True
    assert case['source_fallback'] is False and case['renders'] == 4
    assert set(case['variants']) == {'wide', 'vertical'}
    discovery = Path('C:/Users/carzy/.codex/skills/agent-ffmpeg-local-editor')
    assert discovery.resolve() == (ROOT/'skills/agent-ffmpeg-local-editor').resolve()
    assert Path(load(ROOT/'local/agent-ffmpeg/runtime.json')['installed_directory']).resolve() == Path(case['installed']).resolve()
    out = BASE/('formal-kit-build-'+args.run)
    out.mkdir(exist_ok=False)
    (out/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    manifest_pin = sha(manifest_path)
    output = ROOT/'local/agent-ffmpeg'/('ad-selection-kit56-'+args.run)
    argv = [sys.executable, '-I', '-S', '-B', '-u', '-X', 'utf8',
            str(ROOT/'scripts/package_community_skill.py'), '--output', str(output),
            '--archive-name', 'agent-editor-kit-community-unified-skill-r55.zip']
    result = subprocess.run(argv, cwd=ROOT, capture_output=True, timeout=180,
                            creationflags=subprocess.CREATE_NO_WINDOW)
    (out/'package.stdout').write_bytes(result.stdout)
    (out/'package.stderr').write_bytes(result.stderr)
    assert result.returncode == 0, result.stderr.decode('utf-8', 'replace')
    report = json.loads(result.stdout)
    assert report['cli_version'] == '0.1.56' and report['files'] == 157
    assert report['skill_count'] == 1 and report['module_count'] == 17
    assert sha(Path(report['archive'])) == report['sha256']
    assert sha(manifest_path) == manifest_pin
    proof = dict(status='built-awaiting-independent-verification', package=report,
                 registered_case_sha256=sha(case_path), namespace_sha256=manifest_pin,
                 public_entries=1, modules=17, skill_files=93,
                 product_docs_added=['AD_SEMANTIC_SELECTION.md', 'PROCESS_OPERATION_BUDGET.md',
                                     'SEMANTIC_WORKER_ISOLATION.md'],
                 actual_registered_GPU_case_accepted=True, independent_kit_accepted=False)
    (out/'verification.json').write_text(json.dumps(proof, ensure_ascii=False, indent=2)+'\n',
                                        encoding='utf-8', newline='\n')
    print(json.dumps(proof, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
