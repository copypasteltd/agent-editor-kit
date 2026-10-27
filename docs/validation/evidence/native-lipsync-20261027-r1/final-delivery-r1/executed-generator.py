"""Audit frozen native lip-sync delivery, actual neural cases and complete history."""
from pathlib import Path
from datetime import datetime,timezone
from urllib.parse import unquote
import argparse,hashlib,json,re,subprocess,zipfile
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/validation/evidence/native-lipsync-20261027-r1'
BASELINE='1584222bb95bce5479bee2928798f5e9d811a51d'
GIT='C:/Users/carzy/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/git/cmd/git.exe'
def load(p):return json.loads(Path(p).read_bytes())
def sha(p):
    with Path(p).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
def git(*args):return subprocess.check_output([GIT,'--no-optional-locks','-c','core.fsmonitor=false','-c','gc.auto=0','-c','maintenance.auto=false',*args],cwd=ROOT,timeout=600)
def rows(s,prefix):return {m[1]:m[0] for m in re.finditer(r'^\| ('+prefix+r'\d+)\s*\|.*$',s,re.M)}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--run',required=True);a=ap.parse_args();assert re.fullmatch('r[1-9][0-9]*',a.run)
    out=BASE/('final-delivery-'+a.run);out.mkdir(exist_ok=False)
    (out/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    report=dict(status='running',at_utc=datetime.now(timezone.utc).isoformat(),goal_complete=False,native_windows=True,virtualization=False,source_fallback=False)
    def save():(out/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    save()
    try:
        assert git('rev-parse','HEAD').decode().strip()==BASELINE and git('branch','--show-current').strip()==b'main'
        for args in [('remote','get-url','origin'),('remote','get-url','--push','origin')]:assert git(*args).strip()==b'git@github.com:copypasteltd/agent-editor-kit.git'
        install=load(BASE/'installation-final-r1/verification.json');package=Path(install['installed'])
        pins={p.name:sha(p) for p in (ROOT/'product/src/ai_ad_editor').glob('*.py')}
        assert len(pins)==248 and pins=={p.name:sha(p) for p in (package/'site/ai_ad_editor').glob('*.py')}
        assert pins=={r['path']:r['sha256'] for r in install['source_files']}
        assert install['status']=='installed-and-byte-verified' and install['cli_version']=='0.1.41' and install['capability_count']==80
        assert sha(install['archive'])==install['archive_sha256'] and Path(install['archive']).stat().st_size==install['archive_bytes']
        assert install['manifest_sha256']=='sha256:'+sha(ROOT/'local/agent-ffmpeg/v0.1.0-alpha.4-local.39/unpacked-r1/manifest.json')
        schema=(ROOT/'docs/specs/agent-project.schema.json').read_bytes()
        assert schema==(package/'site/ai_ad_editor/agent-project.schema.json').read_bytes()==(ROOT/'product/src/ai_ad_editor/agent-project.schema.json').read_bytes()
        for attempt,count,installed in [('source-lipsync-r3',28,False),('installed-lipsync-r1',28,True),('source-service-compat-r1',177,False)]:
            result=load(BASE/attempt/'verification.json')
            assert result['status']=='passed' and result['tests']==count and result['failures']==result['errors']==result['skipped']==0
            assert result['frozen_equal'] and result['test_frozen_equal'] and result['product_files']==pins
            assert bool(result['installed'])==installed
            if installed:assert (ROOT/result['installed']).resolve()==package.resolve()
            for name,digest in result['test_files'].items():assert sha(ROOT/'product/tests'/name)==digest==sha(BASE/attempt/'executed-tests'/name)
            assert (BASE/attempt/'executed-runner.py').read_bytes()==(ROOT/'scripts/test_lipsync_20261027.py').read_bytes()
            outcomes=re.findall(r'^(test_\S+) \(([^)]+)\)(?:\n[^\n]*)? \.\.\. (ok|FAIL|ERROR|skipped[^\n]*)$',(BASE/attempt/'tests.log').read_text('utf8'),re.M)
            assert len(outcomes)==len({r[1] for r in outcomes})==count and all(r[2]=='ok' for r in outcomes),(attempt,len(outcomes))
        case=load(BASE/'case-r1/verification.json');moving=load(BASE/'video-and-cancel-r1/verification.json')
        for result in (case,moving):assert result['status']=='passed' and all(c['ok'] for c in result['checks']) and not result['source_fallback'] and not result['natural_quality_accepted']
        assert case['registered_skill'] and not case['synthetic_protocol_worker'] and not moving['fake_worker']
        assert case['frames']==133 and case['fps']==25 and case['duration_seconds']==5.32 and case['selected_PCM_scalars']==126795
        assert case['padded_PCM_scalars']==885 and case['GIF_duration_ms']==5320 and case['rendered_frames']==160 and case['rendered_fps']=='30/1'
        for key in ('all_source_PCM_equal','all_source_alpha_equal','all_outside_region_RGB_equal','all_package_rendered_frames_equal','all_package_rendered_PCM_equal'):assert case[key]
        assert moving['moving_frames']==30 and moving['all_moving_source_alpha_and_outside_RGB_equal'] and moving['real_cancel_after_neural_frames']
        assert all(p['state'] in {'exited','terminated_by_cleanup'} and p['final_exit'] is not None for p in moving['cancellation_diagnostic']['manifest']['processes'])
        for result,n in [(case,133),(moving,30)]:
            model=result['model_execution'];assert not model['CPU_fallback'] and model['network']=='disabled' and sum(model['batch_frames'])==n
            assert all(model['calls'][k]>0 for k in ('audio_encoder','vae_encoder','unet','vae_decoder','face_parser'))
        work=Path(case['project']).parent
        assert sha(work/'rendered-rgba.bin')==sha(work/'restored-rgba.bin') and sha(work/'rendered-pcm.bin')==sha(work/'restored-pcm.bin')
        assert (work/'master-rgba.bin').stat().st_size==133*512*512*4
        media=ROOT/'docs/assets/native-lipsync-20261027-r1';inventory=load(media/'media-manifest.json')
        for row in inventory['files']:assert sha(media/row['path'])==row['sha256'] and (media/row['path']).stat().st_size==row['bytes']
        for result in (case,moving):
            for row in result['public_files']:assert sha(ROOT/row['path'])==row['sha256'] and (ROOT/row['path']).stat().st_size==row['bytes']
        review=load(BASE/'static-portrait-review.json');assert review['status']=='reviewed' and not review['continuous_human_playback'] and not review['human_listening']
        for name,digest in review['files'].items():assert sha(media/name)==digest
        namespace=load(ROOT/'agent-ffmpeg-local-install-manifest.json');runtime=load(ROOT/'local/agent-ffmpeg/runtime.json')
        assert namespace['cli_version']=='0.1.41' and namespace['skill_count']==1 and namespace['module_count']==17 and len(namespace['files'])==80
        assert namespace['release']==runtime['release']=='v0.1.0-alpha.4-local.39' and namespace['manifest_sha256']==runtime['manifest_sha256']==install['manifest_sha256']
        assert Path(runtime['installed_directory']).resolve()==package.resolve()
        for row in namespace['files']:assert sha(ROOT/row['path'])==row['sha256'] and (ROOT/row['path']).stat().st_size==row['bytes']
        assert Path('C:/Users/carzy/.codex/skills/agent-ffmpeg-local-editor').resolve()==(ROOT/'skills/agent-ffmpeg-local-editor').resolve()
        activation=load(BASE/'activation-final-r1/activation-and-registration.json');registration=activation['registration']
        assert activation['status']=='passed' and len(activation['activation']['verified_packs'])==4
        assert registration['namespace_manifest_sha256']==sha(ROOT/'agent-ffmpeg-local-install-manifest.json') and registration['launcher_preflight_verified'] and registration['registered_cli_version']=='0.1.41'
        kit=load(ROOT/'docs/skills/community-unified-skill-package-0.1.41-r42.json');fresh=load(BASE/'kit-r1/verification.json')
        assert kit['files']==128 and sha(ROOT/kit['archive'])==kit['sha256']
        assert fresh['status']=='passed' and fresh['files']==128 and fresh['skill_files']==80 and not fresh['real_discovery_changed']
        assert fresh['process_calls']==34 and fresh['new_renders']==fresh['new_model_forwards']==0
        with zipfile.ZipFile(ROOT/kit['archive']) as z:assert len(z.namelist())==128 and 'docs/product/LIP_SYNC.md' in z.namelist()
        caps=load(ROOT/'docs/product/lip-sync-capabilities-cli-0.1.41.json')['data']['capabilities'];assert len(caps)==80 and caps['native_lip_sync']['protocol']=='agent-native-lipsync-v1'
        for suffix in ('','.zh-TW','.en'):
            name='README'+suffix+'.md';text=(ROOT/name).read_text('utf8');old=rows(git('show',BASELINE+':'+name).decode('utf8'),'R')
            assert len(old)==277 and len(rows(text,'R'))==283 and all(rows(text,'R')[k]==v for k,v in old.items())
            assert len(rows(text,'F'))==67 and len(rows(text,'S'))==22 and len(rows(text,'K'))==17
            assert 'CLI0.1.41 / alpha.4-local.39 / r42 kit' in text and 'local.39/final-r1/installed' in text
            manual=(ROOT/('docs/product/CAPABILITIES'+suffix+'.md')).read_text('utf8')
            assert len(rows(manual,'F'))==67 and len(rows(manual,'S'))==22
            for key,value in caps.items():
                m=re.search(r'^### `'+re.escape(key)+r'`\s*\n\n```json\n(.*?)\n```',manual,re.M|re.S);assert m and json.loads(m[1])==value,key
        path='docs/product/GOAL_GAPS_20261025.md';old=rows(git('show',BASELINE+':'+path).decode('utf8'),'G');now=rows((ROOT/path).read_text('utf8'),'G')
        assert len(old)==len(now)==38 and all(now[k].split('|')[5]==v.split('|')[5] for k,v in old.items())
        path='docs/product/IMPLEMENTATION_PLAN_20261025.md';old=git('show',BASELINE+':'+path).decode('utf8');now=(ROOT/path).read_text('utf8')
        assert all(line in now for line in old.splitlines() if line)
        changed=set(git('diff','HEAD','--name-only','-z').decode('utf8').split('\0'))|set(git('ls-files','--others','--exclude-standard','-z').decode('utf8').split('\0'))
        files=[];links=0
        for name in sorted(changed):
            if not name or (ROOT/name).is_relative_to(out):continue
            path=ROOT/name;assert path.is_file() and path.stat().st_size<95*1024**2,name
            assert not name.startswith(('local/','workspace/','sources/')),name
            if path.suffix=='.md':
                for target in re.findall(r'!?\[[^\]]*\]\(([^\n)]+)\)',path.read_text('utf-8-sig')):
                    target=target.strip().strip('<>')
                    if re.match(r'^[a-z][a-z0-9+.-]*:',target,re.I) or target.startswith('#'):continue
                    assert (path.parent/unquote(target.split('#',1)[0])).resolve().exists(),(name,target)
                    links+=1
            files.append(dict(path=name,bytes=path.stat().st_size,sha256=sha(path)))
        (out/'product-files.json').write_text(json.dumps(pins,indent=2)+'\n',encoding='utf8',newline='\n')
        (out/'files.json').write_text(json.dumps(files,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
        report.update(status='passed',product_files=248,capabilities=80,installed_tests=28,source_lipsync_tests=28,source_compatibility_tests=177,
            earlier_HDR_tests_aggregated=False,source_and_installed_equal=True,actual_neural_master_frames=133,moving_video_frames=30,actual_neural_cancellation=True,
            skill_files=80,kit_files=128,readme_prior_R_rows_preserved=277,readme_R_rows=283,goal_closure_cells_preserved=38,changed_files=len(files),local_links_verified=links)
        save();print(json.dumps(report,ensure_ascii=False))
    except BaseException as exc:report.update(status='failed',error=repr(exc));save();raise
if __name__=='__main__':main()
