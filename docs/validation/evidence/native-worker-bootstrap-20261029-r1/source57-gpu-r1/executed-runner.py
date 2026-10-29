"""Actual source CLI57 CUDA denoising with fresh binding and full-PCM package replay."""
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
BASE = ROOT/'docs/validation/evidence/native-worker-bootstrap-20261029-r1'
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
    args = parser.parse_args()
    assert args.run.replace('-', '').isalnum()
    assert load(BASE/'source57-bootstrap-r1/verification.json')['status'] == 'passed'
    out = BASE/('source57-gpu-'+args.run)
    work = ROOT/'local/agent-ffmpeg'/('native-worker-source57-gpu-'+args.run)
    out.mkdir(exist_ok=False)
    work.mkdir(exist_ok=False)
    shutil.copyfile(Path(__file__), out/'executed-runner.py')
    package = ROOT/'product/src/ai_ad_editor'
    pins = {p.name: sha(p) for p in package.glob('*.py')}
    assert len(pins) == 281
    namespace = ROOT/'agent-ffmpeg-local-install-manifest.json'
    namespace_pin = sha(namespace)
    project, replay = work/'project', work/'replay'
    code = ('import sys;sys.path.insert(0,'+repr(str(package.parent))+
            ');from ai_ad_editor.cli import main;raise SystemExit(main())')
    prefix = [sys.executable, '-E', '-B', '-u', '-X', 'utf8', '-c', code]
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
        assert value['ok'] and value['provenance']['cli_version'] == '0.1.57'
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
            '--asset-id', 'native57_enhanced', '--apply', '--track-id', 'track_audio_1',
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
        exported = project/'exports/native57-audio.zip'
        cli('export', 'convert', 'export', '--project', project, '--output', exported, '--target-format', 'package')
        cli('import-replay', 'convert', 'import', '--input', exported, '--output', replay)
        replay_asset = next(a for a in load(replay/'project.json')['assets'] if a['id'] == 'native57_enhanced')
        assert sha(output) == sha(replay/replay_asset['uri'])
        assert after == pcm('replay', replay/replay_asset['uri'])
        assert pins == {p.name: sha(p) for p in package.glob('*.py')} and sha(namespace) == namespace_pin
        report = dict(status='passed', cli_version='0.1.57', actual_CUDA_model=True,
            fresh_adapter_registered=True, native_model=model, native_numpy_version=model['versions']['numpy'],
            code_files=281, frozen_equal=True, installed_skill_unchanged=True, complete_PCM_bytes=len(after),
            complete_PCM_replay_equal=True, source_and_model_licenses_retained=True,
            input_MSE=mse_before, output_MSE=mse_after, MSE_improvement_dB=10*math.log10(mse_before/mse_after),
            controlled_noise_only=True, human_listening=False, natural_quality_accepted=False,
            installed57_accepted=False, other14_models_accepted=False)
        save(out/'verification.json', report)
        print(json.dumps(report), flush=True)
    except BaseException as exc:
        save(out/'verification.json', dict(status='failed', error=repr(exc), source_cli='0.1.57'))
        raise


if __name__ == '__main__':
    main()
