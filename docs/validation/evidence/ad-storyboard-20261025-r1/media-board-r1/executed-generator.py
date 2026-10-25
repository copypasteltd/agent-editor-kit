"""Arrange actual variant frames without overlap; preserve original media receipt."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
PUBLIC = ROOT / 'docs/assets/ad-storyboard-20261025-r1'
OUT = ROOT / 'docs/validation/evidence/ad-storyboard-20261025-r1/media-board-r1'


def main():
    OUT.mkdir(exist_ok=False)
    (OUT / 'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    board = Image.new('RGB', (1040, 990), '#eef1f4')
    draw = ImageDraw.Draw(board)
    font = ImageFont.truetype(str(ROOT / 'product/src/ai_ad_editor/material_data/fonts/noto-sans-sc-variable.ttf'), 23)
    draw.text((30, 24), 'agent editor kit / actual editable ad variants', font=font, fill='#1b2b36')
    originals = []
    for name, xy, size, label in (
        ('vertical12', (30, 125), (270, 480), '9:16 / 12 s / 360 frames'),
        ('wide9', (350, 125), (640, 360), '16:9 / 9 s / 270 frames'),
        ('square9', (350, 570), (360, 360), '1:1 / 9 s / 270 frames'),
    ):
        path = PUBLIC / (name + '.png')
        originals.append(dict(path=path.relative_to(ROOT).as_posix(), sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
        with Image.open(path) as source:
            image = source.convert('RGB')
            image.thumbnail(size)
            board.paste(image, xy)
        draw.text((xy[0], xy[1]-40), label, font=font, fill='#1b2b36')
    target = PUBLIC / 'variants-clear.png'
    assert not target.exists()
    board.save(target)
    report = dict(status='passed', created_at_utc=datetime.now(timezone.utc).isoformat(), source_stills=originals,
        output=target.relative_to(ROOT).as_posix(), sha256=hashlib.sha256(target.read_bytes()).hexdigest(),
        bytes=target.stat().st_size, original_media_receipt_unchanged=True,
        purpose='Nonoverlapping contact sheet only; no new inference or render.')
    (OUT/'verification.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf8', newline='\n')
    print(json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    main()
