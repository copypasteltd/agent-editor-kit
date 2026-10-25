# Interrupted local jobs

Use for cancellation, timeout or an interrupted four-source/subtitle-dubbing job.
Inspect `project recover --help` through the pinned installed launcher first.

```powershell
& $avk project recover --project $project --cleanup-jobs --dry-run
& $avk project recover --project $project --cleanup-jobs
& $avk validate --project $project
```

Default `project recover` restores metadata only. `--cleanup-jobs` restores a
pending transaction first, then inspects the durable managed workspaces in
`cache/managed-jobs/`. Check `data.job_recovery.jobs`: the native lease protects
active jobs; only matching filesystem identity/hash and unreferenced derived
outputs can be removed. Committed assets and active local Rights Ledger evidence/
license references survive. Changed outputs, unknown or
blocked directories, user media and legacy unmanaged caches are preserved.
Dry-run makes no metadata or file changes. Keep preserved evidence and inspect
the reason; do not replace recovery with a blanket cache deletion.

Subtitle dubbing overflow deliberately returns `preserved_for_review` and keeps
complete WAVs and failure.json. Explicit cleanup can remove this uncommitted
directory: save required review samples first. Current budgets are 2MiB of
manifest data/4096 published outputs and 10,000 scanned entries per job, at most
256 jobs per scan. No other model cache automatically gains this contract.

Normal transactional responses may expose `data.job_cleanup`. If the owner was
hard-stopped, the private native process job ends descendants launched through
the shared helper; explicit recovery handles abandoned files. Other custom
process paths and other model caches do not gain this recovery contract.

This is cleanup/recovery, not inference checkpoint resume. Preserve sources and
failure records, use a fresh prefix when retrying separation, and do not claim
power-loss, disk-exhaustion or general long-concurrency acceptance. Upgrading a
four-source adapter requires explicit registration of the new implementation
pins; never silently rewrite old hashes or infer model redistribution rights.
