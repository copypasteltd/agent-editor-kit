"""Audit frozen candidate evidence, history, namespace and new documentation."""
from pathlib import Path
import ast,hashlib,json,re,subprocess
from urllib.parse import unquote
ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/validation/evidence/oklab-gamut-20261029-r1'
GIT='C:/Users/carzy/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/git/cmd/git.exe'
BASELINE='97bbda9177b37db9fb9ea6a21605a68bfec41433'

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def old(path):return subprocess.check_output([GIT,'--no-optional-locks','-c','core.fsmonitor=false','show',BASELINE+':'+path],cwd=ROOT)
def main():
    out=BASE/'preview-fix-audit-r1';out.mkdir(exist_ok=False)
    (out/'executed-auditor.py').write_bytes(Path(__file__).read_bytes())
    source=ROOT/'product/src/ai_ad_editor'
    pins={p.name:sha(p) for p in source.glob('*.py')};assert len(pins)==277
    for p in source.glob('*.py'):ast.parse(p.read_text('utf8'),filename=str(p))
    for name,n in [('preview-fix-r3',15),('source-r5',64),('preview-regression-r1',18),('installed-measure-r1',64),('installed-preview-r1',18)]:
        record=json.loads((BASE/name/'verification.json').read_bytes())
        assert record['status']=='passed' and record['tests']==n and record['product_files']==pins
        assert record['errors']==record['failures']==record['skipped']==0
        for module,digest in record['test_files'].items():
            assert sha(ROOT/'product/tests'/(module+'.py'))==sha(BASE/name/'executed-tests'/(module+'.py'))==digest
    build=json.loads((BASE/'installation-final-r2/verification.json').read_bytes())
    installed=Path(build['installed']);assert {p.name:sha(p) for p in (installed/'site/ai_ad_editor').glob('*.py')}==pins
    assert sha(Path(build['archive']))==build['archive_sha256']
    assert json.loads((installed/'receipt.json').read_bytes())['manifest_sha256']==build['manifest_sha256']
    assert 'sha256:'+sha(installed.parent.parent/'unpacked-r2/manifest.json')==build['manifest_sha256']
    assert (source/'agent-project.schema.json').read_bytes()==(ROOT/'docs/specs/agent-project.schema.json').read_bytes()
    for name in ['README.md','README.zh-TW.md','README.en.md']:
        prior=re.findall(rb'^\| R\d+ .*$',old(name),re.M)
        current=re.findall(rb'^\| R\d+ .*$',(ROOT/name).read_bytes(),re.M)
        # LF conversion is allowed, historical content changes are not.
        assert [r.rstrip(b'\r') for r in prior]==[r.rstrip(b'\r') for r in current[:344]]
        assert len(current)==349
    for name in ['docs/product/GOAL_GAPS_20261025.md','agent-ffmpeg-local-install-manifest.json','skills/agent-ffmpeg-local-editor/SKILL.md','skills/agent-ffmpeg-local-editor/scripts/run.py']:
        assert (ROOT/name).read_bytes()==old(name),name
    report=ROOT/'docs/validation/SDR预览映射修复_2026-10-29.md'
    links=[]
    for target in re.findall(r'\]\(([^)]+)\)',report.read_text('utf8')):
        if '://' in target or target.startswith('#'):continue
        path=(report.parent/unquote(target.split('#')[0])).resolve();assert path.exists(),target
        links.append(target)
    assets=ROOT/'docs/assets/oklab-preview-candidate-20261029-r1'
    media=json.loads((assets/'SOURCE.json').read_bytes())
    for row in media['files']:assert sha(assets/row['path'])==row['sha256'] and (assets/row['path']).stat().st_size==row['bytes']
    probe=json.loads((BASE/'preview-probe-r3/verification.json').read_bytes())
    assert probe['status']=='passed' and probe['author_unchanged'] and not probe['source_fallback']
    assert len(probe['calls'])==8 and all(c['ok'] and c['exit_code']==0 for c in probe['calls'])
    result=dict(status='passed',product_file_count=len(pins),source_installed_frozen_equal=True,
                historical_readme_rows_preserved_per_language=344,current_rows_per_language=349,
                original_gap_document_unchanged=True,registered_skill_unchanged=True,
                new_report_local_links_checked=len(links),actual_installed_cli_calls=8,
                full_compatibility_not_claimed=True,files=pins)
    (out/'verification.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    print(json.dumps({k:v for k,v in result.items() if k!='files'}))
if __name__=='__main__':main()
