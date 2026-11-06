# CLI66原r4完整回归结果

2026-11-06，Asia/Taipei。原r4整套已正常走到终态，执行4,114项，10项失败、15项错误、零跳过，退出码1。未提前停止、过滤或重跑单项；546个产品／测试／依赖文件、6个工具及95个正式文件与原冻结完全相符。

监督从2026-11-05T23:06:27Z运行至2026-11-06T02:28:46Z，约3小时22分钟。两条原进程实例随后均已确认退出。终态收据SHA256为`cc775e4393cd787eb31d23a4835a223585dd5c6bd6da98605a925f6c61ec4f0e`。测试数不代表功能完成比例；25个结果条目包含子测试，不等于25个独立产品缺陷。

| 编号 | 归类 | 条目数 | 已有直接证据 | 修正及验收状态 |
| --- | --- | --- | --- | --- |
| Q01 | 诊断测试夹具 | 2 | WindowsPath被当作Directory调用.read | 改用真实Session.prepare；音乐诊断另补畸形字段／有界读取处理，产品全套r5验证中 |
| Q02 | 主测试解释器缺OpenCV | 10 | 完整堆栈直接记录ModuleNotFoundError: cv2 | 换用既有E盘原生Python，实际隔离导入及原生文件摘要预检已通过；原像素断言保留 |
| Q03 | 隔离worker及关联传输 | 7 | 两个CLI堆栈明确缺NumPy；其余5条仅记录上层错误，不能宣称根因全部确认 | 独立验证无应用注入的worker依赖；即时日志新增结构化AppError.cause。完整r5及安装组仍待终态 |
| Q04 | 过时的目录精确预期 | 3 | 原预期0.9.0／46，产品既有实际为0.11.0／51 | 更新三个精确字面量；原通道、布尔、像素、数值误差断言保持 |
| Q05 | 轻量CLI提前加载NumPy | 3 | 最终堆栈定位effects模块初始化调用_optical_catalog，再进入float_optics | 总计8个模块改为计算时加载；扩大静态图至145模块／49函数作用域，实际CLI与数学回归待r5 |

首版静态图只看模块级import，漏掉模块初始化调用的目录函数；不能据其“零路径”宣称实际轻量CLI已通过。最后堆栈暴露该遗漏后，修正批次补齐光学、辉光、颜色信号及曲线4个模块。扩展图仍只是静态证据，实际结论以集中回归为准。

原r4日志中的12项test_model_session用例均为ok，包含原20秒门槛；这是4,114项中的子集，不是额外12项新测试，也不替代安装版或下一轮依赖环境验收。B03因此取得源码子集证据，但还不能关闭整项。

[原终态](../validation/evidence/delivery66-20261106-r1/source-all-r4/verification.json) · [完整日志](../validation/evidence/delivery66-20261106-r1/source-all-r4/tests.stderr) · [25条完整堆栈和置信边界](../validation/evidence/delivery66-handoff-20261106-r1/r4-terminal-review-r1/failure-catalog.json) · [完整复核](../validation/evidence/delivery66-handoff-20261106-r1/r4-terminal-review-r1/verification.json)

修正已一次写齐20个代码文件并冻结r5；31项交付契约通过，实际发现4,124项的新产品整套仍运行。[完整修正](DELIVERY66_R5_CANDIDATE.md) · [当前未完成内容](UNFINISHED_20261106.md)。正式Skill仍为CLI0.1.63／local61／r58。

