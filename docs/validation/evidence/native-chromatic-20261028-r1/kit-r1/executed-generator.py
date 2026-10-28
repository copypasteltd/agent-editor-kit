"""Independently extract/configure/register r46 and exercise installed chromatic plans."""
from pathlib import Path
import argparse,hashlib,json,re,subprocess,sys,zipfile
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'docs/validation/evidence/native-chromatic-20261028-r1'
ap=argparse.ArgumentParser();ap.add_argument('--run',required=True);a=ap.parse_args();assert a.run.replace('-','').isalnum()
out=BASE/('kit-'+a.run);out.mkdir(exist_ok=False);(out/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
home=ROOT/'local/agent-ffmpeg'/('native-chromatic-kit-'+a.run)/'独立工具 包';home.mkdir(parents=True,exist_ok=False)
kit=ROOT/'docs/skills/agent-editor-kit-community-unified-skill-r46.zip'
def load(p):return json.loads(Path(p).read_bytes())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def save(p,v):(out/p).write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
with zipfile.ZipFile(kit) as z:
    inventory=json.loads(z.read('KIT-FILES.json'));assert inventory['cli_version']=='0.1.45' and inventory['skill_count']==1 and inventory['module_count']==17
    names=[r['path'] for r in inventory['files']];assert len(names)==len(set(names))==135 and set(z.namelist())==set(names)|{'KIT-FILES.json'}
    assert sum(Path(p).name=='SKILL.md' for p in names)==1
    for row in inventory['files']:
        name=row['path'];p=Path(name);assert not p.is_absolute() and '..' not in p.parts and ':' not in name
        data=z.read(name);assert len(data)==row['bytes'] and hashlib.sha256(data).hexdigest()==row['sha256']
        if name.startswith('skills/'):assert data==(ROOT/p).read_bytes()
        if name.startswith('docs/') and name.endswith('.md'):
            def externalize(m):
                target=m[2]
                if re.match(r'^[a-z]+:',target) or target.startswith('#'):return m.group()
                plain,mark,fragment=target.partition('#');resolved=(ROOT/p).parent.joinpath(plain).resolve();assert resolved.is_relative_to(ROOT)
                relative=resolved.relative_to(ROOT).as_posix()
                if relative in names:return m.group()
                assert resolved.exists(),(p,target)
                return m[1]+'https://github.com/copypasteltd/agent-editor-kit/blob/main/'+relative+(mark+fragment if mark else '')+')'
            assert data==re.sub(r'(!?\[[^\]]*\]\()([^\n)]+)\)',externalize,(ROOT/p).read_text('utf8')).encode('utf8'),name
        target=home/p;target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
runtime=load(ROOT/'local/agent-ffmpeg/runtime.json');devices=load(runtime['community_config'])
discovery=Path('C:/Users/carzy/.codex/skills/agent-ffmpeg-local-editor');original_target=discovery.resolve()
ps=['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File'];calls=[]
def run(name,argv,json_cli=False):
    argv=list(map(str,argv));r=subprocess.run(argv,capture_output=True,cwd=ROOT,timeout=900,creationflags=subprocess.CREATE_NO_WINDOW)
    stdout=out/(name+'.stdout.txt');stderr=out/(name+'.stderr.txt');stdout.write_bytes(r.stdout);stderr.write_bytes(r.stderr)
    calls.append(dict(name=name,argv=argv,exit_code=r.returncode,json_cli=json_cli,stdout_sha256=sha(stdout),stderr_sha256=sha(stderr)));save('calls.json',calls)
    print(json.dumps(dict(name=name,exit_code=r.returncode)),flush=True);assert r.returncode==0,(name,r.stderr[-2500:],r.stdout[-1500:])
    if json_cli:
        v=json.loads(r.stdout);assert v['ok'] and v['provenance']['cli_version']=='0.1.45';return v['data']
try:
    run('configure',[sys.executable,'-I','-B','-u','-X','utf8',home/'scripts/activate_community_runtime.py',
        '--installed',runtime['installed_directory'],'--packs',Path(devices['voice']['cpu_pack']).parent,
        '--voice-cuda-lib',devices['voice']['cuda_library_directory'],'--translation-cuda-lib',devices['translation']['cuda_library_directory'],
        '--semantic-config',runtime['semantic_config'],'--verify-timeout-seconds','600'])
    isolated=home.parent/'isolated-discovery';run('register',[*ps,home/'register-agent-ffmpeg-local-skills.ps1','-SkillsDirectory',isolated,'-ReceiptPath',out/'registration.json'])
    entry=isolated/'agent-ffmpeg-local-editor';assert entry.resolve()==(home/'skills/agent-ffmpeg-local-editor').resolve();launcher=entry/'scripts/run.ps1'
    def cli(name,*argv):return run(name,[*ps,launcher,*argv],True)
    assert cli('version','version')['cli_version']=='0.1.45'
    caps=cli('capabilities','capabilities')['capabilities'];assert len(caps)==84
    assert caps['native_chromatic_adaptation']['protocol']=='explicit-white-Bradford-float32-v1'
    run('render-help',[*ps,launcher,'render','--help'])
    project=home.parent/'portable-hdr10';cli('import','convert','import','--input',ROOT/'docs/assets/native-chromatic-20261028-r3/editable-chromatic.aevpkg.zip','--output',project)
    cli('validate','validate','--project',project);before=(project/'project.json').read_bytes()
    plan=cli('plan','render','--project',project,'--output',project/'renders/portable.mkv','--dry-run',
             '--hardware-encode','off','--projection-acceleration','require','--projection-device','0.0')
    assert load(project/'project.json')['settings']['pixel_pipeline']['working_signal']==dict(primaries='aces-ap1',transfer='linear',white_xy=[.32168,.33767])
    assert plan['plan']['command']
    assert before==(project/'project.json').read_bytes() and not (project/'renders/portable.mkv').exists()
    assert discovery.resolve()==original_target
    report=dict(status='passed',files=136,skill_files=84,cli_version='0.1.45',kit_sha256=sha(kit),registered_skills=1,internal_modules=17,
        process_calls=len(calls),json_cli_calls=sum(c['json_cli'] for c in calls),native_windows=True,virtualization=False,source_fallback=False,
        real_discovery_changed=False,full_inventory_verified=True,portable_white_signal_validated=True,dry_run_metadata_unchanged=True,
        new_model_forwards=0,new_renders=0,scope='Independent extraction/configuration/junction registration,installed chromatic plan and portable package validation.')
    save('verification.json',report);print(json.dumps(report),flush=True)
except BaseException as e:save('failure.json',dict(status='failed',error=repr(e),calls=calls));raise
