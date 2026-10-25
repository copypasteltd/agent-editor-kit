"""Render actual applied timings and verify editable package/PCM/pixel roundtrip."""
import argparse
import contextlib
import hashlib
import io
import json
import math
from pathlib import Path
import shutil
import subprocess
import sys
import time
import wave

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('site','project','output','public'):
        parser.add_argument('--'+name,type=Path,required=True)
    parser.add_argument('--runner',type=Path)
    a=parser.parse_args()
    site,project,output,public=a.site.resolve(strict=True),a.project.resolve(strict=True),a.output.resolve(),a.public.resolve()
    assert output.is_relative_to(ROOT/'docs/validation/evidence') and not output.exists()
    assert public.is_relative_to(ROOT/'docs/assets') and not public.exists()
    output.mkdir(parents=True);public.mkdir(parents=True)
    sys.path.insert(0,str(site))
    from ai_ad_editor.cli import main as cli_main
    from ai_ad_editor.runtime import configure_local_runtime
    configure_local_runtime()
    def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
    def save(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    before={str(p):sha(p) for p in sorted((site/'ai_ad_editor').glob('*.py'))}
    (output/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    calls=[]
    def cli(*argv):
        argv=list(map(str,argv));start=time.monotonic()
        if a.runner:
            process=subprocess.run(['powershell','-NoProfile','-ExecutionPolicy','Bypass','-File',str(a.runner),*argv],
                                   cwd=ROOT,capture_output=True,timeout=900)
            code,raw,err=process.returncode,process.stdout.decode('utf-8-sig'),process.stderr.decode('utf-8','replace')
        else:
            out,errors=io.StringIO(),io.StringIO()
            with contextlib.redirect_stdout(out),contextlib.redirect_stderr(errors):code=cli_main(argv)
            raw,err=out.getvalue(),errors.getvalue()
        value=json.loads(raw);calls.append(dict(argv=argv,exit_code=code,result=value,stderr=err,seconds=time.monotonic()-start))
        save(output/f'{len(calls):02}.json',calls[-1]);assert code==0,value
        print(json.dumps(dict(call=len(calls),command=value['command'],code=code)),flush=True)
        return value
    original=ROOT/'docs/assets/ctc-alignment-20261018'
    result=json.loads((project/'assets/alignment/activity.json').read_text('utf-8'))
    truth=json.loads((original/'input-provenance.json').read_text('utf-8'))
    n=truth['samples'];ticks=(n*90000+8000)//16000;frames=math.ceil(ticks*30/90000)
    font=site/'ai_ad_editor/material_data/fonts/noto-sans-sc-variable.ttf'
    canvas=Image.new('RGB',(1280,720),'#111d29');draw=ImageDraw.Draw(canvas)
    def label(x,y,text,size=24,color='#dce8ed'):
        draw.text((x,y),text,font=ImageFont.truetype(str(font),size),fill=color)
    label(42,25,'agent editor kit | CTC word boundary comparison',34)
    label(42,80,'Original authored blocks / raw CTC / audio-activity estimate',23)
    segment=result['segments'][0]
    for i,(reference,raw,estimated) in enumerate(zip(truth['words'],segment['raw_units'],segment['units'])):
        y=145+i*57
        label(42,y,reference['word'],21)
        for delta,value,color in ((0,reference,'#91a3b0'),(13,raw,'#f0b36c'),(26,estimated,'#6bd4ba')):
            left=185+value['start_sample']*1030/n;right=185+value['end_sample']*1030/n
            draw.rounded_rectangle((left,y+delta,right,y+delta+9),radius=2,fill=color)
    label(42,510,'Gray = authored placement   Amber = raw peaks   Green = estimated activity',21)
    label(42,550,'Controlled synthetic speech; continuous speech, Chinese and lyrics remain open.',20)
    label(42,585,'The subtitle below uses the actual CLI-applied timing:',21)
    board=public/'comparison-board.png';canvas.save(board)
    source=dict(kind='original diagnostic layout using actual inference and unchanged authored word references',
                license_spdx='CC0-1.0',creator='agent editor kit',input_audio_published_elsewhere=True,
                audio_source='../../ctc-alignment-20261018/input.wav',
                font='Noto Sans SC / OFL-1.1, retained in installed package material data',
                source_alignment_sha256=sha(project/'assets/alignment/activity.json'),
                no_claim_of_natural_phonetic_ground_truth=True)
    save(public/'SOURCE.json',source)
    cli('media','ingest','--project',project,'--input',board,'--asset-id','comparison',
        '--license-spdx','CC0-1.0','--creator','agent editor kit','--evidence',public/'SOURCE.json','--verification-status','verified')
    cli('media','ingest','--project',project,'--input',font,'--asset-id','font')
    changes=project/'comparison-timeline.json'
    save(changes,dict(operations=[
        dict(op='update_sequence',sequence_id='seq_main',patch=dict(canvas=dict(width=1280,height=720))),
        dict(op='append_clip',track_id='track_video_1',asset_id='comparison',source_in_tick=0,source_out_tick=ticks,
             timeline_start_tick=0,duration_tick=ticks),
        dict(op='append_clip',track_id='track_audio_1',asset_id='speech',source_in_tick=0,source_out_tick=ticks,
             timeline_start_tick=0,duration_tick=ticks),
        dict(op='add_track',track_id='captions',kind='subtitle',order=2)]))
    cli('timeline','compose','--project',project,'--input',changes)
    aligned=cli('subtitle','align','--project',project,'--asset-id','speech','--adapter-id','ctc',
        '--transcript',original/'transcript.txt','--output','assets/alignment/applied.json','--granularity','whitespace',
        '--boundary-mode','activity','--apply','--track-id','captions','--font-asset-id','font')['data']['result']
    assert aligned['segments'][0]['units']==segment['units']
    render_args=['--container','mkv','--audio-codec','pcm_f32le','--width','1280','--height','720','--crf','0','--pixel-format','yuv444p']
    movie=project/'renders/activity.mkv'
    cli('render','--project',project,'--output',movie,*render_args)
    cli('quality','check','--project',project,'--input',movie,'--width','1280','--height','720','--require-audio')
    package=project.parent/'activity.aevpkg.zip'
    cli('convert','export','--project',project,'--target-format','package','--output',package)
    restored=project.parent/'对齐往返 工程'
    cli('convert','import','--input',package,'--output',restored)
    cli('validate','--project',restored)
    second=restored/'renders/activity-roundtrip.mkv'
    cli('render','--project',restored,'--output',second,*render_args)
    ff_calls=[]
    def ff(*args):
        process=subprocess.run(['ffmpeg','-v','error','-nostdin',*map(str,args)],capture_output=True,timeout=300)
        ff_calls.append(dict(argv=list(map(str,args)),exit_code=process.returncode))
        assert process.returncode==0,process.stderr
        return process.stdout
    audios=[ff('-i',p,'-vn','-ar','48000','-ac','2','-f','f32le','pipe:1') for p in (original/'input.wav',movie,second)]
    # Last partial video frame may pad a few trailing zero samples. Compare all source samples separately.
    source_pcm=np.frombuffer(audios[0],dtype='<f4');rendered=np.frombuffer(audios[1],dtype='<f4')
    assert len(rendered)>=len(source_pcm)
    error=float(np.max(np.abs(rendered[:len(source_pcm)]-source_pcm)))
    assert error<=3e-6,(error,len(rendered),len(source_pcm))
    assert audios[1]==audios[2]
    pixels=[]
    for index,p in enumerate((movie,second)):
        raw=ff('-i',p,'-an','-pix_fmt','rgb24','-c:v','rawvideo','-f','framemd5','pipe:1')
        count=sum(1 for line in raw.decode().splitlines() if line and not line.startswith('#'))
        assert count==frames,(count,frames)
        (output/f'roundtrip-{index}-rgb.framemd5').write_bytes(raw)
        pixels.append(hashlib.sha256(raw).hexdigest())
    assert pixels[0]==pixels[1]
    ff('-n','-i',movie,'-vf',"select='eq(n,30)'",'-frames:v','1',public/'actual-frame-30.png')
    ff('-n','-i',movie,'-map','0:v:0','-an','-c:v','copy',public/'actual-output-silent.mp4')
    ff('-n','-loop','1','-i',board,'-t',str(frames/30),'-r','30','-an','-c:v','libx264','-pix_fmt','yuv420p',public/'original-board-silent.mp4')
    ff('-n','-i',movie,'-an','-vf','fps=10,scale=960:540:flags=lanczos,split[a][b];[a]palettegen[p];[b][p]paletteuse',public/'actual-output-silent.gif')
    shutil.copyfile(project/'assets/alignment/applied.json',public/'applied-alignment.json')
    after={str(p):sha(p) for p in sorted((site/'ai_ad_editor').glob('*.py'))};assert before==after
    with Image.open(public/'actual-output-silent.gif') as image:
        gif_frames=image.n_frames;duration=0
        for i in range(gif_frames):image.seek(i);duration+=image.info.get('duration',0)
    save(output/'verification.json',dict(status='passed',cli_calls=len(calls),model_forward_calls=aligned['worker']['model_forward_calls'],
        project=str(project),local_audio_movie=str(movie),local_package=str(package),package_sha256=sha(package),
        source_samples_16000=n,video_frames=frames,fps=30,gif_frames=gif_frames,gif_duration_ms=duration,
        source_pcm_max_abs_difference=error,package_roundtrip_pcm_exact=True,package_roundtrip_rgb_exact=True,
        decoded_rgb_framemd5_manifest_sha256=pixels[0],frozen_before=before,frozen_after=after,frozen_equal=True,
        continuous_playback_review=False,human_listening=False,full_G15_closed=False,
        files={p.name:dict(bytes=p.stat().st_size,sha256=sha(p)) for p in public.iterdir() if p.is_file()},ffmpeg_calls=ff_calls))
    print(json.dumps(dict(status='passed',frames=frames,pcm_max_abs_difference=error,roundtrip_exact=True)),flush=True)


if __name__=='__main__':main()
