"""Actually request activation with missing draft receipts; prove full gate blocks it."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'docs/validation/evidence/lipsync-timeout-20261029-r1'

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    # These candidate cases have not been started; no other process creates them.
    assert not (BASE/'staged-actual-case-r1/verification.json').exists()
    assert not (BASE/'staged61-gpu-r1/verification.json').exists()
    namespace=ROOT/'agent-ffmpeg-local-install-manifest.json';runtime=ROOT/'local/agent-ffmpeg/runtime.json'
    live=json.loads(namespace.read_bytes());assert live['cli_version']=='0.1.59'
    files=[namespace,runtime,*[ROOT/r['path'] for r in live['files']]]
    guard={str(p):sha(p) for p in files};assert len(guard)==95
    out=BASE/'activation-gate-check-r1';out.mkdir(exist_ok=False)
    target=BASE/'skill61-activation-gate-check-r1';assert not target.exists()
    argv=[sys.executable,'-E','-B','-u','-X','utf8',str(ROOT/'docs/validation/activate_source61_skill.py'),
        '--run','gate-check-r1','--apply']
    p=subprocess.run(argv,cwd=ROOT,capture_output=True,timeout=120,creationflags=subprocess.CREATE_NO_WINDOW)
    (out/'stdout').write_bytes(p.stdout);(out/'stderr').write_bytes(p.stderr)
    response=json.loads(p.stdout)
    assert p.returncode==2 and response['status']=='pending' and not response['mutated'] and not response['activated']
    assert 'installed61_contracts' in response['missing']
    assert guard=={str(p):sha(p) for p in files} and not target.exists()
    report=dict(status='passed',actual_activation_requested=True,actual_exit_code=2,mutated=False,activated=False,
        protected_files_unchanged=95,missing=response['missing'],formal_cli='0.1.59',
        activation_runner_sha256=sha(ROOT/'docs/validation/activate_source61_skill.py'),
        installed403_still_required=True)
    (out/'verification.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report),flush=True)

if __name__=='__main__':main()
