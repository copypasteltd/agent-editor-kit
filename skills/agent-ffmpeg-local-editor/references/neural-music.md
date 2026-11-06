# Native neural music / CLI0.1.66

Use this for local original instrumental music or explicit singing requests.
`music compose` remains the separate CPU score synthesizer. `music generate`
uses ACE-Step1.5 Turbo through an existing native ComfyUI core, without a GUI,
HTTP service, shared queue, Docker or WSL. Keep one public Skill entry.

The application bundle does not include the 10 GB model pack or the external
native Torch/ComfyUI environment. Register the four pinned safetensors and
that existing environment explicitly; do not substitute YuE2, a quantized
checkpoint or an online service. Model and native-core declarations/limits:
https://github.com/copypasteltd/agent-editor-kit/blob/v0.1.0-alpha.4/docs/product/NEURAL_MUSIC_GENERATION.md
The local pack contains diffusion_model.safetensors, text_encoder.safetensors,
language_model.safetensors and vae.safetensors with the exact built-in hashes.

Use the exact CLI0.1.66 launcher in this Skill. The registration evidence and
license reference must be local files. URLs in the source declaration are
research metadata, not runtime license arguments. Complete model, interpreter,
ComfyUI source/resource and implementation checks precede execution. Cold
integrity reads can take minutes and are distinct from GPU inference time.

```powershell
& $avk music generator-adapter register --project $project --adapter-id ace15 `
  --model-path $models --runtime-root $core --executable $nativePython --evidence $evidence
& $avk music generator-adapter inspect --project $project --adapter-id ace15
& $avk music inspect-generation --input $request
& $avk music generate --project $project --adapter-id ace15 --input $request `
  --new-asset-id music01 --dry-run
& $avk music generate --project $project --adapter-id ace15 --input $request `
  --new-asset-id music01
```

Request JSON uses format `agent-neural-music-v1`, prompt, explicit instrumental,
lyrics, duration_seconds, bpm, language, keyscale, timesignature, seed, steps and
generate_audio_codes. Keep the client's original prompt and lyrics. Prompt is
1..4000 characters; lyrics at most 12000. Instrumental requires empty lyrics;
singing requires nonempty lyrics and an explicit language. Schema support for
languages is not acceptance of pronunciation or exact lyric delivery.

Duration accepts 10..600 seconds in 0.04 second increments. Only an actual observed
range/device is a tested range; do not promise long-song quality from this bound.
Default 8 steps uses Euler/simple/CFG1/flow shift3/multiplier1. BPM 10..300, signature
2/3/4/6, key names such as D minor, nonnegative 63 bit seed. Set
generate_audio_codes explicitly when changing the language-model path.

Text, optional language-model, diffusion and VAE forwards must actually execute
on CUDA 0. CPU weight offload is allowed; CPU neural inference fallback is not.
The exact output is 48 kHz stereo Float32 WAV: no padding, looping, resampling,
normalization or cropping to pretend that the requested duration was generated.
Check the model forward counts/devices, native samples and full PCM roundtrip.

The generator registers a static loading policy and selects the native safetensors
pread backend for all four pinned components. Unsupported backends fail;
never retry with mmap, pickle or CPU neural inference. Read local_weight_reads
for actual file/backend/open observations. The runtime parser must declare
the required flags; optional frontend --offline is used only if declared.
Worker network blocking and offline environment settings remain mandatory.

Model elapsed_seconds now includes runtime imports. Review the separate
runtime_import_seconds, checkpoint loading and generation/decode timings.
Generation timings can include device transfers; they are not GPU kernel time.
An earlier adapter pins earlier implementation/settings bytes: re-register
explicitly with a new adapter ID after upgrading. Existing audio and recipes
remain reusable; do not silently rewrite the old registration or original WAV.

Listen to the complete local WAV before selecting it for a client. Preserve the
asset ID, request, model/runtime hashes, seed and actual sample count. Show real
auditions; a waveform card is not listening or music-quality acceptance. Review
phrasing, instrumentation, structure, lyric delivery and level separately.
Generated rights remain unverified/internal until explicitly reviewed; model
license declarations do not automatically approve an individual output.

After selection, use --apply --track-id TRACK for an unlocked independent audio
track; inspect overlaps first. The saved source.music_generation recipe is an
editable request/provenance record, not MIDI, stems or editable musical notes.
Use --recipe-asset-id music01 --new-asset-id music02 to rerun its original
request with the same model/runtime bytes; edit a new JSON for a new request.
Seeds do not guarantee identical bytes across devices or library versions.

Set --cancel-file, --timeout-seconds and --storage-budget-mib as needed. The
default 1800 second budget covers the worker/output checks after command preflight.
Keep original assets and snapshots; a new result uses a new ID. On failure,
inspect the bounded redacted diagnostic and verify process cleanup before retry.
Export a project package and replay the whole WAV/recipe/encoded AV. The package
retains external model pins; it does not silently bundle or download the models.
Natural listening, broad singing/language/style quality, clean-host setup and
complete CapCut equivalence remain separate acceptance work.

Historical actual CUDA generation was verified on CLI65. Confirm the actual CLI66 receipts before describing new-version inference as accepted. CLI66 reports concurrent output occupation as `MUSIC_GENERATION_OUTPUT_CONFLICT` and other filesystem failures as `MUSIC_GENERATION_IO_FAILED`; inspect the transaction outcome, preserve foreign files and use a fresh asset ID for a deliberate retry.
