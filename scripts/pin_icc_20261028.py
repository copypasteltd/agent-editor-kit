"""Pin the unified installed Skill to the verified native ICC release."""
from pathlib import Path
import hashlib,json,re
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'docs/validation/evidence/native-icc-20261028-r1'
def load(p):return json.loads(Path(p).read_bytes())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,s):Path(p).write_text(s,encoding='utf8',newline='\n')
out=BASE/'skill-pin-r1';out.mkdir(exist_ok=False);(out/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
install=load(BASE/'installation-final-r1/verification.json');test=load(BASE/'source-r3/verification.json')
assert install['status']=='installed-and-byte-verified' and install['cli_version']=='0.1.46'
pins={p.name:sha(p) for p in (ROOT/'product/src/ai_ad_editor').glob('*.py')}
assert test['status']=='passed' and test['tests']==26 and test['failures']==test['errors']==test['skipped']==0
assert pins==test['product_files']=={p.name:sha(p) for p in (Path(install['installed'])/'site/ai_ad_editor').glob('*.py')}
folder=ROOT/'skills/agent-ffmpeg-local-editor';p=folder/'SKILL.md';s=p.read_text('utf8')
s=s.replace('v0.1.0-alpha.4-local.43','v0.1.0-alpha.4-local.44').replace('CLI `0.1.45`','CLI `0.1.46`')
s=s.replace('D50/D60 white adaptation and SDR previews','D50/D60 white adaptation, native RGB ICC profiles and SDR previews')
needle='For ProPhoto RGB D50, linear AP1 D60 or explicit RGB reference whites, read';assert needle in s
s=s.replace(needle,'For explicit project-local RGB ICC v2/v4 source profiles, read\n'
    '[ICC color management](references/icc-profiles.md). Inspect the actual file,\n'
    'lock its SHA-256 and choose rendering intent/BPC; native LittleCMS converts\n'
    'directly to linear working RGB. This also supports native-clock surface\n'
    'export, actual previews and portable profile dependencies. Never substitute\n'
    'an arbitrary profile for a creative look or infer embedded metadata.\n'+needle,1);write(p,s)
p=folder/'references/runtime.md';write(p,p.read_text('utf8').replace('v0.1.0-alpha.4-local.43','v0.1.0-alpha.4-local.44').replace('CLI 0.1.45','CLI 0.1.46'))
p=folder/'references/icc-profiles.md';assert not p.exists()
write(p,'''# Explicit native ICC source color management

Use the pinned installed launcher and inspect `native_icc_source_profiles`.
The packaged `docs/product/ICC_PROFILES.md` provides full JSON/commands and C56.
The native Windows x64 LittleCMS 2.19.1 DLL, source revision, SHA and MIT license
are included and verified. Color management runs on CPU; supported editing
operators use the separately selected native OpenCL GPU.

1. Confirm what the local source code values actually represent. Obtain its
   RGB ICC v2/v4 file and rights evidence; place it inside the project. Do not
   invent a camera profile or treat a profile as a creative LUT.
2. Run `surface inspect-profile --project PROJECT --input assets/source.icc`.
   This checks header/tag budgets, real native parsing and actual SHA without
   editing author data. Choose a supported rendering intent explicitly.
3. Set `settings.pixel_pipeline.engine:"float32-native-v1"` and source signal:

```json
{
  "icc_profile":"assets/source.icc",
  "sha256":"sha256:<actual 64 lowercase hex>",
  "intent":"relative-colorimetric",
  "black_point_compensation":false
}
```

4. Declare a linear RGB `working_signal` and explicit output signal. Native CMM
   converts directly to that working profile, including declared D50/D60 whites.
   The four intents are `perceptual`, `relative-colorimetric`, `saturation` and
   `absolute-colorimetric`; an intent missing from a table profile is rejected.
   Results can differ according to profile tables; matrix profiles need not
   produce different results for each intent. BPC is an explicit boolean.
5. For absolute light units/HDR, declare `reference_white_nits` on the ICC source
   and working/output signals. ICC white-point tags are chromaticity/media-white
   data, not a measurement of scene illumination or display peak luminance.
6. Validate, inspect dry-run, render and preview actual output. Read
   `delivery.pixel_pipeline.source_receipts.<asset_id>.ICC_transform`, including
   CMM version, profile bytes, intent, unit scaling and handle cleanup. Source
   RGB must be finite 0..1; working negative/superwhite RGB and alpha bits are
   preserved until a separately declared output boundary.
7. `surface export` accepts `--source-icc-profile assets/source.icc
   --source-icc-sha256 sha256:... --source-icc-intent relative-colorimetric`
   with `--working-primaries`, optional `--working-white-xy` and linear transfer.
   Optional BPC uses `--source-icc-black-point-compensation`. Explicit nit units
   use `--source-reference-white-nits` and `--working-reference-white-nits`.
   Do not mix ICC flags with `--source-primaries/transfer/white-xy` declarations.
8. Export a `package` and test its import/replay. The exact profile bytes are
   included; profiles outside `assets/` become content-addressed package paths.
   Author data is unchanged. Register rights separately; packaging grants none.

Show C56's actual PNG/MP4/GIF and its profile/settings before client selection.
Its left comparison is an independent no-adaptation/no-Bloom mathematical
control; right is the actual ICC/OpenCL engine output. It is a numeric diagnostic,
not a natural-image artistic assessment. No continuous human playback/listening
or HDR-monitor acceptance is claimed. Scope: RGB matrix/shaper and table source
profiles, not CMYK/device links, arbitrary output ICC, softproofing, embedded
profile auto-detection, ICC v5 or complete ACES rendering. The profile is limited
to 16MiB/4096 tags; surface budgets are estimates, not total process peak RSS.
''')
p=folder/'references/chromatic-adaptation.md';write(p,p.read_text('utf8')+'\nFor actual explicit ICC source files use the separate [native ICC path](icc-profiles.md), added in CLI0.1.46. The mathematical RGB/white conversion above still performs no profile inference.\n')
p=folder/'references/hdr-display.md';write(p,p.read_text('utf8')+'\nCLI0.1.46 adds [explicit native RGB ICC source profiles](icc-profiles.md). HDR projects require authored reference-white nits on every source, including ICC inputs; ICC tags do not measure luminance.\n')
p=folder/'scripts/run.py';s=p.read_text('utf8')
s,n=re.subn(r"^MANIFEST = '[^']+'$",'MANIFEST = '+repr(install['manifest_sha256']),s,count=1,flags=re.M);assert n==1
s,n=re.subn(r"^RELEASE = '[^']+'$","RELEASE = 'v0.1.0-alpha.4-local.44'",s,count=1,flags=re.M);assert n==1;write(p,s)
p=ROOT/'agent-ffmpeg-local-install-manifest.json';m=load(p);m.update(release='v0.1.0-alpha.4-local.44',cli_version='0.1.46',manifest_sha256=install['manifest_sha256'])
m['skills'][0]['skill_md_sha256']=sha(folder/'SKILL.md')
m['files']=[dict(path=p.relative_to(ROOT).as_posix(),bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(folder.rglob('*')) if p.is_file()]
assert len(m['files'])==85 and sum(Path(r['path']).name=='SKILL.md' for r in m['files'])==1
write(p,json.dumps(m,ensure_ascii=False,indent=2)+'\n')
report=dict(status='candidate-pinned-for-installed-acceptance',product_files=len(pins),skill_files=85,public_entries=1,modules=17,
    source_tests=26,installed_acceptance_required=True,source_fallback=False,namespace_manifest_sha256=sha(p))
write(out/'verification.json',json.dumps(report,indent=2)+'\n');print(json.dumps(report))
