"""Rebuild a labelled GIF from the two actual, unmodified Windows outputs."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys


def digest(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream,'sha256').hexdigest()


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--ffmpeg',type=Path,required=True)
    parser.add_argument('--pillow-site',type=Path)
    args=parser.parse_args()
    if args.pillow_site:
        sys.path.insert(0,str(args.pillow_site.resolve()))
    from PIL import Image,ImageDraw,ImageFont
    root=Path(__file__).resolve().parent
    movies=[root/'primary.mp4',root/'second-host.mp4']
    frames=[]
    for movie in movies:
        value=subprocess.run([str(args.ffmpeg),'-nostdin','-v','error','-i',str(movie),'-an',
            '-vf','fps=10,format=rgb24','-f','rawvideo','pipe:1'],check=True,capture_output=True)
        stride=320*180*3
        assert len(value.stdout)==20*stride
        frames.append([Image.frombytes('RGB',(320,180),value.stdout[i*stride:(i+1)*stride]) for i in range(20)])
    font=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',16)
    small=ImageFont.truetype('C:/Windows/Fonts/msyh.ttc',13)
    output=[]
    for index in range(20):
        image=Image.new('RGB',(640,252),'#f6f3eb')
        draw=ImageDraw.Draw(image)
        draw.text((12,10),'本机 Windows / Primary',font=font,fill='#18382a')
        draw.text((332,10),'第二台 Windows / Second host',font=font,fill='#18382a')
        image.paste(frames[0][index],(0,40));image.paste(frames[1][index],(320,40))
        draw.text((12,230),'实际输出 · CPU · CLI 0.1.63 · 完整画面与音频校验一致',font=small,fill='#18382a')
        output.append(image)
    output[0].save(root/'comparison.png')
    output[0].save(root/'comparison.gif',save_all=True,append_images=output[1:],duration=100,loop=0,optimize=False)
    with Image.open(root/'comparison.gif') as gif:
        durations=[]
        for index in range(gif.n_frames):
            gif.seek(index);durations.append(gif.info['duration'])
        actual=dict(frames=gif.n_frames,width=gif.width,height=gif.height,duration_ms=sum(durations))
    paths=[*movies,root/'comparison.gif',root/'comparison.png',root/'build_preview.py',root/'input-pattern.mp4',root/'input-tone.wav']
    value=dict(format='actual-cross-machine-baseline-preview-v1',cli_version='0.1.63',
        source='procedural FFmpeg testsrc2 video and 440Hz sine; no model inference',
        actual_movie_video=dict(frames=60,width=320,height=180,fps='30/1',duration_seconds=2),
        audio=dict(sample_rate=48000,channels=2,decoded_samples_per_channel=96256,
                   decoded_tail='AAC decoding includes 256 tail samples; complete decoded PCM was compared'),
        gif=actual,preview_only=True,natural_quality_accepted=False,human_listening=False,
        model_inference=False,gpu_render=False,cli66_accepted=False,
        files=[dict(path=p.name,bytes=p.stat().st_size,sha256=digest(p)) for p in paths])
    with (root/'metadata.json').open('x',encoding='utf-8',newline='\n') as stream:
        json.dump(value,stream,ensure_ascii=False,indent=2);stream.write('\n')
    print(json.dumps(dict(status='actual-output-preview-built',gif=actual),ensure_ascii=False))


if __name__=='__main__':
    main()
