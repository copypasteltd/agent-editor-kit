"""Audit installed performance delivery, historical goal cells and full manuals."""
from pathlib import Path
from datetime import datetime,timezone
import argparse,hashlib,json,re,subprocess,zipfile
from urllib.parse import unquote

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/validation/evidence/gpu-dispatch-20261027-r1'
BASELINE='d75e5cb26cb58d5f7c18923fb841dfe341f9716c'
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
    report={'status':'running','at_utc':datetime.now(timezone.utc).isoformat(),'goal_complete':False,
        'native_windows':True,'virtualization':False,'source_fallback':False}
    def save():(out/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    save()
    try:
        assert git('rev-parse','HEAD').decode().strip()==BASELINE
        assert git('branch','--show-current').strip()==b'main'
        for args in [('remote','get-url','origin'),('remote','get-url','--push','origin')]:
            assert git(*args).strip()==b'git@github.com:copypasteltd/agent-editor-kit.git'
        install=load(BASE/'installation-final-r1/verification.json');package=Path(install['installed'])
        pins={p.name:sha(p) for p in (ROOT/'product/src/ai_ad_editor').glob('*.py')}
        assert len(pins)==234 and pins=={p.name:sha(p) for p in (package/'site/ai_ad_editor').glob('*.py')}
        assert pins=={r['path']:r['sha256'] for r in install['source_files']}
        assert sha(install['archive'])==install['archive_sha256'] and Path(install['archive']).stat().st_size==install['archive_bytes']
        assert install['manifest_sha256']=='sha256:'+sha(ROOT/'local/agent-ffmpeg/v0.1.0-alpha.4-local.34/unpacked-r1/manifest.json')
        assert (ROOT/'docs/specs/agent-project.schema.json').read_bytes()==(package/'site/ai_ad_editor/agent-project.schema.json').read_bytes()
        tests=load(BASE/'installed-regression-r1/verification.json')
        assert tests['status']=='passed' and tests['tests']==656 and tests['failures']==tests['errors']==tests['skipped']==0
        assert tests['frozen_equal'] and tests['test_frozen_equal'] and tests['product_files']==pins
        assert Path(tests['installed']).resolve()==package.resolve()
        for name,digest in tests['test_files'].items():
            assert sha(ROOT/'product/tests'/name)==digest==sha(BASE/'installed-regression-r1/executed-tests'/name)
        assert (BASE/'installed-regression-r1/executed-runner.py').read_bytes()==(ROOT/'scripts/test_float_gpu_dispatch_20261027.py').read_bytes()
        kernel=load(BASE/'kernel-identity-r1/verification.json')
        assert kernel['status']=='passed' and kernel['byte_identical_existing_files']==227
        assert kernel['worker_execute_and_probe_AST_equal'] and kernel['source_and_installed_equal']
        for name,digest in kernel['unchanged_numeric_files'].items():assert sha(ROOT/'product/src/ai_ad_editor'/name)==digest
        baseline=load(BASE/'render-baseline-r1/verification.json');current=load(BASE/'render-installed-r1/verification.json')
        assert baseline['status']==current['status']=='passed' and baseline['cli_version']=='0.1.35' and current['cli_version']=='0.1.36'
        for key in ('fixture_sha256','author_graph_sha256','native_tools','frame_sha256','video_sha256','audio_sha256','audio_samples'):
            assert baseline[key]==current[key],key
        assert len(current['frame_sha256'])==48 and current['all_frames_equal'] and current['all_PCM_equal']
        assert current['audio_samples']==384000 and current['decoded_audio_all_zero']
        gpu=current['GPU'];assert gpu['operations']['particles']==288
        assert gpu['worker_closed'] and gpu['shared_handles_closed']
        assert gpu['control']['protocol']=='owned-inherited-binary-pipes-v1'
        assert gpu['control']['threads_closed'] and gpu['control']['streams_closed']
        assert not gpu['control']['transient_control_persisted'] and not gpu['runtime_failure_CPU_fallback']
        profile=load(BASE/'profile-installed-r2/verification.json')
        assert profile['status']=='passed' and not profile['source_package'] and profile['cli_version']=='0.1.36'
        assert profile['CPU_GPU_max_error']<=3e-6 and profile['product_files_frozen']
        assert load(BASE/'profile-installed-r2/product-files.json')==pins
        namespace=load(ROOT/'agent-ffmpeg-local-install-manifest.json');runtime=load(ROOT/'local/agent-ffmpeg/runtime.json')
        assert namespace['cli_version']=='0.1.36' and namespace['skill_count']==1 and namespace['module_count']==17
        assert len(namespace['files'])==76 and namespace['release']==runtime['release']=='v0.1.0-alpha.4-local.34'
        assert namespace['manifest_sha256']==runtime['manifest_sha256']==install['manifest_sha256']
        assert Path(runtime['installed_directory']).resolve()==package.resolve()
        for row in namespace['files']:assert sha(ROOT/row['path'])==row['sha256'] and (ROOT/row['path']).stat().st_size==row['bytes']
        assert Path('C:/Users/carzy/.codex/skills/agent-ffmpeg-local-editor').resolve()==(ROOT/'skills/agent-ffmpeg-local-editor').resolve()
        activation=load(BASE/'activation-final-r1/activation-and-registration.json');assert activation['status']=='passed'
        assert len(activation['activation']['verified_packs'])==4
        registration=load(BASE/'registration-final-r1.json')
        assert registration['namespace_manifest_sha256']==sha(ROOT/'agent-ffmpeg-local-install-manifest.json')
        assert registration['launcher_preflight_verified'] and registration['registered_cli_version']=='0.1.36'
        kit=load(ROOT/'docs/skills/community-unified-skill-package-0.1.36-r37.json')
        assert kit['files']==119 and sha(ROOT/kit['archive'])==kit['sha256']
        fresh=load(BASE/'kit-r1/verification.json')
        assert fresh['status']=='passed' and fresh['files']==119 and fresh['skill_files']==76 and not fresh['real_discovery_changed']
        assert fresh['process_calls']==23 and fresh['new_renders']==fresh['new_model_forwards']==0
        with zipfile.ZipFile(ROOT/kit['archive']) as z:
            assert len(z.namelist())==119 and 'docs/product/GPU_DISPATCH.md' in z.namelist()
            assert z.read('agent-ffmpeg-local-install-manifest.json')==(ROOT/'agent-ffmpeg-local-install-manifest.json').read_bytes()
            for row in namespace['files']:assert hashlib.sha256(z.read(row['path'])).hexdigest()==row['sha256']
        caps=load(ROOT/'docs/product/gpu-dispatch-capabilities-cli-0.1.36.json')['data']['capabilities'];assert len(caps)==76
        for suffix in ('','.zh-TW','.en'):
            name='README'+suffix+'.md';text=(ROOT/name).read_text('utf8')
            old=rows(git('show',BASELINE+':'+name).decode('utf8'),'R')
            assert len(old)==247 and len(rows(text,'R'))==253 and all(rows(text,'R')[k]==v for k,v in old.items())
            assert len(rows(text,'F'))==63 and len(rows(text,'S'))==21 and len(rows(text,'K'))==17
            assert 'CLI0.1.36 / alpha.4-local.34 / r37 kit' in text and 'local.34/final-r1/installed' in text
            manual=(ROOT/('docs/product/CAPABILITIES'+suffix+'.md')).read_text('utf8')
            assert len(rows(manual,'F'))==63 and len(rows(manual,'S'))==21
            for key,value in caps.items():
                m=re.search(r'^### `'+re.escape(key)+r'`\s*\n\n```json\n(.*?)\n```',manual,re.M|re.S)
                assert m and json.loads(m[1])==value,key
        path='docs/product/GOAL_GAPS_20261025.md'
        old=rows(git('show',BASELINE+':'+path).decode('utf8'),'G');now=rows((ROOT/path).read_text('utf8'),'G')
        assert len(old)==len(now)==38 and all(now[k].split('|')[5]==v.split('|')[5] for k,v in old.items())
        path='docs/product/IMPLEMENTATION_PLAN_20261025.md';old=git('show',BASELINE+':'+path).decode('utf8')
        text=(ROOT/path).read_text('utf8')
        assert all(line in text for line in old.replace('当前本地 **CLI0.1.35','此前本地 **CLI0.1.35',1).splitlines() if line)
        media=ROOT/'docs/assets/gpu-dispatch-20261027-r1'
        for name,record in load(media/'media-manifest.json')['files'].items():
            assert sha(media/name)==record['sha256'] and (media/name).stat().st_size==record['bytes']
        assert sha(media/'optimized.mkv')==current['movie_sha256']
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
        report.update(status='passed',product_files=234,capabilities=76,installed_tests=656,
            source_and_installed_equal=True,all_48_frames_and_PCM_equal=True,
            baseline_seconds=baseline['render_seconds'],current_seconds=current['render_seconds'],
            speedup_one_pair=current['speedup_one_pair'],skill_files=76,kit_files=119,
            readme_prior_R_rows_preserved=247,readme_R_rows=253,goal_closure_cells_preserved=38,
            changed_files=len(files),local_links_verified=links)
        save();print(json.dumps(report,ensure_ascii=False))
    except BaseException as exc:report.update(status='failed',error=repr(exc));save();raise

if __name__=='__main__':main()
