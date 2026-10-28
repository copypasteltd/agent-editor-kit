"""Prepare an unregistered E-drive Skill candidate; preserve the live CLI52 entry."""
import hashlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
REFERENCE='''# Native ACES display views

Use installed CLI0.1.53 or newer with `native_aces_display`. Start with `version`,
`capabilities` and `surface ocio-configs --config aces-2.1`; keep the actual
display/view names and configuration hash. One outer Skill still routes the
17 task modules. Do not invoke source as a fallback for an old installed CLI.

## Author the scene and output

The input must be explicitly scene-linear ACEScg/AP1/D60, not guessed camera
Log, an ordinary sRGB bitmap or PQ codes. Existing declared source colour
conversion is not an automatic camera IDT. Merge into the existing native
Float32 pixel pipeline, retaining `engine`, all `sources` and budgets:

```json
{
  "working_signal": {"primaries":"aces-ap1","transfer":"linear"},
  "output_signal": {"primaries":"bt709","transfer":"srgb","reference_white_nits":100},
  "aces_display": {
    "config":"aces-2.1",
    "display":"sRGB - Display",
    "view":"ACES 2.0 - SDR 100 nits (Rec.709)",
    "exposure_stops":0,
    "input_interpretation":"scene-linear-ACEScg"
  }
}
```

This is a field fragment, not a complete project. Match `settings.color`
BT.709 primaries/matrix and `iec61966-2-1` transfer for this output. Declare
`range_policy: reject` or `clip`; do not silently invent a clipping choice.
ACES2.1 is the config version; the actual SDR Output Transform is named
ACES2.0. Raw and Un-tone-mapped views are not ACES Output Transforms.

Rec.1886 and Gamma2.2 displays decode their real transfer before conversion
to the declared SDR output. PQ/HLG displays require matching BT.2020 ten-bit
output and explicit working/output/source luminance fields under the current
HDR contract. HLG uses1000nits/system gamma1.2/zero display black. Scene values
are passed to ACES as declared, without another output-nit rescaling.

## Preview, measure and present

Validate, render and use `preview frame/range` through the pinned launcher.
SDR previews inherit formal ACES once, then resize in display-linear light.
For HDR masters, explicitly choose a BT.709 SDR `aces_preview` selection or
an existing explicit `preview_mapping`. Never treat PQ/HLG codes as SDR.
`aces_preview` and `preview_mapping` cannot coexist. Formal `aces_display`
cannot coexist with `display_mapping`. ICC soft-proof compounds remain
unaccepted and are rejected, rather than silently stacking transforms.

For `surface measure`, declare output reference-white nits. Scene-relative
ACES working input need not have a display-nit unit for SDR metering; other
pipelines retain their working/output-nit contract. Compare the measured
`encoder_RGB16_input_sha256` to render `transport.video_input_sha256`.
This is pre-codec metering, not decoded-media or physical-display measurement.

Inspect actual `aces_display`/`last_aces_display` or `last_preview_aces`, frame
and pixel counts, selected view/config hash, and `ACES_processors_closed`.
Show the client's actual PNG/MP4 with its selected configuration. Export/import
an editable package and verify the full decoded video and PCM before delivery.
The existing500-look gallery is a different selection axis; do not represent
an unrelated look thumbnail as the selected ACES output.

Numeric example and user workflow:
https://github.com/copypasteltd/agent-editor-kit/blob/main/docs/product/ACES_TIMELINE.md

## Execution scope

Pinned native Windows CPython3.13 x64 OCIO2.6.0, CPU display transforms,
Float32 RGBA, alpha bits retained. Existing GPU projection/compositing does
not make ACES a GPU operator. Runtime files and licenses are verified locally;
no network LUTs, GUI, Docker, WSL or global installation is needed.
Processor closure is not DLL unloading or measured total-process memory.
Camera IDT/AMF/LMT, ACES GPU, additional output standards, natural artistic
quality, physical HDR monitoring and full product parity remain unaccepted.
'''

def main():
    manifest=json.loads((ROOT/'agent-ffmpeg-local-install-manifest.json').read_bytes())
    assert manifest['cli_version']=='0.1.52' and manifest['skill_count']==1 and manifest['module_count']==17
    stage=ROOT/'local/agent-ffmpeg/aces-skill-stage51'
    stage.mkdir(parents=True,exist_ok=False)
    for r in manifest['files']:
        source=ROOT/r['path'];data=source.read_bytes()
        assert len(data)==r['bytes'] and hashlib.sha256(data).hexdigest()==r['sha256']
        target=stage/r['path'];target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(data)
    skill=stage/'skills/agent-ffmpeg-local-editor'
    p=skill/'SKILL.md';s=p.read_text(encoding='utf-8').replace('local.50','local.51').replace('0.1.52','0.1.53')
    s=s.replace('explicit PQ/HLG HDR,','explicit PQ/HLG HDR and native ACES display/view transforms,',1)
    needle='For all-frame HDR light metering';assert needle in s
    s=s.replace(needle,'For scene-linear ACEScg delivery and explicit display/view selection, read\n[native ACES](references/aces-display.md). Use actual previews and preserve\nthe selected config/view; ACES runs on CPU, not the projection GPU.\n'+needle,1)
    p.write_text(s,encoding='utf-8',newline='\n')
    (skill/'references/aces-display.md').write_text(REFERENCE,encoding='utf-8',newline='\n')
    p=skill/'references/runtime.md';p.write_text(p.read_text(encoding='utf-8').replace('local.50','local.51').replace('0.1.52','0.1.53'),encoding='utf-8',newline='\n')
    (stage/'STAGING.json').write_text(json.dumps(dict(status='unregistered-candidate',live_skill_changed=False,public_entries=1,modules=17,
        files=sum(p.is_file() for p in skill.rglob('*')),runtime_launcher_pin='pending-final-gates'),indent=2),encoding='utf-8')
    print(stage)

if __name__=='__main__':main()
