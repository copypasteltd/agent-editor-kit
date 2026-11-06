"""Freeze the complete shaping batch, then run all native contracts and UAX9 corpora."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
DEV = ROOT / 'development/shaping69'
BASE = ROOT / 'docs/validation/evidence/shaping69-20261107-r1'
TOOLS = ['prepare_shaping69_sources.py', 'build_shaping69.py', 'validate_shaping69.py', 'shaping69_case.py']
PINS = {'BidiTest.txt': '888bdfc8090652272d1f859cdb00ae659e2dc6c26740be61ef1d03998a687620',
        'BidiCharacterTest.txt': 'a3e6e905ab5afbe318a96df5401d0372a04cd73ef139ab5e3cf0ae241c255488'}
REPRESENTATIVES = dict(L='A', R='א', AL='ا', EN='1', AN='١', ES='+', ET='$', CS=',', NSM='\u0300',
    BN='\u0000', B='\u2029', S='\t', WS=' ', ON='!', LRE='\u202a', RLE='\u202b', LRO='\u202d',
    RLO='\u202e', PDF='\u202c', LRI='\u2066', RLI='\u2067', FSI='\u2068', PDI='\u2069')


def sha(path):
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def save(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def inputs():
    files = sorted(path for path in DEV.rglob('*') if path.is_file() and '__pycache__' not in path.parts)
    files += [ROOT / 'docs/validation' / name for name in TOOLS]
    files += sorted(path for path in (ROOT / 'development/text68/src').rglob('*') if path.is_file() and '__pycache__' not in path.parts)
    files += [ROOT / 'product/src/ai_ad_editor/material_data/fonts/noto-sans-sc-variable.ttf',
              ROOT / 'product/src/ai_ad_editor/material_data/licenses/google-notosanssc.txt', ROOT / 'LICENSE']
    return {path.relative_to(ROOT).as_posix(): sha(path) for path in files}


def portrait_guard():
    path = ROOT / 'docs/validation/evidence/portrait67-20261106-r1/freeze-r1/verification.json'
    assert sha(path) == 'd8c6ccf3fd740ffc0063034e2a765d88b47e26f9d77c41d6a3a75a9446bd71a3'
    frozen = json.loads(path.read_bytes())
    names = ('file_hashes', 'formal_guard', 'delivery_tool_files', 'packaging_source_files')
    for key in names:
        assert all(sha(ROOT / name) == pin for name, pin in frozen[key].items()), 'Original CLI67/formal66 freeze changed'
    return {key: len(frozen[key]) for key in names}


def source_guard(run):
    stage = ROOT / ('local/agent-ffmpeg/shaping69-20261106-' + run)
    manifest = stage / 'sources.json'
    rows = json.loads(manifest.read_bytes())
    assert rows['status'] == 'downloaded-for-review-not-executed'
    for row in rows['sources'] + rows['extracted']:
        assert sha(stage / row['path']) == row['sha256']
    for row in rows['sources']:
        if 'license_path' in row:
            assert sha(stage / row['license_path']) == row['license_sha256']
    for name, expected in PINS.items():
        assert sha(stage / 'upstream' / name) == expected
    assert sha(stage / 'upstream/freetype-2.15.0.tar.gz') == '87c7f1f8699b91e89f773f7dcfa505b044e1dae67f62a55d4e29c3afdcac4fb8'
    return sha(manifest)


def guard(frozen):
    assert frozen['file_hashes'] == inputs(), 'Candidate changed after full-batch freeze'
    assert frozen['source_manifest_sha256'] == source_guard(frozen['source_run'])
    assert frozen['portrait_guard'] == portrait_guard()


def freeze(run, source_run):
    required = ['native/aek_text_native.cpp', 'aek_shaping69.py', 'src/aek_shaping/native.py',
                'src/aek_shaping/layout.py', 'src/aek_shaping/cli.py', 'src/aek_shaping/png.py',
                'tests/font_fixture.py', 'tests/test_shaping69.py']
    assert all((DEV / name).is_file() for name in required)
    record = dict(status='complete-batch-frozen-before-build-and-tests', observed_at_utc=datetime.now(timezone.utc).isoformat(),
        file_hashes=inputs(), source_run=source_run, source_manifest_sha256=source_guard(source_run),
        portrait_guard=portrait_guard(), planned_units=['native-bidi', 'scripts', 'OpenType-shaping', 'GDEF-selections',
            'font-stack', 'variation', 'lossless-wrapping', 'prefix-reshaping', 'actual-grayscale-raster',
            'strict-CLI', 'atomic-publication', 'native-build', 'complete-UAX9-corpora', 'actual-font-contracts',
            'actual-media-case', 'portable-archive-replay'],
        functional_validation_started=False, native_libraries_loaded=False, product_integrated=False,
        formal_skill_modified=False, full_goal_closed=False)
    save(BASE / ('freeze-' + run) / 'verification.json', record)
    print(json.dumps({key: value for key, value in record.items() if key != 'file_hashes'}))


def bidi_corpus(engine, path, characters):
    assert sha(path) == PINS[path.name]
    cases = rows = failures = 0
    examples, failed_lines = [], []
    levels, order = None, None
    for number, raw in enumerate(path.read_text('utf-8-sig').splitlines(), 1):
        line = raw.split('#', 1)[0].strip()
        if not line:
            continue
        if line.startswith('@Levels:'):
            levels = [None if value == 'x' else int(value) for value in line.split(':', 1)[1].split()]
            continue
        if line.startswith('@Reorder:'):
            order = [int(value) for value in line.split(':', 1)[1].split()]
            continue
        if line.startswith('@'):
            continue
        fields = [value.strip() for value in line.split(';')]
        rows += 1
        if characters:
            assert len(fields) == 5
            text = ''.join(chr(int(value, 16)) for value in fields[0].split())
            modes = [{'0': 'ltr', '1': 'rtl', '2': 'auto-ltr'}[fields[1]]]
            expected_base = int(fields[2])
            expected_levels = [None if value == 'x' else int(value) for value in fields[3].split()]
            expected_order = [int(value) for value in fields[4].split()]
        else:
            assert len(fields) == 2 and levels is not None and order is not None
            text = ''.join(REPRESENTATIVES[value] for value in fields[0].split())
            modes = [mode for bit, mode in ((1, 'auto-ltr'), (2, 'ltr'), (4, 'rtl')) if int(fields[1], 16) & bit]
            expected_base, expected_levels, expected_order = None, levels, order
        for mode in modes:
            cases += 1
            try:
                actual = engine.bidi(text, base=mode)
                good = (expected_base is None or actual['base'] == expected_base) and actual['order'] == expected_order
                good = good and len(actual['levels']) == len(expected_levels) and all(
                    value is None or value == actual['levels'][index] for index, value in enumerate(expected_levels))
            except Exception as exc:
                actual, good = dict(error=type(exc).__name__, message=str(exc)), False
            if not good:
                failures += 1
                if len(failed_lines) < 256:
                    failed_lines.append(dict(line=number, mode=mode))
                if len(examples) < 32:
                    examples.append(dict(line=number, mode=mode, codepoints=[f'{ord(char):04X}' for char in text],
                        expected_levels=expected_levels, expected_order=expected_order, expected_base=expected_base, actual=actual))
    assert cases > 0 and rows > 0
    return dict(name=path.name, rows=rows, executed_direction_cases=cases, passed=cases-failures, failed=failures,
                excluded=0, skipped=0, input_sha256=sha(path), failed_lines_first256=failed_lines, examples_first32=examples,
                scope='single-paragraph/single-line UAX9 through L2; rendering L3/L4 tested separately')


def tests(run, freeze_run, build_run):
    frozen_path = BASE / ('freeze-' + freeze_run) / 'verification.json'
    frozen = json.loads(frozen_path.read_bytes())
    guard(frozen)
    build = json.loads((BASE / ('build-' + build_run) / 'verification.json').read_bytes())
    assert build['status'] == 'built-not-yet-functionally-validated' and build['freeze_sha256'] == sha(frozen_path)
    target = BASE / ('tests-' + run)
    target.mkdir(parents=True, exist_ok=False)
    stage = ROOT / ('local/agent-ffmpeg/shaping69-native-20261107-' + build_run)
    runtime = stage / 'runtime'
    assert sha(stage / 'aek-shaping69-windows-x64.zip') == build['archive_sha256']
    payload = json.loads((runtime / 'payload.json').read_bytes())
    assert all(sha(runtime / name) == pin for name, pin in payload['files'].items())
    sys.path[:0] = [str(DEV / 'src'), str(ROOT / 'development/text68/src'), str(DEV / 'tests')]
    from aek_shaping import Engine
    engine = Engine(runtime / 'native.json')
    os.environ['SHAPING69_RUNTIME'] = str(runtime)
    os.environ['SHAPING69_TESTROOT'] = str(stage / ('contract-fixtures-' + run))
    suite = unittest.TestLoader().discover(str(DEV / 'tests'), pattern='test_*.py')
    with (target / 'tests.stderr').open('x', encoding='utf-8') as logs:
        result = unittest.TextTestRunner(stream=logs, verbosity=2).run(suite)
    print(json.dumps(dict(phase='actual-native-contracts-finished', tests=result.testsRun,
                         failures=len(result.failures), errors=len(result.errors), skipped=len(result.skipped))), flush=True)
    upstream = ROOT / ('local/agent-ffmpeg/shaping69-20261106-' + frozen['source_run']) / 'upstream'
    reports = []
    for name, characters in [('BidiCharacterTest.txt', True), ('BidiTest.txt', False)]:
        report = bidi_corpus(engine, upstream / name, characters)
        save(target / (name + '.json'), report)
        reports.append(report)
        print(json.dumps({key: value for key, value in report.items() if not key.startswith(('examples', 'failed_lines'))}), flush=True)
    guard(frozen)
    assert all(sha(runtime / name) == pin for name, pin in payload['files'].items()), 'Built runtime changed during tests'
    passed = result.wasSuccessful() and not result.skipped and all(row['failed'] == 0 for row in reports)
    record = dict(status='passed' if passed else 'failed', observed_at_utc=datetime.now(timezone.utc).isoformat(),
        freeze_sha256=sha(frozen_path), build_archive_sha256=build['archive_sha256'],
        actual_engine_versions=engine.versions, code_completed_before_build_and_tests=True,
        actual_font_contracts=dict(tests=result.testsRun, failures=len(result.failures), errors=len(result.errors), skipped=len(result.skipped)),
        official_UAX9_corpora=[{key: value for key, value in row.items() if not key.startswith(('examples', 'failed_lines'))} for row in reports],
        conformance_cases_filtered=False, test_groups_combined=False, frozen_inputs_unchanged=True,
        portrait_guard=portrait_guard(), product_integrated=False, formal_skill_modified=False,
        gpu_used=False, neural_model_forwards=0, full_goal_closed=False)
    save(target / 'verification.json', record)
    print(json.dumps(record, ensure_ascii=False))
    return 0 if passed else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['freeze', 'tests'])
    parser.add_argument('--run', required=True)
    parser.add_argument('--freeze-run', default='r1')
    parser.add_argument('--source-run', default='r3')
    parser.add_argument('--build-run', default='r1')
    args = parser.parse_args()
    assert all(value.isalnum() and len(value) <= 32 for name, value in vars(args).items() if name != 'action')
    assert sys.dont_write_bytecode and sys.prefix == sys.base_prefix
    if args.action == 'freeze':
        freeze(args.run, args.source_run)
        return 0
    return tests(args.run, args.freeze_run, args.build_run)


if __name__ == '__main__':
    raise SystemExit(main())
