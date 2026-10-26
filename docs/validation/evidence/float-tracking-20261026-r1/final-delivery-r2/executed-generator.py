"""Verify final installed grading, media, Skill, docs and preserved goal conditions."""
import argparse
from datetime import datetime,timezone
import hashlib,json,re,subprocess
from pathlib import Path
from urllib.parse import unquote

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/validation/evidence/float-tracking-20261026-r1'
INSTALL=ROOT/'local/agent-ffmpeg/v0.1.0-alpha.4-local.24/final-r2/installed'
BASELINE='8de33691417328a1d801312028697096e971d404'
GIT='C:/Users/carzy/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/git/cmd/git.exe'
def load(p):return json.loads(Path(p).read_bytes())
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def git(*args):return subprocess.check_output([GIT,'--no-optional-locks','-c','core.fsmonitor=false','-c','gc.auto=0','-c','maintenance.auto=false',*args],cwd=ROOT,timeout=600)
def rows(text,prefix):return {m[1]:m[0] for m in re.finditer(r'^\| ('+prefix+r'\d{2,3})\s*\|.*$',text,re.M)}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--run',default='r1');a=ap.parse_args();assert re.fullmatch(r'r[1-9][0-9]*',a.run)
    out=BASE/('final-delivery-'+a.run);out.mkdir(exist_ok=False)
    (out/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    def save(name,value):(out/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    report=dict(status='running',goal_closed=False,virtualization=False,source_fallback=False)
    save('verification.json',report)
    try:
        install=load(BASE/'installation-final-r2/verification.json')
        assert install['cli_version']=='0.1.26' and install['source_and_installed_equal']
        product={p.name:sha(p) for p in (ROOT/'product/src/ai_ad_editor').glob('*.py')}
        assert len(product)==219 and product=={p.name:sha(p) for p in (INSTALL/'site/ai_ad_editor').glob('*.py')}
        assert product=={p['path']:p['sha256'] for p in install['source_files']}
        assert sha(install['archive'])==install['archive_sha256']
        assert Path(install['archive']).stat().st_size==install['archive_bytes']
        save('product-files.json',product)
        groups={}
        expected={'tracking':18,'bindings':71,'adjustments':14,'effects':219,'float':98,'audio':65,'render':46,'legacy':192,'text':98,'gpu':23}
        for group,count in expected.items():
            proof=load(BASE/(group+'-installed-r2/verification.json'))
            assert proof['status']=='passed' and not proof['skipped'] and proof['frozen_equal']
            assert proof['product_files']==product and proof['tests']==count
            assert Path(proof['installed']).resolve()==INSTALL.resolve()
            groups[group]=count
        manifest=load(ROOT/'agent-ffmpeg-local-install-manifest.json')
        assert manifest['release']=='v0.1.0-alpha.4-local.24' and manifest['cli_version']=='0.1.26'
        assert manifest['manifest_sha256']==install['manifest_sha256']
        assert len(manifest['files'])==73 and manifest['skill_count']==1 and manifest['module_count']==17
        for row in manifest['files']:
            assert sha(ROOT/row['path'])==row['sha256'] and (ROOT/row['path']).stat().st_size==row['bytes']
        runtime=load(ROOT/'local/agent-ffmpeg/runtime.json')
        assert Path(runtime['installed_directory']).resolve()==INSTALL.resolve() and runtime['release']==manifest['release']
        assert Path('C:/Users/carzy/.codex/skills/agent-ffmpeg-local-editor').resolve()==(ROOT/'skills/agent-ffmpeg-local-editor').resolve()
        activated=load(BASE/'activation-final-r2/activation-and-registration.json')
        assert activated['status']=='passed' and len(activated['activation']['verified_packs'])==4
        registered=load(BASE/'activation-final-r2/registration-current.json')
        assert registered['namespace_manifest_sha256']==sha(ROOT/'agent-ffmpeg-local-install-manifest.json')
        assert registered['skill_count']==1 and registered['module_count']==17
        assert Path(registered['runtime_directory']).resolve()==INSTALL.resolve()
        case=load(BASE/'case-r5/verification.json');package=load(BASE/'package-r1/verification.json')
        assert case['status']==package['status']=='passed' and case['registered_skill'] and package['registered_skill']
        assert case['actual_frames']==36 and case['tracking_bindings']==1 and case['tracking_observations']==36
        assert case['max_anchor_error_pixels']<.05 and case['max_red_marker_centroid_error_pixels']<1
        assert case['max_pcm_error']<=3e-8 and case['original_authoring_unchanged'] and all(v['ok'] for v in case['checks'])
        assert package['binding_observations_preserved'] and package['font_license_preserved'] and len(package['checked_frames'])==3
        assert package['binding_observations_sha256']==case['binding_observations_sha256']
        assert package['range_float32_and_pcm_equal'] and package['range_preview_frames']==12 and package['range_full_pcm_samples_per_channel']==48000
        tracking=load(BASE/'case-r5/tracking-receipt.json')
        assert tracking['bindings']==1 and tracking['observations']==36 and tracking['evaluations']==36
        assert not tracking['display_keyframes_baked'] and not tracking['model_inference']
        samples=load(BASE/'case-r5/independent-frame-oracles.json');assert len(samples)==36
        assert all(v['source_index']==v['actual_source_index']==v['tracking']['native_frame_index'] for v in samples)
        attempts=load(BASE/'development-attempts-r1/verification.json')
        assert attempts['status']=='passed' and len(attempts['attempts'])==5 and not attempts['failed_evidence_rewritten']
        schema=(ROOT/'product/src/ai_ad_editor/agent-project.schema.json').read_bytes()
        assert schema==(INSTALL/'site/ai_ad_editor/agent-project.schema.json').read_bytes()==(ROOT/'docs/specs/agent-project.schema.json').read_bytes()
        gpu=load(BASE/'case-r5/gpu-receipt.json')
        assert gpu['status']=='verified' and gpu['worker_closed'] and gpu['shared_handles_closed']
        assert gpu['native']['device']['name']=='NVIDIA GeForce RTX 3060'
        assert all(gpu['operations'].get(k,0)>0 for k in ('affine','over','paint'))
        for folder,proof in [('case-r5',case),('package-r1',package)]:
            for call in proof['calls']:
                for channel in ('stdout','stderr'):
                    assert sha(BASE/folder/(call['name']+'.'+channel+'.log'))==call[channel+'_sha256']
            for row in proof.get('public_files',[]):
                assert sha(ROOT/row['path'])==row['sha256'] and (ROOT/row['path']).stat().st_size==row['bytes']
        kit=load(ROOT/'docs/skills/community-unified-skill-package-0.1.26-r27.json')
        assert kit['cli_version']=='0.1.26' and kit['files']==106 and sha(ROOT/kit['archive'])==kit['sha256']
        proof=load(BASE/'kit-r2/verification.json')
        assert proof['status']=='passed' and proof['files']==106 and proof['skill_files']==73 and not proof['real_discovery_changed']
        assert proof['kit_sha256']==kit['sha256']
        assert proof['tracking_plan']['bindings']==1 and proof['tracking_plan']['evaluations']==0
        caps=load(ROOT/'docs/product/float-tracking-capabilities-cli-0.1.26.json')['data']['capabilities']
        assert len(caps)==75 and caps['standard_native_float_render']['tracking']['protocol']==tracking['protocol']
        for suffix,readme in [('', 'README.md'),('.zh-TW','README.zh-TW.md'),('.en','README.en.md')]:
            text=(ROOT/readme).read_text('utf-8-sig');old=rows(git('show',BASELINE+':'+readme).decode('utf-8-sig'),'R')
            assert len(old)==185 and all(rows(text,'R')[k]==v for k,v in old.items())
            assert len(rows(text,'F'))==59 and len(rows(text,'S'))==20 and len(rows(text,'K'))==17 and len(rows(text,'R'))==193
            manual=(ROOT/('docs/product/CAPABILITIES'+suffix+'.md')).read_text('utf-8-sig')
            assert len(rows(manual,'F'))==59 and len(rows(manual,'S'))==20
            for key,value in caps.items():
                m=re.search(r'^### `'+re.escape(key)+r'`\s*\n+```json\n(.*?)\n```',manual,re.M|re.S);assert m,key
                assert json.loads(m[1])==value,key
        name='docs/product/GOAL_GAPS_20261025.md'
        old=rows(git('show',BASELINE+':'+name).decode('utf-8-sig'),'G');new=rows((ROOT/name).read_text('utf-8-sig'),'G')
        assert len(new)==38 and all(new[k].split('|')[5]==v.split('|')[5] for k,v in old.items())
        assert 'local.24-final-r2/CLI0.1.26/r27' in new['G38'].split('|')[3]
        assert git('branch','--show-current').strip()==b'main'
        assert git('remote','get-url','origin').strip()==b'git@github.com:copypasteltd/agent-editor-kit.git'
        changed=set(git('diff','HEAD','--name-only','-z').decode('utf8').split('\0'))|set(git('ls-files','--others','--exclude-standard','-z').decode('utf8').split('\0'))
        inventory=[];links=0
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
            inventory.append(dict(path=name,bytes=path.stat().st_size,sha256=sha(path)))
        report.update(status='passed',verified_at_utc=datetime.now(timezone.utc).isoformat(),product_files=219,skill_files=73,modules=17,
            test_groups=groups,functions=59,services=20,declarations=75,readme_rows=193,historical_rows_preserved=185,
            original_goal_closures_preserved=38,local_links_checked=links,actual_registered_skill_frames=36,
            tracking_bindings=1,range_reimport_frames=12,kit_sha256=kit['sha256'],files=inventory)
        save('verification.json',report);print(json.dumps({k:v for k,v in report.items() if k!='files'},ensure_ascii=False),flush=True)
    except BaseException as exc:
        report.update(status='failed',error=repr(exc));save('verification.json',report);raise

if __name__=='__main__':main()
