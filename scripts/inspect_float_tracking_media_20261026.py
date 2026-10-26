"""Extract actual GIF checkpoint images; retain the missing late-seek observation."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json
from PIL import Image,ImageDraw

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/validation/evidence/float-tracking-20261026-r1'

def main():
    out=BASE/'media-inspection-r1';out.mkdir(exist_ok=False)
    (out/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    public=ROOT/'docs/assets/float-tracking-20261026-r5'
    panels=[]
    with Image.open(public/'original.png') as image:panels.append(('Original first frame',image.convert('RGB')))
    with Image.open(public/'native-tracking.gif') as image:
        assert image.n_frames==24
        for index in (0,12,23):
            image.seek(index);panels.append(('Actual GIF frame '+str(index),image.convert('RGB')))
    sheet=Image.new('RGB',(640,408),(18,24,32));draw=ImageDraw.Draw(sheet)
    for i,(title,image) in enumerate(panels):
        x,y=(i%2)*320,(i//2)*204;draw.text((x+8,y+5),title,fill=(240,240,240));sheet.paste(image,(x,y+24))
    path=out/'contact-sheet.png';sheet.save(path)
    missing=not (public/'midpoint.png').exists()
    report=dict(status='extracted',checked_at_utc=datetime.now(timezone.utc).isoformat(),
        actual_GIF_frames=[0,12,23],source_frame=0,continuous_playback=False,human_listening=False,
        source=str(public/'native-tracking.gif'),source_sha256=hashlib.sha256((public/'native-tracking.gif').read_bytes()).hexdigest(),
        contact_sheet=path.relative_to(ROOT).as_posix(),sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        late_seek_empty_output_observed=missing,
        late_seek_note='Original case-r5 display-still exit0 had no frame after a 2.95s seek on the3s file. It is not counted as a successful still. The reproduction now seeks1.5s and checks file existence plus image decoding. Original evidence is retained.',
        goal_closed=False)
    (out/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    print(json.dumps(report))

if __name__=='__main__':main()
