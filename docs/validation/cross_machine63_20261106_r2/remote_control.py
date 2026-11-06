"""Serialize native Windows-MCP calls; never print or publish transport secrets."""
import argparse
import base64
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import runpy
import sys
import time
import uuid


ROOT = Path(__file__).resolve().parent
REMOTE = 'C:/dev/agent-editor-kit-validation-20261106-r2'
CLIENT = Path('C:/Users/carzy/.codex/skills/remote-4090/scripts/windows_mcp.py')
MARKER = 'AEK_BASELINE_JSON_BASE64:'


def load(path):
    return json.loads(Path(path).read_bytes())


def encoded(value):
    return base64.b64encode(value).decode('ascii')


def save(path, value):
    with Path(path).open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(value, stream, ensure_ascii=False, indent=2)
        stream.write('\n')


def owner_prelude(owner):
    return """$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
$OutputEncoding = [Console]::OutputEncoding
$AekRoot = '%s'
if (-not (Test-Path -LiteralPath $AekRoot -PathType Container)) { throw 'Owned test root missing' }
$AekItem = Get-Item -LiteralPath $AekRoot -Force
if ($AekItem.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Unexpected reparse root' }
$AekOwner = Get-Content -LiteralPath (Join-Path $AekRoot 'ownership.json') -Raw -Encoding utf8 | ConvertFrom-Json
if ($AekOwner.owner_id -ne '%s') { throw 'Test directory belongs to another run' }
""" % (REMOTE, owner['owner_id'])


def emit_ps():
    return """
$AekJson = $AekResult | ConvertTo-Json -Depth 60 -Compress
'%s' + [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($AekJson))
""" % MARKER


def start_command():
    assert not (ROOT / 'start-intent.json').exists(), 'Inspect existing run; never repeat a start blindly'
    owner = dict(owner_id=str(uuid.uuid4()), remote_root=REMOTE,
                 native_only=True, cli_version='0.1.63',
                 created_at_utc=dt.datetime.now(dt.timezone.utc).isoformat())
    save(ROOT / 'start-intent.json', owner)
    files = {'ownership.json': (json.dumps(owner, ensure_ascii=False)+'\n').encode('utf-8')}
    transfer_bytes=(ROOT/'transfer.json').read_bytes()
    transfer=json.loads(transfer_bytes)
    helper=next(row for row in transfer['files'] if row['name']=='remote_baseline.py')
    command = """$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
$OutputEncoding = [Console]::OutputEncoding
$AekRoot = '%s'
if ($env:COMPUTERNAME -ne 'DESKTOP-TE44HE1') { throw 'Unexpected native host' }
$AekParent = Get-Item -LiteralPath 'C:/dev' -Force
if ($AekParent.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Unexpected parent reparse point' }
if (Test-Path -LiteralPath $AekRoot) { throw 'Preserve existing directory; inspect it first' }
$null = New-Item -ItemType Directory -Path $AekRoot
""" % REMOTE
    for name, data in files.items():
        command += "[IO.File]::WriteAllBytes((Join-Path $AekRoot '%s'), [Convert]::FromBase64String('%s'))\n" % (name, encoded(data))
    command += "$AekWeb = New-Object Net.WebClient\n$AekWeb.Proxy = $null\ntry {\n"
    downloads=[('transfer.json',hashlib.sha256(transfer_bytes).hexdigest()),('remote_baseline.py',helper['sha256'])]
    for name,pin in downloads:
        command += "$AekWeb.DownloadFile('%s/%s',(Join-Path $AekRoot '%s'))\n" % (transfer['base_url'],name,name)
    command += "} finally { $AekWeb.Dispose() }\n$AekHasher=[Security.Cryptography.SHA256]::Create()\ntry {\n"
    for name,pin in downloads:
        command += "if (([BitConverter]::ToString($AekHasher.ComputeHash([IO.File]::ReadAllBytes((Join-Path $AekRoot '%s'))))).Replace('-','').ToLowerInvariant() -ne '%s') { throw 'Bootstrap SHA256 mismatch' }\n" % (name,pin)
    command += "} finally { $AekHasher.Dispose() }\n"
    command += """$AekPython = [IO.Path]::GetFullPath('C:/dev/comfyUI/python_embeded/python.exe')
$AekScript = Join-Path $AekRoot 'remote_baseline.py'
$AekProcess = Start-Process -FilePath $AekPython -ArgumentList @('-I','-B','-u','-X','utf8',$AekScript) -WorkingDirectory $AekRoot -WindowStyle Hidden -RedirectStandardOutput (Join-Path $AekRoot 'job.stdout') -RedirectStandardError (Join-Path $AekRoot 'job.stderr') -PassThru
$AekProcess.Refresh()
$AekResult = [ordered]@{pid=$AekProcess.Id; creation_filetime=$AekProcess.StartTime.ToUniversalTime().ToFileTimeUtc(); executable=$AekPython; script=$AekScript; root=$AekRoot; owner_id='%s'}
$AekLaunchJson = ($AekResult | ConvertTo-Json -Depth 10) + "`n"
[IO.File]::WriteAllText((Join-Path $AekRoot 'launch.json'),$AekLaunchJson,(New-Object Text.UTF8Encoding($false)))
""" % owner['owner_id']
    return command + emit_ps()


