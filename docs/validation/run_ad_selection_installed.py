"""Accept actual GPU ad selection through the isolated installed CLI54 only."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT/'docs/validation/evidence/ad-selection-20261029-r1'


def load(path):
    return json.loads(Path(path).read_bytes())


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def save(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n',
                          encoding='utf-8', newline='\n')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--installed', required=True, type=Path)
    parser.add_argument('--run', required=True)
    parser.add_argument('--source-case', type=Path, default=BASE/'case-r2/verification.json')
    args = parser.parse_args()
    assert sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode
    assert args.run.replace('-', '').isalnum()
    installed = args.installed.resolve()
    source = ROOT/'product/src/ai_ad_editor'
    package = installed/'site/ai_ad_editor'
    before = {p.name: sha(p) for p in source.glob('*.py')}
    assert len(before) == 281 and before == {p.name: sha(p) for p in package.glob('*.py')}
    source_case = load(args.source_case)
    assert source_case['status'] == 'passed' and source_case['full_project_replay_equal']
    for group, count in [('selection', 45), ('semantic', 104)]:
        gate = load(BASE/('installed-'+group+'-r1')/'verification.json')
        assert gate['status'] == 'passed' and gate['tests'] == count and gate['frozen_equal']
        assert Path(gate['installed']).resolve() == installed
    out = BASE/('installed-case-'+args.run)
    out.mkdir(parents=True, exist_ok=False)
    (out/'executed-runner.py').write_bytes(Path(__file__).read_bytes())
    work = ROOT/'local/agent-ffmpeg'/('ad-selection-installed-20261029-'+args.run)
    work.mkdir(parents=True, exist_ok=False)
    original_work = ROOT/'local/agent-ffmpeg/ad-selection-20261029-r2'
    setup = load(BASE/'complete-r2/verification.json')
    assert sha(original_work/'request.json') == setup['heldout_queries_sha256']
    project, replay = work/'project', work/'replay'
    calls = []
    env = os.environ.copy()
    env['TEMP'] = env['TMP'] = str(ROOT/'local/tmp')

    def run(name, argv, *, binary=False):
        argv = list(map(str, argv))
        result = subprocess.run(argv, cwd=ROOT, env=env, capture_output=True,
            timeout=1200, creationflags=subprocess.CREATE_NO_WINDOW)
        (work if binary else out).joinpath(name+('.raw' if binary else '.stdout')).write_bytes(result.stdout)
        (out/(name+'.stderr')).write_bytes(result.stderr)
        calls.append(dict(name=name, argv=argv, exit_code=result.returncode,
            stdout_sha256=hashlib.sha256(result.stdout).hexdigest()))
        save(out/'calls.json', calls)
        print(json.dumps(dict(name=name, exit_code=result.returncode)), flush=True)
        assert result.returncode == 0, (name, result.stdout[-1500:], result.stderr[-1500:])
        return result.stdout

    def cli(name, *argv):
        value = json.loads(run(name, [sys.executable, '-I', '-S', '-B', '-u', '-X', 'utf8',
                                     installed/'run.py', *argv]))
        assert value['ok'] and value['provenance']['cli_version'] == '0.1.54'
        return value['data']

    try:
        cli('import-original', 'convert', 'import', '--input', original_work/'project/exports/editable.zip',
            '--output', project)
        moved = cli('upgrade-semantic', 'project', 'upgrade-semantic', '--project', project,
            '--adapter-id', 'source54', '--new-adapter-id', 'installed54', '--id-prefix', 'i54',
            '--index-id', 'visual54full', '--timeout-seconds', '600')
        assert moved['implementation_bytes_identical'] and moved['model_forward_calls'] == 0
        index_id = next(x['target'] for x in moved['index_mappings'] if x['source'] == 'visual54full')
        calibration_id = next(x['target'] for x in moved['calibration_mappings'] if x['source'] == 'full54cuda')
        request = load(original_work/'request.json')
        # Only campaign identity changes to avoid overwriting imported editable sequences.
        # Queries, captions, variants, expected labels and calibration remain frozen.
        request['brief']['id'] = 'installeddemo'
        save(work/'request.json', request)
        original_project = (project/'project.json').read_bytes()
        selected = cli('select', 'ad', 'select', '--project', project, '--input', work/'request.json',
            '--output', project/'validation/installed-selected.json', '--index-id', index_id,
            '--calibration-id', calibration_id, '--kind', 'image', '--device', 'cuda',
            '--timeout-seconds', '900')
        assert (project/'project.json').read_bytes() == original_project
        actual = {r['shot_id']: r['asset_id'] for r in selected['selection']['selected']}
        expected_record = load(BASE/'setup-r2/heldout-expected.json')
        expected = {q['id']: expected_record[q['id']] for q in request['queries']}
        assert actual == expected
        cli('build', 'ad', 'build', '--project', project, '--input', project/'validation/installed-selected.json')
        for variant in ('wide', 'vertical'):
            cli('render-'+variant, 'render', '--project', project,
                '--sequence-id', 'ad_installeddemo_'+variant+'_sequence',
                '--output', project/('renders/installed-'+variant+'.mp4'))
        exported = project/'exports/installed-editable.zip'
        cli('export', 'convert', 'export', '--project', project, '--output', exported, '--target-format', 'package')
        cli('import-replay', 'convert', 'import', '--input', exported, '--output', replay)
        cli('render-replay', 'render', '--project', replay, '--sequence-id', 'ad_installeddemo_wide_sequence',
            '--output', replay/'renders/installed-wide.mp4')
        ffmpeg = shutil.which('ffmpeg')
        assert ffmpeg

        def stream(name, path, audio=False):
            tail = (['-map', '0:a:0', '-vn', '-c:a', 'pcm_f32le', '-f', 'f32le'] if audio else
                    ['-map', '0:v:0', '-an', '-pix_fmt', 'rgb24', '-f', 'rawvideo'])
            return run(name, [ffmpeg, '-nostdin', '-v', 'error', '-i', path, *tail, 'pipe:1'], binary=True)

        movie = project/'renders/installed-wide.mp4'
        replay_movie = replay/'renders/installed-wide.mp4'
        rgb, pcm = stream('original-rgb', movie), stream('original-pcm', movie, True)
        assert rgb == stream('replay-rgb', replay_movie) and pcm == stream('replay-pcm', replay_movie, True)
        assert len(rgb) == 320*180*3*90 and len(pcm) > 0
        assert before == {p.name: sha(p) for p in source.glob('*.py')} == {
            p.name: sha(p) for p in package.glob('*.py')}
        save(out/'verification.json', dict(status='passed', cli_version='0.1.54', installed=str(installed),
            source_fallback=False, actual_GPU_semantic_search=True, selection=actual, renders=3,
            full_RGB_bytes=len(rgb), full_PCM_bytes=len(pcm), full_project_replay_equal=True,
            project_unchanged_by_selection=True, frozen_equal=True, registered_skill_unchanged=True,
            natural_motion_quality_accepted=False, independent_agent_benchmark=False))
    except BaseException as exc:
        save(out/'verification.json', dict(status='failed', error=repr(exc), source_fallback=False))
        raise


if __name__ == '__main__':
    main()
