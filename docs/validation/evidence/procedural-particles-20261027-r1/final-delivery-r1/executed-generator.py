"""Audit actual installed particle delivery without reducing the original goal."""
from pathlib import Path
from datetime import datetime,timezone
import argparse,hashlib,json,re,subprocess,zipfile
from urllib.parse import unquote
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/validation/evidence/procedural-particles-20261027-r1'
BASELINE='10520dee506a3f48dc465813be6fa70a05ce6610'
GIT='C:/Users/carzy/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/git/cmd/git.exe'

def load(p):return json.loads(Path(p).read_bytes())
def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def git(*args):return subprocess.check_output([GIT,'--no-optional-locks','-c','core.fsmonitor=false','-c','gc.auto=0','-c','maintenance.auto=false',*args],cwd=ROOT,timeout=600)
def rows(s,prefix):return {m[1]:m[0] for m in re.finditer(r'^\| ('+prefix+r'\d+)\s*\|.*$',s,re.M)}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--run',required=True);a=ap.parse_args();assert re.fullmatch('r[1-9][0-9]*',a.run)
    out=BASE/('final-delivery-'+a.run);out.mkdir(exist_ok=False)
    (out/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    report={'status':'running','goal_complete':False,'at_utc':datetime.now(timezone.utc).isoformat(),
        'native_windows':True,'virtualization':False,'source_fallback':False}
    def save():(out/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    save()
    try:
        assert git('rev-parse','HEAD').decode().strip()==BASELINE
        assert git('branch','--show-current').strip()==b'main'
        assert git('remote','get-url','origin').strip()==b'git@github.com:copypasteltd/agent-editor-kit.git'
        installed=load(BASE/'installation-final-r2/verification.json');package=Path(installed['installed'])
        pins={p.name:sha(p) for p in (ROOT/'product/src/ai_ad_editor').glob('*.py')}
        assert len(pins)==233 and pins=={p.name:sha(p) for p in (package/'site/ai_ad_editor').glob('*.py')}
        assert pins=={r['path']:r['sha256'] for r in installed['source_files']}
        assert sha(installed['archive'])==installed['archive_sha256'] and Path(installed['archive']).stat().st_size==installed['archive_bytes']
        assert installed['manifest_sha256']=='sha256:'+sha(ROOT/'local/agent-ffmpeg/v0.1.0-alpha.4-local.33/unpacked-r2/manifest.json')
        assert (ROOT/'docs/specs/agent-project.schema.json').read_bytes()==(package/'site/ai_ad_editor/agent-project.schema.json').read_bytes()
        groups=[]
        for name,count in [('installed-particles-r2',19),('installed-particle-gpu-r3',1),('installed-integration-r2',5),('installed-legacy-r2',192)]:
            result=load(BASE/name/'verification.json')
            assert result['status']=='passed' and result['tests']==count
            assert result['failures']==result['errors']==result['skipped']==0
            assert result['frozen_equal'] and result['test_frozen_equal'] and result['product_files']==pins
            assert (ROOT/Path(result['installed'])).resolve()==package.resolve()
            for file,digest in result['test_files'].items():
                assert sha(ROOT/'product/tests'/file)==digest==sha(BASE/name/'executed-tests'/file)
            groups.append({'attempt':name,'tests':count})
        change=load(BASE/'loader-final-r1/verification.json')
        assert change['byte_identical_product_files']==231 and change['pixel_and_GPU_kernels_byte_identical']
        assert change['changed_product_files']==['procedural_cli.py','utils.py']
        old=load(BASE/'installed-native-regression-r1/verification.json')
        assert old['status']=='passed' and old['tests']==427 and old['frozen_equal']
        assert [n for n in sorted(pins) if pins[n]!=old['product_files'][n]]==change['changed_product_files']
        gpu=load(BASE/'installed-particle-gpu-r3/receipts.json')['test_procedural_particles']['RECEIPTS'][0]
        assert gpu['operations']['particles']==23 and gpu['worker_closed'] and gpu['particle_cpu_max_error']<=3e-6
        case=load(BASE/'case-r3/verification.json');assert case['status']=='passed' and case['frame_count']==48
        assert case['actual_gpu_particle_dispatches']==288 and case['all_decoded_package_frames_equal'] and case['decoded_audio_all_zero']
        assert case['GPU']['worker_closed'] and Path(case['installed']).resolve()==package.resolve()
        assert case['manifest_sha256']==installed['manifest_sha256']
        media=ROOT/case['public'];manifest=load(media/'media-manifest.json')
        for name,record in manifest['files'].items():assert sha(media/name)==record['sha256'] and (media/name).stat().st_size==record['bytes']
        assert manifest['video_frames']==48 and manifest['video_fps']=='12/1' and manifest['authored_seconds']==4
        with Image.open(media/'particle-grid.gif') as gif:
            assert gif.n_frames==manifest['GIF_frames']==48
            assert sum((gif.seek(i) or gif.info['duration']) for i in range(gif.n_frames))==manifest['GIF_duration_ms']
        review=load(BASE/'static-review-r1.json')
        assert review['static_image_review'] and not review['continuous_playback'] and not review['natural_quality_accepted']
        assert review['image_sha256']==sha(media/'contact.png')
        namespace=load(ROOT/'agent-ffmpeg-local-install-manifest.json');runtime=load(ROOT/'local/agent-ffmpeg/runtime.json')
        assert namespace['cli_version']=='0.1.35' and namespace['skill_count']==1 and namespace['module_count']==17
        assert len(namespace['files'])==76 and namespace['release']==runtime['release']=='v0.1.0-alpha.4-local.33'
        assert namespace['manifest_sha256']==runtime['manifest_sha256']==installed['manifest_sha256']
        assert Path(runtime['installed_directory']).resolve()==package.resolve()
        for row in namespace['files']:assert sha(ROOT/row['path'])==row['sha256'] and (ROOT/row['path']).stat().st_size==row['bytes']
        assert Path('C:/Users/carzy/.codex/skills/agent-ffmpeg-local-editor').resolve()==(ROOT/'skills/agent-ffmpeg-local-editor').resolve()
        activation=load(BASE/'activation-final-r3/activation-and-registration.json');assert activation['status']=='passed'
        assert len(activation['activation']['verified_packs'])==4
        registration=load(BASE/'registration-final-r1.json')
        assert registration['namespace_manifest_sha256']==sha(ROOT/'agent-ffmpeg-local-install-manifest.json')
        assert registration['launcher_preflight_verified'] and registration['registered_cli_version']=='0.1.35'
        assert load(BASE/'development-attempts-r1/verification.json')['status']=='recorded'
        kit=load(ROOT/'docs/skills/community-unified-skill-package-0.1.35-r36.json')
        assert kit['files']==118 and sha(ROOT/kit['archive'])==kit['sha256']
        fresh=load(BASE/'kit-r1/verification.json')
        assert fresh['status']=='passed' and fresh['files']==118 and fresh['skill_files']==76 and not fresh['real_discovery_changed']
        with zipfile.ZipFile(ROOT/kit['archive']) as z:
            assert len(z.namelist())==118 and 'docs/product/PROCEDURAL_PARTICLES.md' in z.namelist()
            assert z.read('agent-ffmpeg-local-install-manifest.json')==(ROOT/'agent-ffmpeg-local-install-manifest.json').read_bytes()
            for row in namespace['files']:assert hashlib.sha256(z.read(row['path'])).hexdigest()==row['sha256']
        caps=load(ROOT/'docs/product/procedural-particles-capabilities-cli-0.1.35.json')['data']['capabilities'];assert len(caps)==76
        for suffix in ('','.zh-TW','.en'):
            name='README'+suffix+'.md';text=(ROOT/name).read_text('utf8')
            old=rows(git('show',BASELINE+':'+name).decode('utf8'),'R')
            assert len(old)==241 and len(rows(text,'R'))==247 and all(rows(text,'R')[k]==v for k,v in old.items())
            assert len(rows(text,'F'))==63 and len(rows(text,'S'))==21 and len(rows(text,'K'))==17
            assert 'CLI0.1.35 / alpha.4-local.33 / r36 kit' in text and 'local.33/final-r2/installed' in text
            manual=(ROOT/('docs/product/CAPABILITIES'+suffix+'.md')).read_text('utf8')
            assert len(rows(manual,'F'))==63 and len(rows(manual,'S'))==21
            for key,value in caps.items():
                m=re.search(r'^### `'+re.escape(key)+r'`\s*\n\n```json\n(.*?)\n```',manual,re.M|re.S)
                assert m and json.loads(m[1])==value,key
        gap='docs/product/GOAL_GAPS_20261025.md'
        old=rows(git('show',BASELINE+':'+gap).decode('utf8'),'G');now=rows((ROOT/gap).read_text('utf8'),'G')
        assert len(old)==len(now)==38 and all(now[k].split('|')[5]==v.split('|')[5] for k,v in old.items())
        # The implementation ledger must still include every previously authored line;
        # only the newest current-version label is demoted to history.
        path='docs/product/IMPLEMENTATION_PLAN_20261025.md';old=git('show',BASELINE+':'+path).decode('utf8')
        text=(ROOT/path).read_text('utf8')
        assert all(line in text for line in old.replace('当前本地 **CLI0.1.34','此前本地 **CLI0.1.34',1).splitlines() if line)
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
            files.append({'path':name,'bytes':path.stat().st_size,'sha256':sha(path)})
        (out/'files.json').write_text(json.dumps(files,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
        (out/'product-files.json').write_text(json.dumps(pins,indent=2)+'\n',encoding='utf8',newline='\n')
        report.update(status='passed',cli_version='0.1.35',product_files=233,groups=groups,earlier_native_regression_tests=427,
            earlier_native_regression_final_r1=True,byte_identical_after_input_fix=231,particle_gpu_comparisons=23,
            particle_gpu_max_error=gpu['particle_cpu_max_error'],case_frames=48,case_gpu_dispatches=288,
            all_package_frames_equal=True,skill_files=76,kit_files=118,historical_R_rows_preserved=241,current_R_rows=247,
            original_G_closure_cells_preserved=38,functional_rows=63,services=21,modules=17,capability_declarations=76,
            local_links_checked=links,natural_quality_accepted=False,files=len(files))
        save();print(json.dumps(report,ensure_ascii=False),flush=True)
    except BaseException as exc:report.update(status='failed',error=repr(exc));save();raise

if __name__=='__main__':main()
