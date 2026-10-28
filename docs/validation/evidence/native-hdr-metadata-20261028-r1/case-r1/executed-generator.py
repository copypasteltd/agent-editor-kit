"""C54: registered installed Skill, actual GPU edit/HEVC SEI and package replay."""
from pathlib import Path
from fractions import Fraction
from datetime import datetime,timezone
import argparse,hashlib,json,shutil,subprocess,time
from PIL import Image,ImageDraw,ImageFont

ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'docs/validation/evidence/native-hdr-metadata-20261028-r1'
SKILL=Path('C:/Users/carzy/.codex/skills/agent-ffmpeg-local-editor/scripts/run.ps1')
DECLARATION={'mastering_display':{'red_xy':[.68,.32],'green_xy':[.265,.69],
    'blue_xy':[.15,.06],'white_xy':[.3127,.329],'min_luminance_nits':.0001,'max_luminance_nits':1000},
    'content_light':{'max_cll_nits':1000,'max_fall_nits':400}}
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def save(p,v):Path(p).write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
def load(p):return json.loads(Path(p).read_bytes())
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--run',required=True);a=ap.parse_args();assert a.run.replace('-','').isalnum()
    out=BASE/('case-'+a.run);out.mkdir(exist_ok=False);(out/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    work=ROOT/'local/agent-ffmpeg'/('native-hdr-metadata-case-'+a.run);work.mkdir(exist_ok=False)
    public=ROOT/('docs/assets/native-hdr-metadata-20261028-'+a.run);public.mkdir(exist_ok=False)
    project=work/'project';calls=[];checks=[]
    ffmpeg=shutil.which('ffmpeg');ffprobe=shutil.which('ffprobe');assert ffmpeg and ffprobe
    def run(name,argv,cli=False):
        argv=list(map(str,argv));start=time.perf_counter()
        r=subprocess.run(argv,cwd=ROOT,capture_output=True,timeout=1500,creationflags=subprocess.CREATE_NO_WINDOW)
        stdout=(out if cli else work)/(name+('.stdout.json' if cli else '.bin'));stdout.write_bytes(r.stdout)
        stderr=out/(name+'.stderr.txt');stderr.write_bytes(r.stderr)
        calls.append(dict(id=name,argv=argv,exit_code=r.returncode,seconds=time.perf_counter()-start,
                          stdout_bytes=len(r.stdout),stdout_sha256=sha(stdout),stderr_sha256=sha(stderr)))
        save(out/'calls.json',calls);print(json.dumps(dict(id=name,exit_code=r.returncode)),flush=True)
        assert r.returncode==0,(name,r.stdout[-3000:],r.stderr[-3000:])
        if cli:
            value=json.loads(r.stdout);assert value['ok'] and value['provenance']['cli_version']=='0.1.44';return value['data']
        return r.stdout
    def invoke(name,*args):return run(name,['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',SKILL,*args],True)
    def check(name,ok,**more):
        checks.append(dict(name=name,ok=bool(ok),**more));save(out/'checks.json',checks);assert ok,name
    def decoded(name,movie,audio=False):return run(name,[ffmpeg,'-nostdin','-v','error','-i',movie,
        *(['-map','0:a:0','-vn','-c:a','pcm_f32le','-f','f32le'] if audio else
          ['-map','0:v:0','-an','-pix_fmt','yuv420p10le','-fps_mode','passthrough','-f','rawvideo']),'pipe:1'])
    def render(name,root):
        r=invoke(name,'render','--project',root,'--output',root/('renders/'+name+'.mkv'),
            '--hardware-encode','off','--projection-acceleration','require','--projection-device','0.0')
        manifest=load(r['manifest']);gpu=manifest['delivery']['pixel_pipeline']['projection_acceleration']
        check(name+'-actual-GPU',gpu['operations']['glow']==48 and gpu['worker_closed'] and gpu['shared_handles_closed']
              and gpu['control']['threads_closed'] and gpu['control']['streams_closed'])
        return r,manifest
    report=dict(status='running',native_windows=True,virtualization=False,registered_skill=True,
        source_fallback=False,started_at_utc=datetime.now(timezone.utc).isoformat(),
        content_peaks_measured=False,HDR_monitor_accepted=False,human_listening=False,continuous_human_playback=False)
    try:
        assert invoke('version','version')['cli_version']=='0.1.44'
        caps=invoke('capabilities','capabilities');check('new-capability',caps['capabilities']['native_hdr10_static_metadata']['status']=='implemented_with_limits')
        original=ROOT/'docs/assets/native-hdr-20261027-r3/editable-native-hdr.aevpkg.zip'
        invoke('import-original','convert','import','--input',original,'--output',project)
        p=load(project/'project.json');p['project']['name']='C54 actual HDR10 static metadata'
        p['settings']['output'].update(video=dict(codec='libx265',preset='ultrafast',crf=16,pixel_format='yuv420p10le'),hdr10=DECLARATION)
        save(project/'project.json',p);before=(project/'project.json').read_bytes()
        invoke('validate','validate','--project',project)
        plan=invoke('plan','render','--project',project,'--output',project/'renders/plan.mkv','--dry-run',
                    '--hardware-encode','off','--projection-acceleration','require','--projection-device','0.0')
        check('dry-run-declared-flags','-x265-params' in plan['plan']['command'] and not (project/'renders/plan.mkv').exists())
        first,manifest=render('hdr10',project);master=Path(first['path'])
        receipt=manifest['delivery']['hdr10_static_metadata']
        check('production-prefix-verification',receipt['status']=='verified' and receipt['declaration']==DECLARATION
              and receipt['scope']=='decoded-prefix-only' and 0<receipt['verified_decoded_frames']<=32,
              decoded_frames=receipt['verified_decoded_frames'])
        raw=json.loads(run('independent-all-frame-sei',[ffprobe,'-v','error','-select_streams','v:0',
            '-show_frames','-show_streams','-show_entries',
            'stream=codec_name,pix_fmt,color_primaries,color_transfer,color_space,color_range:frame=best_effort_timestamp:frame_side_data',
            '-of','json',master]));save(out/'independent-all-frame-sei.json',raw)
        expected={'red_x':Fraction(34000,50000),'red_y':Fraction(16000,50000),'green_x':Fraction(13250,50000),
            'green_y':Fraction(34500,50000),'blue_x':Fraction(7500,50000),'blue_y':Fraction(3000,50000),
            'white_point_x':Fraction(15635,50000),'white_point_y':Fraction(16450,50000),
            'min_luminance':Fraction(1,10000),'max_luminance':Fraction(10000000,10000)}
        for frame in raw['frames']:
            sides=frame['side_data_list'];d=next(s for s in sides if s['side_data_type']=='Mastering display metadata')
            light=next(s for s in sides if s['side_data_type']=='Content light level metadata')
            assert {k:Fraction(d[k]) for k in expected}==expected
            assert light['max_content']==1000 and light['max_average']==400
        check('independent-all-48-frames',len(raw['frames'])==48)
        frame=invoke('preview-frame','preview','frame','--project',project,'--frame','24','--height','360')
        preview=invoke('preview-range','preview','range','--project',project,'--start-frame','0','--end-frame','48','--height','360')
        check('SDR-view-does-not-change-author',(project/'project.json').read_bytes()==before and not preview['request']['HDR_reference_preserved'])
        view=json.loads(run('independent-SDR-probe',[ffprobe,'-v','error','-select_streams','v:0','-show_frames','-show_streams',
            '-show_entries','stream=codec_name,pix_fmt,color_transfer:frame_side_data','-of','json',preview['path']]))
        check('SDR-copy-has-no-HDR-SEI',view['streams'][0]['color_transfer']=='bt709' and not
              [s for f in view['frames'] for s in f.get('side_data_list',[]) if s['side_data_type'] in
               ('Mastering display metadata','Content light level metadata')])
        package=public/'editable-hdr10.aevpkg.zip';invoke('export','convert','export','--project',project,'--output',package,'--target-format','package')
        restored=work/'restored';invoke('import-replay','convert','import','--input',package,'--output',restored)
        invoke('validate-replay','validate','--project',restored)
        check('portable-declarations',load(restored/'project.json')['settings']['output']['hdr10']==DECLARATION)
        second,replayed=render('replayed',restored)
        v1=decoded('original-all-video',master);v2=decoded('replayed-all-video',second['path'])
        a1=decoded('original-all-PCM',master,True);a2=decoded('replayed-all-PCM',second['path'],True)
        check('all-decoded-video-identical',v1==v2 and len(v1)==48*640*360*3,decoded_frames=48,bytes=len(v1))
        check('all-PCM-identical',a1==a2 and len(a1)==384000*4 and any(a1),samples=384000,bytes=len(a1))
        for source,target in [(master,'hdr10-master.mkv'),(Path(first['manifest']),'hdr10-master.mkv.manifest.json'),
                              (Path(preview['path']),'sdr-preview.mp4'),(Path(frame['path']),'sdr-frame.png')]:
            shutil.copyfile(source,public/target)
        save(public/'declaration.json',DECLARATION)
        gif=public/'sdr-view.gif';run('gif',[ffmpeg,'-nostdin','-v','error','-i',public/'sdr-preview.mp4',
            '-vf','fps=6,scale=480:-1:flags=lanczos,split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse',
            '-loop','0',gif])
        with Image.open(gif) as im:
            count=im.n_frames;duration=0
            for i in range(count):im.seek(i);duration+=im.info['duration']
        check('actual-GIF-clock',count==24 and abs(duration-4000)<=10,frames=count,duration_ms=duration)
        actual=Image.open(public/'sdr-frame.png').convert('RGB');sheet=Image.new('RGB',(960,720),'#111927')
        sheet.paste(actual.resize((960,540)),(0,0));d=ImageDraw.Draw(sheet);font=ImageFont.load_default(size=20)
        for i,line in enumerate(['ACTUAL SDR VIEW / HDR10 MASTER IS SEPARATE',
            'Declared P3-D65 mastering: 0.0001 - 1000 cd/m2',
            'Declared MaxCLL 1000 / MaxFALL 400 | not measured peaks',
            '48 frames verified in this case | production checks first32 packets']):
            d.text((22,555+i*35),line,font=font,fill='#f0f4fc')
        sheet.save(public/'comparison.png')
        (public/'SOURCE.txt').write_text('C54 / agent editor kit CLI0.1.44\nOriginal contributor-generated CC0 diagnostic media reused from C50:\n'
            '../native-hdr-20261027-r3/SOURCE.txt\nActual local OpenCL composition and CPU x265 encoding; not a natural HDR-monitor assessment.\n'
            'The PNG/GIF/MP4 are explicitly mapped SDR viewing copies; the HEVC master is PQ/BT2020/10bit.\n'
            'Mastering and CLL values are author declarations, not measured peaks. No human continuous playback/listening claimed.\n',encoding='utf8')
        inventory=[dict(path=p.name,bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(public.iterdir()) if p.is_file()]
        save(public/'media-manifest.json',dict(case='C54',files=inventory,public_media_rights='Original contributor-generated CC0 diagnostic media',
            HDR_monitor_accepted=False,human_listening=False,continuous_human_playback=False,content_peaks_measured=False))
        report.update(status='passed',checks=checks,project=str(project),restored=str(restored),public_directory=str(public),
            prefix_frames=receipt['verified_decoded_frames'],independent_case_frames=48,decoded_video_bytes=len(v1),PCM_scalar_samples=384000,
            GPU_glow_calls_per_render=48,render_count=2,cli_calls=sum(c['id'] in [v['id'] for v in calls] and c['argv'][0]=='powershell.exe' for c in calls),
            files=inventory,finished_at_utc=datetime.now(timezone.utc).isoformat())
        save(out/'verification.json',report);print(json.dumps({k:v for k,v in report.items() if k not in ('files','checks')},ensure_ascii=False),flush=True)
    except BaseException as e:
        report.update(status='failed',error=repr(e),checks=checks);save(out/'verification.json',report);raise
if __name__=='__main__':main()
