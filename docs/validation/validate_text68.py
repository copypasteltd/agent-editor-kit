"""Freeze and collectively validate the isolated Unicode text68 candidate.

The full default Unicode17 test corpora are compared without exclusions or
rewritten expected boundaries. Public API tests and default corpus cases have
separate counts. This does not test or activate the installed product CLI.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
DEV = ROOT / 'development/text68'
BASE = ROOT / 'docs/validation/evidence/text68-20261106-r1'
PINS = {
    'GraphemeBreakTest.txt': 'e2d134d2c52919bace503ebb6a551c1855fe1a1faec18478c78fff254a1793ec',
    'LineBreakTest.txt': 'e69884e0dde6a8724873f885d68c52dc14518abf9ae4ca9e2283b8773db3b752',
}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(data, stream, ensure_ascii=False, indent=2)
        stream.write('\n')


def inputs():
    files = sorted(path for path in DEV.rglob('*') if path.is_file() and '__pycache__' not in path.parts)
    files += [Path(__file__).resolve(), ROOT / 'docs/validation/build_text68_candidate.py',
              ROOT / 'docs/validation/prepare_text68_sources.py']
    return {path.relative_to(ROOT).as_posix(): sha(path) for path in files}


def portrait_guard():
    path = ROOT / 'docs/validation/evidence/portrait67-20261106-r1/freeze-r1/verification.json'
    assert sha(path) == 'd8c6ccf3fd740ffc0063034e2a765d88b47e26f9d77c41d6a3a75a9446bd71a3'
    frozen = json.loads(path.read_text(encoding='utf-8'))
    maps = [frozen[key] for key in ('file_hashes', 'delivery_tool_files', 'packaging_source_files')]
    assert all(sha(ROOT / name) == digest for mapping in maps for name, digest in mapping.items()), 'CLI67 frozen input changed'
    return dict(freeze_sha256=sha(path), product_test_dependency_count=len(maps[0]),
                delivery_tool_count=len(maps[1]), packaging_source_count=len(maps[2]), unchanged=True)


def freeze(run):
    assert (DEV / 'src/aek_unicode17/SOURCE_MANIFEST.json').is_file()
    record = dict(status='frozen-before-collective-tests', observed_at_utc=datetime.now(timezone.utc).isoformat(),
        unicode_version='17.0.0', file_hashes=inputs(), product67_modified=False,
        installed_skill_modified=False, goal_closed=False, tests_started=False,
        portrait67_guard=portrait_guard())
    save(BASE / ('freeze-' + run) / 'verification.json', record)
    print(json.dumps({key: value for key, value in record.items() if key != 'file_hashes'}))


def test_case(line):
    tokens = line.split('#', 1)[0].split()
    if not tokens:
        return None
    assert len(tokens) % 2 == 1
    chars, expected = [], []
    for index in range(0, len(tokens), 2):
        assert tokens[index] in ('÷', '×')
        if tokens[index] == '÷':
            expected.append(len(chars))
        if index + 1 < len(tokens):
            chars.append(chr(int(tokens[index + 1], 16)))
    return ''.join(chars), expected


def corpus(name, raw, implementation, expected_sha):
    assert hashlib.sha256(raw).hexdigest() == expected_sha
    failures, total, examples = [], 0, []
    for number, line in enumerate(raw.decode('utf-8-sig').splitlines(), 1):
        parsed = test_case(line)
        if parsed is None:
            continue
        text, expected = parsed
        total += 1
        try:
            actual = list(implementation(text))
        except Exception as exc:
            actual = [f'{type(exc).__name__}: {exc}']
        if actual != expected:
            failures.append(number)
            if len(examples) < 64:
                examples.append(dict(line=number, codepoints=[f'{ord(c):04X}' for c in text],
                                     expected=expected, actual=actual))
    assert total > 0
    return dict(name=name, cases=total, passed=total - len(failures), failed=len(failures),
                skipped=0, excluded=0, input_sha256=expected_sha, failed_lines=failures, examples=examples)


def tests(run, freeze_run, source_run):
    target = BASE / ('tests-' + run)
    target.mkdir(parents=True, exist_ok=False)
    frozen_path = BASE / ('freeze-' + freeze_run) / 'verification.json'
    frozen = json.loads(frozen_path.read_text(encoding='utf-8'))
    assert frozen['file_hashes'] == inputs(), 'Candidate changed after freeze'
    portrait_guard()
    sys.path.insert(0, str(DEV / 'src'))
    suite = unittest.TestLoader().discover(str(DEV / 'tests'), pattern='test_*.py')
    logs = io.StringIO()
    result = unittest.TextTestRunner(stream=logs, verbosity=2).run(suite)
    (target / 'tests.stderr').write_text(logs.getvalue(), encoding='utf-8', newline='\n')
    from aek_unicode17._vendor.graphemecluster import grapheme_cluster_boundaries
    from aek_unicode17._vendor.linebreak import line_break_boundaries
    ucd = ROOT / ('local/agent-ffmpeg/text68-20261106-' + source_run) / 'upstream/unicode17/auxiliary'
    cases = [corpus('GraphemeBreakTest-17.0.0', (ucd / 'GraphemeBreakTest.txt').read_bytes(),
                    grapheme_cluster_boundaries, PINS['GraphemeBreakTest.txt']),
             corpus('LineBreakTest-17.0.0', (ucd / 'LineBreakTest.txt').read_bytes(),
                    line_break_boundaries, PINS['LineBreakTest.txt'])]
    unchanged = frozen['file_hashes'] == inputs()
    passed = result.wasSuccessful() and not result.skipped and all(row['failed'] == 0 for row in cases) and unchanged
    record = dict(status='passed' if passed else 'failed', observed_at_utc=datetime.now(timezone.utc).isoformat(),
        freeze_sha256=sha(frozen_path), frozen_inputs_unchanged=unchanged,
        public_api_contracts=dict(tests=result.testsRun, failures=len(result.failures), errors=len(result.errors),
                                  skipped=len(result.skipped), successful=result.wasSuccessful()),
        unicode_default_corpora=cases, product_cli_tested=False, installed_skill_modified=False,
        dependency_installation=False, neural_model_forwards=0, gpu_used=False,
        typography_renderer_integrated=False, full_bidi_implemented=False, goal_closed=False,
        portrait67_guard=portrait_guard())
    save(target / 'verification.json', record)
    print(json.dumps({key: value for key, value in record.items() if key != 'unicode_default_corpora'}, ensure_ascii=False))
    print(json.dumps([{key: value for key, value in row.items() if key not in ('examples', 'failed_lines')} for row in cases]))
    return 0 if passed else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['freeze', 'tests'])
    parser.add_argument('--run', required=True)
    parser.add_argument('--freeze-run', default='r1')
    parser.add_argument('--source-run', default='r2')
    args = parser.parse_args()
    assert all(value.isalnum() and len(value) <= 32 for value in [args.run, args.freeze_run, args.source_run])
    if args.action == 'freeze':
        freeze(args.run)
        return 0
    return tests(args.run, args.freeze_run, args.source_run)


if __name__ == '__main__':
    raise SystemExit(main())
