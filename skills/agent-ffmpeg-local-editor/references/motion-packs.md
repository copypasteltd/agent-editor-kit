# Reusable camera motion / 可复用运镜

Use for saving an accepted animation, parameterized shot movement, or reusing
motion across local projects/durations. CLI 0.1.16 adds `motion pack`; the twelve
original `motion apply` presets remain separate and unchanged.

Inspect `motion pack list` and `motion pack inspect --name ID`. Six builtin IDs:
`orbit_focus`, `arc_push`, `bezier_sweep`, `whip_settle`, `breathe_float`,
`detail_scan`. Use the [actual contact sheet](../assets/motion-packs/contact-sheet.png)
for an initial client choice; full original/MP4/GIF/JSON previews and parameter
ranges are in the [motion guide](https://github.com/copypasteltd/agent-editor-kit/blob/main/docs/product/MOTION_PACKS.md).
These examples use a self-authored graphic, not the client's footage. Render a
short actual-footage preview after the client selects an ID and amount.

```powershell
& $avk motion pack inspect --name arc_push
& $avk motion pack apply --project $project --sequence-id $sequence --clip-id $clip --name arc_push --param travel=0.18 --param zoom=0.12 --dry-run
& $avk motion pack apply --project $project --sequence-id $sequence --clip-id $clip --name arc_push --param travel=0.18 --param zoom=0.12 --idempotency-key motion-shot-1
```

Use actual IDs and inspect the returned compiled keys, validation, warnings and
snapshot. Existing touched properties reject unless `--replace` is explicit;
replacement drops the *whole* prior property track, including outside points.
Other properties and source/speed/reverse fields remain. Start/end ticks are on
the current visible clip output, not source media or global timeline time.
Presentation-window offsets are applied to the authored clock automatically.
Outside a partial interval, the new endpoint values hold.

`motion pack create --name ID --output NEW.json` writes a portable parameterized
recipe. For existing animation:

```powershell
& $avk motion pack capture --project $project --sequence-id $sequence --clip-id $clip --id customer_motion --title 'Accepted motion v1' --creator 'Credited creator' --license LicenseRef-UNVERIFIED --output 'E:/video-work/customer-motion.json'
& $avk motion pack apply --project $otherProject --sequence-id $otherSequence --clip-id $otherClip --input 'E:/video-work/customer-motion.json'
```

Capture preserves the **complete authored** transform curves, including hidden
parts of a trimmed clip and native easing/Bezier controls. Project idempotency
keys are supported only for apply; capture/query reject them without writing
project records. Additive scale may use negative deltas; resolved scale must
remain .001..100. Capture emits normalized
rational times and absolute values with no inferred parameters. Repeat
`--property transform.scale` etc. to select properties. Creator/license are
declarations; unknown rights remain unverified. The recipe contains no media.

Generated paths have 65 linear samples, not an analytic 3D camera or automatic
subject follow. Short intervals causing tick collisions reject; large offsets
can expose the background. Locked tracks and tracking relationships reject.
After applying, ordinary keys and the embedded recipe travel with the editable
project package; the original standalone JSON is not needed for rendering.
Keep normal preview/render/pixel review and source-rights checks.
