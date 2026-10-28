# Explicit OKLab gamut reduction and SDR preview selection

Available in pinned installed CLI0.1.51. In native `float32-native-v1`, author
all source/working/output signals and nits explicitly. Use the mapping object:

```json
{"operator":"reinhard-luminance","source_peak_nits":1000,"target_peak_nits":100,"exposure_stops":0,"gamut_policy":"oklab-chroma"}
```

Set `settings.pixel_pipeline.display_mapping` for formal SDR delivery, with
BT.709/D65 output and `reference_white_nits` equal to `target_peak_nits`.
Set `preview_mapping` for a separate HDR-master viewing trim. Explicit
`preview_mapping` overrides the delivery mapping; otherwise previews inherit
formal `display_mapping` once, including output proofing, before display-linear
resizing. With no declared mapping, HDR previews fail rather than invent a trim.

Use the Skill's pinned `scripts/run.ps1`:

```powershell
& $aekSkill validate --project PROJECT
& $aekSkill preview frame --project PROJECT --frame 0 --height 720
& $aekSkill preview range --project PROJECT --start-frame 0 --end-frame 30 --height 720
```

Set `$aekSkill` to the absolute installed Skill launcher. Select a valid author
frame range and even height64..2160; requested height does not upscale a small
canvas. Inspect the returned PNG and MP4 alongside their explicit settings.
Show a clip-policy comparison generated from the same authored input; keep
client selection tied to the actual preview, mapping and output signal. Do not
use the unrelated 500 style-filter gallery as an OKLab/HDR accuracy reference.

The algorithm applies a modified-Reinhard luminance shoulder then reduces OKLab
a/b along constant L/hue to fit BT.709. It preserves perceptual L, not CIE Y.
Black/near-white endpoint mappings are counted separately; alpha is preserved.
Keep `last_preview_mapping`, `preview_delivery_boundary`, full-frame gamut and
clipping counters with delivery reports. PNG16 and Float32 range reference are
not the same as the compressed viewing MP4 or a physical HDR master.

CPU tiled execution; no GPU colour-kernel, soft-knee, ACES or monitor claim.
Reject invalid targets, negative CIE Y or undeclared signal assumptions.
C61 historical source package reused `sound` as both asset and clip ID; use the
corrected package in the preview-fix report, validate after import, then export
and re-import to verify editability. Do not silently bypass project validation.

Full parameter contract and real previews:
https://github.com/copypasteltd/agent-editor-kit/blob/main/docs/product/OKLAB_GAMUT.md
Historical C61 correction and actual candidate previews:
https://github.com/copypasteltd/agent-editor-kit/blob/main/docs/validation/SDR预览映射修复_2026-10-29.md
