"""Verify frozen installed interpolation delivery, actual media and all goal history."""
from pathlib import Path
from datetime import datetime,timezone
from urllib.parse import unquote
import argparse,hashlib,json,re,subprocess,zipfile
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'docs/validation/evidence/native-interpolation-20261027-r1'
BASELINE='656d136f2677d7ce07c4bb9734370cc7f9147e50'
GIT='C:/Users/carzy/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/git/cmd/git.exe'
def load(p):return json.loads(Path(p).read_bytes())
def sha(p):
    with Path(p).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
def git(*args):return subprocess.check_output([GIT,'--no-optional-locks','-c','core.fsmonitor=false','-c','gc.auto=0','-c','maintenance.auto=false',*args],cwd=ROOT,timeout=600)
def rows(s,prefix):return {m[1]:m[0] for m in re.finditer(r'^\| ('+prefix+r'\d+)\s*\|.*$',s,re.M)}
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--run',required=True);a=ap.parse_args();assert re.fullmatch('r[1-9][0-9]*',a.run)
    out=BASE/('final-delivery-'+a.run);out.mkdir(exist_ok=False);(out/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    report=dict(status='running',at_utc=datetime.now(timezone.utc).isoformat(),goal_complete=False,native_windows=True,virtualization=False,source_fallback=False)
    def save():(out/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    save()
    try:
        assert git('rev-parse','HEAD').decode().strip()==BASELINE and git('branch','--show-current').strip()==b'main'
        for args in [('remote','get-url','origin'),('remote','get-url','--push','origin')]:assert git(*args).strip()==b'git@github.com:copypasteltd/agent-editor-kit.git'
        install=load(BASE/'installation-final-r1/verification.json');package=Path(install['installed']);pins={p.name:sha(p) for p in (ROOT/'product/src/ai_ad_editor').glob('*.py')}
        assert len(pins)==257 and pins=={p.name:sha(p) for p in (package/'site/ai_ad_editor').glob('*.py')}=={r['path']:r['sha256'] for r in install['source_files']}
        assert install['status']=='installed-and-byte-verified' and install['cli_version']=='0.1.42' and install['capability_count']==81
        assert sha(install['archive'])==install['archive_sha256'] and Path(install['archive']).stat().st_size==install['archive_bytes']
        assert install['manifest_sha256']=='sha256:'+sha(ROOT/'local/agent-ffmpeg/v0.1.0-alpha.4-local.40/unpacked-r1/manifest.json')
        schema=(ROOT/'docs/specs/agent-project.schema.json').read_bytes();assert schema==(package/'site/ai_ad_editor/agent-project.schema.json').read_bytes()==(ROOT/'product/src/ai_ad_editor/agent-project.schema.json').read_bytes()
        assert (ROOT/'product/src/ai_ad_editor/RIFE_LICENSE.txt').read_bytes()==(package/'site/ai_ad_editor/RIFE_LICENSE.txt').read_bytes()
        for attempt,count,installed in [('source-interpolation-r3',37,False),('installed-interpolation-r1',37,True),('installed-compat-r2',143,True)]:
            result=load(BASE/attempt/'verification.json');assert result['status']=='passed' and result['tests']==count and result['failures']==result['errors']==result['skipped']==0
            assert result['frozen_equal'] and result['test_frozen_equal'] and result['product_files']==pins and bool(result['installed'])==installed
            if installed:assert (ROOT/result['installed']).resolve()==package.resolve()
            for name,digest in result['test_files'].items():assert sha(ROOT/'product/tests'/name)==digest==sha(BASE/attempt/'executed-tests'/name)
            assert (BASE/attempt/'executed-runner.py').read_bytes()==(ROOT/'scripts/test_interpolation_20261027.py').read_bytes()
            outcomes=re.findall(r'^(test_\S+) \(([^)]+)\)(?:\n[^\n]*)? \.\.\. (ok|FAIL|ERROR|skipped[^\n]*)$',(BASE/attempt/'tests.log').read_text('utf8'),re.M)
            assert len(outcomes)==len({r[1] for r in outcomes})==count and all(r[2]=='ok' for r in outcomes),(attempt,len(outcomes))
        case=load(BASE/'case-r1/verification.json');quality=load(BASE/'quality-and-cancel-r1/verification.json')
        for result in (case,quality):assert result['status']=='passed' and all(c['ok'] for c in result['checks']) and not result['source_fallback'] and not result['natural_quality_accepted'] and not result['continuous_playback'] and not result['human_listening']
        assert case['registered_skill'] and not case['synthetic_protocol_worker'] and not quality['fake_worker']
        assert (case['source_frames'],case['generated_frames'],case['actual_model_forwards'],case['alpha_VFR_source_frames'],case['alpha_VFR_generated_frames'],case['alpha_model_forwards'],case['selected_PCM_scalars'],case['GIF_duration_ms'])==(24,96,69,12,36,20,105840,8000)
        assert case['all_package_rendered_frames_equal'] and case['all_package_rendered_PCM_equal'];held=case['held_out_comparison']
        assert held['count']==len(held['per_frame'])==23 and held['model_better_than_hold_frames']==22 and held['model_better_than_blend_frames']==13
        assert abs(sum(v['model_mse'] for v in held['per_frame'])/23-held['model_mse'])<1e-10
        assert quality['actual_failure_pair']==22 and quality['unguarded_MSE']>quality['explicit_hold_MSE'] and quality['guard_forward_count']==66 and quality['real_cancel_after_neural_frames']
        children=quality['cancellation_diagnostic']['manifest']['processes'];assert len(children)==3 and all(p['state'] in {'exited','terminated_by_cleanup'} and p['final_exit'] is not None for p in children)
        for key,forwards in [('natural_result',69),('alpha_result',20)]:
            result=case[key];generation=result['generation'];worker=generation['worker'];execution=worker['model_execution']
            assert worker['providers']==['torch-cuda'] and worker['blocked_network_events']==[] and execution['flow_forwards']==execution['generated_frames']==forwards and execution['network']=='disabled' and not execution['CPU_fallback']
            assert generation['complete_RGBA_roundtrip_verified'] and generation['all_original_anchors_roundtrip_verified'] and generation['all_native_PTS_and_durations_verified']
            assert all(p['exited'] and p['stdout_closed'] for p in generation['cleanup']['processes']) and not generation['cleanup']['warnings']
        assert case['alpha_result']['generation']['complete_PCM_roundtrip_verified']
        work=Path(case['project']).parent;assert sha(work/'rendered-rgba.bin')==sha(work/'restored-rgba.bin') and sha(work/'rendered-pcm.bin')==sha(work/'restored-pcm.bin')
        media=ROOT/'docs/assets/native-interpolation-20261027-r1';inventory=load(media/'media-manifest.json')
        for row in inventory['files']:assert sha(media/row['path'])==row['sha256'] and (media/row['path']).stat().st_size==row['bytes']
        for result in (case,quality):
            for row in result['public_files']:assert sha(ROOT/row['path'])==row['sha256'] and (ROOT/row['path']).stat().st_size==row['bytes']
        review=load(BASE/'static-review.json');assert review['status']=='static-frames-inspected' and not review['continuous_human_playback'] and not review['human_listening']
        for name,digest in review['files'].items():assert sha(media/name)==digest
        conversion=load(BASE/'weight-conversion.json');assert conversion['status']=='converted-and-byte-exact-tensor-verified' and conversion['tensors']==158
        probe=load(BASE/'private-cuda-probe.json');assert probe['status']=='passed' and probe['network_events']==[] and probe['execution']['flow_forwards']==3
        assert (BASE/'drive-attempt-r1.json').is_file() and (BASE/'weight-conversion-attempt-r1.json').is_file() and (BASE/'weight-conversion-attempt-r2.json').is_file()
        namespace=load(ROOT/'agent-ffmpeg-local-install-manifest.json');runtime=load(ROOT/'local/agent-ffmpeg/runtime.json')
        assert namespace['cli_version']=='0.1.42' and namespace['skill_count']==1 and namespace['module_count']==17 and len(namespace['files'])==81
        assert namespace['release']==runtime['release']=='v0.1.0-alpha.4-local.40' and namespace['manifest_sha256']==runtime['manifest_sha256']==install['manifest_sha256'] and Path(runtime['installed_directory']).resolve()==package.resolve()
        for row in namespace['files']:assert sha(ROOT/row['path'])==row['sha256'] and (ROOT/row['path']).stat().st_size==row['bytes']
        assert Path('C:/Users/carzy/.codex/skills/agent-ffmpeg-local-editor').resolve()==(ROOT/'skills/agent-ffmpeg-local-editor').resolve()
        activation=load(BASE/'activation-final-r1/activation-and-registration.json');registration=activation['registration']
        assert activation['status']=='passed' and len(activation['activation']['verified_packs'])==4 and registration['namespace_manifest_sha256']==sha(ROOT/'agent-ffmpeg-local-install-manifest.json') and registration['launcher_preflight_verified'] and registration['registered_cli_version']=='0.1.42'
        kit=load(ROOT/'docs/skills/community-unified-skill-package-0.1.42-r43.json');fresh=load(BASE/'kit-r2/verification.json')
        assert kit['files']==130 and sha(ROOT/kit['archive'])==kit['sha256'] and fresh['status']=='passed' and fresh['files']==130 and fresh['skill_files']==81 and not fresh['real_discovery_changed']
        assert fresh['process_calls']==36 and fresh['new_renders']==fresh['new_model_forwards']==0
        with zipfile.ZipFile(ROOT/kit['archive']) as z:assert len(z.namelist())==130 and 'docs/product/NEURAL_INTERPOLATION.md' in z.namelist()
        caps=load(ROOT/'docs/product/neural-interpolation-capabilities-cli-0.1.42.json')['data']['capabilities'];assert len(caps)==81 and caps['native_neural_interpolation']['protocol']=='agent-native-frame-interpolation-v1'
        for suffix in ('','.zh-TW','.en'):
            name='README'+suffix+'.md';text=(ROOT/name).read_text('utf8');old=rows(git('show',BASELINE+':'+name).decode('utf8'),'R')
            assert len(old)==283 and len(rows(text,'R'))==290 and all(rows(text,'R')[k]==v for k,v in old.items())
            assert len(rows(text,'F'))==68 and len(rows(text,'S'))==23 and len(rows(text,'K'))==17 and 'CLI0.1.42 / alpha.4-local.40 / r43 kit' in text and 'local.40/final-r1/installed' in text
            manual=(ROOT/('docs/product/CAPABILITIES'+suffix+'.md')).read_text('utf8');assert len(rows(manual,'F'))==68 and len(rows(manual,'S'))==23
            for key,value in caps.items():
                m=re.search(r'^### `'+re.escape(key)+r'`\s*\n\n```json\n(.*?)\n```',manual,re.M|re.S);assert m and json.loads(m[1])==value,key
        path='docs/product/GOAL_GAPS_20261025.md';old=rows(git('show',BASELINE+':'+path).decode('utf8'),'G');now=rows((ROOT/path).read_text('utf8'),'G')
        assert len(old)==len(now)==38 and all(now[k].split('|')[5]==v.split('|')[5] for k,v in old.items())
        path='docs/product/IMPLEMENTATION_PLAN_20261025.md';old=git('show',BASELINE+':'+path).decode('utf8');now=(ROOT/path).read_text('utf8');assert all(line in now for line in old.splitlines() if line)
        changed=set(git('diff','HEAD','--name-only','-z').decode('utf8').split('\0'))|set(git('ls-files','--others','--exclude-standard','-z').decode('utf8').split('\0'))
        files=[];links=0;upstream=[]
        for name in sorted(changed):
            if not name or (ROOT/name).is_relative_to(out):continue
            path=ROOT/name;assert path.is_file() and path.stat().st_size<95*1024**2 and not name.startswith(('local/','workspace/','sources/')),name
            if name=='docs/validation/evidence/native-interpolation-20261027-r1/upstream-code/README.md':upstream.append(dict(path=name,sha256=sha(path),scope='Verbatim pinned upstream README;relative image links belong to upstream repository.'))
            elif path.suffix=='.md':
                for target in re.findall(r'!?\[[^\]]*\]\(([^\n)]+)\)',path.read_text('utf-8-sig')):
                    target=target.strip().strip('<>')
                    if re.match(r'^[a-z][a-z0-9+.-]*:',target,re.I) or target.startswith('#'):continue
                    assert (path.parent/unquote(target.split('#',1)[0])).resolve().exists(),(name,target)
                    links+=1
            files.append(dict(path=name,bytes=path.stat().st_size,sha256=sha(path)))
        (out/'product-files.json').write_text(json.dumps(pins,indent=2)+'\n',encoding='utf8',newline='\n');(out/'files.json').write_text(json.dumps(files,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
        report.update(status='passed',product_files=257,capabilities=81,source_interpolation_tests=37,installed_interpolation_tests=37,installed_compatibility_tests=143,
            earlier_HDR_or_services_tests_aggregated=False,source_and_installed_equal=True,actual_animation_frames=96,actual_alpha_VFR_frames=36,original_PCM_scalars=105840,
            actual_neural_cancellation=True,retained_actual_ghosting_failure=True,skill_files=81,kit_files=130,readme_prior_R_rows_preserved=283,readme_R_rows=290,goal_closure_cells_preserved=38,
            changed_files=len(files),local_links_verified=links,verbatim_upstream_link_scope=upstream)
        save();print(json.dumps(report,ensure_ascii=False))
    except BaseException as exc:report.update(status='failed',error=repr(exc));save();raise
if __name__=='__main__':main()
