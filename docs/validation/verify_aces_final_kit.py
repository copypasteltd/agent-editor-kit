"""Independently extract and register the final CLI53 Skill kit while preserving live discovery."""
import argparse,hashlib,json,re,shutil,subprocess,sys,zipfile
from pathlib import Path,PurePosixPath
ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'docs/validation/evidence/aces-delivery-20261029-r1'
def load(p):return json.loads(Path(p).read_bytes())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,v):p.write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')

def main():
    p=argparse.ArgumentParser();p.add_argument('--run',required=True);a=p.parse_args();assert a.run.replace('-','').isalnum()
    assert sys.flags.isolated and sys.flags.no_site
    source=ROOT;package=load(ROOT/'local/agent-ffmpeg/aces-kit-final-r1/package.json')
    kit=Path(package['archive']);assert package['cli_version']=='0.1.53' and sha(kit)==package['sha256']
    out=BASE/('final-kit-'+a.run);out.mkdir(exist_ok=False);(out/'executed-runner.py').write_bytes(Path(__file__).read_bytes())
    home=ROOT/'local/agent-ffmpeg'/('aces-independent-final-kit-'+a.run)/'独立工具 包';home.mkdir(parents=True,exist_ok=False)
    discovery=Path('C:/Users/carzy/.codex/skills/agent-ffmpeg-local-editor');original_target=discovery.resolve()
    live_manifest=ROOT/'agent-ffmpeg-local-install-manifest.json';manifest_pin=sha(live_manifest)
    runtime_path=ROOT/'local/agent-ffmpeg/runtime.json';runtime_pin=sha(runtime_path)
    assert load(live_manifest)['cli_version']=='0.1.53'
    for row in load(live_manifest)['files']:assert sha(ROOT/row['path'])==row['sha256']
    with zipfile.ZipFile(kit) as z:
        inventory=json.loads(z.read('KIT-FILES.json'));assert inventory['cli_version']=='0.1.53' and inventory['skill_count']==1 and inventory['module_count']==17
        names=[r['path'] for r in inventory['files']];assert len(names)==len(set(names))==152 and len(z.namelist())==153 and set(z.namelist())==set(names)|{'KIT-FILES.json'}
        assert sum(Path(n).name=='SKILL.md' for n in names)==1 and sum(n.startswith('skills/') for n in names)==92
        assert {'docs/product/ACES_NATIVE.md','docs/product/ACES_TIMELINE.md'}<=set(names)
        for row in inventory['files']:
            name=row['path'];relative=PurePosixPath(name)
            assert not relative.is_absolute() and '..' not in relative.parts and ':' not in name and '\\' not in name and relative.as_posix()==name
            info=z.getinfo(name);assert not info.is_dir() and ((info.external_attr>>16)&0o170000)!=0o120000
            data=z.read(name);assert len(data)==row['bytes'] and hashlib.sha256(data).hexdigest()==row['sha256']
            if name.startswith('skills/') or name=='agent-ffmpeg-local-install-manifest.json':assert data==(source/name).read_bytes()
            elif name.startswith('docs/') and name.endswith('.md'):
                def externalize(m):
                    target=m[2]
                    if re.match(r'^[a-z]+:',target) or target.startswith('#'):return m.group()
                    plain,mark,fragment=target.partition('#');resolved=(ROOT/name).parent.joinpath(plain).resolve();assert resolved.is_relative_to(ROOT) and resolved.exists()
                    relative=resolved.relative_to(ROOT).as_posix()
                    return m.group() if relative in names else m[1]+'https://github.com/copypasteltd/agent-editor-kit/blob/main/'+relative+(mark+fragment if mark else '')+')'
                assert data==re.sub(r'(!?\[[^\]]*\]\()([^\n)]+)\)',externalize,(ROOT/name).read_text('utf-8')).encode('utf-8'),name
            else:assert data==(ROOT/name).read_bytes()
            target=home/Path(*relative.parts);target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
    runtime=load(runtime_path);devices=load(runtime['community_config']);install=load(BASE/'installation-final-r2/verification.json')
    ps=['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File'];calls=[]
    work=home.parent
    def run(name,argv,cli=False,binary=False):
        argv=list(map(str,argv));r=subprocess.run(argv,cwd=ROOT,capture_output=True,timeout=900,creationflags=subprocess.CREATE_NO_WINDOW)
        destination=(work if binary else out)/(name+('.raw' if binary else '.stdout'))
        destination.write_bytes(r.stdout);(out/(name+'.stderr')).write_bytes(r.stderr)
        calls.append(dict(name=name,argv=argv,exit_code=r.returncode,stdout_sha256=hashlib.sha256(r.stdout).hexdigest()));save(out/'calls.json',calls)
        print(json.dumps(dict(name=name,exit_code=r.returncode)),flush=True);assert r.returncode==0,(name,r.stdout[-1200:],r.stderr[-2000:])
        if cli:
            v=json.loads(r.stdout);assert v['ok'] and v['provenance']['cli_version']=='0.1.53';return v['data']
        return r.stdout
    run('configure',[sys.executable,'-I','-B','-u','-X','utf8',home/'scripts/activate_community_runtime.py',
        '--installed',install['installed'],'--packs',Path(devices['voice']['cpu_pack']).parent,
        '--voice-cuda-lib',devices['voice']['cuda_library_directory'],'--translation-cuda-lib',devices['translation']['cuda_library_directory'],
        '--semantic-config',runtime['semantic_config'],'--verify-timeout-seconds','600'])
    isolated=home.parent/'isolated-discovery'
    run('register',[*ps,home/'register-agent-ffmpeg-local-skills.ps1','-SkillsDirectory',isolated,'-ReceiptPath',out/'registration.json'])
    entry=isolated/'agent-ffmpeg-local-editor';assert entry.resolve()==(home/'skills/agent-ffmpeg-local-editor').resolve()
    def cli(name,*args):return run(name,[*ps,entry/'scripts/run.ps1',*args],True)
    assert cli('version','version')['cli_version']=='0.1.53'
    capabilities=cli('capabilities','capabilities')['capabilities'];assert len(capabilities)==90 and 'native_aces_display' in capabilities
    assert cli('catalog','surface','ocio-configs','--config','aces-2.1')['version']=='2.6.0'
    project=work/'project';reference=ROOT/'docs/assets/aces-installed-20261029-r1'
    cli('import','convert','import','--input',reference/'editable-aces.zip','--output',project)
    cli('validate','validate','--project',project);seq=load(project/'project.json')['sequences'][0]['id']
    movie=project/'renders/kit-aces.mkv';rendered=cli('render','render','--project',project,'--sequence-id',seq,'--output',movie)
    assert rendered['delivery']['pixel_pipeline']['aces_display']['frames']==8 and rendered['delivery']['pixel_pipeline']['ACES_processors_closed']
    before=(project/'project.json').read_bytes()
    frame=cli('frame','preview','frame','--project',project,'--frame','7','--height','128')
    assert sha(frame['path'])==sha(reference/'frame7.png')
    cli('measure','surface','measure','--project',project,'--sequence-id',seq)
    exported=project/'exports/kit-aces.zip';cli('export','convert','export','--project',project,'--output',exported,'--target-format','package')
    replay=work/'replay';cli('reimport','convert','import','--input',exported,'--output',replay)
    again=replay/'renders/kit-aces.mkv';cli('replay-render','render','--project',replay,'--sequence-id',seq,'--output',again)
    ffmpeg=shutil.which('ffmpeg');assert ffmpeg
    def pixels(name,path):return run(name,[ffmpeg,'-nostdin','-v','error','-i',path,'-map','0:v:0','-an','-pix_fmt','yuv444p10le','-f','rawvideo','pipe:1'],binary=True)
    actual=pixels('render-yuv',movie);assert len(actual)==589824 and actual==pixels('replay-yuv',again)==pixels('reference-yuv',reference/'aces.mkv')
    def pcm(name,path):return run(name,[ffmpeg,'-nostdin','-v','error','-i',path,'-map','0:a:0','-vn','-c:a','pcm_f32le','-f','f32le','pipe:1'],binary=True)
    audio=pcm('render-pcm',movie);assert len(audio)==307200 and audio==pcm('replay-pcm',again)==pcm('reference-pcm',reference/'aces.mkv')
    assert before==(project/'project.json').read_bytes() and discovery.resolve()==original_target and sha(live_manifest)==manifest_pin and sha(runtime_path)==runtime_pin
    for row in load(live_manifest)['files']:assert sha(ROOT/row['path'])==row['sha256']
    report=dict(status='passed',kit_sha256=sha(kit),kit_entries=153,inventory_files=152,skill_files=92,public_entries=1,modules=17,
        independently_extracted=True,independent_E_drive_registration=True,actual_registered_kit_used=True,actual_live_discovery_changed=False,live_skill_cli='0.1.53',
        kit_cli='0.1.53',source_fallback=False,new_renders=2,new_model_forwards=0,complete_YUV_equal=True,YUV_bytes=len(actual),
        complete_PCM_equal=True,PCM_bytes=len(audio),PNG_file_byte_equal=True,author_bytes_unchanged_by_readonly_operations=True,ACES_docs_included=True)
    save(out/'verification.json',report);print(json.dumps(report),flush=True)

if __name__=='__main__':main()
