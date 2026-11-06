"""Download the published CLI66 assets and verify a new native single-Skill installation."""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import sys
import time
import urllib.parse
import urllib.request

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import delivery66_handoff as handoff

ROOT = handoff.ROOT
COMMIT = '2eb9130c45fa446b1f328df777a0a3624d681990'
LOCK = ROOT / 'local/agent-ffmpeg/delivery66-handoff/release-assets-r1/release-lock.json'
LOCK_SHA = '8b16bbf8e4047cc9a255644a8aa50fe267deb6aa1f65035a3237ae976e5d0bbd'
CASE = HERE / 'cross_machine66_20261106_r1/case.py'
CASE_SHA = '1f46e8829f565240c7d1b920f3caf38784e62c9bbd63a27cb51286b45543d246'
CODE_PHASE = HERE / 'evidence/delivery66-public-20261106-r1/code-phase-r1/verification.json'


def api(url):
    request = urllib.request.Request(url, headers={
        'Accept': 'application/vnd.github+json', 'User-Agent': 'agent-editor-kit-public-acceptance'})
    with urllib.request.urlopen(request, timeout=45) as response:
        raw = response.read(8 * 1024**2 + 1)
    handoff.require(len(raw) <= 8 * 1024**2, 'Public API response exceeds budget')
    return handoff.decode(raw)


def download(row, published, target):
    handoff.require(published['size'] == row['bytes'] and published.get('digest') == 'sha256:' + row['sha256'],
                    'Public metadata does not match the accepted lock')
    url = published['browser_download_url']
    parsed = urllib.parse.urlsplit(url)
    handoff.require(parsed.scheme == 'https' and parsed.hostname == 'github.com'
                    and not parsed.username and not parsed.password, 'Unexpected public asset URL')
    request = urllib.request.Request(url, headers={'User-Agent': 'agent-editor-kit-public-acceptance'})
    pending = target.with_name(target.name + '.part')
    digest, size, began = hashlib.sha256(), 0, time.monotonic()
    with urllib.request.urlopen(request, timeout=60) as response, pending.open('xb') as output:
        final = urllib.parse.urlsplit(response.url)
        handoff.require(final.scheme == 'https' and final.hostname in {
            'github.com', 'release-assets.githubusercontent.com', 'objects.githubusercontent.com'},
            'Unexpected public download redirect')
        while True:
            block = response.read(1024**2)
            if not block:
                break
            size += len(block)
            handoff.require(size <= row['bytes'] and time.monotonic() - began < 900,
                            'Public download exceeded byte/time budget')
            digest.update(block)
            output.write(block)
        output.flush()
        os.fsync(output.fileno())
    handoff.require(size == row['bytes'] and digest.hexdigest() == row['sha256'],
                    'Independently downloaded bytes differ')
    os.replace(pending, target)
    return dict(name=row['name'], bytes=size, sha256=digest.hexdigest(),
                anonymous_download=True, elapsed_seconds=time.monotonic() - began)


def retain_logs(work, out):
    """Keep actual command evidence, excluding raw decoded PCM sample streams."""
    kept = []
    for name in ('setup', 'authored-case', 'registered-case', 'preview'):
        source = work / name
        candidates = [source / leaf for leaf in ('calls.json', 'expected.json', 'verification.json')]
        logs = source / 'logs'
        if logs.is_dir():
            candidates.extend(sorted(logs.iterdir()))
        for path in candidates:
            if not path.is_file() or path.name.endswith('-PCM-samples.stdout'):
                continue
            handoff.require(path.stat().st_size <= 4 * 1024**2, 'Command evidence exceeds its budget')
            target = out / 'commands' / name / path.relative_to(source)
            target.parent.mkdir(parents=True, exist_ok=True)
            with path.open('rb') as original, target.open('xb') as copied:
                shutil.copyfileobj(original, copied)
            kept.append(dict(path=target.relative_to(out).as_posix(), bytes=target.stat().st_size,
                             sha256=handoff.sha(target)))
    return kept


