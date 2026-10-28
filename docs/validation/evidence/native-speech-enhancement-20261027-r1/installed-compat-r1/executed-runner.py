"""Capture frozen source/installed enhancement and relevant compatibility suites."""
from pathlib import Path
from datetime import datetime,timezone
import argparse,hashlib,json,os,sys,tempfile,unittest
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/validation/evidence/native-speech-enhancement-20261027-r1'
GROUPS={'enhancement':['test_speech_enhancement'],
    'compat':['test_stem_separation','test_local_separation','test_native_audio_clock','test_fragments','test_schema_contract','test_interpolation']}
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def pins(p):return {f.name:sha(f) for f in p.glob('*.py')}
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--run',required=True);ap.add_argument('--installed',type=Path);ap.add_argument('--group',choices=GROUPS,default='enhancement');a=ap.parse_args()
    assert a.run.replace('-','').isalnum();out=BASE/a.run;out.mkdir(parents=True,exist_ok=False)
    (out/'executed-runner.py').write_bytes(Path(__file__).read_bytes())
    work=ROOT/'local/agent-ffmpeg'/('native-enhancement-tests-'+a.run);work.mkdir(parents=True,exist_ok=False)
    os.environ.update(TEMP=str(work),TMP=str(work),TMPDIR=str(work),AI_AD_EDITOR_TEST_NATIVE_PYTHON='D:/dev/comfyui/ComfyUI_windows_portable_nvidia_0_30_0/ComfyUI_windows_portable/python_embeded/python.exe');tempfile.tempdir=str(work)
    source=ROOT/'product/src/ai_ad_editor';package=a.installed.resolve()/'site/ai_ad_editor' if a.installed else source
    before=pins(source);assert pins(package)==before
    sys.path[:0]=[str(package.parent),str(ROOT/'product/tests')]
    selected={n.split('.')[0] for n in GROUPS[a.group]};tests=[ROOT/'product/tests'/(n+'.py') for n in sorted(selected)]
    frozen={p.name:sha(p) for p in tests};(out/'executed-tests').mkdir()
    for p in tests:(out/'executed-tests'/p.name).write_bytes(p.read_bytes())
    with (out/'tests.log').open('w',encoding='utf8',newline='\n') as f:
        result=unittest.TextTestRunner(stream=f,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromNames(GROUPS[a.group]))
    record=dict(status='passed' if result.wasSuccessful() and not result.skipped and pins(source)==before and frozen=={p.name:sha(p) for p in tests} else 'failed',
        tests=result.testsRun,failures=len(result.failures),errors=len(result.errors),skipped=len(result.skipped),group=a.group,modules=GROUPS[a.group],
        product_files=before,test_files=frozen,frozen_equal=pins(source)==before,installed=str(a.installed) if a.installed else None,at_utc=datetime.now(timezone.utc).isoformat())
    (out/'verification.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf8')
    print(json.dumps({k:v for k,v in record.items() if k not in ('product_files','test_files')},ensure_ascii=False),flush=True)
    if record['status']!='passed':print((out/'tests.log').read_text('utf8')[-12000:]);raise SystemExit(1)
if __name__=='__main__':main()
