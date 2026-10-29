# Corrected text and CTC word boundaries

Use `subtitle align` for an existing local audio/video asset and explicit corrected
TXT/SRT. Register an existing native Python and standard Wav2Vec2 safetensors model
with `asr adapter register`; the base package contains neither Torch nor weights.
Use CUDA when the supplied runtime supports it; register CPU explicitly otherwise.
Moving from source to the installed release requires fresh implementation pins.

```powershell
& $avk subtitle align --project $project --asset-id speech --adapter-id words `
  --transcript $correctedText --output assets/alignment/words.json `
  --granularity whitespace --boundary-mode activity --timeout 600 --dry-run
# Inspect the plan, then repeat without --dry-run using the new output path.
```

- `ctc` is the default raw-character-peak mode. `activity` requires `whitespace`
  and uses actual PCM to estimate isolated words separated by silence.
- Keep `characters`, `raw_units`, final `units` and `activity.decisions` available
  to the customer. Shared/ambiguous regions preserve CTC rather than inventing
  internal word boundaries. The controller independently recomputes the PCM result.
- `posterior_geometric_mean` describes character emissions, not confidence in the
  expanded boundary. Audio activity may be speech, noise or music.
- `--apply --track-id captions --font-asset-id font` needs an existing unlocked
  subtitle track and font asset. Add source audio to an explicit audio track.
- Use strict SRT to bound long paragraphs; limits remain 1800s, 16384 codepoints,
  8192 tokens and 128 displayed ranges per applied cue. Unknown characters require
  explicit corrections; never silently convert script, delete words or distribute
  timestamps uniformly.

Inspect maximum start/end error against an independent reference, not just whether
the subtitles light up on schedule. Preserve the original 66.6667ms controlled
gate and all failed candidates. Synthetic word-block placement is not natural
phonetic ground truth. Continuous speech internals, Chinese characters, lyrics,
overlap and broad natural quality remain unaccepted under G15.

Full workflow, actual results and limitations:
[CTC activity alignment](https://github.com/copypasteltd/agent-editor-kit/blob/main/docs/product/CTC_ACTIVITY_ALIGNMENT.md).
