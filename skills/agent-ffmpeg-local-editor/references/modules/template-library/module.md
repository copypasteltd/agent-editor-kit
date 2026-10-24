# 模板变量、素材索引和片段组复用 / template-library

[Unified entry](../../../SKILL.md) · [Shared runtime](../../runtime.md)

Templates/variables/library → editable variants/index

Commands: `template apply/batch; library; fragment`. User-provided assets and per-resource licenses.

## Workflow

Inspect `template --help`, `fragment --help` and `library --help`. Define required variables and asset IDs,
verify rights, then apply into an owned project. Validate and preview each variant before rendering. Preserve
editable clips, keyframes, audio and nested timing when reusing groups; do not replace them with a flattened render.
