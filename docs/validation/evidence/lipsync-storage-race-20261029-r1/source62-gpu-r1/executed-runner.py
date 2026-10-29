"""Actual source or installed CLI62 CUDA denoising and full-PCM package replay."""
import argparse
from array import array
import hashlib
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT/'docs/validation/evidence/lipsync-storage-race-20261029-r1'
PRIOR = ROOT/'docs/validation/evidence/native-speech-enhancement-20261027-r1/case-r2'


def load(path):
    return json.loads(path.read_bytes())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n',
                    encoding='utf-8', newline='\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', required=True)
    parser.add_argument('--installed', type=Path, help='Independent candidate, without source fallback')
    args = parser.parse_args()
    assert args.run.replace('-', '').isalnum()
    gate = load(BASE/'source62-bootstrap-r1/verification.json')
    assert gate['status'] == 'passed' and gate['cli_version'] == '0.1.62' and gate['tests'] == 31 and gate['frozen_equal']
    assert all(sha(ROOT/name)==pin for name,pin in gate['file_hashes'].items())
    installed = args.installed.resolve() if args.installed else None
    mode = 'installed62' if installed else 'source62'
    if installed:
        assert installed.is_relative_to((ROOT/'local/agent-ffmpeg').resolve())
        gate = load(BASE/('installed62-bootstrap-'+args.run)/'verification.json')
        assert gate['status'] == 'passed' and gate['source_and_installed_equal']
    out = BASE/(mode+'-gpu-'+args.run)
    work = ROOT/'local/agent-ffmpeg'/('native-worker-'+mode+'-gpu-'+args.run)
    out.mkdir(exist_ok=False)
    work.mkdir(exist_ok=False)
    shutil.copyfile(Path(__file__), out/'executed-runner.py')
    source_package = ROOT/'product/src/ai_ad_editor'
    source_pins = {p.name: sha(p) for p in source_package.glob('*.py')}
    package = installed/'site/ai_ad_editor' if installed else source_package
    pins = {p.name: sha(p) for p in package.glob('*.py')}
    assert len(pins) == 283 and pins == source_pins
    namespace = ROOT/'agent-ffmpeg-local-install-manifest.json'
    namespace_pin = sha(namespace)
    project, replay = work/'project', work/'replay'
    code = ('import sys;sys.path.insert(0,'+repr(str(package.parent))+
            ');from ai_ad_editor.cli import main;raise SystemExit(main())')
    prefix = ([sys.executable, '-I', '-S', '-B', '-u', '-X', 'utf8', str(installed/'run.py')]
              if installed else [sys.executable, '-E', '-B', '-u', '-X', 'utf8', '-c', code])
    calls = []

    def run(name, argv, *, binary=False):
        argv = list(map(str, argv))
        r = subprocess.run(argv, cwd=ROOT, capture_output=True, timeout=2100,
                           creationflags=subprocess.CREATE_NO_WINDOW)
        (work if binary else out).joinpath(name+('.raw' if binary else '.stdout')).write_bytes(r.stdout)
        (out/(name+'.stderr')).write_bytes(r.stderr)
        calls.append(dict(name=name, argv=argv, exit_code=r.returncode,
                          stdout_sha256=hashlib.sha256(r.stdout).hexdigest()))
        save(out/'calls.json', calls)
        print(json.dumps(dict(name=name, exit_code=r.returncode)), flush=True)
        assert r.returncode == 0, (name, r.stdout[-1500:], r.stderr[-1500:])
        return r.stdout

    def cli(name, *args):
        value = json.loads(run(name, [*prefix, *args]))
        assert value['ok'] and value['provenance']['cli_version'] == '0.1.62'
        return value['data']

    try:
        cli('version', 'version')
        cli('init', 'project', 'init', project)
        old = load(PRIOR/'verification.json')
        register = next(c['command'] for c in old['calls'] if c['name'] == 'register')
        register = register[register.index('audio'):]
        register[register.index('--project')+1] = str(project)
        cli('register-fresh', *register)
        ingest = next(c['command'] for c in old['calls'] if c['name'] == 'ingest-english-noisy')
        ingest = ingest[ingest.index('media'):]
        ingest[ingest.index('--project')+1] = str(project)
        noisy = Path(ingest[ingest.index('--input')+1])
        prior_asset = load(PRIOR/'ingest-english-noisy.stdout.json')['data']['asset']
        assert 'sha256:'+sha(noisy) == prior_asset['sha256']
        source = cli('ingest', *ingest)['asset']
        enhanced = cli('enhance', 'audio', 'enhance', '--project', project,
            '--adapter-id', 'df3_local', '--source-asset-id', source['id'],
            '--asset-id', 'native58_enhanced', '--apply', '--track-id', 'track_audio_1',
            '--timeout-seconds', '1800')
        worker = enhanced['generation']['worker']
        model = worker['model']
        assert worker['status'] == 'succeeded' and model['neural_backend'] == 'cuda'
        assert model['CPU_fallback'] is False and model['model_forwards'] > 0
        assert enhanced['generation']['complete_PCM_roundtrip_verified']
        output = project/enhanced['asset']['uri']
        ffmpeg = shutil.which('ffmpeg')
        assert ffmpeg

        def pcm(name, path):
            return run(name, [ffmpeg, '-nostdin', '-v', 'error', '-i', path, '-map', '0:a:0',
                       '-vn', '-c:a', 'pcm_f32le', '-f', 'f32le', 'pipe:1'], binary=True)

        clean = noisy.with_name('english-clean.wav')
        assert 'sha256:'+sha(clean) == load(PRIOR/'ingest-english-clean.stdout.json')['data']['asset']['sha256']
        reference, before, after = pcm('clean', clean), pcm('noisy', noisy), pcm('enhanced', output)
        assert len(reference) == len(before) == len(after) == worker['range']['samples']*worker['channels']*4
        x, y, z = array('f', reference), array('f', before), array('f', after)
        assert all(math.isfinite(v) for v in z) and any(v != 0 for v in z)
        mse_before = sum((a-b)**2 for a,b in zip(x,y))/len(x)
        mse_after = sum((a-b)**2 for a,b in zip(x,z))/len(x)
        assert mse_after < mse_before/2, 'Fixed controlled-noise checkpoint requires at least 3 dB MSE improvement'
        cli('validate', 'validate', '--project', project)
        exported = project/'exports/native58-audio.zip'
        cli('export', 'convert', 'export', '--project', project, '--output', exported, '--target-format', 'package')
        cli('import-replay', 'convert', 'import', '--input', exported, '--output', replay)
        replay_asset = next(a for a in load(replay/'project.json')['assets'] if a['id'] == 'native58_enhanced')
        assert sha(output) == sha(replay/replay_asset['uri'])
        assert after == pcm('replay', replay/replay_asset['uri'])
        source_pcm_sha256 = None
        if installed:
            accepted_source = ROOT/'local/agent-ffmpeg/native-worker-source62-gpu-r1/enhanced.raw'
            source_result = load(BASE/'source62-gpu-r1/verification.json')
            assert source_result['status'] == 'passed' and source_result['actual_CUDA_model']
            assert accepted_source.stat().st_size == source_result['complete_PCM_bytes']
            source_pcm_sha256 = sha(accepted_source)
            assert hashlib.sha256(after).hexdigest() == source_pcm_sha256, 'Installed full PCM differs from accepted source62 case'
        assert pins == {p.name: sha(p) for p in package.glob('*.py')} and sha(namespace) == namespace_pin
        assert source_pins == {p.name: sha(p) for p in source_package.glob('*.py')}
        report = dict(status='passed', cli_version='0.1.62', actual_CUDA_model=True,
            installed=str(installed) if installed else None, loaded_package=str(package),
            source_fallback=False if installed else None, source_and_installed_equal=bool(installed),
            installed_actual_CUDA_case_accepted=bool(installed),
            complete_PCM_sha256=hashlib.sha256(after).hexdigest(),
            accepted_source_PCM_sha256=source_pcm_sha256,
            complete_source_installed_PCM_equal=bool(installed and source_pcm_sha256),
            fresh_adapter_registered=True, native_model=model, native_numpy_version=model['versions']['numpy'],
            code_files=len(pins), frozen_equal=True, installed_skill_unchanged=True, complete_PCM_bytes=len(after),
            complete_PCM_replay_equal=True, source_and_model_licenses_retained=True,
            input_MSE=mse_before, output_MSE=mse_after, MSE_improvement_dB=10*math.log10(mse_before/mse_after),
            controlled_noise_only=True, human_listening=False, natural_quality_accepted=False,
            installed62_accepted=False, other14_models_accepted=False)
        save(out/'verification.json', report)
        print(json.dumps(report), flush=True)
    except BaseException as exc:
        save(out/'verification.json', dict(status='failed', error=repr(exc), source_cli='0.1.62'))
        raise


if __name__ == '__main__':
    main()
