"""Audit the exact final installed product, evidence, Skill kit and full manuals."""
from pathlib import Path
from datetime import datetime,timezone
from urllib.parse import unquote
import argparse,hashlib,json,re,subprocess,zipfile

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/validation/evidence/tracking-magnetic-20261026-r1'
BASELINE='8dd9e69c56ad5f46e723f6f1c2d2a4a866f4b3bd'
GIT='C:/Users/carzy/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/git/cmd/git.exe'

def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def load(p):return json.loads(Path(p).read_bytes())
def git(*args):return subprocess.check_output([GIT,'--no-optional-locks','-c','core.fsmonitor=false','-c','gc.auto=0','-c','maintenance.auto=false',*args],cwd=ROOT,timeout=600)
def rows(s,p):return {m[1]:m[0] for m in re.finditer(r'^\| ('+p+r'\d{2,3})\s*\|.*$',s,re.M)}

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--run',default='r1');args=parser.parse_args()
    assert re.fullmatch(r'r[1-9][0-9]*',args.run)
    out=BASE/('final-delivery-'+args.run);out.mkdir(exist_ok=False)
    (out/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    def save(name,v):(out/name).write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    report=dict(status='running',native_windows=True,virtualization=False,source_fallback=False,goal_complete=False)
    save('verification.json',report)
    try:
        assert git('rev-parse','HEAD').decode().strip()==BASELINE
        assert git('branch','--show-current').strip()==b'main'
        assert git('remote','get-url','origin').strip()==b'git@github.com:copypasteltd/agent-editor-kit.git'
        install=load(BASE/'installation-final-r1/verification.json');assert install['status']=='installed-and-byte-verified'
        tested_installed=Path(install['installed'])
        installed=Path(install['installed']);assert install['cli_version']=='0.1.29' and install['source_file_count']==220
        pins={p.name:sha(p) for p in (ROOT/'product/src/ai_ad_editor').glob('*.py')};assert len(pins)==220
        assert pins=={p.name:sha(p) for p in (installed/'site/ai_ad_editor').glob('*.py')}
        assert pins=={r['path']:r['sha256'] for r in install['source_files']};save('product-files.json',pins)
        assert sha(install['archive'])==install['archive_sha256'] and Path(install['archive']).stat().st_size==302783126
        assert 'sha256:'+sha(ROOT/'local/agent-ffmpeg/v0.1.0-alpha.4-local.27/unpacked-r1/manifest.json')==install['manifest_sha256']
        assert load(installed/'receipt.json')['manifest_sha256']==install['manifest_sha256']
        schema=ROOT/'docs/specs/agent-project.schema.json';schema_bytes=schema.read_bytes()
        assert schema_bytes==(ROOT/'product/src/ai_ad_editor/agent-project.schema.json').read_bytes()==(installed/'site/ai_ad_editor/agent-project.schema.json').read_bytes()
        assert sha(schema) in (installed/'site/ai_ad_editor/schema_contract.py').read_text('utf8')
        expected={'tracking':61,'magnetic':66,'editing':195,'bindings':71,'legacy':192,'render':46,'audio':65,'float':98}
        groups=[]
        for name,count in expected.items():
            v=load(BASE/(name+'-installed-r1')/'verification.json')
            assert v['status']=='passed' and v['tests']==count and v['skipped']==v['failures']==v['errors']==0
            assert v['frozen_equal'] and v['product_files']==pins
            assert (ROOT/v['installed']).resolve()==tested_installed.resolve()
            groups.append(dict(group=name,tests=count,skipped=0,frozen_equal=True))
        runtime=load(ROOT/'local/agent-ffmpeg/runtime.json');manifest=load(ROOT/'agent-ffmpeg-local-install-manifest.json')
        assert Path(runtime['installed_directory']).resolve()==installed.resolve()
        assert runtime['manifest_sha256']==manifest['manifest_sha256']==install['manifest_sha256']
        assert manifest['cli_version']=='0.1.29' and manifest['skill_count']==1 and manifest['module_count']==17 and len(manifest['files'])==73
        assert Path('C:/Users/carzy/.codex/skills/agent-ffmpeg-local-editor').resolve()==(ROOT/'skills/agent-ffmpeg-local-editor').resolve()
        assert sum(Path(r['path']).name=='SKILL.md' for r in manifest['files'])==1
        for r in manifest['files']:assert sha(ROOT/r['path'])==r['sha256'] and (ROOT/r['path']).stat().st_size==r['bytes']
        activation=load(BASE/'activation-final-r1/activation-and-registration.json')
        assert activation['status']=='passed' and len(activation['activation']['verified_packs'])==4
        registered=load(BASE/'registration-current.json')
        assert registered['namespace_manifest_sha256']==sha(ROOT/'agent-ffmpeg-local-install-manifest.json')
        assert registered['skill_count']==1 and registered['module_count']==17
        assert Path(registered['runtime_directory']).resolve()==installed.resolve()
        kit=load(ROOT/'docs/skills/community-unified-skill-package-0.1.29-r30.json')
        assert kit['files']==109 and sha(ROOT/kit['archive'])==kit['sha256']
        assert load(BASE/'kit-r1/verification.json')['status']=='passed'
        with zipfile.ZipFile(ROOT/kit['archive']) as z:
            assert len(z.namelist())==109 and 'docs/product/TRACKING_MAGNETIC.md' in z.namelist()
            inventory=load(ROOT/'agent-ffmpeg-local-install-manifest.json')
            assert z.read('agent-ffmpeg-local-install-manifest.json')==(ROOT/'agent-ffmpeg-local-install-manifest.json').read_bytes()
            for r in inventory['files']:assert hashlib.sha256(z.read(r['path'])).hexdigest()==r['sha256']
        case=load(BASE/'case-r1/verification.json');assert case['status']=='passed' and Path(case['installed']).resolve()==tested_installed.resolve()
        assert case['registered_skill'] and not case['source_fallback'] and case['new_model_forwards']==0
        assert case['edited_frames']==36 and case['full_pcm_samples_per_channel']==144000 and case['max_pcm_error']==0
        assert case['restored_frames_and_pcm_equal'] and case['gif_frames']==24 and not case['natural_quality_accepted']
        for c in case['calls']:
            assert c['exit_code']==0 and sha(c['stdout_path'])==c['stdout_sha256']
            assert sha(BASE/'case-r1'/(c['name']+'.stderr.log'))==c['stderr_sha256']
        oracle=load(BASE/'case-r1/native-float-frame-oracles.json')
        assert len(oracle)==36 and all(r['pixels_equal'] and r['clock_geometry_equal'] for r in oracle)
        assert [r['original_frame'] for r in oracle]==list(range(24,36))+list(range(24))
        assert case['synchronized_source_follower_audio_splits']==3 and case['all_tracking_clocks_geometry_equal']
        gpu=load(BASE/'case-r1/gpu-receipt.json')
        assert gpu['status']=='verified' and gpu['operations']['affine']>=30 and gpu['operations']['over']>=30
        assert gpu['worker_closed'] and gpu['shared_handles_closed']
        queue=load(BASE/'queue-r1/verification.json')
        assert queue['status']=='passed' and queue['decoded_frames']==36 and queue['full_pcm_samples_per_channel']==144000
        assert queue['full_pcm_equal'] and queue['all_frame_pixels_and_clocks_equal'] and queue['authored_graph_and_rights_unchanged']
        public=Path(case['public']);media=load(public/'media-manifest.json')
        assert media['output_frames']==36 and media['gif_frames']==24 and media['seconds']==3
        for r in media['files']:assert sha(ROOT/r['path'])==r['sha256'] and (ROOT/r['path']).stat().st_size==r['bytes']
        assert sha(public/'editable-tracking-magnetic.aevpkg.zip')==case['package_sha256']
        assert load(BASE/'media-inspection-r1/verification.json')['status']=='passed'
        still=load(BASE/'media-inspection-r1/still-review.json')
        assert still['status']=='reviewed' and still['contact_sheet_sha256']==sha(BASE/'media-inspection-r1/contact-sheet.png')
        assert not still['continuous_playback'] and not still['human_listening']
        failures=load(BASE/'development-attempts-r1/verification.json');assert failures['status']=='passed' and len(failures['failed_attempts'])==1
        for r in failures['failed_attempts']:assert sha(ROOT/r['path'])==r['sha256'] and r['excluded_from_final_acceptance']
        caps=load(ROOT/'docs/product/tracking-magnetic-capabilities-cli-0.1.29.json')['data']['capabilities'];assert len(caps)==75
        assert caps['standard_native_float_render']['tracking']['edit_protocol']=='native-tracking-edit-lineage-v1'
        assert {'physical_source_slip_and_real_head_tail_extension',
            'fragment_specific_author_reference_offsets_and_target_opacity_reanchor',
            'source_handle_roll_slide_with_retained_observations',
            'rational_integer_grid_piecewise_constant_curve_clock',
            'magnetic_reorder_synchronized_source_target_cuts_and_lineage_repair'}<=set(caps['standard_native_float_render']['tracking']['features'])
        for suffix,name in [('','README.md'),('.zh-TW','README.zh-TW.md'),('.en','README.en.md')]:
            text=(ROOT/name).read_text('utf-8-sig');previous=rows(git('show',BASELINE+':'+name).decode('utf-8-sig'),'R')
            assert len(previous)==205 and all(rows(text,'R')[k]==v for k,v in previous.items())
            assert len(rows(text,'R'))==211 and len(rows(text,'F'))==60 and len(rows(text,'S'))==20 and len(rows(text,'K'))==17
            assert 'CLI0.1.29 / alpha.4-local.27 / r30 kit' in text and 'local.27/final-r1/installed' in text
            manual=(ROOT/('docs/product/CAPABILITIES'+suffix+'.md')).read_text('utf-8-sig')
            assert len(rows(manual,'F'))==60 and len(rows(manual,'S'))==20
            for key,value in caps.items():
                match=re.search(r'^### `'+re.escape(key)+r'`\s*\n\n```json\n(.*?)\n```',manual,re.M|re.S)
                assert match and json.loads(match[1])==value,key
        name='docs/product/GOAL_GAPS_20261025.md';old=rows(git('show',BASELINE+':'+name).decode('utf-8-sig'),'G');current=rows((ROOT/name).read_text('utf-8-sig'),'G')
        assert len(old)==len(current)==38 and all(current[k].split('|')[5]==v.split('|')[5] for k,v in old.items())
        assert 'local.27-final-r1/CLI0.1.29/r30' in current['G38'].split('|')[3]
        changed=set(git('diff','HEAD','--name-only','-z').decode('utf8').split('\0'))|set(git('ls-files','--others','--exclude-standard','-z').decode('utf8').split('\0'))
        files=[];links=0
        for name in sorted(changed):
            if not name or (ROOT/name).is_relative_to(out):continue
            assert not name.startswith(('local/','workspace/','sources/')),name
            path=ROOT/name;assert path.is_file() and path.stat().st_size<95*1024**2,name
            if path.suffix=='.md':
                for target in re.findall(r'!?\[[^\]]*\]\(([^\n)]+)\)',path.read_text('utf-8-sig')):
                    target=target.strip().strip('<>')
                    if re.match(r'^[a-z][a-z0-9+.-]*:',target,re.I) or target.startswith('#'):continue
                    assert (path.parent/unquote(target.split('#')[0])).resolve().exists(),(name,target)
                    links+=1
            files.append(dict(path=name,bytes=path.stat().st_size,sha256=sha(path)))
        report.update(status='passed',checked_at_utc=datetime.now(timezone.utc).isoformat(),product_files=220,skill_files=73,modules=17,
            test_groups=groups,functions=60,services=20,declarations=75,readme_rows=211,historical_rows_preserved=205,
            original_goal_closures_preserved=38,local_links_checked=links,actual_registered_skill_frames=36,
            full_pcm_samples_per_channel=144000,kit_sha256=kit['sha256'],files=files)
        save('verification.json',report);print(json.dumps({k:v for k,v in report.items() if k!='files'},ensure_ascii=False),flush=True)
    except BaseException as exc:report.update(status='failed',error=repr(exc));save('verification.json',report);raise

if __name__=='__main__':main()
