"""Verify the actual Codex discovery junction and new pinned installed commands."""
from pathlib import Path
import hashlib
import json
import os
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    evidence = ROOT / 'docs/validation/evidence/implementation-20261025-r1/skill'
    evidence.mkdir(parents=True, exist_ok=False)
    (evidence/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    discovery = Path(os.environ.get('CODEX_HOME', str(Path(os.environ['USERPROFILE'])/'.codex'))) / 'skills'
    entry = discovery/'agent-ffmpeg-local-editor'
    assert entry.is_junction() and entry.resolve() == ROOT/'skills/agent-ffmpeg-local-editor'
    assert [p.name for p in discovery.iterdir() if p.name.startswith('agent-ffmpeg-local-')] == ['agent-ffmpeg-local-editor']
    manifest = json.loads((ROOT/'agent-ffmpeg-local-install-manifest.json').read_bytes())
    runtime = json.loads((ROOT/'local/agent-ffmpeg/runtime.json').read_bytes())
    assert manifest['release'] == runtime['release'] == 'v0.1.0-alpha.4-local.2'
    assert manifest['manifest_sha256'] == runtime['manifest_sha256']
    assert manifest['cli_version'] == '0.1.4' and manifest['skill_count'] == 1 and manifest['module_count'] == 17
    for row in manifest['files']:
        data = (ROOT/row['path']).read_bytes()
        assert len(data) == row['bytes'] and hashlib.sha256(data).hexdigest() == row['sha256']
    prefix = ['powershell.exe', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-File', str(entry/'scripts/run.ps1')]
    calls = []
    def cli(*args):
        p = subprocess.run([*prefix, *map(str,args)], capture_output=True, timeout=120,
                           creationflags=subprocess.CREATE_NO_WINDOW)
        result = json.loads(p.stdout)
        row = {'args': list(map(str,args)), 'exit_code': p.returncode, 'result': result,
               'stderr': p.stderr.decode('utf-8',errors='replace')}
        calls.append(row)
        (evidence/f'{len(calls):02}.json').write_text(json.dumps(row,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        assert p.returncode == 0 and result['ok'], row
        print(json.dumps({'call':len(calls),'command':result['command'],'status':result['status']}),flush=True)
        return result
    version = cli('version')
    cli('doctor')
    capabilities = cli('capabilities')
    cli('schema','show')
    cli('gpu','inspect')
    cli('model-pack','list')
    cli('voice','list','--language','zh')
    cli('capture','devices')
    project = ROOT/'workspace/implementation-skill-20261025-r1'
    assert not project.exists()
    cli('project','init',project)
    plan = cli('capture','record','--project',project,'--kind','window','--window-title','explicit-plan-only-window',
               '--duration-seconds','1','--asset-id','plan-only','--dry-run')
    assert plan['status'] == 'planned' and not (project/'assets/captures').exists()
    cli('validate','--project',project)
    caps = capabilities['data'].get('capabilities',{})
    assert caps['native_capture']['status'] == 'implemented_with_limits' and len(caps) == 72
    report = {'status':'passed','commands':len(calls),'release':manifest['release'],'cli_version':manifest['cli_version'],
              'manifest_sha256':manifest['manifest_sha256'],'skill_count':1,'module_count':17,
              'discovery':str(entry),'installed_directory':runtime['installed_directory'],
              'source_fallback':False,'actual_new_capture_started':False,'new_inferences':0,
              'capability_declarations':len(caps),'version_response':version['data']}
    (evidence/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({'status':'passed','commands':len(calls),'release':manifest['release']}),flush=True)


if __name__ == '__main__':
    main()
