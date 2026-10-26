"""Actual registered-Skill project package import and three decoded preview checks."""
from pathlib import Path
import hashlib,json,subprocess,sys,zipfile

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/validation/evidence/float-tracking-20261026-r1'
INSTALL=ROOT/'local/agent-ffmpeg/v0.1.0-alpha.4-local.24/final-r2/installed'

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def main():
    out=BASE/'package-r1';out.mkdir(exist_ok=False)
    (out/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    entry=Path('C:/Users/carzy/.codex/skills/agent-ffmpeg-local-editor')
    assert entry.resolve()==(ROOT/'skills/agent-ffmpeg-local-editor').resolve()
    prefix=['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',str(entry/'scripts/run.ps1')]
    target=ROOT/'workspace/float-tracking-20261026-package-r1/导入 工程'
    report={'status':'running','calls':[],'source_fallback':False,'virtualization':False,'registered_skill':True}
    def save():
        (out/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    def run(name,argv):
        command=list(map(str,argv));r=subprocess.run(command,cwd=ROOT,capture_output=True,timeout=600,creationflags=subprocess.CREATE_NO_WINDOW)
        sout=out/(name+'.stdout.log');serr=out/(name+'.stderr.log');sout.write_bytes(r.stdout);serr.write_bytes(r.stderr)
        report['calls'].append({'name':name,'argv':command,'exit_code':r.returncode,'stdout_sha256':sha(sout),'stderr_sha256':sha(serr)})
        save();print(json.dumps({'name':name,'code':r.returncode}),flush=True)
        assert r.returncode==0,(name,r.stdout[-4000:],r.stderr[-2000:])
        return r.stdout
    def cli(name,*argv):
        r=json.loads(run(name,[*prefix,*argv]));assert r['ok'];return r['data']
    try:
        case=json.loads((BASE/'case-r5/verification.json').read_bytes());assert case['status']=='passed'
        archive=ROOT/'docs/assets/float-tracking-20261026-r5/editable-native-tracking.aevpkg.zip'
        binding_hash=case['binding_observations_sha256']
        def bindings(project):return [c['tracking_binding'] for seq in project['sequences'] for track in seq['tracks'] for c in track['clips'] if c.get('tracking_binding')]
        def binding_digest(project):
            values=bindings(project);assert len(values)==1
            return hashlib.sha256(json.dumps(values[0],sort_keys=True,separators=(',',':')).encode()).hexdigest()
        notice=(INSTALL/'site/ai_ad_editor/material_data/licenses/google-notosanssc.txt').read_bytes()
        with zipfile.ZipFile(archive) as z:
            assert z.read('fonts/Noto-Sans-SC-OFL.txt')==notice
            assert binding_digest(json.loads(z.read('project.json')))==binding_hash
            ledger=json.loads(z.read('rights-ledger.json'))
            assert next(r for r in ledger['records'] if r['asset_id']=='font')['license_spdx']=='OFL-1.1'
        cli('import','convert','import','--input',archive,'--output',target)
        cli('validate','validate','--project',target)
        assert (target/'fonts/Noto-Sans-SC-OFL.txt').read_bytes()==notice
        assert binding_digest(json.loads((target/'project.json').read_bytes()))==binding_hash
        ffmpeg=json.loads((BASE/'case-r5/native-pipeline.json').read_bytes())['timeline']['text']['artifacts']
        native=next(r['path'] for r in ffmpeg if r['role']=='float-text-native-runtime')
        checked=[]
        for frame in (0,18,35):
            actual=cli('preview-'+str(frame),'preview','frame','--project',target,'--frame',frame,'--height',180)
            previous=json.loads((BASE/'case-r5'/('preview-'+str(frame)+'.stdout.log')).read_bytes())['data']
            hashes=[]
            for label,r in [('imported',actual),('original',previous)]:
                raw=run(label+'-'+str(frame),[native,'-nostdin','-v','error','-i',r['path'],'-pix_fmt','rgba64le','-f','hash','-hash','sha256','-'])
                hashes.append(raw.decode().strip())
            assert hashes[0]==hashes[1],(frame,hashes)
            checked.append({'frame':frame,'decoded_RGBA64_SHA256':hashes[0],'equal':True})
        ranges=[]
        for label,project in [('original',case['project']),('imported',target)]:
            result=cli(label+'-range','preview','range','--project',project,'--start-frame',12,'--end-frame',24,'--height',180)
            pixels=run(label+'-range-pixels',[native,'-nostdin','-v','error','-i',result['master'],
                '-map','0:v:0','-an','-pix_fmt','gbrapf32le','-f','rawvideo','-'])
            pcm=run(label+'-range-pcm',[native,'-nostdin','-v','error','-i',result['master'],
                '-map','0:a:0','-c:a','pcm_f32le','-f','f32le','-'])
            assert len(pixels)==12*320*180*16 and len(pcm)==48000*2*4
            ranges.append(dict(pixel_sha256=hashlib.sha256(pixels).hexdigest(),pcm_sha256=hashlib.sha256(pcm).hexdigest()))
        assert ranges[0]==ranges[1]
        report.update(status='passed',project=str(target),archive_sha256=sha(archive),font_license_sha256=hashlib.sha256(notice).hexdigest(),
            font_license_preserved=True,range_preview_frames=12,range_full_pcm_samples_per_channel=48000,range_float32_and_pcm_equal=True,range_hashes=ranges,binding_observations_preserved=True,binding_observations_sha256=binding_hash,checked_frames=checked,natural_quality_accepted=False)
        save();print(json.dumps({'status':'passed','frames':len(checked),'font_license_preserved':True}),flush=True)
    except BaseException as exc:
        report.update(status='failed',error=repr(exc));save();raise

if __name__=='__main__':main()
