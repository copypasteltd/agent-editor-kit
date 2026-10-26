"""Run native Float32 text and regression tests with captured, attempt-specific evidence."""
import argparse,hashlib,json,os,sys,unittest
from datetime import datetime,timezone
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--run',required=True)
    parser.add_argument('--installed',type=Path)
    parser.add_argument('--group',choices=('gpu','text','float','audio','render','legacy','text-legacy'),default='gpu')
    args=parser.parse_args();assert args.run.replace('-','').isalnum()
    out=ROOT/'docs/validation/evidence/float-gpu-20261026-r1'/args.run
    out.mkdir(parents=True,exist_ok=False)
    (out/'executed-runner.py').write_bytes(Path(__file__).read_bytes())
    temporary=ROOT/'workspace'/('float-gpu-20261026-tests-'+args.run)
    temporary.mkdir(parents=True,exist_ok=False)
    os.environ.update(TEMP=str(temporary),TMP=str(temporary),TMPDIR=str(temporary))
    import tempfile
    tempfile.tempdir=str(temporary)
    package=args.installed.resolve()/'site/ai_ad_editor' if args.installed else ROOT/'product/src/ai_ad_editor'
    sys.path[:0]=[str(package.parent),str(ROOT/'product/tests')]
    binary=ROOT/'product/.runtime/rubberband-offline-probe-20261017/native/rubberband-4.0.0-gpl-executable-windows/rubberband.exe'
    assert binary.is_file(),'Explicit existing native Rubber Band required; do not skip'
    os.environ['AI_AD_EDITOR_TEST_RUBBERBAND']=str(binary)
    frozen={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'product/src/ai_ad_editor').glob('*.py')}
    assert frozen=={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in package.glob('*.py')}
    modules={'gpu':['native_float_gpu'],'text':['test_float_text'],
        'float':['test_float_timeline','test_float_composite','test_float_geometry','test_float_crop','test_float_mask'],
        'audio':['test_float_audio_graph','test_source_transitions','test_nested_transitions'],
        'text-legacy':['test_text_paint','test_word_highlight','test_text_animation_composition','test_subtitle_clock'],
        'render':['test_float_standard_render','test_float_stream','test_float_preview'],
        'legacy':['test_cli','test_timeline_preview','test_queue_reuse','test_schema_contract']}
    suite=unittest.defaultTestLoader.loadTestsFromNames(modules[args.group])
    with (out/'tests.log').open('w',encoding='utf8',newline='\n') as log:
        result=unittest.TextTestRunner(stream=log,verbosity=2).run(suite)
    for name,attribute in [('native_float_gpu','RECEIPTS'),('test_float_text','TEXT_RECEIPTS'),('test_float_text','NATIVE_CALLS')]:
        module=sys.modules.get(name)
        if module is not None:
            (out/(attribute.lower()+'.json')).write_text(json.dumps(getattr(module,attribute),ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    after={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'product/src/ai_ad_editor').glob('*.py')}
    report=dict(status='passed' if result.wasSuccessful() and not result.skipped and frozen==after else 'failed',
        tests=result.testsRun,failures=len(result.failures),errors=len(result.errors),skipped=len(result.skipped),
        group=args.group,modules=modules[args.group],at_utc=datetime.now(timezone.utc).isoformat(),
        product_files=frozen,frozen_equal=frozen==after,installed=str(args.installed) if args.installed else None)
    (out/'verification.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8',newline='\n')
    print(json.dumps({k:v for k,v in report.items() if k!='product_files'}),flush=True)
    if report['status']!='passed':
        print((out/'tests.log').read_text(encoding='utf8')[-16000:]);raise SystemExit(1)

if __name__=='__main__':main()
