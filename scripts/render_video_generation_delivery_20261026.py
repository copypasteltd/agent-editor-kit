"""Render all four real generated clips through the registered Skill twice."""
import argparse
from datetime import datetime, timezone
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import subprocess

import numpy as np
from PIL import Image, ImageSequence

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/validation/evidence/video-generation-20261026-r1'


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--run',required=True);a=ap.parse_args();assert a.run.replace('-','').isalnum()
    out=BASE/('render-roundtrip-'+a.run);out.mkdir(exist_ok=False)
    (out/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    case=json.loads((BASE/'case-r1/verification.json').read_bytes());assert case['status']=='passed_actual_four_mode_cuda_transport_and_editable_package'
    project=Path(case['project']);imported=project.parent/'重新 导入工程'
    prefix=['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',
        'C:/Users/carzy/.codex/skills/agent-ffmpeg-local-editor/scripts/run.ps1']
    record=dict(status='running',at_utc=datetime.now(timezone.utc).isoformat(),registered_skill=True,
        source_fallback=False,new_model_windows=0,model_audio_generated=False,source_outputs_silent=True,natural_quality_accepted=False,
        model_output_publication_accepted=False,continuous_playback=False,human_listening=False,calls=[])
    def save():(out/'verification.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    def run(name,argv,*,binary=False):
        value=subprocess.run(list(map(str,argv)),cwd=ROOT,capture_output=True,timeout=900,creationflags=subprocess.CREATE_NO_WINDOW)
        destination=(project.parent if binary else out)/(name+('.bin' if binary else '.stdout.log'))
        error=out/(name+'.stderr.log');destination.write_bytes(value.stdout);error.write_bytes(value.stderr)
        record['calls'].append(dict(name=name,argv=list(map(str,argv)),exit_code=value.returncode,
            stdout=str(destination),stdout_sha256=sha(destination),stderr_sha256=sha(error)))
        save();print(json.dumps(dict(name=name,exit_code=value.returncode)),flush=True)
        assert value.returncode==0,(name,value.stdout[-2000:],value.stderr[-2000:]);return value.stdout
    def cli(name,*argv):
        value=json.loads(run(name,[*prefix,*argv]));assert value['ok'];return value
    try:
        assert cli('version','version')['data']['cli_version']=='0.1.33'
        author=json.loads((project/'project.json').read_bytes());clock=author['settings']['timebase']
        fps=Fraction(clock['display_fps']['num'],clock['display_fps']['den'])
        sequence=author['sequences'][0];duration=Fraction(sequence['duration_tick'],clock['ticks_per_second'])
        expected=(duration*fps).__ceil__();assert fps==30 and duration==Fraction(17*4,12) and expected==170
        record.update(author_display_fps=str(fps),author_duration=str(duration),expected_frames=expected)
        hashes=[];outputs=[]
        for label,root in [('original',project),('imported',imported)]:
            movie=root/'renders/combined-generated.mp4'
            cli(label+'-render','render','--project',root,'--output',movie,'--hardware-encode','off')
            cli(label+'-quality','quality','check','--project',root,'--input',movie)
            probe=json.loads(run(label+'-probe',['ffprobe','-v','error','-count_frames','-show_streams','-of','json',movie]))
            video=next(stream for stream in probe['streams'] if stream['codec_type']=='video')
            assert video['width']==256 and video['height']==144 and Fraction(video['avg_frame_rate'])==30
            assert int(video['nb_read_frames'])==expected
            digest=run(label+'-framemd5',['ffmpeg','-nostdin','-v','error','-i',movie,'-map','0:v:0','-an','-pix_fmt','rgba','-f','framemd5','pipe:1'])
            frames=[line for line in digest.decode('ascii').splitlines() if line and not line.startswith('#')]
            assert len(frames)==expected
            hashes.append(frames);outputs.append(dict(path=str(movie),sha256=sha(movie),decoded_frames=len(frames),
                video_fps=video['avg_frame_rate'],width=video['width'],height=video['height'],
                audio_streams=[dict(codec=stream['codec_name'],sample_rate=stream.get('sample_rate'),channels=stream.get('channels'))
                    for stream in probe['streams'] if stream['codec_type']=='audio']))
        assert hashes[0]==hashes[1]
        raw=run('original-rgb',['ffmpeg','-nostdin','-v','error','-i',outputs[0]['path'],'-an','-pix_fmt','rgb24','-f','rawvideo','pipe:1'],binary=True)
        pixels=np.frombuffer(raw,np.uint8).reshape(170,144,256,3)
        indices=list(range(0,170,3));frames=[Image.fromarray(pixels[i]) for i in indices]
        delays=[round((min(index+3,170)/30*100))-round(index/30*100) for index in indices]
        delays=[delay*10 for delay in delays];gif=project.parent/'combined-generated.gif'
        frames[0].save(gif,save_all=True,append_images=frames[1:],duration=delays,loop=0,disposal=2)
        with Image.open(gif) as image:actual_delays=[frame.info.get('duration',0) for frame in ImageSequence.Iterator(image)]
        assert abs(sum(actual_delays)-float(duration)*1000)<=10
        record.update(status='passed',outputs=outputs,decoded_equal_frames=170,
            source_native_frames=68,source_native_fps='12',combined_display_fps='30',
            gif=str(gif),gif_sha256=sha(gif),gif_frames=len(actual_delays),gif_duration_ms=sum(actual_delays),
            gif_frame_delays_ms=actual_delays,source_and_imported_pixels_equal=True);save()
    except BaseException as exc:record.update(status='failed',error=repr(exc));save();raise


if __name__=='__main__':main()
