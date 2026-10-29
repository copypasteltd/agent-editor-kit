"""Installed CLI57 actual RIFE CUDA, original anchors and full package replay."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT/'docs/validation/evidence/native-worker-bootstrap-20261029-r1'
PRIOR = ROOT/'docs/validation/evidence/native-interpolation-20261027-r1/case-r1'


def load(path):
    return json.loads(path.read_bytes())


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--installed', type=Path, required=True)
    parser.add_argument('--run', required=True)
    args = parser.parse_args()
    assert args.run.replace('-', '').isalnum()
    installed = args.installed.resolve()
    assert installed.is_relative_to((ROOT/'local/agent-ffmpeg').resolve())
    gate = load(BASE/('installed57-bootstrap-'+args.run)/'verification.json')
    assert gate['status'] == 'passed' and gate['source_and_installed_equal']
    assert Path(gate['installed']).resolve() == installed
    package, source = installed/'site/ai_ad_editor', ROOT/'product/src/ai_ad_editor'
    pins = {p.name: sha(p) for p in package.glob('*.py')}
    assert len(pins) == 281 and pins == {p.name: sha(p) for p in source.glob('*.py')}
    namespace = ROOT/'agent-ffmpeg-local-install-manifest.json'
    namespace_pin = sha(namespace)
    runtime = ROOT/'local/agent-ffmpeg/runtime.json'
    runtime_pin = sha(runtime)
    out = BASE/('installed57-interpolation-'+args.run)
    work = ROOT/'local/agent-ffmpeg'/('native-worker-installed57-interpolation-'+args.run)
    out.mkdir(exist_ok=False)
    work.mkdir(exist_ok=False)
    shutil.copyfile(Path(__file__), out/'executed-runner.py')
    prefix = [sys.executable, '-I', '-S', '-B', '-u', '-X', 'utf8', installed/'run.py']
    ffmpeg = shutil.which('ffmpeg')
    assert ffmpeg
    calls = []

    def run(name, argv, binary=False):
        argv = list(map(str, argv))
        result = subprocess.run(argv, cwd=ROOT, capture_output=True, timeout=1800,
                                creationflags=subprocess.CREATE_NO_WINDOW)
        target = (work if binary else out)/(name+('.raw' if binary else '.stdout'))
        target.write_bytes(result.stdout)
        (out/(name+'.stderr')).write_bytes(result.stderr)
        calls.append(dict(name=name, argv=argv, exit_code=result.returncode, stdout_sha256=sha(target)))
        save(out/'calls.json', calls)
        print(json.dumps(dict(name=name, exit_code=result.returncode)), flush=True)
        assert result.returncode == 0, (name, result.stdout[-1500:], result.stderr[-1500:])
        return result.stdout

    def cli(name, *argv):
        value = json.loads(run(name, [*prefix, *argv]))
        assert value['ok'] and value['provenance']['cli_version'] == '0.1.57'
        return value['data']

    def rgba(name, path):
        return run(name, [ffmpeg, '-nostdin', '-v', 'error', '-i', path, '-an', '-pix_fmt', 'rgba',
                         '-fps_mode', 'passthrough', '-f', 'rawvideo', 'pipe:1'], True)

    def pcm(name, path):
        return run(name, [ffmpeg, '-nostdin', '-v', 'error', '-i', path, '-vn', '-c:a', 'pcm_f32le',
                         '-f', 'f32le', 'pipe:1'], True)

    try:
        previous = load(PRIOR/'verification.json')
        assert previous['status'] == 'passed' and previous['synthetic_protocol_worker'] is False
        project, replay = work/'project', work/'replay'
        cli('version', 'version')
        cli('init', 'project', 'init', project)
        def old_args(name, command):
            call = next(c['command'] for c in previous['calls'] if c['name'] == name)
            argv = call[call.index(command):]
            argv[argv.index('--project')+1] = str(project)
            return argv
        cli('register-fresh', *old_args('register', 'interpolate'))
        inputs = {}
        for name in ['natural', 'alpha']:
            argv = old_args('ingest-'+name, 'media')
            path = Path(argv[argv.index('--input')+1])
            accepted = load(PRIOR/('ingest-'+name+'.stdout.json'))['data']['asset']
            assert accepted['sha256'] == 'sha256:'+sha(path)
            inputs[name] = path
            cli('ingest-'+name, *argv)
        author = load(project/'project.json')
        author['settings']['canvas'].update(width=320, height=180, fps=dict(num=24, den=1))
        save(project/'project.json', author)
        results, checks = {}, {}
        for name, stride, width, height, count in [('natural', 4, 320, 180, 96), ('alpha', 3, 192, 120, 36)]:
            result = cli('generate-'+name, *old_args('generate-'+name, 'interpolate'))
            execution = result['generation']['worker']['model_execution']
            assert execution['flow_forwards'] > 0
            assert result['generation']['worker']['blocked_network_events'] == []
            generated = rgba(name+'-generated', project/result['asset']['uri'])
            original = rgba(name+'-input', inputs[name])
            frame_bytes = width*height*4
            assert len(generated) == count*frame_bytes and len(original) == (count//stride)*frame_bytes
            assert b''.join(generated[i*frame_bytes:(i+1)*frame_bytes] for i in range(0, count, stride)) == original
            baseline = previous[name+'_result']
            master = Path(previous['project'])/baseline['asset']['uri']
            assert baseline['asset']['sha256'] == 'sha256:'+sha(master)
            assert generated == rgba(name+'-accepted-baseline', master)
            if name == 'alpha':
                assert result['generation']['all_native_PTS_and_durations_verified']
                assert result['generation']['worker']['metrics']['cut_after_frames'] == [5]
                assert pcm('alpha-input-pcm', inputs[name]) == pcm('alpha-generated-pcm', project/result['asset']['uri'])
            results[name] = result
            checks[name] = dict(frames=count, complete_RGBA_bytes=len(generated),
                original_anchors_equal=True, complete_accepted_baseline_equal=True,
                actual_model_execution=execution)
        cli('validate', 'validate', '--project', project)
        rendered = project/'renders/movie.mp4'
        cli('render', 'render', '--project', project, '--output', rendered)
        archive = project/'exports/interpolation.zip'
        cli('export', 'convert', 'export', '--project', project, '--target-format', 'package', '--output', archive)
        cli('import', 'convert', 'import', '--input', archive, '--output', replay)
        replay_data = load(replay/'project.json')
        for name, result in results.items():
            asset = next(a for a in replay_data['assets'] if a['id'] == result['asset']['id'])
            assert asset['source']['interpolation'] == result['asset']['source']['interpolation']
            assert sha(replay/asset['uri']) == sha(project/result['asset']['uri'])
        replay_movie = replay/'renders/replay.mp4'
        cli('render-replay', 'render', '--project', replay, '--output', replay_movie)
        assert rgba('rendered-rgba', rendered) == rgba('replay-rgba', replay_movie)
        assert pcm('rendered-pcm', rendered) == pcm('replay-pcm', replay_movie)
        assert pins == {p.name:sha(p) for p in package.glob('*.py')} == {p.name:sha(p) for p in source.glob('*.py')}
        assert sha(namespace) == namespace_pin and sha(runtime) == runtime_pin
        report = dict(status='passed', cli_version='0.1.57', installed=str(installed), source_fallback=False,
            installed_only=True, actual_RIFE_CUDA=True, fresh_adapter_registered=True,
            synthetic_protocol_worker=False, checks=checks, full_rendered_RGBA_and_PCM_replay_equal=True,
            source_and_installed_281_modules_frozen_equal=True, registered56_skill_and_runtime_unchanged=True,
            licenses='Sintel CC-BY-3.0;diagnostic CC0;RIFE MIT;original attribution retained',
            natural_quality_accepted=False, human_listening=False, continuous_human_playback=False,
            all15_models_accepted=False, live_skill_activation=False)
        save(out/'verification.json', report)
        print(json.dumps(report, ensure_ascii=False), flush=True)
    except BaseException as exc:
        save(out/'verification.json', dict(status='failed', error=repr(exc), installed=str(installed)))
        raise


if __name__ == '__main__':
    main()
