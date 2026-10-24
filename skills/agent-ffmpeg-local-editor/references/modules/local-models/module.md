# 显式登记并运行已有离线模型 / local-models

[Unified entry](../../../SKILL.md) · [Shared runtime](../../runtime.md)

Native runtime + weights/hashes/licenses → adapters/artifacts

Commands: `media adapter; asr adapter; ocr; face; tts; voice; translate; gpu; model-pack`.
No weight downloads; check capability/runtime before execution.

For the installed community speech/translation packs, read
[community-materials.md](../../community-materials.md). Prefer configured GPU
with `--device auto`, inspect the actual provider and retain explicit CPU fallback
or strict CUDA errors. General adapters still require their own registration.

## Workflow

Inspect `media adapter --help`, `media adapter register --help` and the advertised capability before running.
Require explicit existing weights, native dependencies, adapter settings and rights evidence. The base package
contains no model weights. Verify returned artifacts and actual inference reports; do not claim a missing adapter
is integrated or copy experimental post-release commands from old notes.