def status_command():
    owner = load(ROOT / 'start-intent.json')
    return owner_prelude(owner) + r"""
$AekLaunchPath = Join-Path $AekRoot 'launch.json'
$AekLaunch = if (Test-Path -LiteralPath $AekLaunchPath) { Get-Content -LiteralPath $AekLaunchPath -Raw -Encoding utf8 | ConvertFrom-Json } else { $null }
$AekProcess = if ($AekLaunch) { Get-CimInstance Win32_Process -Filter ('ProcessId=' + [int]$AekLaunch.pid) } else { $null }
$AekLive = $false
if ($AekProcess) {
    $AekNativeProcess = Get-Process -Id ([int]$AekLaunch.pid) -ErrorAction SilentlyContinue
    if ($AekNativeProcess) {
        $AekActualCreation = $AekNativeProcess.StartTime.ToUniversalTime().ToFileTimeUtc()
        $AekLive = ($AekActualCreation -eq $AekLaunch.creation_filetime -and [IO.Path]::GetFullPath($AekProcess.ExecutablePath) -eq [IO.Path]::GetFullPath($AekLaunch.executable) -and $AekProcess.CommandLine.Contains('remote_baseline.py'))
    }
}
$AekStatePath = Join-Path $AekRoot 'state.json'
$AekState = if (Test-Path -LiteralPath $AekStatePath) { Get-Content -LiteralPath $AekStatePath -Raw -Encoding utf8 | ConvertFrom-Json } else { $null }
$AekResult = [ordered]@{observed_at_utc=[DateTime]::UtcNow.ToString('o'); launch=$AekLaunch; actual_process_live=$AekLive; state=$AekState; downloads_verified=(Test-Path -LiteralPath (Join-Path $AekRoot 'downloads-verified.json')); verification_present=(Test-Path -LiteralPath (Join-Path $AekRoot 'verification.json')); failure_present=(Test-Path -LiteralPath (Join-Path $AekRoot 'failure.json'))}
""" + emit_ps()


