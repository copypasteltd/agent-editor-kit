"""Retest two stale catalog assertions and retain full-run702 plus targeted2 proof."""
from pathlib import Path
from datetime import datetime,timezone
import ast,copy,hashlib,json,re,runpy,sys

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/validation/evidence/optical-effects-20261027-r1'
NAMES=['test_capabilities_manifest_is_local_and_agent_readable','test_effect_catalog_cli_is_local_and_queryable']
MODULES=['test_cli.P0CliTests.'+name for name in NAMES]
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def load(p):return json.loads(Path(p).read_bytes())
def save(p,v):Path(p).write_text(json.dumps(v,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')

def main():
    out=BASE/'installed-regression-final-r1';out.mkdir(exist_ok=False)
    (out/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    original=BASE/'installed-regression-r1';before=load(original/'verification.json')
    assert before['status']=='failed' and (before['tests'],before['failures'],before['errors'],before['skipped'])==(704,2,0,0)
    assert before['frozen_equal'] and before['test_frozen_equal']
    package=ROOT/'local/agent-ffmpeg/v0.1.0-alpha.4-local.36/final-r1/installed'
    product={p.name:sha(p) for p in (ROOT/'product/src/ai_ad_editor').glob('*.py')}
    assert before['product_files']==product=={p.name:sha(p) for p in (package/'site/ai_ad_editor').glob('*.py')}
    final_tests={name:sha(ROOT/'product/tests'/name) for name in before['test_files']}
    assert [n for n in final_tests if final_tests[n]!=before['test_files'][n]]==['test_cli.py']
    old=(original/'executed-tests/test_cli.py').read_text('utf8');new=(ROOT/'product/tests/test_cli.py').read_text('utf8')
    assert hashlib.sha256(old.encode()).hexdigest()==before['test_files']['test_cli.py']
    def remove_changed_methods(text):
        tree=ast.parse(text)
        for node in tree.body:
            if isinstance(node,ast.ClassDef) and node.name=='P0CliTests':
                assert len([v for v in node.body if isinstance(v,ast.FunctionDef) and v.name in NAMES])==2
                node.body=[v for v in node.body if not isinstance(v,ast.FunctionDef) or v.name not in NAMES]
        return ast.dump(tree,include_attributes=False)
    assert remove_changed_methods(old)==remove_changed_methods(new)
    rows=re.findall(r'^(test_\S+) \(([^)]+)\) \.\.\. (ok|FAIL|ERROR|skipped[^\n]*)$',
        (original/'tests.log').read_text('utf8'),re.M)
    assert len(rows)==704 and sum(r[2]=='ok' for r in rows)==702
    assert {r[1]+'.'+r[0] for r in rows if r[2]!='ok'}==set(MODULES)
    ns=runpy.run_path(str(ROOT/'scripts/test_float_optics_20261027.py'),run_name='optical_targeted_runner')
    ns['GROUPS']['catalog-correction']=MODULES
    sys.argv=[str(ROOT/'scripts/test_float_optics_20261027.py'),'--run','installed-catalog-r1',
        '--installed',str(package),'--group','catalog-correction']
    ns['main']()
    targeted=load(BASE/'installed-catalog-r1/verification.json')
    assert targeted['status']=='passed' and targeted['tests']==2 and targeted['product_files']==product
    assert targeted['frozen_equal'] and targeted['test_frozen_equal'] and targeted['test_files']['test_cli.py']==final_tests['test_cli.py']
    assert product=={p.name:sha(p) for p in (ROOT/'product/src/ai_ad_editor').glob('*.py')}
    assert final_tests=={n:sha(ROOT/'product/tests'/n) for n in final_tests}
    (out/'executed-tests').mkdir()
    for name in final_tests:(out/'executed-tests'/name).write_bytes((ROOT/'product/tests'/name).read_bytes())
    for name in ('executed-runner.py','receipts.json'):(out/name).write_bytes((original/name).read_bytes())
    report=copy.deepcopy(before)
    report.update(status='passed',failures=0,errors=0,skipped=0,tests=704,installed=str(package),
        test_files=final_tests,at_utc=datetime.now(timezone.utc).isoformat(),
        verification_method='702 full-run successes plus two corrected catalog retests on unchanged runtime',
        full_run_reference='installed-regression-r1/verification.json',
        targeted_reference='installed-catalog-r1/verification.json',unique_tests_passed=704,
        total_test_executions=706,earlier_failed_executions_preserved=2,
        all_704_passed_as_one_new_run=False,product_changes_after_full_run=False,
        test_AST_changes_limited_to=MODULES,untouched_702_tests_not_reexecuted=True)
    save(out/'verification.json',report)
    save(out/'outcome-inventory.json',dict(full_run_sha256=sha(original/'verification.json'),
        full_log_sha256=sha(original/'tests.log'),targeted_sha256=sha(BASE/'installed-catalog-r1/verification.json'),
        outcomes=[dict(id=r[1]+'.'+r[0],first_status=r[2],final_status='passed',
            repeated=r[1]+'.'+r[0] in MODULES) for r in rows]))
    print(json.dumps({k:report[k] for k in ('status','tests','unique_tests_passed','total_test_executions',
        'verification_method','all_704_passed_as_one_new_run','product_changes_after_full_run')}))

if __name__=='__main__':main()