def gallery(work, movie, case_module, tools, run_id):
    """Generate public previews of procedural diagnostics, not natural-quality examples."""
    preview = case_module.Case(work / 'preview', [], tools)
    original = work / 'authored-case/pattern.mp4'
    comparison = preview.root / 'comparison.mp4'
    animation = preview.root / 'comparison.gif'
    screenshot = preview.root / 'comparison.png'
    ffmpeg, ffprobe = tools / 'ffmpeg.exe', tools / 'ffprobe.exe'
    preview.call('comparison-encode', [ffmpeg, '-nostdin', '-v', 'error', '-i', original, '-i', movie,
        '-filter_complex', '[0:v][1:v]hstack=inputs=2[v]', '-map', '[v]', '-map', '1:a:0',
        '-c:v', 'libx264', '-threads', '2', '-pix_fmt', 'yuv420p', '-c:a', 'aac', comparison])
    preview.call('comparison-gif', [ffmpeg, '-nostdin', '-v', 'error', '-i', comparison,
        '-filter_complex', 'fps=10,split[a][b];[a]palettegen[p];[b][p]paletteuse',
        '-loop', '0', animation])
    preview.call('comparison-still', [ffmpeg, '-nostdin', '-v', 'error', '-ss', '0.5',
        '-i', comparison, '-frames:v', '1', screenshot])
    media = {}
    for label, path, frames in (('comparison', comparison, 60), ('gif', animation, 20)):
        raw = preview.call('probe-' + label, [ffprobe, '-v', 'error', '-count_frames',
            '-show_streams', '-show_format', '-of', 'json', path])
        probe = handoff.decode(raw)
        video = next(row for row in probe['streams'] if row['codec_type'] == 'video')
        handoff.require((video['width'], video['height'], int(video['nb_read_frames'])) == (640, 180, frames),
                        'Actual comparison preview dimensions/frame count differ')
        media[label] = dict(width=640, height=180, frames=frames,
            fps=video['avg_frame_rate'], duration=probe['format']['duration'])
    destination = handoff.local(ROOT / 'docs/assets/public-release66-20261106-r1' / run_id)
    handoff.require(not destination.exists(), 'Preserve the previous public preview run')
    destination.mkdir(parents=True)
    copies = [('source.mp4', original), ('actual.mp4', movie), ('comparison.mp4', comparison),
              ('comparison.gif', animation), ('comparison.png', screenshot)]
    artifacts = []
    for name, source in copies:
        target = destination / name
        with source.open('rb') as original_stream, target.open('xb') as output:
            shutil.copyfileobj(original_stream, output)
        artifacts.append(dict(path=target.relative_to(ROOT).as_posix(), bytes=target.stat().st_size,
                              sha256=handoff.sha(target)))
    metadata = dict(format='agent-editor-public-install-diagnostic-v1', cli_version=handoff.VERSION,
        source='Native FFmpeg testsrc2 and 440Hz sine authored by the public acceptance case',
        generated_media_license='CC0-1.0', source_video=dict(width=320, height=180, fps=30, frames=60, seconds=2),
        result_video=dict(width=320, height=180, fps=30, frames=60, seconds=2, stereo_sample_rate=48000),
        left='original procedural source', right='actual public-install output with t3-kodak-gold-200 strength0.65',
        complete_product_replay_checked=True, comparison_media=media, artifacts=artifacts,
        screenshot_time_seconds=0.5, model_inference=False, human_listening=False,
        continuous_playback_accepted=False, natural_quality_accepted=False)
    handoff.save(destination / 'metadata.json', metadata)
    return metadata


