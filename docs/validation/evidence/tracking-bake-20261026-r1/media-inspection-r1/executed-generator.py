"""Inspect all 24 actual paired GIF frames and prepare static review evidence."""
from pathlib import Path
import hashlib
import json
from PIL import Image, ImageChops, ImageDraw

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/validation/evidence/tracking-bake-20261026-r1'

def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()

def main():
    out=BASE/'media-inspection-r1';out.mkdir(exist_ok=False)
    (out/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    public=ROOT/'docs/assets/tracking-bake-20261026-r5'
    selected=[];durations=[]
    with Image.open(public/'comparison.gif') as image:
        assert image.n_frames==24 and image.size==(640,180)
        for index in range(image.n_frames):
            image.seek(index);frame=image.convert('RGB');durations.append(image.info['duration'])
            assert ImageChops.difference(frame.crop((0,0,320,180)),frame.crop((320,0,640,180))).getbbox() is None
            if index in (0,6,12,15,18,23): selected.append((index,frame.copy()))
    sheet=Image.new('RGB',(640,204*len(selected)),(245,245,245));draw=ImageDraw.Draw(sheet)
    for row,(index,frame) in enumerate(selected):
        draw.text((8,row*204+4),f'GIF frame {index:02d}: native binding (left) / baked hold keys (right)',fill=(12,12,12))
        sheet.paste(frame,(0,row*204+24))
    sheet.save(out/'contact-sheet.png')
    assert sum(durations)==3000
    report=dict(status='awaiting_static_review',gif_frames=24,gif_size=[640,180],duration_ms=sum(durations),
        all_left_right_GIF_frames_equal=True,selected_frames=[r[0] for r in selected],
        contact_sheet_sha256=sha(out/'contact-sheet.png'),gif_sha256=sha(public/'comparison.gif'),
        static_image_review=False,continuous_playback=False,human_listening=False,natural_quality_accepted=False)
    (out/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    print(json.dumps(report,ensure_ascii=False))

if __name__=='__main__': main()
