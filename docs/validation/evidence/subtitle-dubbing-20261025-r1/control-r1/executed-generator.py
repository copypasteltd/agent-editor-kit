"""Inject native owner exits/cancellation into real installed dubbing operations."""
import argparse
from datetime import datetime,timezone
import ctypes
from ctypes import wintypes
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback

ROOT=Path(__file__).resolve().parents[1]
OWNER='''import json,os,sys,time
from pathlib import Path
sys.path.insert(0,sys.argv[1])
stage,handshake=sys.argv[2],Path(sys.argv[3])
def hold():
 handshake.write_text(json.dumps(dict(pid=os.getpid(),stage=stage)),encoding='utf-8')
 while True: time.sleep(.05)
if stage=='publication':
 from ai_ad_editor.job_workspaces import Workspace
 original=Workspace.publish
 def publish(self,*args,**kwargs):
  result=original(self,*args,**kwargs);hold();return result
 Workspace.publish=publish
elif stage=='saved':
 import ai_ad_editor.dubbing_cli as module
 original=module.save_project
 def save(*args,**kwargs):
  result=original(*args,**kwargs);hold();return result
 module.save_project=save
elif stage=='committed':
 import ai_ad_editor.project as module
 original=module.commit_project_transaction
 def commit(*args,**kwargs):
  result=original(*args,**kwargs);hold();return result
 module.commit_project_transaction=commit
from ai_ad_editor.cli import main
raise SystemExit(main(sys.argv[4:]))
'''


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path,data):
    path.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


def descendant_handles(parent):
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    class Entry(ctypes.Structure):
        _fields_=[('dwSize',wintypes.DWORD),('cntUsage',wintypes.DWORD),('pid',wintypes.DWORD),
            ('heap',ctypes.c_size_t),('module',wintypes.DWORD),('threads',wintypes.DWORD),
            ('parent',wintypes.DWORD),('priority',wintypes.LONG),('flags',wintypes.DWORD),('name',wintypes.WCHAR*260)]
    kernel.CreateToolhelp32Snapshot.restype=wintypes.HANDLE
    kernel.Process32FirstW.argtypes=[wintypes.HANDLE,ctypes.POINTER(Entry)]
    kernel.Process32NextW.argtypes=[wintypes.HANDLE,ctypes.POINTER(Entry)]
    kernel.CloseHandle.argtypes=[wintypes.HANDLE]
    kernel.OpenProcess.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD]
    kernel.OpenProcess.restype=wintypes.HANDLE
    snapshot=kernel.CreateToolhelp32Snapshot(2,0)
    assert snapshot not in (None,ctypes.c_void_p(-1).value)
    rows=[];entry=Entry();entry.dwSize=ctypes.sizeof(entry)
    try:
        more=kernel.Process32FirstW(snapshot,ctypes.byref(entry))
        while more:
            rows.append((entry.pid,entry.parent,entry.name))
            more=kernel.Process32NextW(snapshot,ctypes.byref(entry))
    finally:
        kernel.CloseHandle(snapshot)
    family={parent}
    for _ in range(16):
        updated=family|{pid for pid,owner,_ in rows if owner in family}
        if updated==family:break
        family=updated
    handles={}
    for pid,_,name in rows:
        if pid!=parent and pid in family and name.casefold() in ('python.exe','ct2-translator.exe'):
            handle=kernel.OpenProcess(0x101000,False,pid)
            if handle:handles[pid]=handle
    return handles


def handles_exited(handles):
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.WaitForSingleObject.argtypes=[wintypes.HANDLE,wintypes.DWORD]
    return all(kernel.WaitForSingleObject(handle,0)==0 for handle in handles.values())


