"""Exercise incomplete-delivery rejection and prove the live Skill is untouched."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[2]

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    namespace=ROOT/'agent-ffmpeg-local-install-manifest.json';runtime=ROOT/'local/agent-ffmpeg/runtime.json'
    manifest=json.loads(namespace.read_bytes());assert manifest['cli_version']=='0.1.59'
    files=[namespace,runtime,*[ROOT/r['path'] for r in manifest['files']]]
    before={str(p):sha(p) for p in files};assert len(before)==95
    candidate=ROOT/'local/agent-ffmpeg/music61-skill-stage-gate-check-r1';assert not candidate.exists()
    out=ROOT/'docs/validation/evidence/lipsync-timeout-20261029-r1/stage-gate-check-r1';out.mkdir(exist_ok=False)
    argv=[sys.executable,'-E','-B','-u','-X','utf8',str(ROOT/'docs/validation/stage_source61_skill.py'),'--run','gate-check-r1']
    p=subprocess.run(argv,cwd=ROOT,capture_output=True,timeout=120,creationflags=subprocess.CREATE_NO_WINDOW)
    (out/'stdout').write_bytes(p.stdout);(out/'stderr').write_bytes(p.stderr)
    response=json.loads(p.stdout)
    assert p.returncode==2 and response['status']=='pending' and not response['mutated']
    assert response['missing'] and not candidate.exists()
    assert before=={str(p):sha(p) for p in files}
    report=dict(status='passed',actual_gate_exit_code=2,missing=response['missing'],
        protected_files=95,live_cli='0.1.59',live_skill_unchanged=True,candidate_created=False,
        actual_installed61_acceptance=False,actual_skill61_activation=False,
        runner_sha256=sha(ROOT/'docs/validation/stage_source61_skill.py'))
    (out/'verification.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(report),flush=True)

if __name__=='__main__':main()
