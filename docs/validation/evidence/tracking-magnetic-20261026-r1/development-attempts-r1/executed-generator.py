"""Retain the rejected globally conflicting fixture ID without counting it as acceptance."""
from datetime import datetime,timezone
import hashlib,json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/validation/evidence/tracking-magnetic-20261026-r1'

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    out=BASE/'development-attempts-r1';out.mkdir(exist_ok=False)
    (out/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    failed=BASE/'source-r2/verification.json';v=json.loads(failed.read_bytes())
    assert v['status']=='failed' and v['tests']==61 and v['errors']==1 and v['failures']==0
    assert '生成的 ID 无效或在项目中已经存在' in (failed.parent/'tests.log').read_text('utf8')
    final=json.loads((BASE/'tracking-installed-r1/verification.json').read_bytes())
    assert final['status']=='passed' and final['tests']==61 and final['frozen_equal'] and final['skipped']==0
    report=dict(status='passed',checked_at_utc=datetime.now(timezone.utc).isoformat(),failed_attempts=[
        dict(path=failed.relative_to(ROOT).as_posix(),sha256=sha(failed),excluded_from_final_acceptance=True,
             reason='New direct-main fixture requested clip ID a, already reserved by asset a. Correctly rejected; fixture uses shot_a/shot_b/shot_c.',
             files=[dict(path=p.relative_to(ROOT).as_posix(),sha256=sha(p),bytes=p.stat().st_size) for p in sorted(failed.parent.iterdir()) if p.is_file()])],
        pixel_threshold_relaxed=False,product_guard_removed=False,virtualization=False,new_model_forwards=0)
    (out/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    print(json.dumps(dict(status='passed',retained_failed_attempts=1)))

if __name__=='__main__':main()
