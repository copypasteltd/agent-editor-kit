"""Commit guarded CLI63 transition preparation and installed-group evidence."""
import hashlib,json,os,re,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];BASE=ROOT/'docs/validation/evidence/job-enumeration-20261029-r1'
GIT=Path('C:/Users/carzy/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/git/cmd/git.exe')
def load(p):return json.loads(p.read_bytes())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
proof=load(BASE/'activation-preflight-r1/verification.json')
assert proof['status']=='passed' and proof['formal_files_unchanged']==95
assert proof['actual_atomic_replacement'] and proof['actual_failed_replace_temp_cleanup']
assert proof['script_sha256']==sha(ROOT/'docs/validation/activate_source63_skill.py')
assert all(c['exit_code']==2 and not c['reply']['mutated'] for c in proof['calls'])
installation=load(BASE/'installation-candidate-r1/verification.json')
assert all(sha(Path(p))==h for p,h in installation['registered_skill_file_hashes'].items())
for group,count in [('bootstrap',31),('loop',37),('control',26),('selection',57)]:
 r=load(BASE/f'installed63-{group}-r1/verification.json')
 assert r['status']=='passed' and r['tests']==count and r['frozen_equal'] and r['source_and_installed_equal']
 assert r['failures']==r['errors']==r['skipped']==0
 assert all(sha(ROOT/p)==h for p,h in r['file_hashes'].items())
files=['README.md','README.zh-TW.md','README.en.md','docs/validation/CLI63候选交付门禁_2026-10-29.md']
for name in files[:3]:assert len(re.findall(r'^\| R\d+ \|',(ROOT/name).read_text(encoding='utf-8'),re.M))==518
for name in ['prepare_source63_activation.py','activate_source63_skill.py','check_source63_activation_preflight.py',
 'wait_source63_skill_acceptance.py','update_source63_activation_readmes.py','commit_source63_activation_preparation.py']:
 p=ROOT/'docs/validation'/name;compile(p.read_text(encoding='utf-8'),str(p),'exec');files.append(p.relative_to(ROOT).as_posix())
for directory in ['activation-preflight-r1','installed63-loop-r1','installed63-control-r1','installed63-selection-r1']:
 files.extend(p.relative_to(ROOT).as_posix() for p in (BASE/directory).iterdir() if p.is_file())
files=sorted(set(files));out=ROOT/'local/agent-ffmpeg/source63-activation-preparation-commit-r1';out.mkdir(exist_ok=False)
spec=out/'paths.nul';spec.write_bytes(b'\0'.join(p.encode('utf-8') for p in files)+b'\0')
env=dict(os.environ);env['PATH']=str(GIT.parent)+os.pathsep+env.get('PATH','')
git=[str(GIT),'--no-optional-locks','-c','core.fsmonitor=false','-c','gc.auto=0','-c','maintenance.auto=0']
def get(args):return subprocess.check_output([*git,*args],cwd=ROOT,env=env).decode().strip()
assert get(['branch','--show-current'])=='main'
assert get(['rev-parse','HEAD'])=='5fff4b022f2f2df919fe281ebaadc00cc4a48c9c'
assert get(['remote','get-url','origin'])=='git@github.com:copypasteltd/agent-editor-kit.git'
steps=[('add',['add','--pathspec-from-file='+str(spec),'--pathspec-file-nul'])]
steps += [('check-'+str(i//60),['diff','--cached','--check','--',*files[i:i+60]]) for i in range(0,len(files),60)]
steps += [('commit',['commit','--only','-m','feat: guard exact tested Skill activation and continue installed acceptance','--pathspec-from-file='+str(spec),'--pathspec-file-nul'])]
for phase,args in steps:
 r=subprocess.run([*git,*args],cwd=ROOT,env=env,capture_output=True)
 (out/(phase+'.stdout')).write_bytes(r.stdout);(out/(phase+'.stderr')).write_bytes(r.stderr)
 print(json.dumps(dict(phase=phase,exit_code=r.returncode)),flush=True)
 if r.returncode:raise SystemExit(r.returncode)
refs=dict(head=get(['rev-parse','HEAD']),origin=get(['rev-parse','origin/main']),remote=get(['ls-remote','origin','refs/heads/main']).split()[0])
assert len(set(refs.values()))==1
receipt=dict(status='passed',refs=refs,files=len(files),source='0.1.63',installed_candidate='0.1.63/local61',formal='0.1.59/local57/r57',README_rows=518,formal_activation=False,full_goal_closed=False)
(out/'verification.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8');print(json.dumps(receipt),flush=True)
