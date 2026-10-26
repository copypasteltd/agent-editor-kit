"""Pin the final control fix and prove the measured inference kernel is unchanged."""
from __future__ import annotations
import argparse
import ast
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT / 'docs/validation/evidence/model-session-20261027-r1'


def load(path): return json.loads(Path(path).read_bytes())
def digest(path): return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--run', required=True); args = parser.parse_args()
    assert args.run.replace('-', '').isalnum()
    out = BASE / ('control-fix-' + args.run); out.mkdir(exist_ok=False)
    (out / 'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    old = load(BASE / 'installation-final-r2/verification.json')
    new = load(BASE / 'installation-final-r3/verification.json')
    assert old['status'] == new['status'] == 'installed-and-byte-verified'
    before = Path(old['installed']) / 'site/ai_ad_editor'
    after = Path(new['installed']) / 'site/ai_ad_editor'
    names = {p.name for p in before.glob('*.py')}
    assert names == {p.name for p in after.glob('*.py')} and len(names) == 230
    changed = [n for n in sorted(names) if digest(before/n) != digest(after/n)]
    assert changed == ['cli.py']
    left = ast.parse((before/'cli.py').read_text('utf-8-sig'))
    right = ast.parse((after/'cli.py').read_text('utf-8-sig'))
    assignments = [n for n in right.body if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == '_READ_ONLY_PROJECT_COMMANDS' for t in n.targets)]
    assert len(assignments) == 1 and isinstance(assignments[0].value, ast.Set)
    values = assignments[0].value.elts
    added = [n for n in values if isinstance(n, ast.Tuple) and all(isinstance(v, ast.Constant) for v in n.elts) and ast.literal_eval(n) == ('media', 'model-session')]
    assert len(added) == 1
    values.remove(added[0])
    assert ast.dump(left, include_attributes=False) == ast.dump(right, include_attributes=False)
    case = load(BASE/'case-r1/verification.json')
    assert Path(case['installed']).resolve() == Path(old['installed']).resolve()
    artifact_checks = []
    for row in case['adapter']['artifacts']:
        path = Path(row['path'])
        if path.is_relative_to(before):
            relative = path.relative_to(before); destination = after/relative
            assert path.read_bytes() == destination.read_bytes()
            assert 'sha256:'+digest(path) == row['sha256']
            artifact_checks.append(dict(path=relative.as_posix(), role=row['role'], sha256=row['sha256']))
    assert artifact_checks and all(row['path'] != 'cli.py' for row in artifact_checks)
    failed = load(BASE/'control-source-r1/verification.json')
    fixed = load(BASE/'control-source-r2/verification.json')
    real = load(BASE/'control-lock-r1/verification.json')
    assert failed['failures'] == 1 and fixed['status'] == 'passed' and real['active_model']
    namespace = ROOT/'agent-ffmpeg-local-install-manifest.json'; manifest = load(namespace)
    manifest['manifest_sha256'] = new['manifest_sha256']
    namespace.write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    for name in ('docs/product/COMMUNITY_LOCAL_DELIVERY.md','docs/releases/CLI_0.1.34_LOCAL.md'):
        path=ROOT/name; text=path.read_text('utf8')
        for a,b in [('local.32/final-r2/installed','local.32/final-r3/installed'),('local.32/candidate-r2/bundle.zip','local.32/candidate-r3/bundle.zip'),
                    (old['archive_sha256'],new['archive_sha256']),(old['manifest_sha256'],new['manifest_sha256']),
                    (str(old['archive_bytes']),str(new['archive_bytes']))]: text=text.replace(a,b)
        path.write_text(text,encoding='utf8',newline='\n')
    report=dict(status='passed',measured_gpu_installation=str(before.parent.parent),final_installation=new['installed'],
        source_files=230,byte_identical_non_cli_files=229,changed_files=changed,only_ast_change="_READ_ONLY_PROJECT_COMMANDS adds ('media', 'model-session')",
        entire_remaining_cli_ast_identical=True,model_generate_lock_unchanged=True,model_implementation_artifacts_identical=artifact_checks,
        full_adapter_artifact_count=len(case['adapter']['artifacts']),gpu_case_rerun_after_control_fix=False,
        provenance='Real CUDA measurements used final-r2; final-r3 changes only the model-session CLI transaction/lock exemption. All inference code is byte-identical. Final installed control/regression tests run separately.',
        previously_blocked_during_real_inference=True,control_test_failed_before=True,control_test_passed_after=True,
        namespace_sha256=digest(namespace),archive_sha256=new['archive_sha256'])
    (out/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf8',newline='\n')
    print(json.dumps({k:v for k,v in report.items() if k!='model_implementation_artifacts_identical'}),flush=True)


if __name__=='__main__': main()
