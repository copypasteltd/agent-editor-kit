"""Compose labeled contact sheets and a still-preview animation from actual N002 outputs."""
from pathlib import Path
import hashlib
import json
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / 'docs/assets/looks-n002-20261024-r1'


def main():
    manifest = json.loads((ASSETS / 'manifest.json').read_bytes())
    records = manifest['records']
    font = ImageFont.truetype('C:/Windows/Fonts/msyh.ttc', 17)
    mono = ImageFont.truetype('C:/Windows/Fonts/consola.ttf', 17)
    (ASSETS / 'sheets').mkdir(exist_ok=True)

    def tile(image_path, title, subtitle, width=320):
        height = round(width * 940 / 1672)
        value = Image.new('RGB', (width, height + 53), '#101d29')
        with Image.open(image_path) as image:
            value.paste(image.convert('RGB').resize((width, height), Image.Resampling.LANCZOS), (0, 0))
        draw = ImageDraw.Draw(value)
        # Fit rather than clipping the stable number and readable name.
        while draw.textlength(title, font=font) > width - 14:
            title = title[:-2] + '…'
        draw.text((7, height + 4), title, font=font, fill='#f4f7fa')
        while draw.textlength(subtitle, font=mono) > width - 14:
            subtitle = subtitle[:-2] + '…'
        draw.text((7, height + 28), subtitle, font=mono, fill='#9eb2bf')
        return value

    for start in range(0, 500, 50):
        sheet = Image.new('RGB', (1600, 2330), '#101d29')
        for offset, r in enumerate(records[start:start + 50]):
            picture = tile(ASSETS / r['thumbnail'], f"{r['number']:03} · {r['name']}", r['id'])
            sheet.paste(picture, ((offset % 5) * 320, (offset // 5) * 233))
        sheet.save(ASSETS / 'sheets' / f'{start+1:03}-{start+50:03}.jpg', quality=92, subsampling=0)
    numbers = [1, 11, 49, 70, 80, 101, 134, 188, 267, 368, 500]
    tiles = [tile(ASSETS / 'source.webp', '000 · Original N002', 'Unmodified source', 368)]
    for number in numbers:
        r = records[number - 1]
        tiles.append(tile(ASSETS / r['full'], f"{number:03} · {r['name']}", r['id'], 368))
    poster = Image.new('RGB', (1472, tiles[0].height * 3), '#101d29')
    for index, picture in enumerate(tiles):
        poster.paste(picture, ((index % 4) * 368, (index // 4) * picture.height))
    poster.save(ASSETS / 'selection-board.jpg', quality=95, subsampling=0)
    frames = []
    for number in [0, 1, 11, 70, 101, 134, 188, 368, 500, 0]:
        r = records[number - 1] if number else None
        image = ASSETS / r['full'] if r else ASSETS / 'source.webp'
        frames.append(tile(image, f"{number:03} · {r['name'] if r else 'Original N002'}", 'Actual still preview · strength 1.0' if r else 'Unmodified source', 668))
    frames[0].save(ASSETS / 'look-selection.gif', save_all=True, append_images=frames[1:], duration=1100, loop=0, disposal=2)
    outputs = []
    for path in [ASSETS / 'selection-board.jpg', ASSETS / 'look-selection.gif', *sorted((ASSETS / 'sheets').glob('*.jpg'))]:
        with Image.open(path) as image:
            outputs.append({'path': path.relative_to(ROOT).as_posix(), 'bytes': path.stat().st_size,
                            'sha256': hashlib.sha256(path.read_bytes()).hexdigest(), 'size': list(image.size),
                            'frames': getattr(image, 'n_frames', 1),
                            'duration_ms': sum(image.seek(i) or image.info.get('duration', 0) for i in range(getattr(image, 'n_frames', 1)))})
    out = ROOT / 'docs/validation/evidence/looks-n002-20261024-r1/gallery-media.json'
    out.write_text(json.dumps({'status': 'passed', 'outputs': outputs, 'animation_type': 'sequence of actual still previews; not rendered video footage', 'audio': False}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({'contact_sheets': 10, 'poster': 1, 'still_animation': 1}))


if __name__ == '__main__':
    main()
