# 原生 ACES 开发阶段：运行内核与配置发现

源码 CLI0.1.53 已将 OpenColorIO 2.6.0 CPU 内核接入正式时间线、测量与预览，使用流程见 [ACES 时间线](ACES_TIMELINE.md)。本页保留首轮内核实现与独立上游对照证据。当前安装包及 `$agent-ffmpeg-local-editor` 仍为已验 CLI0.1.52 / local.50 / r53；新安装与 Skill 激活尚待交付。

## 当前实际能力

| 编号 | 能力 | 范围 |
| --- | --- | --- |
| A01 | 固定 ACES 1.3、2.0、2.1 Studio 配置 | 原生 OCIO 内置配置，禁止 latest、环境配置及网络 LUT 下载 |
| A02 | Agent 可枚举显示与视图 | `surface ocio-configs`，不需要工程，返回 JSON |
| A03 | 场景线性 ACEScg → 显示/视图变换 | 使用官方 `DisplayViewTransform`，不以普通 RGB 基色转换替代 Output Transform |
| A04 | 场景曝光、Float32 分块、透明度保留 | 曝光 −16 至 +16 stops；alpha 位模式保留；输入不变；取消、预算与关闭检查 |
| A05 | 原生依赖及许可随产品数据声明 | Windows CPython 3.13 x64；固定 wheel、二进制、许可证及清单摘要；无 GUI 工具、无全局安装 |

ACES 2.1 是配置版本，不代表每个视图都命名为 ACES 2.1。该配置的 sRGB SDR 视图实际名称为 `ACES 2.0 - SDR 100 nits (Rec.709)`。必须从配置结果选择原始名称。目录也包含 Raw/Un-tone-mapped 等视图，这些不等同于 ACES 色调映射。

## 源码使用流程

以下命令由项目根目录执行，适用于开发者。它不是已安装 Skill 的新命令。

```powershell
C:/Python313/python.exe -E -B -X utf8 -c "import sys;sys.path.insert(0,'product/src');from ai_ad_editor.cli import main;raise SystemExit(main(['surface','ocio-configs','--config','aces-2.1','--format','json']))"
```

调用内核时，先获得已明确解释为**场景线性 ACEScg / AP1 D60** 的连续 H×W×4 Float32 数组。不得直接将普通 sRGB 图像、PQ 码值或相机 Log 数据标记为 ACEScg。

```python
from ai_ad_editor.ocio_runtime import DisplayTransform

selection = {
    'config': 'aces-2.1',
    'display': 'sRGB - Display',
    'view': 'ACES 2.0 - SDR 100 nits (Rec.709)',
    'exposure_stops': 0,
    'input_interpretation': 'scene-linear-ACEScg',
}
with DisplayTransform(selection) as transform:
    display_rgba, receipt = transform.apply(scene_rgba, cancel=poll_cancel)
```

输出处于所选显示的编码域；不自动裁剪、不自动量化。消费者必须显式处理实际范围和编码标签。例如实际 sRGB 输出可能因数值误差略大于 1。内存预算是工作区估算，不是进程峰值 RSS。原生模块随进程驻留，`close()` 释放本封装对处理器的引用，不承诺卸载 DLL。

## 证据与复跑

```powershell
C:/Python313/python.exe -E -B -u -X utf8 docs/validation/verify_ocio_kernel.py
```

- [原生专项及上游进程对照](../validation/evidence/aces-kernel-20261029-r1/verification.json)：9 项测试；三个配置各 37×41 像素，官方原始 wheel 在隔离子进程中运行，输出与封装逐字节一致。此为同一上游算法的集成比对，不能充当独立色彩科学真值。
- [专项日志](../validation/evidence/aces-kernel-20261029-r1/tests.txt)、[实际 CLI JSON](../validation/evidence/aces-kernel-20261029-r1/cli-catalog.json)、[回归结果](../validation/evidence/aces-kernel-20261029-r1/regression.json)。
- 固定上游 [PyPI 2.6.0](https://pypi.org/project/opencolorio/2.6.0/)、[官方 Studio 配置说明](https://opencolorio.readthedocs.io/en/v2.6.0/configurations/aces_studio.html)。产品保留 BSD-3-Clause 与第三方许可原文；没有复制上游 GUI 和命令行可执行工具。

## 未完成事项

| 编号 | 下一步 | 原目标 |
| --- | --- | --- |
| P01 | 新离线包构建、实际安装、统一 Skill 激活与安装版完整音画重放 | 交付/G32 |
| P02 | 在最终交付版本继续完成兼容与组合验收，不沿用测量修复前快照冒充最终全套通过 | G08/G32 |
| P03 | 相机 IDT、AMF/LMT、其他交付制式、ACES GPU、自然素材及显示验收 | G08 |

以上是原目标的一部分进展；[完整 38 项差距清单](GOAL_GAPS_20261025.md)继续有效，未关闭其原始验收条件。
