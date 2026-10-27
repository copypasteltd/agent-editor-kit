"""Verify the complete CLI38 delivery and preserve all prior acceptance history."""
from pathlib import Path
from datetime import datetime,timezone
from urllib.parse import unquote
import argparse,hashlib,json,re,subprocess,zipfile

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/validation/evidence/optical-effects-20261027-r1'
BASELINE='f9776caf9d1d49d0878f8123b32be35f512b9f78'
GIT='C:/Users/carzy/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/git/cmd/git.exe'
def load(p):return json.loads(Path(p).read_bytes())
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def git(*args):return subprocess.check_output([GIT,'--no-optional-locks','-c','core.fsmonitor=false',
    '-c','gc.auto=0','-c','maintenance.auto=false',*args],cwd=ROOT,timeout=600)
def rows(s,prefix):return {m[1]:m[0] for m in re.finditer(r'^\| ('+prefix+r'\d+)\s*\|.*$',s,re.M)}
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--run',required=True);a=ap.parse_args();assert re.fullmatch('r[1-9][0-9]*',a.run)
    out=BASE/('final-delivery-'+a.run);out.mkdir(exist_ok=False)
    (out/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    report=dict(status='running',at_utc=datetime.now(timezone.utc).isoformat(),goal_complete=False,
        native_windows=True,virtualization=False,source_fallback=False)
    def save():(out/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    save()
    try:
        assert git('rev-parse','HEAD').decode().strip()==BASELINE and git('branch','--show-current').strip()==b'main'
        for args in [('remote','get-url','origin'),('remote','get-url','--push','origin')]:
            assert git(*args).strip()==b'git@github.com:copypasteltd/agent-editor-kit.git'
        install=load(BASE/'installation-final-r1/verification.json');package=Path(install['installed'])
        pins={p.name:sha(p) for p in (ROOT/'product/src/ai_ad_editor').glob('*.py')}
        assert len(pins)==237 and pins=={p.name:sha(p) for p in (package/'site/ai_ad_editor').glob('*.py')}
        assert pins=={r['path']:r['sha256'] for r in install['source_files']}
        assert install['status']=='installed-and-byte-verified' and install['cli_version']=='0.1.38'
        assert sha(install['archive'])==install['archive_sha256'] and Path(install['archive']).stat().st_size==install['archive_bytes']
        assert install['manifest_sha256']=='sha256:'+sha(ROOT/'local/agent-ffmpeg/v0.1.0-alpha.4-local.36/unpacked-r1/manifest.json')
        schema=(ROOT/'docs/specs/agent-project.schema.json').read_bytes()
        assert schema==(package/'site/ai_ad_editor/agent-project.schema.json').read_bytes()==(ROOT/'product/src/ai_ad_editor/agent-project.schema.json').read_bytes()
        assert hashlib.sha256(schema).hexdigest()=='8eccc163d7a6fd937d7fa3b0409922a40c264038df43823e05b3f90f9746e5f3'
        tests=load(BASE/'installed-regression-final-r2/verification.json')
        assert tests['status']=='passed' and tests['tests']==704 and tests['failures']==tests['errors']==tests['skipped']==0
        assert tests['frozen_equal'] and tests['test_frozen_equal'] and tests['product_files']==pins
        assert tests['unique_tests_passed']==704 and tests['total_test_executions']==706
        assert not tests['all_704_passed_as_one_new_run'] and not tests['product_changes_after_full_run']
        outcomes=load(BASE/'installed-regression-final-r2/outcome-inventory.json')['outcomes']
        assert len(outcomes)==704 and sum(v['repeated'] for v in outcomes)==2
        assert all(v['final_status']=='passed' for v in outcomes)
        assert (BASE/'installed-regression-final-r2/executed-generator.py').read_bytes()==(ROOT/'scripts/finalize_optical_regression_20261027.py').read_bytes()
        assert Path(tests['installed']).resolve()==package.resolve()
        for name,digest in tests['test_files'].items():assert sha(ROOT/'product/tests'/name)==digest==sha(BASE/'installed-regression-final-r2/executed-tests'/name)
        assert (BASE/'installed-regression-final-r2/executed-runner.py').read_bytes()==(ROOT/'scripts/test_float_optics_20261027.py').read_bytes()
        for attempt,count in [('source-optics-r2',16),('source-optics-gpu-r2',3),('source-optics-integration-r3',6)]:
            r=load(BASE/attempt/'verification.json');assert r['status']=='passed' and r['tests']==count 
            assert r['frozen_equal'] and r['test_frozen_equal']
        case=load(BASE/'case-r3/verification.json');assert case['status']=='passed' and case['cli_version']=='0.1.38'
        assert case['all_48_decoded_10bit_frames_equal'] and case['all_384000_PCM_equal'] and case['all_effects_and_tracks_preserved']
        assert case['animation_tracks']==9 and len(case['frame_sha256'])==48 and case['GIF_duration_ms']==4000
        assert not case['source_fallback'] and case['registered_skill'] and not case['natural_quality_accepted']
        for key in ('GPU','restored_GPU','before_GPU'):
            g=case[key];assert g['operations'].get('optics',0) in (0,143) and g['worker_closed'] and g['shared_handles_closed']
            assert g['control']['threads_closed'] and g['control']['streams_closed'] and not g['runtime_failure_CPU_fallback']
        assert case['GPU']['operations']['optics']==case['restored_GPU']['operations']['optics']==143
        media=ROOT/case['public'];m=load(media/'media-manifest.json')
        assert m['video_frames']==48 and m['GIF_duration_ms']==4000
        for name,r in m['files'].items():assert sha(media/name)==r['sha256'] and (media/name).stat().st_size==r['bytes']
        assert sha(media/'editable-optical-effects.aevpkg.zip')==case['package_sha256']
        review=load(BASE/'static-chart-review.json');assert review['status']=='reviewed' and not review['continuous_human_playback'] and not review['human_listening']
        namespace=load(ROOT/'agent-ffmpeg-local-install-manifest.json');runtime=load(ROOT/'local/agent-ffmpeg/runtime.json')
        assert namespace['cli_version']=='0.1.38' and namespace['skill_count']==1 and namespace['module_count']==17 and len(namespace['files'])==77
        assert namespace['release']==runtime['release']=='v0.1.0-alpha.4-local.36'
        assert namespace['manifest_sha256']==runtime['manifest_sha256']==install['manifest_sha256']
        assert Path(runtime['installed_directory']).resolve()==package.resolve()
        for r in namespace['files']:assert sha(ROOT/r['path'])==r['sha256'] and (ROOT/r['path']).stat().st_size==r['bytes']
        assert Path('C:/Users/carzy/.codex/skills/agent-ffmpeg-local-editor').resolve()==(ROOT/'skills/agent-ffmpeg-local-editor').resolve()
        activation=load(BASE/'activation-final-r1/activation-and-registration.json');assert activation['status']=='passed' and len(activation['activation']['verified_packs'])==4
        registration=load(BASE/'registration-final-r1.json');assert registration['namespace_manifest_sha256']==sha(ROOT/'agent-ffmpeg-local-install-manifest.json')
        assert registration['launcher_preflight_verified'] and registration['registered_cli_version']=='0.1.38'
        kit=load(ROOT/'docs/skills/community-unified-skill-package-0.1.38-r39.json');assert kit['files']==122 and sha(ROOT/kit['archive'])==kit['sha256']
        fresh=load(BASE/'kit-r1/verification.json');assert fresh['status']=='passed' and fresh['files']==122 and fresh['skill_files']==77 and not fresh['real_discovery_changed']
        assert fresh['process_calls']==29 and fresh['new_renders']==fresh['new_model_forwards']==0
        with zipfile.ZipFile(ROOT/kit['archive']) as z:
            assert len(z.namelist())==122 and 'docs/product/OPTICAL_EFFECTS.md' in z.namelist()
            assert z.read('agent-ffmpeg-local-install-manifest.json')==(ROOT/'agent-ffmpeg-local-install-manifest.json').read_bytes()
            for r in namespace['files']:assert hashlib.sha256(z.read(r['path'])).hexdigest()==r['sha256']
        caps=load(ROOT/'docs/product/optical-effects-capabilities-cli-0.1.38.json')['data']['capabilities'];assert len(caps)==77
        assert caps['optical_effects']['protocol']=='author-clock-linear-float32-optical-effects-v1'
        for suffix in ('','.zh-TW','.en'):
            name='README'+suffix+'.md';text=(ROOT/name).read_text('utf8');old=rows(git('show',BASELINE+':'+name).decode('utf8'),'R')
            assert len(old)==259 and len(rows(text,'R'))==265 and all(rows(text,'R')[k]==v for k,v in old.items())
            assert len(rows(text,'F'))==64 and len(rows(text,'S'))==21 and len(rows(text,'K'))==17
            assert 'CLI0.1.38 / alpha.4-local.36 / r39 kit' in text and 'local.36/final-r1/installed' in text
            manual=(ROOT/('docs/product/CAPABILITIES'+suffix+'.md')).read_text('utf8')
            assert len(rows(manual,'F'))==64 and len(rows(manual,'S'))==21
            for key,value in caps.items():
                m=re.search(r'^### `'+re.escape(key)+r'`\s*\n\n```json\n(.*?)\n```',manual,re.M|re.S)
                assert m and json.loads(m[1])==value,key
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
        report.update(status='passed',product_files=237,capabilities=77,installed_tests=704,source_and_installed_equal=True,
            all_48_frames_and_PCM_equal=True,optical_effects=3,animated_case_tracks=9,skill_files=77,kit_files=122,
            readme_prior_R_rows_preserved=259,readme_R_rows=265,goal_closure_cells_preserved=38,changed_files=len(files),local_links_verified=links)
        save();print(json.dumps(report,ensure_ascii=False))
    except BaseException as e:report.update(status='failed',error=repr(e));save();raise
if __name__=='__main__':main()
