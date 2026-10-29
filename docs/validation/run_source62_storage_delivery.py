"""Sequential verification then scoped commit; no registration or virtualization."""
import subprocess,sys
from pathlib import Path
root=Path(__file__).resolve().parents[2]
for script in ('run_source62_storage_race.py','commit_source62_storage_race.py'):
 result=subprocess.run([sys.executable,'-I','-B','-u','-X','utf8',str(root/'docs/validation'/script)],cwd=root)
 if result.returncode:raise SystemExit(result.returncode)
