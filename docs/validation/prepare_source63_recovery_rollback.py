"""Rebind isolated rollback checks to the explicit installed-contract r2 gate.

The original four r1/r2 fixture results remain immutable. The new r3/r4 runs
still use synthetic acceptance inputs and CLI failures, never real models.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOC = ROOT / 'docs/validation'
base = (DOC / 'check_source63_activation_rollback.py').read_text(encoding='utf-8')
needle = "   receipt(mode+'-'+group+'-r1',dict("
replacement = "   run='r2' if mode=='installed63' and group=='contracts' else 'r1'\n   receipt(mode+'-'+group+'-'+run,dict("
assert base.count(needle) == 1
base = base.replace(needle, replacement)
for run, name, full in [('r3', 'check_source63_recovery_rollback.py', False),
                         ('r4', 'check_source63_recovery_full_rollback.py', True)]:
    text = base.replace("out=BASE/'activation-rollback-r1'", "out=BASE/'activation-rollback-" + run + "'")
    text = text.replace("home=ROOT/'local/agent-ffmpeg/source63-activation-rollback-r1'",
                        "home=ROOT/'local/agent-ffmpeg/source63-activation-rollback-" + run + "'")
    if full:
        substitutions = [
            ("for scenario,fail_write in [('after-transition',1),('after-first-skill-write',2),('entry-verification',None)]:",
             "for scenario,fail_write in [('all93-skill-files-and-metadata',None)]:"),
            ("if relative.as_posix()=='SKILL.md':data+=", 'if True:data+='),
            ('  cli_calls.append(list(argv));return SimpleNamespace',
             '  assert sum(Path(p).read_bytes()!=data for p,data in original.items())==95\n  cli_calls.append(list(argv));return SimpleNamespace'),
            ('synthetic_CLI_calls=len(cli_calls),', 'synthetic_CLI_calls=len(cli_calls),files_changed_before_entry_failure=95,')]
        for old, new in substitutions:
            assert old in text
            text = text.replace(old, new)
    target = DOC / name
    compile(text, str(target), 'exec')
    if target.exists():
        assert target.read_text(encoding='utf-8') == text
    else:
        target.write_text(text, encoding='utf-8', newline='\n')
print('Prepared r3/r4 isolated rollback against the r2 contract gate; synthetic model inputs only.')
