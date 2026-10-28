"""Pin CLI52 only after source and installed native compatibility gates pass."""
from pathlib import Path
import argparse,hashlib,json,re
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'docs/validation/evidence/gpu-gamut-20261029-r1'
def load(p):return json.loads(Path(p).read_bytes())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()
def write(p,s):Path(p).write_text(s,encoding='utf8',newline='\n')
REFERENCE='''# Native GPU SDR gamut mapping

Available in pinned installed CLI0.1.52. Read `oklab-gamut.md` for the shared
mapping contract. In native Float32 rendering, set the existing project settings:

```json
{"projection_acceleration":{"mode":"require","device":"0.0"}}
```

Merge this settings fragment without replacing the existing pixel pipeline.
Enumerate and verify the actual local device; `0.0` is the tested RTX3060,
not a portable device guarantee. OpenCL FP64 is required. Use an explicit
`display_mapping` for BT.709/D65 SDR delivery, or `preview_mapping` for viewing
an HDR master. Select `gamut_policy: oklab-chroma`, declare source/target peak
nits, exposure and all source/working/output signals. Output reference white
must match the mapping target. Explicit preview mapping wins; otherwise the
formal mapping is inherited once, then resized in display-linear light.

Use the pinned launcher from `runtime.md` to validate, render and preview.
Check `pixel_pipeline.projection_acceleration.operations.gamut_map` and
`last_display_mapping.perceptual_gamut.GPU` (or `last_preview_mapping` for an
explicit viewing trim). Planned GPU work does not prove actual dispatch.
Show real PNG/MP4 previews and preserve the chosen mapping configuration.
Export/import the editable package and verify complete decoded video and PCM.
Client choices refer to actual viewing media, not the unrelated 500-look gallery.

GPU scope is exposure, modified-Reinhard luminance shoulder and 24-step OKLab
chroma search. Arithmetic is binary64, output Float32; alpha bits are retained.
Signal conversion, ICC and output encoding remain CPU. Fixed OKLab L/hue is
not fixed CIE Y. Black/near-white endpoint mappings have separate counters.
`clip` and `reject` keep their CPU paths. `off` uses CPU; `prefer` may record an
initial preflight fallback. Running GPU failure, timeout or cancellation never
silently becomes a successful CPU render. Keep owned process/pipe/shared-handle
cleanup receipts; do not terminate other GPU jobs.

Three reused device buffers plan 48 bytes/pixel, with 4 bytes/pixel host flags.
This is not full RSS or measured post-exit VRAM. One 4K surface comparison is
not encoded 4K, realtime, natural quality or long-form acceptance. Complete
ACES, soft-knee, dynamic HDR, monitor calibration and cross-vendor acceptance
remain outside this implementation.

Workflow and actual source/installed receipts:
https://github.com/copypasteltd/agent-editor-kit/blob/main/docs/product/GPU_GAMUT.md
'''
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--run',required=True);a=ap.parse_args();assert a.run.replace('-','').isalnum()
    install=load(BASE/'installation-final-r1/verification.json');assert install['cli_version']=='0.1.52' and install['status']=='installed-and-byte-verified'
    pins={p.name:sha(p) for p in (ROOT/'product/src/ai_ad_editor').glob('*.py')};assert len(pins)==278
    for name,n in [('source-r2',70),('compat-r1',352),('installed-measure-r1',70),('installed-compat-r1',352)]:
        v=load(BASE/name/'verification.json');assert v['status']=='passed' and v['tests']==n and v['skipped']==0 and v['frozen_equal'] and v['product_files']==pins
    assert {p.name:sha(p) for p in (Path(install['installed'])/'site/ai_ad_editor').glob('*.py')}==pins
    ns=ROOT/'agent-ffmpeg-local-install-manifest.json';manifest=load(ns);assert manifest['cli_version']=='0.1.51' and len(manifest['files'])==90
    for entry in manifest['files']:assert sha(ROOT/entry['path'])==entry['sha256']
    out=BASE/('skill-pin-'+a.run);out.mkdir(exist_ok=False);(out/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    folder=ROOT/'skills/agent-ffmpeg-local-editor';changes={}
    for name in ('SKILL.md','references/runtime.md'):
        p=folder/name;changes[name]=p.read_text('utf8').replace('local.49','local.50').replace('0.1.51','0.1.52')
    needle='For final encoded HDR media';assert needle in changes['SKILL.md']
    changes['SKILL.md']=changes['SKILL.md'].replace(needle,'For GPU HDR-to-SDR mapping, read [native GPU colour](references/gpu-gamut.md).\nCheck actual `gamut_map` dispatch; signal conversion and ICC remain CPU.\n'+needle,1)
    changes['references/gpu-gamut.md']=REFERENCE
    p=folder/'references/oklab-gamut.md';s=p.read_text('utf8').replace('0.1.51','0.1.52')
    needle='CPU tiled execution; no GPU colour-kernel, soft-knee, ACES or monitor claim.';assert needle in s
    changes['references/oklab-gamut.md']=s.replace(needle,'CPU tiled execution remains available. For explicit GPU shoulder/chroma mapping,\nread [gpu-gamut.md](gpu-gamut.md); signal conversion and ICC remain CPU.\nNo soft-knee, full ACES or physical-monitor claim.')
    p=folder/'references/projection-gpu.md';s=p.read_text('utf8')
    changes['references/projection-gpu.md']=s+'\n## CLI52 GPU colour addition\n\nRead [gpu-gamut.md](gpu-gamut.md) for actual luminance shoulder/OKLab chroma\nsearch. Native GPU scope now includes this operator; signal conversion and ICC\nremain CPU. Inspect `operations.gamut_map`, not merely GPU preparation status.\n'
    p=folder/'scripts/run.py';s=p.read_text('utf8')
    s,n=re.subn(r"^MANIFEST = '[^']+'$",'MANIFEST = '+repr(install['manifest_sha256']),s,count=1,flags=re.M);assert n==1
    s,n=re.subn(r"^RELEASE = '[^']+'$","RELEASE = 'v0.1.0-alpha.4-local.50'",s,count=1,flags=re.M);assert n==1;changes['scripts/run.py']=s
    (out/'previous-namespace.json').write_bytes(ns.read_bytes())
    for name,s in changes.items():
        p=folder/name
        if p.exists():
            backup=out/'previous-skill'/name;backup.parent.mkdir(parents=True,exist_ok=True);backup.write_bytes(p.read_bytes())
        write(p,s)
    manifest.update(release='v0.1.0-alpha.4-local.50',cli_version='0.1.52',manifest_sha256=install['manifest_sha256'])
    manifest['skills'][0]['skill_md_sha256']=sha(folder/'SKILL.md')
    manifest['files']=[dict(path=p.relative_to(ROOT).as_posix(),bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(folder.rglob('*')) if p.is_file()]
    assert len(manifest['files'])==91 and sum(Path(v['path']).name=='SKILL.md' for v in manifest['files'])==1
    write(ns,json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    report=dict(status='pinned-for-installed-acceptance',cli_version='0.1.52',product_files=278,skill_files=91,public_entries=1,modules=17,source_tests=70,source_compatibility_tests=352,installed_tests=70,installed_compatibility_tests=352,preview_tests_in_compatibility_group=18,source_fallback=False,namespace_manifest_sha256=sha(ns))
    write(out/'verification.json',json.dumps(report,indent=2)+'\n');print(json.dumps(report))
if __name__=='__main__':main()
