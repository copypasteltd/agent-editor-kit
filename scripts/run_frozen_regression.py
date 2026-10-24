"""Run native offline unittest discovery and retain byte-frozen evidence."""
from __future__ import annotations
import argparse, hashlib, json, os, re, subprocess, sys, time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def sha(path):
    return 'sha256:'+hashlib.sha256(path.read_bytes()).hexdigest()

def frozen():
    paths = [*(ROOT/'product/src').rglob('*.py'), *(ROOT/'product/tests').rglob('*.py'),
             *(ROOT/'product/src').rglob('*.mjs'), ROOT/'product/pyproject.toml',
             *(ROOT/'product/src').rglob('*.c'), *(ROOT/'product/src').rglob('*.dll'),
             *([ROOT/'product/setup.py'] if (ROOT/'product/setup.py').is_file() else []),
             ROOT/'docs/specs/agent-project.schema.json', *(ROOT/'product/src').rglob('*.json'),
             *(ROOT/'product/src').rglob('*LICENSE*.txt'), *(ROOT/'product/src').rglob('*NOTICE*.txt'), *(ROOT/'product/offline').glob('*.py')]
    return {p.relative_to(ROOT).as_posix(): sha(p) for p in sorted(paths)}

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, required=True, help='new JSON evidence path; adjacent .log is retained')
    parser.add_argument('--pattern', default='test*.py')
    parser.add_argument('--installed', type=Path, help='test an explicit native installed release with -I -S, never source fallback')
    parser.add_argument('--html-runtime', type=Path, default=os.environ.get('AI_AD_EDITOR_TEST_HTML_RUNTIME'),
                        help='explicit existing native Node/playwright-core/Chromium JSON; never downloads')
    parser.add_argument('--rubberband', type=Path, default=os.environ.get('AI_AD_EDITOR_TEST_RUBBERBAND'),
                        help='explicit existing native executable, with COPYING.txt and sndfile.dll beside it')
    args = parser.parse_args()
    output = args.output.resolve()
    log = output.with_suffix('.log')
    assert not output.exists() and not log.exists(), 'choose fresh evidence paths'
    output.parent.mkdir(parents=True, exist_ok=True)
    before = frozen()
    record = {'started_at_utc': datetime.now(timezone.utc).isoformat(), 'pattern': args.pattern, 'frozen_before': before,
              'native_windows': sys.platform == 'win32', 'virtualization': False}
    module_root = ROOT/'product/src'
    installed_files = []
    if args.installed:
        installed = args.installed.resolve(strict=True)
        module_root = installed/'site'
        if not all(p.is_file() for p in (installed/'receipt.json', installed/'run.py', module_root/'ai_ad_editor/__init__.py')):
            parser.error('--installed requires a complete explicit installed release')
        installed_files = [p for p in (module_root/'ai_ad_editor').rglob('*')
                           if p.is_file() and p.suffix in {'.py', '.mjs', '.json', '.c', '.dll', '.txt'}]
        installed_files += [installed/'receipt.json', installed/'run.py']
        record['installed_release'] = {'directory': str(installed),
             'manifest_sha256': json.loads((installed/'receipt.json').read_bytes())['manifest_sha256'],
             'frozen_before': {str(p.relative_to(installed)): sha(p) for p in sorted(installed_files)}}
    if args.rubberband:
        binary = args.rubberband.resolve(strict=True)
        paths = [binary, binary.with_name('COPYING.txt'), binary.with_name('sndfile.dll')]
        if not all(p.is_file() for p in paths):
            parser.error('--rubberband requires the existing executable, COPYING.txt and sndfile.dll')
        record['native_audio_toolchain'] = {str(p): {'sha256': sha(p), 'bytes': p.stat().st_size} for p in paths}
    def save():
        output.write_text(json.dumps(record, ensure_ascii=False, indent=2)+'\n', encoding='utf-8', newline='\n')
    save()
    bootstrap = ('import sys,unittest;sys.path.insert(0,sys.argv.pop(1));'
                 'from ai_ad_editor.runtime import configure_local_runtime;configure_local_runtime();'
                 'unittest.main(module=None)')
    command = [sys.executable, *(['-I', '-S'] if args.installed else ['-E']), '-B', '-X', 'utf8', '-c', bootstrap, str(module_root),
               'discover', '-s', str(ROOT/'product/tests'), '-p', args.pattern, '-v']
    env = dict(os.environ)
    env.update(TEMP=str(ROOT/'product/.runtime/temp'), TMP=str(ROOT/'product/.runtime/temp'),
               TMPDIR=str(ROOT/'product/.runtime/temp'), PYTHONDONTWRITEBYTECODE='1',
               PYTHONPATH=str(module_root))
    if args.installed:
        env['AI_AD_EDITOR_RUNTIME_DIR'] = str(installed/'runtime')
    if args.rubberband:
        env['AI_AD_EDITOR_TEST_RUBBERBAND'] = str(binary)
    if args.html_runtime:
        html_runtime = args.html_runtime.resolve(strict=True)
        record['native_html_configuration'] = {'path': str(html_runtime), 'sha256': sha(html_runtime)}
        env['AI_AD_EDITOR_TEST_HTML_RUNTIME'] = str(html_runtime)
    record['subprocess_product_pythonpath'] = env['PYTHONPATH']
    record['command'] = command
    save()
    started = time.monotonic()
    with log.open('wb') as stream:
        result = subprocess.run(command, cwd=ROOT, env=env, stdout=stream, stderr=subprocess.STDOUT)
    text = log.read_text(encoding='utf-8')
    match = re.search(r'Ran (\d+) tests in ([\d.]+)s', text)
    after = frozen()
    record.update(finished_at_utc=datetime.now(timezone.utc).isoformat(), exit_code=result.returncode,
                  wall_seconds=time.monotonic()-started, frozen_after=after, frozen_equal=before == after,
                  log_sha256=sha(log), methods=int(match[1]) if match else None,
                  suite_seconds=float(match[2]) if match else None,
                  skipped=len(re.findall(r'\.\.\. skipped ', text)), terminal_ok=bool(re.search(r'\bOK\s*$', text)))
    if args.installed:
        info = record['installed_release']
        info['frozen_after'] = {str(p.relative_to(installed)): sha(p) for p in sorted(installed_files)}
        info['frozen_equal'] = info['frozen_before'] == info['frozen_after']
        record['frozen_equal'] = record['frozen_equal'] and info['frozen_equal']
    save()
    print(json.dumps({k: record[k] for k in ('exit_code', 'methods', 'suite_seconds', 'skipped', 'frozen_equal', 'terminal_ok')}))
    return 0 if result.returncode == 0 and record['terminal_ok'] and record['frozen_equal'] else 1

if __name__ == '__main__':
    raise SystemExit(main())
