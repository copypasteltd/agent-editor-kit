"""Render actual dubbed captions; verify PCM and editable package; publish silent evidence."""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

import numpy as np
from PIL import Image,ImageDraw,ImageFont

ROOT=Path(__file__).resolve().parents[1]


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()
def save(path,value):path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('site','project','output','public'):
        parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args()
    site,project=args.site.resolve(strict=True),args.project.resolve(strict=True)
    output,public=args.output.resolve(),args.public.resolve()
    assert output.is_relative_to(ROOT/'docs/validation/evidence') and public.is_relative_to(ROOT/'docs/assets')
    output.mkdir(parents=True,exist_ok=False);public.mkdir(parents=True,exist_ok=False)
    (output/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    prefix=[sys.executable,'-I','-S','-B','-u','-X','utf8','-c','import sys;sys.path.insert(0,sys.argv.pop(1));from ai_ad_editor.cli import main;raise SystemExit(main())',str(site)]
    calls=[]
    frozen=lambda:{p.name:sha(p) for p in sorted((site/'ai_ad_editor').glob('*.py'))}
    before=frozen()
    def cli(*argv):
        start=time.monotonic();result=subprocess.run([*prefix,*map(str,argv)],cwd=ROOT,capture_output=True,timeout=900,creationflags=subprocess.CREATE_NO_WINDOW)
        value=json.loads(result.stdout.decode('utf-8-sig'))
        calls.append(dict(argv=list(map(str,argv)),exit_code=result.returncode,response=value,seconds=time.monotonic()-start))
        save(output/(f'{len(calls):02}-cli.json'),calls[-1]);assert result.returncode==0,value
        print(json.dumps(dict(call=len(calls),command=value['command'])),flush=True)
        return value
    def ffmpeg(argv):
        result=subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-nostdin',*map(str,argv)],capture_output=True,timeout=900,creationflags=subprocess.CREATE_NO_WINDOW)
        assert result.returncode==0,result.stderr.decode('utf-8','replace')
        return result.stdout
    report_path=next((project/'assets/derived/dubbing').glob('*/report.json'))
    report=json.loads(report_path.read_text('utf-8'))
    assert len(report['cues'])==3
    ticks=max(c['end_ms'] for c in report['cues'])*90
    seconds=ticks/90000;frames=round(seconds*30)
    font=site/'ai_ad_editor/material_data/fonts/noto-sans-sc-variable.ttf'
    image=Image.new('RGB',(1280,720),'#0d1723');draw=ImageDraw.Draw(image)
    def text(x,y,value,size=24,color='#dce9f4'):
        draw.text((x,y),value,font=ImageFont.truetype(str(font),size),fill=color)
    text(46,26,'agent editor kit',38)
    text(46,86,'Subtitle translation + local GPU voice',30,'#84d6c0')
    text(46,132,'Actual WAV durations / one Kokoro initialization / editable cue clips',21)
    for i,cue in enumerate(report['cues']):
        y=184+i*100
        draw.rounded_rectangle((42,y,1238,y+86),radius=12,fill='#182838')
        text(60,y+8,f'{i+1:02}  '+cue['source_text'],24)
        final=cue['attempts'][-1]
        text(60,y+44,f"{cue['voice']['id']}  |  speech {final['samples']/24000:.3f}s  |  window {(cue['end_ms']-cue['start_ms'])/1000:.3f}s  |  retained whole speech",20,'#9eb5c9')
        left=976;right=1216;top=y+16
        draw.rectangle((left,top,right,top+7),fill='#50647b')
        fraction=final['samples']/cue['slot_samples']
        draw.rectangle((left,top,left+(right-left)*fraction,top+7),fill='#84d6c0')
    text(46,498,'Cue-window timing. Natural speech, semantics, lip sync and voice rights need review.',18,'#9eb5c9')
    board=public/'source-board.png';image.save(board)
    provenance=dict(source='Authored diagnostic graphic using actual report durations and three authored English lines.',
        license='CC0-1.0',font='Noto Sans SC / OFL-1.1, included in installed material data',
        report_sha256=sha(report_path),image_sha256=sha(board),voice_media_in_public_artifacts=False)
    save(public/'source-provenance.json',provenance)
    (project/'assets/dubbing-demo-source.json').write_bytes((public/'source-provenance.json').read_bytes())
    cli('media','ingest','--project',project,'--input',board,'--asset-id','dubbing_board','--verification-status','verified',
        '--creator','agent editor kit validation fixture','--license-spdx','CC0-1.0','--source-url','local://assets/dubbing-demo-source.json',
        '--evidence','assets/dubbing-demo-source.json','--license-url','assets/dubbing-demo-source.json','--permitted-use','commercial_ad')
    changes=output/'compose.json'
    save(changes,dict(sequence_id='seq_main',operations=[dict(op='append_clip',track_id='track_video_1',asset_id='dubbing_board',
        source_in_tick=0,source_out_tick=ticks,timeline_start_tick=0)]))
    cli('timeline','compose','--project',project,'--input',changes)
    cli('validate','--project',project)
    options=['--container','mkv','--audio-codec','pcm_f32le','--crf','0','--pixel-format','yuv444p','--width','1280','--height','720']
    movie=project/'renders/dubbing.mkv'
    cli('render','--project',project,'--output',movie,*options)
    package=project.parent/'dubbing.aevpkg.zip'
    cli('convert','export','--project',project,'--target-format','package','--output',package)
    restored=project.parent/'dubbing-restored'
    cli('convert','import','--input',package,'--output',restored)
    cli('validate','--project',restored)
    roundtrip=restored/'renders/dubbing-roundtrip.mkv'
    cli('render','--project',restored,'--output',roundtrip,*options)
    pcm=[ffmpeg(['-i',path,'-map','0:a:0','-ac','1','-ar','48000','-f','f32le','-']) for path in (movie,roundtrip)]
    assert pcm[0]==pcm[1]
    rgb=[ffmpeg(['-i',path,'-map','0:v:0','-pix_fmt','rgb24','-f','hash','-hash','sha256','-']).decode().strip() for path in (movie,roundtrip)]
    assert rgb[0]==rgb[1]
    expected=np.zeros(round(seconds*48000),dtype=np.float32)
    for cue in report['cues']:
        audio=project/cue['attempts'][-1]['output']
        source=np.frombuffer(ffmpeg(['-i',audio,'-ac','1','-ar','48000','-f','f32le','-']),dtype='<f4')
        start=cue['start_ms']*48
        expected[start:start+len(source)]+=source
    actual=np.frombuffer(pcm[0],dtype='<f4')
    assert len(actual)==len(expected),(len(actual),len(expected))
    error=float(np.max(np.abs(actual-expected)))
    assert error<=3e-6,dict(pcm_max_abs_difference=error)
    silent=public/'output-silent.mp4'
    ffmpeg(['-i',movie,'-map','0:v:0','-an','-c:v','libx264','-crf','23','-pix_fmt','yuv420p',silent])
    ffmpeg(['-i',movie,'-vf','fps=5,scale=640:-2:flags=lanczos,palettegen',public/'palette.png'])
    ffmpeg(['-i',movie,'-i',public/'palette.png','-filter_complex','fps=5,scale=640:-2:flags=lanczos[v];[v][1:v]paletteuse',
        '-an','-loop','0',public/'preview.gif'])
    for i,second in enumerate((2,9,15)):
        ffmpeg(['-ss',str(second),'-i',movie,'-frames:v','1',public/f'frame-{i+1}.png'])
    with Image.open(public/'preview.gif') as gif:
        gif_frames=gif.n_frames;gif_ms=0
        for index in range(gif.n_frames):gif.seek(index);gif_ms+=gif.info.get('duration',0)
    assert gif_ms==round(seconds*1000),(gif_ms,seconds)
    after=frozen();assert before==after
    receipt=dict(status='passed-with-natural-quality-review-open',checked_at_utc=datetime.now(timezone.utc).isoformat(),
        project=str(project),local_audio_movie=str(movie),local_package=str(package),package_sha256=sha(package),
        frames=frames,fps=30,duration_seconds=seconds,width=1280,height=720,source_pcm_max_abs_difference=error,
        package_pcm_exact=True,package_decoded_rgb_exact=True,rendered_pcm_sha256=hashlib.sha256(pcm[0]).hexdigest(),
        decoded_rgb_sha256=rgb[0],gif_frames=gif_frames,gif_duration_ms=gif_ms,cli_calls=len(calls),
        frozen_equal=True,source_provenance=provenance,human_listening=False,human_semantic_acceptance=False,
        continuous_playback=False,public_outputs_silent=True,full_G19_closed=False,native_windows=True,virtualization=False,
        files=[dict(path=p.relative_to(ROOT).as_posix(),bytes=p.stat().st_size,sha256=sha(p)) for p in public.iterdir() if p.is_file()])
    save(output/'verification.json',receipt)
    save(public/'media-manifest.json',receipt)
    print(json.dumps({k:v for k,v in receipt.items() if k not in ('files','source_provenance')}),flush=True)


if __name__=='__main__':main()
