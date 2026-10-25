# Interrupted local jobs

Use for cancellation, timeout or an interrupted four-source, subtitle-dubbing or
`semantic adapter-register/index/calibrate/search` job (CLI 0.1.12 and later).
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
license references survive. For a semantic index/calibration directory, any
asset or active rights reference inside protects the entire published directory.
Changed outputs, unknown or
blocked directories, user media and legacy unmanaged caches are preserved.
Dry-run makes no metadata or file changes. Keep preserved evidence and inspect
the reason; do not replace recovery with a blanket cache deletion.

Subtitle dubbing overflow deliberately returns `preserved_for_review` and keeps
complete WAVs and failure.json. Explicit cleanup can remove this uncommitted
directory: save required review samples first. Semantic jobs likewise keep
requests, responses, failures and `worker-phase.json` for review until explicit
cleanup. Normal uncommitted semantic publication is rolled back, while committed
index/profile data remains available. Current budgets are 2MiB of
manifest data/4096 published outputs and 10,000 scanned entries per job, at most
256 jobs per scan. One semantic publication tree permits up to 4098 files within
the 10,000-entry scan limit. Legacy `cache/semantic-jobs/` is not adopted.
No other model cache automatically gains this contract.

Normal transactional responses may expose `data.job_cleanup`. If the owner was
hard-stopped, the private native process job ends descendants launched through
the shared helper; explicit recovery handles abandoned files. Other custom
process paths and other model caches do not gain this recovery contract.

This is cleanup/recovery, not inference checkpoint resume. Preserve sources and
failure records, use a fresh prefix when retrying separation, and do not claim
power-loss, disk-exhaustion or general long-concurrency acceptance. Upgrading a
four-source adapter requires explicit registration of the new implementation
pins; semantic upgrades likewise require explicit registration and rebuilt
indexes/profiles. Never silently rewrite old hashes or infer model redistribution
rights. Phase timings expose import, verification, loading and inference costs;
there is no persistent model service. CLI 0.1.13 checks deadline/cancellation
between integrity reads, preserves interruption codes, discards partial digests
and closes the current file handle. Report actual wall time and
`errors[].diagnostics` (`phase`, `bytes_processed`, partial-digest status).
Already verified files retain their command read locks. Rollback runs after the
expired operation budget resets and still validates ownership/full hashes.
OS-blocked file reads are not preempted, so this is not a universal timing guarantee.

[Full semantic recovery workflow](https://github.com/copypasteltd/agent-editor-kit/blob/main/docs/product/SEMANTIC_JOB_RECOVERY.md)
