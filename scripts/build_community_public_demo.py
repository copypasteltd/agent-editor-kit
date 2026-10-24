"""Render a publishable resource-only example with the installed CLI.

Generated speech is deliberately retained in separate local audition projects;
this public example uses verified CC0 art/SFX, credited CC-BY music and OFL fonts.
"""
from pathlib import Path
import argparse
import hashlib
import json
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    with path.open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--installed', type=Path, required=True)
    p.add_argument('--work', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    a = p.parse_args()
    work, out = a.work.resolve(), a.output.resolve()
    if not work.is_relative_to(ROOT) or not out.is_relative_to(ROOT / 'docs/assets'):
        raise ValueError('Use new project-owned output paths')
    work.mkdir(parents=True, exist_ok=False)
    out.mkdir(parents=True, exist_ok=False)
    logs = work / 'logs'
    logs.mkdir()
    prefix = [sys.executable, '-I', '-S', '-B', '-u', '-X', 'utf8', str(a.installed.resolve() / 'run.py')]
    rows = []
    def cli(name, args):
        argv = [*prefix, *map(str, args)]
        r = subprocess.run(argv, capture_output=True, timeout=360, creationflags=subprocess.CREATE_NO_WINDOW)
        (logs / (name + '.stdout.json')).write_bytes(r.stdout)
        (logs / (name + '.stderr.txt')).write_bytes(r.stderr)
        result = json.loads(r.stdout)
        rows.append(dict(id=name, argv=argv, exit_code=r.returncode, ok=result['ok']))
        (work / 'commands.json').write_text(json.dumps(rows, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
        print(json.dumps(rows[-1], ensure_ascii=False), flush=True)
        assert r.returncode == 0 and result['ok'], result
        return result.get('data', {})
    project = work / 'public project'
    base = ['--project', project]
    cli('init', ['project', 'init', project, '--name', 'Community resources / public demo'])
    music = cli('music-search', ['materials', 'list', '--kind', 'music', '--limit', '100'])
    music_id = next(r['id'] for r in music['records'] if r['collection_id'] == 'oga-gt-rpg' and 'frozen' in r['id'])
    for ident, aid in [(music_id, 'asset_music'), ('kenney-interface-sounds-confirmation-001', 'asset_sfx'),
                       ('noto-sans-sc-variable', 'asset_sc'), ('noto-sans-tc-variable', 'asset_tc')]:
        cli('ingest-' + aid, ['materials', 'ingest', *base, '--id', ident, '--asset-id', aid])
    image = ROOT / 'docs/assets/release-v0.1.0-alpha.3-r1/input/card-1.png'
    license_file = image.with_name('LICENSE.txt')
    cli('ingest-art', ['media', 'ingest', *base, '--input', image, '--asset-id', 'asset_art',
        '--license-spdx', 'CC0-1.0', '--creator', 'Agent Video Kit contributors',
        '--source-url', 'local://community-demo/field-art', '--license-url', license_file, '--evidence', license_file,
        '--verification-status', 'verified', '--permitted-use', 'commercial_ad'])
    cli('prepare-bed', ['music', 'prepare', *base, '--asset-id', 'asset_music', '--duration-seconds', '12',
        '--gain-db', '-8', '--fade-in-seconds', '0.6', '--fade-out-seconds', '1', '--new-asset-id', 'asset_bed'])
    duration = 1080000
    operations = [
        dict(op='update_sequence', sequence_id='seq_main', patch=dict(canvas=dict(width=360, height=640))),
        dict(op='append_clip', track_id='track_video_1', asset_id='asset_art', source_in_tick=0,
             source_out_tick=duration, duration_tick=duration),
        dict(op='append_clip', track_id='track_audio_1', asset_id='asset_bed', source_in_tick=0,
             source_out_tick=duration, duration_tick=duration),
        dict(op='add_track', track_id='track_sfx', kind='audio'),
        dict(op='append_clip', track_id='track_sfx', asset_id='asset_sfx', source_in_tick=0,
             source_out_tick=9000, duration_tick=9000, timeline_start_tick=720000),
        dict(op='add_track', track_id='track_text', kind='subtitle')]
    messages = [('359 项真实资源\nBGM · 短乐 · 音效 · 字体', 'asset_sc', 0, 360000),
                ('本機離線編輯\n獨立音軌 · 可編輯字幕', 'asset_tc', 360000, 360000),
                ('实际成片 / Actual output\n12s · 360 × 640 · 30fps', 'asset_sc', 720000, 360000)]
    for text, font, start, ticks in messages:
        operations.append(dict(op='append_clip', track_id='track_text', generator=dict(type='text'),
            source_in_tick=0, source_out_tick=ticks, duration_tick=ticks, timeline_start_tick=start,
            subtitle=dict(text=text, style=dict(font_asset_id=font, fontsize=25, fontcolor='#FFFFFF',
                max_width=310, line_spacing=6, x='(w-text_w)/2', y='h-text_h-110', borderw=2, bordercolor='#111111'))))
    changes = work / 'changes.json'
    changes.write_text(json.dumps(dict(sequence_id='seq_main', operations=operations), ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    cli('compose', ['timeline', 'compose', *base, '--input', changes])
    cli('look', ['look', 'apply', *base, '--id', 't3-kodak-gold-200', '--global', '--strength', '0.5'])
    cli('validate', ['validate', *base])
    cli('preview', ['preview', 'frame', *base, '--frame', '150', '--height', '640'])
    video = project / 'renders/community-resources.mp4'
    cli('render', ['render', *base, '--output', video, '--width', '360', '--height', '640', '--publish'])
    cli('quality', ['quality', 'check', *base, '--input', video, '--width', '360', '--height', '640', '--require-audio'])
    probe = subprocess.run(['ffprobe', '-v', 'error', '-count_frames', '-show_streams', '-show_format', '-of', 'json', str(video)], capture_output=True, check=True, timeout=90)
    data = json.loads(probe.stdout)
    visual = next(s for s in data['streams'] if s['codec_type'] == 'video')
    assert int(visual['nb_read_frames']) == 360 and any(s['codec_type'] == 'audio' for s in data['streams'])
    decoded = subprocess.run(['ffmpeg', '-v', 'error', '-nostdin', '-i', str(video), '-f', 'null', '-'], capture_output=True, timeout=90)
    (work / 'decode.log').write_bytes(decoded.stderr)
    assert decoded.returncode == 0
    target_video = out / 'community-resources.mp4'
    shutil.copyfile(video, target_video)
    gif = out / 'community-resources.gif'
    subprocess.run(['ffmpeg', '-v', 'error', '-nostdin', '-i', str(video), '-filter_complex',
        '[0:v]fps=8,scale=270:-1:flags=lanczos,split[a][b];[a]palettegen=stats_mode=diff[p];[b][p]paletteuse=dither=sierra2_4a',
        '-an', '-loop', '0', str(gif)], capture_output=True, check=True, timeout=120)
    poster = out / 'preview.png'
    subprocess.run(['ffmpeg', '-v', 'error', '-nostdin', '-ss', '5', '-i', str(video), '-frames:v', '1', str(poster)], capture_output=True, check=True, timeout=60)
    # Publish only evidence/licenses used by these verified source assets.
    notices = out / 'licenses'
    notices.mkdir()
    for source in project.rglob('*'):
        if source.is_file() and source.name in {'NOTICE.txt', 'SOURCE.txt', 'LICENSE.txt', 'provenance.json'} and 'history' not in source.parts:
            dest = notices / source.relative_to(project)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, dest)
    shutil.copyfile(license_file, notices / 'art-CC0.txt')
    (out / 'SOURCE_AND_LICENSES.md').write_text(
        '# Public resource example\n\n12 s, 360 × 640, 30 fps, 360 fully decoded frames. '
        'The GIF is a silent 8 fps preview. MP4 audio contains music and a short interface SFX; no generated speech.\n\n'
        '- Original FIELD art: Agent Video Kit contributors, CC0; original input remains in '
        '`docs/assets/release-v0.1.0-alpha.3-r1/input/card-1.png`.\n'
        '- GT RPG Frozen music: Juhani Junkala, CC-BY-4.0; '
        'https://opengameart.org/content/gt-rpg-soundtrack . Trim/gain/fades are applied, original is retained.\n'
        '- Confirmation SFX: Kenney, CC0-1.0; https://kenney.nl/assets/interface-sounds .\n'
        '- Noto Sans SC/TC: original font copyright holders, OFL-1.1; full notices in licenses/.\n'
        '- Kodak Gold 200 creative LUT: João Almeida, MIT; strength 0.5, full original MIT/provenance retained. '
        'Trademark names do not imply endorsement.\n\n'
        'Native installed CLI render, publish rights gate and full decode pass; human listening and continuous playback remain unreviewed. '
        'Reproduce with scripts/build_community_public_demo.py using the current installed CLI.\n', encoding='utf8', newline='\n')
    report = dict(status='passed-with-review-limits', installed=str(a.installed.resolve()), commands=len(rows),
        video_seconds=12, video_frames=360, fps='30/1', dimensions=[360, 640], full_decode=True,
        publish_gate_passed=True, generated_speech_in_public_media=False, human_listening=False, continuous_playback=False,
        source_music_id=music_id, files=[dict(path=p.relative_to(ROOT).as_posix(), bytes=p.stat().st_size, sha256=sha(p))
            for p in (target_video, gif, poster)], project=str(project), work=str(work))
    for path in (work / 'verification.json', out / 'verification.json'):
        path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf8', newline='\n')
    (work / 'probe.json').write_bytes(probe.stdout)
    print(json.dumps(report, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
