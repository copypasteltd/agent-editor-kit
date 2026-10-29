"""Derive an unregistered early draft; keep the strict release gate unchanged."""
import hashlib
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]

def main():
    original=ROOT/'docs/validation/stage_source60_skill.py'
    assert hashlib.sha256(original.read_bytes()).hexdigest()=='786e14aad83c677adb78bef35555d22c8edb420c08e584693f62f5430a137a1d'
    text=original.read_text(encoding='utf-8')
    text=text.replace('Stage a single CLI60 Skill only after native installation and complete checks.',
        'Create an unregistered CLI60 draft while installed400 is pending; never activate.')
    old="    missing=[k for k,p in paths.items() if not p.is_file()]"
    new="    pending=[k for k,p in paths.items() if not p.is_file()]\n    missing=[k for k in pending if k!='installed60_contracts']"
    assert old in text;text=text.replace(old,new,1)
    text=text.replace("    reports={k:load(p) for k,p in paths.items()}",
        "    reports={k:load(p) for k,p in paths.items() if p.is_file()}")
    needle="            r=reports[mode+'_'+group]"
    assert needle in text;text=text.replace(needle,
        "            if mode=='installed60' and group=='contracts' and 'installed60_contracts' in pending:continue\n"+needle,1)
    text=text.replace("status='unregistered-candidate'", "status='unregistered-draft'")
    text=text.replace("gates={str(p):sha(p) for p in paths.values()},", "gates={str(p):sha(p) for p in paths.values() if p.is_file()},\n        pending_gates=pending,installed400_accepted='installed60_contracts' not in pending,\n        requires_installed400_before_activation=True,strict_release_gate_unchanged=True,")
    path=ROOT/'docs/validation/draft_source60_skill.py';assert not path.exists()
    compile(text,str(path),'exec');path.write_text(text,encoding='utf-8')
    print('Prepared unregistered draft; strict release gate and live Skill unchanged.')

if __name__=='__main__':main()
