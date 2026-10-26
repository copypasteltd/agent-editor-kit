"""Inspect actual local outputs and publish only an original numeric timing chart."""
from fractions import Fraction
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageSequence

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/validation/evidence/model-session-20261027-r1'


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def load(path):return json.loads(Path(path).read_bytes())


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--run',required=True);args=parser.parse_args();assert args.run.replace('-','').isalnum()
    out=BASE/('media-inspection-'+args.run);out.mkdir(exist_ok=False);(out/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    case=load(BASE/'case-r1/verification.json');assert case['status']=='passed_actual_cuda_resident_reuse_and_cancel'
    project=Path(case['project']);work=project.parent;imported=work/'重新 导入工程'
    source=load(project/'project.json');target=load(imported/'project.json')
    target_assets={a['id']:a for a in target['assets']};checks=[]
    for asset in source['assets']:
        before=project/asset['uri'];after=imported/target_assets[asset['id']]['uri']
        equal=sha(before)==sha(after)==asset['sha256'].removeprefix('sha256:')
        assert equal;checks.append(dict(asset_id=asset['id'],sha256=sha(before),equal=equal))
    font=ImageFont.truetype('C:/Windows/Fonts/segoeui.ttf',18)
    contact=Image.new('RGB',(5*256,3*(144+30)),(20,23,29));draw=ImageDraw.Draw(contact);cases=[]
    for i,row in enumerate(case['jobs']):
        raw=(work/(row['asset_id']+'-decode.bin')).read_bytes();pixels=np.frombuffer(raw,np.uint8).reshape(17,144,256,4)
        for column,index in enumerate((0,4,8,12,16)):
            contact.paste(Image.fromarray(pixels[index,:,:,:3]),(column*256,i*174+30))
            draw.text((column*256+8,i*174+4),row['asset_id']+' | frame '+str(index),font=font,fill=(237,241,247))
        result=subprocess.run(['ffprobe','-v','error','-count_frames','-show_streams','-of','json',row['preview']],capture_output=True,check=True,
            timeout=60,creationflags=subprocess.CREATE_NO_WINDOW)
        (out/(row['asset_id']+'-probe.json')).write_bytes(result.stdout);probe=json.loads(result.stdout)
        video=next(x for x in probe['streams'] if x['codec_type']=='video')
        assert int(video['nb_read_frames'])==17 and Fraction(video['avg_frame_rate'])==12
        assert not any(x['codec_type']=='audio' for x in probe['streams'])
        gif=work/(row['asset_id']+'.gif')
        with Image.open(gif) as opened:delays=[frame.info.get('duration',0) for frame in ImageSequence.Iterator(opened)]
        assert abs(sum(delays)-17*1000/12)<=10
        cases.append(dict(asset_id=row['asset_id'],preview=row['preview'],sha256=sha(row['preview']),frames=17,fps='12',audio=False,
            gif=str(gif),gif_sha256=sha(gif),gif_frames=len(delays),gif_duration_ms=sum(delays),rgba_sha256=row['rgba_sha256']))
    path=work/'actual-resident-contact.png';contact.save(path)
    public=ROOT/'docs/assets/model-session-20261027-r1';public.mkdir(exist_ok=False)
    rows=[('Session full-model verification',case['session_start']['startup_seconds']),('First generation, includes loading',case['cold_cli_seconds']),
          ('Warm replay, identical seed',case['warm_cli_seconds'][0]),('Warm generation, new condition',case['warm_cli_seconds'][1])]
    data=dict(scope='single observations on one RTX3060, not a repeated benchmark',units='seconds',rows=[dict(name=n,seconds=s) for n,s in rows],
        registration_seconds=next(c['seconds'] for c in case['calls'] if c['name']=='register-vace'),
        actual_model_frames_published=False,evidence='docs/validation/evidence/model-session-20261027-r1/case-r1/verification.json')
    (public/'timing-data.json').write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    chart=Image.new('RGB',(1160,435),(246,248,252));painter=ImageDraw.Draw(chart)
    title=ImageFont.truetype('C:/Windows/Fonts/segoeuib.ttf',27);label=ImageFont.truetype('C:/Windows/Fonts/segoeui.ttf',18)
    painter.text((30,22),'Native GPU sessions: measured cold and warm costs',font=title,fill=(21,33,52))
    maximum=max(s for _,s in rows)
    for i,(name,seconds) in enumerate(rows):
        top=89+i*65;painter.text((30,top+7),name,font=label,fill=(35,46,65))
        width=max(3,round(560*seconds/maximum));color=(54,103,197) if i<2 else (20,139,116)
        painter.rounded_rectangle((390,top,390+width,top+37),radius=5,fill=color)
        painter.text((402+width,top+7),f'{seconds:.2f}s',font=label,fill=(21,33,52))
    painter.text((30,365),'One host / single observations. Startup and first loading remain real costs.',font=label,fill=(67,78,94))
    painter.text((30,395),f"Registration: {data['registration_seconds']:.2f}s separately. No model imagery shown.",font=label,fill=(67,78,94))
    chart.save(public/'timing.png')
    (public/'SOURCE.txt').write_text('Original chart generated from actual C44 numeric timing receipts by scripts/inspect_model_session_media_20261027.py. CC0-1.0 for this chart. No model output frame, third-party image, voice or weight included.\n',encoding='utf8',newline='\n')
    (public/'PUBLICATION_SCOPE.txt').write_text('Public: measured numeric evidence and original data chart only. Actual VACE model video/GIF/project package stays local with unverified/internal rights.\n',encoding='utf8',newline='\n')
    report=dict(status='passed',synthetic_model=False,model_media_published=False,contact_sheet=str(path),contact_sha256=sha(path),cases=cases,
        package_asset_checks=checks,static_image_review=False,continuous_playback=False,human_listening=False,natural_quality_accepted=False,
        timing_chart='docs/assets/model-session-20261027-r1/timing.png',timing_chart_sha256=sha(public/'timing.png'))
    (out/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    print(json.dumps(dict(status='passed',actual_cases=len(cases),matching_package_assets=len(checks),contact_sheet=str(path))),flush=True)


if __name__=='__main__':main()
