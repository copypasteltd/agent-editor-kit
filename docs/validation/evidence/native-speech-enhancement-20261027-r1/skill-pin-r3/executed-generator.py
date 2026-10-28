"""Pin the one installed Skill to the byte-verified native enhancement release."""
from pathlib import Path
import hashlib,json,re
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'docs/validation/evidence/native-speech-enhancement-20261027-r1'
def load(p):return json.loads(Path(p).read_bytes())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,s):Path(p).write_text(s,encoding='utf8',newline='\n')
out=BASE/'skill-pin-r3';out.mkdir(exist_ok=False);(out/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
install=load(BASE/'installation-final-r3/verification.json');test=load(BASE/'source-enhancement-r6/verification.json')
assert install['status']=='installed-and-byte-verified' and install['cli_version']=='0.1.43'
pins={p.name:sha(p) for p in (ROOT/'product/src/ai_ad_editor').glob('*.py')}
assert test['status']=='passed' and test['tests']==33 and test['failures']==test['errors']==test['skipped']==0
assert pins==test['product_files']=={p.name:sha(p) for p in (Path(install['installed'])/'site/ai_ad_editor').glob('*.py')}
folder=ROOT/'skills/agent-ffmpeg-local-editor'
p=folder/'SKILL.md';s=p.read_text('utf8').replace('v0.1.0-alpha.4-local.40','v0.1.0-alpha.4-local.41').replace('CLI `0.1.42`','CLI `0.1.43`')
s=s.replace('native CUDA frame interpolation/slow motion and lip sync','native CUDA speech denoising, frame interpolation/slow motion and lip sync')
needle='- Separate drums, bass, other instruments and vocals: read';assert needle in s
if '[speech enhancement](references/speech-enhancement.md)' not in s:
    s=s.replace(needle,'- Enhance noisy local dialogue: read [speech enhancement](references/speech-enhancement.md).\n  Use the registered CUDA model, retain source and enhanced tracks, and show actual\n  audio comparisons. Native sample counts/mono-stereo remain explicit; model\n  state resets per overlapping segment. Listening quality requires review.\n'+needle,1)
write(p,s)
p=folder/'references/runtime.md';s=p.read_text('utf8').replace('v0.1.0-alpha.4-local.40','v0.1.0-alpha.4-local.41').replace('CLI 0.1.42','CLI 0.1.43');write(p,s)
p=folder/'scripts/run.py';s=p.read_text('utf8')
s,n=re.subn(r"^MANIFEST = '[^']+'$",'MANIFEST = '+repr(install['manifest_sha256']),s,count=1,flags=re.M);assert n==1
s,n=re.subn(r"^RELEASE = '[^']+'$","RELEASE = 'v0.1.0-alpha.4-local.41'",s,count=1,flags=re.M);assert n==1;write(p,s)
p=ROOT/'agent-ffmpeg-local-install-manifest.json';m=load(p)
m.update(release='v0.1.0-alpha.4-local.41',cli_version='0.1.43',manifest_sha256=install['manifest_sha256'])
m['skills'][0]['purpose_zh']='唯一入口：17内部模块、真实CUDA对白降噪/神经补帧/口型、GPU视频生成/会话、原生跟踪、HDR/Float32合成、500滤镜、语义检索、字幕配音与四轨分离'
m['skills'][0]['skill_md_sha256']=sha(folder/'SKILL.md')
m['files']=[dict(path=p.relative_to(ROOT).as_posix(),bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(folder.rglob('*')) if p.is_file()]
assert len(m['files'])==82 and sum(Path(r['path']).name=='SKILL.md' for r in m['files'])==1;write(p,json.dumps(m,ensure_ascii=False,indent=2)+'\n')
report=dict(status='candidate-pinned-for-installed-acceptance',product_files=len(pins),skill_files=82,public_entries=1,modules=17,
    source_tests=33,installed_acceptance_required=True,source_fallback=False,namespace_manifest_sha256=sha(p))
write(out/'verification.json',json.dumps(report,indent=2)+'\n');print(json.dumps(report))
