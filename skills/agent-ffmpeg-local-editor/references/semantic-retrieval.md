# Offline visual semantic retrieval / 离线图文语义检索

[Unified entry](../SKILL.md) · [Runtime](runtime.md) ·
[Full guide](https://github.com/copypasteltd/agent-editor-kit/blob/main/docs/product/SEMANTIC_RETRIEVAL.md)

Use CLI 0.1.10 through this Skill's pinned installed launcher. This is part of K08,
not an additional Skill registration. Local images/video samples can be searched
with Chinese, English or an existing local reference image using SigLIP2.

CLI 0.1.10 has a verified migration gap: the new indexed/calibrated project
exports/imports and passes general `validate`, but search on that imported copy
fails with `SEMANTIC_INDEX_INVALID` / `Manifest outside project semantic asset tree`.
Do not promise portable profiles or rewrite pins. Re-register, rebuild and
recalibrate explicitly after moving; that workaround has not been verified by
this case. Ordinary diagnostic image-card package rendering passed separately.
[Actual failure and preview](https://github.com/copypasteltd/agent-editor-kit/blob/main/docs/assets/semantic-decision-20261025-r1/demo-installed-r1/KNOWN_ISSUE.md).

## Existing runtime and explicit registration

Read the checkout's `local/agent-ffmpeg/runtime.json`; resolve `semantic_config`
to its existing `agent-local-semantic-runtime-v1` JSON profile. Required fields
are `python_executable`, `model_path`, `evidence`, `creator`, `license_spdx` and
`verification_status`. Pass those values explicitly when registering each project.
Missing paths are a capability gap. Do not invoke ComfyUI, download models, use
Docker/WSL or silently switch to another runtime. The approximately 1.5GB weights
and native Torch runtime are separate from the base application ZIP.

With `$avk` set as in SKILL.md and `$project` an existing project:

```powershell
$semantic = Get-Content -LiteralPath $semanticProfilePath -Raw -Encoding utf8 | ConvertFrom-Json
& $avk semantic adapter-register --project $project --adapter-id siglip2 `
  --python-executable $semantic.python_executable --model-path $semantic.model_path `
  --evidence $semantic.evidence --creator $semantic.creator `
  --license-spdx $semantic.license_spdx --verification-status $semantic.verification_status
& $avk semantic adapter-inspect --project $project --adapter-id siglip2
```

Registration pins selected model, implementation and native dependency bytes;
it does not perform a model forward. Changed runtime bytes require new explicit
registration and a rebuilt index. This is not a complete OS dependency closure.

## Index and query

Ingest existing media normally, then use returned asset IDs:

```powershell
& $avk semantic index --project $project --index-id campaign-v1 --adapter-id siglip2 `
  --asset-id asset_product --asset-id asset_scene --sample-interval-seconds 2 --device auto
& $avk semantic verify --project $project --index-id campaign-v1
& $avk semantic search --project $project --index-id campaign-v1 `
  --query '木桌上的一杯咖啡' --limit 5 --device auto
& $avk semantic search --project $project --index-id campaign-v1 `
  --queries-file $queriesPath --kind video --all-samples --limit 5 --device cuda
& $avk semantic search --project $project --index-id campaign-v1 `
  --image $referenceImage --kind image --device cpu
```

`--all-visual-assets` explicitly selects the entire project instead of individual
IDs. Sampling retains actual native PTS and deduplicates held VFR frames. Budgets
are 512 source assets, 4,096 rows, 128 requested samples per video, 128 queries per
batch and 64 tokens per embedded clause. Overlong requests are rejected, not truncated.
The query file is `{"queries":[{"id":"q1","text":"a cat"}]}`; never pass labels.

`auto` prefers an available GPU with enough free memory and records CPU fallback;
`cuda` is strict. CUDA BF16 and CPU float32 are tested on the current native host.
Batch queries to amortize model loading and large-file hashing. There is no
persistent model service. Cancellation terminates only the operation's child
process; startup cancellation has been exercised, not in-flight CUDA kernels.

## Explicit conditions and empirical rejection

Default `--query-mode clauses` preserves the original query and exposes its
`include` and `exclude` conditions. The bounded grammar recognizes forms such as
`一只猫，不是一杯咖啡` or `a cat, not a cup of coffee`. For reviewed conditions,
provide an explicit query file:

```json
{"queries":[{"id":"q1","text":"一只猫，不是一杯咖啡","include":["一只猫"],"exclude":["一杯咖啡"]}]}
```

Every positive condition must hold on the same sampled frame. Its minimum cosine
must exceed every exclusion score. Exclusions are relative visual evidence,
not object-absence detection. Ambiguous/unparsed negation returns
`SEMANTIC_QUERY_SCOPE_REQUIRES_REVIEW`. The conservative grammar can also flag
affirmative Chinese words containing `不`; preserve the customer's wording and
review scope rather than silently changing its meaning. Search rows accept no
expected-answer labels.

For automatic empirical acceptance, first calibrate the current index using a
separately reviewed local file with exactly `format`, `scope` and `queries`.
Use format `agent-semantic-calibration-set-v1`, 32–128 distinct queries, at least
16 positive and 16 absent-from-index. Rows contain `id`, `text`, optional
`include`/`exclude`, and `expected_asset_ids`; `[]` means no matching indexed asset.
The controller uses labels after embedding; labels never go to the worker.
Freeze a separate evaluation set before inference, and retain its failures.
Do not tune on those results and continue calling the set held out.

```powershell
& $avk semantic calibrate --project $project --index-id campaign-v1 `
  --calibration-id accept-cuda --input $calibrationPath --kind video `
  --false-accept-rate 0.05 --minimum-coverage 0.75 --device cuda
& $avk semantic calibration-list --project $project
& $avk semantic search --project $project --index-id campaign-v1 `
  --queries-file $queriesPath --kind video --calibration-id accept-cuda --device cuda
```

The false-accept control selects an empirical negative-score cutoff; coverage
also requires correct positive top-1 matches. Reject-all cannot pass.
`SEMANTIC_CALIBRATION_QUALITY_FAILED` preserves fit diagnostics without registering
a usable profile. Normal publication failures roll back; hard-crash recovery of
this new job is not yet a managed-job guarantee.

Profiles bind index/model/implementation/query protocol, `--kind`, actual device
and device index. Build a separate CPU profile with `--device cpu` for CPU use.
When `auto` falls back, a different-device profile fails explicitly; inspect the
actual provider and select or calibrate the corresponding profile. Strict CUDA
examples avoid a silent change of profile scope. `search --dry-run` verifies
binding without inference; `calibration-list` only lists registrations.

Changed semantic implementation or relocated dependencies require explicit
adapter registration and a rebuilt index. Do not rewrite stored hashes to bypass
verification. New media needs a new index/profile; old indexes still cover only
their selected assets/samples. Use new IDs to retain previous evidence.

Present decisions accurately:

- `calibrated_match`: show the actual preview, asset/source point, conditions,
  cosine score, calibration ID and review requirement. Acceptance is empirical.
- `no_calibrated_match`: explain that no candidate passed this profile; do not
  fabricate a selection or claim absence from every original source frame.
- `candidates_require_review`: show results as candidates for manual selection.

Reference-image search remains candidate retrieval without calibrated rejection.
`--query-mode raw` retains original whole-sentence ranking for reproduction;
it cannot use a calibration profile and does not reliably understand negation.

## Human selection and editable ranges

Show the top actual previews with source asset IDs, sampled times and scores.
Use `preview_uri` only after resolving it under the project and verifying the
returned integrity information. Keep low scores and failure warnings visible.
Cosine similarity is not a probability. `--min-score` alone is an explicit filter,
not calibrated rejection. Without a profile, absent queries can return candidates.
Profiles also retain false accepts and false rejections; show both to the client.

After selection, use `editable_reference.asset_id` and `source_in_tick` for an
`append_clip` operation. Inspect the source and author a duration separately:
`point_sample_only=true` and `duration_requires_review=true` do not define an
event boundary. Preserve source/rights records and perform normal render checks.
Search leaves project metadata/rights unchanged and writes task cache evidence.

## Evidence and limitations

[All 20 query results](https://github.com/copypasteltd/agent-editor-kit/blob/main/docs/assets/semantic-20261025-r1/all-query-results.png)
show the complete frozen positive/negation/out-of-domain set. On this small
familiar static-image set, development CUDA and CPU achieve 16/16 positive top-1
and mean asset recall@3 of 1.0. Six synthetic-sequence timestamps and cropped-cat
reference retrieval pass. These images may have occurred in model training.
Historical raw Chinese negation misselects coffee; both shark queries return grass.
Those original failures remain reproducible. New clauses/calibration are assessed
separately in the full guide, including positive recall and absent-query errors.
Query-wording independence on familiar images is not independent footage,
human acceptance or an action/identity/audio benchmark.
For the new installed profile, show the
[complete 80-decision gallery](https://github.com/copypasteltd/agent-editor-kit/blob/main/docs/assets/semantic-decision-20261025-r1/installed-r1/index.html)
and its failure cards alongside the historical raw results. The gallery contains
actual returned previews and empty decisions, not generated substitute images.
Natural actions, cross-shot identity, audio embeddings, semantic music matching,
large libraries and independent Agent task success remain unaccepted. Do not
claim complete G26 closure or full CapCut parity.

For an indexed/calibrated project package, read [semantic-package.md](semantic-package.md).
The CLI 0.1.11 path preserves the owned tree and checks semantic data before
import publication. The old 0.1.10 failed package remains historical evidence.
