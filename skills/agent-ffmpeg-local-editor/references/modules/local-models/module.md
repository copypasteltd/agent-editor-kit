# 显式登记并运行已有离线模型 / local-models

[Unified entry](../../../SKILL.md) · [Shared runtime](../../runtime.md)

Native runtime + weights/hashes/licenses → adapters/artifacts

Commands: `media adapter; asr adapter; ocr; face; tts`. No weight downloads; check capability/runtime before execution.

## Workflow

Inspect `media adapter --help`, `media adapter register --help` and the advertised capability before running.
Require explicit existing weights, native dependencies, adapter settings and rights evidence. The base package
contains no model weights. Verify returned artifacts and actual inference reports; do not claim a missing adapter
is integrated or copy experimental post-release commands from old notes.
