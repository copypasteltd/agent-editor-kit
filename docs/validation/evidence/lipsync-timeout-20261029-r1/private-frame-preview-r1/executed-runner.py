"""Create a private, labelled actual-output contact sheet; no public-media grant."""
import hashlib,json
from pathlib import Path
from PIL import Image,ImageDraw

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'docs/validation/evidence/lipsync-timeout-20261029-r1'
WORK=ROOT/'local/agent-ffmpeg/native-worker-source61-lipsync-r1'

def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def main():
    r=json.loads((BASE/'source61-lipsync-cuda-r1/verification.json').read_bytes())
    assert r['status']=='passed' and r['actual_MuseTalk_CUDA']
    w,h,n=r['width'],r['height'],r['frames'];size=w*h*4
    original=WORK/'input-rgba.raw';master=WORK/'master-rgba.raw'
    assert original.stat().st_size==size and master.stat().st_size==n*size
    out=BASE/'private-frame-preview-r1';out.mkdir(exist_ok=False)
    (out/'executed-runner.py').write_bytes(Path(__file__).read_bytes())
    sheet=Image.new('RGB',(1536,448),'#18212a');draw=ImageDraw.Draw(sheet)
    draw.text((14,12),'ACTUAL CLI61 / original and generated frames / private internal preview',fill='white')
    rows=[('SOURCE',original,0),('GENERATED frame 0',master,0),
          ('GENERATED frame 66 / 2.64s',master,66),('GENERATED frame 132 / 5.28s',master,132)]
    pins={}
    for i,(label,p,index) in enumerate(rows):
        with p.open('rb') as f:f.seek(index*size);raw=f.read(size)
        assert len(raw)==size
        frame=Image.frombytes('RGBA',(w,h),raw)
        frame=Image.alpha_composite(Image.new('RGBA',(w,h),(48,55,65,255)),frame).convert('RGB')
        frame.thumbnail((384,384),Image.Resampling.LANCZOS);sheet.paste(frame,(384*i,46))
        draw.text((384*i+8,32),label,fill='#cbd6e1')
        pins[label]=hashlib.sha256(raw).hexdigest()
    target=WORK/'private-actual-frames.png';assert not target.exists();sheet.save(target)
    ledger=WORK/'project/rights-ledger.json';rights=json.loads(ledger.read_bytes())
    active=[x for x in rights['records'] if x.get('active')]
    assert active and all(x['permitted_uses']==['internal'] for x in active)
    report=dict(status='passed',contact_sheet=str(target),contact_sheet_sha256=sha(target),
        exact_master_frames=n,width=w,height=h,sampled_frames=[0,66,132],frame_RGBA_sha256=pins,
        original_RGBA_sha256=sha(original),master_RGBA_sha256=sha(master),
        rights_ledger_sha256=sha(ledger),media_scope='private-internal-only',
        neural_forwards=0,human_visual_review=False,continuous_playback=False,human_listening=False,
        natural_quality_accepted=False,public_media_published=False)
    (out/'verification.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report),flush=True)

if __name__=='__main__':main()
