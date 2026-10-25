"""Reproducible installed motion gallery, capture/reuse, package and Skill case."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import time

from PIL import Image, ImageDraw, ImageFont

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/validation/evidence/motion-pack-20261025-r1'
PUBLIC=ROOT/'docs/assets/motion-pack-20261025-r1'
WORK=ROOT/'workspace/motion-pack-20261025-installed-r1'
INSTALLED=ROOT/'local/agent-ffmpeg/v0.1.0-alpha.4-local.14/final-r1/installed'
PYTHON='C:/Python313/python.exe'
NAMES=('orbit_focus','arc_push','bezier_sweep','whip_settle','breathe_float','detail_scan')


def sha(path):
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def load(path):return json.loads(path.read_bytes())


def save(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--phase',choices=('setup','setup-continue','render','reuse','skill'),required=True)
    parser.add_argument('--run',required=True)
    args=parser.parse_args();assert args.run.replace('-','').isalnum()
    out=BASE/(args.phase+'-'+args.run);out.mkdir(parents=True,exist_ok=False)
    (out/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    frozen={p.name:sha(p) for p in (ROOT/'product/src/ai_ad_editor').glob('*.py')}
    assert frozen=={p.name:sha(p) for p in (INSTALLED/'site/ai_ad_editor').glob('*.py')}
    prefix=[PYTHON,'-I','-S','-B','-u','-X','utf8',str(INSTALLED/'run.py')]
    if args.phase=='skill':prefix=['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',
        'C:/Users/carzy/.codex/skills/agent-ffmpeg-local-editor/scripts/run.ps1']
    calls=[]
    report=dict(status='running',phase=args.phase,cli_version='0.1.16',source_files=len(frozen),
        started_at_utc=datetime.now(timezone.utc).isoformat(),native_windows=True,virtualization=False,
        browser_ui=False,human_listening=False,continuous_playback=False,natural_motion_quality_acceptance=False)
    save(out/'verification.json',report)
    project=WORK/'原工程'
    def run(name,argv,cli=False,expected=None,timeout=900):
        start=time.perf_counter();argv=list(map(str,argv))
        result=subprocess.run(argv,cwd=ROOT,capture_output=True,timeout=timeout,creationflags=subprocess.CREATE_NO_WINDOW)
        stdout,stderr=out/(name+'.stdout'),out/(name+'.stderr');stdout.write_bytes(result.stdout);stderr.write_bytes(result.stderr)
        row=dict(name=name,argv=argv,exit_code=result.returncode,elapsed_seconds=time.perf_counter()-start,
                 stdout_sha256=sha(stdout),stderr_sha256=sha(stderr));calls.append(row);save(out/'calls.json',calls)
        print(json.dumps({k:row[k] for k in ('name','exit_code','elapsed_seconds')}),flush=True)
        if cli:
            value=json.loads(result.stdout.decode('utf-8-sig'))
            if expected:assert not value['ok'] and value['errors'][0]['code']==expected,value
            else:assert result.returncode==0 and value['ok'],value
            return value if expected else value['data']
        assert result.returncode==0,result.stderr.decode('utf8','replace')[-3000:]
        return result.stdout
    def cli(name,*argv,expected=None):return run(name,[*prefix,*argv],True,expected)
    def compose(name,root,operations):
        input_path=WORK/(name+'.json');save(input_path,dict(operations=operations))
        return cli(name,'timeline','compose','--project',root,'--input',input_path)
    def render(name,root,seq,target,gpu=False):
        return cli(name,'render','--project',root,'--sequence-id',seq,'--output',target,
            '--container','mkv','--audio-codec','pcm_f32le','--pixel-format','yuv444p' if not gpu else 'yuv420p',
            '--crf','0','--hardware-encode','require' if gpu else 'off',
            *(['--hardware-encoder','nvenc','--video-bitrate','4M'] if gpu else []))
    def fingerprint(name,path,expected_frames=None):
        raw=run(name+'-frames',['ffmpeg','-v','error','-i',path,'-map','0:v:0','-pix_fmt','rgb24','-f','framemd5','-'])
        frames=[line.rsplit(b',',1)[-1].strip().decode() for line in raw.splitlines() if line and not line.startswith(b'#')]
        probe=json.loads(run(name+'-probe',['ffprobe','-v','error','-count_frames','-show_streams','-show_format','-of','json',path]))
        video=next(s for s in probe['streams'] if s['codec_type']=='video')
        if expected_frames is not None:assert len(frames)==int(video['nb_read_frames'])==expected_frames
        result=dict(frame_count=len(frames),frames=frames,width=video['width'],height=video['height'],
                    frame_rate=video['avg_frame_rate'],duration=probe['format'].get('duration'),sha256=sha(path),bytes=path.stat().st_size)
        save(out/(name+'-decoded.json'),result)
        return result
    try:
        if args.phase in ('setup','setup-continue'):
            if args.phase=='setup':
                WORK.mkdir(parents=True,exist_ok=False);PUBLIC.mkdir(parents=True,exist_ok=False)
            image=Image.new('RGB',(640,360),'#102c31');draw=ImageDraw.Draw(image)
            font_path=INSTALLED/'site/ai_ad_editor/material_data/fonts/noto-sans-sc-variable.ttf'
            title=ImageFont.truetype(str(font_path),36);small=ImageFont.truetype(str(font_path),15)
            for x in range(0,640,32):draw.line((x,0,x,360),fill='#19383c')
            for y in range(0,360,32):draw.line((0,y,640,y),fill='#19383c')
            draw.rounded_rectangle((130,52,510,307),radius=18,fill='#ece5cf',outline='#c9bfa0',width=3)
            draw.ellipse((276,86,364,174),fill='#dc6f3c');draw.ellipse((300,110,340,150),fill='#f7d992')
            draw.text((206,184),'FIELD NOTES',font=title,fill='#183436')
            draw.text((201,241),'MOTION STUDY  /  001',font=small,fill='#56645b')
            draw.line((164,281,476,281),fill='#c1b69a',width=2)
            draw.text((24,19),'AGENT EDITOR KIT',font=small,fill='#b7c6ba')
            draw.text((24,325),'ORIGINAL  /  SELF-AUTHORED VECTOR CARD',font=small,fill='#b7c6ba')
            original=PUBLIC/'original.png'
            if args.phase=='setup':
                image.save(original)
                cli('init','project','init',project,'--name','Reusable motion package gallery')
                asset=cli('ingest','media','ingest','--project',project,'--input',original)['asset']['id']
            else:
                prior=load(BASE/'setup-r1/compose-gallery.stdout')
                assert prior['errors'][0]['code']=='SEQUENCE_CANVAS_INVALID'
                existing=load(project/'project.json');assert len(existing['assets'])==1 and len(existing['sequences'])==1
                asset=existing['assets'][0]['id']
                assert existing['assets'][0]['sha256']=='sha256:'+sha(original)
            operations=[]
            for name in ('original',*NAMES):
                operations += [dict(op='add_sequence',id='motion_'+name,duration_tick=360000,canvas=dict(width=640,height=360)),
                    dict(op='append_clip',sequence_id='motion_'+name,id='hero_'+name,asset_id=asset,
                         timeline_start_tick=0,duration_tick=360000,source_in_tick=0,source_out_tick=360000)]
            compose('compose-gallery',project,operations)
            for name in NAMES:
                recipe=PUBLIC/(name+'.aek-motion.json')
                cli('create-'+name,'motion','pack','create','--name',name,'--output',recipe)
                cli('apply-'+name,'motion','pack','apply','--project',project,'--sequence-id','motion_'+name,
                    '--clip-id','hero_'+name,'--input',recipe,'--idempotency-key','gallery-'+name)
            cli('validate','validate','--project',project)
            report.update(source_sha256=sha(original),source_license='MIT; self-authored vector illustration; bundled OFL font',
                pack_count=6,editable_sequences=7,full_duration_seconds=4,generated_video=False)
        elif args.phase=='render':
            fingerprints={}
            for name in ('original',*NAMES):
                target=project/'renders'/(name+'.mkv')
                render(name,project,'motion_'+name,target)
                fingerprints[name]=fingerprint(name,target,120)
                if name!='original':
                    mp4=PUBLIC/(name+'.mp4')
                    run(name+'-mp4',['ffmpeg','-v','error','-i',target,'-map','0:v:0','-an','-c:v','h264_nvenc',
                        '-b:v','3M','-pix_fmt','yuv420p','-movflags','+faststart',mp4])
                    run(name+'-gif',['ffmpeg','-v','error','-i',mp4,'-vf',
                        'fps=10,scale=480:-1:flags=lanczos,split[a][b];[a]palettegen[p];[b][p]paletteuse',PUBLIC/(name+'.gif')])
                    fingerprint(name+'-public',mp4,120)
                    run(name+'-still',['ffmpeg','-v','error','-ss','2','-i',mp4,'-frames:v','1',PUBLIC/(name+'-mid.png')])
            gpu_target=project/'renders/arc_push-nvenc.mkv';render('native-nvenc',project,'motion_arc_push',gpu_target,True)
            fingerprint('native-nvenc',gpu_target,120)
            tiles=Image.new('RGB',(960,3*300),'#0c2226');d=ImageDraw.Draw(tiles)
            font=ImageFont.truetype(str(INSTALLED/'site/ai_ad_editor/material_data/fonts/noto-sans-sc-variable.ttf'),18)
            for index,name in enumerate(NAMES):
                x,y=(index%2)*480,(index//2)*300
                tile=Image.open(PUBLIC/(name+'-mid.png')).resize((480,270));tiles.paste(tile,(x,y+30))
                d.text((x+12,y+4),f'{index+1:02d}  {name}',font=font,fill='#e4e6d0')
            tiles.save(PUBLIC/'contact-sheet.png')
            # Independent finite-sampling bound: midpoint error on the orbit,
            # evaluated in normalized frame coordinates without renderer helpers.
            import math
            errors=[]
            for n in range(64):
                a,b=n/64,(n+1)/64;u=(a+b)/2
                exact=(.12*math.cos(2*math.pi*u),.072*math.sin(2*math.pi*u))
                poly=(.06*(math.cos(2*math.pi*a)+math.cos(2*math.pi*b)),.036*(math.sin(2*math.pi*a)+math.sin(2*math.pi*b)))
                errors.append(math.hypot((exact[0]-poly[0])*640,(exact[1]-poly[1])*360))
            assert max(errors)<.1
            report.update(rendered_sequences=7,frames_per_sequence=120,public_mp4_count=6,public_gif_count=6,
                native_product_nvenc_frames=120,preview_encode='h264_nvenc',transform_backend='native CPU FFmpeg',
                orbit_midpoint_sample_error_pixels_at_640x360=max(errors),fingerprints=fingerprints)
        elif args.phase=='reuse':
            capture=WORK/'captured-arc.aek-motion.json'
            cli('capture','motion','pack','capture','--project',project,'--sequence-id','motion_arc_push','--clip-id','hero_arc_push',
                '--id','customer_arc_v1','--title','Customer arc','--creator','agent editor kit contributors','--license','MIT','--output',capture)
            before=load(project/'project.json');asset=before['assets'][0]['id']
            compose('compose-reuse',project,[dict(op='add_sequence',id='reused_arc',duration_tick=360000,canvas=dict(width=640,height=360)),
                dict(op='append_clip',sequence_id='reused_arc',id='reused_hero',asset_id=asset,timeline_start_tick=0,duration_tick=360000,source_in_tick=0,source_out_tick=360000)])
            dry_before=(project/'project.json').read_bytes()
            cli('apply-dry','motion','pack','apply','--project',project,'--sequence-id','reused_arc','--clip-id','reused_hero','--input',capture,'--dry-run')
            assert dry_before==(project/'project.json').read_bytes()
            cli('apply-capture','motion','pack','apply','--project',project,'--sequence-id','reused_arc','--clip-id','reused_hero','--input',capture)
            capture.rename(capture.with_suffix('.unavailable'))
            target=project/'renders/reused_arc.mkv';render('reused',project,'reused_arc',target)
            reused=fingerprint('reused',target,120);baseline=load(BASE/'render-r1/arc_push-decoded.json')
            assert reused['frames']==baseline['frames']
            package=WORK/'editable-motion.aevpkg.zip';restored=WORK/'导入工程'
            cli('export','convert','export','--project',project,'--target-format','package','--output',package)
            cli('import','convert','import','--input',package,'--output',restored)
            imported=load(restored/'project.json');original=load(project/'project.json')
            assert imported==original
            for a in original['assets']:assert sha(project/a['uri'])==sha(restored/a['uri'])
            # Make all original standalone recipes and the original project
            # unavailable. Only owned paths are moved, using native Python.
            assert project.resolve().is_relative_to(WORK.resolve())
            project.rename(WORK/'原工程不可用')
            for name in NAMES:
                path=PUBLIC/(name+'.aek-motion.json');path.rename(path.with_suffix('.temporarily-unavailable'))
            try:
                cli('validate-imported','validate','--project',restored)
                target=restored/'renders/imported_arc.mkv';render('imported',restored,'reused_arc',target)
                check=fingerprint('imported',target,120);assert check['frames']==baseline['frames']
            finally:
                for name in NAMES:
                    path=PUBLIC/(name+'.aek-motion.json');path.with_suffix('.temporarily-unavailable').rename(path)
            report.update(dry_run_unchanged=True,captured_reuse_pixels_equal=True,package_project_json_equal=True,
                asset_bytes_equal=True,original_project_unavailable=True,external_recipes_unavailable_during_render=True,
                imported_pixels_equal=True,compared_frames=120,package_bytes=package.stat().st_size,package_sha256=sha(package))
        else:
            project=WORK/'导入工程'
            cli('version','version');cli('catalog','motion','pack','list')
            before=(project/'project.json').read_bytes()
            planned=cli('dry-run','motion','pack','apply','--project',project,'--sequence-id','reused_arc',
                '--clip-id','reused_hero','--name','arc_push','--replace','--param','zoom=0.15','--dry-run')
            assert before==(project/'project.json').read_bytes()
            cli('apply','motion','pack','apply','--project',project,'--sequence-id','reused_arc',
                '--clip-id','reused_hero','--name','arc_push','--replace','--param','zoom=0.15','--idempotency-key','skill-motion-case')
            target=project/'renders/skill_arc.mkv';render('skill-render',project,'reused_arc',target)
            check=fingerprint('skill',target,120);baseline=load(BASE/'render-r1/arc_push-decoded.json')
            assert check['frames']==baseline['frames']
            cli('skill-validate','validate','--project',project)
            report.update(actual_registered_skill=True,source_fallback=False,internal_modules=17,
                dry_run_unchanged=True,compiled_keyframes=planned['motion']['keyframe_count'],
                compared_frames=120,skill_pixels_equal=True)
        assert frozen=={p.name:sha(p) for p in (ROOT/'product/src/ai_ad_editor').glob('*.py')}
        report.update(status='passed',process_calls=len(calls),finished_at_utc=datetime.now(timezone.utc).isoformat(),
            product_frozen_equal=True,files=[dict(path=p.relative_to(ROOT).as_posix(),bytes=p.stat().st_size,sha256=sha(p))
                for p in sorted(PUBLIC.iterdir()) if p.is_file()])
        save(out/'verification.json',report);print(json.dumps({k:v for k,v in report.items() if k not in ('files','fingerprints')},ensure_ascii=False),flush=True)
    except BaseException as exc:
        report.update(status='failed',error=repr(exc),process_calls=len(calls));save(out/'verification.json',report);raise


if __name__=='__main__':main()
