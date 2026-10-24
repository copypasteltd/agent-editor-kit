# Functional filter README: 500 built-in looks

[简体中文](FILTERS.md) · [繁體中文](FILTERS.zh-TW.md) · [English](FILTERS.en.md)

Installed release **v0.1.0-alpha.3 / CLI 0.1.2 / catalog 2.0.0** ships 500 offline color transforms, previews and per-resource evidence. Existing 100 LUT bytes/IDs are preserved.

| # | Capability | Behavior |
|---|---|---|
| P01 | Stable naming | 001–100 retain sp-/t3-; new nt-/fl- IDs identify sources and original variants |
| P02 | Search | Simplified/Traditional Chinese names, English, IDs, Simplified Chinese/English descriptions, licenses and category |
| P03 | Inspect | Actual gray/skin/RGB measurements, use suggestions, trial strength, grid, author, license, pinned source and hashes |
| P04 | Preview | New PNG from a bundled synthetic card or local SDR still; static intensity 0–1; existing output preserved |
| P05 | Apply | Explicit clip or global scope; replace bundled looks and preserve manual effects; append only when requested |
| P06 | Transaction | Dry run writes nothing; actual edits copy LUT/license/provenance, add rights/snapshot/idempotency; refuse modified project resources |
| P07 | Compatibility | Preserve exact alpha.2 provenance, replace old preset markers and retain LUT IDs/licenses through package round trips |
| P08 | Licensing | 100 MIT, 267 CC-BY-SA-4.0, 133 CC0; apply each resource's actual obligations |

Workflow: **list → inspect description/license → preview several strengths → dry-run explicit scope → apply → render → inspect decoded output**.

```powershell
$avk = 'E:/dev/sandbox/AI广告剪辑/skills/agent-ffmpeg-local-editor/scripts/run.ps1'
& $avk look list --query '黑白'
& $avk look list --query 'CC0-1.0'
& $avk look inspect --id fl-0000001-action-magenta-01
& $avk look preview --id fl-0000001-action-magenta-01 --output 'E:/video-work/magenta-preview.png' --strength 0.65
& $avk look apply --project 'E:/video-work/my-ad' --id fl-0000001-action-magenta-01 --global --strength 0.65 --dry-run
& $avk look apply --project 'E:/video-work/my-ad' --id fl-0000001-action-magenta-01 --global --strength 0.65
```

## Complete names and detailed profiles

[500 numbered looks with actual effects](LOOK_PRESETS.en.md). Each has a source-qualified ID and original title. New localized titles include measured tone hints. All 500 include seven gray, three skin and three RGB swatches, gray Y′ code values, middle-span ratio, suggested use/intensity, cautions, author/source/license, conversion error, digest, PNG and video.

| Numbers | Profiles |
|---|---|
| 001–100 | [Existing looks](look-profiles/001-100.en.md) |
| 101–200 | [New looks and original curve variants](look-profiles/101-200.en.md) |
| 201–300 | [New looks and original curve variants](look-profiles/201-300.en.md) |
| 301–400 | [Film and community looks](look-profiles/301-400.en.md) |
| 401–500 | [Community creative looks](look-profiles/401-500.en.md) |

500 means distinct numeric transforms, including related upstream curve variants, not 500 unrelated style families. Runtime intensity settings and alternate file formats are not additional looks. Common 17³ sampled signatures and reference previews are unique.

Sources: 49 Striped Purple, 51 t3mujinpack, 267 Natron and 133 FreshLUTs. Categories follow source collections; instant and negative groups also contain monochrome variants. Inspect measured profiles for actual behavior. Hald inputs become 33³ CUBEs with disclosed numerical approximation; original CUBE grids remain intact. FreshLUTs selections use explicit uploader Rec.709 labels, without reclassifying unknown/Log/HLG labels as SDR. Labels are not independent camera calibration: `fl-0000228-science-fiction-for-flog` is labeled Rec.709 but mentions FLog in its title. Its input is ambiguous; use only for experimental creative comparisons on prepared SDR, not verified FLog conversion.

CC-BY-SA resources require author/source credit, retained license, stated conversions and share-alike redistribution of adapted data/previews. Application MIT does not replace these terms. [Notices and pinned sources](../releases/v0.1.0-alpha.3/THIRD_PARTY.md).

## Actual output and boundaries

![Actual original/new-look video comparison](../assets/look500-20261024-r1/motion-comparison.gif)

[Original video](../assets/look500-20261024-r1/original.mp4) · [500 native previews](../assets/look500-20261024-r1/contact-sheet.jpg) · [Individual PNG/video](LOOK_PRESETS.en.md) · [Exact checks and corrected failures](../validation/LOOK500_20261024.md).

These are per-pixel SDR color transforms, not grain, glow, vignette, spatial haze, beauty or AI effects. Suggested scenes/intensity are starting points, not natural-footage acceptance. Y′ and span use encoded RGB, not exposure or linear luminance.

`look apply` uses the default SDR FFmpeg path and refuses Float32/Log/HDR. Static partial strength mixes encoded RGB. Explicit source conversion must precede look selection when appropriate.

The existing 46 processing operators and 500 looks are different counts. `lut register` accepts local .cube/.3dl/.csp/.dat; default-renderer static partial strength requires a full 3D CUBE and other formats have limited metadata. The explicit Float32 path separately supports complete CUBE 1D/3D/shapers with declared signals/domain/budget; renderer coverage differs.

## Custom LUTs and processing operators

```powershell
$avk = 'E:/dev/sandbox/AI广告剪辑/skills/agent-ffmpeg-local-editor/scripts/run.ps1'
& $avk effects list
& $avk effects inspect --name lut3d
& $avk lut register --help
& $avk lut register --project 'E:/video-work/my-project' --input 'E:/looks/cinematic.cube' --name 'My look'
```

Add the returned `lut_id` to a supported timeline LUT effect before preview/render. Registration alone does not change pixels. Supply actual rights and provenance for your own assets. Dynamic strength uses encoded 8-bit RGB mixing; inspect `lut3d`, `effects.numeric_effect_automation` and the selected renderer. Some historical registry limit fields describe static handling only.

Explicit `float32-native-v1` reads complete 1D/3D/shaper+3D CUBEs, not .3dl/.csp/.dat, and does not add 1D support to the default FFmpeg renderer. Proprietary CapCut packs and arbitrary third-party plugins are separate formats.

[Historical installed Float32/shaper evidence](../validation/evidence/float-shaper-20261023-lab/installed-r1/verification.json) · [Historical actual comparison GIF](../assets/float-shaper-20261023-installed-r1/formal-comparison.gif). These checks are not included in this round's 500-look counts.

[Local Skills/install](INSTALLATION.md) · [New release usage](../releases/v0.1.0-alpha.3/USAGE.md) · [Historical 100-look measurements](LOOK_PRESET_DETAILS.md).
