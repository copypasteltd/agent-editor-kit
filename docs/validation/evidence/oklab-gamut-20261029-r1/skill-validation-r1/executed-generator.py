"""Capture the Skill creator validator against the actual pinned unified entry."""
from pathlib import Path
import argparse,hashlib,json,subprocess,sys
ROOT=Path(__file__).resolve().parents[1]
ap=argparse.ArgumentParser();ap.add_argument('--run',required=True);a=ap.parse_args();assert a.run.replace('-','').isalnum()
out=ROOT/'docs/validation/evidence/oklab-gamut-20261029-r1'/('skill-validation-'+a.run);out.mkdir(exist_ok=False)
(out/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
validator=Path('C:/Users/carzy/.codex/skills/.system/skill-creator/scripts/quick_validate.py')
result=subprocess.run([sys.executable,'-E','-B','-X','utf8',str(validator),str(ROOT/'skills/agent-ffmpeg-local-editor')],cwd=ROOT,capture_output=True,timeout=120,creationflags=subprocess.CREATE_NO_WINDOW)
(out/'stdout.txt').write_bytes(result.stdout);(out/'stderr.txt').write_bytes(result.stderr)
report=dict(status='passed' if result.returncode==0 else 'failed',exit_code=result.returncode,
 validator_sha256=hashlib.sha256(validator.read_bytes()).hexdigest(),stdout_sha256=hashlib.sha256(result.stdout).hexdigest(),
 namespace_manifest_sha256=hashlib.sha256((ROOT/'agent-ffmpeg-local-install-manifest.json').read_bytes()).hexdigest(),
 skill_files=len(json.loads((ROOT/'agent-ffmpeg-local-install-manifest.json').read_bytes())['files']))
(out/'verification.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8',newline='\n');print(json.dumps(report));raise SystemExit(result.returncode)
