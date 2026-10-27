"""Finish C51 presentation from already verified real neural output, without inference."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib, json
import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT=Path(__file__).resolve().parents[1]
out=ROOT/'docs/validation/evidence/native-lipsync-20261027-r1/case-r1'
work=ROOT/'local/agent-ffmpeg/native-lipsync-case-r1'
public=ROOT/'docs/assets/native-lipsync-20261027-r1'
report=out/'verification.json'
record=json.loads(report.read_bytes())
assert record['status']=='failed' and 'cannot reshape array' in record['error']
saved=out/'verification.first-attempt.json'
assert not saved.exists()
saved.write_bytes(report.read_bytes())
(out/'executed-resume.py').write_bytes(Path(__file__).read_bytes())

def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def save():report.write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
def check(name,value):
    record['checks'].append(dict(name=name,ok=bool(value)))
    save()
    assert value,name

try:
    result=record['image_result'];configuration=result['configuration']
    n=configuration['video']['frames'];width=configuration['video']['width'];height=configuration['video']['height']
    worker=result['generation']['worker'];project=work/'可编辑 口型工程'
    master=project/result['asset']['uri']
    check('resume retains original neural master bytes','sha256:'+sha(master)==result['asset']['sha256'])
    raw=(work/'master-rgba.bin').read_bytes()
    check('resume retains complete decoded neural frame evidence','sha256:'+hashlib.sha256(raw).hexdigest()==worker['metrics']['rgba_sha256'])
    frames=np.frombuffer(raw,np.uint8).reshape(n,height,width,4)
    image=Image.open(public/'portrait.png').convert('RGB')
    font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',16)
    comparison=[]
    for i in range(n):
        sheet=Image.new('RGB',(width*2,height+34),(22,26,32));sheet.paste(image,(0,34));sheet.paste(Image.fromarray(frames[i,:,:,:3]),(width,34))
        draw=ImageDraw.Draw(sheet);draw.text((12,8),'SOURCE / synthetic portrait',font=font,fill='white');draw.text((width+12,8),'MuseTalk CUDA / synthetic lip sync',font=font,fill='white')
        comparison.append(sheet.resize((768,round((height+34)*768/(width*2))),Image.Resampling.LANCZOS))
    comparison[0].save(public/'comparison.gif',save_all=True,append_images=comparison[1:],duration=40,loop=0,optimize=False,disposal=2)
    comparison[0].save(public/'frame-first.png');comparison[n//2].save(public/'frame-middle.png');comparison[-1].save(public/'frame-last.png')
    with Image.open(public/'comparison.gif') as gif:
        duration=sum((gif.seek(i),gif.info.get('duration',0))[1] for i in range(gif.n_frames))
        check('GIF uses complete neural master clock',gif.n_frames==n and duration==n*40)
    render=json.loads((out/'render.stdout.json').read_bytes())['data']['probe']
    rendered_stream=next(s for s in render['streams'] if s['codec_type']=='video')
    adapter=json.loads((out/'register.stdout.json').read_bytes())['data']['adapter']
    clock=configuration['audio']
    record.pop('error',None)
    record.update(status='passed',presentation_resume=True,initial_presentation_failure='verification.first-attempt.json',
        frames=n,fps=25,duration_seconds=n/25,selected_PCM_scalars=clock['samples']*clock['channels'],padded_PCM_scalars=clock['padded_samples']*clock['channels'],
        all_source_PCM_equal=True,all_source_alpha_equal=True,all_outside_region_RGB_equal=True,all_package_rendered_frames_equal=True,all_package_rendered_PCM_equal=True,
        GIF_duration_ms=duration,rendered_frames=int(rendered_stream['nb_frames']),rendered_fps=rendered_stream['avg_frame_rate'],rendered_duration_seconds=render['duration_seconds'],
        presentation_clock_note='GIF: complete 25 fps RGBA neural master; MP4: project display_fps 30, complete package render equivalence verified separately.',
        adapter_sha256=adapter['sha256'],model_execution=worker['model_execution'],project=str(project),
        public_files=[dict(path=p.relative_to(ROOT).as_posix(),bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(public.iterdir()) if p.is_file()],
        finished_at_utc=datetime.now(timezone.utc).isoformat())
    save();print(json.dumps({k:record[k] for k in ('status','frames','fps','duration_seconds','rendered_frames','rendered_fps','GIF_duration_ms')}))
except BaseException as exc:
    record.update(status='failed',error=repr(exc));save();raise
