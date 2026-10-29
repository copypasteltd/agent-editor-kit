"""Independent installed58 media/edit/render replay; explicit synthetic search response."""
import argparse
import contextlib
import hashlib
import io
import json
from pathlib import Path
import shutil
import subprocess
import sys
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', required=True)
    parser.add_argument('--installed', type=Path, required=True)
    args = parser.parse_args()
    assert args.run.replace('-', '').isalnum() and sys.dont_write_bytecode
    installed = args.installed.resolve()
    assert installed.is_relative_to((ROOT/'local/agent-ffmpeg/v0.1.0-alpha.4-local.56').resolve())
    assert (installed/'run.py').is_file()
    source = ROOT/'product/src/ai_ad_editor'
    package = installed/'site/ai_ad_editor'
    assert sys.flags.isolated and all(Path(p).resolve() != source.parent.resolve() for p in sys.path if p)
    source_pins = {p.name:sha(p) for p in source.glob('*.py')}
    assert len(source_pins) == 281 and source_pins == {p.name:sha(p) for p in package.glob('*.py')}
    gate_base = ROOT/'docs/validation/evidence/ad-content-uniqueness-20261029-r1'
    for group, count in [('bootstrap', 31), ('selection', 57), ('control', 19)]:
        gate = json.loads((gate_base/('installed58-'+group+'-r1')/'verification.json').read_bytes())
        assert gate['status'] == 'passed' and gate['tests'] == count and gate['frozen_equal']
        assert gate['source_and_installed_equal'] and Path(gate['installed']).resolve() == installed
    sys.path.insert(0, str(package.parent))
    import ai_ad_editor
    from ai_ad_editor.cli import main as cli_main
    from ai_ad_editor.project import load_project
    from ai_ad_editor.ad_selection import prepare
    from PIL import Image, ImageDraw
    assert ai_ad_editor.VERSION == '0.1.58'
    assert Path(ai_ad_editor.__file__).resolve() == package/'__init__.py'
    pins = {p.name:sha(p) for p in package.glob('*.py')}
    protected = {p:sha(p) for p in [ROOT/'agent-ffmpeg-local-install-manifest.json',
                                   ROOT/'local/agent-ffmpeg/runtime.json']}
    base = ROOT/'docs/validation/evidence/ad-content-uniqueness-20261029-r1'
    out = base/('installed-content-case-'+args.run)
    work = ROOT/'local/agent-ffmpeg'/('ad-content-installed58-'+args.run)
    out.mkdir(exist_ok=False)
    work.mkdir(exist_ok=False)
    shutil.copyfile(__file__, out/'executed-runner.py')
    project, replay = work/'project', work/'replay'
    calls = []

    def cli(name, *argv):
        stream = io.StringIO()
        with contextlib.redirect_stdout(stream):
            code = cli_main(list(map(str, argv)))
        raw = stream.getvalue()
        (out/(name+'.stdout')).write_text(raw, encoding='utf-8')
        calls.append(dict(name=name, argv=list(map(str, argv)), exit_code=code,
                          stdout_sha256=hashlib.sha256(raw.encode()).hexdigest()))
        save(out/'calls.json', calls)
        assert code == 0, (name, raw[-2000:])
        result = json.loads(raw)
        assert result['ok'] and result['provenance']['cli_version'] == '0.1.58'
        print(json.dumps(dict(name=name, exit_code=code)), flush=True)
        return result['data']

    ffmpeg = shutil.which('ffmpeg')
    assert ffmpeg

    def rgba(name, movie):
        result = subprocess.run([ffmpeg, '-nostdin', '-v', 'error', '-i', str(movie),
            '-an', '-pix_fmt', 'rgba', '-f', 'rawvideo', 'pipe:1'], cwd=ROOT,
            capture_output=True, timeout=600, creationflags=subprocess.CREATE_NO_WINDOW)
        (out/(name+'.stderr')).write_bytes(result.stderr)
        assert result.returncode == 0, result.stderr[-1500:]
        (work/(name+'.rgba')).write_bytes(result.stdout)
        return result.stdout

    try:
        cli('init', 'project', 'init', project)
        source_note = work/'SOURCE.txt'
        source_note.write_text('Original diagnostic cards created by this recorded harness; CC0-1.0. '
            'picture_alias.png is an exact byte copy of picture.png. No AI generation.\n', encoding='utf-8')
        for name, color in [('picture', (24, 56, 112)), ('other', (196, 112, 32))]:
            image = Image.new('RGB', (320, 180), color)
            draw = ImageDraw.Draw(image)
            draw.rectangle((0, 0, 319, 8), fill='white')
            draw.text((14, 30), 'BLUE SOURCE' if name == 'picture' else 'AMBER SOURCE', fill='white')
            image.save(work/(name+'.png'))
        shutil.copyfile(work/'picture.png', work/'picture_alias.png')
        assets = {}
        for aid in ['picture', 'picture_alias', 'other']:
            data = cli('ingest-'+aid, 'media', 'ingest', '--project', project, '--input', work/(aid+'.png'),
                '--asset-id', aid, '--license-spdx', 'CC0-1.0', '--verification-status', 'verified',
                '--creator', 'Agent Editor Kit diagnostic harness', '--evidence', source_note)
            assets[aid] = data['asset']
        font = package/'material_data/fonts/noto-sans-sc-variable.ttf'
        cli('ingest-font', 'media', 'ingest', '--project', project, '--input', font, '--asset-id', 'font',
            '--license-spdx', 'OFL-1.1', '--verification-status', 'verified', '--creator', 'Adobe; Google Noto',
            '--evidence', package/'material_data/licenses/google-notosanssc.txt')
        assert assets['picture']['sha256'] == assets['picture_alias']['sha256']
        assert assets['picture']['sha256'] != assets['other']['sha256']
        request = dict(queries=[dict(id='hook', text='synthetic hook query'), dict(id='proof', text='synthetic proof query')],
            brief=dict(id='content_case', product='Content deduplication', audience='Editors', cta='Review sources',
                caption_style=dict(font_asset_id='font', font_ratio=.08),
                shots=[dict(id='hook', text='Distinct source', weight=1), dict(id='proof', text='Original source', weight=1)],
                variants=[dict(id='wide', canvas=dict(width=320, height=180), duration_seconds=4)]))
        input_path = project/'request.json'
        save(input_path, request)
        initial = (project/'project.json').read_bytes()
        prepared = prepare(load_project(project)[1], request)

        def hit(aid, score):
            return dict(asset_id=aid, source_sha256=assets[aid]['sha256'], decision_score=score,
                editable_reference=dict(asset_id=aid, source_in_tick=0, point_sample_only=True),
                rights_verification_status='verified', preview_asset_id=None)

        response = dict(task='text', query_mode='clauses', index_id='synthetic-fixture', calibration_id='synthetic-cal',
            network='disabled', results=[dict(query=query, calibration_id='synthetic-cal', decision='calibrated_match', hits=hits)
                for query, hits in zip(prepared['queries'], [[hit('picture_alias', .99), hit('other', .8)], [hit('picture', .9)]])])
        save(out/'explicit-synthetic-search-response.json', response)
        plans = {}
        for mode in ['default-content', 'explicit-id-only']:
            if mode == 'explicit-id-only':
                request['unique_content'] = False
                save(input_path, request)
            with patch('ai_ad_editor.semantic.search', return_value=response):
                plans[mode] = cli('select-'+mode, 'ad', 'select', '--project', project, '--input', input_path,
                    '--output', project/('validation/'+mode+'.json'), '--index-id', 'synthetic-fixture',
                    '--calibration-id', 'synthetic-cal')
            assert (project/'project.json').read_bytes() == initial
        default_ids = [x['asset_id'] for x in plans['default-content']['selection']['selected']]
        legacy_ids = [x['asset_id'] for x in plans['explicit-id-only']['selection']['selected']]
        assert default_ids == ['other', 'picture'], default_ids
        assert legacy_ids == ['picture_alias', 'picture'], legacy_ids
        built = cli('build', 'ad', 'build', '--project', project, '--input', project/'validation/default-content.json')
        sequence = built['sequence_ids'][0]
        movie = project/'renders/content.mp4'
        cli('render', 'render', '--project', project, '--sequence-id', sequence, '--output', movie)
        archive = project/'exports/content.zip'
        cli('export', 'convert', 'export', '--project', project, '--target-format', 'package', '--output', archive)
        cli('import', 'convert', 'import', '--input', archive, '--output', replay)
        replay_movie = replay/'renders/content.mp4'
        cli('replay', 'render', '--project', replay, '--sequence-id', sequence, '--output', replay_movie)
        frames = rgba('rendered', movie)
        assert frames == rgba('replayed', replay_movie)
        stride = 320*180*4
        assert len(frames) == 120*stride
        for frame, amber in [(0, True), (59, True), (60, False), (119, False)]:
            offset = frame*stride+(80*320+160)*4
            red, green, blue = frames[offset:offset+3]
            assert (red > blue+80) if amber else (blue > red+50), (frame, red, green, blue)
        assert pins == {p.name:sha(p) for p in package.glob('*.py')}
        assert source_pins == pins == {p.name:sha(p) for p in source.glob('*.py')}
        assert protected == {p:sha(p) for p in protected}
        report = dict(status='passed', cli_version='0.1.58', real_media_and_rights=True,
            independent_installed_case=True, installed=str(installed), source_fallback=False,
            source_and_installed_equal=True,
            synthetic_service_response=True, neural_inference=False, semantic_quality_accepted=False,
            default_selected=default_ids, explicit_id_only_selected=legacy_ids,
            source_alias_SHA256_equal=True, complete_RGBA_replay_equal=True,
            complete_RGBA_bytes=len(frames), frames=120, fps=30, video_only_case=True,
            first_and_last_frame_of_each_shot_color_checked=True, frozen_equal=True,
            registered56_unchanged=True, installed58_accepted=False, movie=str(movie),
            sequence_id=sequence, source_file_hashes=pins)
        save(out/'verification.json', report)
        print(json.dumps({k:v for k,v in report.items() if k!='source_file_hashes'}), flush=True)
    except BaseException as exc:
        save(out/'verification.json', dict(status='failed', error=repr(exc), synthetic_service_response=True,
            neural_inference=False, semantic_quality_accepted=False))
        raise


if __name__ == '__main__':
    main()
