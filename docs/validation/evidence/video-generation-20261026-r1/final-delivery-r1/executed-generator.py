"""Audit the frozen native delivery, real-model artifacts and preserved history."""
from datetime import datetime, timezone
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
from urllib.parse import unquote
import zipfile

import numpy as np
from PIL import Image

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/validation/evidence/video-generation-20261026-r1'
BASELINE='d5d8e7f8915b23f1e67103f44469bccd0dd0e1de'
GIT='C:/Users/carzy/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/git/cmd/git.exe'


def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
def load(path):return json.loads(Path(path).read_bytes())
def git(*args):return subprocess.check_output([GIT,'--no-optional-locks','-c','core.fsmonitor=false','-c','gc.auto=0','-c','maintenance.auto=false',*args],cwd=ROOT,timeout=600)
def rows(text,prefix):return {m[1]:m[0] for m in re.finditer(r'^\| ('+prefix+r'\d{2,3})\s*\|.*$',text,re.M)}


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--run',required=True);a=ap.parse_args();assert re.fullmatch(r'r[1-9][0-9]*',a.run)
    out=BASE/('final-delivery-'+a.run);out.mkdir(exist_ok=False)
    (out/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    report=dict(status='running',goal_complete=False,at_utc=datetime.now(timezone.utc).isoformat(),source_fallback=False,virtualization=False)
    def save():(out/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
    save()
    try:
        assert git('rev-parse','HEAD').decode().strip()==BASELINE
        assert git('branch','--show-current').strip()==b'main'
        assert git('remote','get-url','origin').strip()==b'git@github.com:copypasteltd/agent-editor-kit.git'
        installed=load(BASE/'installation-final-r1/verification.json');package=Path(installed['installed'])
        pins={p.name:sha(p) for p in (ROOT/'product/src/ai_ad_editor').glob('*.py')};assert len(pins)==227
        assert pins=={p.name:sha(p) for p in (package/'site/ai_ad_editor').glob('*.py')}
        assert pins=={r['path']:r['sha256'] for r in installed['source_files']}
        assert sha(installed['archive'])==installed['archive_sha256'] and Path(installed['archive']).stat().st_size==installed['archive_bytes']
        assert (ROOT/'docs/specs/agent-project.schema.json').read_bytes()==(package/'site/ai_ad_editor/agent-project.schema.json').read_bytes()
        groups=[]
        for path,count in [('generation-installed-r1',14),('conversion-installed-r1',83),('legacy-installed-r1',192),('vace-source-r1',160)]:
            result=load(BASE/path/'verification.json');assert result['status']=='passed' and result['tests']==count
            assert result['errors']==result['failures']==result['skipped']==0 and result['product_files']==pins and result['frozen_equal']
            if '-installed-' in path:assert (ROOT/Path(result['installed'])).resolve()==package.resolve()
            groups.append(dict(path=path,tests=count,installed=bool(result['installed'])))
        development=load(BASE/'development-attempts-r1/verification.json')
        assert development['status']=='recorded' and development['final_product_files']==227
        assert development['failed_attempts_retained'] and not development['model_checks_weakened']
        namespace=load(ROOT/'agent-ffmpeg-local-install-manifest.json');runtime=load(ROOT/'local/agent-ffmpeg/runtime.json')
        assert namespace['cli_version']=='0.1.33' and namespace['skill_count']==1 and namespace['module_count']==17 and len(namespace['files'])==74
        assert namespace['release']==runtime['release']=='v0.1.0-alpha.4-local.31'
        assert namespace['manifest_sha256']==runtime['manifest_sha256']==installed['manifest_sha256']
        assert Path(runtime['installed_directory']).resolve()==package.resolve()
        for item in namespace['files']:assert sha(ROOT/item['path'])==item['sha256'] and (ROOT/item['path']).stat().st_size==item['bytes']
        assert Path('C:/Users/carzy/.codex/skills/agent-ffmpeg-local-editor').resolve()==(ROOT/'skills/agent-ffmpeg-local-editor').resolve()
        activation=load(BASE/'activation-final-r1/activation-and-registration.json');assert activation['status']=='passed' and len(activation['activation']['verified_packs'])==4
        registration=load(BASE/'registration-final-r1.json');assert registration['namespace_manifest_sha256']==sha(ROOT/'agent-ffmpeg-local-install-manifest.json')
        kit=load(ROOT/'docs/skills/community-unified-skill-package-0.1.33-r34.json');assert kit['files']==114 and sha(ROOT/kit['archive'])==kit['sha256']
        fresh=load(BASE/'kit-r2/verification.json');assert fresh['status']=='passed' and fresh['files']==114 and fresh['skill_files']==74 and not fresh['real_discovery_changed']
        assert fresh['installer_timeout_preserves_prior_configuration'] and not fresh['integrity_checks_skipped']
        configured=load(BASE/'kit-r2/configure.stdout.txt');assert configured['verify_timeout_seconds']==600 and len(configured['verified_packs'])==4
        failed_deadline=load(BASE/'kit-r2/expected-verification-timeout.json')
        assert failed_deadline['status']=='verification-timeout' and failed_deadline['earlier_runtime_configuration_unchanged']
        with zipfile.ZipFile(ROOT/kit['archive']) as archive:
            assert len(archive.namelist())==114 and 'docs/product/VIDEO_GENERATION.md' in archive.namelist()
            assert archive.read('agent-ffmpeg-local-install-manifest.json')==(ROOT/'agent-ffmpeg-local-install-manifest.json').read_bytes()
            for item in namespace['files']:assert hashlib.sha256(archive.read(item['path'])).hexdigest()==item['sha256']
            for item in json.loads(archive.read('KIT-FILES.json'))['files']:
                if not item['path'].startswith('docs/'):
                    assert archive.read(item['path'])==(ROOT/item['path']).read_bytes(),item['path']
                elif item['path'].endswith('.md'):
                    def externalize(match):
                        target=match[2]
                        if re.match(r'^[a-z]+:',target) or target.startswith('#'):return match.group()
                        plain,mark,fragment=target.partition('#')
                        resolved=(ROOT/item['path']).parent.joinpath(plain).resolve()
                        assert resolved.is_relative_to(ROOT)
                        relative=resolved.relative_to(ROOT).as_posix()
                        if relative in archive.namelist():return match.group()
                        assert resolved.exists()
                        return match[1]+'https://github.com/copypasteltd/agent-editor-kit/blob/main/'+relative+(mark+fragment if mark else '')+')'
                    expected=re.sub(r'(!?\[[^\]]*\]\()([^\n)]+)\)',externalize,(ROOT/item['path']).read_text('utf8')).encode('utf8')
                    assert archive.read(item['path'])==expected,item['path']
        case=load(BASE/'case-r1/verification.json');assert case['status']=='passed_actual_four_mode_cuda_transport_and_editable_package'
        assert not case['synthetic_worker'] and not case['source_fallback'] and len(case['modes'])==4 and all(c['ok'] for c in case['checks'])
        assert case['new_model_windows']==4 and case['diffusion_steps_per_window']==18
        parent=Path(case['project']).parent;source=Path(case['project']);project=load(source/'project.json')
        assets={row['id']:row for row in project['assets']};endpoints=0
        for row in case['modes']:
            assert sha(row['output'])==row['output_sha256']
            raw=(parent/(row['mode']+'-decode.bin')).read_bytes();assert hashlib.sha256(raw).hexdigest()==row['raw_rgba_sha256']
            frames=np.frombuffer(raw,np.uint8).reshape(17,144,256,4);assert np.all(frames[:,:,:,3]==255)
            asset=assets[row['mode']];recipe=asset['source']['video_generation']
            for name,image in recipe['images'].items():
                with Image.open(source/assets[image['asset_id']]['uri']) as opened:
                    rgb=np.asarray(opened.convert('RGB'));reference=np.concatenate([rgb,np.full((*rgb.shape[:2],1),255,np.uint8)],axis=2)
                np.testing.assert_array_equal(frames[0 if name=='first' else -1],reference);endpoints+=1
            generated=frames[1:-1,:,:,:3];assert np.any(generated!=127)
            execution=row['model_execution'];assert execution['window_input_shapes']==[[17,144,256]]
            assert execution['transformer_precision']=='bfloat16-with-declared-float32-stability-modules' and execution['vae_precision']=='float32'
            assert execution['gpu_admission']['reservation'] is False and execution['text_encoder_released_before_generation']
            assert row['rights_status']=='unverified' and row['generated_quality_accepted'] is False
        assert endpoints==4 and sha(case['package'])==case['package_sha256']
        for call in case['calls']:
            assert call['exit_code']==call['expected_exit_code']
            stdout=parent/(call['name']+'.bin') if call['name'].endswith('-decode') else BASE/'case-r1'/(call['name']+'.stdout.json')
            assert sha(stdout)==call['stdout_sha256']
            assert sha(BASE/'case-r1'/(call['name']+'.stderr.log'))==call['stderr_sha256']
        inspection=load(BASE/'media-inspection-r1/verification.json');assert inspection['status']=='passed' and len(inspection['cases'])==4
        assert len(inspection['package_asset_checks'])==6 and all(row['equal'] for row in inspection['package_asset_checks'])
        rendered=load(BASE/'render-roundtrip-r1/verification.json');assert rendered['status']=='passed' and rendered['registered_skill']
        assert rendered['decoded_equal_frames']==170 and rendered['source_and_imported_pixels_equal'] and rendered['new_model_windows']==0
        visual=load(BASE/'static-review-r1.json');assert visual['static_image_review'] and not visual['natural_quality_accepted'] and not visual['continuous_playback']
        public=ROOT/'docs/assets/video-generation-20261026-r1'
        assert {p.name for p in public.iterdir()}=={'first.png','last.png','conditions.png','SOURCE.txt','PUBLICATION_SCOPE.txt'}
        caps=load(ROOT/'docs/product/video-generation-capabilities-cli-0.1.33.json')['data']['capabilities'];assert len(caps)==75
        assert len(caps['generative_video_editing']['complete_video_generation']['modes'])==4
        for suffix,name in [('','README.md'),('.zh-TW','README.zh-TW.md'),('.en','README.en.md')]:
            text=(ROOT/name).read_text('utf-8-sig');old=rows(git('show',BASELINE+':'+name).decode('utf-8-sig'),'R')
            assert len(old)==229 and len(rows(text,'R'))==235 and all(rows(text,'R')[k]==v for k,v in old.items())
            assert len(rows(text,'F'))==61 and len(rows(text,'S'))==20 and len(rows(text,'K'))==17
            assert 'CLI0.1.33 / alpha.4-local.31 / r34 kit' in text and 'local.31/final-r1/installed' in text
            manual=(ROOT/('docs/product/CAPABILITIES'+suffix+'.md')).read_text('utf-8-sig')
            assert len(rows(manual,'F'))==61 and len(rows(manual,'S'))==20
            for key,value in caps.items():
                match=re.search(r'^### `'+re.escape(key)+r'`\s*\n\n```json\n(.*?)\n```',manual,re.M|re.S)
                assert match and json.loads(match[1])==value,key
        gap='docs/product/GOAL_GAPS_20261025.md';old=rows(git('show',BASELINE+':'+gap).decode('utf-8-sig'),'G');now=rows((ROOT/gap).read_text('utf-8-sig'),'G')
        assert len(old)==len(now)==38 and all(now[k].split('|')[5]==v.split('|')[5] for k,v in old.items())
        assert 'CLI0.1.33' in now['G23'].split('|')[3]
        changed=set(git('diff','HEAD','--name-only','-z').decode('utf8').split('\0'))|set(git('ls-files','--others','--exclude-standard','-z').decode('utf8').split('\0'))
        (out/'product-files.json').write_text(json.dumps(pins,indent=2)+'\n',encoding='utf8')
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
        (out/'files.json').write_text(json.dumps(files,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
        report.update(status='passed',cli_version='0.1.33',product_files=227,groups=groups,
            actual_cuda_modes=4,actual_rgba_frames=68,independent_endpoints=4,skill_files=74,kit_files=114,
            historical_R_rows_preserved=229,current_R_rows=235,original_G_closure_cells_preserved=38,
            functional_rows=61,services=20,modules=17,capability_declarations=75,local_links_checked=links,
            model_media_published=False,natural_quality_accepted=False,files=len(files));save();print(json.dumps(report,ensure_ascii=False))
    except BaseException as exc:report.update(status='failed',error=repr(exc));save();raise


if __name__=='__main__':main()
