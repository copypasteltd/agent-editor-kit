# Community voice, translation, music and GPU

Read this reference for narration, bilingual subtitles, BGM, SFX or fonts. These
older commands require CLI 0.1.3 or newer; score synthesis requires CLI0.1.59. Alpha.3 public archives do not
provide them. Use the common launcher from SKILL.md and inspect current help.

## Choose actual local resources

`materials list/inspect/verify/ingest` expose 359 real bundled files: 44 music
tracks, 85 jingles, 228 unique SFX and two Noto SC/TC OFL fonts. Search by ID,
kind, tags and language. `ingest` copies source, license and attribution into the
project. Each resource keeps its own license; not all assets use the core license.

`voice list` lists 103 upstream named Kokoro voices. Three voices (`zf_001`,
`zm_009`, `af_maple`) have actual generated auditions; the remaining mappings
are verified but not individually inferred or listened to. Do not invent age,
tone or commercial suitability from IDs. Generate the actual client's text and
show the local WAV before recording their selection.

## GPU is the preferred configured path

Run `gpu inspect` and `model-pack list`. This machine has explicitly registered
CPU/GPU pack and external NVIDIA library paths. Standalone installations supply
`--pack`, `--gpu-pack` and `--cuda-library-directory` themselves, or register a
local `AEK_COMMUNITY_DEVICE_CONFIG` JSON. No runtime command downloads files.

- Default `--device auto`: prefer CUDA with the required pack and free VRAM;
  voice preflight 3072 MiB, translation 1536 MiB. Other GPU processes stay running.
- `--device cuda`: strict failure when the device, library or inference fails.
- `--device cpu`: force native CPU. `auto` reports its CPU fallback reason;
  a failed GPU worker's log is retained. Pack integrity failures are refusals.
- GPU speech: unquantized Kokoro ONNX, sherpa-onnx/ORT, CUDA 13 and cuDNN 9,
  currently device 0 only. GPU translation: OPUS int8 weights / `int8_float16`
  computation, CTranslate2, CUDA 12 cuBLAS with explicit device index.
- RTX 3060 is the actual tested GPU. AMD/Intel/Apple GPU acceleration remains
  unimplemented. Cold load can exceed CPU time; warm generation speed is not
  an end-to-end CLI guarantee. Do not claim every filter or operation is on GPU.

Inspect `data.device`, `data.synthesis.provider` / `data.inference.provider`,
precision, timing, warnings and produced files. CUDA voice also records actual
CUDA provider DLL loading; configuration alone is not evidence of inference.

## Narration and subtitles

```powershell
& $avk voice synthesize --project $aekProject --voice zf_001 --input 'E:/media/narration.txt' --device auto --asset-id asset_voice
& $avk translate subtitles --project $aekProject --from zh-Hans --to en --input 'E:/media/captions.srt' --output exports/bilingual.srt --mode bilingual --device auto
```

Voice accepts text or UTF-8 files, speed 0.5–2.0, at most 3000 characters per
explicit segment, and returns natural-length 24 kHz mono PCM WAV. Longer speech
requires a longer edit or deliberate sentence segmentation. Never truncate a
line silently to fit a video. Apply to an explicit audio track only when requested.

Translation supports `en ↔ zh-Hans/zh-Hant`, at most 1000 paragraphs/cues and
512 model tokens per unit. Preserve supplied cue order, overlaps and milliseconds;
new translated text is not forcibly aligned to speech. ASS/VTT styling is flattened
to SRT. Glossary substitutions are explicit post-edits and fail if expected variants
are missing. Retain source, translations and scores for review. An observed generic
model error is `speech`→“演讲”; correct context instead of claiming semantic acceptance.

## BGM and mix

```powershell
& $avk materials list --kind music
& $avk materials ingest --project $aekProject --id kenney-music-jingles-jingles-hit00 --asset-id asset_jingle
& $avk music prepare --project $aekProject --asset-id asset_jingle --duration-seconds 12 --loop --fade-in-seconds 0.3 --fade-out-seconds 0.8 --new-asset-id asset_bed
& $avk music mix --project $aekProject --voice-asset-id asset_voice --music-asset-id asset_bed --duration-seconds 12 --music-gain-db -18 --duck --new-asset-id asset_mix
```

