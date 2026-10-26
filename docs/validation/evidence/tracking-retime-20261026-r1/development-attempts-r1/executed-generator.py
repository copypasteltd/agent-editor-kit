"""Keep rejected development receipts separate from frozen installed acceptance."""
from pathlib import Path
import hashlib,json

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/validation/evidence/tracking-retime-20261026-r1'

def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    out=BASE/'development-attempts-r1';out.mkdir(exist_ok=False)
    (out/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    failed=BASE/'source-r1/verification.json';v=json.loads(failed.read_bytes())
    assert v['status']=='failed' and v['failures']==8 and v['errors']==1 and v['tests']==77
    final=json.loads((BASE/'tracking-installed-r1/verification.json').read_bytes())
    assert final['status']=='passed' and final['tests']==79 and final['skipped']==0
    report=dict(status='passed',failed_attempts=[dict(path=failed.relative_to(ROOT).as_posix(),sha256=sha(failed),
        excluded_from_final_acceptance=True,reason='Repeated per-member containers added a Float32 alpha boundary; two partial-main fixtures omitted explicit sync_content:retime.',
        resolution='Retain selected layer/opacity through a shared graph on repeated retime. Fixtures explicitly request synchronized retime; the default ripple contract is unchanged.')],
        intermediate_passes_excluded=['source-r2'],final_acceptance='tracking-installed-r1',
        pixel_threshold_relaxed=False,product_guards_removed=False,source_fallback=False)
    (out/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    print(json.dumps(dict(status='passed',retained_failed_attempts=1,pixel_threshold_relaxed=False)))

if __name__=='__main__':main()
