"""Retain unsuccessful development attempts without counting them as acceptance."""
from pathlib import Path
import hashlib
import json
import argparse

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/validation/evidence/tracking-bake-20261026-r1'

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--run',required=True);args=parser.parse_args()
    assert args.run.replace('-','').isalnum()
    out=BASE/('development-attempts-'+args.run);out.mkdir(exist_ok=False)
    (out/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    rows=[]
    for relative,reason in [('source-r1/verification.json','Invalid initial window/transition fixtures, corrected before installed tests'),
        ('source-r5/verification.json','Real MLT profile display FPS was not preserved; implementation and regression tests corrected'),
        ('activation-final-r1/activation.stderr.txt','Attempted activation before updating the reviewed Skill bundle pin; preserved and corrected'),
        ('case-r1/verification.json','Incorrect expectation of encoded-quality GPU status during frame-only bake; actual operations and cleanup retained'),
        ('case-r2/verification.json','Real .mlt extension import rejection; importer, fractional profile and OTIO clock roundtrips corrected'),
        ('case-r3/verification.json','Real overlapping draft segments failed import after unsupported transition removal; explicit approximate overlap mapping added'),
        ('legacy-installed-r2/verification.json','New regression compared newly assigned asset IDs across imports; now checks edit fields and actual asset hashes'),
        ('case-r4/verification.json','The final source-byte assertion spanned a normal render that appends output/audit records; final case checks exact bytes around every export and separately verifies only the documented render bookkeeping changes'),
        ('media-inspection-r1/recovery-observation.json','Initial GIF inspector assumed exactly 3000 ms; actual 24-frame GIF is 3010 ms with 10 ms delay units. Source MP4 remains 3 seconds; final inspection records every actual delay')]:
        path=BASE/relative;data=path.read_bytes()
        if path.suffix=='.json': assert json.loads(data)['status']=='failed'
        rows.append(dict(path=path.relative_to(ROOT).as_posix(),sha256=hashlib.sha256(data).hexdigest(),
            reason=reason,excluded_from_final_acceptance=True))
    report=dict(status='recorded',failed_attempts=rows,final_installation='installation-final-r3',
        final_installed_tests=['tracking-installed-r3','conversion-installed-r3','legacy-installed-r3'],final_case='case-r5',
        final_pixel_comparison_tolerance=0,external_renderer_verified=False)
    (out/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    print(json.dumps(dict(status='recorded',attempts=len(rows))))

if __name__=='__main__': main()
