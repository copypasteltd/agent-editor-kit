# Actual package failure / 工程迁移失败

CLI 0.1.10: six image-card clips export/import/render correctly and all 360
decoded frames match. The separate retrieval project exports, imports and
passes general validate, but its calibrated search dry run fails with
`SEMANTIC_INDEX_INVALID`: `Manifest outside project semantic asset tree`.

The retrieval package is a retained reproduction of this failure, not a
verified portable semantic index/profile. Do not edit fingerprints or trust
the general validator as proof. Explicitly re-register the local adapter,
rebuild the index and recalibrate after moving; this workaround was not
executed as part of this diagnostic. A clean-host migration is not established.

See the original 19 CLI receipts and failure under
`docs/validation/evidence/semantic-decision-20261025-r1/demo-installed-r1/`.
The MP4/GIF are actual silent diagnostic output, not an execution recording or
a natural advertising benchmark. Typography is rasterized in six individually
editable image clips. All three known query mistakes are shown.
