"""Run a bounded test scope against explicit source/installed bytes with frozen receipts."""
from pathlib import Path
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
import re
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]


def sha(path):
    with path.open('rb') as stream:
        return 'sha256:' + hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--site', type=Path, required=True)
    parser.add_argument('--pattern', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--test-name', help='optional exact unittest name for a failed-method recheck')
    args = parser.parse_args()
    site, output = args.site.resolve(strict=True), args.output.resolve()
    assert output.is_relative_to(ROOT / 'docs/validation/evidence') and not output.exists()
    output.mkdir(parents=True)
    (output / 'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    def frozen():
        paths = sorted((site / 'ai_ad_editor').glob('*.py')) + sorted((ROOT / 'product/tests').glob(args.pattern))
        return [dict(path=str(path), bytes=path.stat().st_size, sha256=sha(path)) for path in paths]
    command = [sys.executable, '-E', '-B', '-X', 'utf8', '-c',
        'import sys,unittest;sys.path.insert(0,sys.argv.pop(1));from ai_ad_editor.runtime import configure_local_runtime;configure_local_runtime();unittest.main(module=None)',
        str(site), 'discover', '-s', str(ROOT / 'product/tests'), '-p', args.pattern, '-v']
    if args.test_name:
        command = [sys.executable, '-E', '-B', '-X', 'utf8', '-c',
            'import sys,unittest;sys.path.insert(0,sys.argv.pop(1));sys.path.insert(0,sys.argv.pop(1));from ai_ad_editor.runtime import configure_local_runtime;configure_local_runtime();unittest.main(module=None)',
            str(site), str(ROOT / 'product/tests'), args.test_name, '-v']
    receipt = dict(started_at_utc=datetime.now(timezone.utc).isoformat(), command=command, site=str(site),
        pattern=args.pattern, frozen_before=frozen(), native_windows=True, virtualization=False)
    if args.test_name:
        receipt['selected_test'] = args.test_name
    environment = dict(os.environ, PYTHONPATH=str(site), PYTHONDONTWRITEBYTECODE='1', PYTHONUTF8='1')
    started = time.monotonic()
    with (output / 'tests.log').open('wb') as stream:
        result = subprocess.run(command, cwd=ROOT, stdout=stream, stderr=subprocess.STDOUT, env=environment,
            timeout=1800, creationflags=subprocess.CREATE_NO_WINDOW)
    log = (output / 'tests.log').read_text('utf8', errors='replace')
    match = re.search(r'Ran (\d+) tests? in ([0-9.]+)s', log)
    receipt.update(finished_at_utc=datetime.now(timezone.utc).isoformat(), exit_code=result.returncode,
        wall_seconds=time.monotonic() - started, frozen_after=frozen(), log_sha256=sha(output / 'tests.log'),
        methods=int(match[1]) if match else None, suite_seconds=float(match[2]) if match else None,
        skipped=len(re.findall(r'\.\.\. skipped ', log)), terminal_ok=bool(re.search(r'^OK\s*$', log, re.M)))
    receipt['frozen_equal'] = receipt['frozen_before'] == receipt['frozen_after']
    (output / 'verification.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    print(json.dumps({k:v for k,v in receipt.items() if k not in ('command','frozen_before','frozen_after')}, ensure_ascii=False), flush=True)
    raise SystemExit(0 if result.returncode == 0 and receipt['frozen_equal'] and receipt['terminal_ok'] else 1)


if __name__ == '__main__':
    main()
