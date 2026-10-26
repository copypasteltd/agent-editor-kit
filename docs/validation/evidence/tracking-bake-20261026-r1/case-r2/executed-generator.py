"""C42: registered installed native binding bake/export/import and full media proof."""
import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
import shutil
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT/'docs/validation/evidence/tracking-bake-20261026-r1'
INSTALL = ROOT/'local/agent-ffmpeg/v0.1.0-alpha.4-local.30/final-r1/installed'


def sha(path):
    with Path(path).open('rb') as stream: return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--run', required=True); a = ap.parse_args()
    assert a.run.replace('-', '').isalnum()
    out = BASE/('case-' + a.run); out.mkdir(exist_ok=False)
    work = ROOT/'workspace'/('tracking-bake-20261026-case-' + a.run); work.mkdir(exist_ok=False)
    public = ROOT/'docs/assets'/('tracking-bake-20261026-' + a.run); public.mkdir(exist_ok=False)
    (out/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    prefix = ['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File',
              'C:/Users/carzy/.codex/skills/agent-ffmpeg-local-editor/scripts/run.ps1']
    report = dict(status='running', cli_version='0.1.32', installed=str(INSTALL), registered_skill=True,
        source_fallback=False, virtualization=False, new_model_forwards=0, external_renderer_verified=False,
        continuous_playback=False, human_listening=False, checks=[], calls=[], started_at_utc=datetime.now(timezone.utc).isoformat())
    def save(name, value): (out/name).write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf8', newline='\n')
    def check(name, value):
        report['checks'].append(dict(name=name, ok=bool(value))); save('verification.json', report)
        assert value, name
    def run(name, args, *, code=0, binary=False):
        args = list(map(str, args)); start = time.perf_counter()
        value = subprocess.run(args, cwd=ROOT, capture_output=True, timeout=900, creationflags=subprocess.CREATE_NO_WINDOW)
        stdout = (work if binary else out)/(name + ('.bin' if binary else '.stdout.log'))
        stderr = out/(name+'.stderr.log'); stdout.write_bytes(value.stdout); stderr.write_bytes(value.stderr)
        report['calls'].append(dict(name=name, argv=args, exit_code=value.returncode, expected_exit_code=code,
            stdout_path=str(stdout), stdout_sha256=sha(stdout), stderr_sha256=sha(stderr), seconds=time.perf_counter()-start))
        save('verification.json', report); print(json.dumps(dict(name=name, code=value.returncode)), flush=True)
        assert value.returncode == code, (name, value.stdout[-3000:], value.stderr[-3000:])
        return value.stdout
    def cli(name, *args, code=0):
        value = json.loads(run(name, [*prefix, *args], code=code)); assert bool(value['ok']) == (code == 0)
        return value
    def bindings(project):
        return {s['id']+'/'+c['id']: c['tracking_binding'] for s in project['sequences'] for t in s['tracks'] for c in t['clips'] if c.get('tracking_binding')}
    def media(name, path):
        raw = run(name+'-frames', [ffmpeg, '-nostdin', '-v', 'error', '-i', path, '-map', '0:v:0',
            '-pix_fmt', 'rgba64le', '-f', 'framemd5', '-'])
        rows = [line.split(',') for line in raw.decode().splitlines() if line and not line.startswith('#')]
        pcm = run(name+'-pcm', [ffmpeg, '-nostdin', '-v', 'error', '-i', path, '-map', '0:a:0',
            '-c:a', 'pcm_f32le', '-f', 'f32le', '-'], binary=True)
        check(name+' all frame clocks/full stereo PCM count', len(rows)==36 and [int(r[2]) for r in rows]==list(range(36)) and len(pcm)==144000*2*4)
        return dict(frames=[r[-1].strip() for r in rows], pcm_sha256=hashlib.sha256(pcm).hexdigest())
    try:
        check('registered installed version', cli('version', 'version')['data']['cli_version']=='0.1.32')
        configured = json.loads((ROOT/'local/agent-ffmpeg/runtime.json').read_bytes())
        check('actual installed directory', Path(configured['installed_directory']).resolve()==INSTALL.resolve())
        # The immutable C41 package has its independent point/pixel oracle in
        # the previous delivery; this case exercises interoperability on it.
        project = work/'原始 工程'
        cli('import-original', 'convert', 'import', '--input', ROOT/'docs/assets/tracking-visibility-20261026-r2/editable-tracking-visibility.aevpkg.zip', '--output', project)
        author = json.loads((project/'project.json').read_bytes()); original_sha = sha(project/'project.json')
        ledger_sha = sha(project/'rights-ledger.json'); original_bindings = bindings(author)
        check('source has both retained native bindings', len(original_bindings)==2)
        assets = {row['id']: row['sha256'] for row in author['assets']}
        package = public/'editable-baked-tracking.aevpkg.zip'
        exported = cli('export-baked-package', 'convert', 'export', '--project', project, '--target-format', 'package',
            '--bake-tracking', '--output', package)['data']
        proof = exported['report_data']['tracking_bake']; save('native-bake-proof.json', proof)
        check('actual full Float32 verification, original preserved', proof['verified_frames']==36 and proof['samples']>=45 and proof['all_float32_frames_equal'] and not proof['original_project_modified'])
        # This is a frame-only operation: the GPU transport remains prepared;
        # encoded-movie quality acceptance belongs to the render command.
        check('actual GPU operations in both frame-only passes and cleanup', all(r['providers_closed'] and r['projection_acceleration']['status']=='prepared'
            and r['projection_acceleration']['operations']['affine']>=36 and r['projection_acceleration']['operations']['over']>0
            and r['projection_acceleration']['worker_closed'] and r['projection_acceleration']['shared_handles_closed'] for r in proof['receipts']))
        source = json.loads(Path(exported['source_sidecar']).read_bytes())
        check('original observation dictionaries retained in sidecar', bindings(source)==original_bindings)
        restored = work/'烘焙 导入'
        cli('import-baked-package', 'convert', 'import', '--input', package, '--output', restored)
        imported = json.loads((restored/'project.json').read_bytes())
        check('imported ordinary hold keys without active bindings', not bindings(imported)
            and any(t['property']=='transform.position.x' for track in imported['sequences'][0]['tracks'] for c in track['clips'] for t in c.get('keyframes', [])))
        check('asset IDs and hashes preserved', {r['id']: r['sha256'] for r in imported['assets']}==assets)
        cli('validate-baked-package', 'validate', '--project', restored)
        original_movie = project/'renders/original.mkv'; baked_movie = restored/'renders/baked.mkv'
        native_render = cli('render-original', 'render', '--project', project, '--output', original_movie)['data']
        baked_render = cli('render-baked', 'render', '--project', restored, '--output', baked_movie)['data']
        ffmpeg = configured['installed_directory'] + '/bin/ffmpeg.exe'
        if not Path(ffmpeg).is_file():
            import sys
            sys.path.insert(0, str(INSTALL/'site'))
            from ai_ad_editor.runtime import configure_local_runtime
            from ai_ad_editor.media import ffmpeg_path
            configure_local_runtime(); ffmpeg = ffmpeg_path()
        before, after = media('original', original_movie), media('baked', baked_movie)
        check('every decoded frame and complete PCM preserved', before==after)
        save('decoded-full-media.json', dict(original=before, baked=after))
        exports = []
        for fmt, suffix in [('agent-json', 'json'), ('otio', 'otio'), ('kdenlive-xml', 'mlt'), ('jianying-draft-json', 'draft.json')]:
            target = project/'exports'/('baked.'+suffix)
            extra = ['--bake-tracking'] if fmt=='agent-json' else []
            result = cli('export-'+fmt, 'convert', 'export', '--project', project, '--target-format', fmt,
                '--output', target, *extra)['data']
            receipt = result['report_data']['tracking_bake']
            check(fmt+' verified native bake and explicit external boundary', receipt['verified_frames']==36
                and receipt['all_float32_frames_equal'] and not receipt['external_renderer_verified'])
            check(fmt+' full source sidecar bindings', bindings(json.loads(Path(result['source_sidecar']).read_bytes()))==original_bindings)
            destination = work/('导入 '+fmt)
            cli('import-'+fmt, 'convert', 'import', '--input', target, '--output', destination)
            reimported = json.loads((destination/'project.json').read_bytes())
            check(fmt+' reimport contains no active binding', not bindings(reimported))
            exports.append(dict(format=fmt, output=str(target), verified_frames=receipt['verified_frames'],
                external_renderer_verified=False, report=str(result['report'])))
        save('format-exports.json', exports)
        strict = project/'exports/strict.json'
        value = cli('strict-draft-rejected', 'convert', 'export', '--project', project, '--target-format', 'jianying-draft-json',
            '--strict', '--output', strict, code=2)
        check('strict draft remains rejected and publishes no files', not strict.exists()
            and not strict.with_suffix('.json.source-agent.json').exists() and 'CONVERSION_STRICT_REJECTED' in json.dumps(value))
        cli('source-overwrite-rejected', 'convert', 'export', '--project', project, '--target-format', 'agent-json',
            '--bake-tracking', '--output', project/'project.json', code=2)
        check('original author and rights files unchanged through all conversions', sha(project/'project.json')==original_sha and sha(project/'rights-ledger.json')==ledger_sha)
        for name, movie in [('original', original_movie), ('baked', baked_movie)]:
            run('public-'+name, [ffmpeg, '-nostdin', '-v', 'error', '-n', '-i', movie, '-c:v', 'libx264', '-crf', '16',
                '-pix_fmt', 'yuv444p', '-c:a', 'aac', '-b:a', '96k', '-movflags', '+faststart', public/(name+'.mp4')])
        run('comparison-gif', [ffmpeg, '-nostdin', '-v', 'error', '-n', '-i', original_movie, '-i', baked_movie,
            '-filter_complex', '[0:v][1:v]hstack,fps=8,split[a][b];[a]palettegen[p];[b][p]paletteuse', '-an', public/'comparison.gif'])
        run('still', [ffmpeg, '-nostdin', '-v', 'error', '-n', '-ss', '1.833333', '-i', public/'comparison.gif', '-frames:v', '1', public/'comparison.png'])
        previous = ROOT/'docs/assets/tracking-visibility-20261026-r2'
        (public/'SOURCE.txt').write_text('C42 reuses the self-authored C41 CC0 geometry/marker/synthetic tone. Full source and font terms: ../tracking-visibility-20261026-r2/SOURCE.txt.\nLeft: native dynamic bindings. Right: verified ordinary hold-key export. Both are actual renders. GIF is silent. Original immutable C41 package remains separate.\nNo natural identity, external-editor runtime, continuous playback or human listening acceptance.\n', encoding='utf8')
        # Original editable source is already published and is not overwritten.
        check('immutable C41 source package retained', (previous/'editable-tracking-visibility.aevpkg.zip').is_file())
        files = [dict(path=p.name, bytes=p.stat().st_size, sha256=sha(p)) for p in sorted(public.iterdir()) if p.is_file()]
        (public/'media-manifest.json').write_text(json.dumps(dict(files=files, frames=36, seconds=3, fps=12,
            full_pcm_samples_per_channel=144000, gif_fps=8, gif_frames=24, external_renderer_verified=False), ensure_ascii=False, indent=2)+'\n', encoding='utf8', newline='\n')
        report.update(status='passed', project=str(project), baked_project=str(restored), public=str(public),
            float32_verified_frames=36, decoded_equal_frames=36, full_pcm_samples_per_channel=144000,
            formats=[r['format'] for r in exports]+['package'], package_sha256=sha(package),
            original_project_sha256=original_sha, rights_sha256=ledger_sha, finished_at_utc=datetime.now(timezone.utc).isoformat())
        save('verification.json', report); print(json.dumps({k:v for k,v in report.items() if k not in ('calls', 'checks')}, ensure_ascii=False), flush=True)
    except BaseException as exc:
        report.update(status='failed', error=repr(exc)); save('verification.json', report); raise


if __name__=='__main__': main()
