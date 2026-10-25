"""Freeze product bytes and execute portable/native OpenCL projection tests."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/validation/evidence/opencl-projection-20261026-r1/tests'
SCOPES={'native':['native_opencl_projection.NativeOpenCLProjectionTests'],
        'policy':['test_projection_opencl'],
        'projection':['test_projection_scanline_cache','test_affine_scanline_cache'],
        'sequence':['test_sequence_sampling','test_sequence_canvas','test_sequence_compositing'],
        'clock':['test_nested_time_mapping','test_nested_native_clock'],
        'hardware':['test_hardware_acceleration'],
        'alpha':['test_alpha_resampling'], 'cli':['test_cli']}

def sha(path):
    with path.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',required=True);parser.add_argument('--scope',choices=SCOPES,required=True)
    parser.add_argument('--installed',type=Path);parser.add_argument('--method')
    args=parser.parse_args();assert args.run.replace('-','').isalnum()
    out=BASE/args.run;out.mkdir(parents=True,exist_ok=False)
    (out/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    source=ROOT/'product/src/ai_ad_editor'
    package=args.installed.resolve()/'site/ai_ad_editor' if args.installed else source
    frozen={p.name:sha(p) for p in source.glob('*.py')}
    assert frozen=={p.name:sha(p) for p in package.glob('*.py')}
    (out/'product-files.json').write_text(json.dumps(frozen,indent=2)+'\n',encoding='utf8',newline='\n')
    names=SCOPES[args.scope]
    if args.method:
        assert args.scope=='native' and args.method.startswith('test_') and args.method.replace('_','').isalnum()
        names=[names[0]+'.'+args.method]
    runner=out/'run.py'
    runner.write_text('import json,sys,unittest\n'+'sys.path[:0]='+repr([str(package.parent),str(ROOT/'product/tests')])+'\n'
        +'suite=unittest.defaultTestLoader.loadTestsFromNames('+repr(names)+')\n'
        +'assert suite.countTestCases()>0\nresult=unittest.TextTestRunner(verbosity=2).run(suite)\n'
        +'print("AEK_RESULT="+json.dumps(dict(methods=result.testsRun,skipped=len(result.skipped),failures=len(result.failures),errors=len(result.errors),success=result.wasSuccessful())))\n'
        +'raise SystemExit(0 if result.wasSuccessful() else 1)\n',encoding='utf8',newline='\n')
    env=dict(os.environ);temp=ROOT/'workspace'/('opencl-projection-20261026-tests-'+args.run)
    temp.mkdir(parents=True,exist_ok=False)
    env.update(TEMP=str(temp),TMP=str(temp),TMPDIR=str(temp),PYTHONDONTWRITEBYTECODE='1')
    started=datetime.now(timezone.utc).isoformat()
    with (out/'tests.log').open('xb') as log:
        result=subprocess.run([sys.executable,'-E','-B','-u','-X','utf8',str(runner)],cwd=ROOT,env=env,
            stdout=log,stderr=subprocess.STDOUT,timeout=3600,creationflags=subprocess.CREATE_NO_WINDOW)
    lines=[line.removeprefix('AEK_RESULT=') for line in (out/'tests.log').read_text('utf8').splitlines() if line.startswith('AEK_RESULT=')]
    report=dict(status='passed' if result.returncode==0 and lines else 'failed',scope=args.scope,method=args.method,
        installed=str(args.installed) if args.installed else None,started_at_utc=started,
        finished_at_utc=datetime.now(timezone.utc).isoformat(),exit_code=result.returncode,source_files=len(frozen),
        frozen_equal=frozen=={p.name:sha(p) for p in source.glob('*.py')},
        installed_frozen_equal=frozen=={p.name:sha(p) for p in package.glob('*.py')},
        log_sha256=sha(out/'tests.log'),result=json.loads(lines[-1]) if lines else None)
    (out/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    print(json.dumps(report,ensure_ascii=False),flush=True)
    raise SystemExit(0 if report['status']=='passed' and report['frozen_equal'] else 1)

if __name__=='__main__':main()
