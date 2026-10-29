"""Prepare rollback-capable activation; complete installed400 remains mandatory."""
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]

def main():
    text=(ROOT/'docs/validation/activate_source59_skill.py').read_text(encoding='utf-8')
    text=text.replace('CLI59','CLI60').replace('cli59','cli60').replace('source59','source60').replace('installed59','installed60')
    text=text.replace('staged59','staged60').replace('skill59','skill60')
    text=text.replace('0.1.59','0.1.60').replace('0.1.58','0.1.59')
    text=text.replace('v0.1.0-alpha.4-local.57','v0.1.0-alpha.4-local.58')
    text=text.replace('music-score-20261029-r1','music-loop-20261029-r1')
    start=text.index('    gates = ');end=text.index('    missing = ',start)
    text=text[:start]+'''    gates = {'installation':BASE/'installation-candidate-r1/verification.json',
        'candidate':BASE/'staged-actual-case-r1/verification.json',
        'staged_gpu':BASE/'staged60-gpu-r1/verification.json',
        'source_gpu':BASE/'source60-gpu-r1/verification.json',
        'installed_gpu':BASE/'installed60-gpu-r1/verification.json',
        'source_loop':BASE/'actual-case-r1/verification.json',
        'installed_loop':BASE/'installed-actual-case-r1/verification.json',
        'source_loop_tests':BASE/'targeted-r1/verification.json',
        'installed_loop_tests':BASE/'installed60-loop-r1/verification.json'}
    for mode in ['source60', 'installed60']:
        for group in ['bootstrap', 'control', 'selection', 'semantic', 'contracts']:
            gates[mode+'_'+group] = BASE/(mode+'-'+group+'-r1/verification.json')
'''+text[end:]
    start=text.index("    audit=reports['fixture_audit']");end=text.index('    for mode in ',start)
    text=text[:start]+text[end:]
    start=text.index('                current=sha(ROOT/name)');end=text.index("            if mode == 'installed60':",start)
    text=text[:start]+'''                assert sha(ROOT/name)==digest,name
'''+text[end:]
    start=text.index("    for name in ['source_score','content']:");end=text.index("    candidate = reports['candidate']",start)
    text=text[:start]+'''    for name in ['source_loop','installed_loop','candidate']:
        report=reports[name]
        assert report['status']=='passed' and report['cli_version']=='0.1.60'
        assert report['complete_package_recipe_repair_PCM_equal'] and report['complete_repeated_PCM_equal']
        assert report['complete_repaired_PCM_bytes']==2557440
        assert report['complete_repaired_PCM_sha256']==reports['source_loop']['complete_repaired_PCM_sha256']
    for name in ['installed_loop','candidate']:
        report=reports[name]
        assert report['complete_source_installed_PCM_equal'] and report['source_fallback'] is False
        assert Path(report['installed']).resolve()==installed
    for name in ['source_loop_tests','installed_loop_tests']:
        report=reports[name]
        assert report['tests']==37 and report['frozen_equal']
        assert report['failures']==report['errors']==report['skipped']==0
        assert all(sha(ROOT/path)==pin for path,pin in report['file_hashes'].items())
'''+text[end:]
    text=text.replace("music59-skill-draft-r1", "music60-skill-stage-r1")
    text=text.replace('len(source_pins)==282','len(source_pins)==283')
    path=ROOT/'docs/validation/activate_source60_skill.py';assert not path.exists()
    compile(text,str(path),'exec');path.write_text(text,encoding='utf-8')
    print('Prepared complete-gated activation and rollback; not executed.')

if __name__=='__main__':main()
