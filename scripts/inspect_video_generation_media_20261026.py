"""Inspect all real local outputs; do not redistribute unaccepted model media."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess

from PIL import Image, ImageDraw, ImageSequence

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/validation/evidence/video-generation-20261026-r1'


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--run',required=True);ap.add_argument('--case-run',default='r1');a=ap.parse_args()
    assert a.run.replace('-','').isalnum() and a.case_run.replace('-','').isalnum()
    out=BASE/('media-inspection-'+a.run);out.mkdir(exist_ok=False)
    (out/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    case=json.loads((BASE/('case-'+a.case_run)/'verification.json').read_bytes())
    assert case['status']=='passed_actual_four_mode_cuda_transport_and_editable_package' and len(case['modes'])==4
    original_root=Path(case['project']);imported_root=original_root.parent/'重新 导入工程'
    original=json.loads((original_root/'project.json').read_bytes());imported=json.loads((imported_root/'project.json').read_bytes())
    first_assets={asset['id']:asset for asset in original['assets']};asset_checks=[]
    for asset in imported['assets']:
        source=first_assets[asset['id']];before=sha(original_root/source['uri']);after=sha(imported_root/asset['uri'])
        assert before==after and 'sha256:'+after==asset['sha256']==source['sha256']
        asset_checks.append(dict(asset_id=asset['id'],original_sha256=before,imported_sha256=after,equal=True))
    assert len(asset_checks)==6
    records=[];board=Image.new('RGB',(768,4*170),(17,22,29));draw=ImageDraw.Draw(board)
    for index,row in enumerate(case['modes']):
        output=Path(row['output']);assert sha(output)==row['output_sha256']
        mp4=Path(row['preview']);gif=Path(row['gif']);contact=Path(row['contact'])
        value=subprocess.run(['ffprobe','-v','error','-count_frames','-show_streams','-show_format','-of','json',str(mp4)],
            capture_output=True,check=True,creationflags=subprocess.CREATE_NO_WINDOW)
        (out/(row['mode']+'-mp4-probe.json')).write_bytes(value.stdout)
        probe=json.loads(value.stdout);video=next(s for s in probe['streams'] if s['codec_type']=='video')
        assert int(video['nb_read_frames'])==17 and video['avg_frame_rate']=='12/1'
        assert not any(s['codec_type']=='audio' for s in probe['streams'])
        with Image.open(gif) as opened:
            delays=[frame.info.get('duration',0) for frame in ImageSequence.Iterator(opened)]
        assert delays and all(type(d) is int and d>0 and d%10==0 for d in delays)
        assert abs(sum(delays)-17/12*1000)<=10
        for path in (output,mp4,gif,contact):assert path.resolve().is_relative_to(ROOT/'workspace')
        with Image.open(contact) as image:board.paste(image.convert('RGB'),(0,index*170+23))
        draw.text((8,index*170+5),row['mode']+' | actual generated frames 0 / 8 / 16',fill=(230,235,241))
        records.append(dict(mode=row['mode'],mp4=str(mp4),mp4_sha256=sha(mp4),mp4_frames=17,mp4_fps='12',
            mp4_duration_seconds=float(probe['format']['duration']),gif=str(gif),gif_sha256=sha(gif),
            gif_frames=len(delays),gif_frame_delays_ms=delays,gif_duration_ms=sum(delays),
            contact=str(contact),contact_sha256=sha(contact),decoded_movie_frames='independently checked in actual case',audio=False))
    grid=Path(case['project']).parent/'all-modes-actual-contact.png';board.save(grid)
    report=dict(status='passed',at_utc=datetime.now(timezone.utc).isoformat(),cases=records,package_asset_checks=asset_checks,local_contact_sheet=str(grid),
        local_contact_sha256=sha(grid),model_media_published=False,static_image_review=False,continuous_playback=False,human_listening=False,
        note='Numerical decode/timing inspection only; visual review is recorded separately after opening the contact sheet.')
    (out/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    print(json.dumps(report,ensure_ascii=False),flush=True)


if __name__=='__main__':main()
