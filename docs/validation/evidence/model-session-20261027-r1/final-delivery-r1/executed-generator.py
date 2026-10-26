"""Audit installed native sessions, real CUDA evidence, usable Skill and preserved history."""
from datetime import datetime, timezone
import argparse
import ctypes
from ctypes import wintypes
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
BASE=ROOT/'docs/validation/evidence/model-session-20261027-r1'
BASELINE='18b93ceae20e78ed44fb9d6e6e58ee874cec3c5a'
GIT='C:/Users/carzy/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/git/cmd/git.exe'


def sha(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()
def load(path):return json.loads(Path(path).read_bytes())
def git(*args):return subprocess.check_output([GIT,'--no-optional-locks','-c','core.fsmonitor=false','-c','gc.auto=0','-c','maintenance.auto=false',*args],cwd=ROOT,timeout=600)
def rows(text,prefix):return {m[1]:m[0] for m in re.finditer(r'^\| ('+prefix+r'\d{2,3})\s*\|.*$',text,re.M)}


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--run',required=True);a=parser.parse_args();assert re.fullmatch(r'r[1-9][0-9]*',a.run)
    out=BASE/('final-delivery-'+a.run);out.mkdir(exist_ok=False);(out/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    report=dict(status='running',goal_complete=False,at_utc=datetime.now(timezone.utc).isoformat(),source_fallback=False,virtualization=False)
    def save():(out/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    save()
    try:
        assert git('rev-parse','HEAD').decode().strip()==BASELINE and git('branch','--show-current').strip()==b'main'
        assert git('remote','get-url','origin').strip()==b'git@github.com:copypasteltd/agent-editor-kit.git'
        installed=load(BASE/'installation-final-r3/verification.json');package=Path(installed['installed'])
        pins={p.name:sha(p) for p in (ROOT/'product/src/ai_ad_editor').glob('*.py')};assert len(pins)==230
        assert pins=={p.name:sha(p) for p in (package/'site/ai_ad_editor').glob('*.py')}=={r['path']:r['sha256'] for r in installed['source_files']}
        assert sha(installed['archive'])==installed['archive_sha256'] and Path(installed['archive']).stat().st_size==installed['archive_bytes']
        assert (ROOT/'docs/specs/agent-project.schema.json').read_bytes()==(package/'site/ai_ad_editor/agent-project.schema.json').read_bytes()
        groups=[]
        for name,count in [('session-installed-r2',19),('generation-installed-r2',14),('vace-installed-r3',161),('legacy-installed-r2',192)]:
            result=load(BASE/name/'verification.json');assert result['status']=='passed' and result['tests']==count
            assert result['errors']==result['failures']==result['skipped']==0 and result['product_files']==pins and result['frozen_equal']
            assert (ROOT/Path(result['installed'])).resolve()==package.resolve();groups.append(dict(path=name,tests=count))
        development=load(BASE/'development-attempts-r2/verification.json');assert development['status']=='recorded' and development['final_product_files']==230
        namespace=load(ROOT/'agent-ffmpeg-local-install-manifest.json');runtime=load(ROOT/'local/agent-ffmpeg/runtime.json')
        assert namespace['cli_version']=='0.1.34' and namespace['skill_count']==1 and namespace['module_count']==17 and len(namespace['files'])==75
        assert namespace['release']==runtime['release']=='v0.1.0-alpha.4-local.32'
        assert namespace['manifest_sha256']==runtime['manifest_sha256']==installed['manifest_sha256']
        assert Path(runtime['installed_directory']).resolve()==package.resolve()
        for item in namespace['files']:assert sha(ROOT/item['path'])==item['sha256'] and (ROOT/item['path']).stat().st_size==item['bytes']
        assert Path('C:/Users/carzy/.codex/skills/agent-ffmpeg-local-editor').resolve()==(ROOT/'skills/agent-ffmpeg-local-editor').resolve()
        activation=load(BASE/'activation-final-r2/activation-and-registration.json');assert activation['status']=='passed' and len(activation['activation']['verified_packs'])==4
        registration=load(BASE/'registration-preflight-r1/registration-final.json');assert registration['namespace_manifest_sha256']==sha(ROOT/'agent-ffmpeg-local-install-manifest.json')
        assert registration['launcher_preflight_verified'] and registration['registered_cli_version']=='0.1.34'
        preflight=load(BASE/'registration-preflight-r1/verification.json')
        assert preflight['status']=='passed' and preflight['stale_pin_rejected_before_discovery_mutation']
        assert sha(ROOT/'scripts/register_unified_skill.ps1')==preflight['registration_script_sha256']
        assert load(BASE/'skill-registration-r1/verification.json')['status']=='passed'
        kit=load(ROOT/'docs/skills/community-unified-skill-package-0.1.34-r35.json');assert kit['files']==116 and sha(ROOT/kit['archive'])==kit['sha256']
        fresh=load(BASE/'kit-r3/verification.json');assert fresh['status']=='passed' and fresh['files']==116 and fresh['skill_files']==75 and not fresh['real_discovery_changed']
        assert fresh['installer_timeout_preserves_prior_configuration'] and not fresh['integrity_checks_skipped']
        with zipfile.ZipFile(ROOT/kit['archive']) as zipped:
            assert len(zipped.namelist())==116 and 'docs/product/MODEL_SESSIONS.md' in zipped.namelist()
            assert zipped.read('agent-ffmpeg-local-install-manifest.json')==(ROOT/'agent-ffmpeg-local-install-manifest.json').read_bytes()
            for item in namespace['files']:assert hashlib.sha256(zipped.read(item['path'])).hexdigest()==item['sha256']
        case=load(BASE/'case-r1/verification.json');assert case['status']=='passed_actual_cuda_resident_reuse_and_cancel'
        correction=load(BASE/'control-fix-r1/verification.json')
        assert correction['status']=='passed' and correction['byte_identical_non_cli_files']==229
        assert correction['entire_remaining_cli_ast_identical'] and correction['model_generate_lock_unchanged']
        assert correction['control_test_failed_before'] and correction['control_test_passed_after']
        assert Path(correction['measured_gpu_installation']).resolve()==Path(case['installed']).resolve()
        assert Path(correction['final_installation']).resolve()==package.resolve()
        for row in correction['model_implementation_artifacts_identical']:
            assert 'sha256:'+sha(package/'site/ai_ad_editor'/row['path'])==row['sha256']
        assert not case['synthetic_model'] and not case['source_fallback'] and len(case['jobs'])==3 and all(c['ok'] for c in case['checks'])
        assert case['replay_comparison']==dict(frames=17,equal=True,changed_channels=0,maximum_absolute_difference=0)
        project=Path(case['project']);parent=project.parent;author=load(project/'project.json');assets={a['id']:a for a in author['assets']}
        endpoints=0
        for i,row in enumerate(case['jobs']):
            assert sha(row['output'])==row['sha256']
            raw=(parent/(row['asset_id']+'-decode.bin')).read_bytes();assert 'sha256:'+hashlib.sha256(raw).hexdigest()==row['rgba_sha256']
            frames=np.frombuffer(raw,np.uint8).reshape(17,144,256,4);assert np.all(frames[:,:,:,3]==255)
            execution=row['model_execution'];reuse=execution['resident_model']
            assert reuse['inference_job']==i+1 and reuse['predictor_loads']==reuse['text_encoder_loads']==1 and reuse['reused']==bool(i)
            assert len(execution['window_seconds'])==execution['gpu_admission']['windows']['count']==1
            for name,image in assets[row['asset_id']]['source']['video_generation']['images'].items():
                with Image.open(project/assets[image['asset_id']]['uri']) as opened:
                    rgb=np.asarray(opened.convert('RGB'));reference=np.concatenate([rgb,np.full((*rgb.shape[:2],1),255,np.uint8)],axis=2)
                np.testing.assert_array_equal(frames[0 if name=='first' else -1],reference);endpoints+=1
        assert endpoints==5
        for call in case['calls']:
            assert call['exit_code']==call['expected_exit_code']
            stdout=parent/(call['name']+'.bin') if call['name'].endswith('-decode') else BASE/'case-r1'/(call['name']+'.stdout.json')
            assert sha(stdout)==call['stdout_sha256'] and sha(BASE/'case-r1'/(call['name']+'.stderr.log'))==call['stderr_sha256']
        cancelled=next(call for call in case['calls'] if call['name']=='actual-denoise-cancelled')
        assert cancelled['cancel_sent_after_denoising'] and cancelled['exit_code']==8
        assert not case['stopped_session']['live'] and case['stopped_session']['active_task_interrupted']
        kernel=ctypes.WinDLL('kernel32',use_last_error=True)
        kernel.OpenProcess.argtypes=[wintypes.DWORD,wintypes.BOOL,wintypes.DWORD];kernel.OpenProcess.restype=wintypes.HANDLE
        kernel.WaitForSingleObject.argtypes=[wintypes.HANDLE,wintypes.DWORD];kernel.WaitForSingleObject.restype=wintypes.DWORD
        kernel.CloseHandle.argtypes=[wintypes.HANDLE];kernel.CloseHandle.restype=wintypes.BOOL
        handle=kernel.OpenProcess(0x100000,False,case['stopped_session']['pid'])
        if handle:
            try:assert kernel.WaitForSingleObject(handle,0)==0,'owned model process is still alive'
            finally:kernel.CloseHandle(handle)
        else:assert ctypes.get_last_error()==87,'cannot confirm owned process exit'
        resource=load(BASE/'resources-r1/verification.json');assert resource['status']=='completed' and resource['process_samples']>0 and resource['peak_working_set_bytes']>0
        rendered=load(BASE/'render-roundtrip-r2/verification.json');assert rendered['status']=='passed' and rendered['registered_skill']
        assert rendered['decoded_equal_frames']==128 and rendered['source_and_imported_pixels_equal'] and rendered['new_model_windows']==0
        inspection=load(BASE/'media-inspection-r1/verification.json');assert inspection['status']=='passed' and len(inspection['cases'])==3
        assert len(inspection['package_asset_checks'])==5 and all(x['equal'] for x in inspection['package_asset_checks'])
        review=load(BASE/'static-review-r1.json');assert review['static_image_review'] and not review['natural_quality_accepted'] and not review['continuous_playback']
        private=load(project/'cache/model-sessions'/case['session_start']['session_id']/'private.json')['auth'].encode('ascii')
        with zipfile.ZipFile(parent/'editable-resident-videos.aevpkg.zip') as zipped:
            assert not any('private.json' in name or '/model-sessions/' in name for name in zipped.namelist())
            assert all(private not in zipped.read(name) for name in zipped.namelist())
        public=ROOT/'docs/assets/model-session-20261027-r1'
        assert {p.name for p in public.iterdir()}=={'timing.png','timing-data.json','SOURCE.txt','PUBLICATION_SCOPE.txt'}
        caps=load(ROOT/'docs/product/model-session-capabilities-cli-0.1.34.json')['data']['capabilities'];assert len(caps)==75
        assert caps['generative_video_editing']['complete_video_generation']['model_session']['status']=='implemented_with_limits'
        for suffix,name in [('','README.md'),('.zh-TW','README.zh-TW.md'),('.en','README.en.md')]:
            text=(ROOT/name).read_text('utf-8-sig');old=rows(git('show',BASELINE+':'+name).decode('utf-8-sig'),'R')
            assert len(old)==235 and len(rows(text,'R'))==241 and all(rows(text,'R')[k]==v for k,v in old.items())
            assert len(rows(text,'F'))==62 and len(rows(text,'S'))==21 and len(rows(text,'K'))==17
            assert 'CLI0.1.34 / alpha.4-local.32 / r35 kit' in text and 'local.32/final-r3/installed' in text
            manual=(ROOT/('docs/product/CAPABILITIES'+suffix+'.md')).read_text('utf8')
            assert len(rows(manual,'F'))==62 and len(rows(manual,'S'))==21
            for key,value in caps.items():
                match=re.search(r'^### `'+re.escape(key)+r'`\s*\n\n```json\n(.*?)\n```',manual,re.M|re.S)
                assert match and json.loads(match[1])==value,key
        gap='docs/product/GOAL_GAPS_20261025.md';old=rows(git('show',BASELINE+':'+gap).decode('utf-8-sig'),'G');now=rows((ROOT/gap).read_text('utf8'),'G')
        assert len(old)==len(now)==38 and all(now[k].split('|')[5]==v.split('|')[5] for k,v in old.items())
        changed=set(git('diff','HEAD','--name-only','-z').decode('utf8').split('\0'))|set(git('ls-files','--others','--exclude-standard','-z').decode('utf8').split('\0'))
        (out/'product-files.json').write_text(json.dumps(pins,indent=2)+'\n',encoding='utf8',newline='\n')
        files=[];links=0
        for name in sorted(changed):
            if not name or (ROOT/name).is_relative_to(out):continue
            assert not name.startswith(('local/','workspace/','sources/')),name
            path=ROOT/name;assert path.is_file() and path.stat().st_size<95*1024**2,name
            assert private not in path.read_bytes(),'private credential leaked: '+name
            if path.suffix=='.md':
                for target in re.findall(r'!?\[[^\]]*\]\(([^\n)]+)\)',path.read_text('utf-8-sig')):
                    target=target.strip().strip('<>')
                    if re.match(r'^[a-z][a-z0-9+.-]*:',target,re.I) or target.startswith('#'):continue
                    assert (path.parent/unquote(target.split('#')[0])).resolve().exists(),(name,target)
                    links+=1
            files.append(dict(path=name,bytes=path.stat().st_size,sha256=sha(path)))
        (out/'files.json').write_text(json.dumps(files,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
        report.update(status='passed',cli_version='0.1.34',product_files=230,groups=groups,actual_cuda_completed_jobs=3,
            actual_rgba_frames=51,independent_endpoints=5,pixel_identical_replay_frames=17,actual_cuda_denoising_cancel=True,
            owned_process_exit_confirmed=True,skill_files=75,kit_files=116,historical_R_rows_preserved=235,current_R_rows=241,
            original_G_closure_cells_preserved=38,functional_rows=62,services=21,modules=17,capability_declarations=75,
            control_cli_available_during_project_write=True,measured_inference_kernel_identical_after_control_fix=True,
            gpu_case_rerun_after_control_fix=False,local_links_checked=links,model_media_published=False,private_credentials_published=False,natural_quality_accepted=False,files=len(files))
        save();print(json.dumps(report,ensure_ascii=False),flush=True)
    except BaseException as exc:report.update(status='failed',error=repr(exc));save();raise


if __name__=='__main__':main()
