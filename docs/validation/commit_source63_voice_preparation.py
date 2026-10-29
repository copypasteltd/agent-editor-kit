"""Commit frozen source acceptance, candidate installation and Skill preparation."""
import hashlib,json,os,re,subprocess
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];BASE=ROOT/'docs/validation/evidence/job-enumeration-20261029-r1'
GIT=Path('C:/Users/carzy/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/git/cmd/git.exe')
def load(p):return json.loads(p.read_bytes())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
source=load(BASE/'source63-contracts-r1/verification.json')
assert source['status']=='passed' and source['tests']==406 and source['frozen_equal']
assert source['failures']==source['errors']==source['skipped']==0
assert all(sha(ROOT/p)==h for p,h in source['file_hashes'].items())
assert load(BASE/'source-controller-r1/verification.json')['status']=='passed'
voice=load(BASE/'voice-preparation-r1/verification.json')
assert voice['status']=='passed' and voice['audited_existing_samples']==103 and voice['formal_files_unchanged']==95
assert voice['stage_script_sha256']==sha(ROOT/'docs/validation/stage_source63_skill.py')
installed=load(BASE/'installation-candidate-r1/verification.json')
assert installed['status']=='installed-and-byte-verified' and installed['source_file_count']==283
assert installed['exact_product_payload']['payload_files']==1707 and installed['exact_product_payload']['payload_byte_exact']
assert sha(Path(installed['archive']))==installed['archive_sha256']
assert all(sha(Path(p))==h for p,h in installed['registered_skill_file_hashes'].items())
files=['README.md','README.zh-TW.md','README.en.md']
for name in files:
 text=(ROOT/name).read_text(encoding='utf-8');assert len(re.findall(r'^\| R\d+ \|',text,re.M))==516
 assert all('| R'+str(n)+' |' in text for n in (513,514,515,516))
scripts=['stage_source63_skill.py','check_source63_voice_preparation.py','prepare_source63_skill_cases.py',
 'run_source63_skill_acceptance.py','run_staged63_loop_case.py','run_staged63_gpu_case.py',
 'run_staged63_lipsync_case.py','update_source63_delivery_readmes.py','commit_source63_voice_preparation.py']
for name in scripts:
 p=ROOT/'docs/validation'/name;compile(p.read_text(encoding='utf-8'),str(p),'exec');files.append(p.relative_to(ROOT).as_posix())
files.append('docs/validation/CLI63候选交付门禁_2026-10-29.md')
for directory in ['source63-contracts-r1','source-controller-r1','publication-r1','installation-candidate-r1','voice-preparation-r1','installed63-bootstrap-r1']:
 files.extend(p.relative_to(ROOT).as_posix() for p in (BASE/directory).iterdir() if p.is_file())
files=sorted(set(files));out=ROOT/'local/agent-ffmpeg/source63-voice-preparation-commit-r1';out.mkdir(exist_ok=False)
spec=out/'paths.nul';spec.write_bytes(b'\0'.join(p.encode('utf-8') for p in files)+b'\0')
env=dict(os.environ);env['PATH']=str(GIT.parent)+os.pathsep+env.get('PATH','')
git=[str(GIT),'--no-optional-locks','-c','core.fsmonitor=false','-c','gc.auto=0','-c','maintenance.auto=0']
def get(args):return subprocess.check_output([*git,*args],cwd=ROOT,env=env).decode().strip()
assert get(['branch','--show-current'])=='main'
assert get(['rev-parse','HEAD'])=='9fbbbc230e5f8b4ed1858150b6cc49fa7f277f54'
assert get(['remote','get-url','origin'])=='git@github.com:copypasteltd/agent-editor-kit.git'
steps=[('add',['add','--pathspec-from-file='+str(spec),'--pathspec-file-nul'])]
steps += [('check-'+str(i//60),['diff','--cached','--check','--',*files[i:i+60]]) for i in range(0,len(files),60)]
steps += [('commit',['commit','--only','-m','feat: prepare pre-tested voice guidance and accept CLI63 source and native candidate','--pathspec-from-file='+str(spec),'--pathspec-file-nul'])]
for phase,args in steps:
 r=subprocess.run([*git,*args],cwd=ROOT,env=env,capture_output=True)
 (out/(phase+'.stdout')).write_bytes(r.stdout);(out/(phase+'.stderr')).write_bytes(r.stderr)
 print(json.dumps(dict(phase=phase,exit_code=r.returncode)),flush=True)
 if r.returncode:raise SystemExit(r.returncode)
refs=dict(head=get(['rev-parse','HEAD']),origin=get(['rev-parse','origin/main']),remote=get(['ls-remote','origin','refs/heads/main']).split()[0])
assert len(set(refs.values()))==1
receipt=dict(status='passed',refs=refs,files=len(files),source='0.1.63',installed_candidate='0.1.63/local61',formal='0.1.59/local57/r57',README_rows=516,formal_activation=False,full_goal_closed=False)
(out/'verification.json').write_text(json.dumps(receipt,indent=2)+'\n',encoding='utf-8');print(json.dumps(receipt),flush=True)
