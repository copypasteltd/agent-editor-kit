"""Use the unchanged formal CLI59 Skill to import and reselect an optical template."""
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[2]
PACK = ROOT / 'docs/content/effect-packs/optical-v1'
PUBLIC = ROOT / 'docs/assets/optical-pack-20261029-r1'


def load(p):
    return json.loads(p.read_bytes())


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def save(p, value):
    p.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')


def main():
    namespace = ROOT / 'agent-ffmpeg-local-install-manifest.json'
    runtime = ROOT / 'local/agent-ffmpeg/runtime.json'
    manifest = load(namespace)
    assert manifest['cli_version'] == '0.1.59'
    pins = {str(p): sha(p) for p in (namespace, runtime)}
    pins.update({str(ROOT / r['path']): r['sha256'] for r in manifest['files']})
    assert len(pins) == 95 and all(sha(Path(p)) == h for p, h in pins.items())
    discovery = Path('C:/Users/carzy/.codex/skills/agent-ffmpeg-local-editor')
    assert discovery.resolve() == (ROOT / 'skills/agent-ffmpeg-local-editor').resolve()
    source = PUBLIC / 'OP01.aevpkg.zip'
    assert source.is_file()
    item = load(PACK / 'catalog.json')['items'][-1]
    assert item['id'] == 'OP08'
    template = PACK / item['template']
    assert sha(template) == item['sha256']
    out = ROOT / 'docs/validation/evidence/optical-pack-20261029-registered59-r1'
    home = ROOT / 'local/agent-ffmpeg/optical-pack-registered59-r1'
    for p in (out, home):
        p.mkdir(parents=True, exist_ok=False)
    (out / 'executed-runner.py').write_bytes(Path(__file__).read_bytes())
    calls = []
    def run(name, argv, cli=False):
        result = subprocess.run(list(map(str, argv)), cwd=ROOT, capture_output=True, timeout=1800,
                                creationflags=subprocess.CREATE_NO_WINDOW)
        (out / (name + '.stderr')).write_bytes(result.stderr)
        if cli:
            (out / (name + '.stdout')).write_bytes(result.stdout)
        calls.append(dict(name=name, exit_code=result.returncode, stdout_bytes=len(result.stdout),
                          stdout_sha256=hashlib.sha256(result.stdout).hexdigest()))
        save(out / 'calls.json', calls)
        print(json.dumps(calls[-1]), flush=True)
        assert result.returncode == 0, (name, result.stdout[-1400:], result.stderr[-2000:])
        if cli:
            value = json.loads(result.stdout)
            assert value['ok'] and value['provenance']['cli_version'] == '0.1.59'
            return value['data']
        return result.stdout
    def cli(name, *args):
        return run(name, ['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
                          discovery / 'scripts/run.ps1', *args], cli=True)
    cli('version', 'version')
    project = home / 'project'
    cli('import', 'convert', 'import', '--input', source, '--output', project)
    values = home / 'variables.json'
    save(values, dict(clip_id='hero', middle_tick=180000, end_tick=360000))
    before = (project / 'project.json').read_bytes()
    cli('dry-run', 'template', 'apply', '--project', project, '--input', template, '--variables', values, '--dry-run')
    assert before == (project / 'project.json').read_bytes()
    cli('reselect-OP08', 'template', 'apply', '--project', project, '--input', template, '--variables', values)
    cli('validate', 'validate', '--project', project)
    movie = project / 'renders/selected.mkv'
    data = cli('render', 'render', '--project', project, '--output', movie, '--container', 'mkv',
               '--video-codec', 'libx264', '--crf', '0', '--pixel-format', 'yuv444p', '--audio-codec', 'pcm_s16le',
               '--hardware-encode', 'off', '--projection-acceleration', 'require', '--projection-device', '0.0')
    gpu = data['delivery']['pixel_pipeline']['projection_acceleration']
    assert gpu['status'] == 'verified' and gpu['operations']['optics'] == gpu['operations']['glow'] == 48
    assert gpu['worker_closed'] and gpu['shared_handles_closed'] and not gpu['runtime_failure_CPU_fallback']
    ffmpeg = shutil.which('ffmpeg')
    assert ffmpeg
    rgba = run('rgba', [ffmpeg, '-nostdin', '-v', 'error', '-i', movie, '-map', '0:v:0', '-an',
                        '-pix_fmt', 'rgba', '-f', 'rawvideo', 'pipe:1'])
    pcm = run('pcm', [ffmpeg, '-nostdin', '-v', 'error', '-i', movie, '-map', '0:a:0', '-vn',
                      '-c:a', 'pcm_s16le', '-f', 's16le', 'pipe:1'])
    assert len(rgba) == 24883200 and len(pcm) == 768000
    assert all(sha(Path(p)) == h for p, h in pins.items()) and discovery.resolve() == (ROOT / 'skills/agent-ffmpeg-local-editor').resolve()
    report = dict(status='passed', actual_C_drive_Skill_entry=True, cli_version='0.1.59',
                  actual_template_reselection='OP01-to-OP08', template_sha256=sha(template),
                  actual_GPU=gpu['native']['device'], edited_operations=gpu['operations'],
                  worker_and_shared_closed=True, runtime_CPU_fallback=False, formal_files_unchanged=95,
                  full_RGBA_bytes=len(rgba), full_RGBA_sha256=hashlib.sha256(rgba).hexdigest(),
                  full_PCM_bytes=len(pcm), full_PCM_sha256=hashlib.sha256(pcm).hexdigest(),
                  comparison_to_all_eight_candidate_cases_pending=True,
                  new_neural_forwards=0, natural_quality_accepted=False, full_goal_closed=False)
    save(out / 'verification.json', report)
    print(json.dumps(report, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
