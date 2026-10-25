"""Audit real installed entry, package pins, full documentation and preserved goals."""
from __future__ import annotations
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
from urllib.parse import unquote
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'docs/validation/evidence/semantic-recovery-20261025-r1'
GIT = 'C:/Users/carzy/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/git/cmd/git.exe'


def sha(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def git(*args):
    return subprocess.check_output([GIT,'--no-optional-locks','-c','core.fsmonitor=false',
        '-c','gc.auto=0','-c','maintenance.auto=false',*args],cwd=ROOT,timeout=60)


def numbered(text, prefix):
    return {m[1]:m[0] for m in re.finditer(r'^\| ('+prefix+r'\d{2})\s*\|.*$',text,re.M)}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run',required=True)
    args=parser.parse_args()
    assert re.fullmatch(r'r[1-9][0-9]*',args.run)
    out=BASE/('final-delivery-'+args.run);out.mkdir(exist_ok=False)
    (out/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    def save(name,data):
        (out/name).write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    report=dict(status='running',started_at_utc=datetime.now(timezone.utc).isoformat(),
        native_windows=True,virtualization=False,browser_ui=False,goal_remains_active=True)
    save('verification.json',report)
    try:
        baseline=git('rev-parse','HEAD').decode().strip();report['baseline_commit']=baseline
        runtime=json.loads((ROOT/'local/agent-ffmpeg/runtime.json').read_bytes())
        installation=json.loads((BASE/'installation-r1/verification.json').read_bytes())
        installed=Path(runtime['installed_directory'])
        assert runtime['release']=='v0.1.0-alpha.4-local.10'
        assert installed.resolve()==Path(installation['installed']).resolve()
        assert sha(Path(installation['archive']))==installation['archive_sha256']
        manifest=json.loads((ROOT/'agent-ffmpeg-local-install-manifest.json').read_bytes())
        assert manifest['cli_version']=='0.1.12' and manifest['skill_count']==1 and manifest['module_count']==17
        assert manifest['manifest_sha256']==runtime['manifest_sha256']==installation['manifest_sha256']
        assert json.loads((installed/'receipt.json').read_bytes())['manifest_sha256']==runtime['manifest_sha256']
        with zipfile.ZipFile(Path(installation['archive'])) as application_zip:
            assert 'sha256:'+hashlib.sha256(application_zip.read('manifest.json')).hexdigest()==runtime['manifest_sha256']
        source=ROOT/'product/src/ai_ad_editor';package=installed/'site/ai_ad_editor'
        product_files=sorted(source.glob('*.py'))
        assert len(product_files)==len(list(package.glob('*.py')))==202
        assert all(p.read_bytes()==(package/p.name).read_bytes() for p in product_files)
        for row in manifest['files']:
            path=ROOT/row['path']
            assert sha(path)==row['sha256'] and path.stat().st_size==row['bytes']
        assert len(manifest['files'])==65
        actual=Path('C:/Users/carzy/.codex/skills/agent-ffmpeg-local-editor')
        assert actual.resolve()==(ROOT/'skills/agent-ffmpeg-local-editor').resolve()
        meta=json.loads((ROOT/'docs/skills/community-unified-skill-package-0.1.12.json').read_bytes())
        kit=ROOT/meta['archive'];assert sha(kit)==meta['sha256'] and kit.stat().st_size==meta['bytes']
        with zipfile.ZipFile(kit) as archive:
            inventory=json.loads(archive.read('KIT-FILES.json'))
            assert inventory['cli_version']=='0.1.12'
            assert set(archive.namelist())=={r['path'] for r in inventory['files']}|{'KIT-FILES.json'}
            for row in inventory['files']:
                data=archive.read(row['path'])
                assert hashlib.sha256(data).hexdigest()==row['sha256'] and len(data)==row['bytes']
                if row['path'].startswith('skills/'):
                    assert data==(ROOT/row['path']).read_bytes()
        kit_result=json.loads((BASE/'kit-r2/verification.json').read_bytes())
        assert kit_result['status']=='passed' and kit_result['kit_sha256']==meta['sha256']
        # These are six real read-only calls, not new model inference or renders.
        prefix=['powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File',str(actual/'scripts/run.ps1')]
        responses={};calls=[]
        for arguments in (['version'],['doctor'],['capabilities'],['schema','show'],['gpu','inspect'],['model-pack','list']):
            name='-'.join(arguments);command=prefix+arguments
            result=subprocess.run(command,cwd=ROOT,capture_output=True,timeout=600,creationflags=subprocess.CREATE_NO_WINDOW)
            stdout=out/(name+'.stdout.json');stderr=out/(name+'.stderr.txt')
            stdout.write_bytes(result.stdout);stderr.write_bytes(result.stderr)
            value=json.loads(result.stdout.decode('utf-8-sig'));responses[name]=value
            calls.append(dict(argv=command,exit_code=result.returncode,status=value.get('status'),
                stdout_sha256=sha(stdout),stderr_sha256=sha(stderr)))
            save('calls.json',calls)
            assert result.returncode==0 and value['ok']
        assert responses['version']['data']['cli_version']=='0.1.12'
        entries=responses['capabilities']['data']['capabilities'];assert len(entries)==75
        captured=json.loads((ROOT/'docs/product/semantic-recovery-capabilities-cli-0.1.12.json').read_bytes())
        assert entries==captured['data']['capabilities']
        counts=dict(Counter(row['status'] for row in entries.values()))
        assert counts==dict(implemented=20,implemented_with_limits=47,local_adapter_only=7,degraded=1)
        previous=git('show',baseline+':docs/product/GOAL_GAPS_20261025.md').decode('utf-8-sig')
        current=(ROOT/'docs/product/GOAL_GAPS_20261025.md').read_text('utf-8-sig')
        old_g,new_g=numbered(previous,'G'),numbered(current,'G')
        assert len(old_g)==len(new_g)==38
        assert all(new_g[key].split('|')[5].strip()==line.split('|')[5].strip() for key,line in old_g.items())
        files=[];manuals=[]
        for suffix in ('','.zh-TW','.en'):
            path=ROOT/('README'+suffix+'.md');text=path.read_text('utf-8-sig')
            old=numbered(git('show',baseline+':'+path.name).decode('utf-8-sig'),'R')
            actual_rows=numbered(text,'R')
            assert len(old)==87 and len(actual_rows)==94
            assert all(actual_rows[key]==line for key,line in old.items())
            for prefix,count in (('F',51),('S',20),('K',17)):
                assert len(numbered(text,prefix))==count,(path.name,prefix)
            files.append(path)
            manual=ROOT/('docs/product/CAPABILITIES'+suffix+'.md')
            content=manual.read_text('utf-8-sig')
            blocks=re.findall(r'^### `([^`]+)`\s*\n\s*```json\n(.*?)\n```',content,re.M|re.S)
            parsed={key:json.loads(value) for key,value in blocks}
            assert len(blocks)==len(parsed)==75 and parsed==entries
            for prefix,count in (('F',51),('S',20)):
                assert len(numbered(content,prefix))==count
            manuals.append(dict(path=manual.relative_to(ROOT).as_posix(),F=51,S=20,actual_fields=75,fields_equal=True))
            files.extend([manual,ROOT/('docs/product/SKILLS'+suffix+'.md')])
        files.extend(ROOT/name for name in ('docs/README.md','docs/product/GOAL_GAPS_20261025.md',
            'docs/product/IMPLEMENTATION_PLAN_20261025.md','docs/product/SEMANTIC_RETRIEVAL.md',
            'docs/product/COMMUNITY_LOCAL_DELIVERY.md','docs/product/COMMUNITY_ACCEPTANCE.md',
            'docs/product/CASES.md','docs/product/SEMANTIC_PROJECT_PACKAGE.md','docs/product/SEMANTIC_JOB_RECOVERY.md','docs/specs/语义任务发布与中断恢复契约_20261025.md',
            'docs/validation/语义任务中断恢复实测_2026-10-25.md'))
        files.extend((ROOT/'skills/agent-ffmpeg-local-editor').rglob('*.md'))
        checked=0;missing=[]
        for path in files:
            content=re.sub(r'```.*?```','',path.read_text('utf-8-sig'),flags=re.S)
            # Inline code is a literal example, not an active Markdown link.
            content=re.sub(r'`[^`\n]+`','',content)
            for target in re.findall(r'!?\[[^\]\n]*\]\(([^)\n]+)\)',content):
                target=target.strip().strip('<>')
                if re.match(r'^(?:[A-Za-z]+:|#)',target):continue
                local=unquote(target.split('#',1)[0])
                if not local:continue
                destination=(path.parent/local).resolve();checked+=1
                if not destination.exists():missing.append(dict(source=path.relative_to(ROOT).as_posix(),target=target))
        save('links.json',dict(checked=checked,missing=missing));assert not missing,missing[:10]
        receipts=[]
        for name in ('tests/trees-r1','tests/development-r1','tests/development-cli-r1','tests/installed-r1','tests/installed-cli-r1',
                     'installed-r1/setup-cuda','installed-r1/index-cuda','installed-r1/calibrate-cuda',
                     'installed-r1/calibrate-cpu','installed-r1/before-cuda','installed-r1/before-cpu',
                     'installed-r1/roundtrip-cuda','installed-r1/after-cuda','installed-r1/after-cpu',
                     'installed-r1/skill-cuda','kit-r2',
                     'faults-r1/index-publication','faults-r1/calibration-publication','faults-r1/calibration-commit',
                     'faults-r1/search-hard-stop','faults-r1/search-cancel','faults-r1/search-timeout','faults-r1/cleanup'):
            path=BASE/name/'verification.json';value=json.loads(path.read_bytes())
            if name.startswith('tests/'):
                assert value['exit_code']==0 and value['status']=='passed' and value['frozen_equal'] and value['installed_frozen_equal']
                assert value['result']['skipped']==0
                assert value['result']['methods']==(22 if 'trees-r' in name else 122 if 'cli-r' in name else 150)
                assert sha(path.parent/'tests.log')==value['log_sha256'].removeprefix('sha256:')
                state='terminal-passing-test-receipt'
            else:
                assert value['status'] not in ('running','failed')
                state=value['status']
            receipts.append(dict(path=path.relative_to(ROOT).as_posix(),sha256=sha(path),status=state))
        artifact_checks=[]
        for folder in ('installed-r1','demo-installed-r1'):
            proof=ROOT/'docs/assets/semantic-package-20261025-r1'/folder/'verification.json'
            value=json.loads(proof.read_bytes())
            for record in value['files']:
                artifact=(ROOT/record['path']).resolve()
                assert artifact.is_relative_to((ROOT/'docs/assets/semantic-package-20261025-r1').resolve())
                assert sha(artifact)==record['sha256'] and artifact.stat().st_size==record['bytes']
                artifact_checks.append(record['path'])
        review=json.loads((ROOT/'docs/validation/evidence/semantic-package-20261025-r1/static-agent-review-r1.json').read_bytes())
        assert len(review['files'])==5 and review['human_review'] is False
        assert all(sha(ROOT/r['path'])==r['sha256'] for r in review['files'])
        for phase in ('after-cuda','after-cpu','skill-cuda'):
            proof=BASE/'installed-r1'/phase
            value=json.loads((proof/'verification.json').read_bytes())
            comparisons=json.loads((proof/'before-after-comparison.json').read_bytes())
            assert value['all_80_decisions_and_ordered_hits_identical'] and value['maximum_score_error']<=1e-6
            assert value['original_source_and_external_paths_unavailable'] and value['project_rights_and_assets_unchanged']
            assert len(comparisons)==80 and all(r['decision_identical'] and r['ordered_asset_ids_identical'] for r in comparisons)
        frozen=BASE/'frozen/protocol.json'
        assert sha(frozen)=='23d312f14e82bb69d80dda73e3143eb1dc4e67ddc2b82b65db401d777ac09199'
        frozen_value=json.loads(frozen.read_bytes())
        assert frozen_value['source_files']=={p.name:sha(p) for p in product_files}
        fault_proofs={name:json.loads((BASE/'faults-r1'/name/'verification.json').read_bytes())
            for name in ('index-publication','calibration-publication','calibration-commit',
                         'search-hard-stop','search-cancel','search-timeout','cleanup')}
        assert all(v['status']=='passed' and v['installed_bytes_unchanged'] for v in fault_proofs.values())
        assert fault_proofs['search-hard-stop']['owned_worker_handle_observed_exited']
        assert fault_proofs['search-cancel']['owned_worker_handle_observed_exited']
        assert fault_proofs['calibration-commit']['real_query_of_committed_recovered_profile']
        assert fault_proofs['cleanup']['committed_assets_rights_and_profiles_unchanged']
        assert fault_proofs['cleanup']['real_query_after_cleanup']
        timeout_seconds=fault_proofs['search-timeout']['fault_process']['elapsed_seconds']
        assert timeout_seconds>1 and fault_proofs['search-timeout']['actual_timeout']
        for name, proof in fault_proofs.items():
            folder=BASE/'faults-r1'/name
            if 'fault_process' in proof:
                assert sha(folder/'fault.stdout.txt')==proof['fault_process']['stdout_sha256']
                assert sha(folder/'fault.stderr.txt')==proof['fault_process']['stderr_sha256']
            fault_calls=json.loads((folder/'calls.json').read_bytes())
            assert len(fault_calls)==proof['calls']
            for i, call in enumerate(fault_calls,1):
                assert sha(folder/f'{i:02}.stdout.json')==call['stdout_sha256']
                assert sha(folder/f'{i:02}.stderr.txt')==call['stderr_sha256']
        for phase in ('before-cuda','before-cpu','after-cuda','after-cpu','skill-cuda'):
            q=json.loads((BASE/'installed-r1'/phase/'verification.json').read_bytes())['quality']
            errors=[r['id'] for r in q['queries'] if not (r['top1_correct'] if r['expected_asset_ids'] else r['rejected'])]
            assert set(errors)=={'q14','hout00zh','hout08zh'},(phase,errors)
        report.update(actual_fault_cases=7,timeout_requested_seconds=1,timeout_observed_seconds=timeout_seconds,
            timeout_timeliness_passed=False,query_errors_unchanged=True,recovery_protocol_sha256=sha(frozen),
            owned_worker_exits_observed=2,committed_profile_query_and_cleanup_query_verified=True)
        old_demo='docs/assets/semantic-decision-20261025-r1/demo-installed-r1/'
        for name in ('retrieval-project.aevpkg.zip','KNOWN_ISSUE.md'):
            assert (ROOT/old_demo/name).read_bytes()==git('show',baseline+':'+old_demo+name)
        # Retain public state accurately without opening browser UI or modifying releases.
        public=dict(url='https://api.github.com/repos/copypasteltd/agent-editor-kit/releases?per_page=10',
                    checked_at_utc=datetime.now(timezone.utc).isoformat())
        try:
            request=urllib.request.Request(public['url'],headers={'User-Agent':'agent-editor-kit-local-review','Accept':'application/vnd.github+json'})
            with urllib.request.urlopen(request,timeout=30) as response:
                raw=response.read(4*1024*1024+1);public['http_status']=response.status
            assert len(raw)<=4*1024*1024
            (out/'github-releases.raw.json').write_bytes(raw)
            releases=json.loads(raw)
            public['releases']=[{key:r[key] for key in ('tag_name','draft','prerelease','published_at','html_url')} for r in releases]
            public['latest_published_tag']=max((r for r in public['releases'] if not r['draft']),key=lambda r:r['published_at'])['tag_name']
            public['response_sha256']=hashlib.sha256(raw).hexdigest()
        except (OSError,ValueError) as exc:
            public['error']=str(exc);public['http_status']=getattr(exc,'code',None)
        assert git('rev-parse','HEAD').decode().strip()==baseline
        assert all(p.read_bytes()==(package/p.name).read_bytes() for p in product_files)
        report.update(status='passed',finished_at_utc=datetime.now(timezone.utc).isoformat(),
            cli_version='0.1.12',release=runtime['release'],read_only_skill_calls=len(calls),
            installed_source_files=202,source_equals_installed=True,skill_files=65,registered_skills=1,internal_modules=17,
            kit_sha256=meta['sha256'],capabilities=75,capability_status_counts=counts,
            all_38_original_closure_conditions_verbatim=True,all_R01_R87_verbatim_in_three_readmes=True,
            current_R_rows=94,manuals=manuals,local_links_checked=checked,missing_local_links=[],
            historical_C20_media_artifacts_hash_verified=len(artifact_checks),historical_static_review_receipt_verified=True,
            all_80_cpu_cuda_and_skill_migration_comparisons_verified=True,
            real_execution_receipts=receipts,new_audit_model_forwards=0,new_audit_renders=0,
            human_listening=False,human_semantic_acceptance=False,full_capcut_parity=False,
            overall_completion_percentage=None,public_release_check=public,
            known_query_errors_preserved=3,legacy_retrieval_package_failure_preserved=True, new_semantic_package_roundtrip_verified=True,
            preserved_historical_static_agent_review=dict(gallery_pages=[1,2,3,4],encoded_contact_sheet=True,
                findings='all query errors and blank no-match cards retained; text visible within canvas; no human continuous-playback claim'),
            files=[dict(path=p.relative_to(ROOT).as_posix(),sha256=sha(p)) for p in files],generator_sha256=sha(Path(__file__)))
        save('verification.json',report)
        print(json.dumps({k:v for k,v in report.items() if k not in ('files','real_execution_receipts','public_release_check','manuals')},ensure_ascii=False))
    except BaseException as exc:
        report.update(status='failed',error=repr(exc));save('verification.json',report);raise


if __name__=='__main__':main()
