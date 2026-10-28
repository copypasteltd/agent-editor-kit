"""Recheck actual C59 encoded master against an independent native-code oracle."""
from pathlib import Path
from fractions import Fraction
import argparse, hashlib, json, os, subprocess, sys
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'product/src'))
from ai_ad_editor import hdr_media_measure as media
from ai_ad_editor.media import ffmpeg_path, ffprobe_path
from ai_ad_editor.errors import AppError


def sha(p):return hashlib.file_digest(p.open('rb'),'sha256').hexdigest()

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--run',required=True);a=ap.parse_args();assert a.run.replace('-','').isalnum()
    out=ROOT/'docs/validation/evidence/native-hdr-media-measure-20261029-r1'/('case-'+a.run)
    out.mkdir(exist_ok=False);(out/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    work=ROOT/'local/agent-ffmpeg'/('native-hdr-media-measure-case-'+a.run);work.mkdir(exist_ok=False)
    source_manifest=ROOT/'docs/assets/native-hdr-measure-20261029-r2/hdr-master.manifest.json'
    manifest=json.loads(source_manifest.read_bytes());source=Path(manifest['output']);project=source.parents[1]
    project_file=project/'project.json';before=dict(source=sha(source),project=sha(project_file))
    product=ROOT/'product/src/ai_ad_editor';frozen={p.name:sha(p) for p in product.glob('*.py')}
    def save(name,value):(out/name).write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n',encoding='utf8')
    calls=[]
    def run(name,argv,output=None):
        result=subprocess.run(list(map(str,argv)),cwd=ROOT,capture_output=True,timeout=300,creationflags=subprocess.CREATE_NO_WINDOW)
        (out/(name+'.stderr.txt')).write_bytes(result.stderr)
        if output:output.write_bytes(result.stdout)
        else:(out/(name+'.stdout.json')).write_bytes(result.stdout)
        calls.append(dict(name=name,argv=list(map(str,argv)),exit_code=result.returncode,
                          stdout_sha256=hashlib.sha256(result.stdout).hexdigest(),stdout_bytes=len(result.stdout)))
        save('calls.json',calls);assert result.returncode==0,result.stderr[-3000:]
        return result.stdout
    signal=manifest['settings']['pixel_pipeline']['output_signal']
    kwargs=dict(pixel_family='yuv',yuv=dict(matrix='bt2020nc',range='limited',chroma_location='left'),scan='progressive')
    failure=None
    try:r=media.measure(project,media.prepare(project,str(source),signal,**kwargs))
    except AppError as exc:
        failure=exc.as_dict();save('reject-failure.json',failure)
        # Recheck only the explicitly expected RGB gamut boundary, never hide arbitrary failures.
        assert exc.code=='HDR_MEASURE_RANGE',failure
        r=media.measure(project,media.prepare(project,str(source),signal,range_policy='clip',**kwargs))
    save('measurement.json',r)
    raw=work/'decoded-native-yuv444p10le.bin'
    run('native-code-decode',[ffmpeg_path(),'-nostdin','-v','error','-noautorotate','-i',source,
        '-map','0:v:0','-an','-sn','-dn','-fps_mode','passthrough','-pix_fmt','yuv444p10le','-f','rawvideo','pipe:1'],raw)
    probe=json.loads(run('native-clock',[ffprobe_path(),'-v','error','-select_streams','v:0','-show_frames',
        '-show_streams','-show_entries','frame=best_effort_timestamp,pkt_duration,duration:stream=time_base,width,height',
        '-of','json',source]))
    frames=probe['frames'];stream=probe['streams'][0];w,h=stream['width'],stream['height'];time_base=Fraction(stream['time_base'])
    yuv=np.memmap(raw,mode='r',dtype='<u2',shape=(len(frames),3,h,w))
    maxrgb=[];ys=[];means_rgb=[];means_y=[];weights=[];payload=hashlib.sha256();minimum=float('inf');negative=over=0
    # CIE Y row independently solved from BT2020 primaries and D65 white.
    xy=np.array([[.708,.292],[.170,.797],[.131,.046]],dtype=np.float64)
    xyz=np.array([[x/y,1,(1-x-y)/y] for x,y in xy]).T
    white=np.array([.3127/.329,1,(1-.3127-.329)/.329]);luma=np.linalg.solve(xyz,white)
    for index,frame in enumerate(frames):
        code=yuv[index].astype(np.float64);yy=(code[0]-64)/876;u=(code[1]-512)/896;v=(code[2]-512)/896
        kr,kb=.2627,.0593;kg=1-kr-kb
        rgb=np.stack([yy+2*(1-kr)*v,yy-2*kb*(1-kb)/kg*u-2*kr*(1-kr)/kg*v,yy+2*(1-kb)*u],axis=-1).astype(np.float32)
        rgba=np.ones((h,w,4),np.float32);rgba[:,:,:3]=rgb;payload.update(rgba.astype('<f4').tobytes())
        negative+=int(np.count_nonzero(rgb<0));over+=int(np.count_nonzero(rgb>1))
        encoded=np.clip(rgb.astype(np.float64),0,1);power=encoded**(1/(2523/32))
        light=(np.maximum(power-3424/4096,0)/(2413/128-2392/128*power))**(1/(2610/16384))*10000
        m=np.max(light,axis=-1);y=np.sum(light*luma,axis=-1)
        maxrgb.append(float(np.max(m)));ys.append(float(np.max(y)));means_rgb.append(float(np.mean(m)));means_y.append(float(np.mean(y)))
        minimum=min(minimum,float(np.min(light)))
        weights.append(int(frame.get('duration',frame.get('pkt_duration',0)))*time_base)
    del yuv
    assert all(dt>0 for dt in weights)
    oracle=dict(frames=len(frames),maxrgb_peak=max(maxrgb),cie_y_peak=max(ys),maxrgb_frame_average=max(means_rgb),
        cie_y_frame_average=max(means_y),maxrgb_weighted=sum(v*float(dt) for v,dt in zip(means_rgb,weights))/float(sum(weights)),
        cie_y_weighted=sum(v*float(dt) for v,dt in zip(means_y,weights))/float(sum(weights)),minimum=minimum,
        decoded_RGBA32_sha256='sha256:'+payload.hexdigest(),negative_components=negative,over_one_components=over,
        duration_seconds=str(sum(weights)),code_decode_sha256=sha(raw),original_media_sha256=before['source'],
        no_product_colour_or_meter_helpers=True)
    save('independent-oracle.json',oracle)
    pairs=[(oracle['maxrgb_peak'],r['peak_pixel']['maxrgb']['nits']),
           (oracle['cie_y_peak'],r['peak_pixel']['cie_y']['nits']),
           (oracle['maxrgb_frame_average'],r['maximum_frame_average']['maxrgb']['nits']),
           (oracle['cie_y_frame_average'],r['maximum_frame_average']['cie_y']['nits']),
           (oracle['maxrgb_weighted'],r['duration_weighted_frame_average_nits']['maxrgb']),
           (oracle['cie_y_weighted'],r['duration_weighted_frame_average_nits']['cie_y']),
           (oracle['minimum'],r['minimum_RGB_component_nits'])]
    maximum_error=max(abs(a-b) for a,b in pairs)
    assert maximum_error<1e-7,(maximum_error,pairs)
    assert oracle['decoded_RGBA32_sha256']==r['decoded_RGBA32_sha256']
    assert (negative,over)==(r['range_counts']['negative_components'],r['range_counts']['over_one_components'])
    assert oracle['duration_seconds']==r['analyzed_duration_seconds']
    assert before==dict(source=sha(source),project=sha(project_file))
    assert frozen=={p.name:sha(p) for p in product.glob('*.py')}
    assert r['frames']==48 and r['all_source_frames_measured'] and r['full_canvas_measured']
    assert r['native_decoder_exit_code']==0 and r['owned_threads_terminated']
    save('verification.json',dict(status='passed',frames=48,pixels=48*w*h,maximum_metric_error_nits=maximum_error,
        independent_decoded_RGBA32_equal=True,original_project_and_movie_bytes_unchanged=True,product_files=frozen,
        prior_reject_failure_retained=failure is not None,installed_skill_used=False,source_only=True,
        actual_native_decode=True,new_media_generated=False,existing_public_C59_preview_not_HDR_acceptance=True))
    print(json.dumps(dict(status='passed',frames=48,maximum_metric_error_nits=maximum_error,prior_reject=failure)),flush=True)

if __name__=='__main__':main()
