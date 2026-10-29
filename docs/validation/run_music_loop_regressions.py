"""Freeze and execute actual CLI60 loop and existing score regression groups."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[2]

def main():
    p=argparse.ArgumentParser();p.add_argument('--run',required=True);args=p.parse_args()
    assert args.run.replace('-','').isalnum() and sys.dont_write_bytecode
    source=ROOT/'product/src/ai_ad_editor';tests=ROOT/'product/tests'
    sys.path[:0]=[str(source.parent),str(tests)]
    import ai_ad_editor
    from ai_ad_editor.runtime import configure_local_runtime
    assert ai_ad_editor.VERSION=='0.1.60' and Path(ai_ad_editor.__file__).resolve()==source/'__init__.py'
    configure_local_runtime()
    sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    files=[*source.glob('*.py'),*tests.glob('*.py'),ROOT/'product/pyproject.toml']
    pins={p.relative_to(ROOT).as_posix():sha(p) for p in files}
    out=ROOT/'docs/validation/evidence/music-loop-20261029-r1'/('targeted-'+args.run)
    out.mkdir(parents=True,exist_ok=False);(out/'executed-runner.py').write_bytes(Path(__file__).read_bytes())
    suite=unittest.defaultTestLoader.loadTestsFromNames(['test_music_loop','test_music_score'])
    assert suite.countTestCases()==37
    with (out/'tests.stderr').open('w',encoding='utf-8',newline='\n') as stream:
        result=unittest.TextTestRunner(stream=stream,verbosity=2).run(suite)
    frozen=pins=={name:sha(ROOT/name) for name in pins}
    report=dict(status='passed' if result.wasSuccessful() and frozen and not result.skipped else 'failed',
        cli_version=ai_ad_editor.VERSION,tests=result.testsRun,failures=len(result.failures),
        errors=len(result.errors),skipped=len(result.skipped),frozen_equal=frozen,
        groups={'loop':18,'score':19},file_hashes=pins,source_only=True,installed60_accepted=False)
    (out/'verification.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps({k:v for k,v in report.items() if k!='file_hashes'}),flush=True)
    return 0 if report['status']=='passed' else 1

if __name__=='__main__':raise SystemExit(main())
