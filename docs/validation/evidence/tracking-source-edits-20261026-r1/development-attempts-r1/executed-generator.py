"""Pin rejected development attempts independently of final installed acceptance."""
from datetime import datetime,timezone
import hashlib,json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/validation/evidence/tracking-source-edits-20261026-r1'

def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def main():
    out=BASE/'development-attempts-r1';out.mkdir(exist_ok=False)
    (out/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    rows=[]
    for name,reason in [
        ('source-r1','Fixture requested a 2x head extension beyond its actual registered physical source handle; input corrected.'),
        ('source-r2','Two retained native frames selected incorrectly at binary floating-point boundaries of a flat curve; fixed using exact rational inversion, without epsilon.'),
        ('case-r1','Independent verifier used non-existent FloatRenderContext.host; corrected to its actual timeline interface.'),
        ('case-r2','Independent oracle incorrectly assumed nominal 12 fps gave uniform source PTS. Actual Matroska PTS uses 1/1000; replaced with independent ffprobe PTS lookup.')]:
        path=BASE/name/'verification.json';v=json.loads(path.read_bytes());assert v['status']=='failed'
        files=[dict(path=f.relative_to(ROOT).as_posix(),bytes=f.stat().st_size,sha256=sha(f))
            for f in sorted(path.parent.iterdir()) if f.is_file()]
        rows.append(dict(path=path.relative_to(ROOT).as_posix(),sha256=sha(path),reason=reason,
            tests=v.get('tests'),failures=v.get('failures'),errors=v.get('errors'),
            excluded_from_final_acceptance=True,files=files))
    final=json.loads((BASE/'tracking-installed-r1/verification.json').read_bytes())
    assert final['status']=='passed' and final['tests']==46 and final['skipped']==0 and final['frozen_equal']
    assert b'FAIL:' in (BASE/'source-r2/tests.log').read_bytes()
    report=dict(status='passed',checked_at_utc=datetime.now(timezone.utc).isoformat(),failed_attempts=rows,
        final_acceptance_only='Final installed-r1 groups and case-r3; rejected attempts are separately retained.',
        original_checks_retained=True,pixel_threshold_relaxed=False,global_epsilon_added=False,
        virtualization=False,new_model_forwards=0)
    (out/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    print(json.dumps(dict(status='passed',retained_failed_attempts=len(rows))))

if __name__=='__main__':main()