def run(args):
    handoff.require(os.name == 'nt' and sys.dont_write_bytecode and sys.prefix == sys.base_prefix,
                    'Use native Windows Python -B without a virtual environment')
    handoff.require(args.run.isalnum() and len(args.run) <= 32, 'Invalid run identifier')
    code = handoff.load(CODE_PHASE)
    handoff.require(code['status'] == 'code-complete-frozen'
        and code['functional_tests_started'] is False
        and all(handoff.sha(HERE / name) == value for name, value in code['files'].items())
        and Path(__file__).name in code['files']
        and handoff.sha(CASE) == CASE_SHA and handoff.sha(LOCK) == LOCK_SHA,
        'Complete frozen validation code and original lock are required')
    lock = handoff.load(LOCK)
    formal = handoff.load(handoff.BASE / 'formal-entry-r1/verification.json')
    formal_pins = dict(formal['skill_files'])
    formal_pins[handoff.MANIFEST] = handoff.sha(ROOT / handoff.MANIFEST)
    formal_pins[handoff.CONFIG] = handoff.sha(ROOT / handoff.CONFIG)
    global_entry = Path('C:/Users/carzy/.codex/skills/agent-ffmpeg-local-editor')
    global_target = global_entry.resolve(strict=True)
    handoff.require(formal['status'] == 'passed' and formal['formal_activation'], 'Formal acceptance is required')
    work = handoff.local(ROOT / 'local/agent-ffmpeg/delivery66-public-20261106-r1' / args.run)
    out = HERE / 'evidence/delivery66-public-20261106-r1' / args.run
    handoff.require(not work.exists() and not out.exists(), 'Preserve the original run; never restart into it')
    work.mkdir(parents=True)
    out.mkdir(parents=True)
    handoff.save(out / 'owner.json', dict(status='started',
        started_at_utc=dt.datetime.now(dt.timezone.utc).isoformat(),
        pid=os.getpid(), executable=str(Path(sys.executable).resolve()),
        source_commit=COMMIT, code_phase_sha256=handoff.sha(CODE_PHASE),
        native_only=True, private_credential_used=False, formal_activation=False))
    try:
        release = api('https://api.github.com/repos/copypasteltd/agent-editor-kit/releases/tags/' + handoff.TAG)
        tag = api('https://api.github.com/repos/copypasteltd/agent-editor-kit/git/ref/tags/' + handoff.TAG)
        marker = '<!-- agent-editor-kit-source:' + COMMIT + ';lock:' + LOCK_SHA + ' -->'
        handoff.require(release['draft'] is False and release['prerelease'] is True
            and release['tag_name'] == handoff.TAG and release['published_at']
            and marker in release.get('body', '') and tag['object']['type'] == 'commit'
            and tag['object']['sha'] == COMMIT, 'The exact reviewed release must already be public')
        published = {row['name']: row for row in release['assets']}
        handoff.require(set(published) == {row['name'] for row in lock['assets']}, 'Public attachment set differs')
        downloads = work / 'downloads'
        downloads.mkdir()
        results = []
        for row in lock['assets']:
            result = download(row, published[row['name']], downloads / row['name'])
            results.append(result)
            handoff.save(out / 'downloads.json', dict(files=results))
            print(json.dumps(dict(phase='downloaded', **result), ensure_ascii=False), flush=True)
        kit = work / '工具包 中文 spaces'
        bundle = work / 'application-bundle'
        inventory = handoff.extract(downloads / 'agent-editor-kit-community-unified-skill-r59.zip', kit, skill=True)
        handoff.extract(downloads / ('agent-editor-kit-' + handoff.TAG + '-cp313-win_amd64.zip'), bundle)
        handoff.require(inventory['cli_version'] == handoff.VERSION and inventory['skill_count'] == 1
                        and inventory['module_count'] == 17, 'Downloaded kit scope differs')
        spec = importlib.util.spec_from_file_location('aek_public_case', CASE)
        case_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(case_module)
        case_module.VERSION = handoff.VERSION
        tool_executable = shutil.which('ffmpeg.exe')
        handoff.require(tool_executable is not None, 'Existing native FFmpeg is required')
        tools = Path(tool_executable).resolve().parent
        handoff.require((tools / 'ffmpeg.exe').is_file() and (tools / 'ffprobe.exe').is_file(),
                        'Existing native FFmpeg and ffprobe are required')
        setup = case_module.Case(work / 'setup', [], tools)
        installed = work / 'application-installed'
        setup.call('offline-install', [sys.executable, '-E', '-B', '-u', '-X', 'utf8',
            bundle / 'install.py', '--bundle', bundle, '--target', installed,
            '--manifest-sha256', handoff.load(kit / handoff.MANIFEST)['manifest_sha256']])
        handoff.require(case_module.app_files(installed) == formal['application_files'],
                        'Downloaded installed application differs from accepted application')
        setup.call('base-configuration', [sys.executable, '-E', '-B', '-u', '-X', 'utf8',
            kit / 'scripts/activate_community_runtime.py', '--installed', installed, '--base-only'])
        runtime = handoff.load(kit / handoff.CONFIG)
        handoff.require(Path(runtime['installed_directory']) == installed
                        and handoff.load(kit / 'local/agent-ffmpeg/community-runtime.json') == {},
                        'Basic configuration retained unrelated model paths')
        discovery = work / 'isolated-discovery'
        setup.call('register', ['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
            kit / 'register-agent-ffmpeg-local-skills.ps1', '-SkillsDirectory', discovery,
            '-ReceiptPath', out / 'registration.json'])
        entry = discovery / 'agent-ffmpeg-local-editor/scripts/run.ps1'
        handoff.require(entry.parent.parent.resolve() == (kit / handoff.SKILL).resolve(),
                        'Actual isolated registration does not select the downloaded kit')
        actual = case_module.Case(work / 'registered-case',
            ['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', entry], tools)
        version = actual.cli('registered-version', 'version')
        schema_path = Path(version['data']['schema_validation']['path'])
        handoff.require(schema_path.is_relative_to(installed / 'site/ai_ad_editor'),
                        'Actual entry did not use its independently installed package')
        actual.cli('registered-capabilities', 'capabilities')
        case_module.prepare(argparse.Namespace(root=work / 'authored-case', installed=installed,
                                               python=Path(sys.executable), tools=tools))
        expected = handoff.load(work / 'authored-case/expected.json')
        project = work / 'registered-case/project'
        actual.cli('import', 'convert', 'import', '--input', work / 'authored-case/baseline.aevpkg.zip', '--output', project)
        actual.cli('validate', 'validate', '--project', project)
        movie = project / 'renders/public-roundtrip.mp4'
        actual.cli('render', 'render', '--project', project, '--output', movie)
        media = actual.decode(movie, 'actual')
        handoff.require(media['decoded'] == expected['complete_decoded']
                        and media['video'] == expected['video'], 'Full public-package RGBA/PCM/clock replay differs')
        assets = handoff.load(project / 'project.json')['assets']
        for asset_id, pin in expected['master_assets'].items():
            asset = next(row for row in assets if row['id'] == asset_id)
            handoff.require('sha256:' + handoff.sha(project / asset['uri']) == pin, 'Master asset changed')
        handoff.require(all(handoff.sha(ROOT / name) == value for name, value in formal_pins.items())
                        and global_entry.resolve(strict=True) == global_target,
                        'Public-package validation changed the existing formal installation')
        previews = gallery(work, movie, case_module, tools, args.run)
        logs = retain_logs(work, out)
        handoff.require(all(handoff.sha(HERE / name) == value for name, value in code['files'].items()),
                        'Frozen validation code changed during acceptance')
        handoff.save(out / 'verification.json', dict(status='passed', cli_version=handoff.VERSION,
            source_commit=COMMIT, release_url=release['html_url'], release_id=release['id'],
            published_at=release['published_at'], public_tag_commit=tag['object']['sha'],
            code_phase_sha256=handoff.sha(CODE_PHASE), command_evidence=logs, preview_gallery=previews,
            downloaded_assets=results, fresh_offline_install=True, actual_base_only_configuration=True,
            actual_isolated_single_Skill=True, actual_PowerShell_entry=True,
            application_modules=len(formal['application_files']), installed_directory=str(installed),
            registered_schema_path=str(schema_path), python_executable=str(Path(sys.executable).resolve()),
            source_fallback=False, complete_RGBA_PCM_clock_equal=True, complete_master_assets_equal=True,
            actual=media, expected=expected, global_formal_unchanged=True,
            model_inference=False, gpu_render=False, clean_host=False, cross_machine=False,
            human_listening=False, natural_quality_accepted=False, full_goal_closed=False))
        print(json.dumps(dict(phase='complete', status='passed', evidence=str(out / 'verification.json'))), flush=True)
    except BaseException as exc:
        logs = []
        try:
            if not (out / 'commands').exists():
                logs = retain_logs(work, out)
        except BaseException:
            pass
        handoff.save(out / 'verification.json', dict(status='failed-preserved',
            error_type=type(exc).__name__, error=str(exc), source_commit=COMMIT,
            command_evidence=logs,
            original_workspace_preserved=True, formal_activation=False, full_goal_closed=False))
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', required=True)
    run(parser.parse_args())
