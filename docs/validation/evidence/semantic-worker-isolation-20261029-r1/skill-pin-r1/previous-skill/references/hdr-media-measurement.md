# Post-codec native media light metering

Use this when checking an actual encoded file, separate from `surface measure`
which measures the authored encoder RGB16 input. Both are available in the
pinned installed CLI 0.1.50; use this Skill's `scripts/run.ps1`.

```powershell
& $aekSkill surface measure-media --project PROJECT --input renders/master.mkv --signal-json SIGNAL.json --pixel-family yuv --yuv-matrix bt2020nc --yuv-range limited --chroma-location left --scan progressive --dry-run
```

Set `$aekSkill` to this Skill's `scripts/run.ps1`; use an absolute signal JSON
path. Remove `--dry-run` for actual all-frame decode. Example PQ signal:
`{"primaries":"bt2020","transfer":"pq-st2084","reference_white_nits":203}`.
HLG additionally requires display peak and system gamma; black lift is explicit.
For native RGB use `--pixel-family rgb` without YCbCr parameters. Do not infer
colour interpretation, display light or mastering values from file tags.

The input must exist within the project. The meter keeps original PTS and
positive native durations, including nonzero starts and VFR; unknown/zero
durations fail. Exposure gaps/overlaps are reported, not silently filled.
`--active-region X Y WIDTH HEIGHT` selects a region without claiming whole-canvas
acceptance. Only full streams are currently measured.

Default range policy rejects negative/over-one reconstructed RGB. An explicit
`--range-policy clip` permits clipping and reports whole-frame component counts.
Keep those counts with client-facing metrics. RGB16 is not quantized again:
native samples/YCbCr reconstruction become Float32 codes and Float64 light math.
Compare full decoded RGBA/clock digests, MaxRGB and CIE Y separately; a pre-codec
peak must not be presented as the encoded movie's peak.

Use `--cancel-file` for interruption. Preserve native reader process/thread
cleanup receipts. No project/media/SEI rewrite, inferred monitor calibration or
automatic MaxCLL/MaxFALL choice occurs. Digital declared-signal metering does not
prove natural HDR viewing, full ACES, dynamic metadata or physical display quality.
