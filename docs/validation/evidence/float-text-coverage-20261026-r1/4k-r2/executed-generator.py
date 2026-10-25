"""Registered-Skill 4K title animation, encoded output and editable delivery."""
import argparse, copy, hashlib, json, shutil, subprocess, sys, time
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/validation/evidence/float-text-coverage-20261026-r1'
INSTALL=ROOT/'local/agent-ffmpeg/v0.1.0-alpha.4-local.21/final-r2/installed'


def sha(path):
    with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--run',required=True);a=ap.parse_args();assert a.run.replace('-','').isalnum()
    out=BASE/('4k-'+a.run);out.mkdir(exist_ok=False)
    (out/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    work=ROOT/'workspace'/('float-text-coverage-20261026-4k-'+a.run);work.mkdir(exist_ok=False)
    public=ROOT/'docs/assets'/('float-text-coverage-20261026-4k-'+a.run);public.mkdir(exist_ok=False)
    sys.path.insert(0,str(INSTALL/'site'))
    from ai_ad_editor.project import create_project,save_project
    from ai_ad_editor.rights import add_record,load_ledger,save_ledger
    from ai_ad_editor.media import ffmpeg_path,ffprobe_path
    from ai_ad_editor.runtime import configure_local_runtime
    from PIL import Image
    configure_local_runtime();native=ffmpeg_path()
    entry=Path('C:/Users/carzy/.codex/skills/agent-ffmpeg-local-editor')
    assert entry.resolve()==(ROOT/'skills/agent-ffmpeg-local-editor').resolve()
    prefix=['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',str(entry/'scripts/run.ps1')]
    report={'status':'running','calls':[],'registered_skill':True,'virtualization':False,'source_fallback':False,
            'continuous_playback':False,'human_listening':False,'natural_quality_accepted':False,'new_model_forwards':0}
    def save():(out/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    def run(name,argv):
        started=time.perf_counter();r=subprocess.run(list(map(str,argv)),cwd=ROOT,capture_output=True,timeout=900,creationflags=subprocess.CREATE_NO_WINDOW)
        (out/(name+'.stdout.log')).write_bytes(r.stdout);(out/(name+'.stderr.log')).write_bytes(r.stderr)
        report['calls'].append(dict(name=name,argv=list(map(str,argv)),exit_code=r.returncode,seconds=time.perf_counter()-started,
            stdout_sha256=hashlib.sha256(r.stdout).hexdigest(),stderr_sha256=hashlib.sha256(r.stderr).hexdigest()))
        save();print(json.dumps({'name':name,'code':r.returncode}),flush=True)
        assert r.returncode==0,(name,r.stdout[-3000:],r.stderr[-3000:]);return r.stdout
    def cli(name,*argv):
        r=json.loads(run(name,[*prefix,*argv]));assert r['ok'];return r
    try:
        root,p=create_project(work/'4K 可编辑 工程','4K native byte coverage and linear text','float_text_4k')
        tps=p['settings']['timebase']['ticks_per_second'];duration=2*tps
        p['settings']['canvas'].update(width=3840,height=2160,background='#142235')
        p['settings']['timebase']['display_fps']={'num':4,'den':1}
        p['settings']['color'].update(primaries='bt709',transfer='iec61966-2-1',matrix='bt709',range='limited')
        p['settings']['output']={'container':'mp4','video':{'codec':'libx264','crf':12,'preset':'ultrafast','pixel_format':'yuv420p'},'audio':{'codec':'aac','bitrate':'128k'}}
        p['settings']['pixel_pipeline']={'engine':'float32-native-v1','working_signal':{'primaries':'bt709','transfer':'linear'},
            'output_signal':{'primaries':'bt709','transfer':'srgb'},'sources':{},'window_frames':2}
        p['settings']['sequence_sampling']={'method':'bilinear','max_working_bytes':768*1024**2}
        font_source=INSTALL/'site/ai_ad_editor/material_data/fonts/noto-sans-sc-variable.ttf'
        font=root/'assets/font.ttf';shutil.copyfile(font_source,font)
        (root/'fonts').mkdir(exist_ok=True);notice=root/'fonts/Noto-Sans-SC-OFL.txt'
        shutil.copyfile(INSTALL/'site/ai_ad_editor/material_data/licenses/google-notosanssc.txt',notice)
        shutil.copyfile(notice,public/'Noto-Sans-SC-OFL.txt')
        p['assets']=[dict(id='font',kind='font',uri='assets/font.ttf',sha256='sha256:'+sha(font),rights_ref='font',probe={'streams':[]})]
        ledger=load_ledger(root);add_record(ledger,dict(asset_id='font',verification_status='verified',source_type='community',
            source_url=str(font_source),license_spdx='OFL-1.1',evidence='fonts/Noto-Sans-SC-OFL.txt',
            license_url='fonts/Noto-Sans-SC-OFL.txt',permitted_uses=['all'],sha256='sha256:'+sha(font),verified_by='bundled-license-catalog'))
        sequence=p['sequences'][0];sequence['duration_tick']=duration
        def title(cid,text,size,y,animation=None,words=None):
            subtitle={'text':text,'style':{'font_asset_id':'font','fontsize':size,'fontcolor':'#e8f0ffed',
                'active_color':'#ffc874ed','box':True,'boxcolor':'#102030b0','boxborderw':24,'borderw':3,
                'bordercolor':'#050c18b0','shadowx':8,'shadowy':8,'shadowcolor':'#00000090',
                'x':'(w-text_w)/2','y':str(y)}}
            if animation:subtitle['animation']=animation
            if words:subtitle['word_timing']=words
            return dict(id=cid,generator={'type':'text'},timeline_start_tick=0,duration_tick=duration,
                source_in_tick=0,source_out_tick=duration,subtitle=subtitle)
        header=title('header','AGENT EDITOR KIT',144,620,{'type':'fade_in','duration':.75})
        center=title('typing','4K LINEAR TEXT',190,960,{'type':'typing','duration':1.5},
            [dict(text='4K',start=0,end=.5),dict(text='LINEAR',start=.5,end=1),dict(text='TEXT',start=1,end=2)])
        footer=title('footer','原生字形 · 分块浮点 · 可编辑交付',90,1360)
        footer['subtitle']['style'].update(box=False,borderw=0,shadowx=0,shadowy=0,fontcolor='#a4bed8dd')
        sequence['tracks']=[dict(id='text'+str(i),kind='subtitle',order=i,clips=[clip]) for i,clip in enumerate((header,center,footer))]
        save_project(root,p);save_ledger(root,ledger);before=copy.deepcopy({k:p[k] for k in ('settings','assets','sequences')})
        assert cli('version','version')['data']['cli_version']=='0.1.23'
        cli('validate','validate','--project',root)
        preview=cli('preview','preview','frame','--project',root,'--frame',4,'--height',540)
        shutil.copyfile(preview['data']['path'],public/'preview.png')
        output=root/'renders/4k-native-text.mp4'
        rendered=cli('render','render','--project',root,'--output',output)
        shutil.copyfile(output,public/output.name)
        pixel=rendered['data']['delivery']['pixel_pipeline']
        assert pixel['transport']['frames']==8
        text=pixel['timeline']['text'];assert len(text['plans'])==3 and text['coverage_conversion']['max_code_error']==0
        (out/'text-receipt.json').write_text(json.dumps(text,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
        run('decode-full',[native,'-nostdin','-v','error','-i',output,'-map','0:v:0','-f','null','-'])
        probe=json.loads(run('probe',[ffprobe_path(),'-v','error','-select_streams','v:0','-count_frames','-show_streams','-of','json',output]))
        stream=probe['streams'][0];assert stream['width']==3840 and stream['height']==2160 and int(stream['nb_read_frames'])==8
        cli('quality','quality','check','--project',root,'--input',output)
        archive=public/'editable-4k-text.aevpkg.zip';cli('export','convert','export','--project',root,'--target-format','package','--output',archive)
        run('gif',[native,'-nostdin','-v','error','-n','-i',output,'-vf',
            'fps=4,scale=960:540:flags=lanczos,split[a][b];[a]palettegen[p];[b][p]paletteuse',public/'4k-native-text.gif'])
        Image.new('RGB',(960,540),(20,34,53)).save(public/'original.png')
        (public/'SOURCE.txt').write_text('CC0-1.0: self-authored text animation and solid background; Noto Sans SC OFL-1.1.\nActual 3840x2160/4fps/2s/8 frames rendered through the registered Skill.\nNo speech or natural-media quality acceptance.\nGenerator: scripts/run_float_text_coverage_4k_20261026.py\n',encoding='utf8',newline='\n')
        after=json.loads((root/'project.json').read_bytes());assert before=={k:after[k] for k in before}
        files=[dict(path=p.relative_to(ROOT).as_posix(),bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(public.iterdir()) if p.is_file()]
        report.update(status='passed',project=str(root),actual_frames=8,width=3840,height=2160,seconds=2,fps=4,
            font_license_preserved=True,original_authoring_unchanged=True,public_files=files,
            native_coverage_rasters=text['native_coverage_rasters'],coverage_cache_hits=text['coverage_cache_hits'],
            native_snapshots=text['native_snapshots'],admission=text['admission'])
        save();print(json.dumps({k:report[k] for k in ('status','actual_frames','width','height','coverage_cache_hits')}),flush=True)
    except BaseException as exc:
        report.update(status='failed',error=repr(exc));save();raise


if __name__=='__main__':main()
