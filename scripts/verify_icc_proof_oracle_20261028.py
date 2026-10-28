"""Independent C58 proof-table roundtrip -> encoded Y/Cb/Cr, no product imports."""
from pathlib import Path
from datetime import datetime,timezone
import hashlib,json
import numpy as np
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'docs/validation/evidence/native-icc-output-20261028-r1/case-r3'
WORK=ROOT/'local/agent-ffmpeg/native-icc-output-case-r3'
def sha(p):
 with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
source_path=WORK/'source.gbrp16le';movie_path=WORK/'original-all-video.bin'
profile=ROOT/'docs/assets/native-icc-output-20261028-r3/original-proof.icc'
assert source_path.stat().st_size==movie_path.stat().st_size==48*3*360*640*2
source=np.memmap(source_path,dtype='<u2',mode='r',shape=(48,3,360,640))
video=np.memmap(movie_path,dtype='<u2',mode='r',shape=(48,3,360,640))
# Published D50-adapted BT709 XYZ matrix; no product/CMM color functions.
matrix=np.array([[.4360747,.3850649,.1430804],[.2225045,.7168786,.0606169],[.0139322,.0971045,.7141733]])
inverse=np.linalg.inv(matrix);records=[];errors=[]
for frame in range(48):
 for patch in range(8):
  rgb=source[frame,[2,0,1],120,50+75*patch].astype(np.float32).astype(float)/65535
  xyz=matrix@rgb;position=xyz*8;lo=np.floor(position).astype(int);fraction=position-lo
  # Original separable17-node B2A table encodes XYZ unit as32768/65535.
  # Separable functions reduce tetrahedral interpolation to one linear
  # interpolation per axis; table samples persist as uint16.
  table=lambda k:np.rint((.05+.12*(k/8)**2)*65535)
  device=(table(lo)*(1-fraction)+table(lo+1)*fraction)/65535
  # The original A2B table maps device RGB directly to D50 XYZ, then the
  # final working profile returns linear BT709. This intentionally noninverse
  # diagnostic pair must change the proof; it is not a printer characterization.
  linear=inverse@device
  encoded=np.where(linear<=.0031308,12.92*linear,1.055*np.maximum(linear,0)**(1/2.4)-.055)
  y=encoded@np.array([.2126,.7152,.0722])
  expected=np.array([64+876*y,512+896*(encoded[2]-y)/(2*(1-.0722)),512+896*(encoded[0]-y)/(2*(1-.2126))])
  actual=video[frame,:,120,50+75*patch].astype(float);error=np.abs(actual-expected);errors.append(error)
  records.append(dict(frame=frame,patch=patch,expected_YCbCr=expected.tolist(),actual_YCbCr=actual.tolist(),errors_codes=error.tolist()))
maximum=np.max(errors,axis=0);assert float(maximum.max())<1.0,maximum
report=dict(status='passed',at_utc=datetime.now(timezone.utc).isoformat(),comparisons=384,code_components=1152,
 maximum_YCbCr_errors_codes=maximum.tolist(),accepted_bound_codes=1.0,product_or_CMM_functions_used=False,
 inputs=[dict(path=str(p.relative_to(ROOT)),bytes=p.stat().st_size,sha256=sha(p)) for p in (source_path,movie_path,profile)],
 reference='Original B2A separable CLUT -> original A2B XYZ table -> inverse D50 matrix -> sRGB -> limited10bit BT709 YCbCr',
 full_physical_device_or_natural_image_acceptance=False,records=records)
(BASE/'independent-softproof.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
(BASE/'executed-softproof-oracle.py').write_bytes(Path(__file__).read_bytes())
print(json.dumps({k:v for k,v in report.items() if k not in ('records','inputs')},ensure_ascii=False))
