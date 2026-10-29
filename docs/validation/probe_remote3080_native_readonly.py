"""Read-only second-host inventory; no install, model execution or desktop input."""
import base64,hashlib,json,re,runpy
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
SKILL=Path('C:/Users/carzy/.codex/skills/remote-3080')
client_module=runpy.run_path(str(SKILL/'scripts/windows_mcp.py'))
config=client_module['read_json'](SKILL/'device.json')
private=ROOT/'local/agent-ffmpeg/remote3080-readonly-r2';private.mkdir(exist_ok=False)
out=ROOT/'docs/validation/evidence/remote3080-native-20261029-r2';out.mkdir(exist_ok=False)
(out/'executed-runner.py').write_bytes(Path(__file__).read_bytes())
code="""import importlib.metadata as m,importlib.util,json,platform,struct,sys
packages={}
for name in ['numpy','Pillow','jsonschema','opencv-python','torch','torchaudio','transformers','onnxruntime','onnxruntime-gpu']:
 try:packages[name]=m.version(name)
 except m.PackageNotFoundError:packages[name]=None
modules={name:importlib.util.find_spec(name) is not None for name in ['numpy','PIL','jsonschema','cv2','torch','onnxruntime']}
print(json.dumps(dict(version=list(sys.version_info[:3]),bits=struct.calcsize('P')*8,machine=platform.machine(),packages=packages,modules=modules)))
"""
encoded=base64.b64encode(code.encode()).decode()
command=r"""$ErrorActionPreference='Stop'
$os=Get-CimInstance Win32_OperatingSystem
$machine=Get-CimInstance Win32_ComputerSystem
$python='C:\dev\comfyUI\python_embeded\python.exe'
$pythonCode="exec(__import__('base64').b64decode('ENCODED'))"
$runtime=(& $python -I -B -c $pythonCode | ConvertFrom-Json)
if ($LASTEXITCODE -ne 0) {throw 'Embedded Python metadata probe failed'}
$gpu=@(& nvidia-smi --query-gpu=name,memory.total,memory.used,utilization.gpu,driver_version --format=csv,noheader,nounits)
if ($LASTEXITCODE -ne 0) {throw 'GPU inventory probe failed'}
$ffmpeg=@(Get-Command ffmpeg.exe,ffprobe.exe -ErrorAction SilentlyContinue | Select-Object Name,Source)
$drives=@(Get-PSDrive -PSProvider FileSystem | Select-Object Name,Free,Used)
$data=[ordered]@{host=$env:COMPUTERNAME;os=$os.Caption;os_version=$os.Version;manufacturer=$machine.Manufacturer;model=$machine.Model;runtime=$runtime;gpu=$gpu;ffmpeg=$ffmpeg;drives=$drives}
$json=$data | ConvertTo-Json -Depth 8 -Compress
'AGENT_SECOND_HOST_B64:'+([Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($json)))
""".replace('ENCODED',encoded)
(private/'request.ps1').write_text(command,encoding='utf-8')
client=client_module['MCPClient'](config,timeout=30)
try:
 with client_module['device_lock'](Path(config['controller_root']),config['name']):
  client.initialize(config['name'])
  schemas=client.list_tools();schema=next(x for x in schemas if x['name']=='PowerShell')
  assert 'command' in schema['inputSchema']['properties']
  reply=client.rpc('tools/call',dict(name='PowerShell',arguments=dict(command=command,timeout=20)))
  (private/'response.json').write_text(client.scrub(json.dumps(reply,ensure_ascii=False,indent=2)),encoding='utf-8')
  assert not reply.get('isError'),client.scrub(client_module['text_of'](reply))
  match=re.search(r'AGENT_SECOND_HOST_B64:([A-Za-z0-9+/=]+)',client_module['text_of'](reply));assert match,'Missing structured inventory'
  data=json.loads(base64.b64decode(match[1]).decode('utf-8-sig'))
finally:client.close()
assert str(data['host']).casefold()==str(config['hostname']).casefold()
assert data['runtime']['version'][:2]==[3,13] and data['runtime']['bits']==64
assert any('RTX 3080' in row for row in data['gpu'])
# Do not publish the host/user identity, private desktop or credentials.
public={key:data[key] for key in ['os','os_version','manufacturer','model','runtime','gpu','drives']}
public['ffmpeg_on_PATH']=[row['Name'] for row in data['ffmpeg']]
report=dict(status='read-only-inventory-completed',captured_utc=datetime.now(timezone.utc).isoformat(),
 device_alias='remote-RTX3080',identity_matched=True,inventory=public,
 system_default_python_315_previously_observed=True,cp313_embedded_metadata_compatible=True,
 native_installation_executed=False,clean_host_accepted=False,actual_CUDA_inference=False,
 explicit_remote_configuration_changes=False,explicit_remote_file_writes=False,
 remote_process_started_except_readonly_probes=False,
 desktop_input=False,browser_tabs_opened=0,private_desktop_published=False,
 source_cli='0.1.63',formal_skill_cli='0.1.59',full_goal_closed=False)
(out/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps(report,ensure_ascii=False),flush=True)
