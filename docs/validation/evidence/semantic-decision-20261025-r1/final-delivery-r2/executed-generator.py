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
BASE = ROOT / 'docs/validation/evidence/semantic-decision-20261025-r1'
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
    try:
        baseline=git('rev-parse','HEAD').decode().strip();report['baseline_commit']=baseline
        runtime=json.loads((ROOT/'local/agent-ffmpeg/runtime.json').read_bytes())
        installation=json.loads((BASE/'installation-r1/verification.json').read_bytes())
        installed=Path(runtime['installed_directory'])
        assert runtime['release']=='v0.1.0-alpha.4-local.8'
        assert installed.resolve()==Path(installation['installed']).resolve()
        assert sha(Path(installation['archive']))==installation['archive_sha256']
        manifest=json.loads((ROOT/'agent-ffmpeg-local-install-manifest.json').read_bytes())
        assert manifest['cli_version']=='0.1.10' and manifest['skill_count']==1 and manifest['module_count']==17
        assert manifest['manifest_sha256']==runtime['manifest_sha256']==installation['manifest_sha256']
        assert json.loads((installed/'receipt.json').read_bytes())['manifest_sha256']==runtime['manifest_sha256']
        with zipfile.ZipFile(Path(installation['archive'])) as application_zip:
            assert 'sha256:'+hashlib.sha256(application_zip.read('manifest.json')).hexdigest()==runtime['manifest_sha256']
        source=ROOT/'product/src/ai_ad_editor';package=installed/'site/ai_ad_editor'
        product_files=sorted(source.glob('*.py'))
        assert len(product_files)==len(list(package.glob('*.py')))==199
        assert all(p.read_bytes()==(package/p.name).read_bytes() for p in product_files)
        for row in manifest['files']:
            path=ROOT/row['path']
            assert sha(path)==row['sha256'] and path.stat().st_size==row['bytes']
        assert len(manifest['files'])==64
        actual=Path('C:/Users/carzy/.codex/skills/agent-ffmpeg-local-editor')
        assert actual.resolve()==(ROOT/'skills/agent-ffmpeg-local-editor').resolve()
        meta=json.loads((ROOT/'docs/skills/community-unified-skill-package-0.1.10.json').read_bytes())
        kit=ROOT/meta['archive'];assert sha(kit)==meta['sha256'] and kit.stat().st_size==meta['bytes']
        with zipfile.ZipFile(kit) as archive:
            inventory=json.loads(archive.read('KIT-FILES.json'))
            assert inventory['cli_version']=='0.1.10'
            assert set(archive.namelist())=={r['path'] for r in inventory['files']}|{'KIT-FILES.json'}
            for row in inventory['files']:
                data=archive.read(row['path'])
                assert hashlib.sha256(data).hexdigest()==row['sha256'] and len(data)==row['bytes']
                if row['path'].startswith('skills/'):
                    assert data==(ROOT/row['path']).read_bytes()
        kit_result=json.loads((BASE/'kit-r1/verification.json').read_bytes())
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
        assert responses['version']['data']['cli_version']=='0.1.10'
        entries=responses['capabilities']['data']['capabilities'];assert len(entries)==75
        captured=json.loads((ROOT/'docs/product/semantic-decision-capabilities-cli-0.1.10.json').read_bytes())
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
            assert len(old)==75 and len(actual_rows)==81
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
            'docs/product/CASES.md','docs/specs/语义条件与校准拒识契约_20261025.md',
            'docs/validation/语义条件与校准拒识实测_2026-10-25.md'))
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
        for name in ('tests/development-r3','tests/installed-r1','tests/installed-cli-r1','controls-r1',
                     'installed-r1/heldout-cuda','installed-r1/heldout-cpu',
                     'installed-r1/regression-cuda','installed-r1/regression-cpu',
                     'skill-r1/heldout-cuda','demo-finalization-r1','kit-r1'):
            path=BASE/name/'verification.json';value=json.loads(path.read_bytes())
            assert value['status'] not in ('running','failed')
            receipts.append(dict(path=path.relative_to(ROOT).as_posix(),sha256=sha(path),status=value['status']))
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
            cli_version='0.1.10',release=runtime['release'],read_only_skill_calls=len(calls),
            installed_source_files=199,source_equals_installed=True,skill_files=64,registered_skills=1,internal_modules=17,
            kit_sha256=meta['sha256'],capabilities=75,capability_status_counts=counts,
            all_38_original_closure_conditions_verbatim=True,all_R01_R75_verbatim_in_three_readmes=True,
            current_R_rows=81,manuals=manuals,local_links_checked=checked,missing_local_links=[],
            real_execution_receipts=receipts,new_audit_model_forwards=0,new_audit_renders=0,
            human_listening=False,human_semantic_acceptance=False,full_capcut_parity=False,
            overall_completion_percentage=None,public_release_check=public,
            known_query_errors_preserved=3,known_new_retrieval_package_failure_preserved=True,
            static_agent_review=dict(gallery_pages=[1,2,3,4],encoded_contact_sheet=True,
                findings='all query errors and blank no-match cards retained; text visible within canvas; no human continuous-playback claim'),
            files=[dict(path=p.relative_to(ROOT).as_posix(),sha256=sha(p)) for p in files],generator_sha256=sha(Path(__file__)))
        save('verification.json',report)
        print(json.dumps({k:v for k,v in report.items() if k not in ('files','real_execution_receipts','public_release_check','manuals')},ensure_ascii=False))
    except BaseException as exc:
        report.update(status='failed',error=repr(exc));save('verification.json',report);raise


if __name__=='__main__':main()
