"""Pin one unified Skill only after immutable source/install byte verification."""
from pathlib import Path
import hashlib,json,re
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'docs/validation/evidence/native-hlg-black-20261028-r1'
def load(p):return json.loads(Path(p).read_bytes())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,s):Path(p).write_text(s,encoding='utf8',newline='\n')
out=BASE/'skill-pin-r1';out.mkdir(exist_ok=False);(out/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
install=load(BASE/'installation-final-r1/verification.json');test=load(BASE/'source-r3/verification.json')
assert install['status']=='installed-and-byte-verified' and install['cli_version']=='0.1.47'
pins={p.name:sha(p) for p in (ROOT/'product/src/ai_ad_editor').glob('*.py')}
assert test['status']=='passed' and test['tests']==21 and test['failures']==test['errors']==test['skipped']==0
assert pins==test['product_files']=={p.name:sha(p) for p in (Path(install['installed'])/'site/ai_ad_editor').glob('*.py')}
folder=ROOT/'skills/agent-ffmpeg-local-editor'
for name in ('SKILL.md','references/runtime.md'):
 p=folder/name;write(p,p.read_text('utf8').replace('v0.1.0-alpha.4-local.44','v0.1.0-alpha.4-local.45').replace('CLI `0.1.46`','CLI `0.1.47`').replace('CLI 0.1.46','CLI 0.1.47'))
p=folder/'SKILL.md';s=p.read_text('utf8');needle='For PQ/HLG HDR media and client SDR viewing, read';assert needle in s
write(p,s.replace(needle,'For declared nonzero HLG display black and complete signal JSON in CLI, read\n[HLG black level](references/hlg-black-level.md). Never infer monitor black,\npeak or gamma; output below the target black must reject or explicitly clip.\n'+needle,1))
write(folder/'references/hlg-black-level.md','''# Explicit HLG display black / CLI0.1.47

Use the pinned launcher; inspect `native_hlg_black_level`. Complete workflow:
`docs/product/HLG_BLACK_LEVEL.md` in the small kit. The ITU-R BT.2100-3 Table5
black-lift extension is CPU Float32 color math; supported editing operators
still use the separately selected native OpenCL GPU. No monitor is probed.

1. Confirm the actual code-value meaning with the client. Explicit source:

```json
{"primaries":"bt2020","transfer":"hlg-bt2100","reference_white_nits":203,
 "display_peak_nits":1000,"system_gamma":1.2,"display_black_nits":0.005}
```

2. Declare linear working RGB with `reference_white_nits:203`, and an explicit
   output signal (PQ, HLG or supported relative output with declared nits).
   Use `settings.pixel_pipeline.engine:"float32-native-v1"`; source declarations
   are under `sources.<asset_id>.source_signal`. Do not invent physical values.
3. `display_black_nits` accepts finite numbers0..10 only on HLG, with beta<1.
   Omission retains the original ideal-zero path. Explicit zero preserves its
   numeric bytes, while recording that the user actually declared zero.
4. For raw native-clock frames, save complete source and working JSON objects:

```text
surface export --project PROJECT --asset-id ASSET --output renders/surface
  --source-signal-json source.json --working-signal-json working.json
  --stop-frame 1
```

   Do not mix complete JSON with individual source/working flags. HDR requires
   explicit reference-white nits on both sides. Input and output domains default
   to reject. To authorize output clipping use `--hdr-range-policy clip`;
   input clipping uses `--hdr-input-range-policy clip`. Recipes embed the parsed
   descriptors and policies; external descriptor files are not live dependencies.
5. In timeline rendering choose `pixel_pipeline.range_policy:"reject"` or
   explicit `"clip"`. Below-black output and rounded white-endpoint overflow
   follow this policy and are counted. No hidden epsilon snapping is performed.
6. Validate, dry-run, render, inspect actual VUI and the HLG black-level receipt,
   preview with an explicit SDR mapping, then package/import/replay. Raw bundles
   preserve alpha bits and original PTS/durations; they contain no encoded audio.
7. Show C57 actual PNG/MP4/GIF and signals to clients. Its intentionally raised
   0.5-nit black is a numeric diagnostic, not calibrated monitor acceptance.
   Left is an independent ideal-zero/no-glow control; right is actual HLG black
   conversion plus GPU Bloom. Full ACES, dynamic HDR, measured display matching,
   subblack PLUGE signals and natural-image artistic validation remain open.
''')
for name in ('hdr-display.md','icc-profiles.md'):
 p=folder/'references'/name;write(p,p.read_text('utf8')+'\nCLI0.1.47 adds [complete HDR/HLG black signal JSON for surface export](hlg-black-level.md), with explicit nits and reject/clip policies. Existing individual RGB/ICC flags remain supported.\n')
p=folder/'scripts/run.py';s=p.read_text('utf8')
s,n=re.subn(r"^MANIFEST = '[^']+'$",'MANIFEST = '+repr(install['manifest_sha256']),s,count=1,flags=re.M);assert n==1
s,n=re.subn(r"^RELEASE = '[^']+'$","RELEASE = 'v0.1.0-alpha.4-local.45'",s,count=1,flags=re.M);assert n==1;write(p,s)
p=ROOT/'agent-ffmpeg-local-install-manifest.json';m=load(p);m.update(release='v0.1.0-alpha.4-local.45',cli_version='0.1.47',manifest_sha256=install['manifest_sha256'])
m['skills'][0]['skill_md_sha256']=sha(folder/'SKILL.md')
m['files']=[dict(path=p.relative_to(ROOT).as_posix(),bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(folder.rglob('*')) if p.is_file()]
assert len(m['files'])==86 and sum(Path(r['path']).name=='SKILL.md' for r in m['files'])==1
write(p,json.dumps(m,ensure_ascii=False,indent=2)+'\n')
report=dict(status='candidate-pinned-for-installed-acceptance',product_files=len(pins),skill_files=86,public_entries=1,modules=17,source_tests=21,installed_acceptance_required=True,source_fallback=False,namespace_manifest_sha256=sha(p))
write(out/'verification.json',json.dumps(report,indent=2)+'\n');print(json.dumps(report))