def fetch_command():
    owner = load(ROOT / 'start-intent.json')
    relative = ['verification.json','failure.json','state.json','launch.json','registration.json',
        'downloads-verified.json','job.stdout','job.stderr','offline-install.stdout','offline-install.stderr',
        'isolated-registration.stdout','isolated-registration.stderr',
        'actual-cross-host-replay.stdout','actual-cross-host-replay.stderr',
        'actual-case/verification.json','actual-case/calls.json',
        'actual-case/imported/renders/cross-host.mp4']
    array = ','.join("'%s'" % name for name in relative)
    return owner_prelude(owner) + r"""
$AekRecords = @()
foreach ($AekRelative in @(%s)) {
    $AekPath = Join-Path $AekRoot $AekRelative
    if (Test-Path -LiteralPath $AekPath -PathType Leaf) {
        $AekFile = Get-Item -LiteralPath $AekPath -Force
        if ($AekFile.Length -gt 2097152) { throw 'Evidence file exceeds explicit return budget' }
        $AekRecords += [ordered]@{path=$AekRelative; bytes=$AekFile.Length; base64=[Convert]::ToBase64String([IO.File]::ReadAllBytes($AekPath))}
    }
}
$AekLogRoot = Join-Path $AekRoot 'actual-case/logs'
if (Test-Path -LiteralPath $AekLogRoot -PathType Container) {
    foreach ($AekLog in @(Get-ChildItem -LiteralPath $AekLogRoot -File)) {
        if ($AekLog.Name -notmatch '^[a-zA-Z0-9_-]+\.(stdout|stderr)$' -or $AekLog.Length -gt 2097152) { throw 'Unexpected case log' }
        $AekRecords += [ordered]@{path=('actual-case/logs/' + $AekLog.Name); bytes=$AekLog.Length; base64=[Convert]::ToBase64String([IO.File]::ReadAllBytes($AekLog.FullName))}
    }
}
$AekResult = [ordered]@{files=$AekRecords; observed_at_utc=[DateTime]::UtcNow.ToString('o')}
""" % array + emit_ps()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=('start', 'status', 'fetch'))
    args = parser.parse_args()
    assert os.name == 'nt' and sys.dont_write_bytecode and sys.prefix == sys.base_prefix
    ns = runpy.run_path(str(CLIENT), run_name='aek_cross_machine_client')
    config = ns['read_json'](CLIENT.parents[1] / 'device.json')
    client = ns['MCPClient'](config, timeout=55)
    observation = ROOT / 'remote-observations' / (args.action + '-' + str(time.time_ns()))
    observation.mkdir(parents=True, exist_ok=False)
    with ns['device_lock'](Path(config['controller_root']), config['name']):
        try:
            client.initialize(config['name'])
            status = client.rpc('tools/call', {'name':'ControlStatus','arguments':{}})
            ns['store_result'](status, observation, 'control-status')
            assert ns['control_state'](status)['state'] in ('ready','ai'), 'Remote user or control session is busy'
            command = {'start':start_command,'status':status_command,'fetch':fetch_command}[args.action]()
            assert len(base64.b64encode(command.encode('utf-16-le'))) <= 10000, 'Native bootstrap command exceeds its transport budget'
            result = client.rpc('tools/call', {'name':'PowerShell','arguments':{'command':command,'timeout':45}})
            ns['store_result'](result, observation, 'response')
            error = ns['tool_error'](result)
            if error:
                error=client.scrub(error)
                if (ROOT/'transfer.json').is_file():
                    error=error.replace(load(ROOT/'transfer.json')['base_url'],'[PRIVATE_LAN_TRANSFER]')
                raise RuntimeError(error)
            matches = re.findall(re.escape(MARKER) + r'([A-Za-z0-9+/=]+)', ns['text_of'](result))
            assert len(matches) == 1, 'No unambiguous native result; inspect existing run before any retry'
            value = json.loads(base64.b64decode(matches[0], validate=True))
            save(observation / 'parsed.json', value)
            if args.action == 'fetch':
                destination = observation / 'files'
                destination.mkdir()
                for row in value['files']:
                    relative = Path(row['path'])
                    assert not relative.is_absolute() and '..' not in relative.parts and ':' not in str(relative)
                    data = base64.b64decode(row['base64'], validate=True)
                    assert len(data) == row['bytes'] <= 2*1024**2
                    target = destination / relative
                    target.parent.mkdir(parents=True, exist_ok=True)
                    with target.open('xb') as stream:
                        stream.write(data)
                print(json.dumps(dict(action='fetch', directory=str(destination), files=len(value['files'])),ensure_ascii=False))
            else:
                if args.action == 'start':
                    save(ROOT / 'launch.json', value)
                print(json.dumps(value,ensure_ascii=False))
        finally:
            client.close()


if __name__ == '__main__':
    main()
