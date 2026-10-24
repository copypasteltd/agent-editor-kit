from pathlib import Path
import json,os,sys,time
installed,phase,barrier=Path(sys.argv[1]),sys.argv[2],Path(sys.argv[3])
sys.path[:]=[str(installed/'site'),*[p for p in sys.path if not {'site-packages','dist-packages'} & set(Path(p).parts)]]
os.environ.setdefault('AI_AD_EDITOR_RUNTIME_DIR',str(installed/'runtime'))
from ai_ad_editor.cli import main
from ai_ad_editor.utils import atomic_write_json
from ai_ad_editor.job_workspaces import Workspace
from ai_ad_editor import project
def pause(point):
 atomic_write_json(barrier,dict(phase=point,cli_pid=os.getpid(),injection='observation barrier only; no DSP/model/quality changes'))
 while True: time.sleep(.1)
original_publish=Workspace.publish
def publish(self,stage,destination):
 original_publish(self,stage,destination)
 if phase=='first-publication': pause(phase)
Workspace.publish=publish
original_commit=project.commit_project_transaction
def commit(root,transaction_id):
 if phase=='prepared-metadata': pause(phase)
 result=original_commit(root,transaction_id)
 if phase=='committed-metadata': pause(phase)
 return result
project.commit_project_transaction=commit
raise SystemExit(main(sys.argv[4:]))
