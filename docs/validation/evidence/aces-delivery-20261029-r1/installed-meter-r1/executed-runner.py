"""Isolated installed-CLI53 acceptance; no source fallback or global site packages."""
import argparse,datetime,hashlib,json,os,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'docs/validation/evidence/aces-delivery-20261029-r1'

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def pins(package):
    files=[*package.glob('*.py'),package/'agent-project.schema.json',package/'native_ocio_manifest.json',package/'native_icc_manifest.json',package/'LITTLECMS_LICENSE.txt']
    files.extend(package/r['path'] for r in json.loads((package/'native_ocio_manifest.json').read_bytes())['files'])
    files.append(package/json.loads((package/'native_icc_manifest.json').read_bytes())['binary_filename'])
    return {p.relative_to(package).as_posix():sha(p) for p in files}

def main():
    p=argparse.ArgumentParser();p.add_argument('--installed',type=Path,required=True);p.add_argument('--group',choices=['special','meter','compat'],required=True);p.add_argument('--run',required=True);a=p.parse_args()
    assert a.run.replace('-','').isalnum() and sys.flags.isolated and sys.flags.no_site
    out=BASE/a.run;out.mkdir(parents=True,exist_ok=False)
    (out/'executed-runner.py').write_bytes(Path(__file__).read_bytes())
    work=ROOT/'local/agent-ffmpeg'/('aces-tests-'+a.run);work.mkdir(exist_ok=False)
    os.environ.update(TEMP=str(work),TMP=str(work),TMPDIR=str(work));tempfile.tempdir=str(work)
    source=ROOT/'product/src/ai_ad_editor';package=a.installed.resolve()/'site/ai_ad_editor'
    before=pins(source);assert pins(package)==before
    sys.path[:0]=[str(package.parent),str(ROOT/'product/tests')]
    import ai_ad_editor,numpy
    assert Path(ai_ad_editor.__file__).resolve().parent==package
    assert Path(numpy.__file__).resolve().is_relative_to(package.parent)
    if a.group=='special':names=['test_ocio_runtime.OCIORuntimeTests','test_aces_pipeline.ACESPipelineTests']
    elif a.group=='meter':names=['test_hdr_measure','test_hdr_media_measure','test_schema_contract']
    else:names=list(json.loads((ROOT/'docs/validation/evidence/gpu-gamut-20261029-r1/compat-r1/verification.json').read_bytes())['test_files'])
    test_before={p.name:sha(p) for p in (ROOT/'product/tests').glob('*.py')}
    with (out/'tests.txt').open('w',encoding='utf-8') as stream:
        r=unittest.TextTestRunner(stream=stream,verbosity=2).run(unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromName(n) for n in names))
    stable=before==pins(source)==pins(package) and test_before=={p.name:sha(p) for p in (ROOT/'product/tests').glob('*.py')}
    receipts={n:m.RECEIPTS for n,m in list(sys.modules.items()) if n.startswith('test_') and hasattr(m,'RECEIPTS')}
    (out/'receipts.json').write_text(json.dumps(receipts,ensure_ascii=False,indent=2),encoding='utf-8')
    d=dict(status='passed' if r.wasSuccessful() and not r.skipped and stable else 'failed',tests=r.testsRun,failures=len(r.failures),errors=len(r.errors),skipped=len(r.skipped),
        installed=str(a.installed.resolve()),package=str(package),source_fallback=False,isolated=True,no_site=True,
        frozen_equal=stable,files=before,test_files=test_before,tests_selected=names,at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat())
    (out/'verification.json').write_text(json.dumps(d,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in d.items() if k not in ['files','test_files']}),flush=True)
    assert d['status']=='passed'

if __name__=='__main__':main()
