"""Prepare actual GIF stills or record explicit agent observations of those stills."""
import argparse, hashlib, json
from pathlib import Path
from PIL import Image, ImageDraw

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/validation/evidence/float-text-coverage-20261026-r1'

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--record',action='store_true');args=ap.parse_args()
    cases=[('case-r1','float-text-coverage-20261026-r1','native-text.gif'),
           ('4k-r2','float-text-coverage-20261026-4k-r2','4k-native-text.gif')]
    for evidence,folder,name in cases:
        public=ROOT/'docs/assets'/folder
        receipt=json.loads((BASE/evidence/'verification.json').read_bytes());assert receipt['status']=='passed'
        sheet=BASE/evidence/'gif-stills.png'
        if args.record:
            assert sheet.exists()
            files=[public/'original.png',public/name,sheet]
            files.append(public/('midpoint.png' if evidence=='case-r1' else 'preview.png'))
            notes=(["Actual reduced-resolution stills show geometric source, transformed child canvas, colored title and Chinese captions; title prefixes and word emphasis vary across selected stills."]
                   if evidence=='case-r1' else ["All eight actual GIF stills show the centered brand title fading in, the main line revealing whole text prefixes, and a visible Chinese footer on the authored dark background."])
            result=dict(inspection_by='agent',inspection='static PNG and actual GIF still contact sheet only',
                files=[dict(path=p.relative_to(ROOT).as_posix(),sha256=sha(p)) for p in files],notes=notes,
                continuous_playback=False,human_listening=False,natural_quality_accepted=False,
                full_resolution_pixel_quality_accepted=False,scope='Static observation is separate from automated full decode, clock and PCM checks.')
            output=BASE/evidence/'visual-observation.json';assert not output.exists()
            output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
            (BASE/evidence/'executed-observation.py').write_bytes(Path(__file__).read_bytes())
        else:
            assert not sheet.exists()
            with Image.open(public/name) as gif:
                indices=list(range(gif.n_frames)) if gif.n_frames<=8 else [round(i*(gif.n_frames-1)/7) for i in range(8)]
                image=Image.new('RGB',(4*480,2*300),(25,25,25));draw=ImageDraw.Draw(image)
                for slot,index in enumerate(indices):
                    gif.seek(index);frame=gif.convert('RGB');frame.thumbnail((480,270))
                    x,y=(slot%4)*480,(slot//4)*300
                    image.paste(frame,(x,y+24));draw.text((x+8,y+4),f'Actual GIF frame {index}',fill=(235,235,235))
                image.save(sheet)
        print(json.dumps(dict(evidence=evidence,recorded=args.record,path=str(sheet)),ensure_ascii=False),flush=True)

if __name__=='__main__':main()
