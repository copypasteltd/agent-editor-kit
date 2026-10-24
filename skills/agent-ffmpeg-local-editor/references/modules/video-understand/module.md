# 镜头、静音、帧证据与转写 / video-understand

[Unified entry](../../../SKILL.md) · [Shared runtime](../../runtime.md)

Local video/audio → analysis JSON, frames, caption candidates

Commands: `media understand/contact-sheet; subtitle transcribe; semantic adapter-register/index/search/verify`.
Distinguish heuristics from model semantics. For description/reference-image
retrieval, read [semantic-retrieval](../../semantic-retrieval.md) before execution.

## Workflow

Ingest and inspect local media, then read `media understand --help` and `media contact-sheet --help`.
Retain candidate times, source ranges and extracted evidence. FFmpeg scene scores are candidates, not semantic
understanding. OCR/ASR requires a registered local adapter. Keep transcript corrections traceable to source timing.

Semantic search uses actual image/text embeddings from an explicitly registered
offline model. Return source IDs, actual sampled timestamps, previews and cosine
scores. A point sample supplies no event duration; negation and open-set rejection
remain unreliable. Review candidates before placing an authored range on the timeline.
