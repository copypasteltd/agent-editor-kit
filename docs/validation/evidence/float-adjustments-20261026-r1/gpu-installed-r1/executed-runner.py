"""Capture source or installed adjustment and related regression evidence."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/validation/evidence/float-adjustments-20261026-r1'
GROUPS={
    'adjustments':['test_float_adjustments'],
    'float':['test_float_timeline','test_float_composite','test_float_geometry','test_float_crop','test_float_mask'],
    'effects':['test_float_exposure','test_float_lut','test_float_curves','test_float_levels','test_float_balance','test_float_tone'],
    'render':['test_float_standard_render','test_float_stream','test_float_preview'],
    'gpu':['native_float_gpu'],
    'audio':['test_float_audio_graph','test_source_transitions','test_nested_transitions'],
    'legacy':['test_cli','test_timeline_preview','test_queue_reuse','test_schema_contract'],
    'text':['test_float_text','test_text_paint','test_word_highlight','test_text_animation_composition','test_subtitle_clock'],
}


def pins(package):
    return {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in package.glob('*.py')}


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--run',required=True)
    ap.add_argument('--installed',type=Path);ap.add_argument('--group',choices=GROUPS,default='adjustments')
    a=ap.parse_args();assert a.run.replace('-','').isalnum()
    out=BASE/a.run;out.mkdir(parents=True,exist_ok=False)
    (out/'executed-runner.py').write_bytes(Path(__file__).read_bytes())
    work=ROOT/'workspace'/('float-adjustments-20261026-tests-'+a.run);work.mkdir(parents=True,exist_ok=False)
    os.environ.update(TEMP=str(work),TMP=str(work),TMPDIR=str(work));tempfile.tempdir=str(work)
    source=ROOT/'product/src/ai_ad_editor'
    package=a.installed.resolve()/'site/ai_ad_editor' if a.installed else source
    frozen=pins(source);assert frozen==pins(package)
    sys.path[:0]=[str(package.parent),str(ROOT/'product/tests')]
    rubberband=ROOT/'product/.runtime/rubberband-offline-probe-20261017/native/rubberband-4.0.0-gpl-executable-windows/rubberband.exe'
    assert rubberband.is_file();os.environ['AI_AD_EDITOR_TEST_RUBBERBAND']=str(rubberband)
    suite=unittest.defaultTestLoader.loadTestsFromNames(GROUPS[a.group])
    with (out/'tests.log').open('w',encoding='utf8',newline='\n') as log:
        result=unittest.TextTestRunner(stream=log,verbosity=2).run(suite)
    for name,attributes in [('test_float_standard_render',('NATIVE_CALLS','RENDER_RECEIPTS','ERROR_RECEIPTS')),
                            ('native_float_gpu',('RECEIPTS',)),('test_float_adjustments',('NATIVE_CALLS','RENDER_RECEIPTS'))]:
        module=sys.modules.get(name)
        if module:
            for attribute in attributes:
                if hasattr(module,attribute):
                    (out/(name+'-'+attribute.lower()+'.json')).write_text(json.dumps(getattr(module,attribute),ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    unchanged=frozen==pins(source)==pins(package)
    report=dict(status='passed' if result.wasSuccessful() and not result.skipped and unchanged else 'failed',
        tests=result.testsRun,failures=len(result.failures),errors=len(result.errors),skipped=len(result.skipped),
        group=a.group,modules=GROUPS[a.group],at_utc=datetime.now(timezone.utc).isoformat(),
        product_files=frozen,frozen_equal=unchanged,installed=str(a.installed) if a.installed else None)
    (out/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    print(json.dumps({k:v for k,v in report.items() if k!='product_files'}),flush=True)
    if report['status']!='passed':
        print((out/'tests.log').read_text('utf8')[-14000:]);raise SystemExit(1)


if __name__=='__main__':main()
