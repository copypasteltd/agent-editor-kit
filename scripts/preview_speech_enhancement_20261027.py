"""Make scientific spectra and playable A/B/C from actual installed C53 WAVs."""
from pathlib import Path
import argparse,hashlib,json,math,os,shutil,subprocess
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'docs/validation/evidence/native-speech-enhancement-20261027-r1'
ap=argparse.ArgumentParser();ap.add_argument('--run',required=True);a=ap.parse_args();assert a.run.replace('-','').isalnum()
out=BASE/('media-'+a.run);out.mkdir(exist_ok=False);(out/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
record=json.loads((BASE/'case-complete-r1/verification.json').read_bytes());assert record['status']=='passed'
public=Path(record['public']);work=Path(record['project']).parent;os.environ['MPLCONFIGDIR']=str(work/'matplotlib-config')
import numpy as np
import matplotlib;matplotlib.use('Agg')
import matplotlib.pyplot as plt
from PIL import Image,ImageDraw,ImageFont
ff=shutil.which('ffmpeg');assert ff
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def run(name,argv,**kw):
    r=subprocess.run(list(map(str,argv)),capture_output=True,cwd=ROOT,timeout=120,creationflags=subprocess.CREATE_NO_WINDOW,**kw)
    (out/(name+'.stdout.txt')).write_bytes(r.stdout);(out/(name+'.stderr.txt')).write_bytes(r.stderr)
    assert r.returncode==0,(name,r.stderr[-2500:]);return r.stdout
names=['english-clean','english-noisy','english-enhanced'];labels=['CLEAN HUMAN REFERENCE','NOISY INPUT / SNR 0 dB','ACTUAL CUDA ENHANCEMENT']
audio=[np.frombuffer(run('decode-'+name,[ff,'-nostdin','-v','error','-i',public/(name+'.wav'),'-c:a','pcm_f32le','-f','f32le','pipe:1']),'<f4').copy() for name in names]
assert all(len(v)==len(audio[0]) for v in audio);rate=48000;n=len(audio[0]);duration=n/rate
fig,axes=plt.subplots(3,2,figsize=(12,6.5),constrained_layout=True)
for i,(data,label) in enumerate(zip(audio,labels)):
    axes[i,0].plot(np.arange(n)[::48]/rate,data[::48],linewidth=.35);axes[i,0].set_ylim(-.5,.5);axes[i,0].set_title(label,fontsize=10)
    axes[i,0].set_ylabel('Amplitude');axes[i,0].set_xlim(0,duration)
    axes[i,1].specgram(data,NFFT=1024,Fs=rate,noverlap=768,cmap='magma',vmin=-100,vmax=-35)
    axes[i,1].set_ylim(0,8000);axes[i,1].set_ylabel('Frequency / Hz');axes[i,1].set_title('Actual PSD / same scale (-100..-35 dB/Hz)',fontsize=9)
for ax in axes[-1]:ax.set_xlabel('Time / seconds')
fig.suptitle('C53 real LibriSpeech 16k source, upsampled48k; seeded noise; no listening acceptance',fontsize=10)
fig.savefig(public/'spectra-and-waveforms.png',dpi=130);plt.close(fig)
font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',15);small=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',12)
width,height=720,414;left,right=20,700;top=48;row=105;base=Image.new('RGB',(width,height),(19,25,34));draw=ImageDraw.Draw(base)
draw.text((left,10),'C53 / actual waveform preview / select and audition original WAVs',font=font,fill='white')
for i,(data,label) in enumerate(zip(audio,labels)):
    y=top+i*row;draw.text((left,y),label,font=font,fill=(185,221,249));center=y+51
    draw.line((left,center,right,center),fill=(72,80,92))
    for column in range(right-left):
        block=data[int(column*n/(right-left)):max(int((column+1)*n/(right-left)),int(column*n/(right-left))+1)]
        lo,hi=np.clip([block.min(),block.max()],-.5,.5);draw.line((left+column,center-round(hi*65),left+column,center-round(lo*65)),fill=(95,198,191))
