# Move an indexed and calibrated project

Use the pinned CLI 0.1.15 installation. Read [semantic-retrieval.md](semantic-retrieval.md)
for explicit adapter/index/device-profile setup and candidate review.

```powershell
& $avk convert export --project $sourceProject --target-format package --output $projectZip
& $avk convert import --input $projectZip --output $restoredProject
& $avk validate --project $restoredProject
& $avk semantic search --project $restoredProject --index-id images-v1 --query '一只猫，不是一杯咖啡' --kind image --calibration-id accept-cuda --device cuda
```

Set those variables to actual local paths, use a new/empty destination, and use
the real index/profile IDs. Inspect exit code, `ok/status/errors/warnings`, and
the returned conversion report. A dry run or general validation alone does not
establish that the final query executes. Present actual returned preview images,
IDs, sampled times, empty results and known mistakes for human review.

The package preserves owned `assets/` directories. For an explicitly allowed
external source it derives only new URI-bearing index/profile fingerprints and
corresponding Rights Ledger revisions. Vectors, sample times, dataset bytes,
observations, fit/cutoff, devices and adapter/model/runtime pins stay unchanged.
Conversion performs no model inference, downloads or implicit re-registration.

Import checks inner source/index/vector/preview/profile/dataset and derived
rights hashes in fresh staging before publishing the destination. A damaged
legacy 0.1.10 flattened semantic ZIP is rejected; re-export from its intact
source with the new version. Automatic repair of that damaged ZIP is unavailable.
If that intact source pins an unavailable installation, use the explicit
runtime-upgrade command below. Package conversion alone does not rebind adapters.

Native model weights, Python packages and implementation pins remain separate.
Same-host relocation can reuse them if their original pins still match. Local
license-evidence paths may also need review after moving hosts.

## Explicit installation-path upgrade

```powershell
& $avk project upgrade-semantic --project $restoredProject --adapter-id siglip2 --new-adapter-id siglip2_current --id-prefix current --dry-run
& $avk project upgrade-semantic --project $restoredProject --adapter-id siglip2 --new-adapter-id siglip2_current --id-prefix current --idempotency-key upgrade-current-1
```

Use actual existing source IDs and unused target IDs. The old installation may
be absent. All 19 semantic implementation modules must match its recorded
SHA/length exactly; model, Python, native dependency and evidence pins must
still verify. Changed bytes produce a rebuild-required/dependency-changed error;
explicitly register and rebuild instead. Never edit old pins to bypass a failure.

The command preserves the original records and creates separate copies of
vectors/previews/datasets with new bindings. It preserves cutoff/fit/observations,
device and query protocol, with zero new model forwards. Use returned
`index_mappings` / `calibration_mappings` for an actual CPU/CUDA search. A dry run
writes no project assets. Existing timeout/cancel, transaction, snapshot,
idempotency and managed-job recovery apply. Maximum 32 indexes, 64 profiles,
4096 preview rows and 512 MiB copied payload; allow the reported disk budget.

[Full upgrade workflow and limits](https://github.com/copypasteltd/agent-editor-kit/blob/main/docs/product/SEMANTIC_RUNTIME_UPGRADE.md)

An identical decision after migration preserves errors too. The familiar-image
regression still includes elephant/guitar false accepts and a clock false
rejection. Migration does not close natural search quality, cross-host delivery,
all interchange formats or complete CapCut parity.

[Complete package workflow](https://github.com/copypasteltd/agent-editor-kit/blob/main/docs/product/SEMANTIC_PROJECT_PACKAGE.md)
