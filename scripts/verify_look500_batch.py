"""Verify every installed look through the actual CLI parser and native FFmpeg.

One isolated process reuses installed imports. Project transactions/rendering are
tested separately; these 500 videos exercise native LUT transforms, not 500
independent full-project render jobs.
"""
from pathlib import Path
import argparse
import contextlib
import gzip
import hashlib
import io
import json
import os
import subprocess
import sys
import time


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('installed','evidence','assets','work','root'):
        parser.add_argument('--'+name,type=Path,required=True)
    args=parser.parse_args()
    site=(args.installed/'site').resolve()
    sys.path[:]=[str(site),*[p for p in sys.path if p and not {'site-packages','dist-packages'} & set(Path(p).parts) and Path(p).resolve()!=args.root/'scripts']]
    import ai_ad_editor.looks as looks
    from ai_ad_editor.cli import main as cli_main
    import numpy as np
    from PIL import Image
    assert Path(looks.__file__).resolve().is_relative_to(site)
    rows=looks.catalog()['records'];assert len(rows)==500
    files=json.loads((args.root/'sources/lut-research-20261024/look-sources.json').read_bytes())
    upstream={r['upstream_path']:args.root/r['path'] for repo in files for r in repo['files']}
    acquired=json.loads((args.root/'docs/validation/evidence/look500-sources-20261024-r1/acquisition.json').read_bytes())
    upstream.update({r['path']:args.root/r['local_path'] for r in acquired['candidates']})
    commands=[];results=[]
    previews=args.assets/'previews';previews.mkdir(exist_ok=True)
    videos=args.assets/'videos';videos.mkdir(exist_ok=True)
    scratch=args.work/'batch';scratch.mkdir()

    def save(name,value):
        (args.evidence/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

    def cli(label,argv):
        out=io.StringIO();err=io.StringIO();started=time.monotonic()
        with contextlib.redirect_stdout(out),contextlib.redirect_stderr(err):
            code=cli_main(list(map(str,argv)))
        response=json.loads(out.getvalue())
        (args.evidence/('batch-'+label+'.stdout.json')).write_text(out.getvalue(),encoding='utf-8')
        if err.getvalue():(args.evidence/('batch-'+label+'.stderr.txt')).write_text(err.getvalue(),encoding='utf-8')
        commands.append({'id':label,'argv':list(map(str,argv)),'exit_code':code,'seconds':round(time.monotonic()-started,4)})
        if code or not response['ok']:raise RuntimeError((label,response))

    def native(argv):
        done=subprocess.run(list(map(str,argv)),cwd=scratch,capture_output=True,timeout=120,
            creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        if done.returncode:raise RuntimeError(done.stderr.decode('utf-8','replace')[-2000:])
        return done.stdout

    try:
        for i,row in enumerate(rows,1):
            look_id=row['id'];preview=previews/(look_id+'.png');video=videos/(look_id+'.mp4')
            cli('inspect-'+look_id,['look','inspect','--id',look_id])
            cli('preview-'+look_id,['look','preview','--id',look_id,'--output',preview])
            raw,_=looks._payload(row);(scratch/'look.cube').write_bytes(raw)
            native(['ffmpeg','-v','error','-nostdin','-threads','1','-filter_threads','1',
                '-i',args.assets/'original.mp4','-vf',"lut3d=file='look.cube':interp=tetrahedral",
                '-c:v','libx264','-preset','veryfast','-crf','20','-pix_fmt','yuv420p','-c:a','copy',video])
            probe=json.loads(native(['ffprobe','-v','error','-count_frames','-show_streams','-of','json',video]))
            stream=next(s for s in probe['streams'] if s['codec_type']=='video')
            assert (stream['width'],stream['height'],int(stream['nb_read_frames']))==(480,300,12)
            decoded=native(['ffmpeg','-v','error','-threads','1','-i',video,'-f','rawvideo','-pix_fmt','rgb24','pipe:1'])
            assert len(decoded)==480*300*3*12
            source=upstream[row['source']['path']]
            output=scratch/'upstream.png';output.unlink(missing_ok=True)
            if source.suffix=='.png':
                argv=['ffmpeg','-v','error','-threads','1','-filter_complex_threads','1','-i',args.assets/'reference.png',
                    '-i',source,'-filter_complex','[0:v][1:v]haldclut=interp=tetrahedral','-frames:v','1','-update','1',output]
            else:
                (scratch/'upstream.cube').write_bytes(gzip.decompress(source.read_bytes()) if source.suffix=='.gz' else source.read_bytes())
                argv=['ffmpeg','-v','error','-threads','1','-filter_threads','1','-i',args.assets/'reference.png',
                    '-vf',"lut3d=file='upstream.cube':interp=tetrahedral",'-frames:v','1','-update','1',output]
            native(argv)
            difference=np.abs(np.asarray(Image.open(preview).convert('RGB')).astype('int16')-np.asarray(Image.open(output).convert('RGB')).astype('int16'))
            results.append({'id':look_id,'preview_sha256':sha(preview),'native_video_sha256':sha(video),
                'decoded_first_frame_sha256':hashlib.sha256(decoded[:480*300*3]).hexdigest(),
                'decoded_all_frames_sha256':hashlib.sha256(decoded).hexdigest(),'frames':12,
                'upstream_native_max_abs_code_error':int(difference.max()),'upstream_native_mean_abs_code_error':float(difference.mean()),
                'license_spdx':row['license']['spdx']})
            if i%20==0:
                save('batch-presets.json',results);save('batch-commands.json',commands)
                print(json.dumps({'native_looks_verified':i,'total':500}),flush=True)
        for field in ('preview_sha256','decoded_first_frame_sha256'):
            assert len({r[field] for r in results})==500,field
        save('batch-presets.json',results);save('batch-commands.json',commands)
        report={'status':'passed','installed_in_process_cli_commands':len(commands),'native_still_previews':500,
            'native_filter_videos':500,'decoded_frames_per_video':12,'upstream_native_comparisons':500,
            'unique_preview_hashes':500,'unique_decoded_first_frames':500,
            'module':str(Path(looks.__file__).resolve()),'source_fallback':False,
            'full_project_render_jobs_in_this_batch':0,'synthetic_input':True,'human_listening':False,'natural_footage_acceptance':False}
        save('batch-verification.json',report);print(json.dumps(report))
    except Exception as exc:
        save('batch-failure.json',{'status':'failed','completed':len(results),'error':str(exc)})
        raise


if __name__=='__main__':main()