draw.text((left,378),'GIF is silent. MP4 audibly plays CLEAN, NOISY, ENHANCED in that order.',font=small,fill=(210,210,210))
draw.text((left,396),'Real English human / Mandarin companion is synthetic. No human listening claimed.',font=small,fill=(210,210,210))
base.save(public/'comparison.png')
gif_count=math.ceil(duration*12);gif=[]
for i in range(gif_count):
    frame=base.copy();d=ImageDraw.Draw(frame);x=left+round((right-left-1)*i/max(1,gif_count-1))
    for r in range(3):d.line((x,top+r*row+23,x,top+r*row+84),fill=(250,206,88),width=2)
    gif.append(frame)
duration_ms=round(duration*100)*10
durations=[round((i+1)*duration_ms/gif_count/10)*10-round(i*duration_ms/gif_count/10)*10 for i in range(gif_count)]
gif[0].save(public/'comparison.gif',save_all=True,append_images=gif[1:],duration=durations,loop=0,optimize=False,disposal=2)
joined=work/'comparison-audio.wav';run('encode-comparison-audio',[ff,'-nostdin','-v','error','-n','-f','f32le','-ar',str(rate),'-ac','1','-i','pipe:0','-c:a','pcm_f32le',joined],input=np.concatenate(audio).astype('<f4').tobytes())
video=public/'audible-comparison.mp4';argv=[ff,'-nostdin','-v','error','-n','-f','rawvideo','-pix_fmt','rgb24','-video_size',f'{width}x{height}',
    '-framerate','12','-i','pipe:0','-i',str(joined),'-map','0:v','-map','1:a','-c:v','libx264','-crf','20','-pix_fmt','yuv420p','-c:a','aac','-b:a','160k','-movflags','+faststart',str(video)]
with (out/'comparison-encode.stderr.txt').open('wb') as log:
    p=subprocess.Popen(argv,stdin=subprocess.PIPE,stdout=subprocess.DEVNULL,stderr=log,creationflags=subprocess.CREATE_NO_WINDOW)
    try:
        for i in range(math.ceil(3*duration*12)):
            t=i/12;active=min(2,int(t/duration));fraction=(t-active*duration)/duration;frame=base.copy();d=ImageDraw.Draw(frame)
            d.rectangle((left-5,top+active*row-3,right+5,top+active*row+88),outline=(255,208,76),width=2)
            x=left+round((right-left-1)*fraction);d.line((x,top+active*row+23,x,top+active*row+84),fill=(255,208,76),width=2)
            p.stdin.write(frame.tobytes())
        p.stdin.close();assert p.wait(timeout=120)==0
    finally:
        if p.poll()is None:p.kill();p.wait(timeout=10)
        if not p.stdin.closed:p.stdin.close()
recipes={k:record[k]['asset']['source']['speech_enhancement'] for k in ('english_result','chinese_result')}
(public/'recipes.json').write_text(json.dumps(recipes,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
files=[]
for path in sorted(public.iterdir()):
    if not path.is_file() or path.name=='media-manifest.json':continue
    v=dict(path=path.name,bytes=path.stat().st_size,sha256=sha(path))
    if path.suffix.lower() in ('.wav','.mp4','.flac'):
        v['probe']=json.loads(run('probe-'+path.stem,['ffprobe','-v','error','-show_streams','-show_format','-of','json',path]))
    if path.suffix=='.gif':
        with Image.open(path) as g:v.update(frames=g.n_frames,duration_ms=sum((g.seek(i),g.info.get('duration',0))[1] for i in range(g.n_frames)))
        assert abs(v['duration_ms']/1000-duration)<=.005
    files.append(v)
(public/'media-manifest.json').write_text(json.dumps(dict(case='C53',human_listening=False,continuous_playback=False,files=files),ensure_ascii=False,indent=2)+'\n',encoding='utf8')
report=dict(status='actual-audio-previews-created',human_listening=False,continuous_playback=False,synthetic_result=False,English_samples=n,
    native_rate=rate,English_duration_seconds=duration,GIF_frames=gif_count,GIF_duration_ms=duration_ms,
    comparison_order=names,MP4_audio_codec='AAC160k_lossy_preview_originals_are_Float32WAV',scientific_plot='matplotlib_Agg_specgram_actual_PCM',
    files=[dict(path=p.relative_to(ROOT).as_posix(),bytes=p.stat().st_size,sha256=sha(p)) for p in public.iterdir() if p.name in ('comparison.gif','comparison.png','spectra-and-waveforms.png','audible-comparison.mp4','media-manifest.json','recipes.json')])
(out/'verification.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8');print(json.dumps(report),flush=True)
