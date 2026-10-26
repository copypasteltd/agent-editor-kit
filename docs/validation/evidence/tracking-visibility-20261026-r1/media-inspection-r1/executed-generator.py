"""Decode real before/after display frames into a static inspection sheet."""
from pathlib import Path
import hashlib,json,subprocess
from PIL import Image,ImageDraw,ImageFont

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/validation/evidence/tracking-visibility-20261026-r1'

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def main():
    out=BASE/'media-inspection-r1';out.mkdir(exist_ok=False);(out/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    case=json.loads((BASE/'case-r2/verification.json').read_bytes());assert case['status']=='passed'
    ffmpeg=next(c['argv'][0] for c in case['calls'] if c['name']=='edited-frames');public=Path(case['public'])
    sheet=Image.new('RGB',(680,1120),'#101722');draw=ImageDraw.Draw(sheet)
    font=ImageFont.truetype(str(Path(case['installed'])/'site/ai_ad_editor/material_data/fonts/noto-sans-sc-variable.ttf'),14)
    calls=[];frames=[]
    for row,(first,last) in enumerate(((0,0),(9,9),(18,18),(22,22),(26,26))):
        for column,(label,index) in enumerate((('before',first),('edited',last))):
            target=out/(label+'-'+str(index)+'.png')
            argv=[ffmpeg,'-nostdin','-v','error','-n','-i',str(public/(label+'.mp4')),'-vf',f'select=eq(n\\,{index})','-frames:v','1',str(target)]
            r=subprocess.run(argv,cwd=ROOT,capture_output=True,timeout=60,creationflags=subprocess.CREATE_NO_WINDOW)
            assert r.returncode==0 and target.is_file(),r.stderr
            calls.append(dict(argv=argv,exit_code=r.returncode,stderr=r.stderr.decode('utf8','replace'),output_sha256=sha(target)))
            with Image.open(target) as image:
                assert image.size==(320,180);sheet.paste(image,(10+column*340,36+row*220))
            draw.text((10+column*340,10+row*220),f'{label} frame {index} / {index/12:.3f}s',font=font,fill='#e6edf5')
            frames.append(dict(label=label,frame=index,sha256=sha(target)))
    sheet.save(out/'contact-sheet.png')
    report=dict(status='passed',source='actual public MP4 decoder output; no reconstructed GUI',frames=frames,calls=calls,
        sheet_sha256=sha(out/'contact-sheet.png'),review_scope='static frame inspection only',continuous_playback=False,human_listening=False,natural_quality_accepted=False)
    (out/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    print(json.dumps(dict(status='passed',decoded_stills=10,contact_sheet=str(out/'contact-sheet.png')),ensure_ascii=False))

if __name__=='__main__':main()
