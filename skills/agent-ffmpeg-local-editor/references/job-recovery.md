# Interrupted local jobs

Use for cancellation, timeout or an interrupted four-source separation job.
Inspect `project recover --help` through the pinned installed launcher first.

```powershell
& $avk project recover --project $project --cleanup-jobs --dry-run
& $avk project recover --project $project --cleanup-jobs
& $avk validate --project $project
```

Default `project recover` restores metadata only. `--cleanup-jobs` restores a
pending transaction first, then inspects the durable four-source workspaces in
`cache/managed-jobs/`. Check `data.job_recovery.jobs`: the native lease protects
active jobs; only matching filesystem identity/hash and unreferenced derived
outputs can be removed. Committed assets survive. Changed outputs, unknown or
blocked directories, user media and legacy unmanaged caches are preserved.
Dry-run makes no metadata or file changes. Keep preserved evidence and inspect
the reason; do not replace recovery with a blanket cache deletion.

Normal transactional responses may expose `data.job_cleanup`. If the owner was
hard-stopped, the private native process job ends descendants launched through
the shared helper; explicit recovery handles abandoned files. Other custom
process paths and other model caches do not gain this recovery contract.

This is cleanup/recovery, not inference checkpoint resume. Preserve sources and
failure records, use a fresh prefix when retrying separation, and do not claim
power-loss, disk-exhaustion or general long-concurrency acceptance. Upgrading a
four-source adapter requires explicit registration of the new implementation
pins; never silently rewrite old hashes or infer model redistribution rights.
