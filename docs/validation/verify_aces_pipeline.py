"""Frozen-source native ACES integration, compatibility and persisted media proof."""
import argparse,hashlib,json,os,shutil,sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
os.environ['TEMP']=os.environ['TMP']=str(ROOT/'local/tmp')
Path(os.environ['TEMP']).mkdir(parents=True,exist_ok=True)
sys.path[:0]=[str(ROOT/'product/src'),str(ROOT/'product/tests')]
OUT=ROOT/'docs/validation/evidence/aces-pipeline-20261029-r1'
OUT.mkdir(parents=True,exist_ok=True)

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def frozen():
    p=ROOT/'product/src/ai_ad_editor'
    paths=[*p.glob('*.py'),p/'agent-project.schema.json',ROOT/'product/pyproject.toml',p/'native_ocio_manifest.json',*sorted((p/'native_ocio').iterdir())]
    return {str(f.relative_to(ROOT)):sha(f) for f in paths if f.is_file()}
def save(name,data):
    (OUT/name).write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')

def tests(group,run_id):
    before=frozen()
    if group=='special':names=['test_ocio_runtime.OCIORuntimeTests','test_aces_pipeline.ACESPipelineTests']
    elif group=='meter':names=['test_hdr_measure','test_hdr_media_measure','test_schema_contract']
    else:names=list(json.loads((ROOT/'docs/validation/evidence/gpu-gamut-20261029-r1/compat-r1/verification.json').read_bytes())['test_files'])
    with (OUT/(group+'-'+run_id+'.txt')).open('w',encoding='utf-8') as stream:
        result=unittest.TextTestRunner(stream=stream,verbosity=2).run(unittest.TestSuite(unittest.defaultTestLoader.loadTestsFromName(n) for n in names))
    after=frozen();equal=before==after
    data=dict(status='passed' if result.wasSuccessful() and equal else 'failed',tests=result.testsRun,
        failures=len(result.failures),errors=len(result.errors),skipped=len(result.skipped),source_files=before,frozen_equal=equal,
        tests_selected=names,test_files={n.split('.')[0]:sha(ROOT/'product/tests'/(n.split('.')[0]+'.py')) for n in names},
        tests_passed=result.wasSuccessful(),source_changes={k:dict(before=before.get(k),after=after.get(k)) for k in before.keys()|after.keys() if before.get(k)!=after.get(k)})
    if group=='special':
        import test_aces_pipeline
        data['receipts']=test_aces_pipeline.RECEIPTS
    save(group+'-'+run_id+'.json',data)
    print(json.dumps({k:v for k,v in data.items() if k not in ['source_files','test_files','receipts']}),flush=True)
    assert data['status']=='passed' and not result.skipped

def case():
    import numpy as np
    from PIL import Image
    from ai_ad_editor.media import ffmpeg_path,probe_media
    from test_aces_pipeline import ACESPipelineTests
    before=frozen();dest=ROOT/'docs/assets/aces-timeline-20261029-r1';dest.mkdir(parents=True,exist_ok=True)
    t=ACESPipelineTests('runTest');t.setUp();f=t.f
    try:
        source=t.visual(128,96,8)
        first=f.execute('aces.mkv');shutil.copy(first['path'],dest/'author-aces.mkv')
        code,v=f.invoke('preview','frame','--project',f.root,'--frame','7','--height','128');assert code==0,v
        frame=v['data'];shutil.copy(frame['path'],dest/'frame7.png')
        code,v=f.invoke('preview','range','--project',f.root,'--start-frame','0','--end-frame','8','--height','64');assert code==0,v
        window=v['data'];shutil.copy(window['path'],dest/'preview.mp4')
        f.native([ffmpeg_path(),'-nostdin','-v','error','-i',dest/'preview.mp4','-filter_complex',
            '[0:v]fps=10,scale=288:384:flags=neighbor,split[a][b];[a]palettegen[p];[b][p]paletteuse',
            '-loop','0','-y',dest/'preview.gif'])
        with Image.open(dest/'preview.gif') as im:
            assert im.n_frames==8
            duration=0
            for i in range(im.n_frames):im.seek(i);duration+=im.info.get('duration',0)
            assert duration==800
        raw=f.native([ffmpeg_path(),'-nostdin','-v','error','-i',dest/'frame7.png','-an','-pix_fmt','rgba64le','-f','rawvideo','pipe:1'])
        actual=np.frombuffer(raw,'<u2').reshape(128,96,4)
        expected=np.rint(np.clip(t.native_reference(source[7]).astype(np.float64),0,1)*65535)
        error=float(np.max(abs(actual.astype(np.float64)-expected)));assert error<=2,error
        archive=f.root/'exports/editable-project.zip';code,v=f.invoke('convert','export','--project',f.root,'--output',archive,'--target-format','package');assert code==0,v
        shutil.copy(archive,dest/'editable-project.zip')
        f.assert_clean();assert frozen()==before
        data=dict(status='passed',scope='source-CLI53-synthetic-scene-ACEScg-case',installed_skill=False,
            render=first,frame=frame,window=window,gif_frames=8,gif_duration_ms=duration,
            frame7_native_reference_max_RGB16_code_error=error,
            raw_native_commands=__import__('test_float_standard_render').NATIVE_CALLS,
            media={p.name:dict(bytes=p.stat().st_size,sha256=sha(p)) for p in dest.iterdir() if p.is_file()},
            probe=probe_media(dest/'preview.mp4'),source_files=before,frozen_equal=True,
            natural_footage=False,physical_monitor_acceptance=False,human_continuous_watch_or_listening=False)
        save('case-r1.json',data);print('source ACES case passed; eight-frame GIF/MP4 and editable project persisted',flush=True)
    finally:t.doCleanups()

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--group',choices=['special','compat','meter','case'],required=True)
    p.add_argument('--run-id',choices=['r3','r4','r5'],default='r3');args=p.parse_args()
    case() if args.group=='case' else tests(args.group,args.run_id)
