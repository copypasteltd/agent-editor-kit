"""Interleave old/new installed full renders on identical cold project copies."""
import argparse, ctypes, hashlib, json, os, platform, shutil, statistics, subprocess, sys, time
from ctypes import wintypes
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/validation/evidence/float-text-coverage-20261026-r1'
OLD=ROOT/'local/agent-ffmpeg/v0.1.0-alpha.4-local.20/final-r2/installed'
NEW=ROOT/'local/agent-ffmpeg/v0.1.0-alpha.4-local.21/final-r2/installed'


def sha(path):
    with Path(path).open('rb') as reader:return hashlib.file_digest(reader,'sha256').hexdigest()


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--run',required=True);args=ap.parse_args()
    assert args.run.replace('-','').isalnum()
    out=BASE/('benchmark-'+args.run);out.mkdir(exist_ok=False)
    work=ROOT/'workspace'/('float-text-coverage-20261026-benchmark-'+args.run);work.mkdir(exist_ok=False)
    (out/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    report={'status':'running','rounds':[],'calls':[],'virtualization':False,'source_fallback':False,
            'exclusive_host':False,'new_model_forwards':0,'python':platform.python_version()}
    def save():(out/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    def run(name,command,timeout=900):
        start=time.perf_counter();result=subprocess.run(list(map(str,command)),cwd=ROOT,capture_output=True,
            timeout=timeout,creationflags=subprocess.CREATE_NO_WINDOW)
        (out/(name+'.stdout.log')).write_bytes(result.stdout);(out/(name+'.stderr.log')).write_bytes(result.stderr)
        report['calls'].append({'name':name,'argv':list(map(str,command)),'exit_code':result.returncode,
            'seconds':time.perf_counter()-start,'stdout_sha256':hashlib.sha256(result.stdout).hexdigest(),
            'stderr_sha256':hashlib.sha256(result.stderr).hexdigest()});save()
        print(json.dumps({'name':name,'code':result.returncode,'seconds':report['calls'][-1]['seconds']}),flush=True)
        assert result.returncode==0,(name,result.stdout[-2000:],result.stderr[-2000:])
        return result.stdout,report['calls'][-1]['seconds']
    try:
        kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        kernel.GetCurrentProcess.restype=wintypes.HANDLE
        kernel.GetProcessAffinityMask.argtypes=[wintypes.HANDLE,ctypes.POINTER(ctypes.c_size_t),ctypes.POINTER(ctypes.c_size_t)]
        kernel.SetProcessAffinityMask.argtypes=[wintypes.HANDLE,ctypes.c_size_t]
        process,system=ctypes.c_size_t(),ctypes.c_size_t();handle=kernel.GetCurrentProcess()
        assert kernel.GetProcessAffinityMask(handle,ctypes.byref(process),ctypes.byref(system))
        available=[i for i in range(8*ctypes.sizeof(process)) if process.value&(1<<i)]
        selected=available[:4];assert len(selected)==4
        assert kernel.SetProcessAffinityMask(handle,sum(1<<i for i in selected))
        report.update(logical_cpu_affinity=selected,logical_cpu_count=os.cpu_count(),
            cache_policy='fresh project directory and empty project cache on every timed render; native OS page cache is uncontrolled')
        import numpy as np
        source=ROOT/'workspace/float-text-20261026-case-r3/编辑 工程'
        authored=json.loads((source/'project.json').read_bytes())
        author_keys=('settings','assets','sequences')
        author_hash=hashlib.sha256(json.dumps({k:authored[k] for k in author_keys},sort_keys=True,ensure_ascii=False).encode()).hexdigest()
        ffmpeg=next(r['path'] for r in json.loads((ROOT/'docs/validation/evidence/float-text-20261026-r1/case-r3/native-text-receipt.json').read_bytes())['artifacts'] if r['role']=='float-text-native-runtime')
        versions={}
        for label,installed in [('old',OLD),('new',NEW)]:
            data,_=run(label+'-version',[sys.executable,'-I','-S','-B','-u','-X','utf8',installed/'run.py','version'])
            versions[label]=json.loads(data)['data']['cli_version']
        assert versions=={'old':'0.1.22','new':'0.1.23'}
        report.update(versions=versions,authoring_sha256=author_hash)
        sequence=[('old',1),('new',1),('new',2),('old',2),('old',3),('new',3)]
        for label,number in sequence:
            name=f'{label}-{number}';project=work/name
            project.mkdir(exist_ok=False)
            for filename in ('project.json','rights-ledger.json'):shutil.copyfile(source/filename,project/filename)
            for folder in ('assets','fonts'):shutil.copytree(source/folder,project/folder)
            output=project/'renders/result.mkv'
            raw,seconds=run(name+'-render',[sys.executable,'-I','-S','-B','-u','-X','utf8',
                (OLD if label=='old' else NEW)/'run.py','render','--project',project,'--output',output])
            response=json.loads(raw);assert response['ok']
            after=json.loads((project/'project.json').read_bytes())
            assert {k:after[k] for k in author_keys}=={k:authored[k] for k in author_keys}
            report['rounds'].append({'label':label,'round':number,'seconds':seconds,'project':str(project),
                'render':str(output),'authoring_unchanged':True,'render_sha256':sha(output)})
            save()
        # Decode after all timing calls, so the comparison work cannot warm a
        # later timed renderer differently. Raw rasters remain on ignored E:.
        reference=None;comparisons=[]
        for row in report['rounds']:
            name=f"{row['label']}-{row['round']}";project=Path(row['project'])
            yuv=project/'decoded.yuv';pcm=project/'decoded.f32'
            run(name+'-decode-video',[ffmpeg,'-nostdin','-v','error','-n','-i',row['render'],'-map','0:v:0',
                '-pix_fmt','yuv444p10le','-f','rawvideo',yuv])
            run(name+'-decode-audio',[ffmpeg,'-nostdin','-v','error','-n','-i',row['render'],'-map','0:a:0',
                '-c:a','pcm_f32le','-f','f32le',pcm])
            clock,_=run(name+'-frame-clocks',[ffmpeg,'-nostdin','-v','error','-i',row['render'],'-map','0:v:0','-f','framemd5','-'])
            clocks=[','.join(line.split(',')[:5]) for line in clock.decode().splitlines() if line and not line.startswith('#')]
            assert len(clocks)==72 and yuv.stat().st_size==72*320*180*3*2 and pcm.stat().st_size==288000*2*4
            values=np.memmap(yuv,dtype='<u2',mode='r',shape=(72,3,180,320))
            if reference is None:reference=(yuv,sha(pcm),clocks)
            previous=np.memmap(reference[0],dtype='<u2',mode='r',shape=values.shape)
            maximum,changed=0,0
            for index in range(72):
                difference=np.abs(values[index].astype(np.int32)-previous[index].astype(np.int32))
                maximum=max(maximum,int(difference.max()));changed+=int(np.count_nonzero(difference))
            del values,previous
            assert maximum<=1 and sha(pcm)==reference[1] and clocks==reference[2],(name,maximum)
            comparisons.append({'name':name,'frames':72,'maximum_decoded_10bit_code_error':maximum,
                'different_codes':changed,'all_frame_clocks_equal':True,'full_PCM_equal':True,
                'decoded_video_sha256':sha(yuv),'PCM_sha256':sha(pcm)})
        medians={k:statistics.median(row['seconds'] for row in report['rounds'] if row['label']==k) for k in ('old','new')}
        report.update(status='passed',comparisons=comparisons,median_seconds=medians,
            median_speedup=medians['old']/medians['new'],actual_renders=6,frames_per_render=72,
            duration_seconds=6,pixel_gate='at most one decoded YUV444 10bit code; exact frame clocks/full float PCM',
            natural_quality_accepted=False,peak_RSS_measured=False)
        save();print(json.dumps({k:report[k] for k in ('status','median_seconds','median_speedup','actual_renders')}),flush=True)
    except BaseException as exc:
        report.update(status='failed',error=repr(exc));save();raise


if __name__=='__main__':main()
