"""Installed CLI63 actual MuseTalk CUDA, source protection and full replay."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT/'docs/validation/evidence/job-enumeration-20261029-r1'
PRIOR = ROOT/'docs/validation/evidence/native-lipsync-20261027-r1/case-r1'


def load(path):
    return json.loads(path.read_bytes())


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--installed', type=Path)
    parser.add_argument('--run', required=True)
    parser.add_argument('--gate-run', default='r1')
    args = parser.parse_args()
    assert args.run.replace('-', '').isalnum() and args.gate_run.replace('-', '').isalnum()
    installed = args.installed.resolve() if args.installed else None
    source = ROOT/'product/src/ai_ad_editor'
    mode='installed63' if installed else 'source63'
    if installed:assert installed.is_relative_to((ROOT/'local/agent-ffmpeg').resolve())
    gate = load(BASE/(mode+'-bootstrap-'+args.gate_run)/'verification.json')
    assert gate['status']=='passed' and gate['cli_version']=='0.1.63' and gate['frozen_equal']
    if installed:
        assert gate['source_and_installed_equal'] and Path(gate['installed']).resolve()==installed
    assert all(sha(ROOT/name)==pin for name,pin in gate['file_hashes'].items())
    package = installed/'site/ai_ad_editor' if installed else source
    pins = {p.name:sha(p) for p in package.glob('*.py')}
    assert len(pins)==283 and pins=={p.name:sha(p) for p in source.glob('*.py')}
    protected = [ROOT/'agent-ffmpeg-local-install-manifest.json', ROOT/'local/agent-ffmpeg/runtime.json']
    protected_pins = {str(p):sha(p) for p in protected}
    out = BASE/(mode+'-lipsync-cuda-'+args.run)
    work = ROOT/'local/agent-ffmpeg'/('native-worker-'+mode+'-lipsync-'+args.run)
    out.mkdir(exist_ok=False)
    work.mkdir(exist_ok=False)
    shutil.copyfile(Path(__file__), out/'executed-runner.py')
    prefix = ([sys.executable,'-I','-S','-B','-u','-X','utf8',installed/'run.py'] if installed else [sys.executable,'-E','-B','-u','-X','utf8',str(ROOT/'scripts/run_source_editor.py')])
    sys.path.insert(0,str(package.parent))
    from ai_ad_editor.runtime import configure_local_runtime
    configure_local_runtime()
    ffmpeg = shutil.which('ffmpeg')
    assert ffmpeg
    calls = []

    def run(name, argv, binary=False):
        argv = list(map(str, argv))
        result = subprocess.run(argv, cwd=ROOT, capture_output=True, timeout=2100,
                                creationflags=subprocess.CREATE_NO_WINDOW)
        target = (work if binary else out)/(name+('.raw' if binary else '.stdout'))
        target.write_bytes(result.stdout)
        (out/(name+'.stderr')).write_bytes(result.stderr)
        calls.append(dict(name=name, argv=argv, exit_code=result.returncode, stdout_sha256=sha(target)))
        save(out/'calls.json', calls)
        print(json.dumps(dict(name=name, exit_code=result.returncode)), flush=True)
        assert result.returncode == 0, (name, result.stdout[-1600:], result.stderr[-1600:])
        return result.stdout

    def cli(name, *argv):
        value = json.loads(run(name, [*prefix, *argv]))
        assert value['ok'] and value['provenance']['cli_version'] == '0.1.63'
        return value['data']

    def rgba(name, path):
        return run(name, [ffmpeg, '-nostdin', '-v', 'error', '-i', path, '-an', '-pix_fmt', 'rgba',
                         '-fps_mode', 'passthrough', '-f', 'rawvideo', 'pipe:1'], True)

    def pcm(name, path):
        return run(name, [ffmpeg, '-nostdin', '-v', 'error', '-i', path, '-vn', '-c:a', 'pcm_f32le',
                         '-f', 'f32le', 'pipe:1'], True)

    try:
        previous = load(PRIOR/'verification.json')
        assert previous['status'] == 'passed' and previous['real_person_reference'] is False
        project, replay = work/'project', work/'replay'
        cli('version', 'version')
        cli('init', 'project', 'init', project)
        mapping = {}
        def old_args(name, command):
            call = next(c['command'] for c in previous['calls'] if c['name'] == name)
            argv = call[call.index(command):]
            argv[argv.index('--project')+1] = str(project)
            for option in ['--source-asset-id', '--audio-asset-id']:
                if option in argv:
                    index = argv.index(option)+1
                    argv[index] = mapping[argv[index]]
            return argv
        cli('register-fresh', *old_args('register', 'lipsync'))
        inputs = {}
        for name in ['image', 'speech']:
            argv = old_args('ingest-'+name, 'media')
            path = Path(argv[argv.index('--input')+1])
            old_asset = load(PRIOR/('ingest-'+name+'.stdout.json'))['data']['asset']
            assert old_asset['sha256'] == 'sha256:'+sha(path)
            current = cli('ingest-'+name, *argv)['asset']
            mapping[old_asset['id']] = current['id']
            inputs[name] = path
        video = previous['image_result']['configuration']['video']
        width, height = video['width'], video['height']
        author = load(project/'project.json')
        author['settings']['canvas'].update(width=width, height=height, fps=dict(num=25, den=1))
        save(project/'project.json', author)
        result = cli('generate', *old_args('generate-image', 'lipsync'))
        worker = result['generation']['worker']
        execution = worker['model_execution']
        n = result['configuration']['video']['frames']
        assert n == previous['frames']
        assert worker['providers'] == ['torch-cuda'] and execution['CPU_fallback'] is False
        assert execution['CUDA_admission']['status'] == 'admitted' and execution['cuda_peak_allocated_bytes'] > 0
        assert execution['calls']['unet'] == math.ceil(n/2) and sum(execution['batch_frames']) == n
        assert worker['blocked_network_events'] == []
        master = project/result['asset']['uri']
        raw, image = rgba('master-rgba', master), rgba('input-rgba', inputs['image'])
        frame_bytes = width*height*4
        assert len(image) == frame_bytes and len(raw) == n*frame_bytes
        assert worker['metrics']['rgba_sha256'] == 'sha256:'+hashlib.sha256(raw).hexdigest()
        assert raw[3::4] == image[3::4]*n
        box = result['configuration']['boxes']['keys'][0]['box']
        x0,y0,x1,y1 = map(int, box)
        for i in range(n):
            frame = memoryview(raw)[i*frame_bytes:(i+1)*frame_bytes]
            assert frame[:y0*width*4] == image[:y0*width*4]
            assert frame[y1*width*4:] == image[y1*width*4:]
            for y in range(y0,y1):
                row = y*width*4
                assert frame[row:row+x0*4] == image[row:row+x0*4]
                assert frame[row+x1*4:row+width*4] == image[row+x1*4:row+width*4]
        assert any(raw[i*frame_bytes:(i+1)*frame_bytes] != image for i in range(n))
        assert raw[:frame_bytes] != raw[(n//2)*frame_bytes:(n//2+1)*frame_bytes]
        input_pcm, output_pcm = pcm('input-pcm', inputs['speech']), pcm('master-pcm', master)
        clock = result['configuration']['audio']
        assert len(input_pcm) == clock['samples']*clock['channels']*4
        assert len(output_pcm) == clock['output_samples']*clock['channels']*4
        assert output_pcm[:len(input_pcm)] == input_pcm and not any(output_pcm[len(input_pcm):])
        assert clock['padding_seconds'] < .04
        assert len(result['clips']) == 2 and len({c['clip']['link_id'] for c in result['clips']}) == 1
        cleanup = result['generation']['cleanup']
        assert all(p['exited'] and p['stdout_closed'] for p in cleanup['processes']) and not cleanup['warnings']
        cli('validate', 'validate', '--project', project)
        rendered = project/'renders/movie.mp4'
        cli('render', 'render', '--project', project, '--output', rendered)
        archive = project/'exports/lipsync.zip'
        cli('export', 'convert', 'export', '--project', project, '--target-format', 'package', '--output', archive)
        cli('import', 'convert', 'import', '--input', archive, '--output', replay)
        asset = next(a for a in load(replay/'project.json')['assets'] if a['id'] == result['asset']['id'])
        assert sha(master) == sha(replay/asset['uri']) and asset['source']['lipsync'] == result['asset']['source']['lipsync']
        replay_movie = replay/'renders/replay.mp4'
        cli('render-replay', 'render', '--project', replay, '--output', replay_movie)
        rendered_rgba, replay_rgba = rgba('rendered-rgba', rendered), rgba('replay-rgba', replay_movie)
        rendered_pcm, replay_pcm = pcm('rendered-pcm', rendered), pcm('replay-pcm', replay_movie)
        assert rendered_rgba == replay_rgba and rendered_pcm == replay_pcm
        assert pins == {p.name:sha(p) for p in package.glob('*.py')} == {p.name:sha(p) for p in source.glob('*.py')}
        assert all(sha(p) == h for p,h in protected_pins.items())
        report = dict(status='passed', cli_version='0.1.63', installed=str(installed) if installed else None, source_fallback=False,
            actual_MuseTalk_CUDA=True, model_execution=execution, frames=n, width=width, height=height,
            complete_master_RGBA_bytes=len(raw), selected_PCM_bytes=len(input_pcm),
            rendered_RGBA_bytes=len(rendered_rgba), rendered_PCM_bytes=len(rendered_pcm),
            full_alpha_and_outside_region_preserved=True, all_selected_PCM_equal=True, explicit_tail_silence_only=True,
            temporal_mouth_changes=True, linked_editable_audio_video=True, owned_process_cleanup_passed=True,
            complete_package_rendered_RGBA_PCM_equal=True, fresh_adapter_and_asset_ids=True,
            source_and_package_283_modules_frozen_equal=True, registered59_namespace_runtime_frozen=True,
            fictional_source_portrait=True, synthetic_speech=True, real_person_reference=False,
            continuous_human_playback=False, human_listening=False, natural_quality_accepted=False,
            remaining_native_models_unaccepted=12, live_skill_activation=False)
        save(out/'verification.json', report)
        print(json.dumps(report, ensure_ascii=False), flush=True)
    except BaseException as exc:
        save(out/'verification.json', dict(status='failed', error=repr(exc), installed=str(installed) if installed else None))
        raise


if __name__ == '__main__':
    main()
