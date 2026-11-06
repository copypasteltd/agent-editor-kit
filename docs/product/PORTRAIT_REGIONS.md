# GPU人像语义区域与保护修饰

本批开发版本为CLI0.1.67。正式CLI0.1.66／alpha.4保持原样，直到新版完成独立验收与正式切换。以下描述实现和待执行的验收范围，不把代码存在写成实测通过。

这是G20／G21的人像区域处理扩建：复用已有BiSeNet／ResNet18图和本机已取得的safetensors权重，实际分割与区域处理使用原生CUDA。不下载模型，不安装环境，不使用Docker／WSL，不增加公开Skill名称。

## 可调用流程

1. `media ingest`导入原图／视频及可选保护蒙版，保留原资产。
2. `portrait classes`查询19类、7个编辑分组、预览颜色与当前限制。
3. `portrait adapter register`显式登记已存在的权重、原生Python和来源证据。
4. `portrait parse`用显式源画面脸框生成无损区域图与真正叠加到源画面的区域预览。
5. 检查区域后，`portrait retouch`按区域编辑曝光、饱和度、平滑与着色，支持静态／动画保护蒙版。
6. 用新ID复用配方、入轨、导出工程包，再在新目录导入验证源依赖、配方、全部RGBA／PCM和时钟。

完整参数和Agent操作逻辑见[统一Skill内部说明](PORTRAIT_REGIONS_SKILL.md)。新版候选会把该说明放入唯一Skill的`references/portrait-regions.md`；正式验收前不修改已注册的95文件入口。

```powershell
& $avk portrait classes
& $avk portrait adapter register --project $project --adapter-id portrait19 `
  --model-path $existingParserWeights --executable $existingNativeCudaPython `
  --evidence $localProvenance
& $avk portrait parse --project $project --adapter-id portrait19 `
  --source-asset-id original --labels-asset-id face_regions `
  --preview-asset-id regions_preview --face-box 100 40 400 440
& $avk portrait retouch --project $project --adapter-id portrait19 `
  --labels-asset-id face_regions --asset-id graded `
  --controls-file controls.json --protection-asset-id protect
& $avk portrait retouch --project $project --adapter-id portrait19 `
  --recipe-asset-id graded --asset-id graded_retry
```

`$avk`须为已验证安装版Skill入口；这些命令不是对当前正式CLI66的兼容承诺。所有输出使用新资产ID，不覆盖旧结果。保护蒙版中的任意非零灰度像素完全保护，黑色允许编辑。灰度取解码RGB亮度，不以蒙版alpha代替。

## 标签与实际边界

标签按[zllrunning的训练预处理顺序](https://github.com/zllrunning/face-parsing.PyTorch/blob/master/prepropess_data.py)，不是其他CelebAMask实现的不同顺序。固定权重摘要与标签顺序一同校验；不接受其他任意19类检查点冒用该语义。

| 标签 | 内容 | 编辑分组 |
| --- | --- | --- |
| 0 | 背景／未选或低于阈值 | 无 |
| 1、10 | 皮肤、鼻 | skin |
| 2、3 | 左右眉 | brows |
| 4、5 | 左右眼 | eyes |
| 6 | 眼镜 | 无 |
| 7、8 | 左右耳 | ears |
| 9 | 耳饰 | 无 |
| 11 | 口腔内部 | 无 |
| 12、13 | 上下唇 | lips |
| 14 | 颈部 | neck |
| 15、16 | 项链、衣物 | 无 |
| 17 | 头发 | hair |
| 18 | 帽子 | 无 |

推理复用[原始BiSeNet参考](https://github.com/zllrunning/face-parsing.PyTorch/blob/master/evaluate.py)的512输入与RGB归一化，使用本地Torch双线性缩放。神经类别和置信阈值不保证真实分割正确。手、通用遮挡物不在标签中，须检查预览并提供显式保护。当前一遍处理一个明确脸框，不进行自动身份判断或跟踪。

皮肤等分组相互不重叠。曝光、饱和度和着色使用显式SDR传递函数；平滑为9采样、颜色引导且排除保护邻居的处理。羽化只向选区内部进行。保留源alpha、隐藏RGB、未选RGB及显式保护像素；这不自动证明肤质、身份、妆效和时序自然。

图片区域图用gray PNG，视频区域图用FFV1/NUT无损保存帧序列；实际预览／修饰使用RGBA PNG或QTRLE MOV，视频逐条保留源音频为Float32 PCM。每次处理核对完整RGBA、标签、源alpha和每条PCM；视频输出再验证所有帧PTS。

## 本批集中验收要求

| 编号 | 要求 |
| --- | --- |
| T01 | 控制参数、脸框、模型摘要、来源时钟、配方、保护及畸形响应的有意义契约测试 |
| T02 | 原有产品整套回归保留原断言，源码与安装版分别运行、分别计数 |
| T03 | 新离线包、候选单Skill、实际PowerShell入口，无源码回退 |
| T04 | 本地真实CUDA分割与区域修饰；模型加载／前向和GPU峰值分别记录，合成夹具不冒充真实推理 |
| T05 | 原图／动态源、区域图、静态及动画保护、全部透明度／区域外RGB／PCM独立比较 |
| T06 | 配方复用、空参数中性结果、完整工程包导出／导入与再次处理 |
| T07 | 实际取消／超时／推理后输出占用，元数据和外部文件保护、受管工作目录与进程回收 |

真实执行结果后续附在本页并链接原始收据；未执行项保持待验收。现有RIFE重影、SAM2手腕漏选、语义检索误判和翻译错译不因本批新增区域内核而关闭。完整皮肤／遮挡质量、美妆、美体、发型、重打光、身体动作驱动与自然视听仍按G01—G38继续。
