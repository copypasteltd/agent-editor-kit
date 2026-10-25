"""Run the published editable example through the actual registered Skill."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

from run_projection_scanline_case_20261026 import affinity

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT/'docs/validation/evidence/projection-scanline-20261026-r1'


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    out = BASE/'example-import-r1'
    out.mkdir(exist_ok=False)
    (out/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    report = dict(status='running', started_at_utc=datetime.now(timezone.utc).isoformat(),
                  affinity=affinity(), native_windows=True, virtualization=False,
                  real_registered_skill=True, source_fallback=False,
                  human_listening=False, continuous_playback=False)
    def save(name, value):
        (out/name).write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf8', newline='\n')
    calls = []
    def call(name, argv, binary=False):
        argv = list(map(str, argv))
        result = subprocess.run(argv, cwd=ROOT, capture_output=True, timeout=420,
                                creationflags=subprocess.CREATE_NO_WINDOW)
        stdout, stderr = out/(name+'.stdout'), out/(name+'.stderr')
        if binary:
            save(stdout.name, dict(bytes=len(result.stdout), sha256=hashlib.sha256(result.stdout).hexdigest()))
        else:
            stdout.write_bytes(result.stdout)
        stderr.write_bytes(result.stderr)
        calls.append(dict(id=name, argv=argv, exit_code=result.returncode,
                          stdout_sha256=sha(stdout), stderr_sha256=sha(stderr)))
        save('calls.json', calls)
        assert result.returncode == 0, result.stderr.decode('utf8', 'replace')[-3000:]
        print(json.dumps(dict(id=name, status='passed')), flush=True)
        return result.stdout
    launcher = Path('C:/Users/carzy/.codex/skills/agent-ffmpeg-local-editor/scripts/run.ps1')
    prefix = ['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', launcher]
    def cli(name, *arguments):
        value = json.loads(call(name, [*prefix, *arguments]).decode('utf-8-sig'))
        assert value['ok']
        return value['data']
    package = ROOT/'docs/assets/projection-scanline-20261026-r2/editable-projection.aevpkg.zip'
    checksum = sha(package)
    project = ROOT/'workspace/projection-scanline-20261026-example-r1/客户 示例'
    assert not project.exists()
    try:
        cli('import', 'convert', 'import', '--input', package, '--output', project)
        cli('validate', 'validate', '--project', project)
        target = project/'renders/client.mkv'
        cli('render', 'render', '--project', project, '--sequence-id', 'projection_demo',
            '--sequence-sampling', 'area', '--sequence-memory-mib', '1024',
            '--output', target, '--container', 'mkv', '--audio-codec', 'pcm_f32le',
            '--pixel-format', 'yuv444p', '--crf', '0', '--hardware-encode', 'off')
        ffmpeg = shutil.which('ffmpeg')
        assert ffmpeg
        raw = call('frames', [ffmpeg, '-v', 'error', '-i', target, '-map', '0:v:0', '-an',
                            '-fps_mode', 'passthrough', '-pix_fmt', 'rgba', '-f', 'framemd5', 'pipe:1'])
        frames = [line.rsplit(',', 1)[-1].strip() for line in raw.decode().splitlines()
                  if line and not line.startswith('#')]
        pcm = call('pcm', [ffmpeg, '-v', 'error', '-i', target, '-map', '0:a:0', '-vn',
                          '-acodec', 'pcm_f32le', '-f', 'f32le', 'pipe:1'], True)
        old = json.loads((BASE/'benchmark-r3/verification.json').read_bytes())['renders'][0]['fingerprint']
        assert len(frames) == 120 and frames == old['frames']
        assert len(pcm) == old['pcm_bytes'] and hashlib.sha256(pcm).hexdigest() == old['pcm_sha256']
        assert sha(package) == checksum
        report.update(status='passed', finished_at_utc=datetime.now(timezone.utc).isoformat(),
                      package=str(package), package_sha256=checksum, package_unchanged=True,
                      project=str(project), compared_frames=120, frames_equal=True, audio_pcm_equal=True,
                      result_sha256=sha(target), process_calls=len(calls), new_model_forwards=0,
                      scope='Relocated published editable case; lossless encoded comparison, not playback/listening acceptance.')
        save('verification.json', report)
        print(json.dumps(report, ensure_ascii=False), flush=True)
    except BaseException as exc:
        report.update(status='failed', error=repr(exc))
        save('verification.json', report)
        raise


if __name__ == '__main__':
    main()
