# 模板变量、素材索引和片段组复用 / template-library

[Unified entry](../../../SKILL.md) · [Shared runtime](../../runtime.md)

Templates/variables/library → editable variants/index

Commands: `template apply/batch; library; fragment`. User-provided assets and per-resource licenses.

## Workflow

Inspect `template --help`, `fragment --help` and `library --help`. Define required variables and asset IDs,
verify rights, then apply into an owned project. Validate and preview each variant before rendering. Preserve
editable clips, keyframes, audio and nested timing when reusing groups; do not replace them with a flattened render.


## Editable composite optical pack v1

For an actual preview,full parameters and editable projects for OP01-OP08,read:
https://github.com/copypasteltd/agent-editor-kit/blob/main/docs/product/OPTICAL_EFFECT_PACK.md
Eight MIT content templates reuse existing optical kernels;they are not eight
new AI models. The real gallery lets a client select a template ID. Review that
direction on the client's actual footage. Original studies are not natural-film
quality acceptance. Current source evidence distinguishes installed CLI63's eight
GPU/package cases from the historical registered CLI59 OP01-to-OP08 reselection.

Read the template and existing clip before applying:it replaces the complete
effects array. Preserve or explicitly merge existing effects after review. Supply
the actual clip ID and original author-clock middle_tick/end_tick. Radii/shifts
are source pixels;other resolutions,crops,retimes and durations need review.
Use template apply --dry-run,then apply,validate,preview,render and export.
Dry-run only substitutes variables;it does not establish final media quality.
Use the actual MP4/GIF and stable ID for selection,not a fabricated preview.
