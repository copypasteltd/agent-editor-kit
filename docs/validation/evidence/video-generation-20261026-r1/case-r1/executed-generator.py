"""C43: actual installed VACE CUDA generation, four modes and editable delivery.

Model outputs stay in the ignored local workspace while publication rights and
natural quality remain unaccepted. Only self-authored CC0 conditions are copied
into public documentation; synthetic protocol workers are never used here.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import time

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT/'docs/validation/evidence/video-generation-20261026-r1'
INSTALL = ROOT/'local/agent-ffmpeg/v0.1.0-alpha.4-local.31/final-r1/installed'
PYTHON = 'C:/Python313/python.exe'


def sha(path):
    with Path(path).open('rb') as stream: return hashlib.file_digest(stream,'sha256').hexdigest()


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--run',required=True); args = parser.parse_args()
    assert args.run.replace('-','').isalnum()
    out = BASE/('case-'+args.run); out.mkdir(exist_ok=False)
    work = ROOT/'workspace'/('video-generation-20261026-'+args.run); work.mkdir(exist_ok=False)
    public = ROOT/'docs/assets'/('video-generation-20261026-'+args.run); public.mkdir(exist_ok=False)
    (out/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    prefix = [PYTHON,'-I','-S','-B','-u','-X','utf8',str(INSTALL/'run.py')]
    record = dict(status='running',started_at_utc=datetime.now(timezone.utc).isoformat(),cli_version='0.1.33',
        installed=str(INSTALL),source_fallback=False,native_windows=True,virtualization=False,
        synthetic_worker=False,models_downloaded=False,other_user_processes_modified=False,
        natural_quality_accepted=False,model_output_publication_accepted=False,
        continuous_playback=False,human_listening=False,audio_generated=False,calls=[],checks=[],modes=[])
    def save(): (out/'verification.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    def check(name,value):
        record['checks'].append(dict(name=name,ok=bool(value))); save(); assert value,name
    def run(name,argv,*,code=0,binary=False,timeout=3600):
        start = time.monotonic(); argv = list(map(str,argv))
        result = subprocess.run(argv,cwd=ROOT,capture_output=True,timeout=timeout,creationflags=subprocess.CREATE_NO_WINDOW)
        stdout = (work if binary else out)/(name+('.bin' if binary else '.stdout.json'))
        stderr = out/(name+'.stderr.log'); stdout.write_bytes(result.stdout); stderr.write_bytes(result.stderr)
        record['calls'].append(dict(name=name,argv=argv,exit_code=result.returncode,expected_exit_code=code,
            stdout_sha256=sha(stdout),stderr_sha256=sha(stderr),seconds=time.monotonic()-start))
        save(); print(json.dumps(dict(name=name,exit_code=result.returncode,seconds=time.monotonic()-start)),flush=True)
        assert result.returncode == code,(name,result.stdout[-3000:],result.stderr[-3000:])
        return result.stdout
    def cli(name,*argv,code=0):
        value = json.loads(run(name,[*prefix,*argv],code=code)); assert value['ok']==(code==0),value
        return value
    def image(path,offset):
        pixels = np.zeros((144,256,3),np.uint8)
        y,x = np.indices((144,256)); pixels[:,:,0]=np.clip(24+y*.18,0,255)
        pixels[:,:,1]=np.clip(42+y*.22,0,255); pixels[:,:,2]=np.clip(68+y*.24,0,255)
        frame=Image.fromarray(pixels); draw=ImageDraw.Draw(frame)
        draw.rectangle((0,103,255,143),fill=(48,65,83)); cx=100+offset
        draw.ellipse((cx-43,112,cx+43,126),fill=(25,31,42))
        draw.rounded_rectangle((cx-23,48,cx+23,118),radius=8,fill=(167,93,29),outline=(225,172,77),width=2)
        draw.rectangle((cx-13,32,cx+13,51),fill=(22,22,26)); draw.rectangle((cx-17,29,cx+17,37),fill=(40,40,44))
        draw.rounded_rectangle((cx-17,71,cx+17,95),radius=2,fill=(220,211,184))
        draw.line((cx-16,58,cx-16,101),fill=(240,178,84),width=3)
        frame.save(path)
    try:
        frozen={p.name:sha(p) for p in (ROOT/'product/src/ai_ad_editor').glob('*.py')}
        check('227 installed product files equal frozen source',len(frozen)==227 and all(sha(INSTALL/'site/ai_ad_editor'/n)==s for n,s in frozen.items()))
        check('installed version',cli('version','version')['data']['cli_version']=='0.1.33')
        run('gpu-before',['nvidia-smi','--query-gpu=name,uuid,memory.total,memory.free','--format=csv,noheader'])
        project=work/'可编辑 生成工程'; cli('init','project','init',project)
        author=json.loads((project/'project.json').read_bytes()); author['settings']['canvas'].update(width=256,height=144,fps={'num':12,'den':1})
        (project/'project.json').write_text(json.dumps(author,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
        proof = work/'condition-evidence.txt'
        proof.write_text('C43 geometric bottle conditions drawn by this script. Original work dedicated to CC0-1.0. No third-party images, brands, voices or music.\n',encoding='utf8')
        images={}
        for name,offset in [('first',0),('last',40)]:
            path=public/(name+'.png'); image(path,offset)
            value=cli('ingest-'+name,'media','ingest','--project',project,'--input',path,'--license-spdx','CC0-1.0',
                '--verification-status','verified','--permitted-use','internal','--permitted-use','commercial_ad','--evidence',proof)
            images[name]=value['data']['asset']['id']
        old=json.loads((ROOT/'workspace/vace-smoke-20261016-controlled-v2/summary.json').read_bytes())['adapter']
        adapter=cli('register-vace','media','adapter','register','--project',project,'--adapter-id','vace_generation',
            '--engine',old['engine'],'--model-path',old['model_path'],'--executable',old['executable'],
            '--evidence',next(a['path'] for a in old['artifacts'] if a['role']=='evidence'),'--device','cuda',
            '--license-spdx','Apache-2.0','--verification-status','unverified','--permitted-use','internal')['data']['adapter']
        record['model_adapter']=adapter; save()
        modes={'text-to-video':(), 'image-to-video':('first',), 'last-frame-to-video':('last',), 'first-last-to-video':('first','last')}
        prompt='An amber glass perfume bottle with a black cap stands on a blue tabletop in a quiet studio. Soft side lighting, realistic glass reflections. A slow smooth camera move to the right. The bottle remains upright. No text, no people.'
        for index,(mode,names) in enumerate(modes.items()):
            command=['media','generate','--project',project,'--adapter-id','vace_generation','--asset-id',mode,
                '--mode',mode,'--width','256','--height','144','--frames','17','--fps','12','--image-fit','reject',
                '--prompt',prompt,'--negative-prompt','watermark, text, people, distorted objects, jitter',
                '--seed',str(230+index),'--inference-steps','18','--guidance-scale','5','--flow-shift','3',
                '--window-frames','17','--window-overlap','4','--apply','--track-id','track_video_1',
                '--timeline-start-seconds',str(float(Fraction(index*17,12))),'--timeout-seconds','1800']
            for name in names: command+=['--'+name+'-asset-id',images[name]]
            before=(project/'project.json').read_bytes(); cli(mode+'-plan',*command,'--dry-run')
            check(mode+' dry-run keeps project bytes',(project/'project.json').read_bytes()==before)
            value=cli(mode+'-actual',*command)['data']; result=value['generation']['result']; worker=result['worker']
            movie=project/value['asset']['uri']; raw=run(mode+'-decode',['ffmpeg','-nostdin','-v','error','-i',movie,
                '-an','-pix_fmt','rgba','-fps_mode','passthrough','-f','rawvideo','pipe:1'],binary=True)
            frames=np.frombuffer(raw,np.uint8).reshape(17,144,256,4)
            check(mode+' all 17 RGBA frames decode and match worker SHA','sha256:'+hashlib.sha256(raw).hexdigest()==worker['metrics']['rgba_sha256'])
            check(mode+' actual CUDA provider, model and one window',worker['model_loaded'] is True and worker['providers']==['torch-cuda'] and worker['metrics']['model_calls']==1 and worker['model_execution']['window_input_shapes']==[[17,144,256]])
            check(mode+' no audio and endpoints independently verified',not any(s['codec_type']=='audio' for s in value['asset']['probe']['streams']) and set(value['generation']['endpoint_checks'])==set(names) and all(r['equal'] for r in value['generation']['endpoint_checks'].values()))
            local=work/(mode+'.mp4'); run(mode+'-preview',['ffmpeg','-nostdin','-v','error','-n','-i',movie,'-an','-c:v','libx264','-crf','18','-pix_fmt','yuv420p','-movflags','+faststart',local])
            views=[Image.fromarray(f[:,:,:3]) for f in frames]
            durations=[round((i+1)*1000/12)-round(i*1000/12) for i in range(17)]
            # GIF duration is quantized to 10ms, distributed to preserve the nearest total.
            gif_durations=[(round((i+1)*100/12)-round(i*100/12))*10 for i in range(17)]
            views[0].save(work/(mode+'.gif'),save_all=True,append_images=views[1:],duration=gif_durations,loop=0,disposal=2)
            contact=Image.new('RGB',(256*3,144));
            for col,number in enumerate((0,8,16)): contact.paste(views[number],(col*256,0))
            contact.save(work/(mode+'-frames.png'))
            record['modes'].append(dict(mode=mode,output=str(movie),output_sha256=sha(movie),preview=str(local),
                gif=str(work/(mode+'.gif')),contact=str(work/(mode+'-frames.png')),frames=17,fps='12',duration_seconds=17/12,
                raw_rgba_sha256=hashlib.sha256(raw).hexdigest(),elapsed_seconds=value['generation']['elapsed_seconds'],
                generated_quality_accepted=False,rights_status=value['rights']['verification_status'],
                endpoint_checks=value['generation']['endpoint_checks'],model_execution=worker['model_execution']))
            save()
        cli('validate','validate','--project',project)
        cli('rights-expected-reject','rights','check','--project',project,code=7)
        package=work/'editable-generated-videos.aevpkg.zip'; cli('export-package','convert','export','--project',project,'--target-format','package','--output',package)
        imported=work/'重新 导入工程'; cli('import-package','convert','import','--input',package,'--output',imported)
        cli('validate-imported','validate','--project',imported)
        original=json.loads((project/'project.json').read_bytes()); roundtrip=json.loads((imported/'project.json').read_bytes())
        check('portable recipes survive complete project package',[(a['id'],a.get('source',{}).get('video_generation')) for a in original['assets']]==[(a['id'],a.get('source',{}).get('video_generation')) for a in roundtrip['assets']])
        check('managed job directories cleaned',not list((project/'cache/managed-jobs').glob('job-*')))
        check('product source and installation remain byte equal',frozen=={p.name:sha(p) for p in (ROOT/'product/src/ai_ad_editor').glob('*.py')} and all(sha(INSTALL/'site/ai_ad_editor'/n)==s for n,s in frozen.items()))
        run('gpu-after',['nvidia-smi','--query-gpu=name,uuid,memory.total,memory.free','--format=csv,noheader'])
        board=Image.new('RGB',(512,172),(14,18,26)); board.paste(Image.open(public/'first.png'),(0,0)); board.paste(Image.open(public/'last.png'),(256,0))
        draw=ImageDraw.Draw(board);draw.text((12,149),'CC0 FIRST CONDITION',fill='white');draw.text((268,149),'CC0 LAST CONDITION',fill='white');board.save(public/'conditions.png')
        (public/'SOURCE.txt').write_bytes(proof.read_bytes())
        (public/'PUBLICATION_SCOPE.txt').write_text('Only original CC0 first/last conditions are public here. Actual model-generated videos, GIFs and editable package remain in the ignored local workspace; their publication rights and natural quality are unaccepted. See C43 evidence for exact local paths and hashes.\n',encoding='utf8')
        record.update(status='passed_actual_four_mode_cuda_transport_and_editable_package',project=str(project),package=str(package),
            package_sha256=sha(package),new_model_forwards=4,finished_at_utc=datetime.now(timezone.utc).isoformat())
        save()
    except BaseException as exc:
        record.update(status='failed',error=repr(exc),finished_at_utc=datetime.now(timezone.utc).isoformat());save();raise


if __name__=='__main__': main()
