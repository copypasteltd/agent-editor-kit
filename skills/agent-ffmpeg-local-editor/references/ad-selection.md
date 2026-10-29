# Calibrated semantic ad selection

Use installed CLI0.1.58 or newer through this unified Skill launcher. Start
with `version` and `capabilities`; `ai.ad_storyboard` must include `ad.select`.
This connects sampled visual retrieval to ordinary editable ad plans. The
caller still supplies approved factual copy, intended audience, music and
variants. Similarity is not evidence for a product claim or whole-shot action.

## Prepare the library and request

Register a local semantic adapter, build an index and calibrate it against
explicit licensed positive/negative examples. Use the same actual device and
device index for calibration and selection. Prefer CUDA when available; a CPU
fallback cannot silently use a CUDA acceptance profile. Read the semantic
module for model registration, dependencies, budgets and rights.

The JSON input wraps the existing storyboard brief:

```json
{
  "brief": {
    "id":"campaign", "product":"Approved product", "audience":"Approved audience",
    "cta":"Approved call to action", "caption_style":{"font_asset_id":"font"},
    "shots":[{"id":"opening","text":"Approved factual caption"}],
    "variants":[{"id":"vertical","canvas":{"width":1080,"height":1920},"duration_seconds":6}]
  },
  "queries":[{"id":"opening","text":"A cup of coffee on a table"}],
  "unique_assets":true,
  "unique_content":true
}
```

Replace example IDs with registered project assets. A queried shot omits
`asset_id` and `source_in_tick`; fixed shots can still declare them. Query IDs
match shot IDs. Optional include/exclude clauses use the semantic query
contract. Keep a candidate limit large enough for competing shots (current
CLI limit1..20); a candidate omitted by that limit cannot be assigned.

## Select, build and review

Using `$avk` as defined in SKILL.md:

```powershell
& $avk ad select --project E:/video-work/demo --input E:/video-work/demo/brief.json `
  --output E:/video-work/demo/validation/selected.json --index-id visual `
  --calibration-id accepted-cuda --device cuda --kind image --limit 20 --dry-run
```

Dry-run checks the request and index/profile binding; it returns no selected
plan and performs no model forward. Run the same command without `--dry-run`
to select. Set an explicit adequate `--timeout-seconds` for model/artifact
loading; a timed-out attempt is a failure, not a selection receipt.

```powershell
& $avk ad build --project E:/video-work/demo --input E:/video-work/demo/validation/selected.json
```

Selection filters current source hashes, verified rights status, required
source audio and source length across every requested variant, then maximizes
the quantized similarity sum globally. CLI58 groups exact source SHA256
aliases before joint assignment, and reserves the content of fixed shots.
`unique_content` defaults to `unique_assets` (normally true). Set
`unique_content:false` with `unique_assets:true` for the old ID-only behavior;
set both false for deliberate reuse. Both options require actual booleans.
Missing or malformed SHA256 cannot silently fall back to asset IDs.
This is exact file identity, not perceptual or cross-transcode deduplication.

Inspect each shot's rationale receipt: original query, index/profile IDs,
source hash/start, score, required duration and preview reference. Validate
and render every variant, show actual previews to the client and use ordinary
`ad revise` for targeted changes. Preserve editable exports and verify complete
decoded video/PCM when package replay matters. Existing500-look previews are
available for an independent style selection; they are not semantic evidence.

A verified rights record is not publication clearance. Check permitted uses,
restrictions and source licenses before sharing the selected media. Calibrated
similarity is empirical, not a no-error guarantee. Review the complete shot,
copy, crop, rhythm and audio; natural ad quality and full parity are separate.

Full contracts and maintained examples:
https://github.com/copypasteltd/agent-editor-kit/blob/main/docs/product/AD_SEMANTIC_SELECTION.md

CLI55 inherits command budgets while waiting for native processes. Keep cold-load latency separate from neural inference time; preserve failures and use an explicit adequate budget, not a retuned acceptance threshold.

CLI56 pins its own application package, then restores the native model runtime dependency search order. Controller-bundled NumPy/Pillow must not silently replace the registered model runtime. Keep runtime/version/path fingerprint checks enabled; register fresh implementation bindings after code changes.

## Explain source selection to a client

Inspect `uniqueness_group`, source SHA256 and the original preview reference.
Show the actual selected source, crop and complete shot before approval.
The C74 demonstration has real byte-identical aliases, default/ID-only
selection, editable timelines and120-frame complete RGBA package replay:
https://github.com/copypasteltd/agent-editor-kit/blob/main/docs/validation/CLI58内容去重实测_2026-10-29.md
Its search scores are explicitly synthetic; do not present it as model or
natural-semantic accuracy. A low score, absent candidate or inadequate
candidate limit cannot be repaired by inventing a preview or selection.
