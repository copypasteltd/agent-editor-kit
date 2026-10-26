"""Preserve failed attempts separately; they are not final installed passes."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/validation/evidence/tracking-visibility-20261026-r1'

def main():
    out=BASE/'development-attempts-r1';out.mkdir(exist_ok=False)
    (out/'executed-generator.py').write_bytes(Path(__file__).read_bytes());rows=[]
    for name in ('source-r1','source-r2','source-r4','case-r1'):
        path=BASE/name/'verification.json';v=json.loads(path.read_bytes());assert v['status']=='failed'
        rows.append(dict(path=path.relative_to(ROOT).as_posix(),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
            excluded_from_final_acceptance=True,status=v['status'],failures=v.get('failures'),errors=v.get('errors')))
    passed=json.loads((BASE/'tracking-installed-r1/verification.json').read_bytes())
    assert passed['status']=='passed' and passed['tests']==125 and passed['failures']==passed['errors']==passed['skipped']==0
    report=dict(status='passed',failed_attempts=rows,final_installed_tests=125,
        resolution='Actual projected-alpha oracle; Fraction progress accepted; slide expectations checked against public pixels; finite-difference perturbation adjusted to resolve Float32 subtraction; real probe and independent-edge retime admitted; C41 request uses schema-complete interpolation/slide alias/explicit overlap. No pixel-equality threshold relaxation or goal closure changes.')
    (out/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    print(json.dumps(dict(status='passed',preserved_failed_runs=len(rows))))

if __name__=='__main__':main()
