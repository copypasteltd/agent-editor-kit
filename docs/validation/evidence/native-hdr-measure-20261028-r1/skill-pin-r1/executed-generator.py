"""Pin the one public Skill to verified native ICC-output release bytes."""
from pathlib import Path
import hashlib,json,re
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'docs/validation/evidence/native-hdr-measure-20261028-r1'
def load(p):return json.loads(Path(p).read_bytes())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,s):Path(p).write_text(s,encoding='utf8',newline='\n')
out=BASE/'skill-pin-r1';out.mkdir(exist_ok=False);(out/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
install=load(BASE/'installation-final-r1/verification.json');test=load(BASE/'source-r4/verification.json')
assert install['status']=='installed-and-byte-verified' and install['cli_version']=='0.1.49'
pins={p.name:sha(p) for p in (ROOT/'product/src/ai_ad_editor').glob('*.py')}
assert test['status']=='passed' and test['tests']==19 and test['failures']==test['errors']==test['skipped']==0
assert pins==test['product_files']=={p.name:sha(p) for p in (Path(install['installed'])/'site/ai_ad_editor').glob('*.py')}
folder=ROOT/'skills/agent-ffmpeg-local-editor'
for name in ('SKILL.md','references/runtime.md'):
 p=folder/name;write(p,p.read_text('utf8').replace('v0.1.0-alpha.4-local.46','v0.1.0-alpha.4-local.47').replace('CLI `0.1.48`','CLI `0.1.49`').replace('CLI 0.1.48','CLI 0.1.49'))
p=folder/'SKILL.md';s=p.read_text('utf8');needle='For actual RGB ICC output'
assert needle in s
write(p,s.replace(needle,'For all-frame HDR light metering and colour-clipping receipts, read\n[light measurement](references/hdr-measurement.md). Use actual native frames,\nexplicit nits and the full/partial scope flags; keep MaxRGB separate from CIE Y.\n'+needle,1))
write(folder/'references/hdr-measurement.md', (ROOT/'docs/product/HDR_MEASUREMENT.md').read_text('utf8'))
p=folder/'scripts/run.py';s=p.read_text('utf8')
s,n=re.subn(r"^MANIFEST = '[^']+'$",'MANIFEST = '+repr(install['manifest_sha256']),s,count=1,flags=re.M);assert n==1
s,n=re.subn(r"^RELEASE = '[^']+'$","RELEASE = 'v0.1.0-alpha.4-local.47'",s,count=1,flags=re.M);assert n==1;write(p,s)
p=ROOT/'agent-ffmpeg-local-install-manifest.json';m=load(p);m.update(release='v0.1.0-alpha.4-local.47',cli_version='0.1.49',manifest_sha256=install['manifest_sha256'])
m['skills'][0]['skill_md_sha256']=sha(folder/'SKILL.md')
m['files']=[dict(path=p.relative_to(ROOT).as_posix(),bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(folder.rglob('*')) if p.is_file()]
assert len(m['files'])==88 and sum(Path(r['path']).name=='SKILL.md' for r in m['files'])==1
write(p,json.dumps(m,ensure_ascii=False,indent=2)+'\n')
report=dict(status='candidate-pinned-for-installed-acceptance',product_files=len(pins),skill_files=88,public_entries=1,modules=17,source_tests=19,source_fallback=False,namespace_manifest_sha256=sha(p))
write(out/'verification.json',json.dumps(report,indent=2)+'\n');print(json.dumps(report))
