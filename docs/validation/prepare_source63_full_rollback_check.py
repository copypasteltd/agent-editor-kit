"""Extend the isolated rollback fixture to all93 changed Skill files."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];DOC=ROOT/'docs/validation'
text=(DOC/'check_source63_activation_rollback.py').read_text(encoding='utf-8')
for old,new in [("out=BASE/'activation-rollback-r1'","out=BASE/'activation-rollback-r2'"),
 ("home=ROOT/'local/agent-ffmpeg/source63-activation-rollback-r1'","home=ROOT/'local/agent-ffmpeg/source63-activation-rollback-r2'"),
 ("for scenario,fail_write in [('after-transition',1),('after-first-skill-write',2),('entry-verification',None)]:","for scenario,fail_write in [('all93-skill-files-and-metadata',None)]:"),
 ("if relative.as_posix()=='SKILL.md':data+=",'if True:data+='),
 ('  cli_calls.append(list(argv));return SimpleNamespace',"  assert sum(Path(p).read_bytes()!=data for p,data in original.items())==95\n  cli_calls.append(list(argv));return SimpleNamespace"),
 ('synthetic_CLI_calls=len(cli_calls),','synthetic_CLI_calls=len(cli_calls),files_changed_before_entry_failure=95,')]:
 assert old in text,old;text=text.replace(old,new)
target=DOC/'check_source63_activation_full_rollback.py';compile(text,str(target),'exec')
if target.exists():assert target.read_text(encoding='utf-8')==text
else:target.write_text(text,encoding='utf-8',newline='\n')
print('Prepared all95-file actual disk rollback fixture;synthetic gates and CLI failure.',flush=True)
