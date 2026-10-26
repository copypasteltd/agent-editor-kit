# CLI0.1.34 · native model sessions · local.32

新增原生 GPU 模型会话：显式启动、查询、停止，连续生成复用权重和同一提示词嵌入；每个任务重置调度器、前窗上下文与统计。实际同机首条生成 654.27 秒，后两条 35.46/28.48 秒；会话全模型校验另计 480.42 秒。相同 seed 的 17 帧逐像素相同，实际去噪取消可回滚并退出所属进程。

Explicit native GPU sessions add start/status/stop and reuse weights plus the same prompt embeddings. Scheduler, prior-frame context and metrics reset per job. This host measured 654.27s for the first generation and 35.46/28.48s for the next two; session-wide model verification adds 480.42s separately. Same-seed replay matches all 17 decoded frames. Cancellation during real denoising rolls back and exits only the owned process.

[Workflow](../product/MODEL_SESSIONS.md) · [Local install](../product/COMMUNITY_LOCAL_DELIVERY.md)

Application ZIP: `local/agent-ffmpeg/v0.1.0-alpha.4-local.32/candidate-r3/bundle.zip`

ZIP bytes: `302823929` · SHA256: `8d3f4e7891d646df3380b5f6dc834e2f002184e19cdb15e9fef9f79da8ddd634`

Manifest SHA256: `sha256:0d3fda8a037d510eb60294ca6c70d3dd6f2c7eaf4fa9be8291987145c0ad41aa`

Public alpha.3 / CLI0.1.2 remains unchanged; local updates are not a new public Release.

安装版19/14/161/192各组通过，230产品文件、75 Skill文件、17模块、r35 kit116文件；[实际完整证据](../validation/原生GPU模型常驻实测_2026-10-27.md)。同提示词串行复用；首条成本及全部38原关闭条件保留。
