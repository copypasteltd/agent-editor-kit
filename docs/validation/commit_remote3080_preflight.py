"""Commit sanitized read-only second-host evidence; normal main push."""
import hashlib,json,os,re,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
GIT=Path('C:/Users/carzy/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/git/cmd/git.exe')
def load(p):return json.loads(p.read_bytes())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
base=ROOT/'docs/validation/evidence/remote3080-native-20261029-r2';r=load(base/'verification.json')
assert r['status']=='read-only-inventory-completed' and r['identity_matched']
assert not r['native_installation_executed'] and not r['actual_CUDA_inference'] and not r['clean_host_accepted']
assert not r['explicit_remote_configuration_changes'] and not r['explicit_remote_file_writes'] and r['browser_tabs_opened']==0
assert (base/'executed-runner.py').read_bytes()==(ROOT/'docs/validation/probe_remote3080_native_readonly.py').read_bytes()
m=load(ROOT/'agent-ffmpeg-local-install-manifest.json');assert m['cli_version']=='0.1.59'
installation=load(ROOT/'docs/validation/evidence/job-enumeration-20261029-r1/installation-candidate-r1/verification.json')
assert all(sha(Path(p))==h for p,h in installation['registered_skill_file_hashes'].items())
files=['README.md','README.zh-TW.md','README.en.md','docs/product/GOAL_GAPS_20261025.md',
 'docs/validation/第二台Windows原生环境预检_2026-10-29.md',
 'docs/validation/probe_remote3080_native_readonly.py','docs/validation/update_remote3080_preflight_docs.py',
 'docs/validation/commit_remote3080_preflight.py']
files.extend(p.relative_to(ROOT).as_posix() for p in base.iterdir() if p.is_file());files=sorted(set(files))
for name in files:
 p=ROOT/name
 if p.suffix=='.py':compile(p.read_text(encoding='utf-8'),str(p),'exec')
 if name in ['README.md','README.zh-TW.md','README.en.md']:assert len(re.findall(r'^\| R\d+ \|',p.read_text(encoding='utf-8'),re.M))==522
# Keep actual device identity/credentials and private desktop outside this commit.
config=load(Path('C:/Users/carzy/.codex/skills/remote-3080/device.json'))
for name in files:
 content=(ROOT/name).read_bytes()
 assert config['bearer_token'].encode() not in content and config['hostname'].encode() not in content
out=ROOT/'local/agent-ffmpeg/remote3080-preflight-commit-r1';out.mkdir(exist_ok=False)
spec=out/'paths.nul';spec.write_bytes(b'\0'.join(p.encode('utf-8') for p in files)+b'\0')
env=dict(os.environ);env['PATH']=str(GIT.parent)+os.pathsep+env.get('PATH','')
git=[str(GIT),'--no-optional-locks','-c','core.fsmonitor=false','-c','gc.auto=0','-c','maintenance.auto=0']
def get(args):return subprocess.check_output([*git,*args],cwd=ROOT,env=env).decode('utf-8').strip()
assert get(['branch','--show-current'])=='main'
assert get(['rev-parse','HEAD'])=='f9176739f49a2a35e1b75dc011383d7cb2b25469'
assert get(['remote','get-url','origin'])=='git@github.com:copypasteltd/agent-editor-kit.git'
old=re.findall(r'^\| G\d\d \|.*$',get(['show','HEAD:docs/product/GOAL_GAPS_20261025.md']),re.M)
new=re.findall(r'^\| G\d\d \|.*$',(ROOT/'docs/product/GOAL_GAPS_20261025.md').read_text(encoding='utf-8'),re.M)
assert len(old)==38 and old==new
steps=[('add',['add','--pathspec-from-file='+str(spec),'--pathspec-file-nul'])]
steps += [('check-'+str(i//60),['diff','--cached','--check','--',*files[i:i+60]]) for i in range(0,len(files),60)]
steps += [('commit',['commit','--only','-m','docs: record second native Windows inventory and explicit deployment gaps','--pathspec-from-file='+str(spec),'--pathspec-file-nul'])]
for phase,args in steps:
 result=subprocess.run([*git,*args],cwd=ROOT,env=env,capture_output=True)
 (out/(phase+'.stdout')).write_bytes(result.stdout);(out/(phase+'.stderr')).write_bytes(result.stderr)
 print(json.dumps(dict(phase=phase,exit_code=result.returncode)),flush=True)
 if result.returncode:raise SystemExit(result.returncode)
refs=dict(head=get(['rev-parse','HEAD']),origin=get(['rev-parse','origin/main']),remote=get(['ls-remote','origin','refs/heads/main']).split()[0])
assert len(set(refs.values()))==1
receipt=dict(status='passed',refs=refs,files=len(files),source='0.1.63',installed_candidate='0.1.63/local61',formal='0.1.59/local57/r57',README_rows=522,original_goal_rows_unchanged=38,formal_activation=False,full_goal_closed=False)
(out/'verification.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8');print(json.dumps(receipt),flush=True)
