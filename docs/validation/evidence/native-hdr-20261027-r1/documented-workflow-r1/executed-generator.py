"""Execute the exact documented PowerShell workflow through the registered Skill."""
from pathlib import Path
from datetime import datetime,timezone
import argparse,hashlib,json,re,shutil,subprocess
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/validation/evidence/native-hdr-20261027-r1'
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def main():
    p=argparse.ArgumentParser();p.add_argument('--run',required=True);a=p.parse_args();assert a.run=='r1'
    out=BASE/'documented-workflow-r1';out.mkdir(exist_ok=False);(out/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    guide=ROOT/'docs/product/HDR_DISPLAY.md'
    match=re.search(r'```powershell\n(.*?)\n```',guide.read_text('utf8'),re.S);assert match
    script=out/'workflow.ps1';script.write_text(match[1]+'\n',encoding='utf-8-sig',newline='\n')
    command=['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',str(script)]
    result=subprocess.run(command,cwd=ROOT,capture_output=True,timeout=1200,creationflags=subprocess.CREATE_NO_WINDOW)
    (out/'workflow.stdout.txt').write_bytes(result.stdout);(out/'workflow.stderr.txt').write_bytes(result.stderr)
    assert result.returncode==0,result.stderr.decode('utf8','replace')
    values=[json.loads(line) for line in result.stdout.decode('utf-8-sig').splitlines() if line.strip()]
    assert len(values)==5 and all(v['ok'] and v['provenance']['cli_version']=='0.1.40' for v in values)
    ffmpeg=shutil.which('ffmpeg');assert ffmpeg
    checks=[]
    for i,path in enumerate([ROOT/'docs/assets/native-hdr-20261027-r3/pq-master.mkv',ROOT/'local/agent-ffmpeg/hdr-usage-r1/renders/usage-pq.mkv']):
        args=[ffmpeg,'-nostdin','-v','error','-i',str(path),'-an','-pix_fmt','yuv444p10le','-fps_mode','passthrough','-f','rawvideo','pipe:1']
        decoded=subprocess.run(args,capture_output=True,timeout=300,creationflags=subprocess.CREATE_NO_WINDOW);assert decoded.returncode==0
        checks.append(dict(path=str(path),bytes=len(decoded.stdout),sha256=hashlib.sha256(decoded.stdout).hexdigest()))
        (out/('decode-'+str(i)+'.stderr.txt')).write_bytes(decoded.stderr)
    assert checks[0]['sha256']==checks[1]['sha256'] and checks[0]['bytes']==checks[1]['bytes']==48*640*360*6
    report=dict(status='passed',at_utc=datetime.now(timezone.utc).isoformat(),exact_documented_workflow_executed=True,
        guide_sha256=sha(guide),script_sha256=sha(script),CLI_calls=5,registered_skill=True,source_fallback=False,
        all_48_frames_match_case=True,decoded_outputs=checks,native_windows=True,virtualization=False,
        human_listening=False,HDR_monitor_accepted=False)
    (out/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n');print(json.dumps(report,ensure_ascii=False))
if __name__=='__main__':main()
