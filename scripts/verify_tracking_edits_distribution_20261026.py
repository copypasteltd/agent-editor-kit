"""Verify metadata-only repack, version rejection and the registered final preview."""
from datetime import datetime, timezone
from pathlib import Path
from email.parser import BytesParser
import hashlib, json, runpy, subprocess, sys, zipfile

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/validation/evidence/tracking-edits-20261026-r1'
LOCAL=ROOT/'local/agent-ffmpeg/v0.1.0-alpha.4-local.25'

def sha(p):
    with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def load(p):return json.loads(Path(p).read_bytes())

def main():
    out=BASE/'distribution-r1';out.mkdir(exist_ok=False)
    (out/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    report=dict(status='running',native_windows=True,virtualization=False,source_fallback=False,
        functional_evidence_installation='final-r3',final_installation='final-r4',calls=[])
    def save(name,value):(out/name).write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    def run(name,argv,expected=0):
        result=subprocess.run(list(map(str,argv)),cwd=ROOT,capture_output=True,timeout=600,creationflags=subprocess.CREATE_NO_WINDOW)
        (out/(name+'.stdout.log')).write_bytes(result.stdout);(out/(name+'.stderr.log')).write_bytes(result.stderr)
        report['calls'].append(dict(name=name,exit_code=result.returncode,expected_exit_code=expected,
            stdout_sha256=sha(out/(name+'.stdout.log')),stderr_sha256=sha(out/(name+'.stderr.log'))))
        save('verification.json',report);assert result.returncode==expected,(name,result.stderr[-2000:])
        return result.stdout
    save('verification.json',report)
    try:
        a,b=[load(BASE/('installation-final-'+n)/'verification.json') for n in ('r3','r4')]
        assert a['status']==b['status']=='installed-and-byte-verified'
        assert a['source_files']==b['source_files'] and len(a['source_files'])==220
        manifests=[load(LOCAL/('unpacked-'+n)/'manifest.json') for n in ('r3','r4')]
        wheels=[{r['name']:r for r in m['wheels']} for m in manifests]
        dependencies=[]
        for name in sorted(set(wheels[0])-{'ai-ad-editor'}):
            old,new=[LOCAL/('unpacked-'+n)/wheels[i][name]['path'] for i,n in enumerate(('r3','r4'))]
            assert wheels[0][name]['version']==wheels[1][name]['version'] and sha(old)==sha(new)
            dependencies.append(dict(name=name,version=wheels[1][name]['version'],sha256=sha(new)))
        assert len(dependencies)==7
        payloads=[];metadata_versions=[]
        for i,n in enumerate(('r3','r4')):
            with zipfile.ZipFile(LOCAL/('unpacked-'+n)/wheels[i]['ai-ad-editor']['path']) as z:
                info=BytesParser().parsebytes(z.read(next(p for p in z.namelist() if p.endswith('.dist-info/METADATA'))))
                metadata_versions.append(info['Version'])
                entries={p.split('.data/purelib/',1)[1]:hashlib.sha256(z.read(p)).hexdigest()
                    for p in z.namelist() if '.data/purelib/' in p and not p.endswith('/')}
                assert entries
                payloads.append(entries)
        assert metadata_versions==['0.1.26','0.1.27'] and payloads[0]==payloads[1]
        save('product-wheel-payload.json',payloads[1])
        installed=Path(b['installed'])
        program="import sys,json,importlib.metadata; from pathlib import Path; sys.path.insert(0,sys.argv[1]); import ai_ad_editor; print(json.dumps(dict(distribution=importlib.metadata.version('ai-ad-editor'),cli=ai_ad_editor.VERSION,package=ai_ad_editor.__file__)))"
        actual=json.loads(run('isolated-distribution-version',[sys.executable,'-I','-S','-B','-u','-X','utf8','-c',program,installed/'site']))
        assert actual['distribution']==actual['cli']=='0.1.27'
        assert Path(actual['package']).is_relative_to(installed/'site')
        build=runpy.run_path(str(ROOT/'product/offline/build.py'))
        metadata=(ROOT/'product/pyproject.toml').read_text('utf8');source=(ROOT/'product/src/ai_ad_editor/__init__.py').read_text('utf8')
        assert build['matching_product_version'](metadata,source)=='0.1.27'
        old_metadata=metadata.replace('version = "0.1.27"','version = "0.1.26"')
        assert old_metadata!=metadata
        try:build['matching_product_version'](old_metadata,source)
        except ValueError as exc:rejection=str(exc)
        else:raise AssertionError('Old distribution metadata accepted')
        entry=ROOT/'skills/agent-ffmpeg-local-editor'
        before={str(p):sha(p) for p in [*entry.rglob('*'),ROOT/'agent-ffmpeg-local-install-manifest.json',ROOT/'local/agent-ffmpeg/runtime.json'] if p.is_file()}
        run('reject-stale-wheel-pin',[sys.executable,'-E','-B','-u','-X','utf8',ROOT/'scripts/pin_community_skill.py',
            '--bundle',LOCAL/'unpacked-r3','--release','v0.1.0-alpha.4-local.25'],1)
        assert all(sha(p)==digest for p,digest in before.items())
        assert b'Bundle wheel version differs from source CLI VERSION' in (out/'reject-stale-wheel-pin.stderr.log').read_bytes()
        rejected=ROOT/'local/agent-ffmpeg/tracking-edits-kit-build-final-r1/package.json'
        failed=load(rejected);assert failed['cli_version']=='0.1.26'
        (out/'rejected-kit-metadata.json').write_bytes(rejected.read_bytes())
        assert (BASE/'kit-r1/executed-generator.py').exists() and not (BASE/'kit-r1/verification.json').exists()
        prefix=['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',
            Path('C:/Users/carzy/.codex/skills/agent-ffmpeg-local-editor/scripts/run.ps1')]
        values={}
        for name,args in [('version',['version']),('capabilities',['capabilities']),('schema',['schema','show'])]:
            value=json.loads(run('registered-'+name,[*prefix,*args]));assert value['ok'];values[name]=value
        assert values['version']['data']['cli_version']=='0.1.27'
        assert values['capabilities']['data']['capabilities']['standard_native_float_render']['tracking']['edit_protocol']=='native-tracking-edit-lineage-v1'
        case=load(BASE/'case-r3/verification.json');project=Path(case['project'])
        author_sha=sha(project/'project.json');rights_sha=sha(project/'rights-ledger.json')
        value=json.loads(run('registered-validate',[*prefix,'validate','--project',project]));assert value['ok']
        preview=json.loads(run('registered-preview-12',[*prefix,'preview','frame','--project',project,'--sequence-id','child','--frame','12','--height','180']))
        assert preview['ok'] and not preview['data']['cache_hit']
        old_preview=load(BASE/'case-r3/preview-12.stdout.log')['data']['path'];new_preview=preview['data']['path']
        sys.path.insert(0,str(installed/'site'))
        from ai_ad_editor.runtime import configure_local_runtime
        from ai_ad_editor.media import ffmpeg_path
        configure_local_runtime()
        digests=[]
        for name,path in [('r3',old_preview),('r4',new_preview)]:
            raw=run('decoded-preview-'+name,[ffmpeg_path(),'-nostdin','-v','error','-i',path,'-frames:v','1','-pix_fmt','rgba64le','-f','hash','-hash','sha256','-'])
            digests.append(raw.decode().strip())
        assert digests[0]==digests[1]
        assert sha(project/'project.json')==author_sha and sha(project/'rights-ledger.json')==rights_sha
        report.update(status='passed',checked_at_utc=datetime.now(timezone.utc).isoformat(),
            product_python_files_equal=220,all_wheel_payload_files_equal=len(payloads[1]),dependencies_equal=dependencies,
            prior_metadata_version='0.1.26',final_metadata_version='0.1.27',cli_version='0.1.27',
            build_mismatch_rejection=rejection,stale_pin_rejected_without_mutation=True,
            rejected_kit_cli_version=failed['cli_version'],incomplete_kit_r1_excluded=True,
            registered_new_preview=True,preview_decoded_rgba64_equal=True,preview_sha256=digests[1],
            project_and_rights_unchanged=True,new_full_video_renders=0,new_model_forwards=0,
            installation=a['installed'],final_installed=b['installed'])
        save('verification.json',report)
        print(json.dumps({k:v for k,v in report.items() if k!='calls'},ensure_ascii=False))
    except BaseException as exc:report.update(status='failed',error=repr(exc));save('verification.json',report);raise

if __name__=='__main__':main()
