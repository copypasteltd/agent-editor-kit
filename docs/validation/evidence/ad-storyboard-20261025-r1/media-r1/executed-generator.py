"""Publish silent derivatives of actual encodes; keep unreviewed speech local."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'docs/validation/evidence/ad-storyboard-20261025-r1'
PUBLIC = ROOT / 'docs/assets/ad-storyboard-20261025-r1'
WORK = ROOT / 'workspace/ad-storyboard-20261025-installed-r1'


def load(path):
    return json.loads(path.read_bytes())


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    for phase in ('render-continue-r1', 'revision-r1', 'roundtrip-r1'):
        assert load(BASE / phase / 'verification.json')['status'] == 'passed'
    out = BASE / 'media-r1'; out.mkdir(exist_ok=False)
    (out / 'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    project = WORK / 'original-project-offline'
    calls, records, frames = [], [], []
    def run(name, command):
        result = subprocess.run(list(map(str, command)), cwd=ROOT, capture_output=True, timeout=180,
                                creationflags=subprocess.CREATE_NO_WINDOW)
        (out / (name + '.stdout')).write_bytes(result.stdout)
        (out / (name + '.stderr')).write_bytes(result.stderr)
        calls.append(dict(name=name, argv=list(map(str, command)), exit_code=result.returncode))
        assert result.returncode == 0, result.stderr.decode('utf8', 'replace')
        return result.stdout
    for vid, seconds, canvas in [('vertical12', 12, (360, 640)), ('wide9', 9, (640, 360)), ('square9', 9, (360, 360))]:
        source = project / 'renders' / (vid + '.mkv')
        mp4 = PUBLIC / (vid + '-silent.mp4')
        gif = PUBLIC / (vid + '.gif')
        still = PUBLIC / (vid + '.png')
        run(vid + '-silent', ['ffmpeg', '-v', 'error', '-i', source, '-map', '0:v:0', '-an',
                             '-c:v', 'libx264', '-crf', '18', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', mp4])
        run(vid + '-gif', ['ffmpeg', '-v', 'error', '-i', source, '-an', '-vf',
            'fps=5,scale=240:-2:flags=lanczos,split[a][b];[a]palettegen[p];[b][p]paletteuse', gif])
        run(vid + '-frame', ['ffmpeg', '-v', 'error', '-ss', '1.5', '-i', source, '-frames:v', '1', still])
        probe = json.loads(run(vid + '-probe', ['ffprobe', '-v', 'error', '-count_frames', '-show_streams', '-of', 'json', mp4]))
        assert len(probe['streams']) == 1
        video = probe['streams'][0]
        assert (video['width'], video['height']) == canvas and int(video['nb_read_frames']) == seconds * 30
        with Image.open(gif) as animation:
            assert animation.n_frames == seconds * 5
            duration = sum((animation.seek(i) or animation.info['duration']) for i in range(animation.n_frames))
            assert duration == seconds * 1000
        records.extend([dict(path=p.relative_to(ROOT).as_posix(), bytes=p.stat().st_size, sha256=sha(p),
                             audio=False, seconds=seconds, frames=seconds*(5 if p.suffix=='.gif' else 30),
                             fps=5 if p.suffix=='.gif' else 30) for p in (mp4, gif)])
        records.append(dict(path=still.relative_to(ROOT).as_posix(), bytes=still.stat().st_size, sha256=sha(still), still=True))
        frames.append(still)
    # A real last-shot before/after comparison, separate from motion previews.
    for name, video in [('before', 'wide9.mkv'), ('after', 'wide9-revision.mkv')]:
        target = PUBLIC / ('revision-' + name + '.png')
        run('revision-' + name, ['ffmpeg', '-v', 'error', '-ss', '7.5', '-i', project / 'renders' / video, '-frames:v', '1', target])
        records.append(dict(path=target.relative_to(ROOT).as_posix(), sha256=sha(target), bytes=target.stat().st_size, still=True))
    board = Image.new('RGB', (1040, 650), '#eef1f4')
    draw = ImageDraw.Draw(board)
    font = ImageFont.truetype(str(ROOT / 'product/src/ai_ad_editor/material_data/fonts/noto-sans-sc-variable.ttf'), 22)
    draw.text((28, 20), 'agent editor kit / actual editable ad variants', font=font, fill='#1b2b36')
    for path, rect in zip(frames, [(25, 75, 295, 555), (325, 75, 1005, 458), (650, 385, 1005, 630)]):
        with Image.open(path) as image:
            image = image.convert('RGB'); image.thumbnail((rect[2]-rect[0], rect[3]-rect[1]))
            board.paste(image, (rect[0], rect[1]))
    board.save(PUBLIC / 'variants.png')
    records.append(dict(path=(PUBLIC/'variants.png').relative_to(ROOT).as_posix(),sha256=sha(PUBLIC/'variants.png'),bytes=(PUBLIC/'variants.png').stat().st_size))
    for path in (PUBLIC / 'source').iterdir():
        records.append(dict(path=path.relative_to(ROOT).as_posix(), sha256=sha(path), bytes=path.stat().st_size, original_input=True))
    report = dict(status='passed', created_at_utc=datetime.now(timezone.utc).isoformat(), files=records,
        public_audio=False, local_complete_speech_preserved=True, source='programmatically authored product-ad art, not GUI screenshots',
        continuous_decode=True, human_playback=False, human_listening=False, independent_natural_ad_quality=False)
    for path in (PUBLIC / 'media-manifest.json', out / 'verification.json'):
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf8', newline='\n')
    (out / 'calls.json').write_text(json.dumps(calls,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    print(json.dumps({k:v for k,v in report.items() if k!='files'},ensure_ascii=False))


if __name__ == '__main__':
    main()
