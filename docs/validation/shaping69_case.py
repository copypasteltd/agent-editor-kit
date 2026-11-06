"""Actual multilingual native-font renders, encoded animation and portable replay."""
from __future__ import annotations
import argparse
from contextlib import ExitStack
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
from pathlib import Path, PurePosixPath
import shutil
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'docs/validation/evidence/shaping69-20261107-r1'
TEXT = 'Agent editor kit\n中文排版 / العربية 123\nעברית שלום 42 (AEK)\nनमस्ते — ffi — A\u0301'


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def save(path, value):
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def checked(argv, *, budget=120):
    result = subprocess.run(list(map(str, argv)), capture_output=True, timeout=budget,
                            creationflags=subprocess.CREATE_NO_WINDOW)
    assert result.returncode == 0, result.stderr.decode('utf-8', errors='replace')[-4000:]
    return result.stdout


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', required=True)
    parser.add_argument('--freeze-run', default='r1')
    parser.add_argument('--build-run', default='r1')
    parser.add_argument('--tests-run', default='r1')
    parser.add_argument('--ffmpeg')
    parser.add_argument('--ffprobe')
    args = parser.parse_args()
    assert all(value.isalnum() and len(value) <= 32 for value in (args.run, args.freeze_run, args.build_run, args.tests_run))
    spec = importlib.util.spec_from_file_location('shaping69_case_guard', ROOT / 'docs/validation/validate_shaping69.py')
    valid = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(valid)
    frozen_path = BASE / ('freeze-' + args.freeze_run) / 'verification.json'
    frozen = json.loads(frozen_path.read_bytes())
    valid.guard(frozen)
    tests = json.loads((BASE / ('tests-' + args.tests_run) / 'verification.json').read_bytes())
    assert tests['status'] == 'passed' and tests['freeze_sha256'] == sha(frozen_path)
    build = json.loads((BASE / ('build-' + args.build_run) / 'verification.json').read_bytes())
    assert build['freeze_sha256'] == sha(frozen_path)
    runtime = Path(build['runtime'])
    target = ROOT / ('local/agent-ffmpeg/shaping69-case-20261107-' + args.run)
    assert target.drive.upper() == 'E:'
    target.mkdir(exist_ok=False)
    frames = target / 'frames'
    frames.mkdir()
    ffmpeg = Path(args.ffmpeg or shutil.which('ffmpeg.exe') or '')
    ffprobe = Path(args.ffprobe or shutil.which('ffprobe.exe') or '')
    assert ffmpeg.is_file() and ffprobe.is_file(), 'Explicit native FFmpeg/FFprobe is required'
    sys.path[:0] = [str(ROOT / 'development/shaping69/src'), str(ROOT / 'development/text68/src')]
    from aek_shaping import Engine, FontSpec, Renderer, layout, selection, prefix_plan
    from aek_shaping.png import encode
    from aek_unicode17 import graphemes
    engine = Engine(runtime / 'native.json')
    frame_hashes, selection_checks, reveal_checks = [], [], []
    with ExitStack() as stack:
        fonts = []
        for role in ('latin', 'arabic', 'hebrew', 'devanagari', 'cjk'):
            row = engine.manifest['fonts'][role]
            fonts.append(stack.enter_context(engine.font(FontSpec(runtime / row['path'], row['sha256'], 44))))
        plan = layout(engine, TEXT, fonts, max_width=960)
        renderer = Renderer(plan, padding=40, line_spacing=12)
        normal, normal_proof = renderer.render()
        (target / 'normal.png').write_bytes(encode(renderer.width, renderer.height, normal))
        save(target / 'plan.json', plan.data())
        words = ['Agent', '中文排版', 'العربية', '123', 'עברית', 'שלום', '42', 'AEK', 'नमस्ते', 'ffi', 'A\u0301']
        selections = [[TEXT.index(word), TEXT.index(word) + len(word)] for word in words]
        ends = [0] + [span.end for span in graphemes(TEXT)]
        for number in range(36):
            if number < 18:
                chosen = selection(plan, [selections[number % len(selections)]])
                rgba, proof = renderer.render(chosen)
                assert proof['alpha'] == normal_proof['alpha']
                assert all(rgba[index*4:index*4+4] == normal[index*4:index*4+4]
                           for index, alpha in enumerate(proof['selected_alpha']) if not alpha)
                selection_checks.append(dict(frame=number, requested=chosen['requested'], selected_pixels=proof['selected_pixels'],
                    alpha_equal=True, outside_selection_RGBA_equal=True, clusters=proof['clusters']))
                if number == 4:
                    (target / 'highlight.png').write_bytes(encode(renderer.width, renderer.height, rgba))
            else:
                end = ends[(len(ends) - 1) * (number - 18) // 17]
                shown = prefix_plan(plan, end)
                rgba, proof = renderer.render(display_plan=shown)
                assert all(glyph['source_end'] <= end for line in shown.lines for glyph in line.glyphs)
                for index, line in enumerate(shown.lines):
                    full = plan.lines[index]
                    expected_anchor = normal_proof['origins_26_6'][index][0] + (full.width if full.base else 0)
                    actual_anchor = proof['origins_26_6'][index][0] + (line.width if line.base else 0)
                    assert actual_anchor == expected_anchor
                assert end != len(TEXT) or rgba == normal
                reveal_checks.append(dict(frame=number, source_end=end, no_hidden_suffix_glyphs=True,
                                          fixed_full_layout_anchors=True, paragraph_bases=[line.base for line in shown.lines]))
            opaque = bytearray(len(rgba))
            for pixel in range(renderer.width * renderer.height):
                alpha = rgba[pixel * 4 + 3]
                for channel, background in enumerate((18, 25, 36)):
                    opaque[pixel*4+channel] = (rgba[pixel*4+channel]*alpha + background*(255-alpha) + 127) // 255
                opaque[pixel*4+3] = 255
            raw = bytes(opaque)
            frame_hashes.append(hashlib.sha256(raw).hexdigest())
            (frames / (f'{number:03}.png')).write_bytes(encode(renderer.width, renderer.height, raw))
        request = dict(format='aek-shaping69-request-v1', runtime=str(runtime / 'native.json'), text=TEXT,
            fonts=[dict(path=str(font.spec.path), sha256=font.spec.sha256, pixels=44) for font in fonts],
            layout=dict(max_width=960), render=dict(padding=40, line_spacing=12))
    pattern = frames / '%03d.png'
    checked([ffmpeg, '-v', 'error', '-n', '-framerate', '8', '-i', pattern, '-c:v', 'qtrle', '-pix_fmt', 'argb', target / 'master.mov'])
    checked([ffmpeg, '-v', 'error', '-n', '-framerate', '8', '-i', pattern, '-vf', 'pad=ceil(iw/2)*2:ceil(ih/2)*2',
             '-c:v', 'libx264', '-crf', '18', '-pix_fmt', 'yuv420p', target / 'actual.mp4'])
    checked([ffmpeg, '-v', 'error', '-n', '-framerate', '8', '-i', pattern, '-filter_complex',
             '[0:v]split[a][b];[a]palettegen=stats_mode=diff[p];[b][p]paletteuse=dither=sierra2_4a', target / 'actual.gif'])
    decoded = checked([ffmpeg, '-v', 'error', '-i', target / 'master.mov', '-f', 'rawvideo', '-pix_fmt', 'rgba', '-'])
    length = renderer.width * renderer.height * 4
    assert len(decoded) == length * 36
    assert all(hashlib.sha256(decoded[index*length:(index+1)*length]).hexdigest() == expected for index, expected in enumerate(frame_hashes))
    probes = {}
    for name in ('master.mov', 'actual.mp4', 'actual.gif'):
        probe = json.loads(checked([ffprobe, '-v', 'error', '-count_frames', '-show_streams', '-show_format', '-of', 'json', target / name]))
        assert not any(row['codec_type'] == 'audio' for row in probe['streams'])
        probes[name] = probe
    for name in ('master.mov', 'actual.mp4'):
        video = next(row for row in probes[name]['streams'] if row['codec_type'] == 'video')
        assert int(video['nb_read_frames']) == 36 and video['r_frame_rate'] == '8/1'
    # Replay the built archive in a new Chinese/space directory, using only its
    # own Python modules, native DLL, declared fonts and license files.
    portable = target / '独立 解包'
    portable.mkdir()
    with zipfile.ZipFile(build['archive']) as zipped:
        members = zipped.infolist()
        assert len(members) <= 256 and sum(row.file_size for row in members) <= 256 * 1024**2
        for row in members:
            member = PurePosixPath(row.filename)
            assert not member.is_absolute() and '..' not in member.parts and ':' not in row.filename and '\\' not in row.filename
            assert (row.external_attr >> 16) & 0o170000 != 0o120000
            if row.is_dir():
                continue
            out = portable / row.filename
            out.parent.mkdir(parents=True, exist_ok=True)
            with out.open('xb') as stream:
                stream.write(zipped.read(row))
    payload = json.loads((portable / 'payload.json').read_bytes())
    assert all(sha(portable / name) == pin for name, pin in payload['files'].items())
    portable_manifest = json.loads((portable / 'native.json').read_bytes())
    request['runtime'] = str(portable / 'native.json')
    request['fonts'] = [dict(path=str(portable / portable_manifest['fonts'][role]['path']),
        sha256=portable_manifest['fonts'][role]['sha256'], pixels=44) for role in ('latin', 'arabic', 'hebrew', 'devanagari', 'cjk')]
    save(target / 'portable-request.json', request)
    command = checked([sys.executable, '-I', '-B', '-X', 'utf8', portable / 'run.py', 'render', '--request',
                       target / 'portable-request.json', '--output', target / 'portable-render'])
    assert json.loads(command)['ok'] and (target / 'portable-render/actual.png').read_bytes() == (target / 'normal.png').read_bytes()
    valid.guard(frozen)
    target_receipt = BASE / ('case-' + args.run)
    target_receipt.mkdir(exist_ok=False)
    record = dict(status='passed', observed_at_utc=datetime.now(timezone.utc).isoformat(),
        freeze_sha256=sha(frozen_path), native_versions=engine.versions, source_text=TEXT,
        source_text_author='Agent editor kit contributors; authored for this case', source_text_license='MIT',
        font_licenses={role: 'OFL-1.1' for role in portable_manifest['fonts']},
        target=str(target), width=renderer.width, height=renderer.height, encoded_frames=36, master_fps='8/1',
        master_duration_seconds='4.5', full_36_frame_RGBA_exact=True, all_frame_hashes=frame_hashes,
        actual_selection_frames=selection_checks, actual_reveal_frames=reveal_checks,
        portable_source_fallback=False, portable_archive_payload_verified=True, portable_render_PNG_exact=True,
        actual_media_probes=probes, ffmpeg_sha256=sha(ffmpeg), ffprobe_sha256=sha(ffprobe),
        artifacts={name: dict(path=str(target / name), sha256=sha(target / name), bytes=(target/name).stat().st_size)
                   for name in ('normal.png', 'highlight.png', 'master.mov', 'actual.mp4', 'actual.gif', 'plan.json')},
        audio_present=False, human_listening=False, continuous_playback_review=False, still_image_review=False,
        model_forwards=0, GPU_used=False, product_integrated=False, formal_skill_modified=False, full_goal_closed=False)
    save(target_receipt / 'verification.json', record)
    print(json.dumps({key: value for key, value in record.items() if key not in ('actual_media_probes', 'actual_selection_frames', 'actual_reveal_frames')}, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
