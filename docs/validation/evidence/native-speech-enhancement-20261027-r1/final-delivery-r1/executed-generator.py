"""Audit frozen installed speech delivery, actual media, kit and preserved goals."""
from pathlib import Path
from datetime import datetime,timezone
from urllib.parse import unquote
import argparse,hashlib,json,re,subprocess,zipfile
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'docs/validation/evidence/native-speech-enhancement-20261027-r1'
BASELINE='009efac332aaa0099b4e694d13370463f2b9f3d8'
GIT='C:/Users/carzy/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/git/cmd/git.exe'
def load(p):return json.loads(Path(p).read_bytes())
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def git(*args):return subprocess.check_output([GIT,'--no-optional-locks','-c','core.fsmonitor=false','-c','gc.auto=0','-c','maintenance.auto=false',*args],cwd=ROOT,timeout=600)
def rows(s,p):return {m[1]:m[0] for m in re.finditer(r'^\| ('+p+r'\d+)\s*\|.*$',s,re.M)}
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--run',required=True);a=ap.parse_args();assert a.run.replace('-','').isalnum()
    out=BASE/('final-delivery-'+a.run);out.mkdir(exist_ok=False);(out/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    report=dict(status='running',at_utc=datetime.now(timezone.utc).isoformat(),goal_complete=False,native_windows=True,virtualization=False,source_fallback=False)
    def save():(out/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    save()
    try:
        assert git('rev-parse','HEAD').decode().strip()==BASELINE and git('branch','--show-current').strip()==b'main'
        for args in [('remote','get-url','origin'),('remote','get-url','--push','origin')]:assert git(*args).strip()==b'git@github.com:copypasteltd/agent-editor-kit.git'
        install=load(BASE/'installation-final-r3/verification.json');package=Path(install['installed']);pins={p.name:sha(p) for p in (ROOT/'product/src/ai_ad_editor').glob('*.py')}
        assert install['status']=='installed-and-byte-verified' and install['cli_version']=='0.1.43' and install['capability_count']==82
        assert len(pins)==266 and pins=={p.name:sha(p) for p in (package/'site/ai_ad_editor').glob('*.py')}=={r['path']:r['sha256'] for r in install['source_files']}
        assert sha(install['archive'])==install['archive_sha256'] and Path(install['archive']).stat().st_size==install['archive_bytes']
        assert install['manifest_sha256']=='sha256:'+sha(ROOT/'local/agent-ffmpeg/v0.1.0-alpha.4-local.41/unpacked-r3/manifest.json')
        schema=(ROOT/'docs/specs/agent-project.schema.json').read_bytes();assert schema==(package/'site/ai_ad_editor/agent-project.schema.json').read_bytes()
        for license in ('DEEPFILTER_LICENSE_MIT.txt','DEEPFILTER_LICENSE_APACHE.txt'):assert (ROOT/'product/src/ai_ad_editor'/license).read_bytes()==(package/'site/ai_ad_editor'/license).read_bytes()
        for attempt,count,installed in [('source-enhancement-r6',33,False),('installed-enhancement-r3',33,True),('installed-compat-r3',156,True)]:
            test=load(BASE/attempt/'verification.json');assert test['status']=='passed' and test['tests']==count and test['failures']==test['errors']==test['skipped']==0
            assert test['frozen_equal'] and test['product_files']==pins and bool(test['installed'])==installed
            if installed:assert (ROOT/test['installed']).resolve()==package.resolve()
            for name,digest in test['test_files'].items():assert sha(ROOT/'product/tests'/name)==digest==sha(BASE/attempt/'executed-tests'/name)
            assert (BASE/attempt/'executed-runner.py').read_bytes()==(ROOT/'scripts/test_speech_enhancement_20261027.py').read_bytes()
        model=ROOT/'product/.runtime/models/deepfilternet3-20261027';conversion=load(BASE/'conversion.json')
        assert conversion['status']=='converted-strict-tensor-equality' and conversion['tensor_count']==133 and conversion['strict_full_graph'] and conversion['weights_only_development_conversion'] and not conversion['pickle_in_product_runtime']
        assert sha(model/'model.safetensors')==conversion['target_sha256'] and sha(model/'config.json')==conversion['config_sha256']
        case=load(BASE/'case-complete-r1/verification.json');extra=load(BASE/'quality-and-cancel-r4/verification.json')
        for v in (case,extra):
            assert v['status']=='passed' and all(c['ok'] for c in v['checks']) and not v['source_fallback'] and not v['fake_worker']
            assert not v['human_listening'] and not v['continuous_playback'] and not v['natural_quality_accepted']
        assert all(c['ok'] for c in case['retained_prior_checks']) and case['prior_attempt_retained_status']=='failed-VIDEO_TRACK_EMPTY'
        for name in ('english','chinese'):
            replay=load(BASE/('quality-and-cancel-r4/final-replay-'+name+'.stdout.json'))['data'];asset=replay['asset'];gen=replay['generation'];worker=gen['worker']
            assert sha(Path(case['project'])/asset['uri'])==asset['sha256'].removeprefix('sha256:')==sha(ROOT/('docs/assets/native-speech-enhancement-20261027-r2/'+name+'-enhanced.wav'))
            assert gen['complete_PCM_roundtrip_verified'] and gen['native_sample_clock_verified'] and worker['model']['neural_backend']=='cuda'
            assert not worker['model']['CPU_fallback'] and worker['blocked_network_events']==[] and worker['metrics']['model_calls']==4
            assert gen['cleanup']['worker_exited'] and gen['cleanup']['owner_job_closed']
        assert case['English_model_calls']==case['Chinese_model_calls']==4
        assert case['english_result']['generation']['worker']['range']['samples']==281040
        assert case['chinese_result']['generation']['worker']['range']==dict(start_sample=137,end_sample=232775,samples=232638,sample_rate=44100)
        assert extra['worker_pid_confirmed_exited'] and extra['metadata_rollback_verified'] and extra['partial_asset_absent'] and extra['cancellation_trigger']['done']>=1
        diagnostic=extra['cancellation_diagnostic'];worker=next(p for p in diagnostic['processes'] if p['role']=='worker')
        assert worker['state']=='terminated_by_cleanup' and worker['final_exit'] is not None and diagnostic['progress']['segments_done']>=1
        assert all(p['state']=='not_started' for p in diagnostic['processes'] if p['role']!='worker')
        assert diagnostic['protocol']=='agent-native-pipeline-diagnostic-v1' and extra['fragment_recipe']['source_asset_id']==extra['fragment_source_id']
        work=Path(case['project']).parent;assert sha(work/'original-render-pcm.bin')==sha(work/'restored-render-pcm.bin')
        for folder in ('native-speech-enhancement-20261027-r1','native-speech-enhancement-20261027-r2'):
            media=ROOT/'docs/assets'/folder;inventory=load(media/'media-manifest.json')
            assert {p.name for p in media.iterdir() if p.is_file() and p.name!='media-manifest.json'}=={r['path'] for r in inventory['files']}
            for row in inventory['files']:assert sha(media/row['path'])==row['sha256'] and (media/row['path']).stat().st_size==row['bytes']
        for row in case['public_files']:assert sha(ROOT/row['path'])==row['sha256'] and (ROOT/row['path']).stat().st_size==row['bytes']
        previews=load(BASE/'media-r1/verification.json');assert previews['status']=='actual-audio-previews-created' and previews['GIF_frames']==71 and previews['GIF_duration_ms']==5860
        for row in previews['files']:assert sha(ROOT/row['path'])==row['sha256']
        review=load(BASE/'static-review.json');assert review['status']=='static-figures-inspected' and not review['human_listening']
        for name,digest in review['files'].items():assert sha(ROOT/'docs/assets/native-speech-enhancement-20261027-r2'/name)==digest
        namespace=load(ROOT/'agent-ffmpeg-local-install-manifest.json');assert namespace['cli_version']=='0.1.43' and len(namespace['files'])==82 and len(namespace['skills'])==1
        for row in namespace['files']:assert sha(ROOT/row['path'])==row['sha256'] and (ROOT/row['path']).stat().st_size==row['bytes']
        assert Path('C:/Users/carzy/.codex/skills/agent-ffmpeg-local-editor').resolve()==(ROOT/'skills/agent-ffmpeg-local-editor').resolve()
        activation=load(BASE/'activation-final-r3/activation-and-registration.json');registration=activation['registration']
        assert activation['status']=='passed' and registration['namespace_manifest_sha256']==sha(ROOT/'agent-ffmpeg-local-install-manifest.json') and registration['launcher_preflight_verified'] and registration['registered_cli_version']=='0.1.43'
        kit=load(ROOT/'docs/skills/community-unified-skill-package-0.1.43-r44.json');fresh=load(BASE/'kit-r2/verification.json')
        assert kit['files']==132 and sha(ROOT/kit['archive'])==kit['sha256'] and fresh['status']=='passed' and fresh['files']==132 and fresh['skill_files']==82 and not fresh['real_discovery_changed']
        with zipfile.ZipFile(ROOT/kit['archive']) as z:assert len(z.namelist())==132 and 'docs/product/SPEECH_ENHANCEMENT.md' in z.namelist()
        caps=load(ROOT/'docs/product/speech-enhancement-capabilities-cli-0.1.43.json')['data']['capabilities'];assert len(caps)==82 and not caps['native_speech_enhancement']['goal_G17_complete']
        for suffix in ('','.zh-TW','.en'):
            name='README'+suffix+'.md';s=(ROOT/name).read_text('utf8');old=rows(git('show',BASELINE+':'+name).decode('utf8'),'R')
            assert len(old)==290 and len(rows(s,'R'))==297 and all(rows(s,'R')[k]==v for k,v in old.items())
            assert len(rows(s,'F'))==69 and len(rows(s,'S'))==24 and len(rows(s,'K'))==17 and 'CLI0.1.43 / alpha.4-local.41 / r44 kit' in s and 'local.41/final-r3/installed' in s
            manual=(ROOT/('docs/product/CAPABILITIES'+suffix+'.md')).read_text('utf8');assert len(rows(manual,'F'))==69 and len(rows(manual,'S'))==24
            for key,value in caps.items():
                m=re.search(r'^### `'+re.escape(key)+r'`\s*\n\n```json\n(.*?)\n```',manual,re.M|re.S);assert m and json.loads(m[1])==value,key
        p='docs/product/GOAL_GAPS_20261025.md';old=rows(git('show',BASELINE+':'+p).decode('utf8'),'G');now=rows((ROOT/p).read_text('utf8'),'G')
        assert len(old)==len(now)==38 and all(now[k].split('|')[5]==v.split('|')[5] for k,v in old.items())
        changed=set(git('diff','HEAD','--name-only','-z').decode('utf8').split('\0'))|set(git('ls-files','--others','--exclude-standard','-z').decode('utf8').split('\0'))
        files=[];links=0
        for name in sorted(changed):
            if not name or (ROOT/name).is_relative_to(out):continue
            path=ROOT/name;assert path.is_file() and path.stat().st_size<95*1024**2 and not name.startswith(('local/','workspace/','sources/')),name
            if path.suffix=='.md' and '/upstream-code/' not in name:
                for target in re.findall(r'!?\[[^\]]*\]\(([^\n)]+)\)',path.read_text('utf-8-sig')):
                    target=target.strip().strip('<>')
                    if re.match(r'^[a-z][a-z0-9+.-]*:',target,re.I) or target.startswith('#'):continue
                    assert (path.parent/unquote(target.split('#',1)[0])).resolve().exists(),(name,target)
                    links+=1
            files.append(dict(path=name,bytes=path.stat().st_size,sha256=sha(path)))
        (out/'product-files.json').write_text(json.dumps(pins,indent=2)+'\n',encoding='utf8',newline='\n')
        (out/'files.json').write_text(json.dumps(files,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
        report.update(status='passed',product_files=266,capabilities=82,source_enhancement_tests=33,installed_enhancement_tests=33,installed_compatibility_tests=156,
            source_installed_equal=True,earlier_test_executions_aggregated=False,actual_English_samples=281040,actual_Chinese_samples_per_channel=232638,
            final_installed_replay_master_bytes_equal=True,actual_neural_cancellation=True,persistent_diagnostic_read_after_rollback=True,
            retained_clean_and_reverb_controls=True,human_listening=False,skill_files=82,kit_files=132,readme_prior_R_rows_preserved=290,readme_R_rows=297,
            goal_closure_cells_preserved=38,changed_files=len(files),local_links_verified=links,upstream_links_scope='Verbatim pinned upstream source is exempt from local relative-link interpretation.')
        save();print(json.dumps(report,ensure_ascii=False))
    except BaseException as exc:report.update(status='failed',error=repr(exc));save();raise
if __name__=='__main__':main()
