"""Real installed CLI63 baseline before cross-host CLI66 upgrade acceptance."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def load(path):
    return json.loads(Path(path).read_bytes())


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    pending = path.with_name(path.name + '.pending')
    with pending.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write('\n')
    os.replace(pending, path)


def app_files(installed):
    folder = Path(installed) / 'site/ai_ad_editor'
    return {p.name: sha(p) for p in sorted(folder.glob('*.py'))}


class Case:
    def __init__(self, root, prefix, tools):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=False)
        self.logs = self.root / 'logs'
        self.logs.mkdir()
        self.temporary = self.root / 'temp'
        self.temporary.mkdir()
        self.prefix = list(map(str, prefix))
        self.tools = Path(tools).resolve()
        self.env = dict(os.environ)
        self.env.update(TEMP=str(self.temporary), TMP=str(self.temporary), TMPDIR=str(self.temporary),
                        PYTHONDONTWRITEBYTECODE='1',
                        PATH=str(self.tools) + os.pathsep + self.env.get('PATH', ''))
        self.calls = []

    def call(self, name, command, *, cli=False, timeout=600):
        command = list(map(str, command))
        began = time.monotonic()
        with (self.logs / (name + '.stdout')).open('xb') as stdout, (self.logs / (name + '.stderr')).open('xb') as stderr:
            result = subprocess.run(command, cwd=self.root, env=self.env, stdin=subprocess.DEVNULL,
                                    stdout=stdout, stderr=stderr, timeout=timeout,
                                    creationflags=subprocess.CREATE_NO_WINDOW)
        self.calls.append(dict(name=name, command=command, exit_code=result.returncode,
                               elapsed_seconds=time.monotonic() - began))
        save(self.root / 'calls.json', self.calls)
        if result.returncode:
            raise RuntimeError(name + ' failed; inspect retained stdout/stderr')
        raw = (self.logs / (name + '.stdout')).read_bytes()
        if cli:
            value = json.loads(raw)
            assert value.get('ok') is True and value['provenance']['cli_version'] == '0.1.63', name
            return value
        return raw

    def cli(self, name, *arguments):
        return self.call(name, [*self.prefix, *arguments], cli=True)

    def decode(self, movie, label):
        values = {}
        for kind, flags in [('RGBA', ['-map', '0:v:0', '-an', '-pix_fmt', 'rgba']),
                            ('PCM', ['-map', '0:a:0', '-vn', '-c:a', 'pcm_f32le'])]:
            raw = self.call(label + '-' + kind, [self.tools / 'ffmpeg.exe', '-nostdin', '-v', 'error',
                            '-i', movie, *flags, '-f', 'hash', '-hash', 'sha256', 'pipe:1'])
            values[kind] = raw.decode().strip()
        raw = self.call(label + '-probe', [self.tools / 'ffprobe.exe', '-v', 'error', '-show_streams',
                        '-show_format', '-of', 'json', movie])
        probe = json.loads(raw)
        streams = probe['streams']
        assert len([s for s in streams if s['codec_type'] == 'video']) == 1
        assert len([s for s in streams if s['codec_type'] == 'audio']) == 1
        video = next(s for s in streams if s['codec_type'] == 'video')
        assert (video['width'], video['height']) == (320, 180)
        return dict(decoded=values, video={k: video.get(k) for k in
                    ('width', 'height', 'r_frame_rate', 'avg_frame_rate', 'time_base', 'duration_ts', 'nb_frames')},
                    movie=str(movie), movie_sha256=sha(movie))


def prepare(args):
    installed = args.installed.resolve()
    prefix = [args.python, '-I', '-S', '-B', '-u', '-X', 'utf8', installed / 'run.py']
    case = Case(args.root, prefix, args.tools)
    case.cli('version', 'version')
    video, audio = case.root / 'pattern.mp4', case.root / 'tone.wav'
    ffmpeg = case.tools / 'ffmpeg.exe'
    case.call('make-video', [ffmpeg, '-nostdin', '-v', 'error', '-f', 'lavfi', '-i',
              'testsrc2=size=320x180:rate=30:duration=2', '-an', '-c:v', 'libx264', '-threads', '2',
              '-pix_fmt', 'yuv420p', video])
    case.call('make-audio', [ffmpeg, '-nostdin', '-v', 'error', '-f', 'lavfi', '-i',
              'sine=frequency=440:sample_rate=48000:duration=2', '-ac', '2', '-c:a', 'pcm_f32le', audio])
    project = case.root / 'project'
    case.cli('init', 'project', 'init', project, '--name', 'Two native Windows baseline')
    spec = load(project / 'project.json')
    spec['settings']['canvas'].update(width=320, height=180)
    save(project / 'project.json', spec)
    assets = []
    for name, path in [('video', video), ('audio', audio)]:
        assets.append(case.cli('ingest-' + name, 'media', 'ingest', '--project', project,
                               '--input', path)['data']['asset'])
    ticks = 2 * spec['settings']['timebase']['ticks_per_second']
    tracks = spec['sequences'][0]['tracks']
    changes = dict(operations=[dict(op='append_clip', id='baseline_' + kind,
        asset_id=asset['id'], track_id=next(t['id'] for t in tracks if t['kind'] == kind),
        timeline_start_tick=0, duration_tick=ticks, source_in_tick=0, source_out_tick=ticks)
        for kind, asset in zip(('video', 'audio'), assets)])
    input_path = case.root / 'changes.json'
    save(input_path, changes)
    case.cli('compose', 'timeline', 'compose', '--project', project, '--input', input_path)
    case.cli('look', 'look', 'apply', '--project', project, '--id', 't3-kodak-gold-200', '--global', '--strength', '0.65')
    case.cli('validate', 'validate', '--project', project)
    movie = project / 'renders/baseline.mp4'
    case.cli('render', 'render', '--project', project, '--output', movie)
    original = case.decode(movie, 'original')
    package = case.root / 'baseline.aevpkg.zip'
    case.cli('export', 'convert', 'export', '--project', project, '--target-format', 'package', '--output', package)
    restored = case.root / 'restored'
    case.cli('import', 'convert', 'import', '--input', package, '--output', restored)
    restored_movie = restored / 'renders/baseline.mp4'
    case.cli('replay-render', 'render', '--project', restored, '--output', restored_movie)
    repeated = case.decode(restored_movie, 'restored')
    assert original['decoded'] == repeated['decoded']
    assert original['video'] == repeated['video']
    expected = dict(format='agent-editor-two-native-host-baseline-v1', cli_version='0.1.63',
        package_sha256=sha(package), complete_decoded=original['decoded'], video=original['video'],
        master_assets={a['id']: a['sha256'] for a in assets}, application_files=app_files(installed),
        tools={name: sha(case.tools / name) for name in ('ffmpeg.exe', 'ffprobe.exe')},
        installed_manifest_sha256=load(installed / 'receipt.json')['manifest_sha256'],
        local_package_replay_equal=True, look_id='t3-kodak-gold-200', look_strength=0.65,
        natural_quality_accepted=False, human_listening=False, model_inference=False, gpu_render=False)
    save(case.root / 'expected.json', expected)
    save(case.root / 'verification.json', dict(status='primary-baseline-passed', **expected,
        original=original, restored=repeated, source_fallback=False))
    print(json.dumps(dict(status='primary-baseline-passed', package=str(package), expected=str(case.root / 'expected.json')), ensure_ascii=False))


def replay(args):
    expected = load(args.expected)
    assert expected['cli_version'] == '0.1.63' and sha(args.package) == expected['package_sha256']
    assert app_files(args.installed) == expected['application_files']
    assert load(args.installed / 'receipt.json')['manifest_sha256'] == expected['installed_manifest_sha256']
    assert all(sha(args.tools / name) == pin for name, pin in expected['tools'].items())
    prefix = ['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', args.entry]
    case = Case(args.root, prefix, args.tools)
    case.cli('registered-version', 'version')
    project = case.root / 'imported'
    case.cli('import', 'convert', 'import', '--input', args.package, '--output', project)
    case.cli('validate', 'validate', '--project', project)
    movie = project / 'renders/cross-host.mp4'
    case.cli('render', 'render', '--project', project, '--output', movie)
    actual = case.decode(movie, 'actual')
    equal = actual['decoded'] == expected['complete_decoded'] and actual['video'] == expected['video']
    assets = load(project / 'project.json')['assets']
    for asset_id, pin in expected['master_assets'].items():
        asset = next(a for a in assets if a['id'] == asset_id)
        assert 'sha256:' + sha(project / asset['uri']) == pin
    save(case.root / 'verification.json', dict(status='cross-host-baseline-passed' if equal else 'cross-host-media-mismatch',
        cli_version='0.1.63', actual=actual, expected=expected, complete_RGBA_PCM_equal=equal,
        complete_master_assets_equal=True, actual_registered_Skill=True, source_fallback=False,
        model_inference=False, gpu_render=False, human_listening=False, natural_quality_accepted=False,
        clean_host=False, cross_machine=True, cli66_accepted=False))
    assert equal, 'Cross-host media differs; preserve the actual output and do not weaken the comparison'
    print(json.dumps(dict(status='cross-host-baseline-passed', verification=str(case.root / 'verification.json')), ensure_ascii=False))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('mode', choices=('prepare', 'replay'))
    for name in ('root', 'installed', 'tools'):
        parser.add_argument('--' + name, type=Path, required=True)
    parser.add_argument('--python', type=Path, default=Path(sys.executable))
    for name in ('package', 'expected', 'entry'):
        parser.add_argument('--' + name, type=Path)
    args = parser.parse_args()
    assert os.name == 'nt' and sys.dont_write_bytecode and sys.prefix == sys.base_prefix
    return {'prepare': prepare, 'replay': replay}[args.mode](args)


if __name__ == '__main__':
    try:
        main()
    except BaseException as exc:
        # Keep the complete command log and failed workspace; never rerun into it.
        for index, argument in enumerate(sys.argv[:-1]):
            if argument == '--root':
                destination = Path(sys.argv[index + 1])
                if destination.is_dir() and not (destination / 'failure.json').exists():
                    save(destination / 'failure.json', dict(status='failed', error=repr(exc), cli66_accepted=False))
                break
        raise
