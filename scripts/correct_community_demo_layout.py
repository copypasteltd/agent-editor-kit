"""Correct a demo's author canvas and verify preview versus encoded layout.

Render width/height overrides change the composition raster; they are not a
post-render resize of pixel-based subtitle styles. Preserve the original evidence.
"""
from pathlib import Path
import argparse
import hashlib
import json
import subprocess
import sys


def sha(path):
    with path.open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--installed', type=Path, required=True)
    p.add_argument('--project', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    project, out = a.project.resolve(strict=True), a.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    (out / 'logs').mkdir()
    data = json.loads((project / 'project.json').read_bytes())
    (out / 'original-project.json').write_bytes((project / 'project.json').read_bytes())
    original_video = project / 'renders/community-demo.mp4'
    original_sha = sha(original_video)
    stems = {p.name: sha(p) for p in (project / 'assets/community-audio').glob('*.wav')}
    ops = [dict(op='update_sequence', sequence_id='seq_main', patch=dict(canvas=dict(width=360, height=640)))]
    for track in data['sequences'][0]['tracks']:
        for clip in track['clips']:
            if 'subtitle' not in clip:
                continue
            subtitle = json.loads(json.dumps(clip['subtitle']))
            style = subtitle['style']
            for field in ('fontsize', 'max_width', 'line_spacing', 'borderw'):
                if field in style:
                    style[field] = max(1, round(style[field] / 3))
            style['y'] = '75' if track['id'] == 'track_title_tc' else 'h-text_h-117'
            ops.append(dict(op='update_clip', track_id=track['id'], clip_id=clip['id'], patch=dict(subtitle=subtitle)))
    changes = out / 'layout.json'
    changes.write_text(json.dumps(dict(sequence_id='seq_main', operations=ops), ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    prefix = [sys.executable, '-I', '-S', '-B', '-u', '-X', 'utf8', str(a.installed.resolve() / 'run.py')]
    rows = []
    def cli(name, args):
        argv = [*prefix, *map(str, args)]
        r = subprocess.run(argv, capture_output=True, timeout=360, creationflags=subprocess.CREATE_NO_WINDOW)
        (out / 'logs' / (name + '.stdout.json')).write_bytes(r.stdout)
        (out / 'logs' / (name + '.stderr.txt')).write_bytes(r.stderr)
        d = json.loads(r.stdout)
        rows.append(dict(id=name, argv=argv, exit_code=r.returncode, ok=d['ok']))
        (out / 'commands.json').write_text(json.dumps(rows, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
        print(json.dumps(rows[-1], ensure_ascii=False), flush=True)
        assert r.returncode == 0 and d['ok'], d
        return d['data']
    base = ['--project', project]
    cli('compose', ['timeline', 'compose', *base, '--input', changes])
    cli('validate', ['validate', *base])
    preview = cli('preview', ['preview', 'frame', *base, '--frame', '90', '--height', '640'])
    video = project / 'renders/community-demo-reviewed.mp4'
    cli('render', ['render', *base, '--output', video])
    cli('quality', ['quality', 'check', *base, '--input', video, '--width', '360', '--height', '640', '--require-audio'])
    cli('export', ['convert', 'export', *base, '--target-format', 'package', '--output', out / 'reviewed.aevpkg.zip'])
    cli('import', ['convert', 'import', '--input', out / 'reviewed.aevpkg.zip', '--output', out / 'restored'])
    cli('restored-validate', ['validate', '--project', out / 'restored'])
    poster = out / 'encoded-frame-90.png'
    subprocess.run(['ffmpeg', '-v', 'error', '-nostdin', '-i', str(video), '-vf', 'select=eq(n\\,90)', '-frames:v', '1', str(poster)], capture_output=True, check=True, timeout=90)
    subprocess.run(['ffmpeg', '-v', 'error', '-nostdin', '-i', str(video), '-f', 'null', '-'], capture_output=True, check=True, timeout=90)
    probe = subprocess.run(['ffprobe', '-v', 'error', '-count_frames', '-show_streams', '-of', 'json', str(video)], capture_output=True, check=True, timeout=90)
    streams = json.loads(probe.stdout)['streams']
    stream = next(s for s in streams if s['codec_type'] == 'video')
    assert int(stream['nb_read_frames']) == 360 and (stream['width'], stream['height']) == (360, 640)
    assert original_sha == sha(original_video) and stems == {p.name: sha(p) for p in (project / 'assets/community-audio').glob('*.wav')}
    # Metrics use the installed base dependencies, not editable product modules.
    sys.path.insert(0, str(a.installed.resolve() / 'site'))
    from PIL import Image
    import numpy as np
    expected, actual = Image.open(preview['path']).convert('RGB'), Image.open(poster).convert('RGB')
    assert expected.size == actual.size == (360, 640)
    mae = float(np.abs(np.asarray(expected, dtype=float) - np.asarray(actual, dtype=float)).mean())
    assert mae < 3.0, mae
    report = dict(status='passed-with-review-limits', commands=len(rows), actual_new_model_inferences=0,
        original_video_preserved=True, original_video_sha256=original_sha, stems_unchanged=True,
        video=str(video), video_sha256=sha(video), frames=360, dimensions=[360, 640], full_decode=True,
        package_roundtrip=True, preview_encoded_frame_mean_absolute_rgb_error=mae,
        preview=str(preview['path']), poster=str(poster), human_listening=False, continuous_playback=False,
        known_boundary='Render width/height changes the composition raster; author pixel-based text in the intended sequence canvas.')
    (out / 'verification.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    print(json.dumps(report, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
