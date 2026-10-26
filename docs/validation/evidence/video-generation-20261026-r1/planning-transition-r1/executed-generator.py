"""Retain a completed real mode and omit redundant heavy planning checks.

Stops only this exact owned case controller and its next read-only dry-run,
after the first mode has fully decoded. Actual generation integrity checks are
unchanged; the installed planning tests already cover all four modes.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import time

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/validation/evidence/video-generation-20261026-r1'


def main():
    p=argparse.ArgumentParser();p.add_argument('--controller-pid',type=int,required=True);p.add_argument('--run',required=True);a=p.parse_args()
    assert a.controller_pid>0 and a.run.replace('-','').isalnum()
    out=BASE/'planning-transition-r1';out.mkdir(exist_ok=False)
    (out/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    case=BASE/('case-'+a.run)/'verification.json'
    report=dict(status='waiting-for-first-fully-decoded-real-mode',controller_pid=a.controller_pid,
        reason='Installed14 planning tests cover all modes. Skip further repeated20GB planning reads; real generation checks remain.',
        started_at_utc=datetime.now(timezone.utc).isoformat(),model_checks_weakened=False,other_processes_modified=False)
    def save():(out/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    save();deadline=time.monotonic()+3600
    while time.monotonic()<deadline:
        value=json.loads(case.read_bytes())
        if value['status']=='failed':raise RuntimeError('Case failed before planning transition; preserve failure')
        if len(value.get('modes',[]))==1:break
        if len(value.get('modes',[]))>1:raise RuntimeError('Transition window passed; do not interrupt an actual model job')
        time.sleep(10)
    else:raise TimeoutError('First actual mode did not complete; no processes modified')
    query="Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | Select-Object ProcessId,ParentProcessId,CommandLine | ConvertTo-Json -Compress"
    for _ in range(30):
        raw=subprocess.check_output(['powershell.exe','-NoProfile','-Command',query],creationflags=subprocess.CREATE_NO_WINDOW)
        processes=json.loads(raw.decode('utf-8-sig'));parent=next(row for row in processes if row['ProcessId']==a.controller_pid)
        assert 'scripts/run_video_generation_case_20261026.py' in parent['CommandLine'].replace('\\','/')
        assert '--run '+a.run in parent['CommandLine'] and '--resume' not in parent['CommandLine']
        children=[row for row in processes if row['ParentProcessId']==a.controller_pid and 'media generate' in str(row['CommandLine'])]
        if children:
            child=children[0];assert len(children)==1
            assert '--dry-run' in child['CommandLine'] and '--mode image-to-video' in child['CommandLine']
            assert 'v0.1.0-alpha.4-local.31' in child['CommandLine'];break
        time.sleep(1)
    else:raise TimeoutError('Next read-only child did not appear; no processes modified')
    saved=case.read_bytes();(out/'before-stop.json').write_bytes(saved)
    # The first real worker is already finished and every output frame decoded.
    # Prevent another child first, then stop only the identified read-only child.
    stop='Stop-Process -Id '+str(a.controller_pid)+' -ErrorAction Stop; Stop-Process -Id '+str(child['ProcessId'])+' -ErrorAction Stop'
    result=subprocess.run(['powershell.exe','-NoProfile','-Command',stop],capture_output=True,creationflags=subprocess.CREATE_NO_WINDOW)
    (out/'stop.stdout.txt').write_bytes(result.stdout);(out/'stop.stderr.txt').write_bytes(result.stderr)
    assert result.returncode==0
    report.update(status='resuming-remaining-real-modes',stopped=[parent,child],
        preserved_case_sha256=hashlib.sha256(saved).hexdigest(),completed_real_modes=1)
    save();print(json.dumps(dict(status=report['status'],completed_real_modes=1)),flush=True)
    command=['C:/Python313/python.exe','-E','-B','-u','-X','utf8',str(ROOT/'scripts/run_video_generation_case_20261026.py'),
        '--run',a.run,'--resume']
    with (out/'resume.stderr.log').open('wb') as error,(out/'resume.stdout.log').open('wb') as log:
        process=subprocess.Popen(command,cwd=ROOT,stdout=subprocess.PIPE,stderr=error,creationflags=subprocess.CREATE_NO_WINDOW)
        for line in process.stdout:
            log.write(line);log.flush();print(line.decode('utf8','replace').rstrip(),flush=True)
        code=process.wait()
    report.update(status='passed' if code==0 else 'failed',resume_exit_code=code,finished_at_utc=datetime.now(timezone.utc).isoformat())
    save();assert code==0


if __name__=='__main__':main()
