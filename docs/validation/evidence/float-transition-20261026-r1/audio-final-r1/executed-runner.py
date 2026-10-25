"""Run native transition tests with captured, attempt-specific evidence."""
import argparse,hashlib,json,os,sys,unittest
from datetime import datetime,timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--run',required=True)
    parser.add_argument('--group',choices=('kernel','float','audio','audio-core','render','legacy'),default='kernel')
    args=parser.parse_args();assert args.run.replace('-','').isalnum()
    out=ROOT/'docs/validation/evidence/float-transition-20261026-r1'/args.run
    out.mkdir(parents=True,exist_ok=False)
    (out/'executed-runner.py').write_bytes(Path(__file__).read_bytes())
    sys.path[:0]=[str(ROOT/'product/src'),str(ROOT/'product/tests')]
    binary=ROOT/'product/.runtime/rubberband-offline-probe-20261017/native/rubberband-4.0.0-gpl-executable-windows/rubberband.exe'
    assert binary.is_file(),'Explicit existing native Rubber Band required; do not skip'
    os.environ['AI_AD_EDITOR_TEST_RUBBERBAND']=str(binary)
    frozen={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'product/src/ai_ad_editor').glob('*.py')}
    modules={'kernel':['test_float_transitions'],
        'float':['test_float_timeline','test_float_composite','test_float_geometry','test_float_crop','test_float_mask'],
        'audio':['test_float_audio_graph','test_source_transitions','test_nested_transitions'],
        'audio-core':['test_float_audio_graph'],
        'render':['test_float_standard_render','test_float_stream'],
        'legacy':['test_validator','test_render','test_preview','test_queue','test_schema']}
    suite=unittest.defaultTestLoader.loadTestsFromNames(modules[args.group])
    with (out/'tests.log').open('w',encoding='utf8',newline='\n') as log:
        result=unittest.TextTestRunner(stream=log,verbosity=2).run(suite)
    after={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'product/src/ai_ad_editor').glob('*.py')}
    report=dict(status='passed' if result.wasSuccessful() and not result.skipped and frozen==after else 'failed',
        tests=result.testsRun,failures=len(result.failures),errors=len(result.errors),skipped=len(result.skipped),
        group=args.group,modules=modules[args.group],at_utc=datetime.now(timezone.utc).isoformat(),
        product_files=frozen,frozen_equal=frozen==after)
    (out/'verification.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8',newline='\n')
    print(json.dumps({k:v for k,v in report.items() if k!='product_files'}),flush=True)
    if report['status']!='passed':
        print((out/'tests.log').read_text(encoding='utf8')[-16000:]);raise SystemExit(1)

if __name__=='__main__':main()
