# 显式登记并运行已有离线模型 / local-models

[Unified entry](../../../SKILL.md) · [Shared runtime](../../runtime.md)

Native runtime + weights/hashes/licenses → adapters/artifacts

Commands: `media adapter; audio adapter; audio separate-stems; asr adapter; ocr; face; tts; voice; translate; dub subtitles; gpu; model-pack`.
No weight downloads; check capability/runtime before execution.

For text/image/first-last video, read [video-generation.md](../../video-generation.md).
`media generate` reuses an explicitly registered VACE CUDA runtime, produces a
new asset and can apply an editable clip. Inspect actual interior frames and
endpoint evidence separately; retain model/image rights dependencies.

For translated SRT with complete timed speech and editable caption/audio clips,
read [subtitle-dubbing.md](../../subtitle-dubbing.md). Preserve all regeneration
attempts and inspect actual providers, fit and content rights; cue timing does
not imply word alignment, naturalness or lip synchronization.

For the installed community speech/translation packs, read
[community-materials.md](../../community-materials.md). Prefer configured GPU
with `--device auto`, inspect the actual provider and retain explicit CPU fallback
or strict CUDA errors. General adapters still require their own registration.
For independent drums/bass/other/vocals, read [audio-stems.md](../../audio-stems.md).
Use the dedicated four-source engine; the older vocal/residual-accompaniment
adapter does not implicitly become a four-source adapter.
For corrected speech word timing, read [ctc-alignment.md](../../ctc-alignment.md).
The explicit activity mode preserves raw CTC evidence and requires review;
continuous speech, Chinese, lyrics and overlapping voices remain unaccepted.

## Workflow

Inspect `media adapter --help`, `media adapter register --help` and the advertised capability before running.
Require explicit existing weights, native dependencies, adapter settings and rights evidence. The base package
contains no model weights. Verify returned artifacts and actual inference reports; do not claim a missing adapter
is integrated or copy experimental post-release commands from old notes.

For actual native CUDA audio-driven face lip sync, explicit25FPS face-box keys,
complete RGBA/PCM preservation and editable recipe reruns, read
[local neural lip sync](../../lip-sync.md). Review natural mouth motion and
complete speech separately from transport proofs; full-body animation remains separate.
