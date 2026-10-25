"""Record static assistant inspection separately from playback or listening."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    out = ROOT/'docs/validation/evidence/ad-storyboard-20261025-r1/still-inspection-r1'
    out.mkdir(exist_ok=False)
    (out/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    folder = ROOT/'docs/assets/ad-storyboard-20261025-r1'
    records = []
    for name, observation in (
        ('variants.png', 'First contact sheet overlaps the square preview with the wide subtitle; preserved, replaced for display by variants-clear.png.'),
        ('variants-clear.png', 'Three decoded variant stills visible without overlap. Fit keeps the wide source inside vertical/square canvases with black padding. Captions visible within canvas.'),
        ('revision-before.png', 'Original last-shot card reads DELIVER THREE FORMATS; single Chinese CTA caption visible.'),
        ('revision-after.png', 'Replacement last-shot card reads START A LOCAL EDIT; reviewed Chinese CTA plus agent editor kit second line visible, within canvas.'),
    ):
        path = folder/name
        records.append(dict(path=path.relative_to(ROOT).as_posix(), sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
            observation=observation, method='Assistant viewed the actual local raster via view_image.'))
    report = dict(status='recorded', at_utc=datetime.now(timezone.utc).isoformat(), files=records,
        continuous_human_playback=False, human_listening=False, natural_ad_quality_acceptance=False,
        static_inspection_only=True)
    (out/'verification.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf8', newline='\n')
    print(json.dumps(dict(status='recorded', stills=len(records), static_inspection_only=True)))


if __name__ == '__main__':
    main()