def close_handles(handles):
    kernel=ctypes.WinDLL('kernel32',use_last_error=True)
    kernel.CloseHandle.argtypes=[wintypes.HANDLE]
    for handle in handles.values():kernel.CloseHandle(handle)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--site',type=Path,required=True)
    parser.add_argument('--label',required=True)
    parser.add_argument('--mode',choices=['control','crashes'],required=True)
    args=parser.parse_args()
    site=args.site.resolve(strict=True)
    output=ROOT/'docs/validation/evidence/subtitle-dubbing-20261025-r1'/args.label
    work=ROOT/'local/agent-ffmpeg/dubbing-20261025-r1'/args.label
    output.mkdir(parents=True,exist_ok=False);work.mkdir(parents=True,exist_ok=False)
    (output/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    helper=work/'owner.py';helper.write_text(OWNER,encoding='utf-8')
    env=dict(os.environ,AEK_COMMUNITY_DEVICE_CONFIG=str(ROOT/'local/agent-ffmpeg/community-runtime.json'))
    prefix=[sys.executable,'-I','-S','-B','-u','-X','utf8','-c','import sys;sys.path.insert(0,sys.argv.pop(1));from ai_ad_editor.cli import main;raise SystemExit(main())',str(site)]
    frozen=lambda:[dict(path=p.name,sha256=sha(p)) for p in sorted((site/'ai_ad_editor').glob('*.py'))]
    result=dict(status='running',site=str(site),mode=args.mode,started_at_utc=datetime.now(timezone.utc).isoformat(),
        frozen_before=frozen(),calls=[],cases=[],real_models=True,native_windows=True,virtualization=False,browser_ui=False)
    def cli(name,*argv):
        completed=subprocess.run([*prefix,*map(str,argv)],cwd=ROOT,env=env,capture_output=True,timeout=900,creationflags=subprocess.CREATE_NO_WINDOW)
        (output/(name+'.stdout.json')).write_bytes(completed.stdout);(output/(name+'.stderr.txt')).write_bytes(completed.stderr)
        value=json.loads(completed.stdout.decode('utf-8-sig'))
        result['calls'].append(dict(name=name,exit_code=completed.returncode,response=value))
        assert completed.returncode==0,value
        return value
    def prepare(name):
        project=work/name
        cli(name+'-init','project','init',project)
        source=output/(name+'.srt');source.write_text('1\n00:00:00,000 --> 00:00:06,000\nKeep every original clip.\n',encoding='utf-8')
        command=['dub','subtitles','--project',str(project),'--input',str(source),'--from','en','--to','zh-Hans','--device','cuda']
        return project,command
    def metadata(project):return {name:sha(project/name) for name in ('project.json','rights-ledger.json')}
    try:
        names=('publication','saved','committed') if args.mode=='crashes' else ('cancel','timeout')
        for name in names:
            project,argv=prepare(name)
            before=metadata(project)
            handshake=work/(name+'-handshake.json')
            marker=project/'cancel.marker'
            if name=='cancel':argv+=['--cancel-file',str(marker)]
            if name=='timeout':
                start=time.monotonic();cli('timeout-preflight',*argv,'--dry-run')
                budget=time.monotonic()-start+3.
                argv+=['--timeout-seconds',str(budget)]
            command=[sys.executable,'-I','-S','-B','-u','-X','utf8',str(helper),str(site),name,str(handshake),*argv]
            handles={}
            start=time.monotonic()
            with (output/(name+'-owner.stdout.json')).open('wb') as stdout,(output/(name+'-owner.stderr.txt')).open('wb') as stderr:
                process=subprocess.Popen(command,cwd=ROOT,env=env,stdout=stdout,stderr=stderr,creationflags=subprocess.CREATE_NO_WINDOW)
                try:
                    while process.poll() is None and time.monotonic()-start<300:
                        if name in ('cancel','timeout'):
                            found=descendant_handles(process.pid)
                            for pid,handle in found.items():
                                if pid in handles:close_handles({pid:handle})
                                else:handles[pid]=handle
                            if name=='cancel' and handles and not marker.exists():marker.write_text('cancel owned active worker',encoding='utf-8')
                        elif handshake.exists():
                            assert json.loads(handshake.read_text('utf-8'))['pid']==process.pid
                            process.kill()
                            break
                        time.sleep(.05)
                    process.wait(timeout=20)
                finally:
                    if process.poll() is None:
                        process.kill();process.wait(timeout=20)
            evidence=dict(name=name,owner_pid=process.pid,owner_exit_code=process.returncode,elapsed_seconds=time.monotonic()-start,
                actual_worker_pids=list(handles),worker_handles_exited=handles_exited(handles))
            close_handles(handles)
            if name in ('cancel','timeout'):
                response=json.loads((output/(name+'-owner.stdout.json')).read_text('utf-8-sig'))
                assert handles and evidence['worker_handles_exited'],evidence
                expected='CANCELLED' if name=='cancel' else 'PROCESS_TIMEOUT'
                assert response['errors'][0]['code']==expected,response
                assert metadata(project)==before
                assert not list((project/'cache/managed-jobs').glob('job-*'))
                evidence.update(error_code=expected,metadata_unchanged=True)
            else:
                assert handshake.exists(),(name,'owner exited before requested injection point')
                preview=cli(name+'-preview','project','recover','--project',project,'--cleanup-jobs','--dry-run')
                recovered=cli(name+'-recover','project','recover','--project',project,'--cleanup-jobs')
                evidence.update(recovery=recovered['data'],preview=preview['data'])
                if name=='committed':
                    payload=json.loads((project/'project.json').read_text('utf-8'))
                    assert payload['assets'] and all((project/a['uri']).is_file() for a in payload['assets'])
                    assert len(list((project/'assets/derived').rglob('*MODEL-SOURCE.txt')))==2
                    cli(name+'-validate','validate','--project',project)
                    evidence['committed_assets_and_licenses_preserved']=True
                else:
                    assert metadata(project)==before
                    assert not any(p.is_file() for p in (project/'assets/derived').rglob('*'))
                    evidence.update(metadata_unchanged=True,partial_publications_removed=True)
                assert not list((project/'cache/managed-jobs').glob('job-*'))
            evidence['status']='passed'
            result['cases'].append(evidence);save(output/'progress.json',result)
            print(json.dumps({k:evidence[k] for k in ('name','status','elapsed_seconds')}),flush=True)
        result['status']='passed'
    except BaseException as error:
        result.update(status='failed',error=repr(error),traceback=traceback.format_exc())
        raise
    finally:
        result.update(finished_at_utc=datetime.now(timezone.utc).isoformat(),frozen_after=frozen())
        result['frozen_equal']=result['frozen_before']==result['frozen_after']
        save(output/'verification.json',result)
        print(json.dumps({k:result[k] for k in ('status','frozen_equal')}),flush=True)
    assert result['frozen_equal']


if __name__=='__main__':main()
