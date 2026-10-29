"""Accept actual GPU ad selection through the isolated installed CLI54 only."""
import argparse
import hashlib
import json
import math
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
    global BASE
    parser = argparse.ArgumentParser()
    parser.add_argument('--installed', required=True, type=Path)
    parser.add_argument('--run', required=True)
    parser.add_argument('--source-case', type=Path)
    parser.add_argument('--source-run', default='r2')
    parser.add_argument('--cli-version', choices=('0.1.54', '0.1.55'), default='0.1.54')
    parser.add_argument('--evidence-series', default='ad-selection-20261029-r1')
    parser.add_argument('--timeout-seconds', type=float, default=1800)
    parser.add_argument('--skill-entry', type=Path, help='Optional actual unified PowerShell entry; its runtime must match --installed')
    args = parser.parse_args()
    assert sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode
    assert args.run.replace('-', '').isalnum()
    assert args.source_run.replace('-', '').isalnum() and args.evidence_series.replace('-', '').isalnum()
    assert math.isfinite(args.timeout_seconds) and 0 < args.timeout_seconds <= 3600
    BASE = ROOT/'docs/validation/evidence'/args.evidence_series
    installed = args.installed.resolve()
    source = ROOT/'product/src/ai_ad_editor'
    package = installed/'site/ai_ad_editor'
    before = {p.name: sha(p) for p in source.glob('*.py')}
    assert len(before) == 281 and before == {p.name: sha(p) for p in package.glob('*.py')}
    source_case = load(args.source_case or BASE/('case-'+args.source_run)/'verification.json')
    assert source_case['status'] == 'passed' and source_case['full_project_replay_equal']
    assert source_case['source_cli'] == args.cli_version
    groups = [('selection', 45), ('semantic', 104)]
    if args.cli_version == '0.1.55':
        groups.append(('deadline', 15))
    for group, count in groups:
        gate = load(BASE/('installed-'+group+'-r1')/'verification.json')
        assert gate['status'] == 'passed' and gate['tests'] == count and gate['frozen_equal']
        assert Path(gate['installed']).resolve() == installed
    out = BASE/('installed-case-'+args.run)
    out.mkdir(parents=True, exist_ok=False)
    (out/'executed-runner.py').write_bytes(Path(__file__).read_bytes())
    work = ROOT/'local/agent-ffmpeg'/('ad-selection-installed-20261029-'+args.run)
    work.mkdir(parents=True, exist_ok=False)
    original_work = ROOT/'local/agent-ffmpeg'/('ad-selection-20261029-'+args.source_run)
    setup_file = BASE/('complete-'+args.source_run)/'verification.json'
    if not setup_file.exists():
        setup_file = BASE/('setup-'+args.source_run)/'verification.json'
    setup = load(setup_file)
    assert sha(original_work/'request.json') == setup['heldout_queries_sha256']
    namespace = ROOT/'agent-ffmpeg-local-install-manifest.json'
    namespace_pin = sha(namespace)
    if args.skill_entry:
        entry = args.skill_entry.resolve()
        assert entry.is_file() and entry.name == 'run.ps1'
        home = entry.parent.parent.parent.parent
        config = load(home/'local/agent-ffmpeg/runtime.json')
        assert Path(config['installed_directory']).resolve() == installed
    project, replay = work/'project', work/'replay'
    calls = []
    env = os.environ.copy()
    env['TEMP'] = env['TMP'] = str(ROOT/'local/tmp')

    def run(name, argv, *, binary=False):
        argv = list(map(str, argv))
        result = subprocess.run(argv, cwd=ROOT, env=env, capture_output=True,
            timeout=args.timeout_seconds+300, creationflags=subprocess.CREATE_NO_WINDOW)
        (work if binary else out).joinpath(name+('.raw' if binary else '.stdout')).write_bytes(result.stdout)
        (out/(name+'.stderr')).write_bytes(result.stderr)
        calls.append(dict(name=name, argv=argv, exit_code=result.returncode,
            stdout_sha256=hashlib.sha256(result.stdout).hexdigest()))
        save(out/'calls.json', calls)
        print(json.dumps(dict(name=name, exit_code=result.returncode)), flush=True)
        assert result.returncode == 0, (name, result.stdout[-1500:], result.stderr[-1500:])
        return result.stdout

    def cli(name, *argv):
        argv = list(argv)
        if '--timeout-seconds' in argv:
            argv[argv.index('--timeout-seconds')+1] = str(args.timeout_seconds)
        prefix = (['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', args.skill_entry]
            if args.skill_entry else [sys.executable, '-I', '-S', '-B', '-u', '-X', 'utf8', installed/'run.py'])
        value = json.loads(run(name, [*prefix, *argv]))
        assert value['ok'] and value['provenance']['cli_version'] == args.cli_version
        return value['data']

    try:
        cli('import-original', 'convert', 'import', '--input', original_work/'project/exports/editable.zip',
            '--output', project)
        suffix = args.cli_version.rsplit('.', 1)[1]
        source_adapter = 'source'+suffix
        source_index, source_profile = setup.get('index_id', 'visual54full'), setup.get('calibration_id', 'full54cuda')
        moved = cli('upgrade-semantic', 'project', 'upgrade-semantic', '--project', project,
            '--adapter-id', source_adapter, '--new-adapter-id', 'installed'+suffix, '--id-prefix', 'i'+suffix,
            '--index-id', source_index, '--timeout-seconds', '600')
        assert moved['implementation_bytes_identical'] and moved['model_forward_calls'] == 0
        assert moved['original_records_preserved'] and moved['cutoff_and_observations_preserved']
        index_id = next(x['target'] for x in moved['index_mappings'] if x['source'] == source_index)
        calibration_id = next(x['target'] for x in moved['calibration_mappings'] if x['source'] == source_profile)
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
        expected_record = load(BASE/('setup-'+args.source_run)/'heldout-expected.json')
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
        ffmpeg = shutil.which('ffmpeg')
        ffprobe = shutil.which('ffprobe')
        assert ffmpeg and ffprobe

        def stream(name, path, audio=False):
            tail = (['-map', '0:a:0', '-vn', '-c:a', 'pcm_f32le', '-f', 'f32le'] if audio else
                    ['-map', '0:v:0', '-an', '-pix_fmt', 'rgb24', '-f', 'rawvideo'])
            return run(name, [ffmpeg, '-nostdin', '-v', 'error', '-i', path, *tail, 'pipe:1'], binary=True)

        from array import array
        from fractions import Fraction
        variant_proofs = {}
        for variant, dimensions in [('wide', (320, 180)), ('vertical', (180, 320))]:
            movie = project/('renders/installed-'+variant+'.mp4')
            replay_movie = replay/('renders/installed-'+variant+'.mp4')
            cli('render-replay-'+variant, 'render', '--project', replay,
                '--sequence-id', 'ad_installeddemo_'+variant+'_sequence', '--output', replay_movie)
            for label, path in [('original', movie), ('replay', replay_movie)]:
                probe = json.loads(run(variant+'-'+label+'-probe', [ffprobe, '-v', 'error',
                    '-count_frames', '-select_streams', 'v:0', '-show_entries',
                    'stream=width,height,nb_read_frames,r_frame_rate', '-of', 'json', path]))['streams'][0]
                assert (probe['width'], probe['height']) == dimensions
                assert int(probe['nb_read_frames']) == 90 and Fraction(probe['r_frame_rate']) == 30
            rgb, pcm = stream(variant+'-original-rgb', movie), stream(variant+'-original-pcm', movie, True)
            assert rgb == stream(variant+'-replay-rgb', replay_movie)
            assert pcm == stream(variant+'-replay-pcm', replay_movie, True)
            assert len(rgb) == dimensions[0]*dimensions[1]*3*90 and len(pcm) > 0
            samples = array('f', pcm)
            assert all(math.isfinite(s) for s in samples) and any(s != 0. for s in samples)
            variant_proofs[variant] = dict(width=dimensions[0], height=dimensions[1], frames=90, fps=30,
                full_RGB_bytes=len(rgb), full_PCM_bytes=len(pcm), RGB_sha256=hashlib.sha256(rgb).hexdigest(),
                PCM_sha256=hashlib.sha256(pcm).hexdigest(), replay_equal=True, finite_non_silent_PCM=True)
        assert before == {p.name: sha(p) for p in source.glob('*.py')} == {
            p.name: sha(p) for p in package.glob('*.py')}
        assert sha(namespace) == namespace_pin
        save(out/'verification.json', dict(status='passed', cli_version=args.cli_version, installed=str(installed),
            source_fallback=False, actual_GPU_semantic_search=True, selection=actual, renders=4, variants=variant_proofs,
            full_RGB_bytes=len(rgb), full_PCM_bytes=len(pcm), full_project_replay_equal=True,
            project_unchanged_by_selection=True, frozen_equal=True, registered_skill_unchanged=True,
            actual_PowerShell_entry=bool(args.skill_entry),
            non_silent_finite_PCM=True,
            natural_motion_quality_accepted=False, independent_agent_benchmark=False))
    except BaseException as exc:
        save(out/'verification.json', dict(status='failed', error=repr(exc), source_fallback=False))
        raise


if __name__ == '__main__':
    main()
