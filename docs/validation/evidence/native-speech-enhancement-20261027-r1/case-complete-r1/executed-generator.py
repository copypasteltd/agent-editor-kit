"""Continue measured C53 after the documented audio-only video-render rejection."""
from pathlib import Path
from datetime import datetime,timezone
import argparse,hashlib,json,shutil,subprocess,time
import numpy as np
from PIL import Image,ImageDraw,ImageFont
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'docs/validation/evidence/native-speech-enhancement-20261027-r1'
ap=argparse.ArgumentParser();ap.add_argument('--run',required=True);a=ap.parse_args();assert a.run.replace('-','').isalnum()
out=BASE/('case-complete-'+a.run);out.mkdir(exist_ok=False);(out/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
prior=json.loads((BASE/'case-r2/verification.json').read_bytes());assert prior['status']=='failed' and 'VIDEO_TRACK_EMPTY' in prior['error']
assert all(c['ok'] for c in prior['checks']) and prior['calls'][-1]['name']=='render' and prior['calls'][-1]['exit_code']==2
work=ROOT/'local/agent-ffmpeg/native-speech-enhancement-case-r2';project=work/'可编辑 对白增强工程';public=ROOT/'docs/assets/native-speech-enhancement-20261027-r2'
ff=shutil.which('ffmpeg');prefix=['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File','C:/Users/carzy/.codex/skills/agent-ffmpeg-local-editor/scripts/run.ps1']
record={k:v for k,v in prior.items() if k not in ('error','calls','checks')};record.update(status='running',prior_attempt='case-r2',prior_attempt_retained_status='failed-VIDEO_TRACK_EMPTY',checks=[],calls=[])
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save():(out/'verification.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
def check(name,ok):record['checks'].append(dict(name=name,ok=bool(ok)));save();assert ok,name
def run(name,argv,*,binary=False):
    started=time.monotonic();r=subprocess.run(list(map(str,argv)),capture_output=True,cwd=ROOT,timeout=900,creationflags=subprocess.CREATE_NO_WINDOW)
    stdout=(work if binary else out)/(name+('.bin' if binary else '.stdout.json'));stderr=out/(name+'.stderr.txt');stdout.write_bytes(r.stdout);stderr.write_bytes(r.stderr)
    record['calls'].append(dict(name=name,command=list(map(str,argv)),exit_code=r.returncode,seconds=time.monotonic()-started,stdout_sha256=sha(stdout),stderr_sha256=sha(stderr)));save()
    print(json.dumps(dict(name=name,exit_code=r.returncode)),flush=True);assert r.returncode==0,(name,r.stdout[-3000:],r.stderr[-1200:]);return r.stdout
def cli(name,*argv):
    v=json.loads(run(name,[*prefix,*argv]));check(name+' installed CLI0.1.43',v['ok'] and v['provenance']['cli_version']=='0.1.43');return v['data']
def pcm(name,path):return run(name,[ff,'-nostdin','-v','error','-i',path,'-vn','-c:a','pcm_f32le','-f','f32le','pipe:1'],binary=True)
try:
    p=json.loads((project/'project.json').read_bytes());english=json.loads((BASE/'case-r2/english-enhance.stdout.json').read_bytes())['data']
    chinese=json.loads((BASE/'case-r2/chinese-enhance.stdout.json').read_bytes())['data'];ids={}
    for name in ('english-clean','english-noisy','chinese-clean','chinese-noisy','english-reverb-noisy'):
        ids[name]=json.loads((BASE/('case-r2/ingest-'+name+'.stdout.json')).read_bytes())['data']['asset']['id']
    check('retained actual master assets still match recorded output bytes',all(sha(project/r['asset']['uri'])==r['asset']['sha256'].removeprefix('sha256:') for r in (english,chinese)))
    wave=np.fromfile(work/'decode-english-enhanced.bin',dtype='<f4');card=Image.new('RGB',(640,360),(19,25,34));draw=ImageDraw.Draw(card)
    draw.text((18,20),'C53 / actual native CUDA speech enhancement',font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',20),fill='white')
    draw.text((18,54),'Enhanced speech waveform / original remains in project',font=ImageFont.truetype('C:/Windows/Fonts/arial.ttf',16),fill=(185,221,249))
    for x in range(600):
        b=wave[x*len(wave)//600:max((x+1)*len(wave)//600,x*len(wave)//600+1)]
        draw.line((x+20,210-round(float(b.max())*190),x+20,210-round(float(b.min())*190)),fill=(95,198,191))
    card.save(public/'timeline-waveform.png')
    asset=cli('waveform-ingest','media','ingest','--project',project,'--input',public/'timeline-waveform.png','--license-spdx','CC0-1.0','--evidence',public/'SOURCE.txt')['asset']['id']
    ticks=p['sequences'][0]['duration_tick'];request=work/'waveform-compose.json';request.write_text(json.dumps(dict(operations=[dict(op='append_clip',track_id='track_video_1',asset_id=asset,
        source_in_tick=0,source_out_tick=ticks,duration_tick=ticks,timeline_start_tick=0)]))+'\n',encoding='utf8')
    cli('waveform-compose','timeline','compose','--project',project,'--input',request);cli('validate','validate','--project',project)
    rendered=project/'renders/enhanced-with-waveform.mp4';cli('render','render','--project',project,'--output',rendered)
    package=cli('package','convert','export','--project',project,'--target-format','package','--output',project/'exports/enhanced.aevpkg.zip')['output']
    restored=work/'restored';cli('restore','convert','import','--input',package,'--output',restored)
    rp=json.loads((restored/'project.json').read_bytes());original=json.loads((project/'project.json').read_bytes())
    check('package every original enhanced asset byte and recipe retained',all(sha(restored/v['uri'])==sha(project/v['uri']) and
        v.get('source',{}).get('speech_enhancement')==next(z for z in original['assets'] if z['id']==v['id']).get('source',{}).get('speech_enhancement') for v in rp['assets']))
    restored_render=restored/'renders/restored.mp4';cli('restored-render','render','--project',restored,'--output',restored_render)
    check('complete package rendered decoded PCM identical',pcm('original-render-pcm',rendered)==pcm('restored-render-pcm',restored_render))
    shutil.copy2(package,public/'editable-enhancement.aevpkg.zip')
    record.update(status='passed',finished_at_utc=datetime.now(timezone.utc).isoformat(),project=str(project),public=str(public),source_ids=ids,
        english_result=english,chinese_result=chinese,English_model_calls=english['generation']['worker']['metrics']['model_calls'],
        Chinese_model_calls=chinese['generation']['worker']['metrics']['model_calls'],human_input_rate=16000,english_working_rate=48000,
        chinese_source_rate=24000,chinese_native_rate=44100,retained_prior_checks=prior['checks'],
        public_files=[dict(path=p.relative_to(ROOT).as_posix(),bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(public.iterdir()) if p.is_file()])
    save();print(json.dumps(dict(status='passed',quality=record['quality'],English_model_calls=record['English_model_calls'],Chinese_model_calls=record['Chinese_model_calls'])),flush=True)
except BaseException as exc:record.update(status='failed',error=repr(exc));save();raise
