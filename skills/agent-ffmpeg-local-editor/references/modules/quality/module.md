# 成片、像素、蒙版、Scope 与证据核验 / quality

[Unified entry](../../../SKILL.md) · [Shared runtime](../../runtime.md)

Video + manifest + reference → reports/scopes/differences

Commands: `quality check/scopes/mask/golden`. Separate static review/playback/listening; review look selections.

## Workflow

Run `validate` and `rights check`, then `quality check` on the actual encoded file. Inspect `quality scopes`
and `quality golden` help for requested comparisons. Retain reports, manifests and actual source/output frames.
Separate automatic decode/PCM checks, static review, continuous playback and human listening. A passed encode
does not establish natural quality or full CapCut parity.

R3 now preserves sample-exact copied, inverted or silent source-channel
relationships and records its proof/change manifest. This does not accept
arbitrary stereo phase or the known four-millisecond stretch pitch failures.

For looks and client choices, read [looks](../../looks.md) and [actual visual selection](../../client-look-selection.md).
