"""Commit actual isolated rollback evidence without promoting the candidate."""
import hashlib,json,os,re,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];BASE=ROOT/'docs/validation/evidence/job-enumeration-20261029-r1'
GIT=Path('C:/Users/carzy/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/git/cmd/git.exe')
def load(p):return json.loads(p.read_bytes())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
for directory in ['activation-rollback-r1','activation-rollback-r2']:
 r=load(BASE/directory/'verification.json')
 assert r['status']=='passed' and r['production_files_unchanged']==95
 assert r['synthetic_gate_inputs'] and not r['model_inference'] and not r['formal_activation']
 assert r['script_sha256']==sha(ROOT/'docs/validation/activate_source63_skill.py')
r=load(BASE/'activation-rollback-r2/verification.json')['cases'][0]
assert r['files_changed_before_entry_failure']==95 and r['restored_files']==95 and r['actual_atomic_writes']==192
installation=load(BASE/'installation-candidate-r1/verification.json')
assert all(sha(Path(p))==h for p,h in installation['registered_skill_file_hashes'].items())
files=['README.md','README.zh-TW.md','README.en.md','docs/product/GOAL_GAPS_20261025.md',
 'docs/validation/CLI63Skill隔离回滚_2026-10-29.md']
for name in files[:3]:assert len(re.findall(r'^\| R\d+ \|',(ROOT/name).read_text(encoding='utf-8'),re.M))==521
for name in ['check_source63_activation_rollback.py','prepare_source63_full_rollback_check.py',
 'check_source63_activation_full_rollback.py','update_source63_rollback_docs.py','commit_source63_rollback.py']:
 p=ROOT/'docs/validation'/name;compile(p.read_text(encoding='utf-8'),str(p),'exec');files.append(p.relative_to(ROOT).as_posix())
for directory in ['activation-rollback-r1','activation-rollback-r2']:
 files.extend(p.relative_to(ROOT).as_posix() for p in (BASE/directory).iterdir() if p.is_file())
files=sorted(set(files));out=ROOT/'local/agent-ffmpeg/source63-rollback-commit-r1';out.mkdir(exist_ok=False)
spec=out/'paths.nul';spec.write_bytes(b'\0'.join(p.encode('utf-8') for p in files)+b'\0')
env=dict(os.environ);env['PATH']=str(GIT.parent)+os.pathsep+env.get('PATH','')
git=[str(GIT),'--no-optional-locks','-c','core.fsmonitor=false','-c','gc.auto=0','-c','maintenance.auto=0']
def get(args):return subprocess.check_output([*git,*args],cwd=ROOT,env=env).decode('utf-8').strip()
assert get(['branch','--show-current'])=='main'
assert get(['rev-parse','HEAD'])=='299fe19fc33e1f7e26248ab1d886442558e46952'
assert get(['remote','get-url','origin'])=='git@github.com:copypasteltd/agent-editor-kit.git'
baseline=get(['show','HEAD:docs/product/GOAL_GAPS_20261025.md'])
before=re.findall(r'^\| G\d\d \|.*$',baseline,re.M)
after=re.findall(r'^\| G\d\d \|.*$',(ROOT/'docs/product/GOAL_GAPS_20261025.md').read_text(encoding='utf-8'),re.M)
assert len(before)==38 and before==after
steps=[('add',['add','--pathspec-from-file='+str(spec),'--pathspec-file-nul'])]
steps += [('check-'+str(i//60),['diff','--cached','--check','--',*files[i:i+60]]) for i in range(0,len(files),60)]
steps += [('commit',['commit','--only','-m','test: verify isolated CLI63 rollback after all 95 files change','--pathspec-from-file='+str(spec),'--pathspec-file-nul'])]
for phase,args in steps:
 result=subprocess.run([*git,*args],cwd=ROOT,env=env,capture_output=True)
 (out/(phase+'.stdout')).write_bytes(result.stdout);(out/(phase+'.stderr')).write_bytes(result.stderr)
 print(json.dumps(dict(phase=phase,exit_code=result.returncode)),flush=True)
 if result.returncode:raise SystemExit(result.returncode)
refs=dict(head=get(['rev-parse','HEAD']),origin=get(['rev-parse','origin/main']),remote=get(['ls-remote','origin','refs/heads/main']).split()[0])
assert len(set(refs.values()))==1
receipt=dict(status='passed',refs=refs,files=len(files),source='0.1.63',installed_candidate='0.1.63/local61',formal='0.1.59/local57/r57',README_rows=521,original_goal_rows_unchanged=38,formal_activation=False,full_goal_closed=False)
(out/'verification.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8');print(json.dumps(receipt),flush=True)
