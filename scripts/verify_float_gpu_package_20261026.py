"""Actual registered-Skill project package import and three decoded preview checks."""
from pathlib import Path
import hashlib,json,subprocess,sys,zipfile

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/validation/evidence/float-gpu-20261026-r1'
INSTALL=ROOT/'local/agent-ffmpeg/v0.1.0-alpha.4-local.22/final-r4/installed'

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def main():
    out=BASE/'package-r1';out.mkdir(exist_ok=False)
    (out/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    entry=Path('C:/Users/carzy/.codex/skills/agent-ffmpeg-local-editor')
    assert entry.resolve()==(ROOT/'skills/agent-ffmpeg-local-editor').resolve()
    prefix=['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',str(entry/'scripts/run.ps1')]
    target=ROOT/'workspace/float-gpu-20261026-package-r1/导入 工程'
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
        case=json.loads((BASE/'case-r1/verification.json').read_bytes());assert case['status']=='passed'
        archive=ROOT/'docs/assets/float-gpu-20261026-r1/editable-native-text.aevpkg.zip'
        notice=(INSTALL/'site/ai_ad_editor/material_data/licenses/google-notosanssc.txt').read_bytes()
        with zipfile.ZipFile(archive) as z:
            assert z.read('fonts/Noto-Sans-SC-OFL.txt')==notice
            ledger=json.loads(z.read('rights-ledger.json'))
            assert next(r for r in ledger['records'] if r['asset_id']=='font')['license_spdx']=='OFL-1.1'
        cli('import','convert','import','--input',archive,'--output',target)
        cli('validate','validate','--project',target)
        assert (target/'fonts/Noto-Sans-SC-OFL.txt').read_bytes()==notice
        ffmpeg=json.loads((BASE/'case-r1/native-text-receipt.json').read_bytes())['artifacts']
        native=next(r['path'] for r in ffmpeg if r['role']=='float-text-native-runtime')
        checked=[]
        for frame in (24,36,48):
            actual=cli('preview-'+str(frame),'preview','frame','--project',target,'--frame',frame,'--height',180)
            previous=json.loads((BASE/'case-r1'/('preview-'+str(frame)+'.stdout.log')).read_bytes())['data']
            hashes=[]
            for label,r in [('imported',actual),('original',previous)]:
                raw=run(label+'-'+str(frame),[native,'-nostdin','-v','error','-i',r['path'],'-pix_fmt','rgba64le','-f','hash','-hash','sha256','-'])
                hashes.append(raw.decode().strip())
            assert hashes[0]==hashes[1],(frame,hashes)
            checked.append({'frame':frame,'decoded_RGBA64_SHA256':hashes[0],'equal':True})
        report.update(status='passed',project=str(target),archive_sha256=sha(archive),font_license_sha256=hashlib.sha256(notice).hexdigest(),
            font_license_preserved=True,checked_frames=checked,natural_quality_accepted=False)
        save();print(json.dumps({'status':'passed','frames':len(checked),'font_license_preserved':True}),flush=True)
    except BaseException as exc:
        report.update(status='failed',error=repr(exc));save();raise

if __name__=='__main__':main()
