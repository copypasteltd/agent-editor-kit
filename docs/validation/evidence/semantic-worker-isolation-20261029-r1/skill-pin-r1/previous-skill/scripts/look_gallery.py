"""Search actual N002 look previews or export a small labeled client comparison board.

Uses Pillow from the pinned local installation; no network, models, source-runtime fallback or project edits.
"""
from pathlib import Path
import argparse
import hashlib
import json
import math
import os
import sys
import textwrap

ROOT = Path(__file__).resolve().parents[3]
ASSETS = ROOT / 'docs/assets/looks-n002-20261024-r1'
PIN = 'sha256:3bc0a74144953b97a769db01f3d2d863889da80f010d78ab7e4a2b4eedf1ceea'
MANIFEST_SHA = '349e8a729586360d8f9186a5f1cd4058bf3f0d463254804529b10d594c44f8da'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--query', help='Search names, IDs, measured descriptions, categories and licenses')
    mode.add_argument('--ids', nargs='+', help='Stable IDs, in the desired display order; at most 12')
    parser.add_argument('--output', type=Path, help='New absolute directory for board.jpg and selection.json')
    parser.add_argument('--limit', type=int, default=12)
    args = parser.parse_args()
    if not 1 <= args.limit <= 50:
        parser.error('--limit must be 1..50')
    if not (ASSETS / 'manifest.json').is_file():
        parser.error('N002 gallery assets are missing; obtain the docs/assets gallery from this checkout')
    if sha(ASSETS / 'manifest.json') != MANIFEST_SHA:
        raise ValueError('Gallery manifest does not match the verified N002 build')
    manifest = json.loads((ASSETS / 'manifest.json').read_bytes())
    if sha(ASSETS / 'source.png') != manifest['source']['sha256']:
        raise ValueError('Source image changed')
    records = manifest['records']
    if args.query is not None:
        if args.output:
            parser.error('--output requires --ids')
        query = args.query.casefold()
        found = [r for r in records if query in ' '.join(str(r[k]) for k in ('number', 'id', 'name', 'name_zh', 'name_zh_tw', 'category', 'summary_zh', 'summary_en', 'license')).casefold()]
        print(json.dumps({'ok': True, 'total': len(found), 'records': [{k: r[k] for k in ('number', 'id', 'name', 'name_zh', 'category', 'license', 'full', 'strength')} for r in found[:args.limit]], 'gallery': str(ASSETS / 'index.html')}, ensure_ascii=False, indent=2))
        return
    if not args.output or not args.output.is_absolute():
        parser.error('--ids requires a new absolute --output directory')
    if not 1 <= len(args.ids) <= 12 or len(set(args.ids)) != len(args.ids):
        parser.error('Choose 1..12 distinct stable IDs')
    by_id = {r['id']: r for r in records}
    unknown = [look_id for look_id in args.ids if look_id not in by_id]
    if unknown:
        parser.error('Unknown IDs: ' + ', '.join(unknown))
    selected = [by_id[look_id] for look_id in args.ids]
    for row in selected:
        full = ASSETS / row['full']
        if not full.resolve().is_relative_to(ASSETS.resolve()) or sha(full) != row['full_sha256']:
            raise ValueError('Selected preview changed: ' + row['id'])
    config = json.loads((ROOT / 'local/agent-ffmpeg/runtime.json').read_bytes())
    installed = Path(config['installed_directory'])
    receipt = json.loads((installed / 'receipt.json').read_bytes())
    if config['release'] != 'v0.1.0-alpha.3' or config['manifest_sha256'] != PIN or receipt['manifest_sha256'] != PIN:
        raise ValueError('Pinned installed release unavailable')
    if not Path(sys.executable).samefile(config['python']) or sys.prefix != sys.base_prefix:
        raise ValueError('Use the registered native Python interpreter')
    if sha(installed / 'run.py') != config['launcher_sha256']:
        raise ValueError('Installed launcher changed')
    sys.path.insert(0, str(installed / 'site'))
    from PIL import Image, ImageDraw, ImageFont
    font_path = Path(os.environ.get('WINDIR', 'C:/Windows')) / 'Fonts/msyh.ttc'
    font = ImageFont.truetype(str(font_path), 17) if font_path.exists() else ImageFont.load_default(size=17)
    mono_path = font_path.parent / 'consola.ttf'
    mono = ImageFont.truetype(str(mono_path), 14) if mono_path.exists() else ImageFont.load_default(size=14)
    all_items = [{'number': 0, 'id': 'original-N002', 'name_zh': '母图 / Original N002', 'full': 'source.webp', 'license': {'spdx': 'User-supplied preview'}}] + selected
    cols = min(3, len(all_items)); width, picture_height, tile_height = 560, 315, 400
    board = Image.new('RGB', (cols * width, math.ceil(len(all_items) / cols) * tile_height), '#101d29')
    draw = ImageDraw.Draw(board)
    for index, row in enumerate(all_items):
        x, y = (index % cols) * width, (index // cols) * tile_height
        with Image.open(ASSETS / row['full']) as image:
            board.paste(image.convert('RGB').resize((width, picture_height), Image.Resampling.LANCZOS), (x, y))
        title = f"{row['number']:03} · {row['name_zh']}"
        while draw.textlength(title, font=font) > width - 20:
            title = title[:-2] + '…'
        draw.text((x + 10, y + picture_height + 4), title, font=font, fill='#f4f7fa')
        stable_id = '\n'.join(textwrap.wrap(row['id'], width=65, break_long_words=True, break_on_hyphens=False))
        draw.multiline_text((x + 10, y + picture_height + 30), stable_id, font=mono, fill='#9eb2bf', spacing=2)
        draw.text((x + 10, y + tile_height - 22), row['license']['spdx'] + (' · strength 1.0' if index else ''), font=mono, fill='#83b2aa')
    target = args.output.resolve()
    target.mkdir(parents=True, exist_ok=False)
    board.save(target / 'board.jpg', quality=95, subsampling=0)
    value = {'schema': 'aek-look-shortlist-v1', 'release': 'v0.1.0-alpha.3', 'catalog_version': '2.0.0',
             'source_sha256': manifest['source']['sha256'], 'preview_strength': 1.0,
             'selection_state': 'candidates; not project application',
             'board': str(target / 'board.jpg'),
             'looks': [{k: r[k] for k in ('number', 'id', 'name', 'name_zh', 'category', 'summary_zh', 'license', 'strength', 'full_sha256')} | {'preview': str(ASSETS / r['full'])} for r in selected],
             'next_step': 'Choose the final ID and render reviewed strengths on the target media before applying to an explicit clip or global scope.'}
    (target / 'selection.json').write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps({'ok': True, 'board': str(target / 'board.jpg'), 'selection': str(target / 'selection.json'), 'candidates': len(selected), 'project_modified': False}, ensure_ascii=False))


if __name__ == '__main__':
    main()
