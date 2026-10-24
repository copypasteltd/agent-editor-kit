"""Render all installed looks on the supplied N002 still, retaining native CLI evidence.

Run with native Python -I -S. Imports are restricted to the pinned installation.
Full-resolution lossless WebP files preserve the decoded CLI PNG pixels exactly.
PNG intermediates and temporary LUTs stay in the explicitly supplied E-drive work folder.
"""
from pathlib import Path
import argparse
import contextlib
import hashlib
import io
import json
import os
import shutil
import sys
import tempfile
import time


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    for key in ('installed', 'source', 'assets', 'evidence', 'work'):
        ap.add_argument('--' + key, type=Path, required=True)
    args = ap.parse_args()
    for key in ('installed', 'source', 'assets', 'evidence', 'work'):
        setattr(args, key, getattr(args, key).resolve())
    for folder in (args.assets, args.evidence, args.work):
        folder.mkdir(parents=True, exist_ok=False)
    (args.work / 'temp').mkdir()
    tempfile.tempdir = str(args.work / 'temp')
    os.environ['TMP'] = str(args.work / 'temp')
    os.environ['TEMP'] = str(args.work / 'temp')
    site = args.installed / 'site'
    sys.path[:] = [str(site), *[p for p in sys.path if p and not {'site-packages', 'dist-packages'} & set(Path(p).parts)]]
    from ai_ad_editor.cli import main as cli_main
    import ai_ad_editor.looks as looks
    import numpy as np
    from PIL import Image
    assert Path(looks.__file__).resolve().is_relative_to(site)
    receipt = json.loads((args.installed / 'receipt.json').read_bytes())
    assert receipt['manifest_sha256'] == 'sha256:3bc0a74144953b97a769db01f3d2d863889da80f010d78ab7e4a2b4eedf1ceea'
    source_hash = sha(args.source)
    assert source_hash == 'babaa64ce3434a23133c41a1d2b4fad384a5e6707546b527508d4731ba83ab4b'
    original = args.assets / 'source.png'
    shutil.copyfile(args.source, original)
    im = Image.open(original).convert('RGB')
    assert im.size == (1672, 940)
    im.save(args.assets / 'source.webp', lossless=True, method=4)
    im.resize((512, 288), Image.Resampling.LANCZOS).save(args.assets / 'source-thumb.webp', quality=90, method=4)
    originals = np.asarray(im).astype('int16')
    for sub in ('full', 'thumbs'):
        (args.assets / sub).mkdir()
    (args.work / 'png').mkdir()
    rows = looks.catalog()['records']
    records = []
    try:
        for index, row in enumerate(rows, 1):
            started = time.monotonic()
            name = f"{row['number']:03}-{row['id']}"
            png = args.work / 'png' / (name + '.png')
            argv = ['look', 'preview', '--id', row['id'], '--input', str(original), '--output', str(png), '--strength', '1']
            out, err = io.StringIO(), io.StringIO()
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                code = cli_main(argv)
            response = json.loads(out.getvalue())
            (args.evidence / (name + '.stdout.json')).write_text(out.getvalue(), encoding='utf-8')
            if err.getvalue():
                (args.evidence / (name + '.stderr.txt')).write_text(err.getvalue(), encoding='utf-8')
            assert code == 0 and response['ok'], (row['id'], code, response)
            with Image.open(png) as image:
                rgb = image.convert('RGB')
                assert rgb.size == im.size
                full = args.assets / 'full' / (name + '.webp')
                rgb.save(full, lossless=True, method=4)
                thumbnail = args.assets / 'thumbs' / (name + '.webp')
                rgb.resize((512, 288), Image.Resampling.LANCZOS).save(thumbnail, quality=90, method=4)
                pixels = np.asarray(rgb)
                with Image.open(full) as decoded:
                    assert np.array_equal(pixels, np.asarray(decoded.convert('RGB'))), name
                diff = np.abs(pixels.astype('int16') - originals)
                records.append({
                    'number': row['number'], 'id': row['id'], 'name': row['name'],
                    'name_zh': row['name_zh'], 'name_zh_tw': row['name_zh_tw'],
                    'category': row['category'], 'license': row['license'], 'source': row['source'],
                    'summary_zh': row['summary_zh'], 'summary_en': row['summary_en'],
                    'suggested_strength_range': row['suggested_strength_range'],
                    'strength': 1.0, 'width': im.width, 'height': im.height,
                    'full': full.relative_to(args.assets).as_posix(),
                    'thumbnail': thumbnail.relative_to(args.assets).as_posix(),
                    'full_sha256': sha(full), 'thumbnail_sha256': sha(thumbnail),
                    'native_png_sha256': sha(png), 'rgb_pixel_sha256': hashlib.sha256(pixels.tobytes()).hexdigest(),
                    'lossless_webp_matches_native_png': True, 'full_bytes': full.stat().st_size,
                    'source_mean_abs_code_difference': round(float(diff.mean()), 6),
                    'output_black_channel_fraction': round(float(np.mean(pixels == 0)), 6),
                    'output_white_channel_fraction': round(float(np.mean(pixels == 255)), 6),
                    'cli_argv': argv, 'exit_code': code,
                    'seconds': round(time.monotonic() - started, 4)
                })
            if index % 10 == 0:
                save(args.evidence / 'progress.json', {'completed': index, 'total': len(rows), 'full_bytes': sum(r['full_bytes'] for r in records)})
                print(json.dumps({'completed': index, 'total': len(rows), 'full_MB': round(sum(r['full_bytes'] for r in records) / 1e6, 1)}), flush=True)
        assert len(records) == 500
        assert len({r['rgb_pixel_sha256'] for r in records}) == 500
        assert sha(args.source) == source_hash == sha(original)
        manifest = {
            'product': 'agent editor kit', 'case_id': 'N002-500-20261024-r1',
            'release': 'v0.1.0-alpha.3', 'catalog_version': '2.0.0',
            'source': {'supplied_path': str(args.source), 'published_original': 'source.png',
                       'sha256': source_hash, 'width': im.width, 'height': im.height,
                       'mode': 'RGB', 'embedded_color_profile': False,
                       'input_assumption': 'encoded SDR RGB; no inferred camera, HDR or ICC calibration',
                       'permission_basis': 'User supplied this image and explicitly requested per-filter examples in the repository README and Skills.',
                       'license': 'LicenseRef-User-Supplied-Preview; not CC0 or the software MIT license'},
            'preview': {'strength': 1.0, 'interpolation': 'tetrahedral',
                        'full_format': 'lossless WebP; decoded RGB equals actual CLI PNG exactly',
                        'thumbnail_format': '512x288 WebP quality 90; resized selection aid'},
            'records': records
        }
        save(args.assets / 'manifest.json', manifest)
        report = {'status': 'passed', 'case_id': manifest['case_id'], 'installed_cli_previews': 500,
                  'full_resolution_images': 500, 'thumbnails': 500, 'unique_pixel_hashes': 500,
                  'lossless_pixel_comparisons': 500, 'source_unchanged': True,
                  'source_sha256': source_hash, 'module': str(Path(looks.__file__).resolve()),
                  'source_fallback': False, 'manifest_sha256': sha(args.assets / 'manifest.json'),
                  'full_bytes': sum(r['full_bytes'] for r in records),
                  'new_video_renders': 0, 'new_model_inferences': 0,
                  'human_500_look_quality_acceptance': False,
                  'scope': '500 real executions on one supplied still; no universal natural-video quality or skin-protection claim'}
        save(args.evidence / 'render-verification.json', report)
        print(json.dumps(report, ensure_ascii=False), flush=True)
    except Exception as exc:
        save(args.evidence / 'failure.json', {'status': 'failed', 'completed': len(records), 'error': str(exc)})
        raise


if __name__ == '__main__':
    main()
