"""Fault-injection harness: load installed bytes, pause only at an explicit boundary."""
import json
import os
from pathlib import Path
import sys
import time

spec = json.loads(Path(sys.argv[1]).read_bytes())
installed = Path(spec['installed']).resolve(strict=True)
sys.path[:] = [str(installed / 'site'), *[p for p in sys.path
    if not {'site-packages', 'dist-packages'} & set(Path(p).parts)]]
os.environ.setdefault('AI_AD_EDITOR_RUNTIME_DIR', str(installed / 'runtime'))
from ai_ad_editor import job_trees, project
from ai_ad_editor.cli import main

state = {}
original_publish = job_trees.publish


def pause():
    record = dict(parent_pid=os.getpid(), hook=spec['hook'], **state)
    Path(spec['checkpoint']).write_text(json.dumps(record, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
    # A controlled pause in the verification harness, never a product retry or
    # production environment switch. The supervising process ends this owner.
    end = time.monotonic() + 600
    while time.monotonic() < end:
        time.sleep(.1)
    raise RuntimeError('Fault checkpoint was not consumed within its bounded window')


def publish(workspace, stage, destination):
    original_publish(workspace, stage, destination)
    state.update(job=str(workspace.path), destination=str(destination), kind=workspace.record['kind'])
    if spec['hook'] == 'after-publication':
        pause()


job_trees.publish = publish
original_commit = project.commit_project_transaction


def commit(*arguments, **options):
    value = original_commit(*arguments, **options)
    if spec['hook'] == 'after-commit' and state:
        pause()
    return value


project.commit_project_transaction = commit
raise SystemExit(main(spec['arguments']))
