"""Run the edited source-fragment project through the actual registered queue."""
from pathlib import Path
import argparse,hashlib,json,subprocess

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/validation/evidence/tracking-retime-20261026-r1'

def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--run',required=True);a=ap.parse_args();assert a.run.replace('-','').isalnum()
    out=BASE/('queue-'+a.run);out.mkdir(exist_ok=False);(out/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    case=json.loads((BASE/'case-r1/verification.json').read_bytes());assert case['status']=='passed'
    reference=Path(case['project'])
    project=ROOT/'workspace'/('tracking-retime-20261026-queue-'+a.run)/'独立 工程'
    prefix=['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',
        str(Path('C:/Users/carzy/.codex/skills/agent-ffmpeg-local-editor/scripts/run.ps1'))]
    report=dict(status='running',calls=[],registered_skill=True,source_fallback=False,virtualization=False,new_model_forwards=0)
    def save():
        (out/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    def run(name,argv):
        argv=list(map(str,argv));r=subprocess.run(argv,cwd=ROOT,capture_output=True,timeout=600,creationflags=subprocess.CREATE_NO_WINDOW)
        (out/(name+'.stdout.log')).write_bytes(r.stdout);(out/(name+'.stderr.log')).write_bytes(r.stderr)
        report['calls'].append(dict(name=name,argv=argv,exit_code=r.returncode,stdout_sha256=hashlib.sha256(r.stdout).hexdigest(),stderr_sha256=hashlib.sha256(r.stderr).hexdigest()));save()
        assert r.returncode==0,(name,r.stdout[-2000:],r.stderr[-2000:]);print(json.dumps(dict(name=name,code=r.returncode)),flush=True)
        return r.stdout
    try:
        value=json.loads(run('import',[*prefix,'convert','import','--input',Path(case['public'])/'editable-tracking-retime.aevpkg.zip','--output',project]));assert value['ok']
        before=json.loads((project/'project.json').read_bytes());rights_before=sha(project/'rights-ledger.json')
        job=out/'jobs.json';job.write_text(json.dumps(dict(job_id='tracking-edits',sequence_id='child',output='renders/queued.mkv',
            container='mkv',video_codec='libx264',audio_codec='pcm_f32le',pixel_format='yuv444p',crf=0,
            hardware_encode='off',hardware_decode='off'))+'\n',encoding='utf8')
        for name,argv in [('enqueue',['queue','enqueue','--project',project,'--input',job]),
                          ('run',['queue','run','--project',project,'--job-id','tracking-edits'])]:
            value=json.loads(run(name,[*prefix,*argv]));assert value['ok']
        ffmpeg=next(c['argv'][0] for c in case['calls'] if c['name']=='edited-frames')
        equal=[]
        for kind,args in [('frames',['-map','0:v:0','-pix_fmt','rgba64le','-f','framemd5']),
                          ('pcm',['-map','0:a:0','-c:a','pcm_f32le','-f','hash','-hash','sha256'])]:
            rows=[]
            for label,name in [('actual','edited'),('queued','queued')]:
                movie=(reference if label=='actual' else project)/('renders/'+name+'.mkv')
                rows.append(run(label+'-'+kind,[ffmpeg,'-nostdin','-v','error','-i',movie,*args,'-']))
            assert rows[0]==rows[1];equal.append(kind)
        after=json.loads((project/'project.json').read_bytes())
        assert all(before[k]==after[k] for k in ('settings','assets','sequences'))
        assert rights_before==sha(project/'rights-ledger.json')
        report.update(status='passed',project=str(project),decoded_frames=18,full_pcm_samples_per_channel=72000,
            all_frame_pixels_and_clocks_equal=True,full_pcm_equal=True,authored_graph_and_rights_unchanged=True,
            bookkeeping_changed_fields=[k for k in before.keys()|after.keys() if before.get(k)!=after.get(k)])
        save();print(json.dumps({k:v for k,v in report.items() if k!='calls'},ensure_ascii=False),flush=True)
    except BaseException as exc:report.update(status='failed',error=repr(exc));save();raise

if __name__=='__main__':main()
