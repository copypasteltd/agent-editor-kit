# Optical template pack v1 / 可编辑复合光效模板

Eight MIT templates built from existing native optical operators, not eight new kernels or AI models. Each replaces the target clip's complete effects array after review. Preserve existing effects separately or explicitly merge them before applying. Source pixels, Float32 linear working/output signals and the original author clock must be explicit.

Current registered CLI59 actually imported the OP01 project and reselected OP08. All eight templates passed installed CLI63 GPU rendering and full-frame/PCM editable-package replay. This is a 480x270 original product study, not natural-footage aesthetic acceptance.

Use the single `$agent-ffmpeg-local-editor` launcher, inspect the real clip's author duration, then provide `clip_id`, `middle_tick`, `end_tick` in a UTF-8 JSON variables file. For the four-second 90000-tick/s study: `{"clip_id":"hero","middle_tick":180000,"end_tick":360000}`. Radius/shift are source-pixel values; no automatic resolution, crop, slip or duration adaptation.

```powershell
& $entry template apply --project PROJECT --input TEMPLATE_JSON --variables VARIABLES_JSON --dry-run
& $entry template apply --project PROJECT --input TEMPLATE_JSON --variables VARIABLES_JSON
& $entry validate --project PROJECT
& $entry preview frame --project PROJECT --frame 24
```

Dry-run substitutes variables but does not decode or establish final rendering quality. Validate and render before delivery. CPU uses projection acceleration `off`; actual tests used `require`/device `0.0`. Encoding and audio remain their explicitly selected CPU paths. Aesthetic selection does not approve audio, source rights or all uses.

See the repository's `docs/product/OPTICAL_EFFECT_PACK.md` for every parameter, preview, real project package and test boundary. `catalog.json` pins each template; `ACCEPTANCE.json` records actual test scope. The original source PNG/WAV and all previews are distributed separately under the documented media licenses. Templates use MIT; no external weights or assets are required.
