"""Pin the single public Skill to the byte-verified native white-point release."""
from pathlib import Path
import hashlib,json,re
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'docs/validation/evidence/native-chromatic-20261028-r1'
def load(p):return json.loads(Path(p).read_bytes())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,s):Path(p).write_text(s,encoding='utf8',newline='\n')
out=BASE/'skill-pin-r1';out.mkdir(exist_ok=False);(out/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
install=load(BASE/'installation-final-r1/verification.json');test=load(BASE/'source-r3/verification.json')
assert install['status']=='installed-and-byte-verified' and install['cli_version']=='0.1.45'
pins={p.name:sha(p) for p in (ROOT/'product/src/ai_ad_editor').glob('*.py')}
assert test['status']=='passed' and test['tests']==20 and test['failures']==test['errors']==test['skipped']==0
assert pins==test['product_files']=={p.name:sha(p) for p in (Path(install['installed'])/'site/ai_ad_editor').glob('*.py')}
folder=ROOT/'skills/agent-ffmpeg-local-editor';p=folder/'SKILL.md';s=p.read_text('utf8')
s=s.replace('v0.1.0-alpha.4-local.42','v0.1.0-alpha.4-local.43').replace('CLI `0.1.44`','CLI `0.1.45`')
s=s.replace('explicit PQ/HLG HDR, verified HDR10 static metadata and SDR previews','explicit PQ/HLG HDR, verified HDR10 static metadata, D50/D60 white adaptation and SDR previews')
needle='For repeated GPU generation with the same prompt, read';assert needle in s
s=s.replace(needle,'For ProPhoto RGB D50, linear AP1 D60 or explicit RGB reference whites, read\n'
    '[chromatic adaptation](references/chromatic-adaptation.md). Declare source and\n'
    'working signals; use actual D65 viewing copies for client selection. This\n'
    'reference-white conversion does not infer a physical illuminant or ICC profile,\n'
    'and linear AP1 alone is not a complete ACES output transform.\n'+needle,1);write(p,s)
p=folder/'references/runtime.md';write(p,p.read_text('utf8').replace('v0.1.0-alpha.4-local.42','v0.1.0-alpha.4-local.43').replace('CLI 0.1.44','CLI 0.1.45'))
p=folder/'references/chromatic-adaptation.md';assert not p.exists()
write(p,'''# Explicit reference whites / ProPhoto D50 / AP1 D60

Use the pinned installed launcher and inspect `native_chromatic_adaptation`.
The packaged `docs/product/CHROMATIC_ADAPTATION.md` contains full JSON, commands
and the actual C55 diagnostic media/package workflow.

- Declare the source interpretation; never label ordinary sRGB imagery as
  ProPhoto just to obtain a look. `prophoto-rgb` primaries default to D50 and
  `prophoto-rgb` transfer uses a linear toe plus signed1.8 extension.
- `aces-ap1` defaults to D60. Choose `linear` for the edit working signal;
  camera IDT, scene/display rendering and ACES RRT/ODT/DRT require separate work.
- Optional `white_xy:[x,y]` belongs inside source/working/effect RGB signal
  declarations. It is CIE1931 reference-white chromaticity, not Kelvin, exposure
  or automatic white balance. Conversion uses Bradford in linear XYZ.
- Preserve explicit `reference_white_nits` on both ends when absolute units
  matter. Reference-white chromaticity and white luminance are separate fields.
- Final BT.709/PQ/HLG video delivery remains D65; use the selected output
  transfer and matching tags. PQ/HLG encoded signals also require BT.2020.
- Use `surface export --source-primaries prophoto-rgb --source-transfer
  prophoto-rgb --working-primaries aces-ap1 --working-transfer linear
  --working-white-xy 0.32168 0.33767` for a native-clock Float32 intermediate.
  Source overrides use `--source-white-xy X Y`; inspect the returned manifest.
- Validate, inspect dry-run, render, preview actual D65 PNG/MP4/GIF and export
  an editable package. CPU performs color conversion; supported geometry and
  Bloom/Halation can use the configured native OpenCL GPU. The glow threshold
  uses luminance coefficients for the declared working reference white.
- Show C55's actual preview together with `signals.json`, original source and
  the clearly labelled independent no-adaptation control. That control omits
  Bloom and is a mathematical diagnostic, not another engine output or a
  natural image quality/HDR-monitor assessment. Preserve this distinction.
- Explicit D65 equivalents keep alpha and identical-signal RGB bits. Other
  conversions preserve alpha, signed/above-one RGB until a separately declared
  output boundary. There is no implicit perceptual gamut mapping or ICC parsing.
''')
p=folder/'references/hdr-display.md';write(p,p.read_text('utf8')+'\nCLI0.1.45 adds explicit Bradford reference-white conversion,ProPhoto D50 and\nlinear AP1 D60. Read [chromatic adaptation](chromatic-adaptation.md). HDR encoded\nBT.2100/output white remains D65; chromaticity is separate from reference nits.\n')
p=folder/'scripts/run.py';s=p.read_text('utf8')
s,n=re.subn(r"^MANIFEST = '[^']+'$",'MANIFEST = '+repr(install['manifest_sha256']),s,count=1,flags=re.M);assert n==1
s,n=re.subn(r"^RELEASE = '[^']+'$","RELEASE = 'v0.1.0-alpha.4-local.43'",s,count=1,flags=re.M);assert n==1;write(p,s)
p=ROOT/'agent-ffmpeg-local-install-manifest.json';m=load(p);m.update(release='v0.1.0-alpha.4-local.43',cli_version='0.1.45',manifest_sha256=install['manifest_sha256'])
m['skills'][0]['skill_md_sha256']=sha(folder/'SKILL.md')
m['files']=[dict(path=p.relative_to(ROOT).as_posix(),bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(folder.rglob('*')) if p.is_file()]
assert len(m['files'])==84 and sum(Path(r['path']).name=='SKILL.md' for r in m['files'])==1
write(p,json.dumps(m,ensure_ascii=False,indent=2)+'\n')
report=dict(status='candidate-pinned-for-installed-acceptance',product_files=len(pins),skill_files=84,public_entries=1,modules=17,
    source_tests=20,installed_acceptance_required=True,source_fallback=False,namespace_manifest_sha256=sha(p))
write(out/'verification.json',json.dumps(report,indent=2)+'\n');print(json.dumps(report))
