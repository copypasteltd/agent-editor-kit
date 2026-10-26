"""Verify current installed delivery, preserved history, actual media and Skill kit."""
from pathlib import Path
from datetime import datetime, timezone
from urllib.parse import unquote
import argparse
import hashlib
import json
import re
import subprocess
import zipfile

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/validation/evidence/tracking-bake-20261026-r1'
BASELINE='2914ec98723c6c458f9538b1ea694221227e1542'
GIT='C:/Users/carzy/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/git/cmd/git.exe'

def sha(path):
    with Path(path).open('rb') as stream: return hashlib.file_digest(stream,'sha256').hexdigest()
def load(path): return json.loads(Path(path).read_bytes())
def git(*args): return subprocess.check_output([GIT,'--no-optional-locks','-c','core.fsmonitor=false','-c','gc.auto=0','-c','maintenance.auto=false',*args],cwd=ROOT,timeout=600)
def rows(text,prefix): return {m[1]:m[0] for m in re.finditer(r'^\| ('+prefix+r'\d{2,3})\s*\|.*$',text,re.M)}

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--run',required=True);args=parser.parse_args()
    assert re.fullmatch(r'r[1-9][0-9]*',args.run)
    out=BASE/('final-delivery-'+args.run);out.mkdir(exist_ok=False)
    (out/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    def save(name,value): (out/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    report=dict(status='running',goal_complete=False,virtualization=False,source_fallback=False)
    save('verification.json',report)
    try:
        assert git('rev-parse','HEAD').decode().strip()==BASELINE
        assert git('branch','--show-current').strip()==b'main'
        assert git('remote','get-url','origin').strip()==b'git@github.com:copypasteltd/agent-editor-kit.git'
        installation=load(BASE/'installation-final-r3/verification.json');installed=Path(installation['installed'])
        assert installation['status']=='installed-and-byte-verified' and installation['source_file_count']==225
        assert installation['cli_version']=='0.1.32'
        assert sha(installation['archive'])==installation['archive_sha256']
        assert Path(installation['archive']).stat().st_size==installation['archive_bytes']
        pins={p.name:sha(p) for p in (ROOT/'product/src/ai_ad_editor').glob('*.py')};assert len(pins)==225
        assert pins=={p.name:sha(p) for p in (installed/'site/ai_ad_editor').glob('*.py')}
        assert pins=={r['path']:r['sha256'] for r in installation['source_files']}
        save('product-files.json',pins)
        schema=ROOT/'docs/specs/agent-project.schema.json'
        assert schema.read_bytes()==(installed/'site/ai_ad_editor/agent-project.schema.json').read_bytes()
        groups=[]
        for name,count in [('tracking',149),('conversion',83),('legacy',192)]:
            tested=load(BASE/(name+'-installed-r3/verification.json'))
            assert tested['status']=='passed' and tested['tests']==count
            assert tested['errors']==tested['failures']==tested['skipped']==0
            assert tested['product_files']==pins and tested['frozen_equal']
            assert Path(tested['installed']).resolve()==installed.resolve()
            groups.append(dict(group=name,tests=count,skips=0))
        manifest=load(ROOT/'agent-ffmpeg-local-install-manifest.json');runtime=load(ROOT/'local/agent-ffmpeg/runtime.json')
        assert manifest['cli_version']=='0.1.32' and manifest['skill_count']==1 and manifest['module_count']==17 and len(manifest['files'])==73
        assert runtime['release']==manifest['release']=='v0.1.0-alpha.4-local.30'
        assert runtime['manifest_sha256']==manifest['manifest_sha256']==installation['manifest_sha256']
        assert Path(runtime['installed_directory']).resolve()==installed.resolve()
        for item in manifest['files']: assert sha(ROOT/item['path'])==item['sha256'] and (ROOT/item['path']).stat().st_size==item['bytes']
        assert sum(Path(item['path']).name=='SKILL.md' for item in manifest['files'])==1
        assert Path('C:/Users/carzy/.codex/skills/agent-ffmpeg-local-editor').resolve()==(ROOT/'skills/agent-ffmpeg-local-editor').resolve()
        activation=load(BASE/'activation-final-r4/activation-and-registration.json')
        assert activation['status']=='passed' and len(activation['activation']['verified_packs'])==4
        registration=load(BASE/'registration-final-r2.json')
        assert registration['namespace_manifest_sha256']==sha(ROOT/'agent-ffmpeg-local-install-manifest.json')
        assert Path(registration['runtime_directory']).resolve()==installed.resolve()
        kit=load(ROOT/'docs/skills/community-unified-skill-package-0.1.32-r33.json')
        assert kit['files']==112 and sha(ROOT/kit['archive'])==kit['sha256']
        fresh=load(BASE/'kit-r1/verification.json')
        assert fresh['status']=='passed' and fresh['files']==112 and fresh['skill_files']==73
        assert fresh['process_calls']==16 and fresh['json_cli_calls']==12 and not fresh['real_discovery_changed']
        with zipfile.ZipFile(ROOT/kit['archive']) as archive:
            assert len(archive.namelist())==112 and 'docs/product/TRACKING_BAKE.md' in archive.namelist()
            assert archive.read('agent-ffmpeg-local-install-manifest.json')==(ROOT/'agent-ffmpeg-local-install-manifest.json').read_bytes()
            for item in manifest['files']: assert hashlib.sha256(archive.read(item['path'])).hexdigest()==item['sha256']
        case=load(BASE/'case-r5/verification.json');assert case['status']=='passed' and Path(case['installed']).resolve()==installed.resolve()
        assert case['registered_skill'] and not case['source_fallback'] and case['new_model_forwards']==0
        assert case['float32_verified_frames']==case['decoded_equal_frames']==36 and case['full_pcm_samples_per_channel']==144000
        assert len(case['formats'])==5 and not case['external_renderer_verified']
        assert all(c['ok'] for c in case['checks'])
        assert len(case['source_immutability'])==7
        for operation in case['source_immutability']:
            assert len(operation['files'])==2
            assert all(f['before_sha256']==f['after_sha256'] for f in operation['files'])
        source=Path(case['project'])
        assert sha(source/'project.json')==case['post_render_project_sha256']
        assert sha(source/'rights-ledger.json')==case['rights_sha256']
        assert sha(BASE/'case-r5/source-before-render.json')==case['original_project_sha256']
        for call in case['calls']:
            assert call['exit_code']==call['expected_exit_code'] and sha(call['stdout_path'])==call['stdout_sha256']
            assert sha(BASE/'case-r5'/(call['name']+'.stderr.log'))==call['stderr_sha256']
        proof=load(BASE/'case-r5/native-bake-proof.json');assert proof['all_float32_frames_equal'] and proof['samples']==45
        for receipt in proof['receipts']:
            gpu=receipt['projection_acceleration']
            assert receipt['providers_closed'] and gpu['status']=='prepared'
            assert gpu['operations']=={'affine':90,'over':81} and gpu['worker_closed'] and gpu['shared_handles_closed']
        decoded=load(BASE/'case-r5/decoded-full-media.json');assert decoded['original']==decoded['baked']
        public=Path(case['public']);media=load(public/'media-manifest.json')
        for item in media['files']: assert sha(public/item['path'])==item['sha256'] and (public/item['path']).stat().st_size==item['bytes']
        with zipfile.ZipFile(public/'editable-baked-tracking.aevpkg.zip') as archive:
            assert load(BASE/'case-r5/native-bake-proof.json')==json.loads(archive.read('conversion-report.json'))['tracking_bake']
        inspection=load(BASE/'media-inspection-r2/verification.json');assert inspection['status']=='passed'
        assert inspection['gif_frames']==24 and inspection['static_image_review'] and not inspection['continuous_playback']
        failures=load(BASE/'development-attempts-r4/verification.json');assert failures['status']=='recorded'
        for item in failures['failed_attempts']: assert sha(ROOT/item['path'])==item['sha256'] and item['excluded_from_final_acceptance']
        caps=load(ROOT/'docs/product/tracking-bake-capabilities-cli-0.1.32.json')['data']['capabilities'];assert len(caps)==75
        assert caps['standard_native_float_render']['tracking']['interchange_bake']['protocol']=='native-PTS-tracking-frame-verified-bake-v1'
        for suffix,name in [('','README.md'),('.zh-TW','README.zh-TW.md'),('.en','README.en.md')]:
            text=(ROOT/name).read_text('utf-8-sig');old=rows(git('show',BASELINE+':'+name).decode('utf-8-sig'),'R')
            assert len(old)==223 and all(rows(text,'R')[key]==value for key,value in old.items())
            assert len(rows(text,'R'))==229 and len(rows(text,'F'))==60 and len(rows(text,'S'))==20 and len(rows(text,'K'))==17
            assert 'CLI0.1.32 / alpha.4-local.30 / r33 kit' in text and 'local.30/final-r3/installed' in text
            manual=(ROOT/('docs/product/CAPABILITIES'+suffix+'.md')).read_text('utf-8-sig')
            assert len(rows(manual,'F'))==60 and len(rows(manual,'S'))==20
            for key,value in caps.items():
                match=re.search(r'^### `'+re.escape(key)+r'`\s*\n\n```json\n(.*?)\n```',manual,re.M|re.S)
                assert match and json.loads(match[1])==value,key
        gap='docs/product/GOAL_GAPS_20261025.md'
        old=rows(git('show',BASELINE+':'+gap).decode('utf-8-sig'),'G');current=rows((ROOT/gap).read_text('utf-8-sig'),'G')
        assert len(old)==len(current)==38 and all(current[k].split('|')[5]==v.split('|')[5] for k,v in old.items())
        assert 'local.30-final-r3/CLI0.1.32/r33' in current['G38'].split('|')[3]
        changed=set(git('diff','HEAD','--name-only','-z').decode('utf8').split('\0'))|set(git('ls-files','--others','--exclude-standard','-z').decode('utf8').split('\0'))
        files=[];links=0
        for name in sorted(changed):
            if not name or (ROOT/name).is_relative_to(out): continue
            assert not name.startswith(('local/','workspace/','sources/')),name
            path=ROOT/name;assert path.is_file() and path.stat().st_size<95*1024**2,name
            if path.suffix=='.md':
                for target in re.findall(r'!?\[[^\]]*\]\(([^\n)]+)\)',path.read_text('utf-8-sig')):
                    target=target.strip().strip('<>')
                    if re.match(r'^[a-z][a-z0-9+.-]*:',target,re.I) or target.startswith('#'): continue
                    assert (path.parent/unquote(target.split('#')[0])).resolve().exists(),(name,target)
                    links+=1
            files.append(dict(path=name,bytes=path.stat().st_size,sha256=sha(path)))
        report.update(status='passed',checked_at_utc=datetime.now(timezone.utc).isoformat(),product_files=225,
            skill_files=73,modules=17,test_groups=groups,functions=60,services=20,declarations=75,
            readme_rows=229,historical_rows_preserved=223,original_goal_closures_preserved=38,
            local_links_checked=links,actual_registered_skill_frames=36,full_pcm_samples_per_channel=144000,
            kit_sha256=kit['sha256'],files=files)
        save('verification.json',report);print(json.dumps({k:v for k,v in report.items() if k!='files'},ensure_ascii=False),flush=True)
    except BaseException as exc:
        report.update(status='failed',error=repr(exc));save('verification.json',report);raise

if __name__=='__main__': main()
