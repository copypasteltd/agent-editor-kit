# Native portrait regions and protected retouch

Use this reference for explicit face-region parsing, skin/feature/hair selection,
region colour and smoothing, or a client preview of the selected regions.
Use `face` for the earlier landmark geometry controls. These are different tools.

Run the installed CLI through this Skill's `scripts/run.ps1`. Inspect
`portrait classes`, `portrait --help`, and the actual version before selecting
an operation. The portrait commands require CLI0.1.67 or later. A development
checkout does not upgrade an older installed Skill.

1. Ingest the actual source image or exact-CFR video and any protection mask.
2. Register the already present pinned BiSeNet19 `.safetensors`, native CUDA
   Python `.exe` and local source/license evidence using `portrait adapter register`.
   No implicit install, model download, remote code, CPU fallback or virtual machine.
3. Use `portrait parse` with a new labels ID, a new preview ID and an explicit
   face box. Moving boxes use `{"clock":"source-frame-index","keys":[
   {"frame":0,"box":[100,40,400,440]}]}`. Coordinates are source pixels,
   `[x0,y0,x1,y1]`; keys linearly interpolate and hold after the last key.
4. Show the actual returned palette preview alongside the original. The labels
   are lossless data, not a colour-graded client image. `portrait classes` lists
   exact IDs and palette colours. Review masks at more than one source frame.
5. Author a controls JSON and run `portrait retouch` with the labels ID and a
   new output ID. The source can be inferred from the labels. Add a registered
   `--protection-asset-id` for hands, glasses or other explicit protected pixels.
6. Show actual encoded before/after results and check complete video/audio,
   skin texture, identity and temporal stability. Export an editable project
   package. An asset and its recipe remain editable; neural inference is not
   automatically acceptable natural quality.

```json
{
  "feather_pixels": 2,
  "regions": {
    "skin": {"exposure_ev": 0.15, "smooth": 0.3, "saturation": 1.05},
    "lips": {"tint": [0.55, 0.08, 0.14], "tint_strength": 0.25},
    "hair": {"exposure_ev": -0.1}
  }
}
```

Seven disjoint edit groups: skin (including nose), brows, eyes, ears, lips,
neck and hair. Mouth interior, glasses, jewellery, clothes, hats and background
are excluded from these groups. A model can misclassify them: the class list is
not automatic occlusion protection. The model has **no hand/general-occluder class**.

Exposure is -2..2EV, saturation 0..2, smoothing and tint opacity 0..1. Tint is
three 0..1 sRGB components. Colour arithmetic uses the declared SDR transfer;
smoothing is a nine-tap edge-aware operation inside valid region support.
Feathering is inward only, 0..8 source pixels. A black protection mask permits
editing; **any nonzero decoded gray value completely protects that pixel**.
A static mask repeats for all frames; an animated mask needs the same canvas,
exact-CFR frame times and count. This is explicit protection, not hand tracking.

All source alpha, hidden RGB, unselected RGB and explicitly protected pixels
must remain bit exact. Labels are gray PNG for images or lossless FFV1/NUT for
video. Retouched images are RGBA PNG; movies use lossless RGBA/QTRLE with every
source audio stream retained as independently verified Float32 PCM.

Use `--recipe-asset-id` for a deliberate rerun, always with fresh output IDs.
Overrides are explicit. `--clear-protection` removes an inherited protection
mask; omitting a mask preserves it. A retouch rerun reuses existing labels and
does not run the parser again. Inspect actual GPU/operator counts in the receipt.
Optional `--apply` uses explicit video/audio tracks. The current convenience
apply accepts at most one audio stream; multiple streams remain in the output
and require separate timeline routing. Images accept an explicit clip duration.

Supported input: one ordinary 8bit SDR image or zero-start, unrotated,
square-pixel exact-CFR video, up to 120FPS/600seconds/18000frames and
3840×2160 total pixels. Default `--max-frames` is 1800; storage and time budgets
are explicit. HDR, implicit VFR resampling, full makeup/body reshaping, hair
generation, relighting, automatic identity tracking and a temporal model remain
outside this implementation. Do not imply that these gaps are closed.

Inspect bounded failure diagnostics. Cancel/timeout must reclaim owned workers;
output conflicts preserve foreign files. Never overwrite old IDs to retry.
Source, code, weights and generated-output uses need separate rights records;
new outputs default to internal/unverified. Do not publish them as cleared media.
