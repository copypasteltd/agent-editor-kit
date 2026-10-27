"""Record actual still-image review, separately from playback/listening/HDR acceptance."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/validation/evidence/native-hdr-20261027-r1'
public=ROOT/'docs/assets/native-hdr-20261027-r3'
report=dict(status='reviewed',at_utc=datetime.now(timezone.utc).isoformat(),
    method='view_image actual preview-frame.png',frame=24,
    files={name:hashlib.sha256((public/name).read_bytes()).hexdigest() for name in ('preview-frame.png','hdr-sdr-view.gif')},
    observations=['Eight labeled brightness patches are ordered and visually distinct in the SDR trim.',
        'Warm moving highlight is visible without obscuring the chart labels at the sampled frame.',
        'The separately declared 100-nit SDR badge is legible over the HDR composition.',
        'Image viewed is a declared SDR trim; no direct HDR-display judgment made.'],
    continuous_human_playback=False,human_listening=False,HDR_monitor_accepted=False,natural_quality_accepted=False)
path=BASE/'static-chart-review.json';assert not path.exists()
path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
print(json.dumps(report,ensure_ascii=False))
