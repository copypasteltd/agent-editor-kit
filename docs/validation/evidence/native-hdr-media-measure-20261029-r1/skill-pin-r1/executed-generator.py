"""Pin the single public Skill to the byte-verified native post-codec meter."""
from pathlib import Path
import argparse,hashlib,json,re
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'docs/validation/evidence/native-hdr-media-measure-20261029-r1'
def load(p):return json.loads(Path(p).read_bytes())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,s):Path(p).write_text(s,encoding='utf8',newline='\n')
def main():
 ap=argparse.ArgumentParser();ap.add_argument('--run',required=True);a=ap.parse_args();assert a.run.replace('-','').isalnum()
 out=BASE/('skill-pin-'+a.run);out.mkdir(exist_ok=False);(out/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
 install=load(BASE/'installation-final-r1/verification.json')
 assert install['status']=='installed-and-byte-verified' and install['cli_version']=='0.1.50'
 pins={p.name:sha(p) for p in (ROOT/'product/src/ai_ad_editor').glob('*.py')}
 for run,count in [('installed-r1',29),('installed-boundary-r1',42)]:
  t=load(BASE/run/'verification.json');assert t['status']=='passed' and t['tests']==count and t['product_files']==pins
 assert pins=={p.name:sha(p) for p in (Path(install['installed'])/'site/ai_ad_editor').glob('*.py')}
 folder=ROOT/'skills/agent-ffmpeg-local-editor'
 for name in ('SKILL.md','references/runtime.md'):
  p=folder/name;write(p,p.read_text('utf8').replace('v0.1.0-alpha.4-local.47','v0.1.0-alpha.4-local.48').replace('0.1.49','0.1.50'))
 p=folder/'SKILL.md';s=p.read_text('utf8');needle='For actual RGB ICC output'
 assert needle in s and 'references/hdr-media-measurement.md' not in s
 s=s.replace(needle,'For final encoded HDR media, read [post-codec metering](references/hdr-media-measurement.md).\nUse `surface measure-media` with explicit signal/YCbCr declarations; keep native\nPTS/exposure gaps, decoded-pixel measurements and pre-codec results distinct.\n'+needle,1)
 write(p,s)
 write(folder/'references/hdr-media-measurement.md',"""# Post-codec native media light metering

Use this when checking an actual encoded file, separate from `surface measure`
which measures the authored encoder RGB16 input. Both are available in the
pinned installed CLI 0.1.50; use this Skill's `scripts/run.ps1`.

```powershell
& $aekSkill surface measure-media --project PROJECT --input renders/master.mkv --signal-json SIGNAL.json --pixel-family yuv --yuv-matrix bt2020nc --yuv-range limited --chroma-location left --scan progressive --dry-run
```

Set `$aekSkill` to this Skill's `scripts/run.ps1`; use an absolute signal JSON
path. Remove `--dry-run` for actual all-frame decode. Example PQ signal:
`{"primaries":"bt2020","transfer":"pq-st2084","reference_white_nits":203}`.
HLG additionally requires display peak and system gamma; black lift is explicit.
For native RGB use `--pixel-family rgb` without YCbCr parameters. Do not infer
colour interpretation, display light or mastering values from file tags.

The input must exist within the project. The meter keeps original PTS and
positive native durations, including nonzero starts and VFR; unknown/zero
durations fail. Exposure gaps/overlaps are reported, not silently filled.
`--active-region X Y WIDTH HEIGHT` selects a region without claiming whole-canvas
acceptance. Only full streams are currently measured.

Default range policy rejects negative/over-one reconstructed RGB. An explicit
`--range-policy clip` permits clipping and reports whole-frame component counts.
Keep those counts with client-facing metrics. RGB16 is not quantized again:
native samples/YCbCr reconstruction become Float32 codes and Float64 light math.
Compare full decoded RGBA/clock digests, MaxRGB and CIE Y separately; a pre-codec
peak must not be presented as the encoded movie's peak.

Use `--cancel-file` for interruption. Preserve native reader process/thread
cleanup receipts. No project/media/SEI rewrite, inferred monitor calibration or
automatic MaxCLL/MaxFALL choice occurs. Digital declared-signal metering does not
prove natural HDR viewing, full ACES, dynamic metadata or physical display quality.
""")
 p=folder/'scripts/run.py';s=p.read_text('utf8')
 s,n=re.subn(r"^MANIFEST = '[^']+'$",'MANIFEST = '+repr(install['manifest_sha256']),s,count=1,flags=re.M);assert n==1
 s,n=re.subn(r"^RELEASE = '[^']+'$","RELEASE = 'v0.1.0-alpha.4-local.48'",s,count=1,flags=re.M);assert n==1;write(p,s)
 p=ROOT/'agent-ffmpeg-local-install-manifest.json';m=load(p);m.update(release='v0.1.0-alpha.4-local.48',cli_version='0.1.50',manifest_sha256=install['manifest_sha256'])
 m['skills'][0]['skill_md_sha256']=sha(folder/'SKILL.md')
 m['files']=[dict(path=p.relative_to(ROOT).as_posix(),bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(folder.rglob('*')) if p.is_file()]
 assert len(m['files'])==89 and sum(Path(r['path']).name=='SKILL.md' for r in m['files'])==1
 write(p,json.dumps(m,ensure_ascii=False,indent=2)+'\n')
 report=dict(status='pinned-for-installed-acceptance',product_files=len(pins),skill_files=89,public_entries=1,modules=17,installed_tests=29,boundary_tests=42,source_fallback=False,namespace_manifest_sha256=sha(p))
 write(out/'verification.json',json.dumps(report,indent=2)+'\n');print(json.dumps(report))
if __name__=='__main__':main()
