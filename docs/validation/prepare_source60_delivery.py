"""Derive a separate CLI60 builder, with unchanged historical CLI59 tooling."""
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]

def main():
    text=(ROOT/'docs/validation/build_source59_delivery.py').read_text(encoding='utf-8')
    text=text.replace('CLI59','CLI60').replace('0.1.59','0.1.60')
    text=text.replace('v0.1.0-alpha.4-local.57','v0.1.0-alpha.4-local.58')
    text=text.replace('music-score-20261029-r1','music-loop-20261029-r1')
    start=text.index('    gate_paths = ')
    end=text.index('    protected_paths = ',start)
    text=text[:start]+'''    gate_paths = [gate_base/(name+'/verification.json') for name in [
        'targeted-r1','source60-bootstrap-r1','source60-selection-r1',
        'source60-semantic-r1','source60-contracts-r1','source60-control-r1',
        'actual-case-r1','publication-r1']]
    gates = [json.loads(p.read_bytes()) for p in gate_paths]
    assert all(g['status'] == 'passed' for g in gates)
    for gate,count in zip(gates[:6],(37,31,57,104,400,19)):
        assert gate['tests']==count and gate['frozen_equal']
        assert gate['failures']==gate['errors']==gate['skipped']==0
        for name,pin in gate['file_hashes'].items():assert sha(ROOT/name)==pin,name
    assert gates[6]['cli_version']=='0.1.60' and gates[6]['model_forwards']==0
    assert gates[6]['complete_package_recipe_repair_PCM_equal']
    assert gates[6]['registered_skill_unchanged']
'''+text[end:]
    target=ROOT/'docs/validation/build_source60_delivery.py'
    assert not target.exists()
    target.write_text(text,encoding='utf-8')
    compile(text,str(target),'exec')
    print('Prepared CLI60/local58 builder; actual complete source gates required before execution.')

if __name__=='__main__':main()
