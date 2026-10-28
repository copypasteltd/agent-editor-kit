"""Inspect actual preview metadata and record the completed agent static PNG review."""
from pathlib import Path
import argparse,hashlib,json,shutil,subprocess
from PIL import Image
ROOT=Path(__file__).resolve().parents[1]
ap=argparse.ArgumentParser();ap.add_argument('--case',required=True);a=ap.parse_args();assert a.case.replace('-','').isalnum()
base=ROOT/'docs/validation/evidence/native-hdr-media-measure-20261029-r1'/('installed-case-'+a.case)
out=base/'preview-review';out.mkdir(exist_ok=False);(out/'executed-reviewer.py').write_bytes(Path(__file__).read_bytes())
public=ROOT/'docs/assets'/('native-hdr-media-installed-20261029-'+a.case)
png=public/'author-SDR-frame.png';gif=public/'author-SDR-preview.gif';mp4=public/'author-SDR-preview.mp4'
with Image.open(png) as im:assert im.size==(640,360);png_info=dict(width=im.width,height=im.height,mode=im.mode)
with Image.open(gif) as im:
 durations=[]
 for index in range(im.n_frames):im.seek(index);durations.append(im.info.get('duration',0))
 gif_info=dict(frames=im.n_frames,width=im.width,height=im.height,total_duration_ms=sum(durations),frame_durations_ms=durations)
 assert im.n_frames==24 and sum(durations)==4000 and im.size==(480,270)
command=[shutil.which('ffprobe'),'-v','error','-count_frames','-select_streams','v:0','-show_streams','-of','json',str(mp4)]
r=subprocess.run(command,cwd=ROOT,capture_output=True,timeout=120,creationflags=subprocess.CREATE_NO_WINDOW)
(out/'ffprobe.stdout.json').write_bytes(r.stdout);(out/'ffprobe.stderr.txt').write_bytes(r.stderr);assert r.returncode==0
video=json.loads(r.stdout)['streams'][0];assert int(video['nb_read_frames'])==48 and video['avg_frame_rate']=='12/1' and float(video['duration'])==4
report=dict(status='passed',PNG=png_info,GIF=gif_info,MP4=dict(frames=48,width=video['width'],height=video['height'],fps='12/1',duration_seconds=4),
 files={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (png,gif,mp4)},
 agent_static_PNG_view_completed=True,static_observation='Full title, colour patches, highlight and footer visible without text overlap.',
 preview_scope='authored working-timeline explicit Reinhard SDR view; not decoded PQ/HLG movie or physical HDR monitoring',
 continuous_playback_review=False,human_listening_acceptance=False,physical_HDR_acceptance=False)
(out/'verification.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8',newline='\n');print(json.dumps(report))
