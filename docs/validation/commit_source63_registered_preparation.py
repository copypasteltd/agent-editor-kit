"""Commit registered-entry guards, loop manual and installed semantic evidence."""
import hashlib,json,os,re,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];BASE=ROOT/'docs/validation/evidence/job-enumeration-20261029-r1'
GIT=Path('C:/Users/carzy/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/git/cmd/git.exe')
def load(p):return json.loads(p.read_bytes())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
r=load(BASE/'registered-preflight-r1/verification.json')
assert r['status']=='passed' and r['formal_files_unchanged']==95 and not r['registered_case_executed'] and not r['final_kit_built']
for name,h in r['compiled_scripts'].items():assert sha(ROOT/'docs/validation'/name)==h
assert all(c['exit_code']==2 and not c['reply']['mutated'] for c in r['calls'])
semantic=load(BASE/'installed63-semantic-r1/verification.json')
assert semantic['status']=='passed' and semantic['tests']==104 and semantic['frozen_equal'] and semantic['source_and_installed_equal']
assert semantic['failures']==semantic['errors']==semantic['skipped']==0
assert all(sha(ROOT/p)==h for p,h in semantic['file_hashes'].items())
installation=load(BASE/'installation-candidate-r1/verification.json')
assert all(sha(Path(p))==h for p,h in installation['registered_skill_file_hashes'].items())
files=['README.md','README.zh-TW.md','README.en.md','docs/validation/CLI63候选交付门禁_2026-10-29.md','docs/product/MUSIC_LOOP.md']
for name in files[:3]:assert len(re.findall(r'^\| R\d+ \|',(ROOT/name).read_text(encoding='utf-8'),re.M))==520
for name in [*r['compiled_scripts'],'check_source63_registered_preflight.py','update_source63_registered_readmes.py','commit_source63_registered_preparation.py']:
 p=ROOT/'docs/validation'/name;compile(p.read_text(encoding='utf-8'),str(p),'exec');files.append(p.relative_to(ROOT).as_posix())
for directory in ['registered-preflight-r1','installed63-semantic-r1']:
 files.extend(p.relative_to(ROOT).as_posix() for p in (BASE/directory).iterdir() if p.is_file())
files=sorted(set(files));out=ROOT/'local/agent-ffmpeg/source63-registered-preparation-commit-r1';out.mkdir(exist_ok=False)
spec=out/'paths.nul';spec.write_bytes(b'\0'.join(p.encode('utf-8') for p in files)+b'\0')
env=dict(os.environ);env['PATH']=str(GIT.parent)+os.pathsep+env.get('PATH','')
git=[str(GIT),'--no-optional-locks','-c','core.fsmonitor=false','-c','gc.auto=0','-c','maintenance.auto=0']
def get(args):return subprocess.check_output([*git,*args],cwd=ROOT,env=env).decode().strip()
assert get(['branch','--show-current'])=='main'
assert get(['rev-parse','HEAD'])=='49952186252d13f46672a39eab22737584d902d5'
assert get(['remote','get-url','origin'])=='git@github.com:copypasteltd/agent-editor-kit.git'
steps=[('add',['add','--pathspec-from-file='+str(spec),'--pathspec-file-nul'])]
steps += [('check-'+str(i//60),['diff','--cached','--check','--',*files[i:i+60]]) for i in range(0,len(files),60)]
steps += [('commit',['commit','--only','-m','feat: gate registered CLI63 checks and final kit on actual acceptance','--pathspec-from-file='+str(spec),'--pathspec-file-nul'])]
for phase,args in steps:
 result=subprocess.run([*git,*args],cwd=ROOT,env=env,capture_output=True)
 (out/(phase+'.stdout')).write_bytes(result.stdout);(out/(phase+'.stderr')).write_bytes(result.stderr)
 print(json.dumps(dict(phase=phase,exit_code=result.returncode)),flush=True)
 if result.returncode:raise SystemExit(result.returncode)
refs=dict(head=get(['rev-parse','HEAD']),origin=get(['rev-parse','origin/main']),remote=get(['ls-remote','origin','refs/heads/main']).split()[0])
assert len(set(refs.values()))==1
receipt=dict(status='passed',refs=refs,files=len(files),source='0.1.63',installed_candidate='0.1.63/local61',formal='0.1.59/local57/r57',README_rows=520,formal_activation=False,full_goal_closed=False)
(out/'verification.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8');print(json.dumps(receipt),flush=True)
