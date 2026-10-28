# 原生 ICC 来源色彩管理 / 原生 ICC 來源色彩管理 / Native ICC sources

[简体中文](../../README.md) · [繁體中文](../../README.zh-TW.md) · [English](../../README.en.md) · [Install](COMMUNITY_LOCAL_DELIVERY.md) · [C56](CASES.md#c56-native-icc-profiles)

CLI0.1.46 / alpha.4-local.44 / r47 kit. One registered `$agent-ffmpeg-local-editor`,17 internal modules. Native Windows only; the pinned offline installation includes the actual LittleCMS2.19.1 x64 DLL and MIT license. No container, virtual environment, global installation, model download or source fallback is involved.

将已知 RGB 素材的真实 ICC 配置显式放入工程，锁定文件 SHA，选择渲染意图和黑点补偿。引擎直接转换到声明的线性工作 RGB；预览、最终渲染和浮点导出使用同一原生 CMM。配置文件随可编辑工程包迁移，预览缓存也包含其实际字节摘要。

繁體：將已知 RGB 素材的真實 ICC 設定檔明確放入專案，固定 SHA、算圖意圖與黑點補償。原生 CMM 直接轉換至線性工作 RGB，貫通預覽、最終算圖、浮點匯出及設定檔依賴封裝。

English: declare the profile that actually describes the source code values. Native LittleCMS converts directly to a linear working profile; profile bytes participate in cache fingerprints and portable packages. Creative looks remain separate [LUT/style operations](../local/LOOK_PRESETS.md).

## Configuration contract

Only `source_signal` changes for an ICC source. Ordinary RGB sources retain their existing primaries/transfer declarations. Do not mix the two interpretations.

```json
{
  "engine": "float32-native-v1",
  "working_signal": {
    "primaries": "aces-ap1",
    "transfer": "linear",
    "white_xy": [0.32168, 0.33767]
  },
  "output_signal": {"primaries": "bt709", "transfer": "srgb"},
  "range_policy": "clip",
  "sources": {
    "chart": {
      "source_signal": {
        "icc_profile": "assets/source.icc",
        "sha256": "sha256:<actual 64 lowercase hex>",
        "intent": "relative-colorimetric",
        "black_point_compensation": false
      },
      "display_geometry": "square-unrotated",
      "demux_origin": 0
    }
  }
}
```

Place this object under `settings.pixel_pipeline` in the editable project. The example's `chart` must be the actual ingested asset ID. Configure matching output tags separately: BT.709 primaries/matrix, `iec61966-2-1` transfer and the chosen range for this SDR example. C56 uses MKV/libx264/yuv444p10le plus PCM. General timeline/setup instructions remain in the [product workflow](COMMUNITY_MATERIALS.md); the complete C56 package below is directly runnable.

| Field | Required behavior |
|---|---|
| `icc_profile` | Project-relative ordinary local file; no URLs, absolute/outside/reparse paths. Header v2/v4, RGB device space, XYZ/Lab PCS. |
| `sha256` | Mandatory actual file pin. A profile change requires an intentional new declaration. |
| `intent` | Mandatory `perceptual`, `relative-colorimetric`, `saturation` or `absolute-colorimetric`; the input profile must advertise support for that intent. |
| `black_point_compensation` | Boolean, default false, passed explicitly to native CMM. It does not promise a visible difference for every profile/intent. |
| `reference_white_nits` | Optional authored absolute unit,0.01..10000; required on all sources when the HDR project contract requires nits. Declare working/output units separately. |
| Working signal | Declared RGB primaries/white with `linear` transfer. D50/D60/reference-white handling occurs in the CMM transform. |

Matrix/shaper and actual nonlinear CLUT source profiles are exercised. Perceptual/saturation appearance depends on the profile's tables; matrix profiles can produce the same result for several intents. A missing selected table is rejected instead of silently substituting another table. ICC media-white/chromatic-adaptation tags do not measure scene illumination or physical display luminance. No extra Bradford transform should be applied after the CMM just to “fix” a profile.

## Reproduce the complete editable C56 example

Install/activate the matching local application ZIP first. The small r47 kit contains the Skill/docs/installer, while the large application bundle remains a separately supplied local artifact. The example output directory must not already exist.

```powershell
$aekSkills = if ($env:CODEX_HOME) { Join-Path $env:CODEX_HOME 'skills' } else { Join-Path $env:USERPROFILE '.codex/skills' }
$avk = Join-Path $aekSkills 'agent-ffmpeg-local-editor/scripts/run.ps1'
$aekRepo = 'E:/dev/sandbox/AI广告剪辑'
$aekProject = Join-Path $aekRepo 'local/agent-ffmpeg/my-icc-example'
& $avk version
& $avk capabilities
& $avk convert import --input (Join-Path $aekRepo 'docs/assets/native-icc-20261028-r1/editable-icc.aevpkg.zip') --output $aekProject
& $avk surface inspect-profile --project $aekProject --input assets/source.icc
& $avk validate --project $aekProject
& $avk render --project $aekProject --output (Join-Path $aekProject 'renders/client.mkv') --dry-run --hardware-encode off --projection-acceleration require --projection-device 0.0
& $avk render --project $aekProject --output (Join-Path $aekProject 'renders/client.mkv') --hardware-encode off --projection-acceleration require --projection-device 0.0
& $avk preview frame --project $aekProject --frame 24 --height 360
& $avk preview range --project $aekProject --start-frame 0 --end-frame 48 --height 360
& $avk convert export --project $aekProject --output (Join-Path $aekProject 'exports/client.aevpkg.zip') --target-format package
```

Check each JSON envelope's `ok` and process exit code before the next dependent operation. GPU selection above is the tested machine's native OpenCL adapter; inspect the installed device configuration for another machine. ICC color conversion itself is CPU CMM; the example's supported Bloom/composition uses GPU. Read [GPU execution](FLOAT_GPU.md) for policies and cleanup, and [HDR](HDR_DISPLAY.md) for absolute-light output.

`surface inspect-profile` returns the actual source SHA, description, header/tags, matrix/shaper flag, CMM version and runtime/profile artifact pins. It performs no decode or author edit. `validate` checks the structural contract; actual native parsing/transform creation is verified when the profile is inspected or used. Do not treat schema validity alone as proof that a vendor profile works.

## Native-clock Float32 surface export

Use the inspection response's `data.source_profile.sha256` for the mandatory pin:

```powershell
$aekICC = (& $avk surface inspect-profile --project $aekProject --input assets/source.icc | ConvertFrom-Json)
& $avk surface export --project $aekProject --asset-id chart --output (Join-Path $aekProject 'renders/icc-working-surface') --source-icc-profile assets/source.icc --source-icc-sha256 $aekICC.data.source_profile.sha256 --source-icc-intent relative-colorimetric --working-primaries aces-ap1 --working-transfer linear --working-white-xy 0.32168 0.33767 --stop-frame 1
```

Optional BPC uses `--source-icc-black-point-compensation`. Explicit light units use `--source-reference-white-nits` and `--working-reference-white-nits`. Do not combine ICC flags with ordinary `--source-primaries`, `--source-transfer` or `--source-white-xy` flags. The bundle stores native PTS/duration/int64 clock and interleaved straight Float32 RGBA. It is an intermediate; the command does not export timeline audio or create a movie.

Encoded source RGB/alpha must be finite0..1. CMM working output may be negative or above one; it is not implicitly clipped. Alpha is copied independently,including signed zero/subnormal bit patterns. Nit scaling uses separately declared source/working reference whites. Final integer/HDR range policy is an independent boundary,as demonstrated by the explicit `clip` in C56. No Pillow/eight-bit conversion occurs in this product path.

## Actual receipts, caching and migration

Inspect `delivery.pixel_pipeline.source_receipts.<asset_id>.ICC_transform` in the render manifest: actual profile SHA/header/description, CMM version2190, intent/BPC, working signal, unit scale, CPU backend, artifact pins and closed native handles. GPU operation counts and worker/thread/stream cleanup remain in `projection_acceleration` separately. For a raw bundle inspect `colour_boundary` in `bundle.json`.

The implementation holds Windows read handles that deny profile/runtime writes/deletion during the transform lifetime,polls cancellation between bounded tiles and closes transform/profile/context handles on success/failure. The16MiB/4096-tag profile limit and768MiB surface workspace estimate are operation budgets,not a measured process peak-RSS guarantee. Native ICC runs synchronously per tile; cancellation waits for that tile's CMM call to finish.

Preview/resume/queue fingerprints hash the actual ICC file and CMM artifacts,not just modification time. Changed or missing bytes fail before successful publication. `package` snapshots and checks actual profile bytes under a native read lock before ZIP publication. Paths under `assets/` stay stable; other project-local profiles become `assets/color-profiles/<SHA>.icc` in the packaged copy. The author project is unchanged. Package import can render without the original source-profile directory. Rights evidence remains required separately; moving or converting a profile grants no license.

## Evidence, previews and limits

[C56 actual PNG/MP4/GIF/profile/editable package](CASES.md#c56-native-icc-profiles) · [Source/installed/compatibility evidence](../validation/原生ICC色彩管理实测_2026-10-28.md) · [Exact capabilities](icc-capabilities-cli-0.1.46.json)

C56 uses an original CC0 diagnostic chart and authored gamma1.8 ProPhoto D50 RGB profile. Independent published matrix/gamma math checks the entire first Float32 working surface and patches in every encoded frame. ICC fixed-point tag serialization causes bounded reference differences; alpha and package replay use exact byte comparisons. A separate Pillow CMM2.17 build is an additional numerical oracle in tests,not a runtime dependency/path. The comparison's left panel is an independent no-adaptation/no-Bloom control; the right panel is actual ICC/GPU Bloom output at the same frame.

This release implements RGB v2/v4 source profiles. Arbitrary output ICC,softproof/gamut-warning output,CMYK/device-link/named-color/abstract profiles,ICC v5,automatic embedded-profile extraction,full ACES IDT/RRT/ODT/DRT,perceptual HDR gamut mapping and monitor calibration remain open. No natural-image artistic assessment,continuous human playback/listening or HDR-monitor acceptance is claimed. The original38 product goal closure conditions remain unchanged.

LittleCMS source: [release2.19.1](https://github.com/mm2/Little-CMS/releases/tag/lcms2.19.1), [MIT license](https://github.com/mm2/Little-CMS/blob/lcms2.19.1/LICENSE), commit `21c582a594fe5279f90c0b93437c398f93bf62b0`. The DLL/manifest/license are shipped as package data; `scripts/build_native_icc_20261028.py` records the pinned archive/source/compiler hashes and actual native build command. Encoded CMM version2190 is the upstream header value for this hotfix release.

CLI0.1.47 adds [HLG display black and complete source/working signal JSON for raw surface CLI](HLG_BLACK_LEVEL.md). Explicit nits,black/peak/gamma and reject/clip policies are required; no monitor inference. Existing RGB/ICC individual flags remain supported.
