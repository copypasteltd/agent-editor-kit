"""Check exact staged Skill/source bytes against the delivered native wheel."""
from pathlib import Path
import hashlib
import io
import json
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]
GIT = 'C:/Users/carzy/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/git/cmd/git.exe'


def main():
    command = [GIT, '--no-optional-locks', '-c', 'core.fsmonitor=false', '-c', 'gc.auto=0', '-c', 'maintenance.auto=false']
    paths = subprocess.check_output([*command, 'diff', '--cached', '--name-only', '-z'], cwd=ROOT).decode('utf-8').strip('\0').split('\0')
    assert paths and not any(p.startswith(('workspace/', 'local/', 'product/.runtime/', 'docs/releases/')) for p in paths)
    assert all((ROOT/p).stat().st_size < 10*1024**2 for p in paths)
    manifest = json.loads((ROOT/'agent-ffmpeg-local-install-manifest.json').read_bytes())
    names = [x['path'] for x in manifest['files']]
    changed = [p for p in paths if p.startswith('product/src/')]
    requested = names + changed
    raw = subprocess.check_output([*command, 'cat-file', '--batch'], cwd=ROOT,
                                  input=''.join(':'+p+'\n' for p in requested).encode('utf-8'))
    stream, blobs = io.BytesIO(raw), {}
    for name in requested:
        header = stream.readline().split()
        assert len(header) == 3 and header[1] == b'blob'
        data = stream.read(int(header[2]))
        assert stream.read(1) == b'\n'
        blobs[name] = data
    for row in manifest['files']:
        assert hashlib.sha256(blobs[row['path']]).hexdigest() == row['sha256'], row['path']
    bundle = ROOT/'local/agent-ffmpeg/v0.1.0-alpha.4-local.2/final/bundle'
    members = {}
    with zipfile.ZipFile(bundle/'wheels/ai_ad_editor-0.1.4-py3-none-win_amd64.whl') as z:
        for name in changed:
            desired = name.removeprefix('product/src/')
            matches = [m for m in z.namelist() if m == desired or m.endswith('/purelib/'+desired)]
            assert len(matches) == 1, (name, matches)
            assert z.read(matches[0]) == blobs[name], name
            members[name] = matches[0]
    subprocess.run([*command, 'diff', '--cached', '--check'], cwd=ROOT, check=True)
    report = {'status': 'passed', 'staged_paths_before_this_receipt': len(paths),
              'staged_skill_files_match_manifest': len(names), 'changed_source_files_match_built_wheel': members,
              'generated_workspace_and_models_unstaged': True, 'prior_public_release_paths_unchanged': True,
              'largest_staged_file_bytes': max((ROOT/p).stat().st_size for p in paths),
              'generator_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    output = ROOT/'docs/validation/evidence/implementation-20261025-r1/staged-scope-check-r2.json'
    assert not output.exists()
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    main()
