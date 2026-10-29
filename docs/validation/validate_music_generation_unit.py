"""Run bounded music contracts. Test fixtures are not model inference evidence."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import time
import unittest

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run', required=True)
    args = parser.parse_args()
    if not args.run.isalnum() or not sys.dont_write_bytecode:
        raise ValueError('Use -B and an alphanumeric run identifier')
    proof = ROOT / f'docs/validation/evidence/music-generation-20261030-{args.run}/unit'
    proof.mkdir(parents=True)
    work = ROOT / f'local/agent-ffmpeg/music-generation-unit-{args.run}'
    work.mkdir()
    os.environ['TMP'] = os.environ['TEMP'] = str(work)
    sys.path[:0] = [str(ROOT / 'product/src'), str(ROOT / 'product/tests')]
    started = time.monotonic()
    suite = unittest.defaultTestLoader.loadTestsFromName('test_music_generation')
    with (proof / 'tests.stdout').open('w', encoding='utf-8') as log:
        result = unittest.TextTestRunner(stream=log, verbosity=2).run(suite)
    paths = ['product/tests/test_music_generation.py'] + [
        'product/src/ai_ad_editor/' + name + '.py' for name in (
            'local_music_generation', 'music_generation_model', 'music_generation_worker',
            'music_generation_pipeline', 'music_generation_cli')]
    files = [{
        'path':path, 'sha256':hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
    } for path in paths]
    report = dict(status='passed' if result.wasSuccessful() else 'failed',
                  scope='input, immutable recipe and worker response contracts; no inference',
                  tests=result.testsRun, failures=len(result.failures), errors=len(result.errors),
                  skipped=len(result.skipped), elapsed_seconds=time.monotonic() - started,
                  music_generated=False, files=files)
    (proof / 'verification.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(report), flush=True)
    if not result.wasSuccessful():
        print((proof / 'tests.stdout').read_text(encoding='utf-8'), flush=True)
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    raise SystemExit(main())
