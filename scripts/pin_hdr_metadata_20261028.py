"""Pin and register one unified Skill against the verified native HDR10 build."""
from pathlib import Path
import hashlib,json,re
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'docs/validation/evidence/native-hdr-metadata-20261028-r1'
def load(p):return json.loads(Path(p).read_bytes())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,s):Path(p).write_text(s,encoding='utf8',newline='\n')
out=BASE/'skill-pin-r1';out.mkdir(exist_ok=False);(out/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
install=load(BASE/'installation-final-r1/verification.json');test=load(BASE/'source-r3/verification.json')
assert install['status']=='installed-and-byte-verified' and install['cli_version']=='0.1.44'
pins={p.name:sha(p) for p in (ROOT/'product/src/ai_ad_editor').glob('*.py')}
assert test['status']=='passed' and test['tests']==21 and test['failures']==test['errors']==test['skipped']==0
assert pins==test['product_files']=={p.name:sha(p) for p in (Path(install['installed'])/'site/ai_ad_editor').glob('*.py')}
folder=ROOT/'skills/agent-ffmpeg-local-editor';p=folder/'SKILL.md';s=p.read_text('utf8')
s=s.replace('v0.1.0-alpha.4-local.41','v0.1.0-alpha.4-local.42').replace('CLI `0.1.43`','CLI `0.1.44`')
s=s.replace('explicit PQ/HLG HDR and SDR previews','explicit PQ/HLG HDR, verified HDR10 static metadata and SDR previews')
needle='For repeated GPU generation with the same prompt, read';assert needle in s
s=s.replace(needle,'For HDR10 mastering-display/MaxCLL/MaxFALL declarations, read\n[HDR10 static metadata](references/hdr-metadata.md). Use exact xy/nit units,\nexplicit native PQ and libx265 ten-bit 4:2:0. Inspect decoded SEI verification\nbefore delivery; declarations are not measured peaks or monitor calibration.\n'+needle,1);write(p,s)
p=folder/'references/runtime.md';write(p,p.read_text('utf8').replace('v0.1.0-alpha.4-local.41','v0.1.0-alpha.4-local.42').replace('CLI 0.1.43','CLI 0.1.44'))
p=folder/'references/hdr-display.md';s=p.read_text('utf8')
s+='\nCLI0.1.44 adds optional actual HDR10 static SEI. Read [HDR10 metadata](hdr-metadata.md).\n';write(p,s)
p=folder/'references/hdr-metadata.md';assert not p.exists()
write(p,'''# HDR10 static declarations and actual encoded SEI

Read the packaged `docs/product/HDR_METADATA.md` for the complete JSON and workflow.
Use the installed launcher; inspect `capabilities.native_hdr10_static_metadata`.

- Author `settings.output.hdr10.mastering_display` with RGB/white xy and min/max
  nits, plus `content_light.max_cll_nits/max_fall_nits`. Zero light levels mean
  unknown. Values are declarations; do not fabricate measured peaks.
- Exact xy steps are 1/50000; luminance steps are 1/10000 nit. Invalid precision,
  triangle/white geometry and light relationships fail without silent rounding.
- Select explicit native PQ/BT.2020 NCL limited range, `libx265`, `yuv420p10le`
  and MKV or MP4. x265 encoding is CPU; configured OpenCL composition can use GPU.
- Validate and inspect render dry-run, render, then read
  `delivery.hdr10_static_metadata`. Verification decodes the first32 video packets
  and checks every observed frame's actual SEI plus stream tags before publish.
  It is prefix verification, not a claim about every frame in a long file.
- Present the original HDR master, declared values and separate actual SDR
  PNG/GIF/MP4. SDR viewing copies do not carry HDR declarations and cannot prove
  HDR-monitor appearance. Export an editable package for retained declarations.
- C54 uses actual registered Skill output and GPU composition; full-frame and
  PCM package replay are checked. Inspect failure receipts if SEI is missing.
- Dynamic HDR10+, Dolby Vision, content-peak analysis, ICC adaptation and monitor
  calibration remain outside this feature. Never describe static tags as those.
''')
p=folder/'scripts/run.py';s=p.read_text('utf8')
s,n=re.subn(r"^MANIFEST = '[^']+'$",'MANIFEST = '+repr(install['manifest_sha256']),s,count=1,flags=re.M);assert n==1
s,n=re.subn(r"^RELEASE = '[^']+'$","RELEASE = 'v0.1.0-alpha.4-local.42'",s,count=1,flags=re.M);assert n==1;write(p,s)
p=ROOT/'agent-ffmpeg-local-install-manifest.json';m=load(p);m.update(release='v0.1.0-alpha.4-local.42',cli_version='0.1.44',manifest_sha256=install['manifest_sha256'])
m['skills'][0]['skill_md_sha256']=sha(folder/'SKILL.md')
m['files']=[dict(path=p.relative_to(ROOT).as_posix(),bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(folder.rglob('*')) if p.is_file()]
assert len(m['files'])==83 and sum(Path(r['path']).name=='SKILL.md' for r in m['files'])==1
write(p,json.dumps(m,ensure_ascii=False,indent=2)+'\n')
report=dict(status='candidate-pinned-for-installed-acceptance',product_files=len(pins),skill_files=83,public_entries=1,modules=17,
    source_tests=21,installed_acceptance_required=True,source_fallback=False,namespace_manifest_sha256=sha(p))
write(out/'verification.json',json.dumps(report,indent=2)+'\n');print(json.dumps(report))
