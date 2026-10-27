"""Record the agent's actual static inspection; do not imply human playback."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib
import json

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/validation/evidence/highlight-glow-20261027-r1'

def main():
    case=json.loads((BASE/'case-r1/verification.json').read_bytes());assert case['status']=='passed'
    media=ROOT/case['public']
    records=[dict(path=p.relative_to(ROOT).as_posix(),sha256=hashlib.sha256(p.read_bytes()).hexdigest())
        for p in (media/'contact.png',media/'before.png')]
    result=dict(status='reviewed',at_utc=datetime.now(timezone.utc).isoformat(),
        method='agent_view_image_static_contact_and_separately_rendered_before',images=records,
        findings=['Before panels share the original sharp unlit chart.',
            'Bloom spreads actual bright text, bottle edges, ring and dots with white light.',
            'Halation retains bright cores with warm red light on neighboring pixels.',
            'Combined panel displays both operators; labels identify all four choices.',
            'Strong demo gain plus explicit clip delivery produces intentional highlight clipping; client gain/exposure still needs tuning.'],
        continuous_human_playback=False,human_listening=False,natural_quality_accepted=False,
        physical_film_accepted=False,HDR_accepted=False,new_renders=0,new_model_forwards=0)
    target=BASE/'static-chart-review.json';assert not target.exists()
    target.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    print(json.dumps(result,ensure_ascii=False))

if __name__=='__main__':main()
