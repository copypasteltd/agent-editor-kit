"""Run the focused look, LUT and installer regression and retain exact counts."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import os
import sys
import time
import unittest

ROOT=Path(__file__).resolve().parents[1]
EVIDENCE=ROOT/'docs/validation/evidence/look500-20261024-r1'


def main():
    EVIDENCE.mkdir(parents=True,exist_ok=True)
    path=EVIDENCE/'regression-policy.json';log=EVIDENCE/'regression-policy.log'
    if path.exists() or log.exists():raise ValueError('Existing evidence is preserved')
    temporary=ROOT/'product/.runtime/look500-test-temp';temporary.mkdir(parents=True,exist_ok=True)
    os.environ.update(TEMP=str(temporary),TMP=str(temporary),TMPDIR=str(temporary))
    sys.path[:0]=[str(ROOT/'product/src'),str(ROOT/'product/tests')]
    from ai_ad_editor.runtime import configure_local_runtime
    configure_local_runtime()
    names=['test_look_presets','test_lut_automation','test_offline_install','test_offline_media_profile','test_release_parts',
           'test_cli.P0CliTests.test_local_policy_rejects_remote_ingest_metadata_and_audits_project']
    files={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
           for p in [*(ROOT/'product/src').rglob('*.py'),*(ROOT/'product/src/ai_ad_editor/look_data').rglob('*'),*(ROOT/'product/offline').glob('*.py')]
           if p.is_file()}
    started=time.monotonic()
    with log.open('w',encoding='utf-8') as stream:
        result=unittest.TextTestRunner(stream=stream,verbosity=2).run(unittest.defaultTestLoader.loadTestsFromNames(names))
    report={'status':'passed' if result.wasSuccessful() else 'failed','date_utc':datetime.now(timezone.utc).isoformat(),
        'modules':names,'tests_run':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),
        'skipped':len(result.skipped),'seconds':round(time.monotonic()-started,3),'native_windows':os.name=='nt',
        'scope':'Focused regression, not the historical 2930-test full suite','frozen_product_files':files}
    path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='frozen_product_files'}))
    return 0 if result.wasSuccessful() else 1


if __name__=='__main__':raise SystemExit(main())
