"""Create an editable six-second demo through the installed Agent Skill launcher.

The supplied fictional FIELD artwork and synthetic pulse are CC0. This is an
installation/editing demonstration, not natural-footage or listening acceptance.
"""
from pathlib import Path
import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import time

HOME = Path(__file__).resolve().parent


def sha(path):
    with Path(path).open('rb') as handle:
        return hashlib.file_digest(handle, 'sha256').hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True, help='New local demo directory; existing paths are preserved')
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists():
        raise ValueError('Existing output is preserved; choose a new --output directory')
    config = HOME / 'local/agent-ffmpeg/runtime.json'
    runtime = json.loads(config.read_bytes())
    if runtime['release'] != 'v0.1.0-alpha.3' or not Path(sys.executable).samefile(runtime['python']):
        raise ValueError('Use the native Python registered by this Agent kit installation')
    output.mkdir(parents=True)
    logs = output / 'logs'
    logs.mkdir()
    inputs = output / 'input'
    shutil.copytree(HOME / 'demo/input', inputs)
    prefix = [sys.executable, '-I', '-S', '-B', '-X', 'utf8',
              str(HOME / 'skills/agent-ffmpeg-local-editor/scripts/run.py'), str(config)]
    commands = []

    def cli(name, arguments):
        started = time.monotonic()
        command = prefix + list(map(str, arguments))
        result = subprocess.run(command, capture_output=True, timeout=300,
                                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        (logs / (name + '.stdout.json')).write_bytes(result.stdout)
        (logs / (name + '.stderr.txt')).write_bytes(result.stderr)
        response = json.loads(result.stdout)
        commands.append({'id': name, 'argv': command, 'exit_code': result.returncode,
                         'ok': response.get('ok'), 'status': response.get('status'),
                         'seconds': round(time.monotonic() - started, 3),
                         'stdout': 'logs/' + name + '.stdout.json'})
        save(output / 'commands.json', commands)
        if result.returncode or not response.get('ok') or response.get('errors'):
            raise RuntimeError(name + ' failed; see retained stdout/stderr logs')
        return response

    for name, arguments in [('version', ['version']), ('doctor', ['doctor']),
                            ('capabilities', ['capabilities']), ('schema', ['schema', 'show'])]:
        cli(name, arguments)
    project = output / 'project'
    cli('project-init', ['project', 'init', project, '--name', 'agent editor kit / first demo'])
    ids = {}
    for name in ('card-1.png', 'card-2.png', 'pulse.wav'):
        response = cli('ingest-' + name.split('.')[0], ['media', 'ingest', '--project', project,
            '--input', inputs / name, '--source-url', 'local://agent-editor-kit-demo/' + name,
            '--license-spdx', 'CC0-1.0', '--license-url', inputs / 'LICENSE.txt',
            '--evidence', inputs / 'LICENSE.txt', '--creator', 'Agent Video Kit contributors',
            '--verification-status', 'verified', '--permitted-use', 'commercial_ad'])
        ids[name] = response['data']['asset']['id']
    changes = {'sequence_id': 'seq_main', 'operations': [
        {'op': 'append_clip', 'track_id': 'track_video_1', 'asset_id': ids['card-1.png'],
         'source_in_tick': 0, 'source_out_tick': 270000, 'duration_tick': 270000},
        {'op': 'append_clip', 'track_id': 'track_video_1', 'asset_id': ids['card-2.png'],
         'source_in_tick': 0, 'source_out_tick': 270000, 'duration_tick': 270000},
        {'op': 'append_clip', 'track_id': 'track_audio_1', 'asset_id': ids['pulse.wav'],
         'source_in_tick': 0, 'source_out_tick': 540000, 'duration_tick': 540000},
    ]}
    save(output / 'changes.json', changes)
    cli('compose', ['timeline', 'compose', '--project', project, '--input', output / 'changes.json'])
    authored = json.loads((project / 'project.json').read_bytes())
    first_clip = next(t for t in authored['sequences'][0]['tracks'] if t['id'] == 'track_video_1')['clips'][0]['id']
    cli('motion', ['motion', 'apply', '--project', project, '--clip-id', first_clip, '--preset', 'zoom_in', '--amount', '0.08'])
    cli('look', ['look', 'apply', '--project', project, '--id', 't3-kodak-gold-200', '--global', '--strength', '0.65'])
    cli('validate', ['validate', '--project', project])
    cli('rights', ['rights', 'check', '--project', project])
    cli('policy', ['policy', 'audit', '--project', project])
    cli('preview', ['preview', 'frame', '--project', project, '--frame', '0'])
    video = project / 'renders/demo.mp4'
    cli('render', ['render', '--project', project, '--output', video, '--width', '360', '--height', '640', '--publish'])
    cli('quality', ['quality', 'check', '--project', project, '--input', video, '--require-audio',
                    '--width', '360', '--height', '640', '--expensive'])
    package = output / 'demo.aevpkg.zip'
    cli('export', ['convert', 'export', '--project', project, '--target-format', 'package', '--output', package])
    cli('import', ['convert', 'import', '--input', package, '--output', output / 'restored'])
    cli('restored-validate', ['validate', '--project', output / 'restored'])
    probe_result = subprocess.run(['ffprobe', '-v', 'error', '-count_frames', '-show_streams', '-show_format', '-of', 'json', str(video)],
                                  capture_output=True, timeout=60, check=True,
                                  creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    (output / 'probe.json').write_bytes(probe_result.stdout)
    probe = json.loads(probe_result.stdout)
    visual = next(s for s in probe['streams'] if s['codec_type'] == 'video')
    if visual['width'] != 360 or visual['height'] != 640 or int(visual['nb_read_frames']) != 180:
        raise RuntimeError('Actual encoded video does not match the six-second demo contract')
    decoded = subprocess.run(['ffmpeg', '-v', 'error', '-i', str(video), '-f', 'null', '-'],
                             capture_output=True, timeout=60,
                             creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    (output / 'decode.log').write_bytes(decoded.stdout + decoded.stderr)
    if decoded.returncode:
        raise RuntimeError('Actual encoded output failed full decode')
    report = {'ok': True, 'release': 'v0.1.0-alpha.3', 'cli_commands': len(commands),
              'video': str(video), 'video_sha256': sha(video), 'frames': 180, 'fps': '30/1',
              'width': 360, 'height': 640, 'seconds': 6, 'full_decode_passed': True,
              'project': str(project / 'project.json'), 'package': str(package),
              'new_model_inferences': 0, 'continuous_playback_review': False, 'listening_review': False,
              'natural_quality_acceptance': False, 'input_license': 'CC0-1.0'}
    save(output / 'verification.json', report)
    print(json.dumps(report, ensure_ascii=False))


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, KeyError, RuntimeError, subprocess.SubprocessError) as exc:
        print(json.dumps({'ok': False, 'status': 'failed-preserved', 'message': str(exc)}, ensure_ascii=False))
        raise SystemExit(2)
