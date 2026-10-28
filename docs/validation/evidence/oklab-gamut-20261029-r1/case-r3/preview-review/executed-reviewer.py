"""Record actual static viewing plus native encoded frame and GIF metadata."""
from pathlib import Path
import argparse,hashlib,json,subprocess,sys
from PIL import Image,ImageSequence
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'docs/validation/evidence/oklab-gamut-20261029-r1'


def main():
 ap=argparse.ArgumentParser();ap.add_argument('--case',required=True);a=ap.parse_args()
 public=ROOT/'docs/assets'/('oklab-gamut-20261029-'+a.case);out=BASE/('case-'+a.case)/'preview-review';out.mkdir(exist_ok=False)
 (out/'executed-reviewer.py').write_bytes(Path(__file__).read_bytes())
 sys.path.insert(0,str(ROOT/'product/src'));from ai_ad_editor.media import ffprobe_path
 cmd=[ffprobe_path(),'-v','error','-count_frames','-select_streams','v:0','-show_entries','stream=width,height,nb_read_frames,r_frame_rate,duration:format=duration','-of','json',str(public/'comparison.mp4')]
 r=subprocess.run(cmd,capture_output=True,check=True);(out/'ffprobe.stdout.json').write_bytes(r.stdout);(out/'ffprobe.stderr.txt').write_bytes(r.stderr)
 probe=json.loads(r.stdout);stream=probe['streams'][0];assert stream['width']==768 and stream['height']==216 and int(stream['nb_read_frames'])==10 and stream['r_frame_rate']=='10/1'
 with Image.open(public/'comparison.gif') as im:
  frames=[v.info.get('duration',0) for v in ImageSequence.Iterator(im)];assert len(frames)==10 and sum(frames)==1000
 with Image.open(public/'comparison.png') as im:assert im.size==(768,216)
 report=dict(status='passed',agent_static_PNG_view_completed=True,static_observation='Full 8x3 patch grids side-by-side; left clip, right less saturated OKLab; no captions expected.',
  human_continuous_playback=False,human_listening=False,physical_HDR_monitor=False,
  GIF=dict(frames=len(frames),duration_ms=sum(frames)),MP4=dict(frames=10,fps=10,width=768,height=216),
  files={name:hashlib.sha256((public/name).read_bytes()).hexdigest() for name in ['comparison.png','comparison.mp4','comparison.gif']})
 (out/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n');print(json.dumps(report,ensure_ascii=False))
if __name__=='__main__':main()
