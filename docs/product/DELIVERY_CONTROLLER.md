# Verified local delivery / CLI0.1.66

Use the installed `delivery` commands for a reviewed single-Skill update.
`--workspace` is the existing agent editor kit checkout; `--descriptor` points
to the locally prepared candidate description. No models or dependencies are
downloaded, no virtual environment starts, and existing release archives stay intact.

```powershell
& $avk delivery inspect --workspace $workspace --descriptor $descriptor
& $avk delivery activate --workspace $workspace --descriptor $descriptor --dry-run
& $avk delivery activate --workspace $workspace --descriptor $descriptor
& $avk delivery recover --workspace $workspace
& $avk delivery rollback --workspace $workspace
```

The descriptor pins the current formal files, staged Skill/configuration,
installation application files, offline archive and four independent gates:
source tests, installed tests, full music project replay and the actual staged
PowerShell entry. A gate must match the candidate CLI/application bytes. Keep
the evidence paths; a descriptor is an input to validation, not proof by itself.

Activation holds a native file lock, writes durable backups and a recovery
journal, temporarily makes the entry unavailable, changes only the one Skill,
runtime configuration and registration manifest, and verifies the real
PowerShell `version` entry before committing. It preserves the existing loader
junction and never falls back to product source. A partial failure restores the
previous files; a killed owner leaves the journal for explicit `delivery recover`.

Rollback verifies every retained backup before any restore and refuses files
modified after activation. Recovering an interrupted transition restores its
recorded baseline. Neither operation promises atomic replacement of multiple
files against uncooperative external writers. Inspect retained backups and the
journal under `local/agent-ffmpeg/deliveries/` before retrying failed recovery.

Normal editing remains `project init` → register authorized assets/models →
show actual filter/voice auditions → dry-run → generate/edit → preview/render →
export and replay. The 500 filter previews and 103 voice WAVs remain selection
resources. Confirm the exact runtime version and actual CUDA receipts; full
natural quality, clean-host installation and full CapCut parity are separate gates.

简体：交付控制器先核对完整候选与证据，再备份、切换、验证；中断使用recover，已成功升级可显式rollback。完整备份预检失败时保留现场。正式入口升级成功前继续使用原版。

繁體：交付控制器先核對完整候選與證據，再備份、切換、驗證；中斷使用recover，已成功升級可明確rollback。完整備份預檢失敗時保留現場。正式入口升級成功前繼續使用原版。
