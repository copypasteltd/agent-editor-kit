"""Probe actual worker entry bootstraps; no neural inference or dependency installs.

Copies the actual worker into a collision fixture and exits at its first owned
contract import. The fixture has competing application packages and dependency
markers. This only tests import ownership/search order, not any model output.
"""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
WORKERS = ('enhancement_worker.py', 'interpolation_worker.py', 'lama_worker.py',
           'lipsync_worker.py', 'sam2_worker.py', 'vace_worker.py', 'rvm_worker.py',
           'face_worker.py', 'ocr_worker.py', 'yolo_worker.py', 'demucs_worker.py',
           'ctc_worker.py', 'vace_session_worker.py', 'stem_separation_worker.py',
           'whisper_worker.py')
FIRST_CONTRACT = dict(rvm_worker='local_matting', face_worker='local_face',
    ocr_worker='local_ocr', yolo_worker='local_vision', demucs_worker='local_separation',
    ctc_worker='whisper_worker', vace_session_worker='model_session',
    stem_separation_worker='demucs_worker', whisper_worker='local_asr')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n',
                    encoding='utf-8', newline='\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', required=True)
    parser.add_argument('--installed', type=Path, required=True)
    parser.add_argument('--candidate-fix', action='store_true',
                        help='Patch only copied fixture workers; leave source and installed code frozen')
    args = parser.parse_args()
    assert args.run.replace('-', '').isalnum()
    assert sys.flags.isolated and sys.flags.no_site and sys.dont_write_bytecode
    out = ROOT/'docs/validation/evidence/native-worker-bootstrap-20261029-r1'/args.run
    work = ROOT/'local/agent-ffmpeg'/('native-worker-bootstrap-'+args.run)
    out.mkdir(parents=True, exist_ok=False)
    work.mkdir(parents=True, exist_ok=False)
    shutil.copyfile(Path(__file__), out/'executed-runner.py')
    source = ROOT/'product/src/ai_ad_editor'
    installed = args.installed.resolve()/'site/ai_ad_editor'
    pins = {p.name: sha(p) for p in source.glob('*.py')}
    assert len(pins) == 281 and pins == {p.name: sha(p) for p in installed.glob('*.py')}
    rows = []
    expected = dict(application='owned application', dependency='registered model runtime')
    for scope, package in [('source', source), ('installed', installed)]:
        for name in WORKERS:
            home = work/scope/name.removesuffix('.py')
            app_site, native_site = home/'application site', home/'native model site'
            app = app_site/'ai_ad_editor'
            app.mkdir(parents=True)
            native_site.mkdir()
            (app/'__init__.py').write_text("ORIGIN='owned application'\n", encoding='utf-8')
            (app_site/'numpy.py').write_text("ORIGIN='bundled controller dependency'\n", encoding='utf-8')
            (native_site/'numpy.py').write_text("ORIGIN='registered model runtime'\n", encoding='utf-8')
            rival = native_site/'ai_ad_editor'
            rival.mkdir()
            (rival/'__init__.py').write_text("raise RuntimeError('foreign application imported')\n", encoding='utf-8')
            # Exiting at the first actual application contract import isolates
            # the bootstrap and prevents all model/file/network operations.
            contract = FIRST_CONTRACT.get(name.removesuffix('.py'), 'rvm_worker')
            (app/(contract+'.py')).write_text(
                "import ai_ad_editor,json,numpy\n"
                "print(json.dumps(dict(application=ai_ad_editor.ORIGIN,dependency=numpy.ORIGIN)))\n"
                "raise SystemExit(0)\n", encoding='utf-8')
            worker = app/name
            shutil.copyfile(package/name, worker)
            if args.candidate_fix:
                lines = [
                    'application_root = str(Path(__file__).resolve().parents[1])',
                    'sys.path.insert(0, application_root)',
                    'try:',
                    '    import ai_ad_editor',
                    'finally:',
                    '    sys.path.remove(application_root)',
                    "if Path(ai_ad_editor.__file__).resolve() != Path(__file__).resolve().with_name('__init__.py'):",
                    "    raise RuntimeError('NATIVE_WORKER_APPLICATION_CHANGED')",
                ]
                def replacement(match):
                    return '\n'.join(match[1]+line for line in lines)
                patched, count = re.subn(
                    r'(?m)^([ \t]*)sys\.path\.insert\(0,\s*str\(Path\(__file__\)\.resolve\(\)\.parents\[1\]\)\)[ \t]*$',
                    replacement, worker.read_text('utf-8'))
                assert count == 1, name
                worker.write_text(patched, encoding='utf-8', newline='\n')
            request = home/'request.json'
            protocol = re.search(r'''(?m)^PROTOCOL\s*=\s*['"]([^'"]+)['"]''',
                                 (package/name).read_text('utf-8'))
            payload = dict(network='disabled', runtime_root=str(home/'runtime'),
                           response=str(home/'response.json'), native=dict(runtime_root=str(home/'runtime')),
                           protocol=protocol[1] if protocol else 'agent-hdemucs-four-stems-v1')
            save(request, payload)
            code = ('import runpy,sys;sys.path.insert(0,'+repr(str(native_site))+');'
                    'sys.argv=['+repr(str(worker))+','+repr(str(request))+'];'
                    'runpy.run_path('+repr(str(worker))+",run_name='__main__')")
            argv = [sys.executable, '-I', '-S', '-B', '-u', '-X', 'utf8', '-c', code]
            stdin = (json.dumps(payload).encode() if name == 'yolo_worker.py' else
                     b'run\n' if name in ('face_worker.py', 'ocr_worker.py') else b'')
            result = subprocess.run(argv, cwd=ROOT, input=stdin, capture_output=True, timeout=30,
                                    creationflags=subprocess.CREATE_NO_WINDOW)
            stem = scope+'-'+name.removesuffix('.py')
            (out/(stem+'.stdout')).write_bytes(result.stdout)
            (out/(stem+'.stderr')).write_bytes(result.stderr)
            try:
                observed = json.loads(result.stdout)
            except (ValueError, UnicodeError):
                observed = None
            row = dict(scope=scope, worker=name, worker_sha256=sha(package/name),
                       executed_fixture_sha256=sha(worker), proposed_fix_only=args.candidate_fix,
                       exit_code=result.returncode, expected=expected, observed=observed,
                       bootstrap_passed=result.returncode == 0 and observed == expected,
                       actual_worker_entry_executed=True, model_forwards=0)
            rows.append(row)
            save(out/'observations.json', rows)
            print(json.dumps(row), flush=True)
    assert pins == {p.name: sha(p) for p in source.glob('*.py')} == {
        p.name: sha(p) for p in installed.glob('*.py')}
    report = dict(status='passed' if all(r['bootstrap_passed'] for r in rows) else 'reproduced-failures',
                  observations=rows, cases=len(rows), passed=sum(r['bootstrap_passed'] for r in rows),
                  failed=sum(not r['bootstrap_passed'] for r in rows), code_files=281,
                  frozen_equal=True, neural_inference_test=False, model_forwards=0,
                  proposed_fix_only=args.candidate_fix, shipped_source_unchanged=True,
                  downloads=False, virtual_environment=False)
    save(out/'verification.json', report)
    print(json.dumps({k:v for k,v in report.items() if k != 'observations'}), flush=True)


if __name__ == '__main__':
    main()
