"""Profile actual GPU dispatch and the unchanged public C45 author graph."""
from pathlib import Path
from datetime import datetime,timezone
import argparse,cProfile,hashlib,json,pstats,sys,time

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/validation/evidence/gpu-dispatch-20261027-r1'

def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def save(p,v):Path(p).write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--run',required=True);ap.add_argument('--package',type=Path,required=True)
    a=ap.parse_args();assert a.run.replace('-','').isalnum()
    out=BASE/('profile-'+a.run);out.mkdir(parents=True,exist_ok=False)
    work=ROOT/'local/agent-ffmpeg'/('gpu-dispatch-profile-'+a.run);work.mkdir(exist_ok=False)
    (out/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    package=a.package.resolve();sys.path.insert(0,str(package))
    import numpy as np
    import ai_ad_editor
    from ai_ad_editor.artifact_locks import verification_scope
    from ai_ad_editor.convert import import_external
    from ai_ad_editor.project import load_project
    from ai_ad_editor.float_color_signal import ColorSignal
    from ai_ad_editor.float_timeline import FloatTimeline
    from ai_ad_editor.float_gpu import FloatGPUSession
    from ai_ad_editor.float_gpu_native import NativeGPU
    from ai_ad_editor.utils import atomic_write_json,read_json_snapshot
    assert Path(ai_ad_editor.__file__).resolve()==package/'ai_ad_editor/__init__.py'
    pins={p.name:sha(p) for p in (package/'ai_ad_editor').glob('*.py')}
    fixture=ROOT/'docs/assets/procedural-particles-20261027-r3/editable-particle-grid.aevpkg.zip'
    imported=import_external(fixture,work/'project');root,p=load_project(imported['root'])
    signal=ColorSignal(**p['settings']['pixel_pipeline']['working_signal'])
    settings={'projection_acceleration':{'mode':'require','device':'0.0'}}
    report={'status':'running','at_utc':datetime.now(timezone.utc).isoformat(),'cli_version':ai_ad_editor.VERSION,
        'package':str(package),'source_package':package.is_relative_to(ROOT/'product/src'),
        'fixture_sha256':sha(fixture),'virtualization':False,'source_fallback':False,'encoded_movie':False}
    try:
        started=time.perf_counter()
        for i in range(16):
            atomic_write_json(work/'durable-control.json',{'sequence':i,'nonce':'native-profile'})
            assert read_json_snapshot(work/'durable-control.json')['sequence']==i
        report['sixteen_durable_writes_seconds']=time.perf_counter()-started
        rng=np.random.default_rng(72);tiny=rng.random((8,8,4),dtype=np.float32);other=tiny[::-1].copy();expected=None
        direct=[]
        with NativeGPU('0.0',256*1024**2) as native:
            output=np.empty_like(tiny)
            for i in range(32):
                started=time.perf_counter();native.over(tiny,other,output,.63);direct.append(time.perf_counter()-started)
            expected=output.copy();report['direct_native_metadata']=native.metadata.copy()
        profiler=cProfile.Profile();gpu_frames=[];cpu_frames=[];indices=(0,18,47)
        with verification_scope() as verification:
            with FloatGPUSession(root,settings,max_pixels=960*360) as gpu:
                worker=[];profiler.enable()
                for i in range(32):
                    started=time.perf_counter();actual=gpu.over(tiny,other,.63);worker.append(time.perf_counter()-started)
                    np.testing.assert_array_equal(actual,expected)
                profiler.disable()
                host=FloatTimeline(p,p['sequences'][0]['id'],{},working_signal=signal,gpu=gpu,resource_root=root)
                profiler.enable();started=time.perf_counter()
                for i in indices:
                    actual,_=host.render_frame(i);gpu_frames.append(actual)
                report['GPU_author_frames_seconds']=time.perf_counter()-started;profiler.disable()
            report['GPU_receipt']=gpu.evidence
            report['artifact_verification']=verification.summary()
        report['tiny_direct_seconds']=direct;report['tiny_worker_seconds']=worker
        report['tiny_direct_total_seconds']=sum(direct);report['tiny_worker_total_seconds']=sum(worker)
        cpu=FloatTimeline(p,p['sequences'][0]['id'],{},working_signal=signal,resource_root=root)
        started=time.perf_counter()
        for i in indices:
            actual,_=cpu.render_frame(i);cpu_frames.append(actual)
        report['CPU_author_frames_seconds']=time.perf_counter()-started
        errors=[]
        for i,x,y in zip(indices,gpu_frames,cpu_frames):
            errors.append(float(np.max(np.abs(x-y))));assert errors[-1]<=3e-6
            for kind,frame in [('GPU',x),('CPU',y)]:np.save(work/(kind+'-'+str(i)+'.npy'),frame,allow_pickle=False)
        profiler.dump_stats(out/'host.prof')
        stats=pstats.Stats(profiler)
        rows=[]
        for (file,line,name),(primitive,calls,own,cumulative,_) in stats.stats.items():
            rows.append({'file':file,'line':line,'function':name,'primitive_calls':primitive,'calls':calls,
                'own_seconds':own,'cumulative_seconds':cumulative})
        rows.sort(key=lambda r:r['cumulative_seconds'],reverse=True);save(out/'profile-functions.json',rows)
        save(out/'product-files.json',pins)
        assert {p.name:sha(p) for p in (package/'ai_ad_editor').glob('*.py')}==pins
        report.update(status='passed',product_files_frozen=True,frame_indices=list(indices),
            CPU_GPU_max_error=max(errors),raw_frames=str(work),worker_closed=gpu.evidence['worker_closed'])
        assert report['worker_closed']
        save(out/'verification.json',report)
        print(json.dumps({k:v for k,v in report.items() if k not in ('GPU_receipt','direct_native_metadata','tiny_direct_seconds','tiny_worker_seconds')},ensure_ascii=False))
        print(json.dumps(rows[:12],ensure_ascii=False))
    except BaseException as e:report.update(status='failed',error=repr(e));save(out/'verification.json',report);raise

if __name__=='__main__':main()
