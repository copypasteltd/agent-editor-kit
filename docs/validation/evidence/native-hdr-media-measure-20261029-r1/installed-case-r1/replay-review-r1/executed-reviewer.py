"""Independently compare actual package-replay receipts and complete source PCM."""
from pathlib import Path
import argparse,hashlib,json,shutil,subprocess
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
ap=argparse.ArgumentParser();ap.add_argument('--case',required=True);ap.add_argument('--run',required=True);a=ap.parse_args();assert all(x.replace('-','').isalnum() for x in (a.case,a.run))
case=ROOT/'docs/validation/evidence/native-hdr-media-measure-20261029-r1'/('installed-case-'+a.case)
out=case/('replay-review-'+a.run);out.mkdir(exist_ok=False);(out/'executed-reviewer.py').write_bytes(Path(__file__).read_bytes())
def load(p):return json.loads(Path(p).read_bytes())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
original=load(case/'hlg420-clip.stdout.json')['data'];replay=load(case/'replay-measure.stdout.json')['data']
keys=['decoded_RGBA32_sha256','native_clock_sha256','framed_metrics_sha256','frames','peak_pixel','maximum_frame_average',
      'duration_weighted_frame_average_nits','minimum_RGB_component_nits','analyzed_duration_seconds','range_counts']
assert all(original[k]==replay[k] for k in keys)
work=ROOT/'local/agent-ffmpeg'/('native-hdr-media-installed-case-'+a.case);p=load(work/'project/project.json')
asset=next(x for x in p['assets'] if x['id']=='tones');source=work/'project'/asset['uri']
assert 'sha256:'+sha(source)==asset['sha256']
command=[shutil.which('ffmpeg'),'-v','error','-i',str(source),'-map','0:a:0','-vn','-c:a','pcm_f32le','-f','f32le','pipe:1']
r=subprocess.run(command,cwd=ROOT,capture_output=True,timeout=120,creationflags=subprocess.CREATE_NO_WINDOW)
(out/'stderr.txt').write_bytes(r.stderr);assert r.returncode==0
source_pcm=work/'source-pcm.f32';assert not source_pcm.exists();source_pcm.write_bytes(r.stdout)
assert r.stdout==(work/'original-pcm.f32').read_bytes()==(work/'replay-pcm.f32').read_bytes()
samples=np.frombuffer(r.stdout,dtype='<f4');assert samples.size==384000 and np.isfinite(samples).all() and np.count_nonzero(samples)>380000
report=dict(status='passed',complete_source_original_replay_PCM_equal=True,PCM_bytes=len(r.stdout),PCM_scalars=samples.size,
 nonzero_PCM_scalars=int(np.count_nonzero(samples)),PCM_sha256=sha(source_pcm),equal_meter_fields=keys,
 input_receipts={p.name:sha(p) for p in [case/'hlg420-clip.stdout.json',case/'replay-measure.stdout.json']},
 command=command,source_asset_sha256=asset['sha256'],human_listening_acceptance=False)
(out/'verification.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8',newline='\n');print(json.dumps(report))
