"""Retain unsuccessful development attempts without counting them as acceptance."""
from pathlib import Path
import hashlib
import json

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/validation/evidence/tracking-bake-20261026-r1'

def main():
    out=BASE/'development-attempts-r1';out.mkdir(exist_ok=False)
    (out/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    rows=[]
    for relative,reason in [('source-r1/verification.json','Invalid initial window/transition fixtures, corrected before installed tests'),
        ('source-r5/verification.json','Real MLT profile display FPS was not preserved; implementation and regression tests corrected'),
        ('activation-final-r1/activation.stderr.txt','Attempted activation before updating the reviewed Skill bundle pin; preserved and corrected'),
        ('case-r1/verification.json','Incorrect expectation of encoded-quality GPU status during frame-only bake; actual operations and cleanup retained'),
        ('case-r2/verification.json','Real .mlt extension import rejection; importer, fractional profile and OTIO clock roundtrips corrected')]:
        path=BASE/relative;data=path.read_bytes()
        if path.suffix=='.json': assert json.loads(data)['status']=='failed'
        rows.append(dict(path=path.relative_to(ROOT).as_posix(),sha256=hashlib.sha256(data).hexdigest(),
            reason=reason,excluded_from_final_acceptance=True))
    report=dict(status='recorded',failed_attempts=rows,final_installation='installation-final-r2',
        final_installed_tests=['tracking-installed-r2','conversion-installed-r2','legacy-installed-r2'],final_case='case-r3',
        final_pixel_comparison_tolerance=0,external_renderer_verified=False)
    (out/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    print(json.dumps(dict(status='recorded',attempts=len(rows))))

if __name__=='__main__': main()
