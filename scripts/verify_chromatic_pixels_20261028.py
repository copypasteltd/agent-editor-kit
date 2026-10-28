"""Strengthen C55 by checking each encoded frame/patch independently, no rerender."""
from pathlib import Path
import hashlib,json
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
out=ROOT/'docs/validation/evidence/native-chromatic-20261028-r1/case-r3'
work=ROOT/'local/agent-ffmpeg/native-chromatic-case-r3'
target=out/'independent-every-frame-patches.json';assert not target.exists()
(out/'executed-every-frame-oracle.py').write_bytes(Path(__file__).read_bytes())
# Independent published CSS Color4 values and rational BT.709 matrix.
CAT=np.array([[.955473421488075,-.02309845494876471,.06325924320057072],
    [-.0283697093338637,1.0099953980813041,.021041441191917323],
    [.012314014864481998,-.020507649298898964,1.330365926242124]])
PROPHOTO=np.array([[.7977666449006423,.13518129740053308,.0313477341283922],
    [.2880748288194013,.711835234241873,.00008993693872564],[0,0,.8251046025104602]])
BT709=np.array([[506752/1228815,87881/245763,12673/70218],
    [87098/409605,175762/245763,12673/175545],[7918/409605,87881/737289,1001167/1053270]])
video=work/'original-all-video.bin';raw=work/'source.gbrp16le'
actual=np.memmap(video,dtype='<u2',mode='r').reshape(48,3,360,640)
source=np.memmap(raw,dtype='<u2',mode='r').reshape(48,3,360,640)
records=[]
for frame in range(48):
    for patch in range(8):
        # Planar original order is G,B,R; native integer decode writes Float32.
        codes=source[frame,[2,0,1],120,50+75*patch].astype(np.float32)/65535
        v=codes.astype(float);linear=np.where(v<=1/32,v/16,v**1.8)
        rgb=np.linalg.inv(BT709)@CAT@PROPHOTO@linear
        encoded=np.where(np.abs(rgb)<=.0031308,12.92*rgb,np.sign(rgb)*(1.055*np.abs(rgb)**(1/2.4)-.055))
        expected=float(64+876*(np.clip(encoded,0,1)@np.array([.2126,.7152,.0722])))
        observed=float(actual[frame,0,110:138,35+75*patch:70+75*patch].mean())
        records.append(dict(frame=frame,patch=patch,expected_luma=expected,actual_luma=observed,absolute_error=abs(observed-expected)))
maximum=max(r['absolute_error'] for r in records)
report=dict(status='passed' if maximum<1.6 else 'failed',frames=48,patches_per_frame=8,comparisons=len(records),
    maximum_luma_code_error=maximum,tolerance=1.6,output_RGB_clip_explicit=True,
    source_sha256=hashlib.sha256(raw.read_bytes()).hexdigest(),decoded_video_sha256=hashlib.sha256(video.read_bytes()).hexdigest(),
    product_code_imported=False,new_renders=0,records=records)
target.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8',newline='\n')
print(json.dumps({k:v for k,v in report.items() if k!='records'}));assert report['status']=='passed'
