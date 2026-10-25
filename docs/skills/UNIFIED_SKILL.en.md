# Unified Skill: one entry, 17 task modules

<!-- community-current -->

**Current local / 当前本机 / 目前本機：CLI 0.1.16 / alpha.4-local.14 / r16 kit.** One registered Skill / 17 modules; [r16 kit](agent-editor-kit-community-unified-skill-r16.zip). Six reusable motion paths and native animation capture are now installed, alongside editable ad variants, semantic runtime migration, GPU voice/translation, subtitle dubbing and 359 resources.

[Motion workflow + previews](../product/MOTION_PACKS.md) · [Current installation](../product/COMMUNITY_LOCAL_DELIVERY.md) · [All 38 original goals](../product/GOAL_GAPS_20261025.md). Public alpha.3 assets retain their original version.

<!-- /community-current -->

## Archived alpha.3 / r1 instructions

[简体中文](UNIFIED_SKILL.md) · [繁體中文](UNIFIED_SKILL.zh-TW.md) · [Detailed modules](../product/SKILLS.en.md)

Invoke **`$agent-ffmpeg-local-editor`** for all supported workflows. The Skill reads relevant internal references for timeline editing, filters, captions, audio, local models, quality, delivery, creative planning and supplied campaign data. Its folder includes the attributed helper scripts, templates and licenses; it does not depend on separately registered specialist Skills.

This changes Skill organization and registration. The runtime remains the published **v0.1.0-alpha.3 / CLI 0.1.2 / 500 looks**. Unpublished community-material, translation and voice candidates are not installed capabilities. The original alpha.3 release, its split 17-Skill kit and checksums remain unchanged.

## Existing repository installation

```powershell
Set-Location 'E:/dev/sandbox/AI广告剪辑'
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ./register-agent-ffmpeg-local-skills.ps1
```

The registrar verifies the runtime receipt, launcher and entire Skill inventory before changing discovery. It keeps the main entry and unlinks only this checkout's 16 known specialist junctions, preserving canonical source files and all unrelated registrations. Conflicting directories, foreign junction targets or edited specialist sources cause refusal before registration changes. Receipts go under `local/agent-ffmpeg/registrations/`; the portable manifest is not rewritten with host paths. Open a new conversation to refresh the client's cached Skill list.

## Fresh installation

Use native Windows x64 with existing CPython 3.13 x64 and FFmpeg/ffprobe on PATH. Download the [unified Skill kit](https://github.com/copypasteltd/agent-editor-kit/raw/refs/heads/main/docs/skills/agent-editor-kit-unified-skill-r1.zip) and the [alpha.3 runtime ZIP](https://github.com/copypasteltd/agent-editor-kit/releases/download/v0.1.0-alpha.3/agent-editor-kit-v0.1.0-alpha.3-cp313-win_amd64.zip). The [gallery ZIP](https://github.com/copypasteltd/agent-editor-kit/releases/download/v0.1.0-alpha.3/agent-editor-kit-v0.1.0-alpha.3-gallery.zip) is optional for human-facing look selection.

```powershell
$aekPython = 'C:/Python313/python.exe'
$aekHome = 'E:/tools/agent-editor-kit-unified'
Expand-Archive -LiteralPath 'E:/Downloads/agent-editor-kit-unified-skill-r1.zip' -DestinationPath $aekHome
Set-Location $aekHome
& $aekPython -I -B -X utf8 ./install.py --archive 'E:/Downloads/agent-editor-kit-v0.1.0-alpha.3-cp313-win_amd64.zip'
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ./register-agent-ffmpeg-local-skills.ps1
$avk = Join-Path $aekHome 'skills/agent-ffmpeg-local-editor/scripts/run.ps1'
& $avk version
& $avk doctor
& $aekPython -I -B -X utf8 ./run-example.py --output 'E:/video-work/unified-first-demo'
```

Choose a new tool directory: existing installations are preserved. If Codex already has the same name pointing at another tool home, keep using that registration or test with `-SkillsDirectory 'E:/video-work/aek-discovery'`; unrelated directories are never overwritten. Runtime checksums remain in the release; the new kit's checksum is in [unified-skill-package.json](unified-skill-package.json). The installer verifies both the pinned runtime ZIP and kit file inventory. Hashes are not publisher signatures. No Docker, WSL, virtual environment or runtime downloads are used.

## Examples

```text
$agent-ffmpeg-local-editor Make a 15-second vertical ad from E:/media/product.mp4.
Inspect support and source audio, show actual warm-film and monochrome choices, then deliver a preview, video, quality report and editable package.

$agent-ffmpeg-local-editor Add an editable push-in and keyframes to clip_1; preview start, middle and end.

$agent-ffmpeg-local-editor Turn E:/media/interview.mp4 into three shorts using the supplied captions and retain original audio.

$agent-ffmpeg-local-editor Analyze supplied local campaign data, calculate ROAS/CPA and propose the next creative script.
```

Name the task in ordinary language. You need neither a module filename nor another Skill name. References load as needed; the unified Skill does not load all 17 modules by default or launch subagents. See the [entry instructions](../../skills/agent-ffmpeg-local-editor/SKILL.md) and [all module responsibilities](../product/SKILLS.en.md).

The included example produces six seconds of 360×640/30 fps video, 180 frames, audio, an editable project and a recoverable package. Editing-chain checks, automatic decoding, natural-media quality and human listening remain distinct acceptance items. Consolidation does not establish complete CapCut parity.

## Maintainer layout

The only registered folder contains `SKILL.md`, UI metadata, the pinned runtime launcher, the look-gallery helper, shared runtime/look references and `references/modules/*/module.md`. Upstream resources and licenses sit beside their relevant module. There are no nested `SKILL.md` entries.

The `agent-ffmpeg-local-skills-v2` manifest declares `skill_count=1`, `module_count=17` and stable K01–K17 mappings to previous names. Future expansion should add internal task references rather than new public specialist registrations. The old split source is retained for historical reproduction; new packaging uses the manifest's single entry.

[Actual verification and migration receipts](../validation/evidence/unified-skill-20261024-r1/) · [Original alpha.3 release](https://github.com/copypasteltd/agent-editor-kit/releases/tag/v0.1.0-alpha.3)
