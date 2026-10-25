"""Render actual search decisions, including every observed error, as editable cards."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

from PIL import Image, ImageDraw, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'docs/validation/evidence/semantic-package-20261025-r1'


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', required=True)
    parser.add_argument('--installed', type=Path, required=True)
    parser.add_argument('--source-project', type=Path, required=True)
    parser.add_argument('--gallery', type=Path, required=True)
    args = parser.parse_args()
    assert args.run.replace('-', '').isalnum()
    installed, source, gallery = (p.resolve(strict=True) for p in
                                 (args.installed, args.source_project, args.gallery))
    assert source.is_relative_to(ROOT / 'workspace') and gallery.is_relative_to(ROOT / 'docs/assets')
    work = ROOT / 'workspace' / ('semantic-package-demo-' + args.run)
    output = ROOT / 'docs/assets/semantic-package-20261025-r1' / ('demo-' + args.run)
    evidence = BASE / ('demo-' + args.run)
    for path in (work, output, evidence):
        path.mkdir(parents=True, exist_ok=False)
    (evidence / 'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    prefix = ['C:/Python313/python.exe', '-I', '-S', '-B', '-u', '-X', 'utf8', str(installed / 'run.py')]
    source_bytes = {p.name: sha(p) for p in (installed / 'site/ai_ad_editor').glob('*.py')}
    calls, media_calls = [], []

    def save(path, value):
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')

    def cli(*arguments):
        command = [*prefix, *map(str, arguments)]
        started = datetime.now(timezone.utc).isoformat()
        value = subprocess.run(command, cwd=ROOT, capture_output=True, timeout=900,
                               creationflags=subprocess.CREATE_NO_WINDOW)
        number = len(calls) + 1
        stdout, stderr = evidence / f'{number:02}.stdout.json', evidence / f'{number:02}.stderr.txt'
        stdout.write_bytes(value.stdout); stderr.write_bytes(value.stderr)
        response = json.loads(value.stdout.decode('utf-8-sig'))
        calls.append(dict(argv=command, exit_code=value.returncode, status=response.get('status'),
            started_at_utc=started, stdout_sha256=sha(stdout), stderr_sha256=sha(stderr)))
        save(evidence / 'calls.json', calls)
        print(json.dumps(dict(call=number, command=response.get('command'), status=response.get('status'))), flush=True)
        assert value.returncode == 0 and response['ok'], response
        return response['data']

    def media(*arguments):
        command = list(map(str, arguments))
        value = subprocess.run(command, capture_output=True, timeout=180,
                               creationflags=subprocess.CREATE_NO_WINDOW)
        media_calls.append(dict(argv=command, exit_code=value.returncode))
        save(evidence / 'media-calls.json', media_calls)
        assert value.returncode == 0, value.stderr.decode('utf-8', 'replace')[-2000:]
        return value.stdout

    report = dict(status='running', started_at_utc=datetime.now(timezone.utc).isoformat(),
                  installed=True, new_model_forwards=0, native_windows=True, virtualization=False)
    try:
        records = {r['id']: r for r in json.loads((gallery / 'decisions.json').read_bytes())}
        order = ['q18', 'q19', 'q14', 'hout00zh', 'hout08zh', 'hpos09en']
        selected = [records[key] for key in order]
        assert len(selected) == 6 and sum(not r['correct'] for r in selected) == 3
        font_path = ROOT / 'product/src/ai_ad_editor/material_data/fonts/noto-sans-sc-variable.ttf'
        font = ImageFont.truetype(str(font_path), 27)
        small = ImageFont.truetype(str(font_path), 21)
        cards = []
        for ordinal, row in enumerate(selected):
            color = '#72d6ad' if row['correct'] else '#ff827d'
            image = Image.new('RGB', (960, 540), '#101821')
            draw = ImageDraw.Draw(image)
            draw.text((20, 12), 'ACTUAL MODEL RESULT / 实际模型结果 · ' + row['id'], font=small, fill=color)
            lines = ['']
            for character in row['text']:
                if draw.textlength(lines[-1] + character, font=font) > 915:
                    lines.append('')
                lines[-1] += character
            assert len(lines) <= 2
            draw.multiline_text((20, 48), '\n'.join(lines), font=font, spacing=4, fill='white')
            if row['actual_image']:
                preview = gallery / row['actual_image']
                with Image.open(preview) as picture:
                    thumb = ImageOps.pad(picture.convert('RGB'), (920, 300), color='#080b0f')
                    image.paste(thumb, (20, 132)); thumb.close()
            else:
                draw.rectangle((20, 132, 940, 432), fill='#080b0f')
                draw.text((205, 260), 'NO CALIBRATED MATCH / 暂无候选', font=font, fill='#c4deed')
            draw.text((20, 443), row['decision'] + ' · ' + ('PASS' if row['correct'] else 'FAIL'), font=small, fill=color)
            expected = ','.join(row['expected_asset_ids']) or 'absent / 库外'
            draw.text((20, 477), 'Frozen expectation / 冻结标注: ' + expected, font=small, fill='#c4deed')
            draw.text((20, 508), 'Familiar static images; empirical acceptance; no human approval. / 非人类验收', font=small, fill='#a3b6c5')
            path = output / f'card-{ordinal+1}.png'
            image.save(path); image.close(); cards.append(path)
        save(output / 'selected-decisions.json', dict(selection=order, records=selected,
            source_sha256=sha(gallery / 'decisions.json'), duration_policy='authored two seconds per diagnostic card',
            editability='six individually editable image-card clips; card typography is rasterized'))
        project = work / 'project'
        cli('project', 'init', project, '--name', 'Actual semantic decisions and failures')
        for ordinal, path in enumerate(cards):
            cli('media', 'ingest', '--project', project, '--input', path, '--asset-id', 'card_' + str(ordinal),
                '--creator', 'Local diagnostic; original CC0/NASA credits in SOURCE.json',
                '--license-spdx', 'LicenseRef-Mixed-CC0-NASA',
                '--evidence', ROOT / 'docs/assets/semantic-package-20261025-r1/SOURCE.json',
                '--source-url', 'local://semantic-decision-card/' + str(ordinal), '--verification-status', 'verified')
        data = json.loads((project / 'project.json').read_bytes())
        tps = data['settings']['timebase']['ticks_per_second']
        operations = [dict(op='update_sequence', sequence_id='seq_main', patch=dict(canvas=dict(width=960, height=540)))]
        for ordinal in range(6):
            operations.append(dict(op='append_clip', track_id='track_video_1', asset_id='card_' + str(ordinal),
                source_in_tick=0, source_out_tick=2*tps, duration_tick=2*tps, timeline_start_tick=ordinal*2*tps))
        edits = work / 'changes.json'; save(edits, dict(sequence_id='seq_main', operations=operations))
        cli('timeline', 'compose', '--project', project, '--input', edits)
        cli('validate', '--project', project)
        video = project / 'renders/decisions.mp4'
        cli('render', '--project', project, '--output', video, '--width', '960', '--height', '540')
        cli('quality', 'check', '--project', project, '--input', video, '--width', '960', '--height', '540')
        cli('convert', 'export', '--project', project, '--target-format', 'package', '--output', output / 'editable-cards.aevpkg.zip')
        restored = work / 'restored'
        cli('convert', 'import', '--input', output / 'editable-cards.aevpkg.zip', '--output', restored)
        cli('validate', '--project', restored)
        again = restored / 'renders/again.mp4'
        cli('render', '--project', restored, '--output', again, '--width', '960', '--height', '540')
        decoded = []
        for ordinal, path in enumerate((video, again)):
            raw = media('ffmpeg', '-nostdin', '-v', 'error', '-i', path, '-map', '0:v:0', '-f', 'framemd5', '-')
            (evidence / f'decoded-{ordinal}.framemd5').write_bytes(raw)
            decoded.append([line for line in raw.splitlines() if not line.startswith(b'#')])
        assert decoded[0] == decoded[1]
        probe = media('ffprobe', '-v', 'error', '-count_frames', '-show_streams', '-show_format', '-of', 'json', video)
        (evidence / 'probe.json').write_bytes(probe)
        visual = next(s for s in json.loads(probe)['streams'] if s['codec_type'] == 'video')
        assert int(visual['nb_read_frames']) == 360 and Fraction(visual['avg_frame_rate']) == 30
        board = Image.new('RGB', (1280, 1140), '#101821')
        ImageDraw.Draw(board).text((16, 12), 'ACTUAL ENCODED FRAMES / 实际编码画面，含失败', font=font, fill='white')
        for ordinal in range(6):
            still = output / f'encoded-frame-{ordinal+1}.png'
            media('ffmpeg', '-nostdin', '-v', 'error', '-ss', str(ordinal*2+1),
                  '-i', video, '-frames:v', '1', '-n', still)
            with Image.open(still) as picture:
                thumbnail = ImageOps.pad(picture.convert('RGB'), (640, 360))
                board.paste(thumbnail, ((ordinal % 2)*640, 60+(ordinal // 2)*360))
                thumbnail.close()
        board.save(output / 'actual-encoded-frames.png'); board.close()
        shutil.copyfile(video, output / 'decisions.mp4')
        gif = output / 'decisions.gif'
        media('ffmpeg', '-nostdin', '-v', 'error', '-i', video, '-filter_complex',
            '[0:v]fps=5,scale=640:-1:flags=lanczos,split[a][b];[a]palettegen[p];[b][p]paletteuse=dither=sierra2_4a',
            '-an', '-loop', '0', '-n', gif)
        with Image.open(gif) as animated:
            durations = []
            for index in range(animated.n_frames):
                animated.seek(index); durations.append(animated.info.get('duration', 0))
        assert sum(durations) == 12000 and len(durations) > 1
        package = output / 'retrieval-project.aevpkg.zip'
        cli('convert', 'export', '--project', source, '--target-format', 'package', '--output', package)
        retrieval_restored = work / 'retrieval-restored'
        cli('convert', 'import', '--input', package, '--output', retrieval_restored)
        cli('validate', '--project', retrieval_restored)
        dry = cli('semantic', 'search', '--project', retrieval_restored, '--index-id', 'images-v1',
            '--query', 'a cat', '--kind', 'image', '--calibration-id', 'accept-cuda', '--device', 'cuda', '--dry-run')
        assert dry['calibration_verified'] and dry['model_forward_calls'] == 0
        shutil.copyfile(ROOT / 'docs/assets/semantic-package-20261025-r1/SOURCE.json', output / 'SOURCE.json')
        shutil.copyfile(gallery / 'SOURCE_AND_LICENSES.md', output / 'SOURCE_AND_LICENSES.md')
        assert source_bytes == {p.name: sha(p) for p in (installed / 'site/ai_ad_editor').glob('*.py')}
        report.update(status='passed-with-review-limits', calls=len(calls), duration_seconds=12, frames=360,
            fps='30', dimensions=[960,540], full_video_decode=True, package_decoded_pixels_equal=True,
            retrieval_profile_package_verified_same_host=True, new_model_forwards=0, selected_cards=6,
            selected_known_errors=3, gif_frames=len(durations), gif_duration_ms=sum(durations),
            gif_sample_fps=5, gif_frame_durations_ms=durations, human_continuous_viewing=False,
            human_listening=False, natural_action_benchmark=False, card_typography_rasterized=True,
            files=[dict(path=p.relative_to(ROOT).as_posix(),sha256=sha(p),bytes=p.stat().st_size)
                   for p in sorted(output.iterdir()) if p.is_file()], finished_at_utc=datetime.now(timezone.utc).isoformat())
        save(evidence / 'verification.json', report)
        save(output / 'verification.json', report)
        print(json.dumps({k:v for k,v in report.items() if k not in ('files','gif_frame_durations_ms')}), flush=True)
    except BaseException as exc:
        report.update(status='failed', error=repr(exc), calls=len(calls))
        save(evidence / 'failure.json', report)
        raise


if __name__ == '__main__':
    main()
