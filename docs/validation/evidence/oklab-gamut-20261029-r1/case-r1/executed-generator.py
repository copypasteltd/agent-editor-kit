"""Real source CLI0.1.51 renders, independent full-frame oracle and replay.

This source-phase evidence must not be described as an installed Skill run.
"""
from pathlib import Path
import argparse,copy,hashlib,json,math,shutil,sys
import numpy as np
from PIL import Image,ImageDraw

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/validation/evidence/oklab-gamut-20261029-r1'
sys.path[:0]=[str(ROOT/'product/src'),str(ROOT/'product/tests')]
from test_float_standard_render import FloatStandardRenderTests
from test_float_gamut import oracle
from ai_ad_editor.project import create_project,load_project,project_write_lock
from ai_ad_editor.render import render_project
from ai_ad_editor.media import ffmpeg_path,probe_media
from ai_ad_editor import VERSION


def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,value):p.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
def matrix(primaries):
    xy=np.array(primaries,np.float64);columns=np.array([[x/y,1,(1-x-y)/y] for x,y in xy]).T
    x,y=.3127,.329;scale=np.linalg.solve(columns,[x/y,1,(1-x-y)/y]);return columns*scale


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--run',required=True);a=ap.parse_args();assert a.run.replace('-','').isalnum()
    out=BASE/('case-'+a.run);out.mkdir(parents=True,exist_ok=False)
    (out/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    work=ROOT/'local/agent-ffmpeg'/('oklab-gamut-case-'+a.run);work.mkdir(exist_ok=False)
    public=ROOT/'docs/assets'/('oklab-gamut-20261029-'+a.run);public.mkdir(exist_ok=False)
    assert VERSION=='0.1.51';pins={p.name:sha(p) for p in (ROOT/'product/src/ai_ad_editor').glob('*.py')}
    f=FloatStandardRenderTests('runTest');f.setUp();settings=copy.deepcopy(f.p['settings'])
    f.root,f.p=create_project(work/'project');f.p['settings']=settings;f.s=f.p['sequences'][0];f.s['duration_tick']=90000
    width,height,count=384,216,10
    rng=np.random.default_rng(61);colors=np.vstack([np.eye(3),1-np.eye(3),np.zeros((1,3)),np.ones((1,3)),rng.random((16,3))])
    chart=np.zeros((height,width,3),np.float32)
    for index,c in enumerate(colors):
        x=(index%8)*48;y=(index//8)*72;chart[y:y+72,x:x+48]=c
    rgba=np.ones((count,height,width,4),np.float32)
    for frame in range(count):rgba[frame,:,:,:3]=chart*(.5+.5*frame/(count-1))
    f.visual(rgba);samples=f.audio()
    p=f.p['settings'];p['color'].update(primaries='bt709',transfer='iec61966-2-1',matrix='bt709',range='limited')
    pipeline=p['pixel_pipeline'];pipeline.update(working_signal=dict(primaries='bt2020',transfer='linear',reference_white_nits=203),
        output_signal=dict(primaries='bt709',transfer='srgb',reference_white_nits=100),range_policy='reject')
    pipeline['sources']['picture']['source_signal']=dict(primaries='bt2020',transfer='linear',reference_white_nits=203)
    mapping=dict(operator='reinhard-luminance',source_peak_nits=1000,target_peak_nits=100,exposure_stops=0,gamut_policy='clip')
    pipeline['display_mapping']=mapping
    # Register original synthetic audio before portable export.
    from ai_ad_editor.rights import add_record,load_ledger,save_ledger
    ledger=load_ledger(f.root);audio=f.p['assets'][-1];audio['rights_ref']='rights_audio'
    add_record(ledger,dict(record_id='rights_audio',asset_id='sound',verification_status='verified',source_type='generated',
        source_url=str(f.root/'assets/audio.wav'),license_spdx='CC0-1.0',permitted_uses=['all'],commercial_use_allowed=True,
        modification_allowed=True,attribution_required=False,sha256=audio['sha256'],evidence='Original diagnostic stereo tones.'))
    save_ledger(f.root,ledger)
    first=f.execute('clip.mkv');mapping['gamut_policy']='oklab-chroma';second=f.execute('oklab.mkv')
    actual=f.decode_y(second['path'],width,height)
    # Independent xy-derived source/target matrix, scalar OKLab inverse and
    # scalar ray search. Only unique authored patch colours need evaluation.
    xyz709=matrix([(.64,.33),(.30,.60),(.15,.06)])
    xyz2020=matrix([(.708,.292),(.170,.797),(.131,.046)])
    transform=np.linalg.solve(xyz709,xyz2020);weights=xyz709[1]
    native=(np.rint(rgba.astype(np.float64)*65535)/65535).astype(np.float32)
    expected=np.empty_like(actual,dtype=np.float64);max_rgb_error=0
    for frame in range(count):
        values,inverse=np.unique(native[frame,:,:,:3].reshape(-1,3),axis=0,return_inverse=True)
        converted=(values.astype(np.float64)@transform.T*2.03).astype(np.float32).astype(np.float64)
        codes=[]
        for rgb in converted:
            Y=float(rgb@weights);shoulder=Y*(1+Y/100)/(1+Y)
            toned=rgb*(shoulder/Y if Y>0 else 0);mapped=np.array(oracle(toned))
            encoded=np.where(mapped<=.0031308,mapped*12.92,1.055*np.maximum(mapped,0)**(1/2.4)-.055)
            codes.append(np.rint(encoded*65535)/65535)
        pixels=np.array(codes)[inverse].reshape(height,width,3)
        y=pixels@weights;cb=(pixels[:,:,2]-y)/(2*(1-weights[2]));cr=(pixels[:,:,0]-y)/(2*(1-weights[0]))
        expected[frame]=np.stack([64+876*y,512+896*cb,512+896*cr])
    error=float(np.max(np.abs(actual.astype(np.float64)-expected)));assert error<2,error
    archive=f.root/'exports/editable-oklab.zip';code,value=f.invoke('convert','export','--project',f.root,'--output',archive,'--target-format','package');assert code==0,value
    code,value=f.invoke('convert','import','--input',archive,'--output',work/'replay');assert code==0,value
    root,p=load_project(work/'replay')
    with project_write_lock(root):replay=render_project(root,p,p['sequences'][0],root/'renders/replay.mkv')
    assert f.decode_y(replay['path'],width,height).tobytes()==actual.tobytes()
    def pcm(path):return f.native([ffmpeg_path(),'-nostdin','-v','error','-i',path,'-map','0:a:0','-vn','-c:a','pcm_f32le','-f','f32le','pipe:1'])
    original_pcm=pcm(second['path']);assert original_pcm==pcm(replay['path'])==samples.tobytes()
    totals=second['delivery']['pixel_pipeline']['colour_boundary_all_frames']['totals']
    assert totals['gamut_pixels_mapped']>0
    for label,r in [('clip',first),('oklab',second)]:shutil.copyfile(r['path'],public/(label+'.mkv'));write(public/(label+'.manifest.json'),r)
    shutil.copyfile(archive,public/'editable-oklab.aevpkg.zip')
    # Actual encoded outputs side-by-side, not an illustrative replacement.
    ff=ffmpeg_path();f.native([ff,'-nostdin','-v','error','-i',public/'clip.mkv','-i',public/'oklab.mkv',
        '-filter_complex','[0:v][1:v]hstack=inputs=2,format=yuv420p[v]','-map','[v]','-an','-c:v','libx264','-crf','18','-preset','ultrafast',public/'comparison.mp4'])
    f.native([ff,'-nostdin','-v','error','-i',public/'comparison.mp4','-vf','fps=10,split[a][b];[a]palettegen[p];[b][p]paletteuse',public/'comparison.gif'])
    f.native([ff,'-nostdin','-v','error','-i',public/'comparison.mp4','-vf',"select=eq(n\\,9)",'-frames:v','1',public/'comparison.png'])
    f.assert_clean();assert pins=={p.name:sha(p) for p in (ROOT/'product/src/ai_ad_editor').glob('*.py')}
    write(out/'native-calls.json',__import__('test_float_standard_render').NATIVE_CALLS)
    write(out/'render-receipts.json',[first,second,replay]);write(out/'oracle.json',dict(no_product_colour_helpers=True,
        independent_matrix=transform.tolist(),full_frames=count,pixels=count*width*height,maximum_10bit_code_error=error))
    write(public/'SOURCE.json',dict(license_spdx='CC0-1.0',source='Original generated wide-gamut numerical patch chart and synthetic stereo tones.',
        generator='scripts/run_oklab_gamut_case_20261029.py',comparison='left component clip; right OKLab chroma reduction; actual encoded SDR outputs',
        natural_quality_or_monitor_acceptance=False,source_phase_not_installed_Skill=True))
    write(public/'media-manifest.json',dict(files=[dict(path=p.name,bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(public.iterdir()) if p.is_file()]))
    report=dict(status='passed',cli_version=VERSION,installed_Skill_used=False,source_files=pins,frames=count,width=width,height=height,
        maximum_10bit_code_error=error,all_YUV_planes_checked=True,complete_replay_pixels_equal=True,complete_source_original_replay_PCM_equal=True,
        PCM_bytes=len(original_pcm),PCM_sha256=hashlib.sha256(original_pcm).hexdigest(),all_frame_gamut_counts=totals,
        preview_probe=probe_media(public/'comparison.mp4'),public=str(public),new_model_forwards=0,new_renders=3)
    write(out/'verification.json',report);print(json.dumps({k:v for k,v in report.items() if k not in ['source_files','preview_probe']},ensure_ascii=False),flush=True)
    f.doCleanups()
if __name__=='__main__':main()
