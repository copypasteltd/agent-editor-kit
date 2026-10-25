# Translate SRT and create editable local dubbed captions

Use the installed CLI's `dub subtitles` for a joint OPUS translation and Kokoro
speech batch. This reference belongs to K07/K01; it adds no separate Skill.
Check `dub subtitles --help` and the pinned runtime before execution.

## Prepare the actual inputs

Require a local, reviewed plain UTF-8 SRT, explicit `en`/`zh-Hans`/`zh-Hant`
source and target languages, and existing registered community model packs.
Translation supports Chinese ↔ English. Matching source/target languages preserve reviewed text and initialize only the voice model; no translation pack or glossary is used. No automatic downloads or voice cloning.
Plain SRT preserves source IDs/order and integer milliseconds; markup, malformed
blocks and duplicate IDs are rejected. Limits are 1 MiB, 1000 cues, 3000
characters/cue and 300 seconds per generated utterance. Project timebase must
be divisible by 1000. Model token limits also apply; long text is not truncated.

For `--apply`, explicitly choose an existing unmuted/unlocked audio track and
subtitle track with empty target ranges, plus an ingested font asset. Use actual
returned IDs. Never replace existing audio, captions or source clips.

```powershell
# $avk uses this Skill's pinned launcher. $project and $sourceSrt must exist.
& $avk materials ingest --project $project --id noto-sans-sc-variable --asset-id caption_font
# Create a subtitle track with timeline compose if the project lacks one.
& $avk dub subtitles --project $project --input $sourceSrt --from en --to zh-Hans --device auto --fit reject --apply --audio-track-id track_audio_1 --subtitle-track-id captions --font-asset-id caption_font --dry-run
& $avk dub subtitles --project $project --input $sourceSrt --from en --to zh-Hans --device auto --fit reject --apply --audio-track-id track_audio_1 --subtitle-track-id captions --font-asset-id caption_font
& $avk validate --project $project
```

Read the [complete setup and track JSON](https://github.com/copypasteltd/agent-editor-kit/blob/main/docs/product/SUBTITLE_DUBBING.md).
A dry run has no inference and cannot establish actual speech duration.
Without `--apply`, assets/evidence are registered for later explicit composition.

## Fit and select whole utterances

Default `--fit reject` refuses the whole commit if any full speech exceeds its
source cue window. `DUBBING_CUE_OVERFLOW` returns a retained local failure report
and complete WAVs for review. Do not silently shorten text or widen windows.

Explicit `--fit speed --speed 1 --max-speed 1.6` can regenerate the complete
unchanged utterance up to three times. All original/retry WAVs are retained;
speed never exceeds the chosen limit, whose maximum is 2. The controller reads
actual 24kHz PCM16 samples and checks the speed sequence and final fit. Faster
speech requires listening; a fitted utterance is not a naturalness verdict.

Default voices are `zf_001` for Chinese and `af_maple` for English. Optional
`--voice-map` reads `{"cues":{"2":"zf_002","3":"zf_003"}}`, keyed by original
SRT ID. Use `voice list` first; language must match. This is manual casting,
not automatic speaker diarization. `--glossary` is explicit post-translation
replacement and does not ensure contextual meaning.

## Devices, output and recovery

Prefer configured `--device auto`; inspect the actual providers used. Same-language mode has only a voice provider. Per-task
`--voice-device`/`--translation-device`, pack and CUDA library overrides exist.
One Kokoro initialization is reused within the voice batch. Translation and
speech workers run sequentially; this is not cross-command persistent caching.
Kokoro CUDA currently supports device 0 only. `cuda` is strict; only an actual
CUDA inference failure in `auto` can retry a verified CPU pack in a fresh
directory. Cancellation, timeout, bad packs and protocol/fit failures do not
trigger this fallback. Do not stop unrelated GPU jobs.

`--timeout-seconds` gives the combined task budget; `--cancel-file` can terminate
its owned running worker. Overlapping cues require explicit
`--overlap-policy mix` and both destination tracks' `overlap_policy=allow`.
`--timeline-start-tick` offsets the batch without changing source cue timings.

Inspect `report`, `assets`, `clips`, `devices`, `total_generations` and actual
WAVs. Preserve source/translated/bilingual SRTs, all speech attempts, model
sources/licenses and the report. Failures roll back project metadata; overflow
retains its managed directory until explicit recovery cleanup. Preview first:

```powershell
& $avk project recover --project $project --cleanup-jobs --dry-run
& $avk project recover --project $project --cleanup-jobs
```

Save needed failure samples before cleanup. Committed assets and model license
evidence are protected; see [job recovery](job-recovery.md) for wider limits.
Source/translation/speech rights stay unverified/internal until reviewed.
Render and inspect the complete output normally; do not claim natural listening,
semantic acceptance, word/phonetic alignment or lip synchronization from the
cue-window checks. G19 and full CapCut equivalence remain open.
