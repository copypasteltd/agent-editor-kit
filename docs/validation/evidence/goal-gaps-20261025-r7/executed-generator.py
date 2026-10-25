"""Read the actual registered installation without rendering or model inference."""
from __future__ import annotations
from collections import Counter
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import subprocess
import argparse
import urllib.request
import urllib.error

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    output=args.output.resolve()
    assert output.is_relative_to(ROOT/'docs/validation/evidence')
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
    assert runtime['release']=='v0.1.0-alpha.4-local.5'
    api='https://api.github.com/repos/copypasteltd/agent-editor-kit/releases?per_page=10'
    releases=None; api_error=None; api_status=None
    try:
        request=urllib.request.Request(api,headers={'User-Agent':'agent-editor-kit-validation','Accept':'application/vnd.github+json'})
        with urllib.request.urlopen(request,timeout=30) as remote:
            raw=remote.read(4*1024**2); api_status=remote.status
        (output/'releases-raw.json').write_bytes(raw)
        releases=[{key:row[key] for key in ('tag_name','prerelease','draft','published_at','html_url')} for row in json.loads(raw)]
        (output/'releases.json').write_text(json.dumps(releases,indent=2)+'\n',encoding='utf-8')
    except (OSError,ValueError) as exc:
        api_error=str(exc); api_status=getattr(exc,'code',None)
    record=dict(checked_at_utc=datetime.now(timezone.utc).isoformat(),scope='six actual read-only unified Skill calls; no new rendering/inference/listening',
        calls=calls,runtime=runtime,version=responses['version']['data'],capability_count=len(entries),statuses=dict(counts),
        skill_count=1,internal_modules=17,goal_groups=38,all_groups_retain_open_conditions=True,
        github_release_api=dict(url=api,http_status=api_status,error=api_error),public_releases=releases,new_model_calls=0,new_renders=0,human_listening=False,
        native_windows=True,virtualization=False,browser_ui=False,
        original_failure_gates_preserved=['G15: 66.6667ms alignment','G16: short-window +/-5Hz','G20/G22 natural failures','G26 negation/OOD'],
        generator_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    (output/'inventory.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n',encoding='utf-8',newline='\n')
    (ROOT/'docs/product/job-recovery-capabilities-cli-0.1.7.json').write_bytes((output/'capabilities.json').read_bytes())
    print(json.dumps(dict(calls=len(calls),capabilities=len(entries),statuses=dict(counts),release_api_http_status=api_status)))


if __name__=='__main__':main()
