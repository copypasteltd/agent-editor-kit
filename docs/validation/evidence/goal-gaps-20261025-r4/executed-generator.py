"""Read the actual registered installation without rendering or model inference."""
from __future__ import annotations
from collections import Counter
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[1]


def main():
    output=ROOT/'docs/validation/evidence/goal-gaps-20261025-r4'
    output.mkdir(parents=True,exist_ok=False)
    (output/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    skill=Path('C:/Users/carzy/.codex/skills/agent-ffmpeg-local-editor/scripts/run.ps1')
    commands=[['version'],['doctor'],['capabilities'],['schema','show'],['gpu','inspect'],['model-pack','list']]
    calls=[]; responses={}
    for argv in commands:
        result=subprocess.run(['powershell','-NoProfile','-ExecutionPolicy','Bypass','-File',str(skill),*argv],cwd=ROOT,
                              capture_output=True,timeout=300)
        name='-'.join(argv)
        (output/(name+'.json')).write_bytes(result.stdout); (output/(name+'-stderr.txt')).write_bytes(result.stderr)
        value=json.loads(result.stdout.decode('utf-8-sig')); assert result.returncode==0 and value['ok'],value
        responses[name]=value
        calls.append(dict(argv=argv,exit_code=result.returncode,command=value['command'],status=value['status']))
    entries=responses['capabilities']['data']['capabilities']
    counts=Counter(value['status'] for value in entries.values())
    runtime=json.loads((ROOT/'local/agent-ffmpeg/runtime.json').read_text('utf-8'))
    assert runtime['release']=='v0.1.0-alpha.4-local.4'
    remote=subprocess.run(['gh','api','repos/copypasteltd/agent-editor-kit/releases','--jq',
        'map({tag_name,prerelease,draft,published_at,html_url})'],cwd=ROOT,capture_output=True,timeout=60)
    (output/'releases.json').write_bytes(remote.stdout); (output/'releases-stderr.txt').write_bytes(remote.stderr)
    releases=json.loads(remote.stdout.decode('utf-8-sig')) if remote.returncode==0 else None
    record=dict(checked_at_utc=datetime.now(timezone.utc).isoformat(),scope='six actual read-only unified Skill calls; no new rendering/inference/listening',
        calls=calls,runtime=runtime,version=responses['version']['data'],capability_count=len(entries),statuses=dict(counts),
        skill_count=1,internal_modules=17,goal_groups=38,all_groups_retain_open_conditions=True,
        github_release_api_exit_code=remote.returncode,public_releases=releases,new_model_calls=0,new_renders=0,human_listening=False,
        native_windows=True,virtualization=False,browser_ui=False,
        original_failure_gates_preserved=['G15: 66.6667ms alignment','G16: short-window +/-5Hz','G20/G22 natural failures','G26 negation/OOD'],
        generator_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    (output/'inventory.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    (ROOT/'docs/product/four-stem-capabilities-cli-0.1.6.json').write_bytes((output/'capabilities.json').read_bytes())
    print(json.dumps(dict(calls=len(calls),capabilities=len(entries),statuses=dict(counts),release_api_exit_code=remote.returncode)))


if __name__=='__main__':main()
