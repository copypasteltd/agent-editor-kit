# Independent four-source audio separation

Use `audio separate-stems` for drums, bass, other instruments and vocals.
Read the installed `capabilities`, `audio adapter register --help` and
`audio separate-stems --help`. The installed CLI must be 0.1.6 or later.
The existing `audio separate` keeps its two-source or mid/side contract.

1. Ingest the original local video/audio, recording its actual rights.
2. Register an existing compatible HDemucs `.pt/.pth`, native Python/Torch/
   TorchAudio/NumPy and local evidence with engine
   `torchaudio-hdemucs-four-stem-local-v1`. Default `auto` prefers GPU;
   `cuda` is strict. No automatic model/runtime download.
3. Inspect the adapter, then dry-run and execute `audio separate-stems` with
   the returned source asset ID and a new `--prefix`. Use `--apply` to create
   four new editable audio tracks. Inputs and existing tracks are retained.
4. Show the actual four WAVs/IDs, model/device report and quality limitations.
   Review source/model rights and listen to the relevant outputs before using
   them for a client. Choose/mute tracks explicitly to avoid doubling an
   existing original mix. Preserve all stems for local revisions.

Example, after registration:

```powershell
& $avk audio separate-stems --project $aekProject --asset-id music --adapter-id music_four --prefix edit --apply --dry-run
& $avk audio separate-stems --project $aekProject --asset-id music --adapter-id music_four --prefix edit --apply --device auto --timeout-seconds 600
```

The fixed model sources are raw independent estimates with shared OLA;
`other` is not a constructed residual. Their sum is not projected to equal
the input. Report `raw_sum_*` diagnostics, float peaks and actual model calls.
There is no independent normalization/limiter. The model uses stereo 44.1kHz;
jobs are bounded to 1800s, 1–20s segments, 0–0.75 overlap. A cancellation marker
and finite overall timeout are supported. Auto fallback occurs at GPU preflight;
model/OOM errors are reported without an automatic retry on CPU.

Full instructions and real successes/failures:
[four-source workflow](https://github.com/copypasteltd/agent-editor-kit/blob/main/docs/product/FOUR_STEM_SEPARATION.md).
The current validation checkpoint license is unverified and it is not bundled.
Contract tests and controlled source metrics do not establish natural-music
quality, dereverberation or human listening acceptance.
