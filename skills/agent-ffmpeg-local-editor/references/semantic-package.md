# Move an indexed and calibrated project

Use the pinned CLI 0.1.12 installation. Read [semantic-retrieval.md](semantic-retrieval.md)
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
If that intact source still pins an older installed implementation, conversion
can preserve its data but cannot make it executable under the new Skill. Use new
adapter/index/profile IDs and explicitly rebuild for the current installation.

Native model weights, Python packages and implementation pins remain separate.
Same-host relocation can reuse them if their original pins still match. Moving
or changing the installed implementation/model/runtime requires explicit adapter
registration and rebuilding indexes/calibrations; never edit pins to bypass a
failure. Local license-evidence paths may also need review after moving hosts.

An identical decision after migration preserves errors too. The familiar-image
regression still includes elephant/guitar false accepts and a clock false
rejection. Migration does not close natural search quality, cross-host delivery,
all interchange formats or complete CapCut parity.

[Complete package workflow](https://github.com/copypasteltd/agent-editor-kit/blob/main/docs/product/SEMANTIC_PROJECT_PACKAGE.md)
