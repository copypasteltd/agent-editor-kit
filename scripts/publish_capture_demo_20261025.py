"""Publish only the generated-pattern capture, with reproducible media metadata."""
from pathlib import Path
import hashlib
import json
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def main():
    evidence = ROOT / 'docs/validation/evidence/implementation-20261025-r1/native-capture-development-r2/verification.json'
    report = json.loads(evidence.read_bytes())
    assert report['status'] == 'passed' and not report['microphone_opened'] and not report['unrelated_windows_captured']
    target = ROOT / 'docs/assets/native-capture-20261025-r1'
    target.mkdir(parents=True, exist_ok=False)
    files = []
    for row in report['outputs']:
        source = Path(row['file'])
        assert hashlib.sha256(source.read_bytes()).hexdigest() == row['sha256']
        output = target / (row['asset_id'] + '.mp4')
        shutil.copyfile(source, output)
        probe = subprocess.run(['ffprobe', '-v', 'error', '-show_streams', '-show_format', '-of', 'json', str(output)], capture_output=True, check=True)
        data = json.loads(probe.stdout)
        assert len(data['streams']) == 1 and data['streams'][0]['codec_type'] == 'video'
        subprocess.run(['ffmpeg', '-v', 'error', '-nostdin', '-xerror', '-i', str(output), '-f', 'null', '-'], check=True, capture_output=True)
        files.append({'path': output.relative_to(ROOT).as_posix(), 'sha256': row['sha256'], 'bytes': output.stat().st_size,
                      'encoder': row['encoder'], 'streams': data['streams'], 'format': data['format'], 'full_decode': True})
    source = target / 'gpu-window.mp4'
    subprocess.run(['ffmpeg', '-v', 'error', '-nostdin', '-n', '-i', str(source), '-frames:v', '1', str(target/'preview.png')], check=True, capture_output=True)
    subprocess.run(['ffmpeg', '-v', 'error', '-nostdin', '-n', '-i', str(source), '-filter_complex',
        'fps=10,scale=480:-2:flags=lanczos,split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse', '-loop', '0', str(target/'preview.gif')], check=True, capture_output=True)
    for name in ['preview.png', 'preview.gif']:
        path = target/name
        files.append({'path': path.relative_to(ROOT).as_posix(), 'bytes': path.stat().st_size,
                      'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
    (target/'SOURCE.md').write_text('# Native capture demonstration\n\n'
        'Input: FFmpeg `testsrc2=size=480x270:rate=15`, displayed in the test script’s own ffplay window. '
        'No third-party footage, other application window, camera or microphone was captured. '
        'The product captures media through a CLI; the player is a test fixture, not a product GUI.\n\n'
        'Reproduction: `scripts/smoke_native_capture_20261025.py`, then `scripts/publish_capture_demo_20261025.py`. '
        'Both CPU/libx264 and GPU/NVENC outputs are two seconds, 30 frames; the GIF is a derived preview. '
        'Decode and changing-pixel checks passed. Continuous human viewing and audiovisual sync were not accepted.\n\n'
        'The project generated these demonstration files for redistribution. FFmpeg and its optional codecs '
        'retain their own licenses; the executable is not redistributed in this media directory.\n', encoding='utf-8')
    value = {'status': 'passed', 'source': report['source'], 'files': files, 'unrelated_content': False,
             'camera': False, 'microphone': False, 'human_viewing_accepted': False,
             'generator_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
             'evidence_sha256': hashlib.sha256(evidence.read_bytes()).hexdigest()}
    (target/'verification.json').write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({'status': 'passed', 'files': len(files), 'directory': str(target)}))


if __name__ == '__main__':
    main()
