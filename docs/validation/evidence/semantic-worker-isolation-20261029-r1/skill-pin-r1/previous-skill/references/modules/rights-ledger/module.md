# 素材、字体、模型与模板权利台账 / rights-ledger

[Unified entry](../../../SKILL.md) · [Shared runtime](../../runtime.md)

Source/license/local evidence → ledger/impact/gates

Commands: `rights list/check/update/impact`. Treat image and LUT rights separately; no automatic legal determination.

## Workflow

Inspect `rights --help` and `media ingest --help`. Record the actual source and license evidence per asset;
unknown rights remain unverified. Use `rights check` before `render --publish`. The publish flag is a local gate,
not a platform upload. When moving a project, rebind local license-evidence paths and recheck the ledger.

For looks and client choices, read [looks](../../looks.md) and [actual visual selection](../../client-look-selection.md).
