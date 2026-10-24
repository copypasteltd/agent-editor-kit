# 快照、恢复、重链和队列 / project-ops

[Unified entry](../../../SKILL.md) · [Shared runtime](../../runtime.md)

Projects + jobs → snapshots/recovery/relink/results

Commands: `project snapshot/recover; media relink; queue`. Preserve sources/failures; not a cloud scheduler.

## Workflow

Inspect `project --help`, `media relink --help` and `queue --help`. Snapshot before substantial edits.
Keep source hashes and explicit relink mappings. Inspect saved state before recovery or replay. Run queued jobs
with explicit output paths and preserve cancellation/failure evidence; do not assume every command is idempotent.