| 条目 | 原结果名称 | 类别 | 根因直接出现在原记录 |
| --- | --- | --- | --- |
| Q06 | `ERROR: test_oversized_progress_is_not_loaded_as_unbounded_json (test_delivery.BoundedMusicProgressTests.test_oversized_progress_is_not_loaded_as_unbounded_json)` | test-fixture | 是 |
| Q07 | `ERROR: test_unknown_phase_and_invalid_clock_are_not_forwarded (test_delivery.BoundedMusicProgressTests.test_unknown_phase_and_invalid_clock_are_not_forwarded)` | test-fixture | 是 |
| Q08 | `ERROR: test_array_budget_rejects_before_neural_batch (test_lipsync.PixelTests.test_array_budget_rejects_before_neural_batch)` | missing-host-opencv | 是 |
| Q09 | `ERROR: test_feather_stays_inside_explicit_box (test_lipsync.PixelTests.test_feather_stays_inside_explicit_box)` | missing-host-opencv | 是 |
| Q10 | `ERROR: test_fractional_and_hidden_alpha_and_outside_box_are_bit_exact (test_lipsync.PixelTests.test_fractional_and_hidden_alpha_and_outside_box_are_bit_exact)` | missing-host-opencv | 是 |
| Q11 | `ERROR: test_invalid_neural_batch_and_semantic_mask_rejected (test_lipsync.PixelTests.test_invalid_neural_batch_and_semantic_mask_rejected)` | missing-host-opencv | 是 |
| Q12 | `ERROR: test_mask_top_protects_upper_face_with_no_feather (test_lipsync.PixelTests.test_mask_top_protects_upper_face_with_no_feather)` | missing-host-opencv | 是 |
| Q13 | `ERROR: test_partial_pipe_reads_produce_the_same_complete_frames (test_lipsync.PixelTests.test_partial_pipe_reads_produce_the_same_complete_frames)` | missing-host-opencv | 是 |
| Q14 | `ERROR: test_semantic_zero_mask_is_identity_even_when_prediction_changes (test_lipsync.PixelTests.test_semantic_zero_mask_is_identity_even_when_prediction_changes)` | missing-host-opencv | 是 |
| Q15 | `ERROR: test_short_write_rejected (test_lipsync.PixelTests.test_short_write_rejected)` | missing-host-opencv | 是 |
| Q16 | `ERROR: test_truncated_and_extra_frames_rejected (test_lipsync.PixelTests.test_truncated_and_extra_frames_rejected) (size=61439)` | missing-host-opencv | 是 |
| Q17 | `ERROR: test_truncated_and_extra_frames_rejected (test_lipsync.PixelTests.test_truncated_and_extra_frames_rejected) (size=61441)` | missing-host-opencv | 是 |
| Q18 | `ERROR: test_atomic_progress_rename_during_storage_scan_preserves_complete_transport (test_lipsync.TransportTests.test_atomic_progress_rename_during_storage_scan_preserves_complete_transport)` | isolated-worker-or-dependent-pipeline | 否；保留完整堆栈，不扩大归因 |
| Q19 | `ERROR: test_complete_actual_qtrle_and_float_pcm_transport_and_cleanup (test_lipsync.TransportTests.test_complete_actual_qtrle_and_float_pcm_transport_and_cleanup)` | isolated-worker-or-dependent-pipeline | 否；保留完整堆栈，不扩大归因 |
| Q20 | `ERROR: test_actual_worker_bypass_complete_PCM_clock_and_owned_cleanup (test_speech_enhancement.NativeTransportTests.test_actual_worker_bypass_complete_PCM_clock_and_owned_cleanup)` | isolated-worker-or-dependent-pipeline | 否；保留完整堆栈，不扩大归因 |
| Q21 | `FAIL: test_catalog_advertises_exact_numeric_channels_and_static_boolean (test_effect_automation.EffectAutomationContractTests.test_catalog_advertises_exact_numeric_channels_and_static_boolean)` | stale-catalog-assertion | 是 |
| Q22 | `FAIL: test_actual_transport_registers_two_editable_linked_tracks_and_rerun_plan (test_lipsync.CLITests.test_actual_transport_registers_two_editable_linked_tracks_and_rerun_plan)` | isolated-worker-or-dependent-pipeline | 是 |
| Q23 | `FAIL: test_validation_failure_after_publication_rolls_back_asset_and_metadata (test_lipsync.CLITests.test_validation_failure_after_publication_rolls_back_asset_and_metadata)` | isolated-worker-or-dependent-pipeline | 是 |
| Q24 | `FAIL: test_forged_alpha_response_is_rejected (test_lipsync.TransportTests.test_forged_alpha_response_is_rejected)` | isolated-worker-or-dependent-pipeline | 否；保留完整堆栈，不扩大归因 |
| Q25 | `FAIL: test_timeout_kills_owned_children (test_lipsync.TransportTests.test_timeout_kills_owned_children)` | isolated-worker-or-dependent-pipeline | 否；保留完整堆栈，不扩大归因 |
| Q26 | `FAIL: test_native_host_cli_runs_without_numpy_pillow_or_torch (test_mask_edit.MaskEditCliTests.test_native_host_cli_runs_without_numpy_pillow_or_torch)` | eager-cli-import | 是 |
| Q27 | `FAIL: test_real_cli_mask_review_runs_when_numpy_import_is_blocked (test_mask_review.MaskReviewCliTests.test_real_cli_mask_review_runs_when_numpy_import_is_blocked)` | eager-cli-import | 是 |
| Q28 | `FAIL: test_cli_planning_and_report_validation_do_not_require_host_numpy (test_repair_blend.HarmonizeTests.test_cli_planning_and_report_validation_do_not_require_host_numpy)` | eager-cli-import | 是 |
| Q29 | `FAIL: test_discovery_separates_real_hsl_kernel_from_native_command_channels (test_selective_hsl.SelectiveContractTests.test_discovery_separates_real_hsl_kernel_from_native_command_channels)` | stale-catalog-assertion | 是 |
| Q30 | `FAIL: test_catalog_and_manifest_advertise_exactly_fourteen_new_channels (test_spatial_automation.SpatialContractTests.test_catalog_and_manifest_advertise_exactly_fourteen_new_channels)` | stale-catalog-assertion | 是 |
