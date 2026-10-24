# Offline visual semantic retrieval / 离线图文语义检索

[Unified entry](../SKILL.md) · [Runtime](runtime.md) ·
[Full guide](https://github.com/copypasteltd/agent-editor-kit/blob/main/docs/product/SEMANTIC_RETRIEVAL.md)

Use CLI 0.1.5 through this Skill's pinned installed launcher. This is part of K08,
not an additional Skill registration. Local images/video samples can be searched
with Chinese, English or an existing local reference image using SigLIP2.

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
batch and 64 tokens per query. Overlong requests are rejected, not truncated.
The query file is `{"queries":[{"id":"q1","text":"a cat"}]}`; never pass labels.

`auto` prefers an available GPU with enough free memory and records CPU fallback;
`cuda` is strict. CUDA BF16 and CPU float32 are tested on the current native host.
Batch queries to amortize model loading and large-file hashing. There is no
persistent model service. Cancellation terminates only the operation's child
process; startup cancellation has been exercised, not in-flight CUDA kernels.

## Human selection and editable ranges

Show the top actual previews with source asset IDs, sampled times and scores.
Use `preview_uri` only after resolving it under the project and verifying the
returned integrity information. Keep low scores and failure warnings visible.
Cosine similarity is not a probability. `--min-score` is an explicit filter, not
calibrated rejection. Queries without a matching asset still return candidates.

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
Chinese negation misselects coffee; both shark queries return grass candidates.
Natural actions, cross-shot identity, audio embeddings, semantic music matching,
large libraries and independent Agent task success remain unaccepted. Do not
claim complete G26 closure or full CapCut parity.
