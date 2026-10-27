"""Audit tested artifacts, complete history, trilingual manuals and final kit."""
from pathlib import Path
from datetime import datetime,timezone
from urllib.parse import unquote
import argparse
import hashlib
import json
import re
import subprocess
import zipfile

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/validation/evidence/native-hdr-20261027-r1'
BASELINE='af9fc64391945901a641fc33b86438d26754a00d'
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
        assert len(pins)==240 and pins=={p.name:sha(p) for p in (package/'site/ai_ad_editor').glob('*.py')}
        assert pins=={r['path']:r['sha256'] for r in install['source_files']}
        assert install['status']=='installed-and-byte-verified' and install['cli_version']=='0.1.40' and install['capability_count']==79
        assert sha(install['archive'])==install['archive_sha256'] and Path(install['archive']).stat().st_size==install['archive_bytes']
        assert install['manifest_sha256']=='sha256:'+sha(ROOT/'local/agent-ffmpeg/v0.1.0-alpha.4-local.38/unpacked-r1/manifest.json')
        schema=(ROOT/'docs/specs/agent-project.schema.json').read_bytes()
        assert schema==(package/'site/ai_ad_editor/agent-project.schema.json').read_bytes()==(ROOT/'product/src/ai_ad_editor/agent-project.schema.json').read_bytes()
        assert hashlib.sha256(schema).hexdigest()=='ea1e439a7ffb6ca7da065cc2ddd872b6b567d47e9275a0dd8b40ee099c5340f4'
        tests=load(BASE/'installed-regression-r2/verification.json')
        assert tests['status']=='passed' and tests['tests']==993 and tests['failures']==tests['errors']==tests['skipped']==0
        assert tests['frozen_equal'] and tests['test_frozen_equal'] and tests['product_files']==pins
        assert Path(tests['installed']).resolve()==package.resolve()
        for name,digest in tests['test_files'].items():assert sha(ROOT/'product/tests'/name)==digest==sha(BASE/'installed-regression-r2/executed-tests'/name)
        assert (BASE/'installed-regression-r2/executed-runner.py').read_bytes()==(ROOT/'scripts/test_hdr_20261027.py').read_bytes()
        outcomes=re.findall(r'^(test_\S+) \(([^)]+)\)(?:\n[^\n]*)? \.\.\. (ok|FAIL|ERROR|skipped[^\n]*)$',
            (BASE/'installed-regression-r2/tests.log').read_text('utf8'),re.M)
        assert len(outcomes)==len({r[1] for r in outcomes})==993 and all(r[2]=='ok' for r in outcomes)
        (out/'test-outcomes.json').write_text(json.dumps([dict(id=r[1],status=r[2]) for r in outcomes],indent=2)+'\n',encoding='utf8',newline='\n')
        for attempt,count in [('source-numeric-r4',12),('source-compat-r1',239)]:
            r=load(BASE/attempt/'verification.json');assert r['status']=='passed' and r['tests']==count and r['frozen_equal'] and r['test_frozen_equal']
        case=load(BASE/'case-r3/verification.json')
        assert case['status']=='passed' and case['all_48_decoded_10bit_frames_equal'] and case['all_384000_PCM_equal'] and case['PCM_nonzero']
        assert case['editable_absolute_signals_preserved'] and case['author_bytes_unchanged_by_preview'] and case['GIF_frames']==48 and case['GIF_duration_ms']==4000
        assert not case['source_fallback'] and case['registered_skill'] and not case['HDR_monitor_accepted'] and not case['natural_quality_accepted']
        assert load(BASE/'case-r3/version.stdout.json')['data']['cli_version']=='0.1.40'
        work=ROOT/'local/agent-ffmpeg/native-hdr-case-r3'
        for group,names,expected_bytes,digest in [
            ('video',['decode-pq.bin','decode-restored.bin'],48*640*360*6,case['decoded_video_sha256']),
            ('audio',['audio-pq.bin','audio-restored.bin'],384000*4,case['decoded_PCM_sha256'])]:
            for name in names:assert (work/name).stat().st_size==expected_bytes and sha(work/name)==digest
        media=Path(case['public']);m=load(media/'media-manifest.json');assert m['frames']==48 and m['fps']==12 and m['duration_seconds']==4
        for r in m['files']:assert sha(media/r['path'])==r['sha256'] and (media/r['path']).stat().st_size==r['bytes']
        assert sha(media/'editable-native-hdr.aevpkg.zip')==case['package_sha256']
        for name,transfer in [('pq','smpte2084'),('hlg','arib-std-b67'),('sdr','iec61966-2-1')]:
            assert case['streams'][name]['color_transfer']==transfer and case['streams'][name]['pix_fmt']=='yuv444p10le'
            manifest=load(media/(name+'-master.mkv.manifest.json'))
            assert manifest['delivery']['pixel_pipeline']['transport']['frames']==48
            g=manifest['delivery']['pixel_pipeline']['projection_acceleration']
            assert g['operations']['glow']==48 and g['worker_closed'] and g['shared_handles_closed']
            assert g['control']['threads_closed'] and g['control']['streams_closed'] and not g['runtime_failure_CPU_fallback']
            assert g['probe']['actual_gpu_operations']==17 and g['probe']['glow_gpu_operations']==8
        review=load(BASE/'static-chart-review.json');assert review['status']=='reviewed' and not review['continuous_human_playback'] and not review['human_listening'] and not review['HDR_monitor_accepted']
        for name,digest in review['files'].items():assert sha(media/name)==digest
        usage=load(BASE/'documented-workflow-r1/verification.json')
        assert usage['status']=='passed' and usage['exact_documented_workflow_executed'] and usage['all_48_frames_match_case'] and usage['CLI_calls']==5
        assert usage['guide_sha256']==sha(ROOT/'docs/product/HDR_DISPLAY.md')
        namespace=load(ROOT/'agent-ffmpeg-local-install-manifest.json');runtime=load(ROOT/'local/agent-ffmpeg/runtime.json')
        assert namespace['cli_version']=='0.1.40' and namespace['skill_count']==1 and namespace['module_count']==17 and len(namespace['files'])==79
        assert namespace['release']==runtime['release']=='v0.1.0-alpha.4-local.38'
        assert namespace['manifest_sha256']==runtime['manifest_sha256']==install['manifest_sha256'] and Path(runtime['installed_directory']).resolve()==package.resolve()
        for r in namespace['files']:assert sha(ROOT/r['path'])==r['sha256'] and (ROOT/r['path']).stat().st_size==r['bytes']
        assert Path('C:/Users/carzy/.codex/skills/agent-ffmpeg-local-editor').resolve()==(ROOT/'skills/agent-ffmpeg-local-editor').resolve()
        activation=load(BASE/'activation-final-r1/activation-and-registration.json');assert activation['status']=='passed' and len(activation['activation']['verified_packs'])==4
        registration=load(BASE/'registration-final-r1.json');assert registration['namespace_manifest_sha256']==sha(ROOT/'agent-ffmpeg-local-install-manifest.json')
        assert registration['launcher_preflight_verified'] and registration['registered_cli_version']=='0.1.40'
        kit=load(ROOT/'docs/skills/community-unified-skill-package-0.1.40-r41.json');assert kit['files']==126 and sha(ROOT/kit['archive'])==kit['sha256']
        fresh=load(BASE/'kit-r1/verification.json');assert fresh['status']=='passed' and fresh['files']==126 and fresh['skill_files']==79 and not fresh['real_discovery_changed']
        assert fresh['process_calls']==32 and fresh['new_renders']==fresh['new_model_forwards']==0
        with zipfile.ZipFile(ROOT/kit['archive']) as z:assert len(z.namelist())==126 and 'docs/product/HDR_DISPLAY.md' in z.namelist()
        caps=load(ROOT/'docs/product/native-hdr-capabilities-cli-0.1.40.json')['data']['capabilities'];assert len(caps)==79
        assert caps['native_hdr_display_pipeline']['protocol']=='explicit-display-nits-PQ-HLG-float32-v1'
        for suffix in ('','.zh-TW','.en'):
            name='README'+suffix+'.md';text=(ROOT/name).read_text('utf8');old=rows(git('show',BASELINE+':'+name).decode('utf8'),'R')
            assert len(old)==271 and len(rows(text,'R'))==277 and all(rows(text,'R')[k]==v for k,v in old.items())
            assert len(rows(text,'F'))==66 and len(rows(text,'S'))==21 and len(rows(text,'K'))==17
            assert 'CLI0.1.40 / alpha.4-local.38 / r41 kit' in text and 'local.38/final-r1/installed' in text
            manual=(ROOT/('docs/product/CAPABILITIES'+suffix+'.md')).read_text('utf8')
            assert len(rows(manual,'F'))==66 and len(rows(manual,'S'))==21
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
        report.update(status='passed',product_files=240,capabilities=79,installed_tests=993,unique_installed_tests=993,
            source_and_installed_equal=True,all_48_frames_and_PCM_equal=True,HDR_transfers=2,actual_HDR_SDR_case=True,
            skill_files=79,kit_files=126,readme_prior_R_rows_preserved=271,readme_R_rows=277,
            goal_closure_cells_preserved=38,changed_files=len(files),local_links_verified=links)
        save();print(json.dumps(report,ensure_ascii=False))
    except BaseException as e:report.update(status='failed',error=repr(e));save();raise

if __name__=='__main__':main()
