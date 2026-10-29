"""Native source-CLI54 semantic advertising acceptance; no downloads/virtualization."""
import argparse
import hashlib
import json
import math
import os
import re
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'docs/validation/evidence/ad-selection-20261029-r1'
WORK = ROOT / 'local/agent-ffmpeg/ad-selection-20261029-r1'
SOURCE = ROOT / 'product/src/ai_ad_editor'
ACTIVE_EVIDENCE = None


def load(path):
    return json.loads(Path(path).read_bytes())


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')


def frozen():
    return {p.name: sha(p) for p in sorted(SOURCE.glob('*.py'))}


def main():
    global WORK, BASE, ACTIVE_EVIDENCE
    parser = argparse.ArgumentParser()
    parser.add_argument('--phase', choices=('tests', 'compat', 'setup', 'complete', 'case'), required=True)
    parser.add_argument('--run', required=True)
    parser.add_argument('--attempt', help='New case evidence identity; retains the same frozen project and queries')
    parser.add_argument('--timeout-seconds', type=float, default=900)
    parser.add_argument('--cli-version', choices=('0.1.54', '0.1.55'), default='0.1.54')
    parser.add_argument('--full-corpus', action='store_true')
    parser.add_argument('--evidence-series', default='ad-selection-20261029-r1')
    parser.add_argument('--python-executable', type=Path, help='Explicit existing native model runtime; registration attests all dependencies')
    parser.add_argument('--model-path', type=Path, help='Explicit local model; defaults to the existing pinned model')
    args = parser.parse_args()
    assert args.run.replace('-', '').isalnum()
    assert args.evidence_series.replace('-', '').isalnum()
    BASE = ROOT/'docs/validation/evidence'/args.evidence_series
    adapter_id = 'source'+args.cli_version.rsplit('.', 1)[1]
    index_name = 'visual'+args.cli_version.rsplit('.', 1)[1]
    profile_name = 'accept'+args.cli_version.rsplit('.', 1)[1]+'cuda'
    assert math.isfinite(args.timeout_seconds) and 0 < args.timeout_seconds <= 3600
    if args.attempt:
        assert args.phase == 'case' and args.attempt.replace('-', '').isalnum()
    WORK = ROOT / ('local/agent-ffmpeg/ad-selection-20261029-'+args.run)
    out = BASE / (args.phase+'-'+args.run+('-'+args.attempt if args.attempt else ''))
    out.mkdir(parents=True, exist_ok=False)
    ACTIVE_EVIDENCE = out
    (out/'executed-runner.py').write_bytes(Path(__file__).read_bytes())
    before = frozen()
    save(out/'source-before.json', before)
    calls = []
    def run(name, command, cli=False, binary=False):
        command = list(map(str, command))
        env = os.environ.copy()
        env['TEMP'] = env['TMP'] = str(ROOT/'local/tmp')
        result = subprocess.run(command, cwd=ROOT, env=env, capture_output=True, timeout=args.timeout_seconds+300,
                                creationflags=subprocess.CREATE_NO_WINDOW)
        dest = (WORK if binary else out)/(name+('.raw' if binary else '.stdout'))
        dest.write_bytes(result.stdout)
        (out/(name+'.stderr')).write_bytes(result.stderr)
        calls.append(dict(name=name, argv=command, exit_code=result.returncode,
                          stdout_sha256=hashlib.sha256(result.stdout).hexdigest()))
        save(out/'calls.json', calls)
        print(json.dumps(dict(name=name, exit_code=result.returncode)), flush=True)
        assert result.returncode == 0, (name, result.stdout[-1500:], result.stderr[-2000:])
        if cli:
            value = json.loads(result.stdout)
            assert value['ok'] and value['provenance']['cli_version'] == args.cli_version
            return value['data']
        return result.stdout
    def cli(name, *items):
        items = list(items)
        if '--timeout-seconds' in items:
            items[items.index('--timeout-seconds')+1] = str(args.timeout_seconds)
        bootstrap = "import sys;sys.path.insert(0,'product/src');from ai_ad_editor.cli import main;raise SystemExit(main())"
        return run(name, [sys.executable, '-E', '-B', '-u', '-X', 'utf8', '-c', bootstrap, *items], cli=True)
    if args.phase in ('tests', 'compat'):
        modules = (['test_ad_selection', 'test_ad_storyboard'] if args.phase == 'tests' else
                   ['test_semantic', 'test_semantic_decisions', 'test_semantic_jobs',
                    'test_semantic_package', 'test_semantic_upgrade'])
        code = ("import sys,unittest;sys.path[:0]=['product/src','product/tests'];"
                "s=unittest.defaultTestLoader.loadTestsFromNames("+repr(modules)+");"
                "r=unittest.TextTestRunner(verbosity=2).run(s);sys.exit(not r.wasSuccessful())")
        run('tests', [sys.executable, '-E', '-B', '-u', '-X', 'utf8', '-c', code])
        log = (out/'tests.stderr').read_text('utf-8')
        report = dict(status='passed', scope=args.phase, tests=int(re.search(r'Ran (\d+) tests', log)[1]),
                      modules=modules, test_log='tests.stderr')
        if args.phase == 'tests':
            report['independent_assignment_oracle_graphs'] = 100
    elif args.phase == 'complete':
        # Preserve the failed nine-image setup and complete its existing
        # project with both missing, licensed calibration sources. The new
        # full index/profile use new identities; no hashes are hand-rebound.
        project = WORK/'project'
        calls_before = load(BASE/('setup-'+args.run)/'calls.json')
        assert calls_before[-1]['name'] == 'calibrate' and calls_before[-1]['exit_code'] != 0
        existing = {row['id'] for row in load(project/'project.json')['assets']}
        source = ROOT/'docs/assets/semantic-package-20261025-r1/SOURCE.json'
        for image in load(source)['assets']:
            if image['asset_id'] not in ('asset_j3', 'asset_k8') or image['asset_id'] in existing:
                continue
            assert sha(ROOT/image['path']) == image['sha256']
            cli('add-'+image['asset_id'], 'media', 'ingest', '--project', project,
                '--input', ROOT/image['path'], '--asset-id', image['asset_id'],
                '--license-spdx', image['license_spdx'], '--creator', image['creator'],
                '--source-url', (ROOT/image['path']).as_uri(), '--verification-status', 'verified', '--evidence', source)
        cli('index-full', 'semantic', 'index', '--project', project, '--adapter-id', 'source54',
            '--index-id', 'visual54full', '--all-visual-assets', '--device', 'cuda', '--timeout-seconds', '900')
        cli('calibrate-full', 'semantic', 'calibrate', '--project', project, '--index-id', 'visual54full',
            '--calibration-id', 'full54cuda', '--input', WORK/'calibration.json', '--kind', 'image',
            '--device', 'cuda', '--timeout-seconds', '900')
        report = dict(status='passed', source_cli='0.1.54', project=str(project),
            index_id='visual54full', calibration_id='full54cuda', native_device='cuda',
            full_eleven_image_scope_restored=True, original_failed_setup_preserved=True,
            calibration_source_sha256=sha(WORK/'calibration.json'), heldout_queries_sha256=sha(WORK/'request.json'),
            new_index_and_calibration=True, downloads=False, virtualization=False)
    elif args.phase == 'setup':
        WORK.mkdir(parents=True, exist_ok=False)
        project = WORK/'project'
        # Freeze a new selection task before any model response. The images
        # remain a familiar static scope, not a natural-motion benchmark.
        queries = [dict(id='coffee', text='A top-down still life showing a cup of coffee on its saucer'),
                   dict(id='cat', text='A close-up photograph of a tabby cat with green eyes'),
                   dict(id='camera', text='A grayscale photograph of a standing photographer holding a camera')]
        brief = dict(id='visualdemo', product='agent editor kit visual selection demo',
            audience='Local video editors', cta='Preview the editable sequence',
            caption_style=dict(font_asset_id='font'),
            shots=[dict(id=q['id'], text=q['id'].title()+' study') for q in queries],
            music=dict(asset_id='music', gain_db=-20),
            variants=[dict(id='wide', canvas=dict(width=320, height=180), duration_seconds=3),
                      dict(id='vertical', canvas=dict(width=180, height=320), duration_seconds=3)])
        save(WORK/'request.json', dict(brief=brief, queries=queries, unique_assets=True))
        save(out/'heldout-expected.json', dict(coffee='asset_b4', cat='asset_c2', camera='asset_a7',
            scope='Familiar static photographs; labels are not sent to the model or selection command.'))
        cli('init', 'project', 'init', project, '--project-id', 'semantic_ad'+args.cli_version.rsplit('.', 1)[1])
        image_evidence = ROOT/('docs/assets/semantic-package-20261025-r1/SOURCE.json' if args.full_corpus
                               else 'docs/assets/semantic-20261025-r1/SOURCE.json')
        images = load(image_evidence)['assets']
        if args.full_corpus:
            assert len([r for r in images if r['kind'] == 'image']) == 11
        for image in images:
            if image['kind'] != 'image':
                continue
            assert sha(ROOT/image['path']) == image['sha256']
            cli('ingest-'+image['asset_id'], 'media', 'ingest', '--project', project,
                '--input', ROOT/image['path'], '--asset-id', image['asset_id'],
                '--license-spdx', image['license_spdx'], '--creator', image['creator'],
                '--source-url', (ROOT/image['path']).as_uri(), '--verification-status', 'verified',
                '--evidence', image_evidence)
        font = SOURCE/'material_data/fonts/noto-sans-sc-variable.ttf'
        cli('font', 'media', 'ingest', '--project', project, '--input', font, '--asset-id', 'font',
            '--license-spdx', 'OFL-1.1', '--creator', 'Noto contributors', '--verification-status', 'verified',
            '--evidence', SOURCE/'material_data/catalog.json')
        catalog = load(SOURCE/'material_data/catalog.json')
        music = next(row for row in catalog['records'] if row['kind'] == 'music')
        collection = next(c for c in catalog['collections'] if c['id'] == music['collection_id'])
        cli('music', 'media', 'ingest', '--project', project, '--input', SOURCE/'material_data'/music['path'],
            '--asset-id', 'music', '--creator', collection['creator'], '--source-url', (SOURCE/'material_data'/music['path']).as_uri(),
            '--license-spdx', collection['license']['spdx'], '--verification-status', 'verified',
            '--evidence', SOURCE/'material_data/catalog.json')
        previous = ROOT/'workspace/semantic-upgrade-20261025-installed-r2/restored'
        old = load(previous/'project.json')['extensions']['local_semantic']['adapters'][-1]
        model_python = args.python_executable or Path(old['python_executable'])
        model_path = args.model_path or Path(old['model_path'])
        cli('register', 'semantic', 'adapter-register', '--project', project, '--adapter-id', adapter_id,
            '--python-executable', model_python, '--model-path', model_path,
            '--evidence', model_path/'README.md', '--creator', 'Google SigLIP2',
            '--license-spdx', 'Apache-2.0', '--verification-status', 'verified', '--timeout-seconds', '900')
        cli('index', 'semantic', 'index', '--project', project, '--adapter-id', adapter_id,
            '--index-id', index_name, '--all-visual-assets', '--device', 'cuda', '--timeout-seconds', '900')
        original = previous/'assets/semantic-calibration/2c838ad2abacb4bbf23fe872/dataset.json'
        shutil.copyfile(original, WORK/'calibration.json')
        cli('calibrate', 'semantic', 'calibrate', '--project', project, '--index-id', index_name,
            '--calibration-id', profile_name, '--input', WORK/'calibration.json', '--kind', 'image',
            '--device', 'cuda', '--timeout-seconds', '900')
        report = dict(status='passed', source_cli=args.cli_version, project=str(project),
                      index_id=index_name, calibration_id=profile_name, full_corpus=args.full_corpus,
                      runtime_python=str(model_python), model_path=str(model_path),
                      calibration_source_sha256=sha(original), heldout_queries_sha256=sha(WORK/'request.json'),
                      native_device='cuda', new_index_and_calibration=True, downloads=False, virtualization=False)
    else:
        gate = BASE/('complete-'+args.run)/'verification.json'
        if not gate.exists():
            gate = BASE/('setup-'+args.run)/'verification.json'
        setup = load(gate)
        assert setup['status'] == 'passed'
        assert sha(WORK/'request.json') == setup['heldout_queries_sha256']
        index_id, calibration_id = setup.get('index_id', 'visual54'), setup.get('calibration_id', 'accept54cuda')
        project = WORK/'project'
        original = (project/'project.json').read_bytes()
        save(out/'project-before.json', dict(sha256=hashlib.sha256(original).hexdigest()))
        plan_file = project/'validation'/('selected'+('-'+args.attempt if args.attempt else '')+'.json')
        dry = cli('select-dry', 'ad', 'select', '--project', project, '--input', WORK/'request.json',
            '--output', plan_file, '--index-id', index_id,
            '--calibration-id', calibration_id, '--kind', 'image', '--device', 'cuda',
            '--timeout-seconds', '900', '--dry-run')
        assert dry['selection_not_executed'] and dry['plan'] is None
        selected = cli('select', 'ad', 'select', '--project', project, '--input', WORK/'request.json',
            '--output', plan_file, '--index-id', index_id,
            '--calibration-id', calibration_id, '--kind', 'image', '--device', 'cuda', '--timeout-seconds', '900')
        assert (project/'project.json').read_bytes() == original
        expected_record = load(BASE/('setup-'+args.run)/'heldout-expected.json')
        expected = {q['id']: expected_record[q['id']] for q in load(WORK/'request.json')['queries']}
        actual = {row['shot_id']: row['asset_id'] for row in selected['selection']['selected']}
        save(out/'actual-selection.json', actual)
        assert actual == expected, (actual, expected)
        cli('build', 'ad', 'build', '--project', project, '--input', plan_file)
        movies = {}
        for variant in ('wide', 'vertical'):
            movie = project/('renders/'+variant+'.mp4')
            cli('render-'+variant, 'render', '--project', project,
                '--sequence-id', 'ad_visualdemo_'+variant+'_sequence', '--output', movie)
            movies[variant] = movie
        package = project/'exports/editable.zip'
        cli('export', 'convert', 'export', '--project', project, '--output', package, '--target-format', 'package')
        replay = WORK/('replay'+('-'+args.attempt if args.attempt else ''))
        cli('import', 'convert', 'import', '--input', package, '--output', replay)
        replay_movie = replay/'renders/wide.mp4'
        cli('replay', 'render', '--project', replay, '--sequence-id', 'ad_visualdemo_wide_sequence', '--output', replay_movie)
        ffmpeg = shutil.which('ffmpeg')
        assert ffmpeg
        def stream(name, path, audio=False):
            tail = ['-map','0:a:0','-vn','-c:a','pcm_f32le','-f','f32le'] if audio else ['-map','0:v:0','-an','-pix_fmt','rgb24','-f','rawvideo']
            return run(name, [ffmpeg,'-nostdin','-v','error','-i',path,*tail,'pipe:1'], binary=True)
        rgb, pcm = stream('original-rgb', movies['wide']), stream('original-pcm', movies['wide'], True)
        assert rgb == stream('replay-rgb', replay_movie) and pcm == stream('replay-pcm', replay_movie, True)
        assert len(rgb) == 320*180*3*90 and len(pcm) > 0
        from array import array
        samples = array('f', pcm)
        assert all(math.isfinite(s) for s in samples) and any(s != 0. for s in samples)
        report = dict(status='passed', source_cli=args.cli_version, actual_GPU_semantic_search=True,
            selection=actual, renders=3, full_RGB_bytes=len(rgb), full_PCM_bytes=len(pcm),
            full_project_replay_equal=True, project_unchanged_by_selection=True,
            non_silent_finite_PCM=True,
            natural_motion_quality_accepted=False, independent_agent_benchmark=False)
    report['frozen_equal'] = before == frozen()
    assert report['frozen_equal']
    save(out/'verification.json', report)
    print(json.dumps(report, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    try:
        main()
    except BaseException as exc:
        if ACTIVE_EVIDENCE is not None:
            save(ACTIVE_EVIDENCE/'terminal-failure.json', dict(status='failed', error=repr(exc)))
        raise
