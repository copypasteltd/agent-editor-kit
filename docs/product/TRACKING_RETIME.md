# Shared-author tracking retime / 跟踪共享作者变速

CLI **0.1.30** / local **alpha.4-local.28** keeps tracked source, follower and
linked sound on one complete author clock during relative output retiming.
Use the explicit `float32-native-v1` pipeline and the locally installed runtime.
The existing legacy binding renderer retains its retime guard.

## Plan, inspect, apply

Invoke the single registered `$agent-ffmpeg-local-editor`. Set the launcher as
described in [local delivery](COMMUNITY_LOCAL_DELIVERY.md), then use the actual
sequence and clip IDs returned by ingestion/composition.

```powershell
& $avk version
& $avk capabilities
& $avk timeline edit --help
& $avk timeline edit --project $project --sequence-id $sequenceId --input $request --dry-run
& $avk timeline edit --project $project --sequence-id $sequenceId --input $request --expected-project-sha256 $hash
& $avk validate --project $project
& $avk preview frame --project $project --sequence-id $sequenceId --frame 0 --height 180
& $avk render --project $project --sequence-id $sequenceId --output $output
& $avk quality check --project $project --input $output
& $avk convert export --project $project --target-format package --output $package
```

Save a request as UTF-8 JSON, for example:

```json
{"action":"retime","clip_ids":["moving_source"],"transform":{"speed":2}}
```

For a separate main shot with overlapping source/follower layers, explicitly
retime synchronized content in that shot's interval:

```json
{"action":"retime","clip_ids":["shot_b"],"transform":{"speed":2},"sync_content":"retime","options":{"sync":true}}
```

The default `sync_content:ripple` policy still shifts/trims following content;
it does not implicitly retime every intersecting layer. Reverse, scalar slow
motion, existing authored speed curves and freeze share the same output-clock
wrapper. Transform speed is relative to the **complete current output**, not
an absolute replacement of the media's original speed.

Inspect `plan.steps[].shared_author_context`: original context IDs, retimed IDs,
readonly reference clips, selected child IDs and generated parent link ID.
Inspect `clock`, `retimed_members`, `tracking_binding_changes`, created sequences
and retained before/after pieces. The dry-run writes no author changes or media.
Apply only its `base_project_sha256`; stale requests reject.

## Editable representation and service behavior

| Part | Actual behavior |
|---|---|
| Dependency closure | Includes both source→follower and follower→source edges, chains, all saved source fragments and enabled linked content. Only intersections change output time; outside reference context is copied readonly. |
| Shared author graph | Full clips, original observations, source ranges, keyframes, crop, masks/effects, ROI reference and fragment author offsets remain editable in a shared child. No analysis/inference runs and no display-FPS binding keys are baked. |
| Parent output | `sequence_id` plus `sequence_clip_id` selects one complete authored layer. Other child peers remain available for tracking geometry but do not render again into that slot. |
| Blend and alpha | Each selected output retains its original place among unrelated layers. The Float32 host defers its mode and scalar opacity to parent composition, avoiding an extra alpha quantization. |
| Linked sound | A private, filtered child instance goes to the existing authored audio engine. Video/label selections cannot accidentally include the same sibling sound bus. Parent track audio controls stay on their original track. |
| Partial retime | Before/after pieces remain on the parent clock. Their routes point to surviving direct source pieces; the transformed interval keeps its binding inside the shared child. |
| Further edits | The generated parent link cohort keeps complete outputs together by default. Edit the shared child's original source/binding for live tracking changes. Explicit unlink/`linked:false` separates complete outputs; it does not make a new live binding between parent wrappers. |
| GPU | Eligible affine/normal Float32 composition uses the explicitly selected/probed GPU backend; tracking coordinate evaluation and the existing audio tempo engine retain their own implementations. |
| Portable format | Native package and agent JSON preserve selectors, observations and all sequences. OTIO/MLT/draft equivalence/native-PTS baking remains unavailable. The common video compiler rejects selectors instead of rendering the whole child silently. |

Locked required dependencies, disabled dependency sync locks, transition endpoints,
mixed side/main dependency selection and existing clip/layer/nesting/resource
budgets reject atomically. Nonconstant curves keep the existing bounded float
clock; natural tracking, source-mask/occlusion visibility, audio quality and
continuous preview performance require their separate goal acceptance conditions.

## C40 reproduction

Run `scripts/run_tracking_retime_case_20261026.py --run <new-id>` from the checkout
after installing/pinning the matching local runtime. The script imports the
versioned CC0 C36 package, calls the actual registered Skill, plans/applies 2x
retime, renders, exports/reimports and checks every output frame and sample.
Its readonly original frame oracle uses frames 0,2,…,34. The independent PCM
oracle applies native FFmpeg `atempo=2.0` to the original authored output, with
explicit 72000-sample padding/trimming; it is a deterministic routing/time-map
check. It does not establish speech/music naturalness or listening acceptance.

The [case catalog](CASES.md) and [validation record](../validation/跟踪共享变速实测_2026-10-26.md)
carry actual outputs and receipts once verified. Keep package/media hashes with
the client-facing preview; the GIF is silent and MP4 is a display preview.

<a id="c40-tracking-retime"></a>

## C40 · 跟踪共享作者变速 · CLI0.1.30

CC0动态裁切/运镜/ROI标签与合成双声道音轨；实际统一Skill执行2倍速，36帧3秒成为18帧1.5秒。全部Float32/解码画面、原生PTS和动态几何对应原偶数帧；完整72000双声道采样与独立tempo输出误差0。工程包及队列分别核验；实际GPU投影和清理留证。静态检查；无自然质量/连续播放/人工听审验收。

![Actual silent GIF](../assets/tracking-retime-20261026-r1/edited.gif)

[Before MP4](../assets/tracking-retime-20261026-r1/before.mp4) · [Edited MP4](../assets/tracking-retime-20261026-r1/edited.mp4) · [Editable package](../assets/tracking-retime-20261026-r1/editable-tracking-retime.aevpkg.zip) · [Source/rights](../assets/tracking-retime-20261026-r1/SOURCE.txt) · [Hashes](../assets/tracking-retime-20261026-r1/media-manifest.json) · [Workflow](TRACKING_RETIME.md) · [Evidence](../validation/跟踪共享变速实测_2026-10-26.md).
