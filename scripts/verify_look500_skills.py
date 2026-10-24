"""Verify all registered Skill formats and edit through the discovery launcher."""
from pathlib import Path
import importlib.util
import json
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]


def save(path,value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')


def main():
    evidence=ROOT/'docs/validation/evidence/look500-20261024-r1/skills'
    if evidence.exists():raise ValueError('Existing Skill evidence is preserved')
    evidence.mkdir(parents=True)
    manifest=json.loads((ROOT/'agent-ffmpeg-local-install-manifest.json').read_bytes())
    spec=importlib.util.spec_from_file_location('skill_verifier',ROOT/'scripts/verify_agent_ffmpeg_local.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    formats=module.validate_registered_skills(manifest);save(evidence/'registered-skills.json',formats)
    launcher=Path(manifest['codex_skills_directory'])/'agent-ffmpeg-local-editor/scripts/run.ps1'
    prefix=['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',str(launcher)]
    commands=[]
    def cli(label,argv,expected=0):
        command=prefix+list(map(str,argv));started=time.monotonic()
        result=subprocess.run(command,cwd=ROOT,capture_output=True,timeout=240,
            creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
        (evidence/(label+'.stdout.json')).write_bytes(result.stdout)
        (evidence/(label+'.stderr.txt')).write_bytes(result.stderr)
        response=json.loads(result.stdout)
        commands.append({'id':label,'argv':command,'exit_code':result.returncode,'expected':expected,'seconds':round(time.monotonic()-started,3)})
        save(evidence/'commands.json',commands)
        assert result.returncode==expected and response['ok']==(expected==0),(label,response)
        return response
    cli('version',['version'])
    listed=cli('look-list',['look','list']);assert listed['data']['count']==500
    cli('look-search',['look','list','--query','黑白'])
    cli('look-inspect',['look','inspect','--id','t3-kodak-gold-200'])
    work=ROOT/'local/agent-ffmpeg/look500-skill-check-20261024'
    cli('project-init',['project','init',work,'--name','Skill 风格 500'])
    assets=ROOT/'docs/assets/look500-20261024-r1'
    ingested=cli('ingest',['media','ingest','--project',work,'--input',assets/'original.mp4',
        '--source-url','local://look-preset-generated/original.mp4','--license-spdx','CC0-1.0',
        '--license-url',assets/'LICENSE.txt','--evidence',assets/'LICENSE.txt',
        '--verification-status','verified','--permitted-use','commercial_ad'])
    asset=ingested['data']['asset']['id']
    save(work/'changes.json',{'sequence_id':'seq_main','operations':[
        {'op':'append_clip','track_id':track,'asset_id':asset,'source_in_tick':0,'source_out_tick':90000,'duration_tick':90000}
        for track in ('track_video_1','track_audio_1')]})
    cli('compose',['timeline','compose','--project',work,'--input',work/'changes.json'])
    cli('look-preview',['look','preview','--id','t3-kodak-gold-200','--output',work/'gold-preview.png','--strength','.65'])
    cli('look-dry',['look','apply','--project',work,'--id','t3-kodak-gold-200','--global','--strength','.65','--dry-run'])
    cli('look-apply',['look','apply','--project',work,'--id','t3-kodak-gold-200','--global','--strength','.65'])
    cli('validate',['validate','--project',work])
    video=work/'renders/Skill 核验 成片.mp4'
    cli('render',['render','--project',work,'--output',video,'--width',360,'--height',640,'--publish'])
    cli('quality',['quality','check','--project',work,'--input',video,'--width',360,'--height',640,'--require-audio'])
    for license in ('CC-BY-SA-4.0','CC0-1.0'):
        row=next(r for r in listed['data']['looks'] if r['license']['spdx']==license and r['category']!='film-bw')
        label=row['id']
        cli('inspect-'+label,['look','inspect','--id',label])
        cli('preview-'+label,['look','preview','--id',label,'--output',work/(label+'.png'),'--strength','.65'])
        applied=cli('apply-'+label,['look','apply','--project',work,'--id',label,'--global','--strength','.65'])
        assert applied['data']['resource']['rights']['license_spdx']==license
        output=work/'renders'/(label+'.mp4')
        cli('render-'+label,['render','--project',work,'--output',output,'--width',360,'--height',640,'--publish'])
        cli('quality-'+label,['quality','check','--project',work,'--input',output,'--width',360,'--height',640,'--require-audio'])
    cli('unknown-refused',['look','inspect','--id','unknown'],3)
    save(evidence/'verification.json',{'status':'passed','release':manifest['release'],'registered_skills':len(formats),
        'skill_launcher_commands':len(commands),'successes':len(commands)-1,'expected_refusals':1,
        'local_preset_count':500,'launcher':str(launcher),'video':str(video),'native_windows':True,
        'runtime_network_downloads':0,'natural_footage_acceptance':False,'human_listening':False})
    print(json.dumps({'ok':True,'registered_skills':len(formats),'skill_commands':len(commands)}))


if __name__=='__main__':main()
