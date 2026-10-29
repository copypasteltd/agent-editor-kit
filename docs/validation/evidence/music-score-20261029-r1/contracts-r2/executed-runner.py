"""Run frozen native CLI59 score/PCM/transaction contracts on E:."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', required=True)
    args = parser.parse_args()
    assert args.run.replace('-', '').isalnum() and sys.dont_write_bytecode
    out = ROOT/'docs/validation/evidence/music-score-20261029-r1'/('contracts-'+args.run)
    out.mkdir(parents=True, exist_ok=False)
    (out/'executed-runner.py').write_bytes(Path(__file__).read_bytes())
    temporary = ROOT/'local/agent-ffmpeg'/('music-score59-temp-'+args.run)
    temporary.mkdir(exist_ok=False)
    os.environ.update(TEMP=str(temporary), TMP=str(temporary), PYTHONDONTWRITEBYTECODE='1')
    sys.path[:0] = [str(ROOT/'product/src'), str(ROOT/'product/tests')]
    paths = [*sorted((ROOT/'product/src/ai_ad_editor').glob('*.py')),
             ROOT/'product/tests/test_music_score.py', ROOT/'product/pyproject.toml']
    def pins():
        return {p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
    before = pins()
    print(json.dumps(dict(status='started', frozen_files=len(before))), flush=True)
    suite = unittest.defaultTestLoader.loadTestsFromName('test_music_score')
    with (out/'tests.stderr').open('w', encoding='utf-8', newline='\n') as stream:
        result = unittest.TextTestRunner(stream=stream, verbosity=2).run(suite)
    frozen = before == pins()
    report = dict(status='passed' if result.wasSuccessful() and frozen else 'failed',
                  tests=result.testsRun, failures=len(result.failures), errors=len(result.errors),
                  skipped=len(result.skipped), frozen_equal=frozen, file_hashes=before,
                  source_fallback=False, scope='source-CLI59-score-PCM-and-transaction-contracts',
                  installed59_accepted=False, neural_music_accepted=False, human_listening=False,
                  full_product_goal_closed=False)
    (out/'verification.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k != 'file_hashes'}), flush=True)
    return 0 if report['status'] == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
