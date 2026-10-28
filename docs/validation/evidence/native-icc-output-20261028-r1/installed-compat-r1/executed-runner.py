"""Immutable native source/installed HDR10 and compatibility test captures."""
from pathlib import Path
import argparse,hashlib,json,os,sys,tempfile,unittest
from datetime import datetime,timezone
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'docs/validation/evidence/native-icc-output-20261028-r1'
GROUPS={'output':['test_icc_output'], 'compat':['test_float_hlg_black','test_icc_profiles','test_float_chromatic','test_float_color_signal','test_float_hdr','test_hdr_metadata','test_float_glow','test_float_standard_render','test_float_preview','test_float_bundle','test_float_bundle_source','test_float_lut','test_float_curves','test_schema_contract','test_queue_reuse']}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--run',required=True);ap.add_argument('--installed',type=Path);ap.add_argument('--group',choices=GROUPS,default='output');a=ap.parse_args()
    assert a.run.replace('-','').isalnum();out=BASE/a.run;out.mkdir(parents=True,exist_ok=False)
    (out/'executed-runner.py').write_bytes(Path(__file__).read_bytes())
    work=ROOT/'local/agent-ffmpeg'/('native-icc-output-tests-'+a.run);work.mkdir(exist_ok=False)
    os.environ.update(TEMP=str(work),TMP=str(work),TMPDIR=str(work));tempfile.tempdir=str(work)
    source=ROOT/'product/src/ai_ad_editor';package=a.installed.resolve()/'site/ai_ad_editor' if a.installed else source
    before={p.name:sha(p) for p in source.glob('*.py')};assert {p.name:sha(p) for p in package.glob('*.py')}==before
    sys.path[:0]=[str(package.parent),str(ROOT/'product/tests')]
    tests={n:sha(ROOT/'product/tests'/(n+'.py')) for n in set(GROUPS[a.group]+['test_float_hdr','test_float_standard_render','test_float_color_signal'])}
    (out/'executed-tests').mkdir()
    for n in tests:(out/'executed-tests'/(n+'.py')).write_bytes((ROOT/'product/tests'/(n+'.py')).read_bytes())
    suite=unittest.defaultTestLoader.loadTestsFromNames(GROUPS[a.group])
    with (out/'tests.log').open('w',encoding='utf8',newline='\n') as f:result=unittest.TextTestRunner(stream=f,verbosity=2).run(suite)
    receipts={n:getattr(m,'RECEIPTS') for n,m in list(sys.modules.items()) if n.startswith('test_') and hasattr(m,'RECEIPTS')}
    (out/'receipts.json').write_text(json.dumps(receipts,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    stable=before=={p.name:sha(p) for p in source.glob('*.py')}
    r=dict(status='passed' if result.wasSuccessful() and not result.skipped and stable else 'failed',tests=result.testsRun,
        failures=len(result.failures),errors=len(result.errors),skipped=len(result.skipped),product_files=before,test_files=tests,
        frozen_equal=stable,installed=str(a.installed) if a.installed else None,group=a.group,at_utc=datetime.now(timezone.utc).isoformat())
    (out/'verification.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    print(json.dumps({k:v for k,v in r.items() if k not in ('product_files','test_files')}),flush=True)
    if r['status']!='passed':print((out/'tests.log').read_text('utf8')[-14000:]);raise SystemExit(1)
if __name__=='__main__':main()
