"""Pin the one public Skill to verified native ICC-output release bytes."""
from pathlib import Path
import hashlib,json,re
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'docs/validation/evidence/native-icc-output-20261028-r1'
def load(p):return json.loads(Path(p).read_bytes())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,s):Path(p).write_text(s,encoding='utf8',newline='\n')
out=BASE/'skill-pin-r1';out.mkdir(exist_ok=False);(out/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
install=load(BASE/'installation-final-r1/verification.json');test=load(BASE/'source-r2/verification.json')
assert install['status']=='installed-and-byte-verified' and install['cli_version']=='0.1.48'
pins={p.name:sha(p) for p in (ROOT/'product/src/ai_ad_editor').glob('*.py')}
assert test['status']=='passed' and test['tests']==17 and test['failures']==test['errors']==test['skipped']==0
assert pins==test['product_files']=={p.name:sha(p) for p in (Path(install['installed'])/'site/ai_ad_editor').glob('*.py')}
folder=ROOT/'skills/agent-ffmpeg-local-editor'
for name in ('SKILL.md','references/runtime.md'):
 p=folder/name;write(p,p.read_text('utf8').replace('v0.1.0-alpha.4-local.45','v0.1.0-alpha.4-local.46').replace('CLI `0.1.47`','CLI `0.1.48`').replace('CLI 0.1.47','CLI 0.1.48'))
p=folder/'SKILL.md';s=p.read_text('utf8');needle='For declared nonzero HLG display black'
assert needle in s
write(p,s.replace(needle,'For actual RGB ICC output, 16-bit profile-embedded frame delivery and native\nsoft proof, read [ICC output](references/icc-output.md). Keep device RGB delivery\nseparate from standard YUV movie encoding; inspect every PNG and the PCM clock.\n'+needle,1))
write(folder/'references/icc-output.md','''# RGB ICC output and native soft proof / CLI0.1.48

Use the pinned unified launcher. Inspect `native_icc_output_profiles` and read
`docs/product/ICC_OUTPUT.md` in the small kit for the complete contract.

1. Ingest authorized media, compose the editable timeline, declare actual
   source signals and linear working RGB with `float32-native-v1`.
2. Obtain the client's authorized RGB ICC v2/v4 output file. Keep it inside the
   project without junctions; record its actual SHA256 and an explicit intent
   in local JSON (`icc_profile`, `sha256`, `intent`, optional boolean BPC).
   Never substitute a vendor-name look or infer physical monitor calibration.
3. Validate, then run `surface render --project PROJECT --sequence-id SEQUENCE
   --output renders/icc --output-profile-json target.json --dry-run` on ONE line.
   Remove `--dry-run` to deliver actual RGBA16 PNG frames, each with the exact
   embedded ICC, plus `output.icc`, stereo 48000Hz `audio.f32le`, `sequence.json`.
   Default range policy rejects CMM output outside0..1. Explicit `--range-policy
   clip` counts application clipping across all frames. The native profile may
   itself compress/map values; that is not counted as application clipping.
4. Use `--start-frame` / `--stop-frame` for half-open timeline CFR intervals.
   Audio uses exact ceil-aligned sample boundaries clamped to authored duration.
   `--max-output-mib` is an output-file budget up to8192MiB, not a peak RSS bound.
   For nits-based working RGB, also declare target `reference_white_nits`.
   Linear values scale by working/output nits before ICC encoding.
5. `surface inspect-output --project PROJECT --input renders/icc` verifies ALL
   hashes, PNG CRCs/decompressed pixels/exact embedded profiles and finite PCM
   with sample counts. It is read-only. This is our filter-0 RGBA16 transport
   verifier, not a general external-PNG validator or proof of media rights.
6. For a client review simulation, author `pixel_pipeline.proofing` containing
   `profile` (same complete relative RGB descriptor, NO nits) and explicit
   `simulation_intent`. Standard `render` / `preview frame` / `preview range`
   use native SOFTPROOFING after an optional declared display mapping and before
   standard output encoding. No alarm colors or physical paper brightness are
   inferred. A matrix-only profile may produce nearly identical proof output.
7. Final `surface render` does NOT apply view simulation a second time. Review
   device PNGs with an ICC-aware viewer. Standard movie previews keep their true
   VUI; never merely label arbitrary ICC device RGB as BT709/BT2020 YUV.
8. Export/import editable packages and replay. Proof profiles are snapshotted
   into portable dependencies and included in actual-byte cache fingerprints.
   A target supplied only as a command argument is not an authored project
   dependency: preserve/distribute it separately unless also used by the proof
   declaration. Packaging bytes does not grant redistribution rights.
9. Show C58 actual MP4/GIF/frame and diagnostic profile provenance before client
   selection. Distinguish a synthetic diagnostic profile from a commercial
   printer/monitor profile. CMM conversion uses CPU; supported authored GPU
   operators remain native OpenCL. No CMYK/ICC5/full ACES/dynamic HDR or measured
   display/printer/artistic acceptance is claimed.
''')
p=folder/'scripts/run.py';s=p.read_text('utf8')
s,n=re.subn(r"^MANIFEST = '[^']+'$",'MANIFEST = '+repr(install['manifest_sha256']),s,count=1,flags=re.M);assert n==1
s,n=re.subn(r"^RELEASE = '[^']+'$","RELEASE = 'v0.1.0-alpha.4-local.46'",s,count=1,flags=re.M);assert n==1;write(p,s)
p=ROOT/'agent-ffmpeg-local-install-manifest.json';m=load(p);m.update(release='v0.1.0-alpha.4-local.46',cli_version='0.1.48',manifest_sha256=install['manifest_sha256'])
m['skills'][0]['skill_md_sha256']=sha(folder/'SKILL.md')
m['files']=[dict(path=p.relative_to(ROOT).as_posix(),bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(folder.rglob('*')) if p.is_file()]
assert len(m['files'])==87 and sum(Path(r['path']).name=='SKILL.md' for r in m['files'])==1
write(p,json.dumps(m,ensure_ascii=False,indent=2)+'\n')
report=dict(status='candidate-pinned-for-installed-acceptance',product_files=len(pins),skill_files=87,public_entries=1,modules=17,source_tests=17,source_fallback=False,namespace_manifest_sha256=sha(p))
write(out/'verification.json',json.dumps(report,indent=2)+'\n');print(json.dumps(report))
