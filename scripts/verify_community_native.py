"""Run the real installed community workflows and preserve every response.

No source fallback, browser, online model endpoint, or virtualization is used.
This is functional evidence; it never claims human listening/translation review.
"""
from pathlib import Path
from datetime import datetime, timezone
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import wave

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    with path.open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--installed', type=Path, required=True)
    parser.add_argument('--packs', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    installed, packs, output = args.installed.resolve(strict=True), args.packs.resolve(strict=True), args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    logs = output / 'logs'
    logs.mkdir()
    prefix = [sys.executable, '-I', '-S', '-B', '-u', '-X', 'utf8', str(installed / 'run.py')]
    commands = []

    def cli(name, arguments, *, error=None):
        started = time.perf_counter()
        argv = [*prefix, *map(str, arguments)]
        result = subprocess.run(argv, capture_output=True, timeout=360, creationflags=subprocess.CREATE_NO_WINDOW)
        (logs / (name + '.stdout.json')).write_bytes(result.stdout)
        (logs / (name + '.stderr.txt')).write_bytes(result.stderr)
        try:
            response = json.loads(result.stdout)
        except (ValueError, UnicodeError):
            response = {'ok': False, 'status': 'invalid-json-response', 'errors': []}
        row = dict(id=name, argv=argv, exit_code=result.returncode, ok=response.get('ok'),
                   status=response.get('status'), seconds=time.perf_counter() - started, expected_error=error)
        commands.append(row)
        save(output / 'commands.json', commands)
        print(json.dumps({k: row[k] for k in ['id', 'exit_code', 'ok', 'seconds']}, ensure_ascii=False), flush=True)
        if error:
            assert result.returncode and not response['ok'] and response['errors'][0]['code'] == error, response
        else:
            assert result.returncode == 0 and response['ok'] and not response['errors'], response
        return response

    assert cli('version', ['version'])['data']['cli_version'] == '0.1.3'
    cli('doctor', ['doctor'])
    cap = cli('capabilities', ['capabilities'])['data']['capabilities']
    assert cap['community_materials']['counts'] == dict(music=44, jingle=85, sfx=228, font=2)
    all_verified = cli('verify-all-materials', ['materials', 'verify', '--all'])['data']
    assert all_verified['verified'] == 359
    search = cli('search-music', ['materials', 'list', '--kind', 'music', '--limit', '100'])['data']
    assert search['total_matches'] == 44
    chinese_search = cli('search-font-traditional', ['materials', 'list', '--query', '繁體', '--kind', 'font'])['data']
    assert chinese_search['total_matches'] == 1
    voices = cli('voices', ['voice', 'list'])['data']
    assert voices['count'] == 103
    for ident in ('kokoro-zh-en-int8', 'opus-zh-en-cpu-int8'):
        cli('verify-' + ident, ['model-pack', 'verify', '--id', ident, '--pack', packs / ident])
    cli('look-regression', ['look', 'inspect', '--id', 't3-kodak-gold-200'])
    project = output / '可编辑示例 project'
    cli('project-init', ['project', 'init', project, '--name', 'Community voice, translation and music'])
    base = ['--project', project]
    ids = {}
    chosen_music = next(r['id'] for r in search['records'] if r['collection_id'] == 'oga-gt-rpg' and 'frozen' in r['id'])
    for key, ident in [('music', chosen_music), ('jingle', 'kenney-music-jingles-jingles-hit00'),
                       ('sfx', 'kenney-interface-sounds-confirmation-001'), ('font_sc', 'noto-sans-sc-variable'),
                       ('font_tc', 'noto-sans-tc-variable')]:
        aid = 'asset_' + key
        response = cli('ingest-' + key, ['materials', 'ingest', *base, '--id', ident, '--asset-id', aid])
        ids[key] = response['data']['asset']['id']
    voice_text = '从本地素材开始，生成可编辑的视频。原声、字幕和配乐均可独立调整。'
    voice = cli('voice-zh', ['voice', 'synthesize', *base, '--pack', packs / 'kokoro-zh-en-int8',
                            '--voice', 'zf_001', '--text', voice_text, '--asset-id', 'asset_voice_zh'])['data']
    ids['voice'] = voice['asset']['id']
    assert voice['synthesis']['sample_rate'] == 24000 and voice['synthesis']['rms'] > 0.001
    assert voice['rights']['verification_status'] == 'unverified'
    english = output / 'english-voice.txt'
    english.write_text('Preview the edit, check the captions, and keep the original audio.', encoding='utf-8')
    cli('voice-en-file-speed', ['voice', 'synthesize', *base, '--pack', packs / 'kokoro-zh-en-int8',
        '--voice', 'af_maple', '--input', english, '--speed', '1.15', '--asset-id', 'asset_voice_en'])
    cli('voice-zh-male-speed', ['voice', 'synthesize', *base, '--pack', packs / 'kokoro-zh-en-int8',
        '--voice', 'zm_009', '--text', '本地配音试听，保留独立音轨。', '--speed', '0.9', '--asset-id', 'asset_voice_male'])
    clip_duration = 12
    prepared = cli('prepare-music', ['music', 'prepare', *base, '--asset-id', ids['music'],
                '--duration-seconds', str(clip_duration), '--fade-in-seconds', '0.6', '--fade-out-seconds', '1.0',
                '--new-asset-id', 'asset_bed'])['data']
    assert prepared['audio_stats']['frames'] == clip_duration * 48000
    looped = cli('loop-short-jingle', ['music', 'prepare', *base, '--asset-id', ids['jingle'], '--loop',
                 '--duration-seconds', '4', '--gain-db', '-6', '--fade-out-seconds', '0.4', '--new-asset-id', 'asset_loop'])['data']
    assert looped['audio_stats']['frames'] == 192000
    for duck in (False, True):
        cli('mix-' + str(duck).lower(), ['music', 'mix', *base, '--voice-asset-id', ids['voice'],
            '--music-asset-id', 'asset_bed', '--duration-seconds', str(clip_duration), '--music-gain-db', '-12',
            '--new-asset-id', 'asset_mix_duck' if duck else 'asset_mix_plain', *(['--duck'] if duck else [])])

    source_srt = output / 'source.srt'
    source_srt.write_text('1\n00:00:00,200 --> 00:00:03,100\n从本地素材开始，生成可编辑的视频。\n\n'
                           '2\n00:00:03,100 --> 00:00:07,300\n原声、字幕和配乐均可独立调整。\n', encoding='utf-8')
    translated = cli('translate-srt-bilingual', ['translate', 'subtitles', *base,
        '--pack', packs / 'opus-zh-en-cpu-int8', '--from', 'zh-Hans', '--to', 'en',
        '--input', source_srt, '--output', 'exports/bilingual.srt', '--mode', 'bilingual'])['data']
    assert len(translated['source_cues']) == len(translated['output_cues']) == 2
    assert [(c['start'], c['end']) for c in translated['source_cues']] == [(c['start'], c['end']) for c in translated['output_cues']]
    for target in ('zh-Hans', 'zh-Hant'):
        cli('translate-text-' + target, ['translate', 'text', *base, '--pack', packs / 'opus-zh-en-cpu-int8',
            '--from', 'en', '--to', target, '--text', 'Keep the original speech, subtitles, and background music.',
            '--output', 'exports/' + target + '.txt'])
    glossary = output / 'editing-glossary.json'
    save(glossary, {'entries': [{'source': 'background music', 'target': 'BGM', 'variants': ['背景音乐']}]})
    glossed = cli('translate-glossary', ['translate', 'text', *base, '--pack', packs / 'opus-zh-en-cpu-int8',
        '--from', 'en', '--to', 'zh-Hans', '--text', 'Keep the background music.', '--glossary', glossary,
        '--output', 'exports/glossary.txt'])['data']
    assert 'BGM' in glossed['translations'][0] and glossed['glossary_edits']
    unordered = output / 'unordered-overlap.srt'
    unordered.write_text('1\n00:00:03,001 --> 00:00:04,999\n保留背景音乐。\n\n'
                         '2\n00:00:00,123 --> 00:00:02,456\n请先预览视频。\n\n'
                         '3\n00:00:01,111 --> 00:00:02,789\n再导出工程。\n', encoding='utf-8')
    unusual = cli('translate-unordered-overlap', ['translate', 'subtitles', *base,
        '--pack', packs / 'opus-zh-en-cpu-int8', '--from', 'zh-Hans', '--to', 'en',
        '--input', unordered, '--output', 'exports/unordered.srt'])['data']
    times = [(c['start'], c['end']) for c in unusual['output_cues']]
    assert times == [(3.001, 4.999), (0.123, 2.456), (1.111, 2.789)]
    stamps = [line for line in Path(unusual['output']).read_text('utf8').splitlines() if ' --> ' in line]
    assert stamps == ['00:00:03,001 --> 00:00:04,999', '00:00:00,123 --> 00:00:02,456', '00:00:01,111 --> 00:00:02,789']

    image = ROOT / 'docs/assets/release-v0.1.0-alpha.3-r1/input/card-1.png'
    license_file = image.with_name('LICENSE.txt')
    art = cli('ingest-cc0-demo-art', ['media', 'ingest', *base, '--input', image,
        '--asset-id', 'asset_card', '--license-spdx', 'CC0-1.0', '--creator', 'Agent Video Kit contributors',
        '--source-url', 'local://community-demo/field-art', '--license-url', license_file, '--evidence', license_file,
        '--verification-status', 'verified', '--permitted-use', 'commercial_ad'])['data']['asset']
    operations = [
        dict(op='update_sequence', sequence_id='seq_main', patch=dict(canvas=dict(width=360, height=640))),
        dict(op='append_clip', track_id='track_video_1', asset_id=art['id'], source_in_tick=0,
             source_out_tick=1080000, duration_tick=1080000),
        dict(op='append_clip', track_id='track_audio_1', asset_id='asset_mix_duck', source_in_tick=0,
             source_out_tick=1080000, duration_tick=1080000),
        dict(op='add_track', track_id='track_sfx', kind='audio'),
        dict(op='add_track', track_id='track_subtitle_1', kind='subtitle'),
        dict(op='append_clip', track_id='track_sfx', asset_id=ids['sfx'], source_in_tick=0,
             source_out_tick=9000, duration_tick=9000, timeline_start_tick=720000),
    ]
    for i, cue in enumerate(translated['output_cues']):
        start, duration = round(cue['start'] * 90000), round((cue['end'] - cue['start']) * 90000)
        operations.append(dict(op='append_clip', track_id='track_subtitle_1', generator=dict(type='text'),
            source_in_tick=0, source_out_tick=duration, duration_tick=duration, timeline_start_tick=start,
            subtitle=dict(text=cue['text'], style=dict(font_asset_id=ids['font_sc'], fontsize=23, fontcolor='#FFFFFF',
                                                      max_width=310, line_spacing=4,
                                                      x='(w-text_w)/2', y='h-text_h-117', borderw=2, bordercolor='#111111'))))
    operations.append(dict(op='add_track', track_id='track_title_tc', kind='subtitle'))
    operations.append(dict(op='append_clip', track_id='track_title_tc', generator=dict(type='text'),
        source_in_tick=0, source_out_tick=1080000, duration_tick=1080000,
        subtitle=dict(text='本機離線配音 · 字幕翻譯 · 配樂', style=dict(font_asset_id=ids['font_tc'], fontsize=20,
                     max_width=310, fontcolor='#FFFFFF', x='(w-text_w)/2', y='75', borderw=1, bordercolor='#111111'))))
    changes = output / 'changes.json'
    save(changes, {'sequence_id': 'seq_main', 'operations': operations})
    cli('compose-demo', ['timeline', 'compose', *base, '--input', changes])
    cli('look-demo', ['look', 'apply', *base, '--id', 't3-kodak-gold-200', '--global', '--strength', '0.5'])
    cli('validate-project', ['validate', *base])
    cli('policy-audit', ['policy', 'audit', *base])
    cli('preview', ['preview', 'frame', *base, '--frame', '90', '--height', '640'])
    video = project / 'renders/community-demo.mp4'
    cli('render-demo', ['render', *base, '--output', video, '--width', '360', '--height', '640'])
    cli('quality', ['quality', 'check', *base, '--input', video, '--require-audio', '--width', '360', '--height', '640'])
    cli('export-package', ['convert', 'export', *base, '--target-format', 'package', '--output', output / 'demo.aevpkg.zip'])
    cli('import-package', ['convert', 'import', '--input', output / 'demo.aevpkg.zip', '--output', output / 'restored'])
    cli('restored-validate', ['validate', '--project', output / 'restored'])
    probe = subprocess.run(['ffprobe', '-v', 'error', '-count_frames', '-show_streams', '-show_format', '-of', 'json', str(video)], capture_output=True, check=True, timeout=90)
    save(output / 'probe.json', json.loads(probe.stdout))
    visual = next(s for s in json.loads(probe.stdout)['streams'] if s['codec_type'] == 'video')
    assert int(visual['nb_read_frames']) == 360 and visual['width'] == 360 and visual['height'] == 640
    decode = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(video), '-f', 'null', '-'], capture_output=True, timeout=90)
    (output / 'decode.log').write_bytes(decode.stdout + decode.stderr)
    assert decode.returncode == 0

    protected = [project / 'project.json', video, packs / 'kokoro-zh-en-int8/models/kokoro/tokens.txt']
    before = {str(p): sha(p) for p in protected}
    cli('refuse-existing-output', ['music', 'prepare', *base, '--asset-id', ids['music'],
        '--duration-seconds', '12', '--output', prepared['asset']['uri']], error='ARGUMENT_INVALID')
    cli('refuse-missing-pack', ['model-pack', 'verify', '--id', 'kokoro-zh-en-int8', '--pack', output / 'missing-pack'],
        error='MODEL_PACK_MANIFEST_MISMATCH')
    cli('refuse-unknown-voice', ['voice', 'synthesize', *base, '--text', '测试', '--voice', 'unknown',
        '--pack', packs / 'kokoro-zh-en-int8'], error='ARGUMENT_INVALID')
    cli('refuse-non-bilingual-pair', ['translate', 'text', *base, '--from', 'zh-Hans', '--to', 'zh-Hant', '--text', '测试',
        '--pack', packs / 'opus-zh-en-cpu-int8', '--output', 'exports/refused.txt'], error='ARGUMENT_INVALID')
    fixture = output / 'fault-pack'
    def fixture_copy(source, target):
        if Path(source).name == 'tokens.txt':
            return shutil.copyfile(source, target)
        os.link(source, target)
        return target
    shutil.copytree(packs / 'kokoro-zh-en-int8', fixture, copy_function=fixture_copy)
    token = fixture / 'models/kokoro/tokens.txt'
    saved = token.read_bytes()
    token.unlink()
    cli('refuse-missing-model-file', ['model-pack', 'verify', '--id', 'kokoro-zh-en-int8', '--pack', fixture], error='MODEL_PACK_FILE_MISMATCH')
    token.write_bytes(b'changed fixture only')
    cli('refuse-tampered-model-file', ['model-pack', 'verify', '--id', 'kokoro-zh-en-int8', '--pack', fixture], error='MODEL_PACK_FILE_MISMATCH')
    token.write_bytes(saved)
    (fixture / 'extra.txt').write_text('extra fixture', encoding='utf8')
    cli('refuse-extra-model-file', ['model-pack', 'verify', '--id', 'kokoro-zh-en-int8', '--pack', fixture], error='MODEL_PACK_EXTRA_FILES')
    assert before == {str(p): sha(p) for p in protected}
    report = dict(status='passed-with-open-review-limits', checked_at_utc=datetime.now(timezone.utc).isoformat(),
                   cli_version='0.1.3', installed=str(installed), source_fallback=False, commands=len(commands),
                   counts=cap['community_materials']['counts'], verified_bundled_materials=359,
                   named_voices=103, actual_model_inferences=8, actual_audition_voices=3, video=str(video), video_sha256=sha(video),
                   video_frames=360, video_fps='30/1', video_seconds=12, video_full_decode=True,
                   subtitle_cue_count=2, subtitle_millisecond_timing_preserved=True,
                   unordered_and_overlapping_subtitle_timing_and_order_preserved=True,
                   original_stems_and_protected_files_unchanged=True, package_roundtrip_validated=True,
                   browser_invoked=False, virtualization_invoked=False, product_network=False,
                   human_listening=False, human_semantic_translation_acceptance=False,
                   full_capcut_parity=False, voice_output_commercial_rights_automatically_granted=False)
    save(output / 'verification.json', report)
    print(json.dumps(report, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    try:
        main()
    except BaseException as exc:
        print(json.dumps({'status': 'failed-preserved', 'error': str(exc)}, ensure_ascii=False), flush=True)
        raise
