# OKLab 色度边界映射 / OKLab 色度邊界映射 / OKLab chroma boundary reduction

**当前已安装CLI0.1.51/local.49，统一Skill已加载；以下初始源码阶段状态保留为历史。** [实际安装与使用](../releases/CLI_0.1.51_LOCAL.md) · [C62](CASES.md#c62-installed-oklab)。

**源码 CLI0.1.51；当前安装与统一Skill仍CLI0.1.50/local.48/r51。** 本功能尚未安装打包，不要给旧Skill传入新枚举或回退到源码。[本轮源码证据](../validation/OKLab色域映射源码实测_2026-10-29.md)。

在 `settings.pixel_pipeline.display_mapping` 或 `preview_mapping` 中明确设置：

```json
{"operator":"reinhard-luminance","source_peak_nits":1000,"target_peak_nits":100,"exposure_stops":0,"gamut_policy":"oklab-chroma"}
```

1. 使用原生 `float32-native-v1`，为素材、线性工作域和输出声明基色、传递函数与 `reference_white_nits`。
2. 正式SDR交付目标须是D65 BT.709，并将输出 `reference_white_nits` 设为 `target_peak_nits`；HDR作者工程使用 `preview_mapping` 生成单独SDR查看副本。
3. 验证工程，再执行既有 `preview frame/range`、`render`、`surface measure` 和工程包导出。源码开发入口与安装Skill分开；本页不是已安装操作承诺。
4. 将实际成片、完整映射配置、`perceptual_gamut` 与全帧 `colour_boundary_all_frames`/transport计数一起交付，比较原图与裁切方案后选型。

转换先将工作线性RGB变换到BT.709/D65，保留负分量，再按非负CIE Y执行明确的modified-Reinhard亮度肩部。之后在OKLab中固定感知明度L和色相方向，将a/b统一乘以0..1的比例，24次二分选择RGB单位立方体内的候选。不是逐通道RGB裁切；不是保持CIE Y。已经位于目标域内的肩部结果保持原字节，alpha位保持。

`gamut_pixels_mapped`、`gamut_chroma_reduced_pixels`、`gamut_lightness_to_black_pixels`、`gamut_lightness_to_white_pixels`按帧统计并在正式交付中汇总。L<=0映为黑；越界像素L>=1-1e-7映为白，后者是公开矩阵有限精度保护，明确计数，不宣称端点色相/明度保留。负CIE Y、非有限输入、错误目标、超预算和取消直接失败，不静默修正。旧reject/clip路径保持其原语义与默认值。

每块最多65536像素，Float64计算后写回Float32，CPU执行并在二分循环内响应取消；工作区估算不是全进程RSS/VRAM。正式渲染及中间包依赖摘要包含新实现。当前不是GPU色彩内核、软拐点压缩、CSS local-MINDE、ACES、BT.2390、动态HDR或显示器校准，也不等于完整剪映效果验收。

矩阵来源：[Björn Ottosson OKLab 原文](https://bottosson.github.io/posts/oklab/)，使用2021-01-25线性sRGB系数（原作者提供public-domain/MIT许可）；二分边界搜索为本项目实现。这里只借鉴坐标变换，不把本项目搜索称为原作者的完整色域映射算法。

繁體：新增明確選用的OKLab固定明度/色相縮色度；僅D65 BT.709目標，CPU分塊，端點與全幀計數可查。已安裝Skill尚未升級，完整自然HDR/藝術品質仍待驗收。

English: Source CLI0.1.51 adds explicit `oklab-chroma` for BT.709/D65 SDR trims and previews. It reduces chroma along a fixed OKLab lightness/hue ray, with counted black/near-white endpoints. This preserves perceptual L, not CIE Y. CPU tiled execution; no soft knee, ACES or monitor-certification claim. Installed Skill remains CLI0.1.50 pending matching delivery.


**2026-10-29 follow-up / 后续勘误 / 後續勘誤：** [SDR预览映射修复与C61包ID勘误](../validation/SDR预览映射修复_2026-10-29.md)。CLI51候选r2已构建与安装专项核验；统一Skill仍50；完整兼容、新kit、自然画面及物理监看待完成。
