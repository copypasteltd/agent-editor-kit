"""Render the same public author graph through the registered installed Skill."""
from pathlib import Path
from datetime import datetime,timezone
import argparse,hashlib,json,shutil,subprocess,time

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/validation/evidence/gpu-dispatch-20261027-r1'
SKILL=Path('C:/Users/carzy/.codex/skills/agent-ffmpeg-local-editor/scripts/run.ps1')
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def load(p):return json.loads(Path(p).read_bytes())
def save(p,v):Path(p).write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--run',required=True);ap.add_argument('--expect-version',required=True);ap.add_argument('--baseline')
    a=ap.parse_args();assert a.run.replace('-','').isalnum()
    out=BASE/('render-'+a.run);out.mkdir(parents=True,exist_ok=False)
    (out/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    work=ROOT/'local/agent-ffmpeg'/('gpu-dispatch-render-'+a.run);work.mkdir(exist_ok=False)
    project=work/'project';calls=[];report={'status':'running','at_utc':datetime.now(timezone.utc).isoformat(),
        'registered_skill':True,'native_windows':True,'virtualization':False,'source_fallback':False,
        'synthetic_diagnostic':True,'natural_quality_accepted':False,'human_listening':False}
    def run(name,argv,*,cli=False):
        started=time.perf_counter();r=subprocess.run(list(map(str,argv)),cwd=ROOT,capture_output=True,timeout=900,creationflags=subprocess.CREATE_NO_WINDOW)
        target=out/(name+'.stdout.json') if cli else work/(name+'.bin');target.write_bytes(r.stdout)
        err=out/(name+'.stderr.txt');err.write_bytes(r.stderr)
        calls.append({'id':name,'argv':list(map(str,argv)),'exit_code':r.returncode,'seconds':time.perf_counter()-started,
            'stdout_bytes':len(r.stdout),'stdout_sha256':sha(target),'stderr_sha256':sha(err)})
        save(out/'calls.json',calls);print(json.dumps({'id':name,'code':r.returncode}),flush=True)
        assert r.returncode==0,(name,r.stdout[-3000:],r.stderr[-3000:])
        if cli:
            v=json.loads(r.stdout);assert v['ok'];return v['data']
        return r.stdout
    def invoke(name,*args):return run(name,['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',SKILL,*args],cli=True)
    try:
        runtime=load(ROOT/'local/agent-ffmpeg/runtime.json')
        report.update(installed=runtime['installed_directory'],manifest_sha256=runtime['manifest_sha256'])
        version=invoke('version','version');assert version['cli_version']==a.expect_version
        fixture=ROOT/'docs/assets/procedural-particles-20261027-r3/editable-particle-grid.aevpkg.zip'
        report['fixture_sha256']=sha(fixture)
        invoke('import','convert','import','--input',fixture,'--output',project)
        author=load(project/'project.json');frozen={k:author[k] for k in ('settings','assets','sequences')}
        report['author_graph_sha256']=hashlib.sha256(json.dumps(frozen,sort_keys=True,separators=(',',':')).encode('utf8')).hexdigest()
        movie=project/'renders/comparison.mkv'
        rendered=invoke('render','render','--project',project,'--output',movie,'--container','mkv',
            '--video-codec','libx264','--crf','0','--pixel-format','yuv444p10le','--audio-codec','pcm_f32le',
            '--hardware-encode','off','--projection-acceleration','require','--projection-device','0.0')
        actual=Path(rendered['path']);m=load(actual.with_suffix('.mkv.manifest.json'))
        gpu=m['delivery']['pixel_pipeline']['projection_acceleration'];assert gpu['operations']['particles']==288 and gpu['worker_closed']
        ffmpeg=Path(shutil.which('ffmpeg'));ffprobe=Path(shutil.which('ffprobe'))
        report['native_tools']={str(p):sha(p) for p in (ffmpeg,ffprobe)}
        video=run('video-decode',[ffmpeg,'-nostdin','-v','error','-i',actual,'-map','0:v:0','-an',
            '-pix_fmt','yuv444p10le','-fps_mode','passthrough','-f','rawvideo','pipe:1'])
        audio=run('audio-decode',[ffmpeg,'-nostdin','-v','error','-i',actual,'-map','0:a:0','-vn','-c:a','pcm_f32le','-f','f32le','pipe:1'])
        size=960*360*3*2;assert len(video)==size*48 and len(audio)==4*48000*2*4
        frame_hashes=[hashlib.sha256(video[i*size:(i+1)*size]).hexdigest() for i in range(48)]
        report.update(cli_version=version['cli_version'],render_seconds=next(c['seconds'] for c in calls if c['id']=='render'),
            frame_count=48,fps='12/1',duration_seconds=4,video_sha256=hashlib.sha256(video).hexdigest(),
            frame_sha256=frame_hashes,audio_sha256=hashlib.sha256(audio).hexdigest(),audio_samples=384000,
            decoded_audio_all_zero=all(x==0 for x in memoryview(audio).cast('f')),GPU=gpu,movie=str(actual),movie_sha256=sha(actual))
        if a.baseline:
            previous=load(BASE/('render-'+a.baseline)/'verification.json');assert previous['status']=='passed'
            for k in ('fixture_sha256','author_graph_sha256','native_tools','frame_sha256','video_sha256','audio_sha256','audio_samples'):
                assert report[k]==previous[k],k
            report.update(baseline=a.baseline,all_frames_equal=True,all_PCM_equal=True,
                speedup_one_pair=previous['render_seconds']/report['render_seconds'],
                performance_scope='One matched 48-frame registered-Skill pair; startup, render, quality and encoding included; no real-time/long-film/multivendor acceptance.')
        report['status']='passed';save(out/'verification.json',report)
        print(json.dumps({k:v for k,v in report.items() if k not in ('GPU','frame_sha256')},ensure_ascii=False))
    except BaseException as e:report.update(status='failed',error=repr(e));save(out/'verification.json',report);raise

if __name__=='__main__':main()
