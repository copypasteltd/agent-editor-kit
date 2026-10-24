# 镜头、静音、帧证据与转写 / video-understand

[Unified entry](../../../SKILL.md) · [Shared runtime](../../runtime.md)

Local video/audio → analysis JSON, frames, caption candidates

Commands: `media understand/contact-sheet; subtitle transcribe`. Distinguish heuristics from model semantics.

## Workflow

Ingest and inspect local media, then read `media understand --help` and `media contact-sheet --help`.
Retain candidate times, source ranges and extracted evidence. FFmpeg scene scores are candidates, not semantic
understanding. OCR/ASR requires a registered local adapter. Keep transcript corrections traceable to source timing.
