# GPU SDR 显示映射 / GPU SDR 顯示映射 / GPU SDR display mapping

开发源码 CLI **0.1.52** 新增原生 OpenCL 色彩算子。本地已注册统一 Skill 仍为 **CLI0.1.51 / local.49 / r52**；新源码、新候选包与已激活安装版分别核验，不能混用版本。公开 alpha.3 附件保持原字节。

## 功能与执行范围

工作线性 RGB 到 BT.709/D65 的信号转换仍在 CPU 完成。GPU 接手曝光、modified-Reinhard CIE Y 亮度肩部及 OKLab 固定感知明度/色相的 24 次二分缩色度，最终返回 Float32 RGBA。GPU 内部计算使用 binary64，禁止 fast math 与 FP contraction；alpha 直接保留输入 Float32 位。ICC、最终信号编码、媒体编解码不因此变成 GPU 色彩算子。

已经在单位 RGB 域内的肩部结果无需缩色度。越界像素的 L<=0 映黑，L>=1−1e−7 映白，并单独计数；其他像素沿 a/b 色度射线搜索。保持的是 OKLab L 与色相方向，**不承诺保持 CIE Y**。完整 CPU 算法及来源见 [OKLab 工作流](OKLAB_GAMUT.md)。

## Agent 使用流程

1. 先核对实际运行入口的 `version` 与 `capabilities`；只有 CLI52 的 `native_sdr_gamut_mapping` 才描述本页的新 GPU 执行路径。不要将源码回退伪装成已安装 Skill。
2. 使用 `float32-native-v1`，为素材、工作域、输出明确声明 RGB 基色、传递函数及 `reference_white_nits`。GPU 色域映射当前只支持 BT.709/D65 SDR 目标。
3. 在工程已有 `settings` 中配置 GPU 选择；在已有 `settings.pixel_pipeline` 中配置正式交付 `display_mapping`，例如：

```json
{
  "projection_acceleration": {"mode": "require", "device": "0.0"},
  "pixel_pipeline": {
    "display_mapping": {
      "operator": "reinhard-luminance",
      "source_peak_nits": 1000,
      "target_peak_nits": 100,
      "exposure_stops": 0,
      "gamut_policy": "oklab-chroma"
    }
  }
}
```

这是需要合并进现有 `settings` 的字段片段，**不是完整可验证工程**，不能覆盖其他像素管线字段。设备 `0.0` 为本机测试的选择值，部署机器须先枚举、核验实际设备与 FP64 支持。正式输出的 `reference_white_nits` 须与目标峰值一致。

4. 运行 `validate --project <目录>`，再运行正常 `render --project <目录> --sequence-id <序列ID> --output <成片>`；渲染收据应含 `projection_acceleration.operations.gamut_map` 以及 `last_display_mapping.perceptual_gamut.GPU=true`。
5. 使用 `preview frame/range` 生成选型预览。明确 `preview_mapping` 优先；没有单独预览映射时继承正式 `display_mapping`，映射一次之后才在显示线性域缩小。HDR 作者工程的 SDR 查看使用单独 `preview_mapping`。
6. 检查每帧和全帧色彩边界计数、完整音画，再导出可编辑工程包、导入新目录并再次验证/渲染。将实际预览、配置与计算收据一并提供给客户。

## 失败与资源管理

新算子只接受明确的 `oklab-chroma`。`clip`/`reject` 保持原 CPU 语义。无效策略在派发前拒绝；负/非有限 CIE Y 在原生工作进程中失败，不交付部分结果。运行中 GPU 失败不静默回退 CPU。设备、配额与取消沿用 [GPU 调度](GPU_DISPATCH.md) 的受管工作进程、共享内存及控制管道清理机制。

GPU 复用三块设备缓冲，计划预算为每像素 48 字节；工作进程另有每像素 4 字节的标志回读。预算和 `retained_device_bytes` 收据不是总进程 RSS 或工作进程退出后的实际显存测量。取消证据验证受管算子生命周期，不证明 GPU 硬件内核可被逐指令抢占。

## 实测与限制

[4K 单表面实测](../validation/evidence/gpu-gamut-20261029-r1/4k-r1/verification.json)：3840×2160，8,294,400 像素全部核对独立标量参考；最大线性 RGB 误差约 1.54×10⁻⁷，CPU/GPU 最大差约 1.78×10⁻¹⁵。一次非独占运行中 CPU 18.10 秒、GPU 映射路径 1.74 秒，另有约 0.94 秒工作进程启动。这是算子实测，不是编码后 4K 影片、实时预览、长片或普遍加速保证。

[12 项控制管道测试](../validation/evidence/gpu-gamut-20261029-r1/gpu-control-r1/verification.json)另行留证。专项、兼容、案例及安装门槛的最新状态见 [本轮核验报告](../validation/GPU色域映射源码实测_2026-10-29.md)，不得将运行中测试写为通过。

尚未覆盖完整 ACES、软拐点、BT.2390、动态 HDR、物理显示校准、自然素材广泛艺术质量验收、跨厂商 GPU 和实时调度。全部原产品关闭条件继续保留。

繁體：原生 GPU 執行亮度肩部及 OKLab 縮色度；訊號轉換與 ICC 仍由 CPU 處理。必須區分源碼 CLI52、候選安裝與目前已註冊 CLI51；完整剪映等價、自然畫面與實體 HDR 監看仍未完成。

English: Source CLI52 adds a native GPU luminance shoulder and 24-step OKLab chroma search. Signal conversion and ICC remain on CPU. Verify the actual executable, per-operation receipts, full decoded video/audio and editable-package replay. The installed unified Skill remains CLI51 until matching installation gates pass. One 4K operator surface is not real-time, long-form or full product-parity acceptance.