Extend the example duration if the actual voice is longer. Explicit looping,
offset/trim, gain and fades prepare a bed; looping does not repair seams. Mixing
keeps original stems, returns exact 48 kHz stereo length and optional sidechain
ducking. It is not music composition. Add asset_mix and any SFX as explicit tracks,
then validate, preview, render, check encoded output and export the editable package.

## Rights and evidence

Music/SFX/font/model licenses and output-context rights are distinct. Kokoro
weights are Apache-2.0; the two original OPUS archives are CC-BY-4.0 even where
a model card differs. Generated speech and derived mixes default to
`unverified/internal` in the project ledger. Ask for human project-context and
output review when publication depends on it; do not mislabel model permission
as an unconditional advertising release.

Optional NVIDIA system libraries and the upstream GPU translation binary's Intel
dependencies retain their own terms and notices. They are not open-source assets.
The separate source-built Ruy CPU translation pack avoids MKL/Intel OpenMP/CUDA.
The base application and media remain separate from optional model packs.

Inspect actual WAV/PCM and encoded video. Automatic non-silence/decode checks,
still inspection, playback, listening and translation acceptance are separate.
The current extension has not achieved complete CapCut parity.

## Editable original scores and procedural effects (CLI0.1.59)

Use `music inspect-score --input score.json` before `music compose --project
PROJECT --input score.json --new-asset-id song --stems --apply --track-id
track_audio_1`. Inspect with `--dry-run` first when placement is uncertain.
The input format is `agent-music-score-v1`: tempo_bpm, duration_beats, seed,
master_gain_db, limiter and tracks. Each track has id, instrument, gain_db,
pan and notes; each note has id, start_beat, duration_beats, MIDI pitch and
velocity. Supported instruments are sine/pluck/bell/pad/kick/snare/hihat/sweep.

Example minimal score:
```json
{"format":"agent-music-score-v1","tempo_bpm":120,"duration_beats":8,
 "seed":42,"master_gain_db":-6,"limiter":"none","tracks":[
 {"id":"lead","instrument":"pluck","gain_db":-12,"pan":0,
  "notes":[{"id":"n1","start_beat":0,"duration_beats":2,"pitch":62,"velocity":0.7}]}]}
```

For editable electronic SFX, use `music effect --project PROJECT --preset
whoosh --duration-seconds 2 --new-asset-id whoosh`. Other presets: riser,
impact and chime. Save each revision under a new asset ID. Do not overwrite
an accepted audition. The source score, master, optional pre-master stems
and provenance live together under `assets/music-scores/ASSET_ID/` and
travel in portable project packages. Modify the score and recompose to edit.

This is 48kHz stereo analytical CPU synthesis, not a neural text-to-music
model. The agent must author notes and structure; a prose prompt is not
valid score input. CPU is the declared backend, with zero model forwards.
Do not start YuE2, download weights, or promise GPU music inference for this
command. Explicit tanh limiting is optional; no implicit normalization.
Clipping under limiter:none is rejected. Limits include600seconds,16tracks,
2048notes,1800 accumulated note-seconds and512MiB output PCM.

Present the actual WAV and distinguish it from a waveform/GIF diagnostic.
Listen/ask for client selection before claiming creative approval. Product
outputs default to unverified/internal rights; never infer commercial rights
from procedurally generated audio. The original C75 fixture has an explicit
CC0 source notice; that notice does not automatically license user inputs.
No neural generation, automatic semantic matching, structural rewriting or
seamless-loop repair is implemented by these commands.

Full schema, quotas and original16-second/5-track audition:
https://github.com/copypasteltd/agent-editor-kit/blob/main/docs/product/MUSIC_SCORE.md
Actual source WAV, MP4, editable score/package and GIF:
https://github.com/copypasteltd/agent-editor-kit/blob/main/docs/product/CASES.md#c75-source59-editable-score
