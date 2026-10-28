"""Exercise source CLI52 GPU rendering, independent RGB16 oracle and package replay."""
from pathlib import Path
import argparse,hashlib,json,shutil,subprocess,sys
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/validation/evidence/gpu-gamut-20261029-r1'
SKILL=Path('C:/Users/carzy/.codex/skills/agent-ffmpeg-local-editor')

def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def load(p):return json.loads(Path(p).read_bytes())
def save(p,v):Path(p).write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--run',required=True);a=ap.parse_args()
    assert a.run.replace('-','').isalnum()
    out=BASE/('case-'+a.run);out.mkdir(exist_ok=False)
    (out/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    work=ROOT/'local/agent-ffmpeg'/('gpu-gamut-case-'+a.run);work.mkdir(exist_ok=False)
    public=ROOT/'docs/assets'/('gpu-gamut-20261029-'+a.run);public.mkdir(exist_ok=False)
    ns=ROOT/'agent-ffmpeg-local-install-manifest.json';pin=sha(ns)
    assert load(ns)['cli_version']=='0.1.51'
    assert SKILL.resolve()==(ROOT/'skills/agent-ffmpeg-local-editor').resolve()
    ffmpeg=shutil.which('ffmpeg');assert ffmpeg
    calls=[]
    def call(name,args,cli=False):
        r=subprocess.run(list(map(str,args)),cwd=ROOT,capture_output=True,timeout=600,creationflags=subprocess.CREATE_NO_WINDOW)
        binary=not cli and any(token in name for token in ('full-yuv','pcm','rgba16'))
        destination=(work if binary else out)/(name+('.raw' if binary else '.stdout'))
        destination.write_bytes(r.stdout);(out/(name+'.stderr')).write_bytes(r.stderr)
        calls.append(dict(name=name,argv=list(map(str,args)),exit_code=r.returncode,stdout_sha256=hashlib.sha256(r.stdout).hexdigest()))
        save(out/'calls.json',calls);print(json.dumps(dict(name=name,exit_code=r.returncode)),flush=True)
        assert r.returncode==0,(name,r.stdout[-1500:],r.stderr[-1500:])
        if cli:
            v=json.loads(r.stdout);assert v['ok'] and v['provenance']['cli_version']=='0.1.52';return v['data']
        return r.stdout
    source_files={p.name:sha(p) for p in (ROOT/'product/src/ai_ad_editor').glob('*.py')}
    bootstrap='import sys;sys.path[:0]='+repr([str(ROOT/'product/src'),str(Path(np.__file__).resolve().parent.parent)])+';from ai_ad_editor.cli import main;main()'
    def cli(name,*args):return call(name,[sys.executable,'-I','-S','-B','-X','utf8','-c',bootstrap,*args],True)
    project=work/'project'
    cli('import','convert','import','--input',ROOT/'docs/assets/oklab-preview-candidate-20261029-r1/corrected-oklab.aevpkg.zip','--output',project)
    authored=load(project/'project.json');authored['settings']['projection_acceleration']=dict(mode='require',device='0.0');save(project/'project.json',authored)
    cli('validate','validate','--project',project);before=(project/'project.json').read_bytes()
    (out/'author-before.json').write_bytes(before)
    seq=load(project/'project.json')['sequences'][0]['id']
    movie=project/'renders/oklab.mkv'
    rendered=cli('render','render','--project',project,'--sequence-id',seq,'--output',movie)
    assert rendered['delivery']['pixel_pipeline']['projection_acceleration']['operations']['gamut_map']==10
    assert rendered['delivery']['pixel_pipeline']['last_display_mapping']['perceptual_gamut']['GPU']
    after_render=(project/'project.json').read_bytes()
    original_author=json.loads(before);rendered_author=json.loads(after_render)
    def graph(value):
        value=json.loads(json.dumps(value));value.pop('outputs')
        value['project'].pop('updated_at');value['provenance'].pop('change_log')
        return value
    assert graph(original_author)==graph(rendered_author)
    assert len(rendered_author['outputs'])==len(original_author['outputs'])+1
    assert len(rendered_author['provenance']['change_log'])==len(original_author['provenance']['change_log'])+1
    assert rendered_author['provenance']['change_log'][-1]['command']=='render'
    assert rendered_author['outputs'][-1]['path']==str(movie)
    (out/'author-after-render.json').write_bytes(after_render)
    frame=cli('frame','preview','frame','--project',project,'--frame','9','--height','216')
    window=cli('range','preview','range','--project',project,'--start-frame','0','--end-frame','10','--height','216')
    for v,n in ((frame,1),(window,10)):
        assert v['request']['display_mapping_source']=='display_mapping'
        assert v['pixel_pipeline']['transport']['frames']==n
    package=project/'exports/editable-oklab.aevpkg.zip'
    cli('export','convert','export','--project',project,'--output',package,'--target-format','package')
    replay=work/'replay';cli('reimport','convert','import','--input',package,'--output',replay)
    cli('revalidate','validate','--project',replay)
    again=replay/'renders/oklab.mkv';cli('replay-render','render','--project',replay,'--sequence-id',seq,'--output',again)
    assert after_render==(project/'project.json').read_bytes() and sha(ns)==pin
    old=ROOT/'docs/assets/oklab-gamut-20261029-r3/oklab.mkv'
    def pixels(name,p):return call(name,[ffmpeg,'-nostdin','-v','error','-i',p,'-map','0:v:0','-an','-pix_fmt','yuv444p10le','-f','rawvideo','pipe:1'])
    original=pixels('old-full-yuv',old);actual=pixels('new-full-yuv',movie);restored=pixels('replay-full-yuv',again)
    assert original==actual==restored and len(actual)==10*384*216*3*2
    def pcm(name,p):return call(name,[ffmpeg,'-nostdin','-v','error','-i',p,'-map','0:a:0','-vn','-c:a','pcm_f32le','-f','f32le','pipe:1'])
    audio=pcm('old-pcm',old);assert audio==pcm('new-pcm',movie)==pcm('replay-pcm',again) and len(audio)==384000
    # Reuse the separately executed scalar/xy-matrix oracle, not product helpers.
    oracle=load(ROOT/'docs/validation/evidence/oklab-gamut-20261029-r1/case-r3/oracle.json');raw=ROOT/'local/agent-ffmpeg/oklab-gamut-case-r3/independent-gbrap16.raw'
    assert 'sha256:'+sha(raw)==oracle['RGB16_sha256']
    assert rendered['delivery']['pixel_pipeline']['transport']['video_input_sha256']==oracle['RGB16_sha256']
    reference=np.frombuffer(raw.read_bytes(),'<u2').reshape(10,4,216,384)
    png=call('preview-png-rgba16',[ffmpeg,'-nostdin','-v','error','-i',frame['path'],'-pix_fmt','rgba64le','-f','rawvideo','pipe:1'])
    rgba=np.frombuffer(png,'<u2').reshape(216,384,4)
    expected=np.moveaxis(reference[9,[2,0,1,3]],0,-1)
    png_error=int(np.max(np.abs(rgba.astype(np.int32)-expected.astype(np.int32))))
    assert png_error<=2,png_error
    for src,name in [(movie,'oklab.mkv'),(again,'replay.mkv'),(package,'editable-oklab.aevpkg.zip'),(Path(frame['path']),'frame.png'),(Path(window['path']),'preview.mp4')]:shutil.copyfile(src,public/name)
    call('gif',[ffmpeg,'-nostdin','-v','error','-i',public/'preview.mp4','-filter_complex','[0:v]split[a][b];[a]palettegen[p];[b][p]paletteuse','-loop','0',public/'preview.gif'])
    from PIL import Image
    with Image.open(public/'preview.gif') as gif:
        durations=[]
        for i in range(gif.n_frames):gif.seek(i);durations.append(gif.info.get('duration',0))
        assert gif.n_frames==10 and sum(durations)==1000
    ffprobe=shutil.which('ffprobe');assert ffprobe
    actual_probe=json.loads(call('view-probe',[ffprobe,'-v','error','-count_frames','-show_streams','-of','json',public/'preview.mp4']))
    video=next(v for v in actual_probe['streams'] if v['codec_type']=='video')
    assert int(video['nb_read_frames'])==10 and (video['width'],video['height'])==(384,216)
    media=[dict(path=p.name,bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(public.iterdir())]
    save(public/'SOURCE.json',dict(license='CC0-1.0',source='Original C61 synthetic chart and original tone audio; corrected IDs, actual source CLI52 GPU execution; registered Skill remains CLI51.',files=media,frames=10,fps=10,duration_seconds=1,width=384,height=216,human_listening=False,physical_HDR_review=False))
    assert source_files=={p.name:sha(p) for p in (ROOT/'product/src/ai_ad_editor').glob('*.py')}
    result=dict(status='passed',registered_skill_used=False,source_execution=True,source_files=source_files,source_fallback=False,cli_version='0.1.52',frames=10,width=384,height=216,
                all_YUV_source_original_replay_equal=True,YUV_bytes=len(actual),complete_PCM_equal=True,PCM_bytes=len(audio),
                complete_independent_RGB16_input_equal=True,independent_RGB16_oracle_sha256=oracle['RGB16_sha256'],frame9_RGBA16_maximum_code_error=png_error,
                actual_preview_inherits_delivery_mapping=True,author_graph_unchanged=True,preview_project_bytes_unchanged=True,render_output_ledger_appended=True,new_renders=2,new_model_forwards=0,
                GIF_frames=10,GIF_duration_ms=1000,MP4_decoded_frames=10,namespace_manifest_sha256=pin,public=str(public),calls=len(calls))
    save(out/'verification.json',result);print(json.dumps({k:v for k,v in result.items() if k!='source_files'}),flush=True)
if __name__=='__main__':main()
