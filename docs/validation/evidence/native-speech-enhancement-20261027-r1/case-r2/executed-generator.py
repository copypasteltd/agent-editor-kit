"""C53: registered installed CUDA denoising, real speech, clocks and portable edits."""
from pathlib import Path
from datetime import datetime, timezone
import argparse, hashlib, json, shutil, subprocess, time
import numpy as np

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/validation/evidence/native-speech-enhancement-20261027-r1'
ap=argparse.ArgumentParser();ap.add_argument('--run',required=True);a=ap.parse_args()
assert a.run.replace('-','').isalnum()
out=BASE/('case-'+a.run);out.mkdir(exist_ok=False)
(out/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
work=ROOT/'local/agent-ffmpeg'/('native-speech-enhancement-case-'+a.run);work.mkdir(exist_ok=False)
public=ROOT/'docs/assets'/('native-speech-enhancement-20261027-'+a.run);public.mkdir(exist_ok=False)
ff=shutil.which('ffmpeg');assert ff
prefix=['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',
        'C:/Users/carzy/.codex/skills/agent-ffmpeg-local-editor/scripts/run.ps1']
record=dict(status='running',started_at_utc=datetime.now(timezone.utc).isoformat(),registered_installed_skill=True,
    source_fallback=False,native_windows=True,virtualization=False,fake_worker=False,human_listening=False,
    continuous_playback=False,natural_quality_accepted=False,calls=[],checks=[],quality={})
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save():(out/'verification.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
def check(name,ok):
    record['checks'].append(dict(name=name,ok=bool(ok)));save();assert ok,name
def run(name,argv,*,binary=False,input=None,code=0,timeout=1200):
    started=time.monotonic();argv=list(map(str,argv))
    r=subprocess.run(argv,input=input,capture_output=True,cwd=ROOT,timeout=timeout,creationflags=subprocess.CREATE_NO_WINDOW)
    stdout=(work if binary else out)/(name+('.bin' if binary else '.stdout.json'));stderr=out/(name+'.stderr.txt')
    stdout.write_bytes(r.stdout);stderr.write_bytes(r.stderr)
    record['calls'].append(dict(name=name,command=argv,exit_code=r.returncode,seconds=time.monotonic()-started,
        stdout_sha256=sha(stdout),stderr_sha256=sha(stderr)));save()
    print(json.dumps(dict(name=name,exit_code=r.returncode,seconds=time.monotonic()-started)),flush=True)
    assert r.returncode==code,(name,r.stdout[-3000:],r.stderr[-1200:]);return r.stdout
def cli(name,*argv):
    v=json.loads(run(name,[*prefix,*argv]));check(name+' registered CLI0.1.43',v['ok'] and v['provenance']['cli_version']=='0.1.43');return v['data']
def pcm(name,path,rate=None,channels=None):
    argv=[ff,'-nostdin','-v','error','-i',path,'-vn']
    if rate:argv+=['-ar',str(rate)]
    if channels:argv+=['-ac',str(channels)]
    return run(name,[*argv,'-c:a','pcm_f32le','-f','f32le','pipe:1'],binary=True)
def wav(name,data,rate,path):
    if data.ndim==1:data=data[:,None]
    run(name,[ff,'-nostdin','-v','error','-n','-f','f32le','-ar',str(rate),'-ac',str(data.shape[1]),'-i','pipe:0',
        '-map_metadata','-1','-c:a','pcm_f32le',path],input=data.astype('<f4').tobytes())
def stats(reference,estimate):
    x=np.asarray(reference,dtype=np.float64).reshape(-1);y=np.asarray(estimate,dtype=np.float64).reshape(-1);assert x.shape==y.shape
    error=np.square(y-x).mean();alpha=np.dot(x,y)/(np.dot(x,x)+1e-30);target=x*alpha
    return dict(samples_per_channel=reference.shape[0],channels=1 if reference.ndim==1 else reference.shape[1],
        MSE=float(error),SNR_dB=float(10*np.log10((np.square(x).mean()+1e-30)/(error+1e-30))),
        SI_SDR_dB=float(10*np.log10((np.square(target).sum()+1e-30)/(np.square(y-target).sum()+1e-30))),
        fitted_gain=float(alpha),peak=float(np.abs(y).max()),RMS=float(np.sqrt(np.square(y).mean())),quality_pass_threshold=None)
def mixture(clean,rate,seed):
    rng=np.random.default_rng(seed);white=rng.standard_normal(clean.shape);t=np.arange(len(clean))/rate
    hum=(np.sin(2*np.pi*60*t)+.35*np.sin(2*np.pi*180*t))[:,None]
    n=.8*white+.6*hum;n*=np.sqrt(np.square(clean,dtype=np.float64).mean()/np.square(n).mean())
    return (clean+n).astype('float32')
try:
    cli('version','version');project=work/'可编辑 对白增强工程';cli('init','project','init',project)
    p=json.loads((project/'project.json').read_bytes());p['settings']['canvas'].update(width=320,height=180,fps=dict(num=24,den=1))
    (project/'project.json').write_text(json.dumps(p,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    model=ROOT/'product/.runtime/models/deepfilternet3-20261027'
    shutil.copy2(model/'reference/1272-128104-0000.flac',public/'original-human-16k.flac')
    human=np.frombuffer(pcm('decode-human',public/'original-human-16k.flac',48000,1),'<f4').reshape(-1,1).copy()
    chinese=np.frombuffer(pcm('decode-chinese',ROOT/'docs/assets/native-lipsync-20261027-r1/speech.wav',44100,1),'<f4').reshape(-1,1).copy()
    chinese=np.concatenate((chinese,chinese*.83),axis=1)
    noisy=mixture(human,48000,20261027);zh_noisy=mixture(chinese,44100,20261028)
    reverb=human.copy()
    for seconds,gain in ((.04,.5),(.11,.4),(.24,.2)):
        n=round(seconds*48000);reverb[n:]+=human[:-n]*gain
    reverb_noisy=mixture(reverb,48000,20261029)
    proof=public/'SOURCE.txt';proof.write_text('C53 original English human speech: LibriSpeech dev-clean/1272/128104/1272-128104-0000, LibriSpeech/LibriVox contributors; corpus by Vassil Panayotov et al. CC BY4.0 https://creativecommons.org/licenses/by/4.0/ ; primary dataset license https://www.openslr.org/12 ; downloaded official Qwen2-Audio sample https://qianwen-res.oss-cn-beijing.aliyuncs.com/Qwen2-Audio/audio/1272-128104-0000.flac listed at https://github.com/QwenLM/Qwen2-Audio . Original16kHz speech is explicitly upsampled to48kHz, not a true full-band recording. Transcript: MISTER QUILTER IS THE APOSTLE OF THE MIDDLE CLASSES AND WE ARE GLAD TO WELCOME HIS GOSPEL.\nChinese source is synthetic local CUDA Kokoro zf_001 speech from ../native-lipsync-20261027-r1/speech.wav; provenance/model terms in that case SOURCE.txt.24kHz source explicitly resampled44.1kHz and duplicated with right-channel gain0.83; it is not real stereo capture or human speech.\nSeeded Gaussian plus60/180Hz hum, known dry speech power gives0dB inputSNR. Reverberation diagnostic is three discrete original delays40/110/240ms with gains0.5/0.4/0.2, not a measured room or broad benchmark. All transformations/enhancement/comparison/diagnostic artwork by agent editor kit; original diagnostic noise/artwork CC0. Actual neural model DeepFilterNet3 fixed133tensor checkpoint, MIT OR Apache2.0; official https://github.com/Rikorose/DeepFilterNet ; model execution CUDA, frontend CPU. Generated noise suppression is not endorsed by source contributors. No human listening acceptance claimed.\n',encoding='utf8')
    fixtures={'english-clean':(human,48000),'english-noisy':(noisy,48000),'chinese-clean':(chinese,44100),
              'chinese-noisy':(zh_noisy,44100),'english-reverb-noisy':(reverb_noisy,48000)}
    ids={}
    for name,(data,rate) in fixtures.items():
        path=public/(name+'.wav');wav('encode-'+name,data,rate,path)
        ids[name]=cli('ingest-'+name,'media','ingest','--project',project,'--input',path,'--evidence',proof,
            '--creator','LibriSpeech contributors' if name.startswith('english') else 'local synthetic Kokoro',
            '--license-spdx','CC-BY-4.0' if name.startswith('english') else 'LicenseRef-See-Source')['asset']['id']
    native='D:/dev/comfyui/ComfyUI_windows_portable_nvidia_0_30_0/ComfyUI_windows_portable/python_embeded/python.exe'
    adapter=cli('register','audio','enhancement-adapter','register','--project',project,'--adapter-id','df3_local','--model-path',model,
        '--executable',native,'--evidence',BASE/'conversion.json','--license-spdx','MIT OR Apache-2.0','--creator','DeepFilterNet contributors',
        '--threads','4','--segment-seconds','2','--overlap','.25')['adapter']
    cmd=['audio','enhance','--project',project,'--adapter-id','df3_local','--source-asset-id',ids['english-noisy'],
         '--asset-id','english_enhanced','--apply','--track-id','track_audio_1']
    before=(project/'project.json').read_bytes();cli('dry-run',*cmd,'--dry-run');check('dry-run leaves project byte-identical',before==(project/'project.json').read_bytes())
    english=cli('english-enhance',*cmd);shutil.copy2(project/english['asset']['uri'],public/'english-enhanced.wav')
    enhanced=np.frombuffer(pcm('decode-english-enhanced',public/'english-enhanced.wav'),'<f4').reshape(-1,1)
    check('English complete native samples retained',enhanced.shape==human.shape)
    worker=english['generation']['worker'];check('actual CUDA full graph with no network and no fallback',
        worker['model']['neural_backend']=='cuda' and worker['metrics']['model_calls']>0 and not worker['model']['CPU_fallback'] and worker['blocked_network_events']==[])
    record['quality']['english_seeded_noise']=dict(input=stats(human,noisy),enhanced=stats(human,enhanced))
    first=137;last=len(chinese)-211
    chinese_result=cli('chinese-enhance','audio','enhance','--project',project,'--adapter-id','df3_local',
        '--source-asset-id',ids['chinese-noisy'],'--asset-id','chinese_enhanced','--start-seconds',str(first/44100),
        '--end-seconds',str(last/44100),'--strength','.85','--attenuation-limit-db','24')
    shutil.copy2(project/chinese_result['asset']['uri'],public/'chinese-enhanced.wav')
    zh_enhanced=np.frombuffer(pcm('decode-chinese-enhanced',public/'chinese-enhanced.wav'),'<f4').reshape(-1,2)
    check('Chinese exact odd native range and both independent channels preserved',zh_enhanced.shape==(last-first,2) and
        chinese_result['generation']['worker']['range']==dict(start_sample=first,end_sample=last,samples=last-first,sample_rate=44100))
    record['quality']['chinese_synthetic_seeded_noise']=dict(input=stats(chinese[first:last],zh_noisy[first:last]),enhanced=stats(chinese[first:last],zh_enhanced),
        selection=dict(start_sample=first,end_sample=last,sample_rate=44100),upsampled_source=True,independent_channels=True)
    for source_id,name in ((ids['english-clean'],'clean_control'),(ids['english-reverb-noisy'],'reverb_control')):
        result=cli(name,'audio','enhance','--project',project,'--adapter-id','df3_local','--source-asset-id',source_id,'--asset-id',name)
        shutil.copy2(project/result['asset']['uri'],public/(name+'.wav'))
        actual=np.frombuffer(pcm('decode-'+name,public/(name+'.wav')),'<f4').reshape(-1,1)
        record['quality'][name]=dict(input=stats(human,human if name=='clean_control' else reverb_noisy),enhanced=stats(human,actual),
            no_quality_acceptance=True);save()
    bypass=cli('bit-exact-bypass','audio','enhance','--project',project,'--adapter-id','df3_local',
        '--recipe-asset-id','chinese_enhanced','--asset-id','native_bypass','--strength','0')
    check('all selected native stereo Float32 bits bypass exactly',pcm('decode-bypass',project/bypass['asset']['uri'])==zh_noisy[first:last].astype('<f4').tobytes()
        and bypass['generation']['worker']['bypass_bit_exact'] and bypass['generation']['worker']['metrics']['model_calls']==0)
    gentler=cli('recipe-rerun','audio','enhance','--project',project,'--adapter-id','df3_local',
        '--recipe-asset-id','english_enhanced','--asset-id','english_gentler','--strength','.5')
    gentle=np.frombuffer(pcm('decode-gentle',project/gentler['asset']['uri']),'<f4').reshape(-1,1)
    check('recipe rerun equals explicit native dry wet mix within Float32 rounding',np.max(np.abs(gentle-(noisy+(enhanced-noisy)*np.float32(.5))))<3e-7)
    cli('validate','validate','--project',project)
    rendered=project/'renders/enhanced.mp4';cli('render','render','--project',project,'--output',rendered)
    package=cli('package','convert','export','--project',project,'--target-format','package','--output',project/'exports/enhanced.aevpkg.zip')['output']
    restored=work/'restored';cli('restore','convert','import','--input',package,'--output',restored)
    rp=json.loads((restored/'project.json').read_bytes());original=json.loads((project/'project.json').read_bytes())
    check('package preserves every source enhanced asset byte and immutable recipe',all(sha(restored/v['uri'])==sha(project/v['uri'])
        and v.get('source',{}).get('speech_enhancement')==next(z for z in original['assets'] if z['id']==v['id']).get('source',{}).get('speech_enhancement') for v in rp['assets']))
    restored_render=restored/'renders/restored.mp4';cli('restored-render','render','--project',restored,'--output',restored_render)
    check('complete package render decoded PCM identical',pcm('original-render-pcm',rendered)==pcm('restored-render-pcm',restored_render))
    shutil.copy2(package,public/'editable-enhancement.aevpkg.zip')
    record.update(status='passed',finished_at_utc=datetime.now(timezone.utc).isoformat(),project=str(project),public=str(public),
        source_ids=ids,adapter_sha256=adapter['sha256'],english_result=english,chinese_result=chinese_result,
        human_input_rate=16000,english_working_rate=48000,chinese_source_rate=24000,chinese_native_rate=44100,
        English_model_calls=worker['metrics']['model_calls'],Chinese_model_calls=chinese_result['generation']['worker']['metrics']['model_calls'],
        public_files=[dict(path=p.relative_to(ROOT).as_posix(),bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(public.iterdir()) if p.is_file()])
    save();print(json.dumps(dict(status=record['status'],quality=record['quality'],English_model_calls=record['English_model_calls'],Chinese_model_calls=record['Chinese_model_calls']),ensure_ascii=False),flush=True)
except BaseException as exc:record.update(status='failed',error=repr(exc));save();raise
