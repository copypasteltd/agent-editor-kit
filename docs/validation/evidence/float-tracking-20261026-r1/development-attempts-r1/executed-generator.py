"""Retain failed development attempts separately from final frozen acceptance."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/validation/evidence/float-tracking-20261026-r1'

def main():
    out=BASE/'development-attempts-r1';out.mkdir(exist_ok=False)
    (out/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    reasons={
        'case-r1':'Product integration gap: overlay track absent from packaged schema and semantic validator; fixture also lacked interpolation and reused an asset ID as clip ID. Schema/validator gates and fixture were corrected.',
        'case-r2':'Fixture still omitted interpolation on leading-decimal scale values. Generator now declares interpolation for every authored key.',
        'case-r3':'Fixture PNG had no container origin; existing native source contract correctly required explicit demux_origin. Generator now declares zero for the self-authored still.',
        'case-r4':'Independent oracle incorrectly assumed exact 1/12-second CFR boundaries for Matroska millisecond PTS. Final oracle independently reads actual PTS and uses half-open rational selection. Pixel centroid uses red-excess weights rather than a thresholded support centroid.',
        'source-bindings-r1':'All71 tests had zero assertion failures/errors/skips, but product version/capability edits happened during the run. Frozen-byte gate failed. This run is excluded; final installed frozen groups are separate.'}
    rows=[]
    for name,reason in reasons.items():
        file=BASE/name/'verification.json';value=json.loads(file.read_bytes());assert value['status']=='failed'
        rows.append(dict(attempt=name,status=value['status'],reason=reason,source=file.relative_to(ROOT).as_posix(),
            sha256=hashlib.sha256(file.read_bytes()).hexdigest(),failure_excerpt=value.get('error'),
            tests=value.get('tests'),assertion_failures=value.get('failures'),errors=value.get('errors'),
            excluded_from_final_acceptance=True))
    final=json.loads((BASE/'case-r5/verification.json').read_bytes());assert final['status']=='passed'
    report=dict(status='passed',scope='Audit of retained failed attempts, not a claim these attempts passed.',
        checked_at_utc=datetime.now(timezone.utc).isoformat(),attempts=rows,final_case='case-r5',
        final_installation='installation-final-r2',failed_evidence_rewritten=False,goal_closed=False)
    (out/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    print(json.dumps(dict(status='retained',failed_attempts=len(rows),final_case='case-r5')))

if __name__=='__main__':main()
