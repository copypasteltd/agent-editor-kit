"""Build licensed, real bundled audio/fonts from preserved upstream inputs.

Only a new output directory is accepted. Development downloads are separate;
this builder and the product never fetch missing resources implicitly.
"""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import argparse
import hashlib
import json
import re
import shutil
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / 'product/.runtime/materials-20261024'
DOWNLOADS = WORK / 'downloads'
RESEARCH = ROOT / 'sources/materials-20261024/research'
FONT_REF = 'e7db6ca603fd4862010383ff17ffd6cc4ffac1c0'


def sha(path):
    with path.open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()


def dump(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')


def slug(value):
    return re.sub(r'[^a-z0-9]+', '-', value.lower()).strip('-')


def run(command):
    result = subprocess.run(command, capture_output=True, text=True, encoding='utf-8',
                            errors='replace', timeout=120, creationflags=subprocess.CREATE_NO_WINDOW)
    if result.returncode:
        raise ValueError(result.stderr[-2000:])
    return result.stdout


def probe(path):
    if path.suffix.lower() == '.ttf':
        return {'family': 'Noto Sans SC' if 'sc-' in path.name else 'Noto Sans TC',
                'format': 'variable-TrueType', 'languages': ['en', 'zh-Hans' if 'sc-' in path.name else 'zh-Hant']}
    data = json.loads(run(['ffprobe', '-v', 'error', '-show_entries',
                          'format=duration:stream=codec_type,codec_name,sample_rate,channels',
                          '-of', 'json', str(path)]))
    stream = next(s for s in data['streams'] if s['codec_type'] == 'audio')
    return {'duration_seconds': float(data['format']['duration']), 'codec': stream['codec_name'],
            'sample_rate': int(stream['sample_rate']), 'channels': int(stream['channels'])}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--fonts', type=Path, default=WORK / 'google-fonts-r1')
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    for directory in ('audio', 'fonts', 'licenses', 'sources'):
        (output / directory).mkdir()
    records, collections = [], []
    encoder = run(['ffmpeg', '-version']).splitlines()[0]

    def collection(ident, *, archive, source, page, creator, license, title, notice=None, attribution=None):
        license_url = {'CC0-1.0': 'https://creativecommons.org/publicdomain/zero/1.0/',
                       'CC-BY-4.0': 'https://creativecommons.org/licenses/by/4.0/',
                       'OFL-1.1': 'https://openfontlicense.org/'}[license]
        attribution = attribution or f'{title} by {creator}; {license}; {source}'
        notice_path = 'licenses/' + ident + '.txt'
        text = (f'{title}\nCreator: {creator}\nSource: {source}\nLicense: {license}\n'
                f'License URL: {license_url}\nAttribution: {attribution}\n'
                'This source is attribution metadata, never a runtime download address.\n')
        (output / notice_path).write_bytes(text.encode('utf-8') + b'\n' + (notice or b''))
        source_path = 'sources/' + ident + ('.html' if page.suffix == '.html' else '.txt')
        shutil.copyfile(page, output / source_path)
        row = dict(id=ident, name=title, creator=creator, source_url=source,
                   archive_name=archive.name, archive_sha256=sha(archive),
                   license=dict(spdx=license, url=license_url, creator=creator, attribution=attribution,
                                obligations=(['Retain attribution, source and license; indicate edits.'] if license == 'CC-BY-4.0'
                                             else ['Retain OFL copyright and license when redistributing the font; do not sell the font by itself.'] if license == 'OFL-1.1' else [])),
                   notice_path=notice_path, notice_sha256=sha(output / notice_path),
                   evidence_path=source_path, evidence_sha256=sha(output / source_path))
        collections.append(row)
        return row

    def asset(col, ident, title, data, suffix, *, kind, category, original, tags, prefix_zh, prefix_tw, transform=None):
        path = ('fonts/' if kind == 'font' else 'audio/') + ident + suffix
        target = output / path
        if target.exists():
            raise ValueError('Duplicate output: ' + path)
        original_sha = hashlib.sha256(data).hexdigest()
        if transform:
            staged = WORK / 'material-transcode' / (ident + '.wav')
            staged.parent.mkdir(parents=True, exist_ok=True)
            if not staged.exists():
                staged.write_bytes(data)
            assert sha(staged) == original_sha
            run(['ffmpeg', '-v', 'error', '-nostdin', '-n', '-i', str(staged), '-vn', '-c:a', 'libvorbis', '-q:a', '5', str(target)])
        else:
            target.write_bytes(data)
        target_sha = sha(target)
        duplicate = next((r for r in records if r['sha256'] == target_sha), None)
        if duplicate:
            if duplicate['collection_id'] != col['id']:
                raise ValueError('Identical bytes from different licensing collections require manual review')
            duplicate.setdefault('aliases', []).append({'id': ident, 'name': title, 'original': original})
            target.unlink()
            return
        row = dict(id=ident, name=title, name_zh=prefix_zh + title, name_zh_tw=prefix_tw + title,
                   kind=kind, category=category, tags=list(dict.fromkeys(tags)), collection_id=col['id'],
                   path=path, bytes=target.stat().st_size, sha256=target_sha,
                   original=dict(member=original, sha256=original_sha, bytes=len(data)),
                   transformation=({'engine': encoder, 'args': ['-c:a', 'libvorbis', '-q:a', '5'],
                                    'lossy': True} if transform else {'mode': 'byte-copy'}))
        records.append(row)

    for key, filename, title, kind, prefix_zh, prefix_tw, count in [
        ('music-jingles', 'kenney_music-jingles.zip', 'Music Jingles', 'jingle', '短乐 / ', '短樂 / ', 85),
        ('interface-sounds', 'kenney_interface-sounds.zip', 'Interface Sounds', 'sfx', '界面音效 / ', '介面音效 / ', 100),
        ('impact-sounds', 'kenney_impact-sounds.zip', 'Impact Sounds', 'sfx', '撞击与脚步 / ', '撞擊與腳步 / ', 130),
    ]:
        archive = DOWNLOADS / filename
        with zipfile.ZipFile(archive) as zipped:
            assert zipped.testzip() is None
            col = collection('kenney-' + key, archive=archive, source='https://kenney.nl/assets/' + key,
                             page=RESEARCH / ('kenney-' + key + '.html'), creator='Kenney',
                             license='CC0-1.0', title=title, notice=zipped.read('License.txt'))
            members = [name for name in zipped.namelist() if name.startswith('Audio/') and name.endswith('.ogg')]
            assert len(members) == count
            for member in sorted(members):
                stem = Path(member).stem
                words = re.sub(r'([a-z])([A-Z])', r'\1 \2', stem).replace('_', ' ')
                asset(col, 'kenney-' + key + '-' + slug(stem), stem, zipped.read(member), '.ogg', kind=kind,
                      category=key, original=member, tags=[kind, key, words, prefix_zh.strip(' /'), prefix_tw.strip(' /'), *Path(member).parts[1:-1]],
                      prefix_zh=prefix_zh, prefix_tw=prefix_tw)

    for key, filename, page_slug, title, creator, genre in [
        ('oga-action', 'oga-action.zip', '5-chiptunes-action', '5 Chiptunes Action', 'Juhani Junkala (SubspaceAudio)', 'chiptune'),
        ('oga-gt-rpg', 'oga-gt-rpg.zip', 'gt-rpg-soundtrack', 'G&T RPG soundtrack', 'Juhani Junkala', 'orchestral'),
    ]:
        archive = DOWNLOADS / filename
        with zipfile.ZipFile(archive) as zipped:
            assert zipped.testzip() is None
            notices = [n for n in zipped.namelist() if n.lower().endswith(('.txt', '.md')) and not n.startswith('__MACOSX/')]
            notice = b'\n\n'.join(zipped.read(n) for n in notices)
            col = collection(key, archive=archive, source='https://opengameart.org/content/' + page_slug,
                             page=RESEARCH / ('oga-action.html' if key == 'oga-action' else 'oga-gt-rpg-soundtrack.html'),
                             creator=creator, license='CC0-1.0' if key == 'oga-action' else 'CC-BY-4.0',
                             title=title, notice=notice)
            members = [n for n in zipped.namelist() if Path(n).suffix.lower() in {'.wav', '.ogg', '.mp3'} and not n.startswith('__MACOSX/')]
            # Count tracks once, even if an archive includes multiple encodings.
            selected = {}
            for name in sorted(members, key=lambda n: ({'.ogg': 0, '.wav': 1, '.mp3': 2}[Path(n).suffix.lower()], n)):
                selected.setdefault(Path(name).stem.casefold(), name)
            assert len(selected) == (5 if key == 'oga-action' else 37), (key, len(selected))
            for member in sorted(selected.values()):
                title = Path(member).stem.replace('Juhani Junkala [Retro Game Music Pack] ', '')
                asset(col, key + '-' + slug(title), title, zipped.read(member),
                      '.ogg' if Path(member).suffix.lower() == '.wav' else Path(member).suffix.lower(), kind='music',
                      category=genre, original=member, tags=['music', 'BGM', genre, title, '背景音乐', '背景音樂', '游戏', '遊戲'],
                      prefix_zh='配乐 / ', prefix_tw='配樂 / ', transform=Path(member).suffix.lower() == '.wav')

    for key, filename, title, creator, category, tags in [
        ('oga-searching', 'Searching.ogg', 'Searching', 'yd', 'ambient', ['drone', 'dark', 'warm', 'electronic']),
        ('oga-mindstream', 'DST-MindStream.mp3', 'MindStream', 'DST', 'ambient', ['techno', 'chill', 'loop']),
    ]:
        archive = DOWNLOADS / filename
        col = collection(key, archive=archive, source='https://opengameart.org/content/' + key.removeprefix('oga-'),
                         page=RESEARCH / (key + '.html'), creator=creator, license='CC0-1.0', title=title)
        asset(col, key, title, archive.read_bytes(), archive.suffix, kind='music', category=category,
              original=filename, tags=['music', 'BGM', 'ambient', '背景音乐', '背景音樂', *tags],
              prefix_zh='配乐 / ', prefix_tw='配樂 / ')

    for slug_, family, ident, zh, tw in [('notosanssc', 'NotoSansSC', 'noto-sans-sc-variable', '简体中文黑体 / ', '簡體中文黑體 / '),
                                       ('notosanstc', 'NotoSansTC', 'noto-sans-tc-variable', '繁体中文黑体 / ', '繁體中文黑體 / ')]:
        directory = args.fonts.resolve() / 'ofl' / slug_
        font = directory / (family + '[wght].ttf')
        col = collection('google-' + slug_, archive=font, source='https://github.com/google/fonts/tree/' + FONT_REF + '/ofl/' + slug_,
                         page=directory / 'METADATA.pb', creator='Adobe (copyright); Google (Noto family)', license='OFL-1.1', title=family,
                         notice=(directory / 'OFL.txt').read_bytes())
        col['source_commit'] = FONT_REF
        asset(col, ident, family, font.read_bytes(), '.ttf', kind='font', category='sans-serif',
              original=font.name, tags=['font', 'subtitle', 'title', 'zh', 'zh-Hans', 'zh-Hant', 'en', '中文', '字幕', '字体', '字體'],
              prefix_zh=zh, prefix_tw=tw)

    assert len({r['id'] for r in records}) == len(records)
    assert len({r['sha256'] for r in records}) == len(records), 'Identical resource bytes counted twice'
    with ThreadPoolExecutor(max_workers=4) as pool:
        for row, metadata in zip(records, pool.map(lambda r: probe(output / r['path']), records)):
            row['media'] = metadata
    voices = [dict(speaker_id=int(sid), id=name, language='zh' if name.startswith('z') else 'en',
                   gender='female' if name[1:2] == 'f' else 'male',
                   description='Upstream named voice; individual naturalness and pronunciation need audition.')
              for sid, name in re.findall(r'<td>(\d+) -&gt; ([a-z]+_[a-z0-9]+)</td>', (RESEARCH / 'sherpa-kokoro.html').read_text('utf-8'))]
    assert len(voices) == 103 and {r['speaker_id'] for r in voices} == set(range(103))
    dump(output / 'voices.json', {'engine': 'kokoro-sherpa-cpu-v1', 'model_id': 'kokoro-zh-en-int8',
                                'source_url': 'https://k2-fsa.github.io/sherpa/onnx/tts/all/Chinese-English/kokoro-multi-lang-v1_1.html',
                                'voices': voices})
    dump(output / 'catalog.json', dict(catalog_version='1.0.0', generated_at_utc=datetime.now(timezone.utc).isoformat(),
                                      development_downloads_only=True, runtime_network=False,
                                      counts={k: sum(r['kind'] == k for r in records) for k in ('music', 'jingle', 'sfx', 'font')},
                                      collections=collections, records=sorted(records, key=lambda r: r['id'])))
    print(json.dumps({'status': 'built', 'count': len(records), 'output': str(output),
                      'catalog_sha256': sha(output / 'catalog.json'), 'voices': len(voices)}), flush=True)


if __name__ == '__main__':
    main()
