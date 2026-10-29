# Reviewed ad brief → editable variants → scoped revision

Use `ad storyboard`, `ad build` and `ad revise` for a brief with explicit local
asset selections and reviewed copy. These commands compile creative decisions
into editable sequences; they do not select footage semantically or invent claims.
Use existing understanding/search commands when choosing actual asset IDs.

Ingest picture, audio, font and music assets first. A brief has:

```json
{
  "id": "product",
  "product": "Actual product",
  "audience": "Actual audience",
  "cta": "Reviewed call to action",
  "caption_style": {"font_asset_id": "font"},
  "shots": [
    {"id": "hook", "asset_id": "picture_a", "text": "Reviewed opening", "weight": 1},
    {"id": "proof", "asset_id": "picture_b", "text": "Actual demonstration", "weight": 1,
     "voice": {"asset_id": "complete_voice"}},
    {"id": "cta", "asset_id": "picture_c", "text": "Reviewed CTA", "weight": 1}
  ],
  "music": {"asset_id": "music", "gain_db": -24},
  "variants": [
    {"id": "wide", "canvas": {"width": 1280, "height": 720}, "duration_seconds": 9},
    {"id": "vertical", "canvas": {"width": 720, "height": 1280}, "duration_seconds": 12}
  ]
}
```

Replace example asset IDs with actual returned IDs. IDs are at most 32 characters.
Each variant can set `shot_ids` and per-shot `overrides` for different openings,
copy or selected media. `weight` apportions complete frames at the project FPS.
Source video audio is included only with `include_source_audio: true`.
`fit` is `fit`, `fill` or `stretch`; review reframing for each actual canvas.

```powershell
& $avk ad storyboard --project $project --input "$project/brief.json" --output "$project/validation/ad-plan.json" --dry-run
& $avk ad storyboard --project $project --input "$project/brief.json" --output "$project/validation/ad-plan.json"
& $avk ad build --project $project --input "$project/validation/ad-plan.json"
& $avk preview frame --project $project --sequence-id ad_product_wide_sequence --frame 0
& $avk render --project $project --sequence-id ad_product_wide_sequence --output "$project/renders/wide.mp4"
```

Plans go to new files inside `validation/`. Dry-run writes neither plan nor
project. Planning writes only the plan. Build checks the original project,
recomputed plan and actual input bytes, saves a snapshot and commits atomically.
Rerun planning after an intervening edit; do not rewrite digests to force a plan.

For reviewed same-language SRT, `dub subtitles --from zh-Hans --to zh-Hans`
(or en/en, zh-Hant/zh-Hant) preserves the text and initializes only the voice
model once for the batch. Prefer configured GPU. No translation pack is needed.
Inspect actual complete WAVs. A voice that exceeds a shot window is rejected;
explicitly adjust timing or regenerate the complete sentence first.

For local changes, write a request such as:

```json
{"campaign_id":"product","variant_ids":["wide"],"shots":[{"id":"cta","asset_id":"replacement","text":"Reviewed revision"}]}
```

Run `ad revise --project ... --input ... --output ...`, inspect the plan, then
`ad build`. Only selected fields/variants/shots change. Other clips and manual
styles/effects/keyframes stay intact. Text changes do not regenerate speech;
provide a new `voice` explicitly, or `voice: null` to remove it. Split or missing
targets and locked tracks require explicit resolution instead of bulk replacement.

Preview and render every selected variant, review actual picture/copy/sound and
rights, then export an editable package and verify a new import. Decoder equality
and process checks do not establish natural quality, human listening or autonomous
Agent task success. The real example and full schema are in
[the product guide](https://github.com/copypasteltd/agent-editor-kit/blob/main/docs/product/AD_STORYBOARD.md).
