# 500 套内置风格：编号、实际作用与完整说明

[简体中文](LOOK_PRESETS.md) · [繁體中文](LOOK_PRESETS.zh-TW.md) · [English](LOOK_PRESETS.en.md)

安装版 **v0.1.0-alpha.3**、CLI **0.1.2**、目录 **2.0.0**。每项包含稳定 ID、原名与来源区分、13 个真实色块测量、场景建议、试用强度、实际预览/视频和独立许可。原 001–100 保留 ID 与 LUT 字节。

**计数口径：500 个不同的数值色彩变换，包含同系列的上游曲线变体；不是 500 个互不相关的风格家族。** 同一 LUT 的运行强度档位和不同文件格式不重复计数；构建时已剔除 6 份重复变换。

[Filter workflow](FILTERS.md) · [Installation](INSTALLATION.md) · [Validation](../validation/LOOK500_20261024.md) · [Catalog JSON](../../product/src/ai_ad_editor/look_data/catalog.json)

## 命名与测量规则

`sp-` 为 Striped Purple（49），`t3-` 为 t3mujinpack（51），`nt-` 为 Natron（267），`fl-` 为 FreshLUTs（133）。编号 001–500 便于阅读，命令始终使用 ID。`curve-plus-N / curve-minus-N` 保留上游的 +/- 曲线标记，不代表 EV 或运行时强度。胶片/产品原名用于识别社区近似风格，不代表厂商授权或官方算法。

测量使用强度 1、四面体插值和编码 SDR RGB，输出截断到 0..1。Y′ = 0.2126 R′ + 0.7152 G′ + 0.0722 B′，以 0–255 码值表示，不是线性亮度或曝光。跨度比 = (Y′75% − Y′25%) / 127.5。肤色色块不代表人脸识别/肤色保护。场景/强度建议只是试片起点，尚无自然画质验收。LUT 不生成颗粒、光晕、暗角、空间雾或美颜。

## 许可与类别

| License | Count | Resource obligation |
|---|---:|---|
| MIT | 100 | Retain copyright and license notice |
| CC-BY-SA-4.0 | 267 | Credit author/source, state changes; adapted LUT data/previews share alike |
| CC0-1.0 | 133 | No attribution condition; provenance retained |

[Original source notices and legal codes](../releases/v0.1.0-alpha.3/THIRD_PARTY.md). Application code remains MIT.

| Category | Count |
|---|---:|
| `cinema` | 39 |
| `creative` | 135 |
| `film-bw` | 37 |
| `film-negative` | 112 |
| `film-slide` | 41 |
| `infrared` | 2 |
| `instant-consumer` | 54 |
| `instant-pro` | 65 |
| `landscape` | 10 |
| `lomography` | 5 |

类别沿用来源分组；拍立得与负片组也含黑白变体。是否去色、中灰偏向和跨度以每套实测说明为准。


上传者输入标签不等于相机校准。`fl-0000228-science-fiction-for-flog` 的锁定来源标为 Rec.709，标题却提到 FLog，输入域存在歧义；仅在已准备的 SDR 素材上作为实验创意风格比较，不作为已验证的 FLog 转换。


## 分册：逐项详情、预览与视频

- [001–100](look-profiles/001-100.md)
- [101–200](look-profiles/101-200.md)
- [201–300](look-profiles/201-300.md)
- [301–400](look-profiles/301-400.md)
- [401–500](look-profiles/401-500.md)

## 完整编号表

| # | 名称 / 稳定 ID | 实际效果 | 建议试片场景 | 试用强度 | 许可 |
|---|---|---|---|---|---|
| 001 | [电影 · 1910s](look-profiles/001-100.md#preset-sp-1910s)<br>`sp-1910s` | 暖色 · 提亮中灰 · 中段跨度接近原值 | 旧报刊、历史回忆、档案段落 | 0.35–0.8 | MIT |
| 002 | [电影 · 1920s](look-profiles/001-100.md#preset-sp-1920s)<br>`sp-1920s` | 黑白 · 中灰近原值 · 中段跨度接近原值 | 黑白叙事、字幕底片、档案风格 | 1–1 | MIT |
| 003 | [电影 · 1930s](look-profiles/001-100.md#preset-sp-1930s)<br>`sp-1930s` | 暖色 · 提亮中灰 · 中段跨度接近原值 | 复古纪实、历史标题、怀旧照片动画 | 0.35–0.8 | MIT |
| 004 | [电影 · 1940s](look-profiles/001-100.md#preset-sp-1940s)<br>`sp-1940s` | 中性 · 中灰近原值 · 中段跨度接近原值 | 复古彩色叙事、海报感短片 | 0.35–0.8 | MIT |
| 005 | [电影 · 1950s](look-profiles/001-100.md#preset-sp-1950s)<br>`sp-1950s` | 中性 · 中灰近原值 · 中段跨度接近原值 | 复古商品故事、街景、旅行片头 | 0.35–0.8 | MIT |
| 006 | [电影 · 1960s](look-profiles/001-100.md#preset-sp-1960s)<br>`sp-1960s` | 中性 · 中灰近原值 · 中段跨度接近原值 | 复古生活方式、音乐片段、街拍 | 0.35–0.8 | MIT |
| 007 | [电影 · 1970s](look-profiles/001-100.md#preset-sp-1970s)<br>`sp-1970s` | 中性 · 中灰近原值 · 中段拉开 | 旅行回忆、生活记录、旧相册感广告 | 0.35–0.8 | MIT |
| 008 | [电影 · 1980_s](look-profiles/001-100.md#preset-sp-1980-s)<br>`sp-1980-s` | 中性 · 中灰近原值 · 中段拉开 | 音乐节奏片、街头、强视觉产品片 | 0.35–0.8 | MIT |
| 009 | [创意色彩 · Amber Haze](look-profiles/001-100.md#preset-sp-amber-haze)<br>`sp-amber-haze` | 暖色 · 压暗中灰 · 中段收窄 | 暗调情绪、夜间氛围、复古静物 | 0.35–0.8 | MIT |
| 010 | [创意色彩 · Ara](look-profiles/001-100.md#preset-sp-ara)<br>`sp-ara` | 暖色 · 压暗中灰 · 中段跨度接近原值 | 鲜明户外、图形画面、暖色主体 | 0.35–0.8 | MIT |
| 011 | [创意色彩 · Arcade Dayz](look-profiles/001-100.md#preset-sp-arcade-dayz)<br>`sp-arcade-dayz` | 暖色 · 提亮中灰 · 中段收窄 | 游戏、潮流、青春生活方式 | 0.35–0.8 | MIT |
| 012 | [创意色彩 · Aricha Blend](look-profiles/001-100.md#preset-sp-aricha-blend)<br>`sp-aricha-blend` | 暖色 · 中灰近原值 · 中段拉开 | 咖啡、木质静物、秋日生活方式 | 0.35–0.8 | MIT |
| 013 | [创意色彩 · Blow Me Down](look-profiles/001-100.md#preset-sp-blow-me-down)<br>`sp-blow-me-down` | 暖色 · 提亮中灰 · 中段拉开 | 海边创意、强色彩插片、暖色物件 | 0.35–0.8 | MIT |
| 014 | [创意色彩 · Blue Lagoon](look-profiles/001-100.md#preset-sp-blue-lagoon)<br>`sp-blue-lagoon` | 中性 · 中灰近原值 · 中段跨度接近原值 | 水景、旅行、暖主体与冷背景对照 | 0.35–0.8 | MIT |
| 015 | [创意色彩 · Boa](look-profiles/001-100.md#preset-sp-boa)<br>`sp-boa` | 暖色 · 压暗中灰 · 中段跨度接近原值 | 森林、户外装备、冷峻静物 | 0.35–0.8 | MIT |
| 016 | [创意色彩 · Caramel Plum Cake](look-profiles/001-100.md#preset-sp-caramel-plum-cake)<br>`sp-caramel-plum-cake` | 暖色 · 压暗中灰 · 中段跨度接近原值 | 甜品、木质桌面、暖调生活片 | 0.35–0.8 | MIT |
| 017 | [创意色彩 · Cherry Champagne](look-profiles/001-100.md#preset-sp-cherry-champagne)<br>`sp-cherry-champagne` | 暖色 · 提亮中灰 · 中段收窄 | 柔和人物、婚礼情绪、粉彩设计 | 0.35–0.8 | MIT |
| 018 | [风景 · December Greens](look-profiles/001-100.md#preset-sp-december-greens)<br>`sp-december-greens` | 中性 · 中灰近原值 · 中段跨度接近原值 | 冬季绿景、冷暖均衡生活片 | 0.35–0.8 | MIT |
| 019 | [创意色彩 · Dodo](look-profiles/001-100.md#preset-sp-dodo)<br>`sp-dodo` | 中性 · 压暗中灰 · 中段收窄 | 低调静物、城市纪实、怀旧故事 | 0.35–0.8 | MIT |
| 020 | [风景 · Emerald Malaise](look-profiles/001-100.md#preset-sp-emerald-malaise)<br>`sp-emerald-malaise` | 冷色 · 压暗中灰 · 中段收窄 | 复古绿景、森林情绪、冷暖叙事 | 0.35–0.8 | MIT |
| 021 | [创意色彩 · Great Auk](look-profiles/001-100.md#preset-sp-great-auk)<br>`sp-great-auk` | 黑白 · 压暗中灰 · 中段跨度接近原值 | 沉静黑白、暗调叙事、图形轮廓 | 1–1 | MIT |
| 022 | [创意色彩 · Grey Matter](look-profiles/001-100.md#preset-sp-grey-matter)<br>`sp-grey-matter` | 暖色 · 压暗中灰 · 中段拉开 | 暖灰人物、旧纸质感、克制叙事 | 0.35–0.8 | MIT |
| 023 | [创意色彩 · Horchata](look-profiles/001-100.md#preset-sp-horchata)<br>`sp-horchata` | 中性 · 压暗中灰 · 中段拉开 | 生活方式、咖啡、暖色商品故事 | 0.35–0.8 | MIT |
| 024 | [红外创意 · Infrared](look-profiles/001-100.md#preset-sp-infrared)<br>`sp-infrared` | 中性 · 中灰近原值 · 中段跨度接近原值 | 音乐视觉、超现实植被、创意片段 | 0.35–0.8 | MIT |
| 025 | [红外创意 · Infrared 2](look-profiles/001-100.md#preset-sp-infrared-2)<br>`sp-infrared-2` | 中性 · 中灰近原值 · 中段跨度接近原值 | 较柔和假色旅行、梦境、MV | 0.35–0.8 | MIT |
| 026 | [风景 · Irish Uprising](look-profiles/001-100.md#preset-sp-irish-uprising)<br>`sp-irish-uprising` | 暖色 · 提亮中灰 · 中段收窄 | 绿景、户外生活、暖人物冷背景 | 0.35–0.8 | MIT |
| 027 | [创意色彩 · Kraken](look-profiles/001-100.md#preset-sp-kraken)<br>`sp-kraken` | 暖色 · 压暗中灰 · 中段跨度接近原值 | 暗调动作、复古街头、强色彩故事 | 0.35–0.8 | MIT |
| 028 | [创意色彩 · Lobster](look-profiles/001-100.md#preset-sp-lobster)<br>`sp-lobster` | 暖色 · 压暗中灰 · 中段收窄 | 暖静物、海岸情绪、复古生活 | 0.35–0.8 | MIT |
| 029 | [Lomo · Lomochrome Purple](look-profiles/001-100.md#preset-sp-lomochrome-purple)<br>`sp-lomochrome-purple` | 中性 · 中灰近原值 · 中段跨度接近原值 | 超现实植被、音乐、紫色创意世界 | 0.35–0.8 | MIT |
| 030 | [Lomo · Lomochrome Purple 2](look-profiles/001-100.md#preset-sp-lomochrome-purple-2)<br>`sp-lomochrome-purple-2` | 中性 · 中灰近原值 · 中段跨度接近原值 | 粉紫植物、时尚创意、梦境画面 | 0.35–0.8 | MIT |
| 031 | [Lomo · Lomochrome Purple 3](look-profiles/001-100.md#preset-sp-lomochrome-purple-3)<br>`sp-lomochrome-purple-3` | 中性 · 中灰近原值 · 中段跨度接近原值 | 紫黄对照、音乐片、非写实设计 | 0.35–0.8 | MIT |
| 032 | [Lomo · Lomochrome Purple 4](look-profiles/001-100.md#preset-sp-lomochrome-purple-4)<br>`sp-lomochrome-purple-4` | 中性 · 中灰近原值 · 中段跨度接近原值 | 低饱和假色、时尚情绪、非写实旅行 | 0.35–0.8 | MIT |
| 033 | [Lomo · Lomochrome Purple 5](look-profiles/001-100.md#preset-sp-lomochrome-purple-5)<br>`sp-lomochrome-purple-5` | 中性 · 中灰近原值 · 中段跨度接近原值 | 暗紫植被、青紫对照、创意短片 | 0.35–0.8 | MIT |
| 034 | [创意色彩 · Moa](look-profiles/001-100.md#preset-sp-moa)<br>`sp-moa` | 暖色 · 压暗中灰 · 中段拉开 | 暖灰纪实、人物回忆、纸感画面 | 0.35–0.8 | MIT |
| 035 | [创意色彩 · Pendleton](look-profiles/001-100.md#preset-sp-pendleton)<br>`sp-pendleton` | 暖色 · 提亮中灰 · 中段拉开 | 日光生活方式、旅行、青春人物 | 0.35–0.8 | MIT |
| 036 | [风景 · Philly Fog](look-profiles/001-100.md#preset-sp-philly-fog)<br>`sp-philly-fog` | 中性 · 中灰近原值 · 中段拉开 | 城市漫步、海边生活、温和纪实 | 0.35–0.8 | MIT |
| 037 | [创意色彩 · Polaroid Mint Cream](look-profiles/001-100.md#preset-sp-polaroid-mint-cream)<br>`sp-polaroid-mint-cream` | 暖色 · 提亮中灰 · 中段跨度接近原值 | 回忆、柔和生活方式、粉彩物件 | 0.35–0.8 | MIT |
| 038 | [风景 · Sea Turtle](look-profiles/001-100.md#preset-sp-sea-turtle)<br>`sp-sea-turtle` | 中性 · 中灰近原值 · 中段跨度接近原值 | 热带绿景、户外、明亮旅行 | 0.35–0.8 | MIT |
| 039 | [风景 · Seagull Cove](look-profiles/001-100.md#preset-sp-seagull-cove)<br>`sp-seagull-cove` | 中性 · 中灰近原值 · 中段跨度接近原值 | 海岸、安静旅行、人物生活片 | 0.35–0.8 | MIT |
| 040 | [风景 · Snowy Blues](look-profiles/001-100.md#preset-sp-snowy-blues)<br>`sp-snowy-blues` | 冷色 · 中灰近原值 · 中段收窄 | 冬景、冷调生活、安静人物 | 0.35–0.8 | MIT |
| 041 | [风景 · Spring Water](look-profiles/001-100.md#preset-sp-spring-water)<br>`sp-spring-water` | 中性 · 中灰近原值 · 中段跨度接近原值 | 日常人物、清淡旅行、自然生活方式 | 0.35–0.8 | MIT |
| 042 | [创意色彩 · Sugar Plums](look-profiles/001-100.md#preset-sp-sugar-plums)<br>`sp-sugar-plums` | 暖色 · 压暗中灰 · 中段拉开 | 甜酷、时尚、音乐与夜间情绪 | 0.35–0.8 | MIT |
| 043 | [风景 · Teal Embers](look-profiles/001-100.md#preset-sp-teal-embers)<br>`sp-teal-embers` | 中性 · 中灰近原值 · 中段跨度接近原值 | 青橙叙事、城市夜景、人物短片 | 0.35–0.8 | MIT |
| 044 | [风景 · Teal Supreme](look-profiles/001-100.md#preset-sp-teal-supreme)<br>`sp-teal-supreme` | 中性 · 中灰近原值 · 中段跨度接近原值 | 克制冷调、城市生活、静物氛围 | 0.35–0.8 | MIT |
| 045 | [创意色彩 · Tiger](look-profiles/001-100.md#preset-sp-tiger)<br>`sp-tiger` | 中性 · 压暗中灰 · 中段跨度接近原值 | 运动、街头、橙蓝视觉广告 | 0.35–0.8 | MIT |
| 046 | [创意色彩 · Turquoise](look-profiles/001-100.md#preset-sp-turquoise)<br>`sp-turquoise` | 中性 · 提亮中灰 · 中段收窄 | 梦幻海边、粉彩创意、柔和旅行 | 0.35–0.8 | MIT |
| 047 | [创意色彩 · Vanilla Bean](look-profiles/001-100.md#preset-sp-vanilla-bean)<br>`sp-vanilla-bean` | 暖色 · 提亮中灰 · 中段拉开 | 奶油暖调、甜品、明亮室内生活 | 0.35–0.8 | MIT |
| 048 | [创意色彩 · Veggie Crisps](look-profiles/001-100.md#preset-sp-veggie-crisps)<br>`sp-veggie-crisps` | 中性 · 中灰近原值 · 中段拉开 | 褪色但有鲜色的生活片、户外物件 | 0.35–0.8 | MIT |
| 049 | [创意色彩 · Woelfelly Neon](look-profiles/001-100.md#preset-sp-woelfelly-neon)<br>`sp-woelfelly-neon` | 冷色 · 压暗中灰 · 中段收窄 | 赛博情绪、音乐、霓虹配色设计 | 0.35–0.8 | MIT |
| 050 | [黑白胶片 · AGFA APX 100](look-profiles/001-100.md#preset-t3-agfa-apx-100)<br>`t3-agfa-apx-100` | 黑白 · 提亮中灰 · 中段跨度接近原值 | 明亮黑白、柔和回忆、清晰人物 | 1–1 | MIT |
| 051 | [黑白胶片 · AGFA APX 25](look-profiles/001-100.md#preset-t3-agfa-apx-25)<br>`t3-agfa-apx-25` | 黑白 · 提亮中灰 · 中段拉开 | 较有深度的明亮黑白、人物纪实 | 1–1 | MIT |
| 052 | [彩色负片 · Agfa Vista 100](look-profiles/001-100.md#preset-t3-agfa-vista-100)<br>`t3-agfa-vista-100` | 中性 · 提亮中灰 · 中段拉开 | 日光旅行、暖色商品故事、复古生活 | 0.35–0.8 | MIT |
| 053 | [彩色负片 · Agfa Vista 200](look-profiles/001-100.md#preset-t3-agfa-vista-200)<br>`t3-agfa-vista-200` | 中性 · 中灰近原值 · 中段拉开 | 日常彩色、城市旅行、温和复古 | 0.35–0.8 | MIT |
| 054 | [彩色负片 · Agfa Vista 400](look-profiles/001-100.md#preset-t3-agfa-vista-400)<br>`t3-agfa-vista-400` | 中性 · 提亮中灰 · 中段拉开 | 鲜明街景、旅行、活泼生活片 | 0.35–0.8 | MIT |
| 055 | [反转片 · Fuji Astia 100F](look-profiles/001-100.md#preset-t3-fuji-astia-100f)<br>`t3-fuji-astia-100f` | 中性 · 提亮中灰 · 中段跨度接近原值 | 日光人物、柔和旅行、服装生活片 | 0.35–0.8 | MIT |
| 056 | [反转片 · Fuji Fortia SP 50](look-profiles/001-100.md#preset-t3-fuji-fortia-sp-50)<br>`t3-fuji-fortia-sp-50` | 中性 · 提亮中灰 · 中段拉开 | 高彩风景、蓝天、强色彩片段 | 0.35–0.8 | MIT |
| 057 | [黑白胶片 · Fuji Neopan 1600](look-profiles/001-100.md#preset-t3-fuji-neopan-1600)<br>`t3-fuji-neopan-1600` | 黑白 · 提亮中灰 · 中段拉开 | 反差黑白、街头、人物叙事 | 1–1 | MIT |
| 058 | [黑白胶片 · Fuji Neopan Acros 100](look-profiles/001-100.md#preset-t3-fuji-neopan-acros-100)<br>`t3-fuji-neopan-acros-100` | 黑白 · 压暗中灰 · 中段拉开 | 安静黑白、建筑、低调人物 | 1–1 | MIT |
| 059 | [彩色负片 · Fuji Pro 160C](look-profiles/001-100.md#preset-t3-fuji-pro-160c)<br>`t3-fuji-pro-160c` | 中性 · 提亮中灰 · 中段拉开 | 暖调人物、生活方式、日光街拍 | 0.35–0.8 | MIT |
| 060 | [彩色负片 · Fuji Pro 400H](look-profiles/001-100.md#preset-t3-fuji-pro-400h)<br>`t3-fuji-pro-400h` | 暖色 · 提亮中灰 · 中段跨度接近原值 | 明亮人物、旅行、彩色生活片 | 0.35–0.8 | MIT |
| 061 | [彩色负片 · Fuji Pro 800Z](look-profiles/001-100.md#preset-t3-fuji-pro-800z)<br>`t3-fuji-pro-800z` | 暖色 · 提亮中灰 · 中段拉开 | 暖室内故事、旅行、人物生活片 | 0.35–0.8 | MIT |
| 062 | [反转片 · Fuji Provia 100F](look-profiles/001-100.md#preset-t3-fuji-provia-100f)<br>`t3-fuji-provia-100f` | 中性 · 提亮中灰 · 中段拉开 | 旅行、城市风景、日光生活 | 0.35–0.8 | MIT |
| 063 | [反转片 · Fuji Provia 400F](look-profiles/001-100.md#preset-t3-fuji-provia-400f)<br>`t3-fuji-provia-400f` | 中性 · 中灰近原值 · 中段跨度接近原值 | 克制风景、人物环境、城市纪实 | 0.35–0.8 | MIT |
| 064 | [反转片 · Fuji Provia 400X](look-profiles/001-100.md#preset-t3-fuji-provia-400x)<br>`t3-fuji-provia-400x` | 中性 · 提亮中灰 · 中段跨度接近原值 | 复古风景、彩色生活、低白端氛围 | 0.35–0.8 | MIT |
| 065 | [反转片 · Fuji Sensia 100](look-profiles/001-100.md#preset-t3-fuji-sensia-100)<br>`t3-fuji-sensia-100` | 中性 · 提亮中灰 · 中段拉开 | 旅行回忆、日常人物、暖日光 | 0.35–0.8 | MIT |
| 066 | [彩色负片 · Fuji Superia 100](look-profiles/001-100.md#preset-t3-fuji-superia-100)<br>`t3-fuji-superia-100` | 冷色 · 提亮中灰 · 中段拉开 | 城市日常、旅行、冷暖人物环境 | 0.35–0.8 | MIT |
| 067 | [彩色负片 · Fuji Superia 1600](look-profiles/001-100.md#preset-t3-fuji-superia-1600)<br>`t3-fuji-superia-1600` | 中性 · 提亮中灰 · 中段拉开 | 明亮街头、生活记录、暖人物 | 0.35–0.8 | MIT |
| 068 | [彩色负片 · Fuji Superia 200](look-profiles/001-100.md#preset-t3-fuji-superia-200)<br>`t3-fuji-superia-200` | 中性 · 提亮中灰 · 中段拉开 | 彩色街景、旅行、生活方式 | 0.35–0.8 | MIT |
| 069 | [彩色负片 · Fuji Superia 400](look-profiles/001-100.md#preset-t3-fuji-superia-400)<br>`t3-fuji-superia-400` | 中性 · 提亮中灰 · 中段拉开 | 日光生活、旅行、暖色人物 | 0.35–0.8 | MIT |
| 070 | [彩色负片 · Fuji Superia 800](look-profiles/001-100.md#preset-t3-fuji-superia-800)<br>`t3-fuji-superia-800` | 冷色 · 提亮中灰 · 中段拉开 | 城市傍晚配色、冷暖环境人物 | 0.35–0.8 | MIT |
| 071 | [彩色负片 · Fuji Superia HG 1600](look-profiles/001-100.md#preset-t3-fuji-superia-hg-1600)<br>`t3-fuji-superia-hg-1600` | 中性 · 提亮中灰 · 中段跨度接近原值 | 较克制生活片、人物与环境共存 | 0.35–0.8 | MIT |
| 072 | [反转片 · Fuji Velvia 100](look-profiles/001-100.md#preset-t3-fuji-velvia-100)<br>`t3-fuji-velvia-100` | 中性 · 提亮中灰 · 中段拉开 | 高彩风景、绿植、城市色块 | 0.35–0.8 | MIT |
| 073 | [反转片 · Fuji Velvia 50](look-profiles/001-100.md#preset-t3-fuji-velvia-50)<br>`t3-fuji-velvia-50` | 中性 · 压暗中灰 · 中段拉开 | 深色风景、绿植、强色彩构图 | 0.35–0.8 | MIT |
| 074 | [黑白胶片 · Ilford Delta 100](look-profiles/001-100.md#preset-t3-ilford-delta-100)<br>`t3-ilford-delta-100` | 黑白 · 提亮中灰 · 中段拉开 | 黑白人物、建筑、均衡纪实 | 1–1 | MIT |
| 075 | [黑白胶片 · Ilford Delta 3200](look-profiles/001-100.md#preset-t3-ilford-delta-3200)<br>`t3-ilford-delta-3200` | 黑白 · 提亮中灰 · 中段拉开 | 抬黑黑白、人物回忆、柔和街头 | 1–1 | MIT |
| 076 | [黑白胶片 · Ilford Delta 400](look-profiles/001-100.md#preset-t3-ilford-delta-400)<br>`t3-ilford-delta-400` | 黑白 · 提亮中灰 · 中段拉开 | 深黑纪实、建筑轮廓、黑白故事 | 1–1 | MIT |
| 077 | [黑白胶片 · Ilford FP4 125](look-profiles/001-100.md#preset-t3-ilford-fp4-125)<br>`t3-ilford-fp4-125` | 黑白 · 提亮中灰 · 中段拉开 | 温和黑白人物、日常纪实、回忆 | 1–1 | MIT |
| 078 | [黑白胶片 · Ilford HP5 Plus 400](look-profiles/001-100.md#preset-t3-ilford-hp5-plus-400)<br>`t3-ilford-hp5-plus-400` | 黑白 · 压暗中灰 · 中段拉开 | 街头、戏剧人物、强明暗叙事 | 1–1 | MIT |
| 079 | [黑白胶片 · Ilford XP2](look-profiles/001-100.md#preset-t3-ilford-xp2)<br>`t3-ilford-xp2` | 黑白 · 压暗中灰 · 中段拉开 | 暗调人像、安静纪实、轮廓叙事 | 1–1 | MIT |
| 080 | [彩色负片 · Kodak ColorPlus 200](look-profiles/001-100.md#preset-t3-kodak-colorplus-200)<br>`t3-kodak-colorplus-200` | 中性 · 提亮中灰 · 中段拉开 | 阳光生活、旅行、暖色复古广告 | 0.35–0.8 | MIT |
| 081 | [反转片 · Kodak Ektachrome 100 G](look-profiles/001-100.md#preset-t3-kodak-ektachrome-100-g)<br>`t3-kodak-ektachrome-100-g` | 中性 · 提亮中灰 · 中段拉开 | 旅行、风景、冷暖人物场景 | 0.35–0.8 | MIT |
| 082 | [反转片 · Kodak Ektachrome 100 GX](look-profiles/001-100.md#preset-t3-kodak-ektachrome-100-gx)<br>`t3-kodak-ektachrome-100-gx` | 中性 · 中灰近原值 · 中段拉开 | 较柔和人物环境、温暖日常 | 0.35–0.8 | MIT |
| 083 | [反转片 · Kodak Ektachrome 100 VS](look-profiles/001-100.md#preset-t3-kodak-ektachrome-100-vs)<br>`t3-kodak-ektachrome-100-vs` | 中性 · 提亮中灰 · 中段拉开 | 彩色街景、复古人物、浓彩设计 | 0.35–0.8 | MIT |
| 084 | [彩色负片 · Kodak Ektar 100](look-profiles/001-100.md#preset-t3-kodak-ektar-100)<br>`t3-kodak-ektar-100` | 中性 · 提亮中灰 · 中段拉开 | 高彩商品故事、旅行、色块风景 | 0.35–0.8 | MIT |
| 085 | [反转片 · Kodak Elite Chrome 400](look-profiles/001-100.md#preset-t3-kodak-elite-chrome-400)<br>`t3-kodak-elite-chrome-400` | 中性 · 压暗中灰 · 中段拉开 | 深色街景、克制复古、静物叙事 | 0.35–0.8 | MIT |
| 086 | [彩色负片 · Kodak Gold 200](look-profiles/001-100.md#preset-t3-kodak-gold-200)<br>`t3-kodak-gold-200` | 中性 · 提亮中灰 · 中段拉开 | 日光回忆、暖人物、生活方式广告 | 0.35–0.8 | MIT |
| 087 | [反转片 · Kodak Kodakchrome 200](look-profiles/001-100.md#preset-t3-kodak-kodakchrome-200)<br>`t3-kodak-kodakchrome-200` | 中性 · 提亮中灰 · 中段拉开 | 克制复古彩色、旅行、人物环境 | 0.35–0.8 | MIT |
| 088 | [反转片 · Kodak Kodakchrome 25](look-profiles/001-100.md#preset-t3-kodak-kodakchrome-25)<br>`t3-kodak-kodakchrome-25` | 冷色 · 提亮中灰 · 中段拉开 | 青影暖肤、复古旅行、轻冷纪实 | 0.35–0.8 | MIT |
| 089 | [反转片 · Kodak Kodakchrome 64](look-profiles/001-100.md#preset-t3-kodak-kodakchrome-64)<br>`t3-kodak-kodakchrome-64` | 中性 · 提亮中灰 · 中段拉开 | 轻复古彩色、人物与环境、旅行 | 0.35–0.8 | MIT |
| 090 | [彩色负片 · Kodak Portra 160](look-profiles/001-100.md#preset-t3-kodak-portra-160)<br>`t3-kodak-portra-160` | 冷色 · 提亮中灰 · 中段拉开 | 日光人物、生活方式、旅行 | 0.35–0.8 | MIT |
| 091 | [彩色负片 · Kodak Portra 160 NC](look-profiles/001-100.md#preset-t3-kodak-portra-160-nc)<br>`t3-kodak-portra-160-nc` | 中性 · 提亮中灰 · 中段跨度接近原值 | 柔和人物、明亮回忆、低反差日光 | 0.35–0.8 | MIT |
| 092 | [彩色负片 · Kodak Portra 160 VC](look-profiles/001-100.md#preset-t3-kodak-portra-160-vc)<br>`t3-kodak-portra-160-vc` | 中性 · 提亮中灰 · 中段拉开 | 彩色人物环境、暖调旅行 | 0.35–0.8 | MIT |
| 093 | [彩色负片 · Kodak Portra 400](look-profiles/001-100.md#preset-t3-kodak-portra-400)<br>`t3-kodak-portra-400` | 中性 · 提亮中灰 · 中段拉开 | 暖人物、日常广告、旅行故事 | 0.35–0.8 | MIT |
| 094 | [彩色负片 · Kodak Portra 400 NC](look-profiles/001-100.md#preset-t3-kodak-portra-400-nc)<br>`t3-kodak-portra-400-nc` | 中性 · 提亮中灰 · 中段拉开 | 柔白端人物、复古纪实、生活片 | 0.35–0.8 | MIT |
| 095 | [彩色负片 · Kodak Portra 400 UC](look-profiles/001-100.md#preset-t3-kodak-portra-400-uc)<br>`t3-kodak-portra-400-uc` | 中性 · 提亮中灰 · 中段拉开 | 高彩日常、街拍、暖人物广告 | 0.35–0.8 | MIT |
| 096 | [彩色负片 · Kodak Portra 400 VC](look-profiles/001-100.md#preset-t3-kodak-portra-400-vc)<br>`t3-kodak-portra-400-vc` | 中性 · 提亮中灰 · 中段拉开 | 有人物也有蓝天蓝衣的彩色场景 | 0.35–0.8 | MIT |
| 097 | [彩色负片 · Kodak Portra 800](look-profiles/001-100.md#preset-t3-kodak-portra-800)<br>`t3-kodak-portra-800` | 中性 · 提亮中灰 · 中段拉开 | 明亮人物、彩色生活方式、旅行 | 0.35–0.8 | MIT |
| 098 | [黑白胶片 · Kodak T-Max 3200](look-profiles/001-100.md#preset-t3-kodak-t-max-3200)<br>`t3-kodak-t-max-3200` | 黑白 · 提亮中灰 · 中段拉开 | 明亮反差黑白、街头、人物叙事 | 1–1 | MIT |
| 099 | [黑白胶片 · Kodak Tri-X 400](look-profiles/001-100.md#preset-t3-kodak-tri-x-400)<br>`t3-kodak-tri-x-400` | 黑白 · 提亮中灰 · 中段拉开 | 戏剧黑白、人物纪实、街拍 | 1–1 | MIT |
| 100 | [彩色负片 · Kodak Ultra Max 400](look-profiles/001-100.md#preset-t3-kodak-ultra-max-400)<br>`t3-kodak-ultra-max-400` | 中性 · 提亮中灰 · 中段拉开 | 日光旅行、生活方式、活泼彩色广告 | 0.35–0.8 | MIT |
| 101 | [黑白胶片 · Agfa Apx 100｜黑白 · 提亮中灰 · 中段拉开](look-profiles/101-200.md#preset-nt-bw-agfa-apx-100)<br>`nt-bw-agfa-apx-100` | 黑白 · 提亮中灰 · 中段拉开 | 黑白纪实、建筑与轮廓试片 | 1–1 | CC-BY-SA-4.0 |
| 102 | [黑白胶片 · Agfa Apx 25｜黑白 · 提亮中灰 · 中段拉开](look-profiles/101-200.md#preset-nt-bw-agfa-apx-25)<br>`nt-bw-agfa-apx-25` | 黑白 · 提亮中灰 · 中段拉开 | 黑白纪实、建筑与轮廓试片 | 1–1 | CC-BY-SA-4.0 |
| 103 | [黑白胶片 · Fuji Neopan 1600｜黑白 · 提亮中灰 · 中段拉开](look-profiles/101-200.md#preset-nt-bw-fuji-neopan-1600)<br>`nt-bw-fuji-neopan-1600` | 黑白 · 提亮中灰 · 中段拉开 | 黑白纪实、建筑与轮廓试片 | 1–1 | CC-BY-SA-4.0 |
| 104 | [黑白胶片 · Fuji Neopan Acros 100｜黑白 · 压暗中灰 · 中段跨度接近原值](look-profiles/101-200.md#preset-nt-bw-fuji-neopan-acros-100)<br>`nt-bw-fuji-neopan-acros-100` | 黑白 · 压暗中灰 · 中段跨度接近原值 | 黑白纪实、建筑与轮廓试片 | 1–1 | CC-BY-SA-4.0 |
| 105 | [黑白胶片 · Ilford Delta 100｜黑白 · 提亮中灰 · 中段拉开](look-profiles/101-200.md#preset-nt-bw-ilford-delta-100)<br>`nt-bw-ilford-delta-100` | 黑白 · 提亮中灰 · 中段拉开 | 黑白纪实、建筑与轮廓试片 | 1–1 | CC-BY-SA-4.0 |
| 106 | [黑白胶片 · Ilford Delta 3200｜黑白 · 中灰近原值 · 中段跨度接近原值](look-profiles/101-200.md#preset-nt-bw-ilford-delta-3200)<br>`nt-bw-ilford-delta-3200` | 黑白 · 中灰近原值 · 中段跨度接近原值 | 黑白纪实、建筑与轮廓试片 | 1–1 | CC-BY-SA-4.0 |
| 107 | [黑白胶片 · Ilford Delta 400｜黑白 · 压暗中灰 · 中段拉开](look-profiles/101-200.md#preset-nt-bw-ilford-delta-400)<br>`nt-bw-ilford-delta-400` | 黑白 · 压暗中灰 · 中段拉开 | 黑白纪实、建筑与轮廓试片 | 1–1 | CC-BY-SA-4.0 |
| 108 | [黑白胶片 · Ilford Fp4 Plus 125｜黑白 · 提亮中灰 · 中段跨度接近原值](look-profiles/101-200.md#preset-nt-bw-ilford-fp4-plus-125)<br>`nt-bw-ilford-fp4-plus-125` | 黑白 · 提亮中灰 · 中段跨度接近原值 | 黑白纪实、建筑与轮廓试片 | 1–1 | CC-BY-SA-4.0 |
| 109 | [黑白胶片 · Ilford Hp5 Plus 400｜黑白 · 提亮中灰 · 中段拉开](look-profiles/101-200.md#preset-nt-bw-ilford-hp5-plus-400)<br>`nt-bw-ilford-hp5-plus-400` | 黑白 · 提亮中灰 · 中段拉开 | 黑白纪实、建筑与轮廓试片 | 1–1 | CC-BY-SA-4.0 |
| 110 | [黑白胶片 · Ilford Hps 800｜黑白 · 中灰近原值 · 中段拉开](look-profiles/101-200.md#preset-nt-bw-ilford-hps-800)<br>`nt-bw-ilford-hps-800` | 黑白 · 中灰近原值 · 中段拉开 | 黑白纪实、建筑与轮廓试片 | 1–1 | CC-BY-SA-4.0 |
| 111 | [黑白胶片 · Ilford Pan F Plus 50｜黑白 · 提亮中灰 · 中段拉开](look-profiles/101-200.md#preset-nt-bw-ilford-pan-f-plus-50)<br>`nt-bw-ilford-pan-f-plus-50` | 黑白 · 提亮中灰 · 中段拉开 | 黑白纪实、建筑与轮廓试片 | 1–1 | CC-BY-SA-4.0 |
| 112 | [黑白胶片 · Ilford Xp2｜黑白 · 压暗中灰 · 中段拉开](look-profiles/101-200.md#preset-nt-bw-ilford-xp2)<br>`nt-bw-ilford-xp2` | 黑白 · 压暗中灰 · 中段拉开 | 黑白纪实、建筑与轮廓试片 | 1–1 | CC-BY-SA-4.0 |
| 113 | [黑白胶片 · Kodak Bw 400 Cn｜黑白 · 压暗中灰 · 中段拉开](look-profiles/101-200.md#preset-nt-bw-kodak-bw-400-cn)<br>`nt-bw-kodak-bw-400-cn` | 黑白 · 压暗中灰 · 中段拉开 | 黑白纪实、建筑与轮廓试片 | 1–1 | CC-BY-SA-4.0 |
| 114 | [黑白胶片 · Kodak Hie (Hs Infra)｜黑白 · 提亮中灰 · 中段拉开](look-profiles/101-200.md#preset-nt-bw-kodak-hie-hs-infra)<br>`nt-bw-kodak-hie-hs-infra` | 黑白 · 提亮中灰 · 中段拉开 | 黑白纪实、建筑与轮廓试片 | 1–1 | CC-BY-SA-4.0 |
| 115 | [黑白胶片 · Kodak T-Max 100｜黑白 · 压暗中灰 · 中段拉开](look-profiles/101-200.md#preset-nt-bw-kodak-t-max-100)<br>`nt-bw-kodak-t-max-100` | 黑白 · 压暗中灰 · 中段拉开 | 黑白纪实、建筑与轮廓试片 | 1–1 | CC-BY-SA-4.0 |
| 116 | [黑白胶片 · Kodak T-Max 3200｜黑白 · 提亮中灰 · 中段拉开](look-profiles/101-200.md#preset-nt-bw-kodak-t-max-3200)<br>`nt-bw-kodak-t-max-3200` | 黑白 · 提亮中灰 · 中段拉开 | 黑白纪实、建筑与轮廓试片 | 1–1 | CC-BY-SA-4.0 |
| 117 | [黑白胶片 · Kodak T-Max 400｜黑白 · 提亮中灰 · 中段拉开](look-profiles/101-200.md#preset-nt-bw-kodak-t-max-400)<br>`nt-bw-kodak-t-max-400` | 黑白 · 提亮中灰 · 中段拉开 | 黑白纪实、建筑与轮廓试片 | 1–1 | CC-BY-SA-4.0 |
| 118 | [黑白胶片 · Kodak Tri-X 400｜黑白 · 提亮中灰 · 中段跨度接近原值](look-profiles/101-200.md#preset-nt-bw-kodak-tri-x-400)<br>`nt-bw-kodak-tri-x-400` | 黑白 · 提亮中灰 · 中段跨度接近原值 | 黑白纪实、建筑与轮廓试片 | 1–1 | CC-BY-SA-4.0 |
| 119 | [黑白胶片 · Polaroid 664｜黑白 · 提亮中灰 · 中段收窄](look-profiles/101-200.md#preset-nt-bw-polaroid-664)<br>`nt-bw-polaroid-664` | 黑白 · 提亮中灰 · 中段收窄 | 黑白纪实、建筑与轮廓试片 | 1–1 | CC-BY-SA-4.0 |
| 120 | [黑白胶片 · Polaroid 667｜黑白 · 提亮中灰 · 中段拉开](look-profiles/101-200.md#preset-nt-bw-polaroid-667)<br>`nt-bw-polaroid-667` | 黑白 · 提亮中灰 · 中段拉开 | 黑白纪实、建筑与轮廓试片 | 1–1 | CC-BY-SA-4.0 |
| 121 | [黑白胶片 · Polaroid 672｜黑白 · 压暗中灰 · 中段拉开](look-profiles/101-200.md#preset-nt-bw-polaroid-672)<br>`nt-bw-polaroid-672` | 黑白 · 压暗中灰 · 中段拉开 | 黑白纪实、建筑与轮廓试片 | 1–1 | CC-BY-SA-4.0 |
| 122 | [黑白胶片 · Rollei Ir 400｜黑白 · 压暗中灰 · 中段拉开](look-profiles/101-200.md#preset-nt-bw-rollei-ir-400)<br>`nt-bw-rollei-ir-400` | 黑白 · 压暗中灰 · 中段拉开 | 黑白纪实、建筑与轮廓试片 | 1–1 | CC-BY-SA-4.0 |
| 123 | [黑白胶片 · Rollei Ortho 25｜黑白 · 提亮中灰 · 中段拉开](look-profiles/101-200.md#preset-nt-bw-rollei-ortho-25)<br>`nt-bw-rollei-ortho-25` | 黑白 · 提亮中灰 · 中段拉开 | 黑白纪实、建筑与轮廓试片 | 1–1 | CC-BY-SA-4.0 |
| 124 | [黑白胶片 · Rollei Retro 100 Tonal｜黑白 · 提亮中灰 · 中段拉开](look-profiles/101-200.md#preset-nt-bw-rollei-retro-100-tonal)<br>`nt-bw-rollei-retro-100-tonal` | 黑白 · 提亮中灰 · 中段拉开 | 黑白纪实、建筑与轮廓试片 | 1–1 | CC-BY-SA-4.0 |
| 125 | [黑白胶片 · Rollei Retro 80S｜黑白 · 压暗中灰 · 中段拉开](look-profiles/101-200.md#preset-nt-bw-rollei-retro-80s)<br>`nt-bw-rollei-retro-80s` | 黑白 · 压暗中灰 · 中段拉开 | 黑白纪实、建筑与轮廓试片 | 1–1 | CC-BY-SA-4.0 |
| 126 | [反转片 · Agfa Precisa 100｜中性 · 压暗中灰 · 中段拉开](look-profiles/101-200.md#preset-nt-colorslide-agfa-precisa-100)<br>`nt-colorslide-agfa-precisa-100` | 中性 · 压暗中灰 · 中段拉开 | 产品、生活与风景对照试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 127 | [反转片 · Fuji Astia 100F｜中性 · 中灰近原值 · 中段跨度接近原值](look-profiles/101-200.md#preset-nt-colorslide-fuji-astia-100f)<br>`nt-colorslide-fuji-astia-100f` | 中性 · 中灰近原值 · 中段跨度接近原值 | 产品、生活与风景对照试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 128 | [反转片 · Fuji Fp 100C｜中性 · 中灰近原值 · 中段拉开](look-profiles/101-200.md#preset-nt-colorslide-fuji-fp-100c)<br>`nt-colorslide-fuji-fp-100c` | 中性 · 中灰近原值 · 中段拉开 | 产品、生活与风景对照试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 129 | [反转片 · Fuji Provia 100F｜中性 · 压暗中灰 · 中段拉开](look-profiles/101-200.md#preset-nt-colorslide-fuji-provia-100f)<br>`nt-colorslide-fuji-provia-100f` | 中性 · 压暗中灰 · 中段拉开 | 产品、生活与风景对照试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 130 | [反转片 · Fuji Provia 400F｜中性 · 中灰近原值 · 中段拉开](look-profiles/101-200.md#preset-nt-colorslide-fuji-provia-400f)<br>`nt-colorslide-fuji-provia-400f` | 中性 · 中灰近原值 · 中段拉开 | 产品、生活与风景对照试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 131 | [反转片 · Fuji Provia 400X｜中性 · 压暗中灰 · 中段跨度接近原值](look-profiles/101-200.md#preset-nt-colorslide-fuji-provia-400x)<br>`nt-colorslide-fuji-provia-400x` | 中性 · 压暗中灰 · 中段跨度接近原值 | 产品、生活与风景对照试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 132 | [反转片 · Fuji Sensia 100｜中性 · 提亮中灰 · 中段拉开](look-profiles/101-200.md#preset-nt-colorslide-fuji-sensia-100)<br>`nt-colorslide-fuji-sensia-100` | 中性 · 提亮中灰 · 中段拉开 | 产品、生活与风景对照试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 133 | [反转片 · Fuji Superia 200 Xpro｜冷色 · 压暗中灰 · 中段收窄](look-profiles/101-200.md#preset-nt-colorslide-fuji-superia-200-xpro)<br>`nt-colorslide-fuji-superia-200-xpro` | 冷色 · 压暗中灰 · 中段收窄 | 冷色城市、夜景与科技试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 134 | [反转片 · Fuji Velvia 50｜中性 · 压暗中灰 · 中段拉开](look-profiles/101-200.md#preset-nt-colorslide-fuji-velvia-50)<br>`nt-colorslide-fuji-velvia-50` | 中性 · 压暗中灰 · 中段拉开 | 产品、生活与风景对照试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 135 | [反转片 · Generic Fuji Astia 100｜中性 · 中灰近原值 · 中段跨度接近原值](look-profiles/101-200.md#preset-nt-colorslide-generic-fuji-astia-100)<br>`nt-colorslide-generic-fuji-astia-100` | 中性 · 中灰近原值 · 中段跨度接近原值 | 产品、生活与风景对照试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 136 | [反转片 · Generic Fuji Provia 100｜中性 · 提亮中灰 · 中段拉开](look-profiles/101-200.md#preset-nt-colorslide-generic-fuji-provia-100)<br>`nt-colorslide-generic-fuji-provia-100` | 中性 · 提亮中灰 · 中段拉开 | 产品、生活与风景对照试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 137 | [反转片 · Generic Fuji Velvia 100｜中性 · 提亮中灰 · 中段拉开](look-profiles/101-200.md#preset-nt-colorslide-generic-fuji-velvia-100)<br>`nt-colorslide-generic-fuji-velvia-100` | 中性 · 提亮中灰 · 中段拉开 | 产品、生活与风景对照试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 138 | [反转片 · Generic Kodachrome 64｜中性 · 中灰近原值 · 中段拉开](look-profiles/101-200.md#preset-nt-colorslide-generic-kodachrome-64)<br>`nt-colorslide-generic-kodachrome-64` | 中性 · 中灰近原值 · 中段拉开 | 产品、生活与风景对照试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 139 | [反转片 · Generic Kodak Ektachrome 100 Vs｜暖色 · 中灰近原值 · 中段拉开](look-profiles/101-200.md#preset-nt-colorslide-generic-kodak-ektachrome-100-vs)<br>`nt-colorslide-generic-kodak-ektachrome-100-vs` | 暖色 · 中灰近原值 · 中段拉开 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 140 | [反转片 · Kodak E-100 Gx Ektachrome 100｜冷色 · 中灰近原值 · 中段拉开](look-profiles/101-200.md#preset-nt-colorslide-kodak-e-100-gx-ektachrome-100)<br>`nt-colorslide-kodak-e-100-gx-ektachrome-100` | 冷色 · 中灰近原值 · 中段拉开 | 冷色城市、夜景与科技试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 141 | [反转片 · Kodak Ektachrome 100 Vs｜中性 · 压暗中灰 · 中段拉开](look-profiles/101-200.md#preset-nt-colorslide-kodak-ektachrome-100-vs)<br>`nt-colorslide-kodak-ektachrome-100-vs` | 中性 · 压暗中灰 · 中段拉开 | 产品、生活与风景对照试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 142 | [反转片 · Kodak Elite Chrome 200｜中性 · 压暗中灰 · 中段拉开](look-profiles/101-200.md#preset-nt-colorslide-kodak-elite-chrome-200)<br>`nt-colorslide-kodak-elite-chrome-200` | 中性 · 压暗中灰 · 中段拉开 | 产品、生活与风景对照试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 143 | [反转片 · Kodak Elite Chrome 400｜中性 · 中灰近原值 · 中段拉开](look-profiles/101-200.md#preset-nt-colorslide-kodak-elite-chrome-400)<br>`nt-colorslide-kodak-elite-chrome-400` | 中性 · 中灰近原值 · 中段拉开 | 产品、生活与风景对照试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 144 | [反转片 · Kodak Elite Extracolor 100｜中性 · 压暗中灰 · 中段拉开](look-profiles/101-200.md#preset-nt-colorslide-kodak-elite-extracolor-100)<br>`nt-colorslide-kodak-elite-extracolor-100` | 中性 · 压暗中灰 · 中段拉开 | 产品、生活与风景对照试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 145 | [反转片 · Kodak Kodachrome 200｜中性 · 提亮中灰 · 中段跨度接近原值](look-profiles/101-200.md#preset-nt-colorslide-kodak-kodachrome-200)<br>`nt-colorslide-kodak-kodachrome-200` | 中性 · 提亮中灰 · 中段跨度接近原值 | 产品、生活与风景对照试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 146 | [反转片 · Kodak Kodachrome 25｜冷色 · 提亮中灰 · 中段拉开](look-profiles/101-200.md#preset-nt-colorslide-kodak-kodachrome-25)<br>`nt-colorslide-kodak-kodachrome-25` | 冷色 · 提亮中灰 · 中段拉开 | 冷色城市、夜景与科技试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 147 | [反转片 · Kodak Kodachrome 64｜中性 · 提亮中灰 · 中段拉开](look-profiles/101-200.md#preset-nt-colorslide-kodak-kodachrome-64)<br>`nt-colorslide-kodak-kodachrome-64` | 中性 · 提亮中灰 · 中段拉开 | 产品、生活与风景对照试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 148 | [反转片 · Lomography X-Pro Slide 200｜中性 · 提亮中灰 · 中段拉开](look-profiles/101-200.md#preset-nt-colorslide-lomography-x-pro-slide-200)<br>`nt-colorslide-lomography-x-pro-slide-200` | 中性 · 提亮中灰 · 中段拉开 | 产品、生活与风景对照试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 149 | [反转片 · Polaroid 669｜暖色 · 提亮中灰 · 中段拉开](look-profiles/101-200.md#preset-nt-colorslide-polaroid-669)<br>`nt-colorslide-polaroid-669` | 暖色 · 提亮中灰 · 中段拉开 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 150 | [反转片 · Polaroid 690｜中性 · 提亮中灰 · 中段拉开](look-profiles/101-200.md#preset-nt-colorslide-polaroid-690)<br>`nt-colorslide-polaroid-690` | 中性 · 提亮中灰 · 中段拉开 | 产品、生活与风景对照试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 151 | [反转片 · Polaroid Polachrome｜暖色 · 提亮中灰 · 中段拉开](look-profiles/101-200.md#preset-nt-colorslide-polaroid-polachrome)<br>`nt-colorslide-polaroid-polachrome` | 暖色 · 提亮中灰 · 中段拉开 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 152 | [大众拍立得 · Polaroid Px-100Uv+ Cold｜中性 · 提亮中灰 · 中段收窄](look-profiles/101-200.md#preset-nt-instant-consumer-polaroid-px-100uv-plus-cold)<br>`nt-instant-consumer-polaroid-px-100uv-plus-cold` | 中性 · 提亮中灰 · 中段收窄 | 产品、生活与风景对照试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 153 | [大众拍立得 · Polaroid Px-100Uv+ Cold +++｜暖色 · 提亮中灰 · 中段收窄](look-profiles/101-200.md#preset-nt-instant-consumer-polaroid-px-100uv-plus-cold-curve-plus-3)<br>`nt-instant-consumer-polaroid-px-100uv-plus-cold-curve-plus-3` | 暖色 · 提亮中灰 · 中段收窄 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 154 | [大众拍立得 · Polaroid Px-100Uv+ Cold ++｜中性 · 提亮中灰 · 中段收窄](look-profiles/101-200.md#preset-nt-instant-consumer-polaroid-px-100uv-plus-cold-curve-plus-2)<br>`nt-instant-consumer-polaroid-px-100uv-plus-cold-curve-plus-2` | 中性 · 提亮中灰 · 中段收窄 | 产品、生活与风景对照试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 155 | [大众拍立得 · Polaroid Px-100Uv+ Cold +｜中性 · 提亮中灰 · 中段收窄](look-profiles/101-200.md#preset-nt-instant-consumer-polaroid-px-100uv-plus-cold-curve-plus-1)<br>`nt-instant-consumer-polaroid-px-100uv-plus-cold-curve-plus-1` | 中性 · 提亮中灰 · 中段收窄 | 产品、生活与风景对照试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 156 | [大众拍立得 · Polaroid Px-100Uv+ Cold --｜中性 · 提亮中灰 · 中段收窄](look-profiles/101-200.md#preset-nt-instant-consumer-polaroid-px-100uv-plus-cold-curve-minus-2)<br>`nt-instant-consumer-polaroid-px-100uv-plus-cold-curve-minus-2` | 中性 · 提亮中灰 · 中段收窄 | 产品、生活与风景对照试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 157 | [大众拍立得 · Polaroid Px-100Uv+ Cold -｜中性 · 提亮中灰 · 中段跨度接近原值](look-profiles/101-200.md#preset-nt-instant-consumer-polaroid-px-100uv-plus-cold-curve-minus-1)<br>`nt-instant-consumer-polaroid-px-100uv-plus-cold-curve-minus-1` | 中性 · 提亮中灰 · 中段跨度接近原值 | 产品、生活与风景对照试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 158 | [大众拍立得 · Polaroid Px-100Uv+ Warm｜暖色 · 提亮中灰 · 中段收窄](look-profiles/101-200.md#preset-nt-instant-consumer-polaroid-px-100uv-plus-warm)<br>`nt-instant-consumer-polaroid-px-100uv-plus-warm` | 暖色 · 提亮中灰 · 中段收窄 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 159 | [大众拍立得 · Polaroid Px-100Uv+ Warm +++｜暖色 · 提亮中灰 · 中段收窄](look-profiles/101-200.md#preset-nt-instant-consumer-polaroid-px-100uv-plus-warm-curve-plus-3)<br>`nt-instant-consumer-polaroid-px-100uv-plus-warm-curve-plus-3` | 暖色 · 提亮中灰 · 中段收窄 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 160 | [大众拍立得 · Polaroid Px-100Uv+ Warm ++｜暖色 · 提亮中灰 · 中段收窄](look-profiles/101-200.md#preset-nt-instant-consumer-polaroid-px-100uv-plus-warm-curve-plus-2)<br>`nt-instant-consumer-polaroid-px-100uv-plus-warm-curve-plus-2` | 暖色 · 提亮中灰 · 中段收窄 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 161 | [大众拍立得 · Polaroid Px-100Uv+ Warm +｜暖色 · 提亮中灰 · 中段收窄](look-profiles/101-200.md#preset-nt-instant-consumer-polaroid-px-100uv-plus-warm-curve-plus-1)<br>`nt-instant-consumer-polaroid-px-100uv-plus-warm-curve-plus-1` | 暖色 · 提亮中灰 · 中段收窄 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 162 | [大众拍立得 · Polaroid Px-100Uv+ Warm --｜暖色 · 提亮中灰 · 中段收窄](look-profiles/101-200.md#preset-nt-instant-consumer-polaroid-px-100uv-plus-warm-curve-minus-2)<br>`nt-instant-consumer-polaroid-px-100uv-plus-warm-curve-minus-2` | 暖色 · 提亮中灰 · 中段收窄 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 163 | [大众拍立得 · Polaroid Px-100Uv+ Warm -｜暖色 · 提亮中灰 · 中段收窄](look-profiles/101-200.md#preset-nt-instant-consumer-polaroid-px-100uv-plus-warm-curve-minus-1)<br>`nt-instant-consumer-polaroid-px-100uv-plus-warm-curve-minus-1` | 暖色 · 提亮中灰 · 中段收窄 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 164 | [大众拍立得 · Polaroid Px-680｜暖色 · 提亮中灰 · 中段拉开](look-profiles/101-200.md#preset-nt-instant-consumer-polaroid-px-680)<br>`nt-instant-consumer-polaroid-px-680` | 暖色 · 提亮中灰 · 中段拉开 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 165 | [大众拍立得 · Polaroid Px-680 ++｜暖色 · 提亮中灰 · 中段跨度接近原值](look-profiles/101-200.md#preset-nt-instant-consumer-polaroid-px-680-curve-plus-2)<br>`nt-instant-consumer-polaroid-px-680-curve-plus-2` | 暖色 · 提亮中灰 · 中段跨度接近原值 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 166 | [大众拍立得 · Polaroid Px-680 +｜暖色 · 提亮中灰 · 中段跨度接近原值](look-profiles/101-200.md#preset-nt-instant-consumer-polaroid-px-680-curve-plus-1)<br>`nt-instant-consumer-polaroid-px-680-curve-plus-1` | 暖色 · 提亮中灰 · 中段跨度接近原值 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 167 | [大众拍立得 · Polaroid Px-680 --｜暖色 · 提亮中灰 · 中段跨度接近原值](look-profiles/101-200.md#preset-nt-instant-consumer-polaroid-px-680-curve-minus-2)<br>`nt-instant-consumer-polaroid-px-680-curve-minus-2` | 暖色 · 提亮中灰 · 中段跨度接近原值 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 168 | [大众拍立得 · Polaroid Px-680 -｜暖色 · 提亮中灰 · 中段拉开](look-profiles/101-200.md#preset-nt-instant-consumer-polaroid-px-680-curve-minus-1)<br>`nt-instant-consumer-polaroid-px-680-curve-minus-1` | 暖色 · 提亮中灰 · 中段拉开 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 169 | [大众拍立得 · Polaroid Px-680 Cold｜暖色 · 提亮中灰 · 中段拉开](look-profiles/101-200.md#preset-nt-instant-consumer-polaroid-px-680-cold)<br>`nt-instant-consumer-polaroid-px-680-cold` | 暖色 · 提亮中灰 · 中段拉开 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 170 | [大众拍立得 · Polaroid Px-680 Cold ++｜暖色 · 提亮中灰 · 中段跨度接近原值](look-profiles/101-200.md#preset-nt-instant-consumer-polaroid-px-680-cold-curve-plus-2)<br>`nt-instant-consumer-polaroid-px-680-cold-curve-plus-2` | 暖色 · 提亮中灰 · 中段跨度接近原值 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 171 | [大众拍立得 · Polaroid Px-680 Cold ++ Alt｜暖色 · 压暗中灰 · 中段收窄](look-profiles/101-200.md#preset-nt-instant-consumer-polaroid-px-680-cold-plus-plus-alt)<br>`nt-instant-consumer-polaroid-px-680-cold-plus-plus-alt` | 暖色 · 压暗中灰 · 中段收窄 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 172 | [大众拍立得 · Polaroid Px-680 Cold +｜暖色 · 提亮中灰 · 中段拉开](look-profiles/101-200.md#preset-nt-instant-consumer-polaroid-px-680-cold-curve-plus-1)<br>`nt-instant-consumer-polaroid-px-680-cold-curve-plus-1` | 暖色 · 提亮中灰 · 中段拉开 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 173 | [大众拍立得 · Polaroid Px-680 Cold --｜暖色 · 提亮中灰 · 中段跨度接近原值](look-profiles/101-200.md#preset-nt-instant-consumer-polaroid-px-680-cold-curve-minus-2)<br>`nt-instant-consumer-polaroid-px-680-cold-curve-minus-2` | 暖色 · 提亮中灰 · 中段跨度接近原值 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 174 | [大众拍立得 · Polaroid Px-680 Cold -｜暖色 · 提亮中灰 · 中段拉开](look-profiles/101-200.md#preset-nt-instant-consumer-polaroid-px-680-cold-curve-minus-1)<br>`nt-instant-consumer-polaroid-px-680-cold-curve-minus-1` | 暖色 · 提亮中灰 · 中段拉开 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 175 | [大众拍立得 · Polaroid Px-680 Warm｜暖色 · 提亮中灰 · 中段跨度接近原值](look-profiles/101-200.md#preset-nt-instant-consumer-polaroid-px-680-warm)<br>`nt-instant-consumer-polaroid-px-680-warm` | 暖色 · 提亮中灰 · 中段跨度接近原值 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 176 | [大众拍立得 · Polaroid Px-680 Warm ++｜暖色 · 提亮中灰 · 中段收窄](look-profiles/101-200.md#preset-nt-instant-consumer-polaroid-px-680-warm-curve-plus-2)<br>`nt-instant-consumer-polaroid-px-680-warm-curve-plus-2` | 暖色 · 提亮中灰 · 中段收窄 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 177 | [大众拍立得 · Polaroid Px-680 Warm +｜暖色 · 提亮中灰 · 中段收窄](look-profiles/101-200.md#preset-nt-instant-consumer-polaroid-px-680-warm-curve-plus-1)<br>`nt-instant-consumer-polaroid-px-680-warm-curve-plus-1` | 暖色 · 提亮中灰 · 中段收窄 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 178 | [大众拍立得 · Polaroid Px-680 Warm --｜暖色 · 提亮中灰 · 中段拉开](look-profiles/101-200.md#preset-nt-instant-consumer-polaroid-px-680-warm-curve-minus-2)<br>`nt-instant-consumer-polaroid-px-680-warm-curve-minus-2` | 暖色 · 提亮中灰 · 中段拉开 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 179 | [大众拍立得 · Polaroid Px-680 Warm -｜暖色 · 提亮中灰 · 中段跨度接近原值](look-profiles/101-200.md#preset-nt-instant-consumer-polaroid-px-680-warm-curve-minus-1)<br>`nt-instant-consumer-polaroid-px-680-warm-curve-minus-1` | 暖色 · 提亮中灰 · 中段跨度接近原值 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 180 | [大众拍立得 · Polaroid Px-70｜暖色 · 提亮中灰 · 中段拉开](look-profiles/101-200.md#preset-nt-instant-consumer-polaroid-px-70)<br>`nt-instant-consumer-polaroid-px-70` | 暖色 · 提亮中灰 · 中段拉开 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 181 | [大众拍立得 · Polaroid Px-70 +++｜暖色 · 提亮中灰 · 中段收窄](look-profiles/101-200.md#preset-nt-instant-consumer-polaroid-px-70-curve-plus-3)<br>`nt-instant-consumer-polaroid-px-70-curve-plus-3` | 暖色 · 提亮中灰 · 中段收窄 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 182 | [大众拍立得 · Polaroid Px-70 ++｜暖色 · 提亮中灰 · 中段跨度接近原值](look-profiles/101-200.md#preset-nt-instant-consumer-polaroid-px-70-curve-plus-2)<br>`nt-instant-consumer-polaroid-px-70-curve-plus-2` | 暖色 · 提亮中灰 · 中段跨度接近原值 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 183 | [大众拍立得 · Polaroid Px-70 +｜暖色 · 提亮中灰 · 中段拉开](look-profiles/101-200.md#preset-nt-instant-consumer-polaroid-px-70-curve-plus-1)<br>`nt-instant-consumer-polaroid-px-70-curve-plus-1` | 暖色 · 提亮中灰 · 中段拉开 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 184 | [大众拍立得 · Polaroid Px-70 --｜暖色 · 提亮中灰 · 中段拉开](look-profiles/101-200.md#preset-nt-instant-consumer-polaroid-px-70-curve-minus-2)<br>`nt-instant-consumer-polaroid-px-70-curve-minus-2` | 暖色 · 提亮中灰 · 中段拉开 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 185 | [大众拍立得 · Polaroid Px-70 -｜暖色 · 提亮中灰 · 中段拉开](look-profiles/101-200.md#preset-nt-instant-consumer-polaroid-px-70-curve-minus-1)<br>`nt-instant-consumer-polaroid-px-70-curve-minus-1` | 暖色 · 提亮中灰 · 中段拉开 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 186 | [大众拍立得 · Polaroid Px-70 Cold｜暖色 · 提亮中灰 · 中段拉开](look-profiles/101-200.md#preset-nt-instant-consumer-polaroid-px-70-cold)<br>`nt-instant-consumer-polaroid-px-70-cold` | 暖色 · 提亮中灰 · 中段拉开 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 187 | [大众拍立得 · Polaroid Px-70 Cold ++｜冷色 · 提亮中灰 · 中段跨度接近原值](look-profiles/101-200.md#preset-nt-instant-consumer-polaroid-px-70-cold-curve-plus-2)<br>`nt-instant-consumer-polaroid-px-70-cold-curve-plus-2` | 冷色 · 提亮中灰 · 中段跨度接近原值 | 冷色城市、夜景与科技试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 188 | [大众拍立得 · Polaroid Px-70 Cold +｜暖色 · 提亮中灰 · 中段拉开](look-profiles/101-200.md#preset-nt-instant-consumer-polaroid-px-70-cold-curve-plus-1)<br>`nt-instant-consumer-polaroid-px-70-cold-curve-plus-1` | 暖色 · 提亮中灰 · 中段拉开 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 189 | [大众拍立得 · Polaroid Px-70 Cold --｜暖色 · 提亮中灰 · 中段拉开](look-profiles/101-200.md#preset-nt-instant-consumer-polaroid-px-70-cold-curve-minus-2)<br>`nt-instant-consumer-polaroid-px-70-cold-curve-minus-2` | 暖色 · 提亮中灰 · 中段拉开 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 190 | [大众拍立得 · Polaroid Px-70 Cold -｜暖色 · 提亮中灰 · 中段拉开](look-profiles/101-200.md#preset-nt-instant-consumer-polaroid-px-70-cold-curve-minus-1)<br>`nt-instant-consumer-polaroid-px-70-cold-curve-minus-1` | 暖色 · 提亮中灰 · 中段拉开 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 191 | [大众拍立得 · Polaroid Px-70 Warm｜暖色 · 提亮中灰 · 中段拉开](look-profiles/101-200.md#preset-nt-instant-consumer-polaroid-px-70-warm)<br>`nt-instant-consumer-polaroid-px-70-warm` | 暖色 · 提亮中灰 · 中段拉开 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 192 | [大众拍立得 · Polaroid Px-70 Warm ++｜暖色 · 提亮中灰 · 中段跨度接近原值](look-profiles/101-200.md#preset-nt-instant-consumer-polaroid-px-70-warm-curve-plus-2)<br>`nt-instant-consumer-polaroid-px-70-warm-curve-plus-2` | 暖色 · 提亮中灰 · 中段跨度接近原值 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 193 | [大众拍立得 · Polaroid Px-70 Warm +｜暖色 · 提亮中灰 · 中段拉开](look-profiles/101-200.md#preset-nt-instant-consumer-polaroid-px-70-warm-curve-plus-1)<br>`nt-instant-consumer-polaroid-px-70-warm-curve-plus-1` | 暖色 · 提亮中灰 · 中段拉开 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 194 | [大众拍立得 · Polaroid Px-70 Warm --｜暖色 · 提亮中灰 · 中段拉开](look-profiles/101-200.md#preset-nt-instant-consumer-polaroid-px-70-warm-curve-minus-2)<br>`nt-instant-consumer-polaroid-px-70-warm-curve-minus-2` | 暖色 · 提亮中灰 · 中段拉开 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 195 | [大众拍立得 · Polaroid Px-70 Warm -｜暖色 · 提亮中灰 · 中段拉开](look-profiles/101-200.md#preset-nt-instant-consumer-polaroid-px-70-warm-curve-minus-1)<br>`nt-instant-consumer-polaroid-px-70-warm-curve-minus-1` | 暖色 · 提亮中灰 · 中段拉开 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 196 | [大众拍立得 · Polaroid Time Zero (Expired)｜暖色 · 提亮中灰 · 中段收窄](look-profiles/101-200.md#preset-nt-instant-consumer-polaroid-time-zero-expired)<br>`nt-instant-consumer-polaroid-time-zero-expired` | 暖色 · 提亮中灰 · 中段收窄 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 197 | [大众拍立得 · Polaroid Time Zero (Expired) ++｜暖色 · 提亮中灰 · 中段收窄](look-profiles/101-200.md#preset-nt-instant-consumer-polaroid-time-zero-expired-curve-plus-2)<br>`nt-instant-consumer-polaroid-time-zero-expired-curve-plus-2` | 暖色 · 提亮中灰 · 中段收窄 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 198 | [大众拍立得 · Polaroid Time Zero (Expired) +｜暖色 · 提亮中灰 · 中段收窄](look-profiles/101-200.md#preset-nt-instant-consumer-polaroid-time-zero-expired-curve-plus-1)<br>`nt-instant-consumer-polaroid-time-zero-expired-curve-plus-1` | 暖色 · 提亮中灰 · 中段收窄 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 199 | [大众拍立得 · Polaroid Time Zero (Expired) ---｜暖色 · 提亮中灰 · 中段拉开](look-profiles/101-200.md#preset-nt-instant-consumer-polaroid-time-zero-expired-curve-minus-3)<br>`nt-instant-consumer-polaroid-time-zero-expired-curve-minus-3` | 暖色 · 提亮中灰 · 中段拉开 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 200 | [大众拍立得 · Polaroid Time Zero (Expired) --｜暖色 · 提亮中灰 · 中段拉开](look-profiles/101-200.md#preset-nt-instant-consumer-polaroid-time-zero-expired-curve-minus-2)<br>`nt-instant-consumer-polaroid-time-zero-expired-curve-minus-2` | 暖色 · 提亮中灰 · 中段拉开 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 201 | [大众拍立得 · Polaroid Time Zero (Expired) -｜暖色 · 提亮中灰 · 中段收窄](look-profiles/201-300.md#preset-nt-instant-consumer-polaroid-time-zero-expired-curve-minus-1)<br>`nt-instant-consumer-polaroid-time-zero-expired-curve-minus-1` | 暖色 · 提亮中灰 · 中段收窄 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 202 | [大众拍立得 · Polaroid Time Zero (Expired) Cold｜暖色 · 提亮中灰 · 中段收窄](look-profiles/201-300.md#preset-nt-instant-consumer-polaroid-time-zero-expired-cold)<br>`nt-instant-consumer-polaroid-time-zero-expired-cold` | 暖色 · 提亮中灰 · 中段收窄 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 203 | [大众拍立得 · Polaroid Time Zero (Expired) Cold ---｜暖色 · 提亮中灰 · 中段拉开](look-profiles/201-300.md#preset-nt-instant-consumer-polaroid-time-zero-expired-cold-curve-minus-3)<br>`nt-instant-consumer-polaroid-time-zero-expired-cold-curve-minus-3` | 暖色 · 提亮中灰 · 中段拉开 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 204 | [大众拍立得 · Polaroid Time Zero (Expired) Cold --｜暖色 · 提亮中灰 · 中段拉开](look-profiles/201-300.md#preset-nt-instant-consumer-polaroid-time-zero-expired-cold-curve-minus-2)<br>`nt-instant-consumer-polaroid-time-zero-expired-cold-curve-minus-2` | 暖色 · 提亮中灰 · 中段拉开 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 205 | [大众拍立得 · Polaroid Time Zero (Expired) Cold -｜暖色 · 提亮中灰 · 中段收窄](look-profiles/201-300.md#preset-nt-instant-consumer-polaroid-time-zero-expired-cold-curve-minus-1)<br>`nt-instant-consumer-polaroid-time-zero-expired-cold-curve-minus-1` | 暖色 · 提亮中灰 · 中段收窄 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 206 | [专业拍立得 · Fuji Fp-100C｜暖色 · 提亮中灰 · 中段拉开](look-profiles/201-300.md#preset-nt-instant-pro-fuji-fp-100c)<br>`nt-instant-pro-fuji-fp-100c` | 暖色 · 提亮中灰 · 中段拉开 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 207 | [专业拍立得 · Fuji Fp-100C +++｜冷色 · 提亮中灰 · 中段收窄](look-profiles/201-300.md#preset-nt-instant-pro-fuji-fp-100c-curve-plus-3)<br>`nt-instant-pro-fuji-fp-100c-curve-plus-3` | 冷色 · 提亮中灰 · 中段收窄 | 冷色城市、夜景与科技试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 208 | [专业拍立得 · Fuji Fp-100C ++｜暖色 · 提亮中灰 · 中段拉开](look-profiles/201-300.md#preset-nt-instant-pro-fuji-fp-100c-curve-plus-2)<br>`nt-instant-pro-fuji-fp-100c-curve-plus-2` | 暖色 · 提亮中灰 · 中段拉开 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 209 | [专业拍立得 · Fuji Fp-100C ++ Alt｜暖色 · 提亮中灰 · 中段跨度接近原值](look-profiles/201-300.md#preset-nt-instant-pro-fuji-fp-100c-plus-plus-alt)<br>`nt-instant-pro-fuji-fp-100c-plus-plus-alt` | 暖色 · 提亮中灰 · 中段跨度接近原值 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 210 | [专业拍立得 · Fuji Fp-100C +｜暖色 · 提亮中灰 · 中段拉开](look-profiles/201-300.md#preset-nt-instant-pro-fuji-fp-100c-curve-plus-1)<br>`nt-instant-pro-fuji-fp-100c-curve-plus-1` | 暖色 · 提亮中灰 · 中段拉开 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 211 | [专业拍立得 · Fuji Fp-100C --｜暖色 · 提亮中灰 · 中段拉开](look-profiles/201-300.md#preset-nt-instant-pro-fuji-fp-100c-curve-minus-2)<br>`nt-instant-pro-fuji-fp-100c-curve-minus-2` | 暖色 · 提亮中灰 · 中段拉开 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 212 | [专业拍立得 · Fuji Fp-100C -｜暖色 · 提亮中灰 · 中段拉开](look-profiles/201-300.md#preset-nt-instant-pro-fuji-fp-100c-curve-minus-1)<br>`nt-instant-pro-fuji-fp-100c-curve-minus-1` | 暖色 · 提亮中灰 · 中段拉开 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 213 | [专业拍立得 · Fuji Fp-100C Cool｜冷色 · 提亮中灰 · 中段拉开](look-profiles/201-300.md#preset-nt-instant-pro-fuji-fp-100c-cool)<br>`nt-instant-pro-fuji-fp-100c-cool` | 冷色 · 提亮中灰 · 中段拉开 | 冷色城市、夜景与科技试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 214 | [专业拍立得 · Fuji Fp-100C Cool ++｜冷色 · 提亮中灰 · 中段拉开](look-profiles/201-300.md#preset-nt-instant-pro-fuji-fp-100c-cool-curve-plus-2)<br>`nt-instant-pro-fuji-fp-100c-cool-curve-plus-2` | 冷色 · 提亮中灰 · 中段拉开 | 冷色城市、夜景与科技试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 215 | [专业拍立得 · Fuji Fp-100C Cool +｜冷色 · 提亮中灰 · 中段拉开](look-profiles/201-300.md#preset-nt-instant-pro-fuji-fp-100c-cool-curve-plus-1)<br>`nt-instant-pro-fuji-fp-100c-cool-curve-plus-1` | 冷色 · 提亮中灰 · 中段拉开 | 冷色城市、夜景与科技试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 216 | [专业拍立得 · Fuji Fp-100C Cool --｜暖色 · 提亮中灰 · 中段拉开](look-profiles/201-300.md#preset-nt-instant-pro-fuji-fp-100c-cool-curve-minus-2)<br>`nt-instant-pro-fuji-fp-100c-cool-curve-minus-2` | 暖色 · 提亮中灰 · 中段拉开 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 217 | [专业拍立得 · Fuji Fp-100C Cool -｜中性 · 提亮中灰 · 中段拉开](look-profiles/201-300.md#preset-nt-instant-pro-fuji-fp-100c-cool-curve-minus-1)<br>`nt-instant-pro-fuji-fp-100c-cool-curve-minus-1` | 中性 · 提亮中灰 · 中段拉开 | 产品、生活与风景对照试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 218 | [专业拍立得 · Fuji Fp-100C Negative｜暖色 · 提亮中灰 · 中段拉开](look-profiles/201-300.md#preset-nt-instant-pro-fuji-fp-100c-negative)<br>`nt-instant-pro-fuji-fp-100c-negative` | 暖色 · 提亮中灰 · 中段拉开 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 219 | [专业拍立得 · Fuji Fp-100C Negative +++｜暖色 · 提亮中灰 · 中段拉开](look-profiles/201-300.md#preset-nt-instant-pro-fuji-fp-100c-negative-curve-plus-3)<br>`nt-instant-pro-fuji-fp-100c-negative-curve-plus-3` | 暖色 · 提亮中灰 · 中段拉开 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 220 | [专业拍立得 · Fuji Fp-100C Negative ++｜暖色 · 提亮中灰 · 中段拉开](look-profiles/201-300.md#preset-nt-instant-pro-fuji-fp-100c-negative-curve-plus-2)<br>`nt-instant-pro-fuji-fp-100c-negative-curve-plus-2` | 暖色 · 提亮中灰 · 中段拉开 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 221 | [专业拍立得 · Fuji Fp-100C Negative ++ Alt｜暖色 · 提亮中灰 · 中段拉开](look-profiles/201-300.md#preset-nt-instant-pro-fuji-fp-100c-negative-plus-plus-alt)<br>`nt-instant-pro-fuji-fp-100c-negative-plus-plus-alt` | 暖色 · 提亮中灰 · 中段拉开 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 222 | [专业拍立得 · Fuji Fp-100C Negative +｜暖色 · 提亮中灰 · 中段拉开](look-profiles/201-300.md#preset-nt-instant-pro-fuji-fp-100c-negative-curve-plus-1)<br>`nt-instant-pro-fuji-fp-100c-negative-curve-plus-1` | 暖色 · 提亮中灰 · 中段拉开 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 223 | [专业拍立得 · Fuji Fp-100C Negative --｜暖色 · 提亮中灰 · 中段拉开](look-profiles/201-300.md#preset-nt-instant-pro-fuji-fp-100c-negative-curve-minus-2)<br>`nt-instant-pro-fuji-fp-100c-negative-curve-minus-2` | 暖色 · 提亮中灰 · 中段拉开 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 224 | [专业拍立得 · Fuji Fp-100C Negative -｜暖色 · 提亮中灰 · 中段拉开](look-profiles/201-300.md#preset-nt-instant-pro-fuji-fp-100c-negative-curve-minus-1)<br>`nt-instant-pro-fuji-fp-100c-negative-curve-minus-1` | 暖色 · 提亮中灰 · 中段拉开 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 225 | [专业拍立得 · Fuji Fp-3000B｜黑白 · 提亮中灰 · 中段拉开](look-profiles/201-300.md#preset-nt-instant-pro-fuji-fp-3000b)<br>`nt-instant-pro-fuji-fp-3000b` | 黑白 · 提亮中灰 · 中段拉开 | 黑白纪实、建筑与轮廓试片 | 1–1 | CC-BY-SA-4.0 |
| 226 | [专业拍立得 · Fuji Fp-3000B +++｜黑白 · 提亮中灰 · 中段跨度接近原值](look-profiles/201-300.md#preset-nt-instant-pro-fuji-fp-3000b-curve-plus-3)<br>`nt-instant-pro-fuji-fp-3000b-curve-plus-3` | 黑白 · 提亮中灰 · 中段跨度接近原值 | 黑白纪实、建筑与轮廓试片 | 1–1 | CC-BY-SA-4.0 |
| 227 | [专业拍立得 · Fuji Fp-3000B ++｜黑白 · 提亮中灰 · 中段拉开](look-profiles/201-300.md#preset-nt-instant-pro-fuji-fp-3000b-curve-plus-2)<br>`nt-instant-pro-fuji-fp-3000b-curve-plus-2` | 黑白 · 提亮中灰 · 中段拉开 | 黑白纪实、建筑与轮廓试片 | 1–1 | CC-BY-SA-4.0 |
| 228 | [专业拍立得 · Fuji Fp-3000B +｜黑白 · 提亮中灰 · 中段拉开](look-profiles/201-300.md#preset-nt-instant-pro-fuji-fp-3000b-curve-plus-1)<br>`nt-instant-pro-fuji-fp-3000b-curve-plus-1` | 黑白 · 提亮中灰 · 中段拉开 | 黑白纪实、建筑与轮廓试片 | 1–1 | CC-BY-SA-4.0 |
| 229 | [专业拍立得 · Fuji Fp-3000B --｜黑白 · 提亮中灰 · 中段跨度接近原值](look-profiles/201-300.md#preset-nt-instant-pro-fuji-fp-3000b-curve-minus-2)<br>`nt-instant-pro-fuji-fp-3000b-curve-minus-2` | 黑白 · 提亮中灰 · 中段跨度接近原值 | 黑白纪实、建筑与轮廓试片 | 1–1 | CC-BY-SA-4.0 |
| 230 | [专业拍立得 · Fuji Fp-3000B -｜黑白 · 提亮中灰 · 中段拉开](look-profiles/201-300.md#preset-nt-instant-pro-fuji-fp-3000b-curve-minus-1)<br>`nt-instant-pro-fuji-fp-3000b-curve-minus-1` | 黑白 · 提亮中灰 · 中段拉开 | 黑白纪实、建筑与轮廓试片 | 1–1 | CC-BY-SA-4.0 |
| 231 | [专业拍立得 · Fuji Fp-3000B Hc｜黑白 · 提亮中灰 · 中段拉开](look-profiles/201-300.md#preset-nt-instant-pro-fuji-fp-3000b-hc)<br>`nt-instant-pro-fuji-fp-3000b-hc` | 黑白 · 提亮中灰 · 中段拉开 | 黑白纪实、建筑与轮廓试片 | 1–1 | CC-BY-SA-4.0 |
| 232 | [专业拍立得 · Fuji Fp-3000B Negative｜黑白 · 提亮中灰 · 中段拉开](look-profiles/201-300.md#preset-nt-instant-pro-fuji-fp-3000b-negative)<br>`nt-instant-pro-fuji-fp-3000b-negative` | 黑白 · 提亮中灰 · 中段拉开 | 黑白纪实、建筑与轮廓试片 | 1–1 | CC-BY-SA-4.0 |
| 233 | [专业拍立得 · Fuji Fp-3000B Negative +++｜黑白 · 提亮中灰 · 中段收窄](look-profiles/201-300.md#preset-nt-instant-pro-fuji-fp-3000b-negative-curve-plus-3)<br>`nt-instant-pro-fuji-fp-3000b-negative-curve-plus-3` | 黑白 · 提亮中灰 · 中段收窄 | 黑白纪实、建筑与轮廓试片 | 1–1 | CC-BY-SA-4.0 |
| 234 | [专业拍立得 · Fuji Fp-3000B Negative ++｜黑白 · 提亮中灰 · 中段拉开](look-profiles/201-300.md#preset-nt-instant-pro-fuji-fp-3000b-negative-curve-plus-2)<br>`nt-instant-pro-fuji-fp-3000b-negative-curve-plus-2` | 黑白 · 提亮中灰 · 中段拉开 | 黑白纪实、建筑与轮廓试片 | 1–1 | CC-BY-SA-4.0 |
| 235 | [专业拍立得 · Fuji Fp-3000B Negative +｜黑白 · 提亮中灰 · 中段拉开](look-profiles/201-300.md#preset-nt-instant-pro-fuji-fp-3000b-negative-curve-plus-1)<br>`nt-instant-pro-fuji-fp-3000b-negative-curve-plus-1` | 黑白 · 提亮中灰 · 中段拉开 | 黑白纪实、建筑与轮廓试片 | 1–1 | CC-BY-SA-4.0 |
| 236 | [专业拍立得 · Fuji Fp-3000B Negative --｜黑白 · 提亮中灰 · 中段拉开](look-profiles/201-300.md#preset-nt-instant-pro-fuji-fp-3000b-negative-curve-minus-2)<br>`nt-instant-pro-fuji-fp-3000b-negative-curve-minus-2` | 黑白 · 提亮中灰 · 中段拉开 | 黑白纪实、建筑与轮廓试片 | 1–1 | CC-BY-SA-4.0 |
| 237 | [专业拍立得 · Fuji Fp-3000B Negative -｜黑白 · 提亮中灰 · 中段拉开](look-profiles/201-300.md#preset-nt-instant-pro-fuji-fp-3000b-negative-curve-minus-1)<br>`nt-instant-pro-fuji-fp-3000b-negative-curve-minus-1` | 黑白 · 提亮中灰 · 中段拉开 | 黑白纪实、建筑与轮廓试片 | 1–1 | CC-BY-SA-4.0 |
| 238 | [专业拍立得 · Fuji Fp-3000B Negative Early｜黑白 · 提亮中灰 · 中段拉开](look-profiles/201-300.md#preset-nt-instant-pro-fuji-fp-3000b-negative-early)<br>`nt-instant-pro-fuji-fp-3000b-negative-early` | 黑白 · 提亮中灰 · 中段拉开 | 黑白纪实、建筑与轮廓试片 | 1–1 | CC-BY-SA-4.0 |
| 239 | [专业拍立得 · Polaroid 665｜黑白 · 中灰近原值 · 中段拉开](look-profiles/201-300.md#preset-nt-instant-pro-polaroid-665)<br>`nt-instant-pro-polaroid-665` | 黑白 · 中灰近原值 · 中段拉开 | 黑白纪实、建筑与轮廓试片 | 1–1 | CC-BY-SA-4.0 |
| 240 | [专业拍立得 · Polaroid 665 ++｜黑白 · 提亮中灰 · 中段拉开](look-profiles/201-300.md#preset-nt-instant-pro-polaroid-665-curve-plus-2)<br>`nt-instant-pro-polaroid-665-curve-plus-2` | 黑白 · 提亮中灰 · 中段拉开 | 黑白纪实、建筑与轮廓试片 | 1–1 | CC-BY-SA-4.0 |
| 241 | [专业拍立得 · Polaroid 665 +｜黑白 · 提亮中灰 · 中段拉开](look-profiles/201-300.md#preset-nt-instant-pro-polaroid-665-curve-plus-1)<br>`nt-instant-pro-polaroid-665-curve-plus-1` | 黑白 · 提亮中灰 · 中段拉开 | 黑白纪实、建筑与轮廓试片 | 1–1 | CC-BY-SA-4.0 |
| 242 | [专业拍立得 · Polaroid 665 --｜黑白 · 提亮中灰 · 中段跨度接近原值](look-profiles/201-300.md#preset-nt-instant-pro-polaroid-665-curve-minus-2)<br>`nt-instant-pro-polaroid-665-curve-minus-2` | 黑白 · 提亮中灰 · 中段跨度接近原值 | 黑白纪实、建筑与轮廓试片 | 1–1 | CC-BY-SA-4.0 |
| 243 | [专业拍立得 · Polaroid 665 -｜黑白 · 提亮中灰 · 中段跨度接近原值](look-profiles/201-300.md#preset-nt-instant-pro-polaroid-665-curve-minus-1)<br>`nt-instant-pro-polaroid-665-curve-minus-1` | 黑白 · 提亮中灰 · 中段跨度接近原值 | 黑白纪实、建筑与轮廓试片 | 1–1 | CC-BY-SA-4.0 |
| 244 | [专业拍立得 · Polaroid 665 Negative｜黑白 · 提亮中灰 · 中段拉开](look-profiles/201-300.md#preset-nt-instant-pro-polaroid-665-negative)<br>`nt-instant-pro-polaroid-665-negative` | 黑白 · 提亮中灰 · 中段拉开 | 黑白纪实、建筑与轮廓试片 | 1–1 | CC-BY-SA-4.0 |
| 245 | [专业拍立得 · Polaroid 665 Negative +｜黑白 · 提亮中灰 · 中段收窄](look-profiles/201-300.md#preset-nt-instant-pro-polaroid-665-negative-curve-plus-1)<br>`nt-instant-pro-polaroid-665-negative-curve-plus-1` | 黑白 · 提亮中灰 · 中段收窄 | 黑白纪实、建筑与轮廓试片 | 1–1 | CC-BY-SA-4.0 |
| 246 | [专业拍立得 · Polaroid 665 Negative -｜黑白 · 提亮中灰 · 中段拉开](look-profiles/201-300.md#preset-nt-instant-pro-polaroid-665-negative-curve-minus-1)<br>`nt-instant-pro-polaroid-665-negative-curve-minus-1` | 黑白 · 提亮中灰 · 中段拉开 | 黑白纪实、建筑与轮廓试片 | 1–1 | CC-BY-SA-4.0 |
| 247 | [专业拍立得 · Polaroid 665 Negative Hc｜黑白 · 提亮中灰 · 中段拉开](look-profiles/201-300.md#preset-nt-instant-pro-polaroid-665-negative-hc)<br>`nt-instant-pro-polaroid-665-negative-hc` | 黑白 · 提亮中灰 · 中段拉开 | 黑白纪实、建筑与轮廓试片 | 1–1 | CC-BY-SA-4.0 |
| 248 | [专业拍立得 · Polaroid 669 +++｜冷色 · 提亮中灰 · 中段跨度接近原值](look-profiles/201-300.md#preset-nt-instant-pro-polaroid-669-curve-plus-3)<br>`nt-instant-pro-polaroid-669-curve-plus-3` | 冷色 · 提亮中灰 · 中段跨度接近原值 | 冷色城市、夜景与科技试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 249 | [专业拍立得 · Polaroid 669 ++｜冷色 · 提亮中灰 · 中段跨度接近原值](look-profiles/201-300.md#preset-nt-instant-pro-polaroid-669-curve-plus-2)<br>`nt-instant-pro-polaroid-669-curve-plus-2` | 冷色 · 提亮中灰 · 中段跨度接近原值 | 冷色城市、夜景与科技试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 250 | [专业拍立得 · Polaroid 669 +｜冷色 · 提亮中灰 · 中段拉开](look-profiles/201-300.md#preset-nt-instant-pro-polaroid-669-curve-plus-1)<br>`nt-instant-pro-polaroid-669-curve-plus-1` | 冷色 · 提亮中灰 · 中段拉开 | 冷色城市、夜景与科技试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 251 | [专业拍立得 · Polaroid 669 --｜中性 · 提亮中灰 · 中段拉开](look-profiles/201-300.md#preset-nt-instant-pro-polaroid-669-curve-minus-2)<br>`nt-instant-pro-polaroid-669-curve-minus-2` | 中性 · 提亮中灰 · 中段拉开 | 产品、生活与风景对照试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 252 | [专业拍立得 · Polaroid 669 -｜冷色 · 提亮中灰 · 中段拉开](look-profiles/201-300.md#preset-nt-instant-pro-polaroid-669-curve-minus-1)<br>`nt-instant-pro-polaroid-669-curve-minus-1` | 冷色 · 提亮中灰 · 中段拉开 | 冷色城市、夜景与科技试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 253 | [专业拍立得 · Polaroid 669 Cold｜冷色 · 提亮中灰 · 中段拉开](look-profiles/201-300.md#preset-nt-instant-pro-polaroid-669-cold)<br>`nt-instant-pro-polaroid-669-cold` | 冷色 · 提亮中灰 · 中段拉开 | 冷色城市、夜景与科技试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 254 | [专业拍立得 · Polaroid 669 Cold +｜冷色 · 提亮中灰 · 中段拉开](look-profiles/201-300.md#preset-nt-instant-pro-polaroid-669-cold-curve-plus-1)<br>`nt-instant-pro-polaroid-669-cold-curve-plus-1` | 冷色 · 提亮中灰 · 中段拉开 | 冷色城市、夜景与科技试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 255 | [专业拍立得 · Polaroid 669 Cold --｜冷色 · 提亮中灰 · 中段拉开](look-profiles/201-300.md#preset-nt-instant-pro-polaroid-669-cold-curve-minus-2)<br>`nt-instant-pro-polaroid-669-cold-curve-minus-2` | 冷色 · 提亮中灰 · 中段拉开 | 冷色城市、夜景与科技试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 256 | [专业拍立得 · Polaroid 669 Cold -｜冷色 · 提亮中灰 · 中段拉开](look-profiles/201-300.md#preset-nt-instant-pro-polaroid-669-cold-curve-minus-1)<br>`nt-instant-pro-polaroid-669-cold-curve-minus-1` | 冷色 · 提亮中灰 · 中段拉开 | 冷色城市、夜景与科技试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 257 | [专业拍立得 · Polaroid 690 ++｜暖色 · 提亮中灰 · 中段收窄](look-profiles/201-300.md#preset-nt-instant-pro-polaroid-690-curve-plus-2)<br>`nt-instant-pro-polaroid-690-curve-plus-2` | 暖色 · 提亮中灰 · 中段收窄 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 258 | [专业拍立得 · Polaroid 690 +｜中性 · 提亮中灰 · 中段拉开](look-profiles/201-300.md#preset-nt-instant-pro-polaroid-690-curve-plus-1)<br>`nt-instant-pro-polaroid-690-curve-plus-1` | 中性 · 提亮中灰 · 中段拉开 | 产品、生活与风景对照试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 259 | [专业拍立得 · Polaroid 690 --｜中性 · 提亮中灰 · 中段拉开](look-profiles/201-300.md#preset-nt-instant-pro-polaroid-690-curve-minus-2)<br>`nt-instant-pro-polaroid-690-curve-minus-2` | 中性 · 提亮中灰 · 中段拉开 | 产品、生活与风景对照试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 260 | [专业拍立得 · Polaroid 690 -｜中性 · 提亮中灰 · 中段拉开](look-profiles/201-300.md#preset-nt-instant-pro-polaroid-690-curve-minus-1)<br>`nt-instant-pro-polaroid-690-curve-minus-1` | 中性 · 提亮中灰 · 中段拉开 | 产品、生活与风景对照试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 261 | [专业拍立得 · Polaroid 690 Cold｜冷色 · 提亮中灰 · 中段拉开](look-profiles/201-300.md#preset-nt-instant-pro-polaroid-690-cold)<br>`nt-instant-pro-polaroid-690-cold` | 冷色 · 提亮中灰 · 中段拉开 | 冷色城市、夜景与科技试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 262 | [专业拍立得 · Polaroid 690 Cold ++｜冷色 · 提亮中灰 · 中段收窄](look-profiles/201-300.md#preset-nt-instant-pro-polaroid-690-cold-curve-plus-2)<br>`nt-instant-pro-polaroid-690-cold-curve-plus-2` | 冷色 · 提亮中灰 · 中段收窄 | 冷色城市、夜景与科技试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 263 | [专业拍立得 · Polaroid 690 Cold +｜冷色 · 提亮中灰 · 中段拉开](look-profiles/201-300.md#preset-nt-instant-pro-polaroid-690-cold-curve-plus-1)<br>`nt-instant-pro-polaroid-690-cold-curve-plus-1` | 冷色 · 提亮中灰 · 中段拉开 | 冷色城市、夜景与科技试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 264 | [专业拍立得 · Polaroid 690 Cold --｜冷色 · 提亮中灰 · 中段跨度接近原值](look-profiles/201-300.md#preset-nt-instant-pro-polaroid-690-cold-curve-minus-2)<br>`nt-instant-pro-polaroid-690-cold-curve-minus-2` | 冷色 · 提亮中灰 · 中段跨度接近原值 | 冷色城市、夜景与科技试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 265 | [专业拍立得 · Polaroid 690 Cold -｜冷色 · 提亮中灰 · 中段拉开](look-profiles/201-300.md#preset-nt-instant-pro-polaroid-690-cold-curve-minus-1)<br>`nt-instant-pro-polaroid-690-cold-curve-minus-1` | 冷色 · 提亮中灰 · 中段拉开 | 冷色城市、夜景与科技试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 266 | [专业拍立得 · Polaroid 690 Warm｜暖色 · 提亮中灰 · 中段拉开](look-profiles/201-300.md#preset-nt-instant-pro-polaroid-690-warm)<br>`nt-instant-pro-polaroid-690-warm` | 暖色 · 提亮中灰 · 中段拉开 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 267 | [专业拍立得 · Polaroid 690 Warm ++｜暖色 · 提亮中灰 · 中段跨度接近原值](look-profiles/201-300.md#preset-nt-instant-pro-polaroid-690-warm-curve-plus-2)<br>`nt-instant-pro-polaroid-690-warm-curve-plus-2` | 暖色 · 提亮中灰 · 中段跨度接近原值 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 268 | [专业拍立得 · Polaroid 690 Warm +｜暖色 · 提亮中灰 · 中段拉开](look-profiles/201-300.md#preset-nt-instant-pro-polaroid-690-warm-curve-plus-1)<br>`nt-instant-pro-polaroid-690-warm-curve-plus-1` | 暖色 · 提亮中灰 · 中段拉开 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 269 | [专业拍立得 · Polaroid 690 Warm --｜暖色 · 提亮中灰 · 中段跨度接近原值](look-profiles/201-300.md#preset-nt-instant-pro-polaroid-690-warm-curve-minus-2)<br>`nt-instant-pro-polaroid-690-warm-curve-minus-2` | 暖色 · 提亮中灰 · 中段跨度接近原值 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 270 | [专业拍立得 · Polaroid 690 Warm -｜暖色 · 提亮中灰 · 中段拉开](look-profiles/201-300.md#preset-nt-instant-pro-polaroid-690-warm-curve-minus-1)<br>`nt-instant-pro-polaroid-690-warm-curve-minus-1` | 暖色 · 提亮中灰 · 中段拉开 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 271 | [彩色负片 · Agfa Ultra Color 100｜中性 · 压暗中灰 · 中段拉开](look-profiles/201-300.md#preset-nt-negative-color-agfa-ultra-color-100)<br>`nt-negative-color-agfa-ultra-color-100` | 中性 · 压暗中灰 · 中段拉开 | 产品、生活与风景对照试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 272 | [彩色负片 · Agfa Vista 200｜中性 · 中灰近原值 · 中段拉开](look-profiles/201-300.md#preset-nt-negative-color-agfa-vista-200)<br>`nt-negative-color-agfa-vista-200` | 中性 · 中灰近原值 · 中段拉开 | 产品、生活与风景对照试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 273 | [彩色负片 · Fuji Superia 200｜中性 · 提亮中灰 · 中段跨度接近原值](look-profiles/201-300.md#preset-nt-negative-color-fuji-superia-200)<br>`nt-negative-color-fuji-superia-200` | 中性 · 提亮中灰 · 中段跨度接近原值 | 产品、生活与风景对照试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 274 | [彩色负片 · Fuji Superia Hg 1600｜中性 · 中灰近原值 · 中段收窄](look-profiles/201-300.md#preset-nt-negative-color-fuji-superia-hg-1600)<br>`nt-negative-color-fuji-superia-hg-1600` | 中性 · 中灰近原值 · 中段收窄 | 产品、生活与风景对照试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 275 | [彩色负片 · Fuji Superia Reala 100｜中性 · 提亮中灰 · 中段跨度接近原值](look-profiles/201-300.md#preset-nt-negative-color-fuji-superia-reala-100)<br>`nt-negative-color-fuji-superia-reala-100` | 中性 · 提亮中灰 · 中段跨度接近原值 | 产品、生活与风景对照试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 276 | [彩色负片 · Fuji Superia X-Tra 800｜中性 · 压暗中灰 · 中段收窄](look-profiles/201-300.md#preset-nt-negative-color-fuji-superia-x-tra-800)<br>`nt-negative-color-fuji-superia-x-tra-800` | 中性 · 压暗中灰 · 中段收窄 | 产品、生活与风景对照试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 277 | [彩色负片 · Kodak Elite 100 Xpro｜暖色 · 中灰近原值 · 中段拉开](look-profiles/201-300.md#preset-nt-negative-color-kodak-elite-100-xpro)<br>`nt-negative-color-kodak-elite-100-xpro` | 暖色 · 中灰近原值 · 中段拉开 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 278 | [彩色负片 · Kodak Elite Color 200｜中性 · 压暗中灰 · 中段拉开](look-profiles/201-300.md#preset-nt-negative-color-kodak-elite-color-200)<br>`nt-negative-color-kodak-elite-color-200` | 中性 · 压暗中灰 · 中段拉开 | 产品、生活与风景对照试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 279 | [彩色负片 · Kodak Elite Color 400｜中性 · 压暗中灰 · 中段拉开](look-profiles/201-300.md#preset-nt-negative-color-kodak-elite-color-400)<br>`nt-negative-color-kodak-elite-color-400` | 中性 · 压暗中灰 · 中段拉开 | 产品、生活与风景对照试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 280 | [彩色负片 · Kodak Portra 160 Nc｜中性 · 压暗中灰 · 中段跨度接近原值](look-profiles/201-300.md#preset-nt-negative-color-kodak-portra-160-nc)<br>`nt-negative-color-kodak-portra-160-nc` | 中性 · 压暗中灰 · 中段跨度接近原值 | 产品、生活与风景对照试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 281 | [彩色负片 · Kodak Portra 160 Vc｜中性 · 压暗中灰 · 中段跨度接近原值](look-profiles/201-300.md#preset-nt-negative-color-kodak-portra-160-vc)<br>`nt-negative-color-kodak-portra-160-vc` | 中性 · 压暗中灰 · 中段跨度接近原值 | 产品、生活与风景对照试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 282 | [彩色负片 · Lomography Redscale 100｜暖色 · 压暗中灰 · 中段拉开](look-profiles/201-300.md#preset-nt-negative-color-lomography-redscale-100)<br>`nt-negative-color-lomography-redscale-100` | 暖色 · 压暗中灰 · 中段拉开 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 283 | [彩色负片 · Fuji 160C｜暖色 · 提亮中灰 · 中段拉开](look-profiles/201-300.md#preset-nt-negative-new-fuji-160c)<br>`nt-negative-new-fuji-160c` | 暖色 · 提亮中灰 · 中段拉开 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 284 | [彩色负片 · Fuji 160C ++｜暖色 · 提亮中灰 · 中段跨度接近原值](look-profiles/201-300.md#preset-nt-negative-new-fuji-160c-curve-plus-2)<br>`nt-negative-new-fuji-160c-curve-plus-2` | 暖色 · 提亮中灰 · 中段跨度接近原值 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 285 | [彩色负片 · Fuji 160C +｜暖色 · 提亮中灰 · 中段跨度接近原值](look-profiles/201-300.md#preset-nt-negative-new-fuji-160c-curve-plus-1)<br>`nt-negative-new-fuji-160c-curve-plus-1` | 暖色 · 提亮中灰 · 中段跨度接近原值 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 286 | [彩色负片 · Fuji 160C -｜暖色 · 提亮中灰 · 中段跨度接近原值](look-profiles/201-300.md#preset-nt-negative-new-fuji-160c-curve-minus-1)<br>`nt-negative-new-fuji-160c-curve-minus-1` | 暖色 · 提亮中灰 · 中段跨度接近原值 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 287 | [彩色负片 · Fuji 400H｜暖色 · 提亮中灰 · 中段拉开](look-profiles/201-300.md#preset-nt-negative-new-fuji-400h)<br>`nt-negative-new-fuji-400h` | 暖色 · 提亮中灰 · 中段拉开 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 288 | [彩色负片 · Fuji 400H ++｜暖色 · 提亮中灰 · 中段跨度接近原值](look-profiles/201-300.md#preset-nt-negative-new-fuji-400h-curve-plus-2)<br>`nt-negative-new-fuji-400h-curve-plus-2` | 暖色 · 提亮中灰 · 中段跨度接近原值 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 289 | [彩色负片 · Fuji 400H +｜暖色 · 提亮中灰 · 中段跨度接近原值](look-profiles/201-300.md#preset-nt-negative-new-fuji-400h-curve-plus-1)<br>`nt-negative-new-fuji-400h-curve-plus-1` | 暖色 · 提亮中灰 · 中段跨度接近原值 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 290 | [彩色负片 · Fuji 400H -｜暖色 · 提亮中灰 · 中段跨度接近原值](look-profiles/201-300.md#preset-nt-negative-new-fuji-400h-curve-minus-1)<br>`nt-negative-new-fuji-400h-curve-minus-1` | 暖色 · 提亮中灰 · 中段跨度接近原值 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 291 | [彩色负片 · Fuji 800Z｜暖色 · 提亮中灰 · 中段拉开](look-profiles/201-300.md#preset-nt-negative-new-fuji-800z)<br>`nt-negative-new-fuji-800z` | 暖色 · 提亮中灰 · 中段拉开 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 292 | [彩色负片 · Fuji 800Z ++｜暖色 · 提亮中灰 · 中段跨度接近原值](look-profiles/201-300.md#preset-nt-negative-new-fuji-800z-curve-plus-2)<br>`nt-negative-new-fuji-800z-curve-plus-2` | 暖色 · 提亮中灰 · 中段跨度接近原值 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 293 | [彩色负片 · Fuji 800Z +｜暖色 · 提亮中灰 · 中段跨度接近原值](look-profiles/201-300.md#preset-nt-negative-new-fuji-800z-curve-plus-1)<br>`nt-negative-new-fuji-800z-curve-plus-1` | 暖色 · 提亮中灰 · 中段跨度接近原值 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 294 | [彩色负片 · Fuji 800Z -｜暖色 · 提亮中灰 · 中段跨度接近原值](look-profiles/201-300.md#preset-nt-negative-new-fuji-800z-curve-minus-1)<br>`nt-negative-new-fuji-800z-curve-minus-1` | 暖色 · 提亮中灰 · 中段跨度接近原值 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 295 | [黑白负片 · Fuji Ilford Hp5｜黑白 · 提亮中灰 · 中段拉开](look-profiles/201-300.md#preset-nt-negative-new-fuji-ilford-hp5)<br>`nt-negative-new-fuji-ilford-hp5` | 黑白 · 提亮中灰 · 中段拉开 | 黑白纪实、建筑与轮廓试片 | 1–1 | CC-BY-SA-4.0 |
| 296 | [黑白负片 · Fuji Ilford Hp5 ++｜黑白 · 提亮中灰 · 中段拉开](look-profiles/201-300.md#preset-nt-negative-new-fuji-ilford-hp5-curve-plus-2)<br>`nt-negative-new-fuji-ilford-hp5-curve-plus-2` | 黑白 · 提亮中灰 · 中段拉开 | 黑白纪实、建筑与轮廓试片 | 1–1 | CC-BY-SA-4.0 |
| 297 | [黑白负片 · Fuji Ilford Hp5 +｜黑白 · 提亮中灰 · 中段拉开](look-profiles/201-300.md#preset-nt-negative-new-fuji-ilford-hp5-curve-plus-1)<br>`nt-negative-new-fuji-ilford-hp5-curve-plus-1` | 黑白 · 提亮中灰 · 中段拉开 | 黑白纪实、建筑与轮廓试片 | 1–1 | CC-BY-SA-4.0 |
| 298 | [黑白负片 · Fuji Ilford Hp5 -｜黑白 · 提亮中灰 · 中段拉开](look-profiles/201-300.md#preset-nt-negative-new-fuji-ilford-hp5-curve-minus-1)<br>`nt-negative-new-fuji-ilford-hp5-curve-minus-1` | 黑白 · 提亮中灰 · 中段拉开 | 黑白纪实、建筑与轮廓试片 | 1–1 | CC-BY-SA-4.0 |
| 299 | [彩色负片 · Kodak Portra 160｜暖色 · 提亮中灰 · 中段拉开](look-profiles/201-300.md#preset-nt-negative-new-kodak-portra-160)<br>`nt-negative-new-kodak-portra-160` | 暖色 · 提亮中灰 · 中段拉开 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 300 | [彩色负片 · Kodak Portra 160 ++｜中性 · 提亮中灰 · 中段拉开](look-profiles/201-300.md#preset-nt-negative-new-kodak-portra-160-curve-plus-2)<br>`nt-negative-new-kodak-portra-160-curve-plus-2` | 中性 · 提亮中灰 · 中段拉开 | 产品、生活与风景对照试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 301 | [彩色负片 · Kodak Portra 160 +｜暖色 · 提亮中灰 · 中段拉开](look-profiles/301-400.md#preset-nt-negative-new-kodak-portra-160-curve-plus-1)<br>`nt-negative-new-kodak-portra-160-curve-plus-1` | 暖色 · 提亮中灰 · 中段拉开 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 302 | [彩色负片 · Kodak Portra 160 -｜中性 · 提亮中灰 · 中段跨度接近原值](look-profiles/301-400.md#preset-nt-negative-new-kodak-portra-160-curve-minus-1)<br>`nt-negative-new-kodak-portra-160-curve-minus-1` | 中性 · 提亮中灰 · 中段跨度接近原值 | 产品、生活与风景对照试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 303 | [彩色负片 · Kodak Portra 400｜中性 · 提亮中灰 · 中段拉开](look-profiles/301-400.md#preset-nt-negative-new-kodak-portra-400)<br>`nt-negative-new-kodak-portra-400` | 中性 · 提亮中灰 · 中段拉开 | 产品、生活与风景对照试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 304 | [彩色负片 · Kodak Portra 400 ++｜中性 · 提亮中灰 · 中段拉开](look-profiles/301-400.md#preset-nt-negative-new-kodak-portra-400-curve-plus-2)<br>`nt-negative-new-kodak-portra-400-curve-plus-2` | 中性 · 提亮中灰 · 中段拉开 | 产品、生活与风景对照试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 305 | [彩色负片 · Kodak Portra 400 +｜中性 · 提亮中灰 · 中段跨度接近原值](look-profiles/301-400.md#preset-nt-negative-new-kodak-portra-400-curve-plus-1)<br>`nt-negative-new-kodak-portra-400-curve-plus-1` | 中性 · 提亮中灰 · 中段跨度接近原值 | 产品、生活与风景对照试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 306 | [彩色负片 · Kodak Portra 400 -｜中性 · 提亮中灰 · 中段跨度接近原值](look-profiles/301-400.md#preset-nt-negative-new-kodak-portra-400-curve-minus-1)<br>`nt-negative-new-kodak-portra-400-curve-minus-1` | 中性 · 提亮中灰 · 中段跨度接近原值 | 产品、生活与风景对照试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 307 | [彩色负片 · Kodak Portra 800｜中性 · 提亮中灰 · 中段拉开](look-profiles/301-400.md#preset-nt-negative-new-kodak-portra-800)<br>`nt-negative-new-kodak-portra-800` | 中性 · 提亮中灰 · 中段拉开 | 产品、生活与风景对照试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 308 | [彩色负片 · Kodak Portra 800 ++｜中性 · 提亮中灰 · 中段拉开](look-profiles/301-400.md#preset-nt-negative-new-kodak-portra-800-curve-plus-2)<br>`nt-negative-new-kodak-portra-800-curve-plus-2` | 中性 · 提亮中灰 · 中段拉开 | 产品、生活与风景对照试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 309 | [彩色负片 · Kodak Portra 800 +｜暖色 · 提亮中灰 · 中段拉开](look-profiles/301-400.md#preset-nt-negative-new-kodak-portra-800-curve-plus-1)<br>`nt-negative-new-kodak-portra-800-curve-plus-1` | 暖色 · 提亮中灰 · 中段拉开 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 310 | [彩色负片 · Kodak Portra 800 -｜暖色 · 提亮中灰 · 中段拉开](look-profiles/301-400.md#preset-nt-negative-new-kodak-portra-800-curve-minus-1)<br>`nt-negative-new-kodak-portra-800-curve-minus-1` | 暖色 · 提亮中灰 · 中段拉开 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 311 | [黑白负片 · Kodak Tmax 3200｜黑白 · 提亮中灰 · 中段拉开](look-profiles/301-400.md#preset-nt-negative-new-kodak-tmax-3200)<br>`nt-negative-new-kodak-tmax-3200` | 黑白 · 提亮中灰 · 中段拉开 | 黑白纪实、建筑与轮廓试片 | 1–1 | CC-BY-SA-4.0 |
| 312 | [黑白负片 · Kodak Tmax 3200 ++｜黑白 · 提亮中灰 · 中段跨度接近原值](look-profiles/301-400.md#preset-nt-negative-new-kodak-tmax-3200-curve-plus-2)<br>`nt-negative-new-kodak-tmax-3200-curve-plus-2` | 黑白 · 提亮中灰 · 中段跨度接近原值 | 黑白纪实、建筑与轮廓试片 | 1–1 | CC-BY-SA-4.0 |
| 313 | [黑白负片 · Kodak Tmax 3200 +｜黑白 · 提亮中灰 · 中段拉开](look-profiles/301-400.md#preset-nt-negative-new-kodak-tmax-3200-curve-plus-1)<br>`nt-negative-new-kodak-tmax-3200-curve-plus-1` | 黑白 · 提亮中灰 · 中段拉开 | 黑白纪实、建筑与轮廓试片 | 1–1 | CC-BY-SA-4.0 |
| 314 | [黑白负片 · Kodak Tmax 3200 -｜黑白 · 中灰近原值 · 中段拉开](look-profiles/301-400.md#preset-nt-negative-new-kodak-tmax-3200-curve-minus-1)<br>`nt-negative-new-kodak-tmax-3200-curve-minus-1` | 黑白 · 中灰近原值 · 中段拉开 | 黑白纪实、建筑与轮廓试片 | 1–1 | CC-BY-SA-4.0 |
| 315 | [黑白负片 · Kodak Tri-X 400 ++｜黑白 · 提亮中灰 · 中段拉开](look-profiles/301-400.md#preset-nt-negative-new-kodak-tri-x-400-curve-plus-2)<br>`nt-negative-new-kodak-tri-x-400-curve-plus-2` | 黑白 · 提亮中灰 · 中段拉开 | 黑白纪实、建筑与轮廓试片 | 1–1 | CC-BY-SA-4.0 |
| 316 | [黑白负片 · Kodak Tri-X 400 +｜黑白 · 提亮中灰 · 中段拉开](look-profiles/301-400.md#preset-nt-negative-new-kodak-tri-x-400-curve-plus-1)<br>`nt-negative-new-kodak-tri-x-400-curve-plus-1` | 黑白 · 提亮中灰 · 中段拉开 | 黑白纪实、建筑与轮廓试片 | 1–1 | CC-BY-SA-4.0 |
| 317 | [黑白负片 · Kodak Tri-X 400 -｜黑白 · 提亮中灰 · 中段拉开](look-profiles/301-400.md#preset-nt-negative-new-kodak-tri-x-400-curve-minus-1)<br>`nt-negative-new-kodak-tri-x-400-curve-minus-1` | 黑白 · 提亮中灰 · 中段拉开 | 黑白纪实、建筑与轮廓试片 | 1–1 | CC-BY-SA-4.0 |
| 318 | [黑白负片 · Fuji Ilford Delta 3200｜黑白 · 提亮中灰 · 中段拉开](look-profiles/301-400.md#preset-nt-negative-old-fuji-ilford-delta-3200)<br>`nt-negative-old-fuji-ilford-delta-3200` | 黑白 · 提亮中灰 · 中段拉开 | 黑白纪实、建筑与轮廓试片 | 1–1 | CC-BY-SA-4.0 |
| 319 | [黑白负片 · Fuji Ilford Delta 3200 ++｜黑白 · 中灰近原值 · 中段拉开](look-profiles/301-400.md#preset-nt-negative-old-fuji-ilford-delta-3200-curve-plus-2)<br>`nt-negative-old-fuji-ilford-delta-3200-curve-plus-2` | 黑白 · 中灰近原值 · 中段拉开 | 黑白纪实、建筑与轮廓试片 | 1–1 | CC-BY-SA-4.0 |
| 320 | [黑白负片 · Fuji Ilford Delta 3200 +｜黑白 · 提亮中灰 · 中段拉开](look-profiles/301-400.md#preset-nt-negative-old-fuji-ilford-delta-3200-curve-plus-1)<br>`nt-negative-old-fuji-ilford-delta-3200-curve-plus-1` | 黑白 · 提亮中灰 · 中段拉开 | 黑白纪实、建筑与轮廓试片 | 1–1 | CC-BY-SA-4.0 |
| 321 | [黑白负片 · Fuji Ilford Delta 3200 -｜黑白 · 提亮中灰 · 中段拉开](look-profiles/301-400.md#preset-nt-negative-old-fuji-ilford-delta-3200-curve-minus-1)<br>`nt-negative-old-fuji-ilford-delta-3200-curve-minus-1` | 黑白 · 提亮中灰 · 中段拉开 | 黑白纪实、建筑与轮廓试片 | 1–1 | CC-BY-SA-4.0 |
| 322 | [黑白负片 · Fuji Neopan 1600 ++｜黑白 · 提亮中灰 · 中段拉开](look-profiles/301-400.md#preset-nt-negative-old-fuji-neopan-1600-curve-plus-2)<br>`nt-negative-old-fuji-neopan-1600-curve-plus-2` | 黑白 · 提亮中灰 · 中段拉开 | 黑白纪实、建筑与轮廓试片 | 1–1 | CC-BY-SA-4.0 |
| 323 | [黑白负片 · Fuji Neopan 1600 +｜黑白 · 提亮中灰 · 中段拉开](look-profiles/301-400.md#preset-nt-negative-old-fuji-neopan-1600-curve-plus-1)<br>`nt-negative-old-fuji-neopan-1600-curve-plus-1` | 黑白 · 提亮中灰 · 中段拉开 | 黑白纪实、建筑与轮廓试片 | 1–1 | CC-BY-SA-4.0 |
| 324 | [黑白负片 · Fuji Neopan 1600 -｜黑白 · 提亮中灰 · 中段拉开](look-profiles/301-400.md#preset-nt-negative-old-fuji-neopan-1600-curve-minus-1)<br>`nt-negative-old-fuji-neopan-1600-curve-minus-1` | 黑白 · 提亮中灰 · 中段拉开 | 黑白纪实、建筑与轮廓试片 | 1–1 | CC-BY-SA-4.0 |
| 325 | [彩色负片 · Fuji Superia 100｜中性 · 提亮中灰 · 中段拉开](look-profiles/301-400.md#preset-nt-negative-old-fuji-superia-100)<br>`nt-negative-old-fuji-superia-100` | 中性 · 提亮中灰 · 中段拉开 | 产品、生活与风景对照试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 326 | [彩色负片 · Fuji Superia 100 ++｜中性 · 提亮中灰 · 中段拉开](look-profiles/301-400.md#preset-nt-negative-old-fuji-superia-100-curve-plus-2)<br>`nt-negative-old-fuji-superia-100-curve-plus-2` | 中性 · 提亮中灰 · 中段拉开 | 产品、生活与风景对照试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 327 | [彩色负片 · Fuji Superia 100 +｜暖色 · 提亮中灰 · 中段拉开](look-profiles/301-400.md#preset-nt-negative-old-fuji-superia-100-curve-plus-1)<br>`nt-negative-old-fuji-superia-100-curve-plus-1` | 暖色 · 提亮中灰 · 中段拉开 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 328 | [彩色负片 · Fuji Superia 100 -｜中性 · 提亮中灰 · 中段拉开](look-profiles/301-400.md#preset-nt-negative-old-fuji-superia-100-curve-minus-1)<br>`nt-negative-old-fuji-superia-100-curve-minus-1` | 中性 · 提亮中灰 · 中段拉开 | 产品、生活与风景对照试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 329 | [彩色负片 · Fuji Superia 1600｜暖色 · 提亮中灰 · 中段拉开](look-profiles/301-400.md#preset-nt-negative-old-fuji-superia-1600)<br>`nt-negative-old-fuji-superia-1600` | 暖色 · 提亮中灰 · 中段拉开 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 330 | [彩色负片 · Fuji Superia 1600 ++｜暖色 · 提亮中灰 · 中段跨度接近原值](look-profiles/301-400.md#preset-nt-negative-old-fuji-superia-1600-curve-plus-2)<br>`nt-negative-old-fuji-superia-1600-curve-plus-2` | 暖色 · 提亮中灰 · 中段跨度接近原值 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 331 | [彩色负片 · Fuji Superia 1600 +｜暖色 · 提亮中灰 · 中段跨度接近原值](look-profiles/301-400.md#preset-nt-negative-old-fuji-superia-1600-curve-plus-1)<br>`nt-negative-old-fuji-superia-1600-curve-plus-1` | 暖色 · 提亮中灰 · 中段跨度接近原值 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 332 | [彩色负片 · Fuji Superia 1600 -｜暖色 · 提亮中灰 · 中段拉开](look-profiles/301-400.md#preset-nt-negative-old-fuji-superia-1600-curve-minus-1)<br>`nt-negative-old-fuji-superia-1600-curve-minus-1` | 暖色 · 提亮中灰 · 中段拉开 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 333 | [彩色负片 · Fuji Superia 400｜暖色 · 提亮中灰 · 中段拉开](look-profiles/301-400.md#preset-nt-negative-old-fuji-superia-400)<br>`nt-negative-old-fuji-superia-400` | 暖色 · 提亮中灰 · 中段拉开 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 334 | [彩色负片 · Fuji Superia 400 ++｜暖色 · 提亮中灰 · 中段拉开](look-profiles/301-400.md#preset-nt-negative-old-fuji-superia-400-curve-plus-2)<br>`nt-negative-old-fuji-superia-400-curve-plus-2` | 暖色 · 提亮中灰 · 中段拉开 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 335 | [彩色负片 · Fuji Superia 400 +｜中性 · 提亮中灰 · 中段拉开](look-profiles/301-400.md#preset-nt-negative-old-fuji-superia-400-curve-plus-1)<br>`nt-negative-old-fuji-superia-400-curve-plus-1` | 中性 · 提亮中灰 · 中段拉开 | 产品、生活与风景对照试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 336 | [彩色负片 · Fuji Superia 400 -｜暖色 · 提亮中灰 · 中段拉开](look-profiles/301-400.md#preset-nt-negative-old-fuji-superia-400-curve-minus-1)<br>`nt-negative-old-fuji-superia-400-curve-minus-1` | 暖色 · 提亮中灰 · 中段拉开 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 337 | [彩色负片 · Fuji Superia 800｜暖色 · 提亮中灰 · 中段拉开](look-profiles/301-400.md#preset-nt-negative-old-fuji-superia-800)<br>`nt-negative-old-fuji-superia-800` | 暖色 · 提亮中灰 · 中段拉开 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 338 | [彩色负片 · Fuji Superia 800 ++｜暖色 · 提亮中灰 · 中段跨度接近原值](look-profiles/301-400.md#preset-nt-negative-old-fuji-superia-800-curve-plus-2)<br>`nt-negative-old-fuji-superia-800-curve-plus-2` | 暖色 · 提亮中灰 · 中段跨度接近原值 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 339 | [彩色负片 · Fuji Superia 800 +｜暖色 · 提亮中灰 · 中段拉开](look-profiles/301-400.md#preset-nt-negative-old-fuji-superia-800-curve-plus-1)<br>`nt-negative-old-fuji-superia-800-curve-plus-1` | 暖色 · 提亮中灰 · 中段拉开 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 340 | [彩色负片 · Fuji Superia 800 -｜中性 · 提亮中灰 · 中段拉开](look-profiles/301-400.md#preset-nt-negative-old-fuji-superia-800-curve-minus-1)<br>`nt-negative-old-fuji-superia-800-curve-minus-1` | 中性 · 提亮中灰 · 中段拉开 | 产品、生活与风景对照试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 341 | [彩色负片 · Kodak Portra 160 Nc ++｜中性 · 提亮中灰 · 中段跨度接近原值](look-profiles/301-400.md#preset-nt-negative-old-kodak-portra-160-nc-curve-plus-2)<br>`nt-negative-old-kodak-portra-160-nc-curve-plus-2` | 中性 · 提亮中灰 · 中段跨度接近原值 | 产品、生活与风景对照试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 342 | [彩色负片 · Kodak Portra 160 Nc +｜暖色 · 提亮中灰 · 中段拉开](look-profiles/301-400.md#preset-nt-negative-old-kodak-portra-160-nc-curve-plus-1)<br>`nt-negative-old-kodak-portra-160-nc-curve-plus-1` | 暖色 · 提亮中灰 · 中段拉开 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 343 | [彩色负片 · Kodak Portra 160 Nc -｜中性 · 提亮中灰 · 中段拉开](look-profiles/301-400.md#preset-nt-negative-old-kodak-portra-160-nc-curve-minus-1)<br>`nt-negative-old-kodak-portra-160-nc-curve-minus-1` | 中性 · 提亮中灰 · 中段拉开 | 产品、生活与风景对照试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 344 | [彩色负片 · Kodak Portra 160 Vc ++｜暖色 · 提亮中灰 · 中段拉开](look-profiles/301-400.md#preset-nt-negative-old-kodak-portra-160-vc-curve-plus-2)<br>`nt-negative-old-kodak-portra-160-vc-curve-plus-2` | 暖色 · 提亮中灰 · 中段拉开 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 345 | [彩色负片 · Kodak Portra 160 Vc +｜暖色 · 提亮中灰 · 中段拉开](look-profiles/301-400.md#preset-nt-negative-old-kodak-portra-160-vc-curve-plus-1)<br>`nt-negative-old-kodak-portra-160-vc-curve-plus-1` | 暖色 · 提亮中灰 · 中段拉开 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 346 | [彩色负片 · Kodak Portra 160 Vc -｜中性 · 提亮中灰 · 中段拉开](look-profiles/301-400.md#preset-nt-negative-old-kodak-portra-160-vc-curve-minus-1)<br>`nt-negative-old-kodak-portra-160-vc-curve-minus-1` | 中性 · 提亮中灰 · 中段拉开 | 产品、生活与风景对照试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 347 | [彩色负片 · Kodak Portra 400 Nc｜中性 · 提亮中灰 · 中段拉开](look-profiles/301-400.md#preset-nt-negative-old-kodak-portra-400-nc)<br>`nt-negative-old-kodak-portra-400-nc` | 中性 · 提亮中灰 · 中段拉开 | 产品、生活与风景对照试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 348 | [彩色负片 · Kodak Portra 400 Nc ++｜暖色 · 提亮中灰 · 中段拉开](look-profiles/301-400.md#preset-nt-negative-old-kodak-portra-400-nc-curve-plus-2)<br>`nt-negative-old-kodak-portra-400-nc-curve-plus-2` | 暖色 · 提亮中灰 · 中段拉开 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 349 | [彩色负片 · Kodak Portra 400 Nc +｜暖色 · 提亮中灰 · 中段拉开](look-profiles/301-400.md#preset-nt-negative-old-kodak-portra-400-nc-curve-plus-1)<br>`nt-negative-old-kodak-portra-400-nc-curve-plus-1` | 暖色 · 提亮中灰 · 中段拉开 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 350 | [彩色负片 · Kodak Portra 400 Nc -｜暖色 · 提亮中灰 · 中段拉开](look-profiles/301-400.md#preset-nt-negative-old-kodak-portra-400-nc-curve-minus-1)<br>`nt-negative-old-kodak-portra-400-nc-curve-minus-1` | 暖色 · 提亮中灰 · 中段拉开 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 351 | [彩色负片 · Kodak Portra 400 Uc｜暖色 · 提亮中灰 · 中段拉开](look-profiles/301-400.md#preset-nt-negative-old-kodak-portra-400-uc)<br>`nt-negative-old-kodak-portra-400-uc` | 暖色 · 提亮中灰 · 中段拉开 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 352 | [彩色负片 · Kodak Portra 400 Uc ++｜暖色 · 提亮中灰 · 中段拉开](look-profiles/301-400.md#preset-nt-negative-old-kodak-portra-400-uc-curve-plus-2)<br>`nt-negative-old-kodak-portra-400-uc-curve-plus-2` | 暖色 · 提亮中灰 · 中段拉开 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 353 | [彩色负片 · Kodak Portra 400 Uc +｜暖色 · 提亮中灰 · 中段跨度接近原值](look-profiles/301-400.md#preset-nt-negative-old-kodak-portra-400-uc-curve-plus-1)<br>`nt-negative-old-kodak-portra-400-uc-curve-plus-1` | 暖色 · 提亮中灰 · 中段跨度接近原值 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 354 | [彩色负片 · Kodak Portra 400 Uc -｜暖色 · 提亮中灰 · 中段拉开](look-profiles/301-400.md#preset-nt-negative-old-kodak-portra-400-uc-curve-minus-1)<br>`nt-negative-old-kodak-portra-400-uc-curve-minus-1` | 暖色 · 提亮中灰 · 中段拉开 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 355 | [彩色负片 · Kodak Portra 400 Vc｜暖色 · 提亮中灰 · 中段拉开](look-profiles/301-400.md#preset-nt-negative-old-kodak-portra-400-vc)<br>`nt-negative-old-kodak-portra-400-vc` | 暖色 · 提亮中灰 · 中段拉开 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 356 | [彩色负片 · Kodak Portra 400 Vc ++｜暖色 · 提亮中灰 · 中段跨度接近原值](look-profiles/301-400.md#preset-nt-negative-old-kodak-portra-400-vc-curve-plus-2)<br>`nt-negative-old-kodak-portra-400-vc-curve-plus-2` | 暖色 · 提亮中灰 · 中段跨度接近原值 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 357 | [彩色负片 · Kodak Portra 400 Vc +｜暖色 · 提亮中灰 · 中段跨度接近原值](look-profiles/301-400.md#preset-nt-negative-old-kodak-portra-400-vc-curve-plus-1)<br>`nt-negative-old-kodak-portra-400-vc-curve-plus-1` | 暖色 · 提亮中灰 · 中段跨度接近原值 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 358 | [彩色负片 · Kodak Portra 400 Vc -｜暖色 · 提亮中灰 · 中段跨度接近原值](look-profiles/301-400.md#preset-nt-negative-old-kodak-portra-400-vc-curve-minus-1)<br>`nt-negative-old-kodak-portra-400-vc-curve-minus-1` | 暖色 · 提亮中灰 · 中段跨度接近原值 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 359 | [创意色彩 · Analogfx Anno 1870 Color｜暖色 · 压暗中灰 · 中段拉开](look-profiles/301-400.md#preset-nt-picturefx-analogfx-anno-1870-color)<br>`nt-picturefx-analogfx-anno-1870-color` | 暖色 · 压暗中灰 · 中段拉开 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 360 | [创意色彩 · Analogfx Sepia Color｜暖色 · 压暗中灰 · 中段拉开](look-profiles/301-400.md#preset-nt-picturefx-analogfx-sepia-color)<br>`nt-picturefx-analogfx-sepia-color` | 暖色 · 压暗中灰 · 中段拉开 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 361 | [创意色彩 · Goldfx Bright Spring Breeze｜冷色 · 提亮中灰 · 中段拉开](look-profiles/301-400.md#preset-nt-picturefx-goldfx-bright-spring-breeze)<br>`nt-picturefx-goldfx-bright-spring-breeze` | 冷色 · 提亮中灰 · 中段拉开 | 冷色城市、夜景与科技试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 362 | [创意色彩 · Goldfx Bright Summer Heat｜暖色 · 提亮中灰 · 中段拉开](look-profiles/301-400.md#preset-nt-picturefx-goldfx-bright-summer-heat)<br>`nt-picturefx-goldfx-bright-summer-heat` | 暖色 · 提亮中灰 · 中段拉开 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 363 | [创意色彩 · Goldfx Hot Summer Heat｜暖色 · 提亮中灰 · 中段拉开](look-profiles/301-400.md#preset-nt-picturefx-goldfx-hot-summer-heat)<br>`nt-picturefx-goldfx-hot-summer-heat` | 暖色 · 提亮中灰 · 中段拉开 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 364 | [创意色彩 · Goldfx Spring Breeze｜中性 · 提亮中灰 · 中段拉开](look-profiles/301-400.md#preset-nt-picturefx-goldfx-spring-breeze)<br>`nt-picturefx-goldfx-spring-breeze` | 中性 · 提亮中灰 · 中段拉开 | 产品、生活与风景对照试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 365 | [创意色彩 · Goldfx Summer Heat｜暖色 · 提亮中灰 · 中段拉开](look-profiles/301-400.md#preset-nt-picturefx-goldfx-summer-heat)<br>`nt-picturefx-goldfx-summer-heat` | 暖色 · 提亮中灰 · 中段拉开 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 366 | [创意色彩 · Zilverfx Infrared｜中性 · 提亮中灰 · 中段拉开](look-profiles/301-400.md#preset-nt-picturefx-zilverfx-infrared)<br>`nt-picturefx-zilverfx-infrared` | 中性 · 提亮中灰 · 中段拉开 | 产品、生活与风景对照试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 367 | [创意色彩 · Zilverfx Vintage B W｜暖色 · 提亮中灰 · 中段拉开](look-profiles/301-400.md#preset-nt-picturefx-zilverfx-vintage-b-w)<br>`nt-picturefx-zilverfx-vintage-b-w` | 暖色 · 提亮中灰 · 中段拉开 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC-BY-SA-4.0 |
| 368 | [创意色彩 · Action - Magenta 01｜暖色 · 中灰近原值 · 中段跨度接近原值](look-profiles/301-400.md#preset-fl-0000001-action-magenta-01)<br>`fl-0000001-action-magenta-01` | 暖色 · 中灰近原值 · 中段跨度接近原值 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC0-1.0 |
| 369 | [创意色彩 · Action Red 01｜冷色 · 压暗中灰 · 中段跨度接近原值](look-profiles/301-400.md#preset-fl-0000002-action-red-01)<br>`fl-0000002-action-red-01` | 冷色 · 压暗中灰 · 中段跨度接近原值 | 冷色城市、夜景与科技试片 | 0.35–0.8 | CC0-1.0 |
| 370 | [创意色彩 · Adventure 1453｜冷色 · 压暗中灰 · 中段跨度接近原值](look-profiles/301-400.md#preset-fl-0000003-adventure-1453)<br>`fl-0000003-adventure-1453` | 冷色 · 压暗中灰 · 中段跨度接近原值 | 冷色城市、夜景与科技试片 | 0.35–0.8 | CC0-1.0 |
| 371 | [创意色彩 · Aggressive Highlighted recovery｜中性 · 压暗中灰 · 中段收窄](look-profiles/301-400.md#preset-fl-0000004-aggressive-highlighted-recovery)<br>`fl-0000004-aggressive-highlighted-recovery` | 中性 · 压暗中灰 · 中段收窄 | 产品、生活与风景对照试片 | 0.35–0.8 | CC0-1.0 |
| 372 | [创意色彩 · Bleach Bypass Green 01｜暖色 · 中灰近原值 · 中段拉开](look-profiles/301-400.md#preset-fl-0000005-bleach-bypass-green-01)<br>`fl-0000005-bleach-bypass-green-01` | 暖色 · 中灰近原值 · 中段拉开 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC0-1.0 |
| 373 | [创意色彩 · Bleach Bypass Yellow 01｜暖色 · 中灰近原值 · 中段拉开](look-profiles/301-400.md#preset-fl-0000006-bleach-bypass-yellow-01)<br>`fl-0000006-bleach-bypass-yellow-01` | 暖色 · 中灰近原值 · 中段拉开 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC0-1.0 |
| 374 | [创意色彩 · Blue Dark｜冷色 · 压暗中灰 · 中段收窄](look-profiles/301-400.md#preset-fl-0000007-blue-dark)<br>`fl-0000007-blue-dark` | 冷色 · 压暗中灰 · 中段收窄 | 冷色城市、夜景与科技试片 | 0.35–0.8 | CC0-1.0 |
| 375 | [创意色彩 · Bright Green 01｜暖色 · 压暗中灰 · 中段收窄](look-profiles/301-400.md#preset-fl-0000009-bright-green-01)<br>`fl-0000009-bright-green-01` | 暖色 · 压暗中灰 · 中段收窄 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC0-1.0 |
| 376 | [电影色彩 · Brownish｜暖色 · 压暗中灰 · 中段拉开](look-profiles/301-400.md#preset-fl-0000010-brownish)<br>`fl-0000010-brownish` | 暖色 · 压暗中灰 · 中段拉开 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC0-1.0 |
| 377 | [创意色彩 · Colorful 0209｜中性 · 中灰近原值 · 中段跨度接近原值](look-profiles/301-400.md#preset-fl-0000011-colorful-0209)<br>`fl-0000011-colorful-0209` | 中性 · 中灰近原值 · 中段跨度接近原值 | 产品、生活与风景对照试片 | 0.35–0.8 | CC0-1.0 |
| 378 | [创意色彩 · Conflict 01｜冷色 · 压暗中灰 · 中段跨度接近原值](look-profiles/301-400.md#preset-fl-0000012-conflict-01)<br>`fl-0000012-conflict-01` | 冷色 · 压暗中灰 · 中段跨度接近原值 | 冷色城市、夜景与科技试片 | 0.35–0.8 | CC0-1.0 |
| 379 | [创意色彩 · Contrast with highlights protection｜中性 · 中灰近原值 · 中段拉开](look-profiles/301-400.md#preset-fl-0000013-contrast-with-highlights-protection)<br>`fl-0000013-contrast-with-highlights-protection` | 中性 · 中灰近原值 · 中段拉开 | 产品、生活与风景对照试片 | 0.35–0.8 | CC0-1.0 |
| 380 | [创意色彩 · Contrasty afternoon｜冷色 · 压暗中灰 · 中段拉开](look-profiles/301-400.md#preset-fl-0000014-contrasty-afternoon)<br>`fl-0000014-contrasty-afternoon` | 冷色 · 压暗中灰 · 中段拉开 | 冷色城市、夜景与科技试片 | 0.35–0.8 | CC0-1.0 |
| 381 | [电影色彩 · Contrasty Green｜暖色 · 提亮中灰 · 中段拉开](look-profiles/301-400.md#preset-fl-0000015-contrasty-green)<br>`fl-0000015-contrasty-green` | 暖色 · 提亮中灰 · 中段拉开 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC0-1.0 |
| 382 | [创意色彩 · Cross Process CP15｜暖色 · 压暗中灰 · 中段拉开](look-profiles/301-400.md#preset-fl-0000016-cross-process-cp15)<br>`fl-0000016-cross-process-cp15` | 暖色 · 压暗中灰 · 中段拉开 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC0-1.0 |
| 383 | [创意色彩 · Cross process CP3｜冷色 · 提亮中灰 · 中段拉开](look-profiles/301-400.md#preset-fl-0000017-cross-process-cp3)<br>`fl-0000017-cross-process-cp3` | 冷色 · 提亮中灰 · 中段拉开 | 冷色城市、夜景与科技试片 | 0.35–0.8 | CC0-1.0 |
| 384 | [创意色彩 · Cross Process CP4｜冷色 · 提亮中灰 · 中段拉开](look-profiles/301-400.md#preset-fl-0000018-cross-process-cp4)<br>`fl-0000018-cross-process-cp4` | 冷色 · 提亮中灰 · 中段拉开 | 冷色城市、夜景与科技试片 | 0.35–0.8 | CC0-1.0 |
| 385 | [创意色彩 · Cross Process CP6｜冷色 · 压暗中灰 · 中段拉开](look-profiles/301-400.md#preset-fl-0000019-cross-process-cp6)<br>`fl-0000019-cross-process-cp6` | 冷色 · 压暗中灰 · 中段拉开 | 冷色城市、夜景与科技试片 | 0.35–0.8 | CC0-1.0 |
| 386 | [创意色彩 · Cross Process CP14｜暖色 · 压暗中灰 · 中段跨度接近原值](look-profiles/301-400.md#preset-fl-0000020-cross-process-cp14)<br>`fl-0000020-cross-process-cp14` | 暖色 · 压暗中灰 · 中段跨度接近原值 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC0-1.0 |
| 387 | [创意色彩 · Cross Process CP16｜暖色 · 压暗中灰 · 中段跨度接近原值](look-profiles/301-400.md#preset-fl-0000021-cross-process-cp16)<br>`fl-0000021-cross-process-cp16` | 暖色 · 压暗中灰 · 中段跨度接近原值 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC0-1.0 |
| 388 | [创意色彩 · Cross Process CP18｜暖色 · 中灰近原值 · 中段跨度接近原值](look-profiles/301-400.md#preset-fl-0000022-cross-process-cp18)<br>`fl-0000022-cross-process-cp18` | 暖色 · 中灰近原值 · 中段跨度接近原值 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC0-1.0 |
| 389 | [创意色彩 · Cross Process CP130｜暖色 · 压暗中灰 · 中段跨度接近原值](look-profiles/301-400.md#preset-fl-0000023-cross-process-cp130)<br>`fl-0000023-cross-process-cp130` | 暖色 · 压暗中灰 · 中段跨度接近原值 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC0-1.0 |
| 390 | [创意色彩 · Dark Green｜冷色 · 压暗中灰 · 中段收窄](look-profiles/301-400.md#preset-fl-0000024-dark-green)<br>`fl-0000024-dark-green` | 冷色 · 压暗中灰 · 中段收窄 | 冷色城市、夜景与科技试片 | 0.35–0.8 | CC0-1.0 |
| 391 | [创意色彩 · Dark Green 02｜冷色 · 压暗中灰 · 中段拉开](look-profiles/301-400.md#preset-fl-0000025-dark-green-02)<br>`fl-0000025-dark-green-02` | 冷色 · 压暗中灰 · 中段拉开 | 冷色城市、夜景与科技试片 | 0.35–0.8 | CC0-1.0 |
| 392 | [创意色彩 · Dream 1｜暖色 · 中灰近原值 · 中段跨度接近原值](look-profiles/301-400.md#preset-fl-0000027-dream-1)<br>`fl-0000027-dream-1` | 暖色 · 中灰近原值 · 中段跨度接近原值 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC0-1.0 |
| 393 | [电影色彩 · Dream 85｜暖色 · 压暗中灰 · 中段跨度接近原值](look-profiles/301-400.md#preset-fl-0000028-dream-85)<br>`fl-0000028-dream-85` | 暖色 · 压暗中灰 · 中段跨度接近原值 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC0-1.0 |
| 394 | [创意色彩 · Faded Retro 01｜暖色 · 提亮中灰 · 中段跨度接近原值](look-profiles/301-400.md#preset-fl-0000029-faded-retro-01)<br>`fl-0000029-faded-retro-01` | 暖色 · 提亮中灰 · 中段跨度接近原值 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC0-1.0 |
| 395 | [创意色彩 · Faded Retro 02｜冷色 · 提亮中灰 · 中段跨度接近原值](look-profiles/301-400.md#preset-fl-0000030-faded-retro-02)<br>`fl-0000030-faded-retro-02` | 冷色 · 提亮中灰 · 中段跨度接近原值 | 冷色城市、夜景与科技试片 | 0.35–0.8 | CC0-1.0 |
| 396 | [电影色彩 · Film 0987｜冷色 · 压暗中灰 · 中段拉开](look-profiles/301-400.md#preset-fl-0000031-film-0987)<br>`fl-0000031-film-0987` | 冷色 · 压暗中灰 · 中段拉开 | 冷色城市、夜景与科技试片 | 0.35–0.8 | CC0-1.0 |
| 397 | [电影色彩 · Film 9879｜中性 · 压暗中灰 · 中段拉开](look-profiles/301-400.md#preset-fl-0000032-film-9879)<br>`fl-0000032-film-9879` | 中性 · 压暗中灰 · 中段拉开 | 产品、生活与风景对照试片 | 0.35–0.8 | CC0-1.0 |
| 398 | [电影色彩 · Film High Contrast｜冷色 · 压暗中灰 · 中段拉开](look-profiles/301-400.md#preset-fl-0000033-film-high-contrast)<br>`fl-0000033-film-high-contrast` | 冷色 · 压暗中灰 · 中段拉开 | 冷色城市、夜景与科技试片 | 0.35–0.8 | CC0-1.0 |
| 399 | [创意色彩 · Flat 30｜暖色 · 中灰近原值 · 中段收窄](look-profiles/301-400.md#preset-fl-0000034-flat-30)<br>`fl-0000034-flat-30` | 暖色 · 中灰近原值 · 中段收窄 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC0-1.0 |
| 400 | [创意色彩 · Green 2025｜暖色 · 压暗中灰 · 中段收窄](look-profiles/301-400.md#preset-fl-0000035-green-2025)<br>`fl-0000035-green-2025` | 暖色 · 压暗中灰 · 中段收窄 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC0-1.0 |
| 401 | [创意色彩 · Green Action｜暖色 · 压暗中灰 · 中段收窄](look-profiles/401-500.md#preset-fl-0000036-green-action)<br>`fl-0000036-green-action` | 暖色 · 压暗中灰 · 中段收窄 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC0-1.0 |
| 402 | [创意色彩 · Green Afternoon｜暖色 · 压暗中灰 · 中段拉开](look-profiles/401-500.md#preset-fl-0000037-green-afternoon)<br>`fl-0000037-green-afternoon` | 暖色 · 压暗中灰 · 中段拉开 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC0-1.0 |
| 403 | [创意色彩 · Green Conflict｜暖色 · 压暗中灰 · 中段拉开](look-profiles/401-500.md#preset-fl-0000038-green-conflict)<br>`fl-0000038-green-conflict` | 暖色 · 压暗中灰 · 中段拉开 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC0-1.0 |
| 404 | [电影色彩 · Green Day 01｜暖色 · 压暗中灰 · 中段跨度接近原值](look-profiles/401-500.md#preset-fl-0000039-green-day-01)<br>`fl-0000039-green-day-01` | 暖色 · 压暗中灰 · 中段跨度接近原值 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC0-1.0 |
| 405 | [电影色彩 · Green Day 02｜暖色 · 压暗中灰 · 中段拉开](look-profiles/401-500.md#preset-fl-0000040-green-day-02)<br>`fl-0000040-green-day-02` | 暖色 · 压暗中灰 · 中段拉开 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC0-1.0 |
| 406 | [创意色彩 · Green G09｜冷色 · 中灰近原值 · 中段拉开](look-profiles/401-500.md#preset-fl-0000041-green-g09)<br>`fl-0000041-green-g09` | 冷色 · 中灰近原值 · 中段拉开 | 冷色城市、夜景与科技试片 | 0.35–0.8 | CC0-1.0 |
| 407 | [创意色彩 · Green Indoor｜暖色 · 压暗中灰 · 中段拉开](look-profiles/401-500.md#preset-fl-0000042-green-indoor)<br>`fl-0000042-green-indoor` | 暖色 · 压暗中灰 · 中段拉开 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC0-1.0 |
| 408 | [创意色彩 · Harsh Day｜暖色 · 压暗中灰 · 中段跨度接近原值](look-profiles/401-500.md#preset-fl-0000044-harsh-day)<br>`fl-0000044-harsh-day` | 暖色 · 压暗中灰 · 中段跨度接近原值 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC0-1.0 |
| 409 | [创意色彩 · Harsh Sunset｜暖色 · 压暗中灰 · 中段跨度接近原值](look-profiles/401-500.md#preset-fl-0000045-harsh-sunset)<br>`fl-0000045-harsh-sunset` | 暖色 · 压暗中灰 · 中段跨度接近原值 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC0-1.0 |
| 410 | [创意色彩 · Highlights Protection｜中性 · 压暗中灰 · 中段拉开](look-profiles/401-500.md#preset-fl-0000046-highlights-protection)<br>`fl-0000046-highlights-protection` | 中性 · 压暗中灰 · 中段拉开 | 产品、生活与风景对照试片 | 0.35–0.8 | CC0-1.0 |
| 411 | [创意色彩 · Low contrast blue｜冷色 · 提亮中灰 · 中段收窄](look-profiles/401-500.md#preset-fl-0000048-low-contrast-blue)<br>`fl-0000048-low-contrast-blue` | 冷色 · 提亮中灰 · 中段收窄 | 冷色城市、夜景与科技试片 | 0.35–0.8 | CC0-1.0 |
| 412 | [创意色彩 · Magenta Day｜暖色 · 压暗中灰 · 中段跨度接近原值](look-profiles/401-500.md#preset-fl-0000049-magenta-day)<br>`fl-0000049-magenta-day` | 暖色 · 压暗中灰 · 中段跨度接近原值 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC0-1.0 |
| 413 | [创意色彩 · Magenta Day 01｜中性 · 压暗中灰 · 中段跨度接近原值](look-profiles/401-500.md#preset-fl-0000050-magenta-day-01)<br>`fl-0000050-magenta-day-01` | 中性 · 压暗中灰 · 中段跨度接近原值 | 产品、生活与风景对照试片 | 0.35–0.8 | CC0-1.0 |
| 414 | [创意色彩 · Memories｜暖色 · 提亮中灰 · 中段收窄](look-profiles/401-500.md#preset-fl-0000052-memories)<br>`fl-0000052-memories` | 暖色 · 提亮中灰 · 中段收窄 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC0-1.0 |
| 415 | [创意色彩 · Moonlight 01｜冷色 · 压暗中灰 · 中段收窄](look-profiles/401-500.md#preset-fl-0000053-moonlight-01)<br>`fl-0000053-moonlight-01` | 冷色 · 压暗中灰 · 中段收窄 | 冷色城市、夜景与科技试片 | 0.35–0.8 | CC0-1.0 |
| 416 | [创意色彩 · Mostly Blue｜中性 · 中灰近原值 · 中段跨度接近原值](look-profiles/401-500.md#preset-fl-0000054-mostly-blue)<br>`fl-0000054-mostly-blue` | 中性 · 中灰近原值 · 中段跨度接近原值 | 产品、生活与风景对照试片 | 0.35–0.8 | CC0-1.0 |
| 417 | [创意色彩 · Muted 01｜暖色 · 提亮中灰 · 中段收窄](look-profiles/401-500.md#preset-fl-0000055-muted-01)<br>`fl-0000055-muted-01` | 暖色 · 提亮中灰 · 中段收窄 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC0-1.0 |
| 418 | [创意色彩 · Only Red｜中性 · 中灰近原值 · 中段跨度接近原值](look-profiles/401-500.md#preset-fl-0000057-only-red)<br>`fl-0000057-only-red` | 中性 · 中灰近原值 · 中段跨度接近原值 | 产品、生活与风景对照试片 | 0.35–0.8 | CC0-1.0 |
| 419 | [创意色彩 · Only Red and Blue｜中性 · 中灰近原值 · 中段跨度接近原值](look-profiles/401-500.md#preset-fl-0000058-only-red-and-blue)<br>`fl-0000058-only-red-and-blue` | 中性 · 中灰近原值 · 中段跨度接近原值 | 产品、生活与风景对照试片 | 0.35–0.8 | CC0-1.0 |
| 420 | [电影色彩 · Operation Yellow｜暖色 · 中灰近原值 · 中段跨度接近原值](look-profiles/401-500.md#preset-fl-0000059-operation-yellow)<br>`fl-0000059-operation-yellow` | 暖色 · 中灰近原值 · 中段跨度接近原值 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC0-1.0 |
| 421 | [创意色彩 · Orange Dark 4｜暖色 · 压暗中灰 · 中段跨度接近原值](look-profiles/401-500.md#preset-fl-0000060-orange-dark-4)<br>`fl-0000060-orange-dark-4` | 暖色 · 压暗中灰 · 中段跨度接近原值 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC0-1.0 |
| 422 | [电影色彩 · Orange Dark 7｜暖色 · 中灰近原值 · 中段拉开](look-profiles/401-500.md#preset-fl-0000061-orange-dark-7)<br>`fl-0000061-orange-dark-7` | 暖色 · 中灰近原值 · 中段拉开 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC0-1.0 |
| 423 | [电影色彩 · Orange Dark look｜暖色 · 中灰近原值 · 中段拉开](look-profiles/401-500.md#preset-fl-0000062-orange-dark-look)<br>`fl-0000062-orange-dark-look` | 暖色 · 中灰近原值 · 中段拉开 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC0-1.0 |
| 424 | [创意色彩 · Protect Highlights 01｜中性 · 提亮中灰 · 中段收窄](look-profiles/401-500.md#preset-fl-0000064-protect-highlights-01)<br>`fl-0000064-protect-highlights-01` | 中性 · 提亮中灰 · 中段收窄 | 产品、生活与风景对照试片 | 0.35–0.8 | CC0-1.0 |
| 425 | [创意色彩 · Red Afternoon 01｜暖色 · 压暗中灰 · 中段跨度接近原值](look-profiles/401-500.md#preset-fl-0000065-red-afternoon-01)<br>`fl-0000065-red-afternoon-01` | 暖色 · 压暗中灰 · 中段跨度接近原值 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC0-1.0 |
| 426 | [创意色彩 · Red Day 01｜暖色 · 压暗中灰 · 中段跨度接近原值](look-profiles/401-500.md#preset-fl-0000066-red-day-01)<br>`fl-0000066-red-day-01` | 暖色 · 压暗中灰 · 中段跨度接近原值 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC0-1.0 |
| 427 | [创意色彩 · Red Dream 01｜暖色 · 压暗中灰 · 中段拉开](look-profiles/401-500.md#preset-fl-0000067-red-dream-01)<br>`fl-0000067-red-dream-01` | 暖色 · 压暗中灰 · 中段拉开 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC0-1.0 |
| 428 | [创意色彩 · Retro Brown 01｜暖色 · 提亮中灰 · 中段跨度接近原值](look-profiles/401-500.md#preset-fl-0000068-retro-brown-01)<br>`fl-0000068-retro-brown-01` | 暖色 · 提亮中灰 · 中段跨度接近原值 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC0-1.0 |
| 429 | [电影色彩 · Saturated Blue｜暖色 · 提亮中灰 · 中段收窄](look-profiles/401-500.md#preset-fl-0000071-saturated-blue)<br>`fl-0000071-saturated-blue` | 暖色 · 提亮中灰 · 中段收窄 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC0-1.0 |
| 430 | [创意色彩 · Smart Contrast｜中性 · 中灰近原值 · 中段拉开](look-profiles/401-500.md#preset-fl-0000072-smart-contrast)<br>`fl-0000072-smart-contrast` | 中性 · 中灰近原值 · 中段拉开 | 产品、生活与风景对照试片 | 0.35–0.8 | CC0-1.0 |
| 431 | [创意色彩 · Subtle green｜中性 · 压暗中灰 · 中段拉开](look-profiles/401-500.md#preset-fl-0000073-subtle-green)<br>`fl-0000073-subtle-green` | 中性 · 压暗中灰 · 中段拉开 | 产品、生活与风景对照试片 | 0.35–0.8 | CC0-1.0 |
| 432 | [创意色彩 · Subtle Blue｜冷色 · 压暗中灰 · 中段跨度接近原值](look-profiles/401-500.md#preset-fl-0000074-subtle-blue)<br>`fl-0000074-subtle-blue` | 冷色 · 压暗中灰 · 中段跨度接近原值 | 冷色城市、夜景与科技试片 | 0.35–0.8 | CC0-1.0 |
| 433 | [创意色彩 · Low key 01｜暖色 · 压暗中灰 · 中段收窄](look-profiles/401-500.md#preset-fl-0000075-low-key-01)<br>`fl-0000075-low-key-01` | 暖色 · 压暗中灰 · 中段收窄 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC0-1.0 |
| 434 | [电影色彩 · Yellow 55B｜暖色 · 压暗中灰 · 中段跨度接近原值](look-profiles/401-500.md#preset-fl-0000076-yellow-55b)<br>`fl-0000076-yellow-55b` | 暖色 · 压暗中灰 · 中段跨度接近原值 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC0-1.0 |
| 435 | [电影色彩 · Yellow Film 01｜中性 · 压暗中灰 · 中段拉开](look-profiles/401-500.md#preset-fl-0000077-yellow-film-01)<br>`fl-0000077-yellow-film-01` | 中性 · 压暗中灰 · 中段拉开 | 产品、生活与风景对照试片 | 0.35–0.8 | CC0-1.0 |
| 436 | [创意色彩 · Bozen｜冷色 · 提亮中灰 · 中段拉开](look-profiles/401-500.md#preset-fl-0000106-bozen)<br>`fl-0000106-bozen` | 冷色 · 提亮中灰 · 中段拉开 | 冷色城市、夜景与科技试片 | 0.35–0.8 | CC0-1.0 |
| 437 | [创意色彩 · powerful cold｜暖色 · 压暗中灰 · 中段拉开](look-profiles/401-500.md#preset-fl-0000107-powerful-cold)<br>`fl-0000107-powerful-cold` | 暖色 · 压暗中灰 · 中段拉开 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC0-1.0 |
| 438 | [创意色彩 · Our Home_Green Sequence｜冷色 · 提亮中灰 · 中段拉开](look-profiles/401-500.md#preset-fl-0000130-our-home-green-sequence)<br>`fl-0000130-our-home-green-sequence` | 冷色 · 提亮中灰 · 中段拉开 | 冷色城市、夜景与科技试片 | 0.35–0.8 | CC0-1.0 |
| 439 | [创意色彩 · SONY LOW LIGHT URBAN｜冷色 · 压暗中灰 · 中段收窄](look-profiles/401-500.md#preset-fl-0000148-sony-low-light-urban)<br>`fl-0000148-sony-low-light-urban` | 冷色 · 压暗中灰 · 中段收窄 | 冷色城市、夜景与科技试片 | 0.35–0.8 | CC0-1.0 |
| 440 | [创意色彩 · GOLDEN FEVE3R｜暖色 · 压暗中灰 · 中段拉开](look-profiles/401-500.md#preset-fl-0000149-golden-feve3r)<br>`fl-0000149-golden-feve3r` | 暖色 · 压暗中灰 · 中段拉开 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC0-1.0 |
| 441 | [创意色彩 · REST SONY A7S2｜暖色 · 提亮中灰 · 中段拉开](look-profiles/401-500.md#preset-fl-0000152-rest-sony-a7s2)<br>`fl-0000152-rest-sony-a7s2` | 暖色 · 提亮中灰 · 中段拉开 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC0-1.0 |
| 442 | [创意色彩 · GREEN VINTAGE｜暖色 · 压暗中灰 · 中段跨度接近原值](look-profiles/401-500.md#preset-fl-0000153-green-vintage)<br>`fl-0000153-green-vintage` | 暖色 · 压暗中灰 · 中段跨度接近原值 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC0-1.0 |
| 443 | [创意色彩 · MORNING CONTRAST｜中性 · 提亮中灰 · 中段拉开](look-profiles/401-500.md#preset-fl-0000154-morning-contrast)<br>`fl-0000154-morning-contrast` | 中性 · 提亮中灰 · 中段拉开 | 产品、生活与风景对照试片 | 0.35–0.8 | CC0-1.0 |
| 444 | [创意色彩 · DROP GREEN ON IT｜冷色 · 压暗中灰 · 中段拉开](look-profiles/401-500.md#preset-fl-0000155-drop-green-on-it)<br>`fl-0000155-drop-green-on-it` | 冷色 · 压暗中灰 · 中段拉开 | 冷色城市、夜景与科技试片 | 0.35–0.8 | CC0-1.0 |
| 445 | [创意色彩 · MORROCO｜中性 · 压暗中灰 · 中段跨度接近原值](look-profiles/401-500.md#preset-fl-0000156-morroco)<br>`fl-0000156-morroco` | 中性 · 压暗中灰 · 中段跨度接近原值 | 产品、生活与风景对照试片 | 0.35–0.8 | CC0-1.0 |
| 446 | [创意色彩 · WOODEN GOLD｜暖色 · 提亮中灰 · 中段拉开](look-profiles/401-500.md#preset-fl-0000157-wooden-gold)<br>`fl-0000157-wooden-gold` | 暖色 · 提亮中灰 · 中段拉开 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC0-1.0 |
| 447 | [创意色彩 · DESERT GOLD｜暖色 · 压暗中灰 · 中段跨度接近原值](look-profiles/401-500.md#preset-fl-0000158-desert-gold)<br>`fl-0000158-desert-gold` | 暖色 · 压暗中灰 · 中段跨度接近原值 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC0-1.0 |
| 448 | [电影色彩 · ELEGANCE SONY ALPHA SERIES｜暖色 · 压暗中灰 · 中段跨度接近原值](look-profiles/401-500.md#preset-fl-0000159-elegance-sony-alpha-series)<br>`fl-0000159-elegance-sony-alpha-series` | 暖色 · 压暗中灰 · 中段跨度接近原值 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC0-1.0 |
| 449 | [创意色彩 · DENOISER SIMPLE｜中性 · 提亮中灰 · 中段跨度接近原值](look-profiles/401-500.md#preset-fl-0000160-denoiser-simple)<br>`fl-0000160-denoiser-simple` | 中性 · 提亮中灰 · 中段跨度接近原值 | 产品、生活与风景对照试片 | 0.35–0.8 | CC0-1.0 |
| 450 | [电影色彩 · SHADOW KING｜冷色 · 压暗中灰 · 中段跨度接近原值](look-profiles/401-500.md#preset-fl-0000163-shadow-king)<br>`fl-0000163-shadow-king` | 冷色 · 压暗中灰 · 中段跨度接近原值 | 冷色城市、夜景与科技试片 | 0.35–0.8 | CC0-1.0 |
| 451 | [创意色彩 · SPY IN THE NIGHT｜冷色 · 压暗中灰 · 中段拉开](look-profiles/401-500.md#preset-fl-0000165-spy-in-the-night)<br>`fl-0000165-spy-in-the-night` | 冷色 · 压暗中灰 · 中段拉开 | 冷色城市、夜景与科技试片 | 0.35–0.8 | CC0-1.0 |
| 452 | [创意色彩 · DIRECTIONS｜暖色 · 压暗中灰 · 中段拉开](look-profiles/401-500.md#preset-fl-0000166-directions)<br>`fl-0000166-directions` | 暖色 · 压暗中灰 · 中段拉开 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC0-1.0 |
| 453 | [创意色彩 · COFFEE｜暖色 · 压暗中灰 · 中段拉开](look-profiles/401-500.md#preset-fl-0000168-coffee)<br>`fl-0000168-coffee` | 暖色 · 压暗中灰 · 中段拉开 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC0-1.0 |
| 454 | [电影色彩 · FIRST DATE｜暖色 · 提亮中灰 · 中段拉开](look-profiles/401-500.md#preset-fl-0000169-first-date)<br>`fl-0000169-first-date` | 暖色 · 提亮中灰 · 中段拉开 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC0-1.0 |
| 455 | [创意色彩 · City Trees｜中性 · 压暗中灰 · 中段收窄](look-profiles/401-500.md#preset-fl-0000179-city-trees)<br>`fl-0000179-city-trees` | 中性 · 压暗中灰 · 中段收窄 | 产品、生活与风景对照试片 | 0.35–0.8 | CC0-1.0 |
| 456 | [创意色彩 · gLUT002｜冷色 · 提亮中灰 · 中段拉开](look-profiles/401-500.md#preset-fl-0000184-glut002)<br>`fl-0000184-glut002` | 冷色 · 提亮中灰 · 中段拉开 | 冷色城市、夜景与科技试片 | 0.35–0.8 | CC0-1.0 |
| 457 | [创意色彩 · gLUT003｜暖色 · 压暗中灰 · 中段拉开](look-profiles/401-500.md#preset-fl-0000186-glut003)<br>`fl-0000186-glut003` | 暖色 · 压暗中灰 · 中段拉开 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC0-1.0 |
| 458 | [创意色彩 · gLUT004｜暖色 · 提亮中灰 · 中段拉开](look-profiles/401-500.md#preset-fl-0000188-glut004)<br>`fl-0000188-glut004` | 暖色 · 提亮中灰 · 中段拉开 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC0-1.0 |
| 459 | [电影色彩 · BLADE RUNNER｜暖色 · 提亮中灰 · 中段拉开](look-profiles/401-500.md#preset-fl-0000210-blade-runner)<br>`fl-0000210-blade-runner` | 暖色 · 提亮中灰 · 中段拉开 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC0-1.0 |
| 460 | [电影色彩 · MONOCHROME 1｜黑白 · 压暗中灰 · 中段拉开](look-profiles/401-500.md#preset-fl-0000211-monochrome-1)<br>`fl-0000211-monochrome-1` | 黑白 · 压暗中灰 · 中段拉开 | 黑白纪实、建筑与轮廓试片 | 1–1 | CC0-1.0 |
| 461 | [电影色彩 · TEAL-ORANGE for Flog｜冷色 · 压暗中灰 · 中段拉开](look-profiles/401-500.md#preset-fl-0000212-teal-orange-for-flog)<br>`fl-0000212-teal-orange-for-flog` | 冷色 · 压暗中灰 · 中段拉开 | 冷色城市、夜景与科技试片 | 0.35–0.8 | CC0-1.0 |
| 462 | [创意色彩 · CINEMA｜冷色 · 压暗中灰 · 中段拉开](look-profiles/401-500.md#preset-fl-0000213-cinema)<br>`fl-0000213-cinema` | 冷色 · 压暗中灰 · 中段拉开 | 冷色城市、夜景与科技试片 | 0.35–0.8 | CC0-1.0 |
| 463 | [创意色彩 · GOLDEN GATE｜中性 · 压暗中灰 · 中段拉开](look-profiles/401-500.md#preset-fl-0000216-golden-gate)<br>`fl-0000216-golden-gate` | 中性 · 压暗中灰 · 中段拉开 | 产品、生活与风景对照试片 | 0.35–0.8 | CC0-1.0 |
| 464 | [创意色彩 · CARIBE｜暖色 · 压暗中灰 · 中段拉开](look-profiles/401-500.md#preset-fl-0000217-caribe)<br>`fl-0000217-caribe` | 暖色 · 压暗中灰 · 中段拉开 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC0-1.0 |
| 465 | [电影色彩 · CINEMA 2｜冷色 · 压暗中灰 · 中段拉开](look-profiles/401-500.md#preset-fl-0000218-cinema-2)<br>`fl-0000218-cinema-2` | 冷色 · 压暗中灰 · 中段拉开 | 冷色城市、夜景与科技试片 | 0.35–0.8 | CC0-1.0 |
| 466 | [电影色彩 · CINEMA 3｜冷色 · 压暗中灰 · 中段拉开](look-profiles/401-500.md#preset-fl-0000219-cinema-3)<br>`fl-0000219-cinema-3` | 冷色 · 压暗中灰 · 中段拉开 | 冷色城市、夜景与科技试片 | 0.35–0.8 | CC0-1.0 |
| 467 | [创意色彩 · CINEMA 4｜暖色 · 压暗中灰 · 中段拉开](look-profiles/401-500.md#preset-fl-0000220-cinema-4)<br>`fl-0000220-cinema-4` | 暖色 · 压暗中灰 · 中段拉开 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC0-1.0 |
| 468 | [电影色彩 · CINEMA 5｜冷色 · 压暗中灰 · 中段拉开](look-profiles/401-500.md#preset-fl-0000221-cinema-5)<br>`fl-0000221-cinema-5` | 冷色 · 压暗中灰 · 中段拉开 | 冷色城市、夜景与科技试片 | 0.35–0.8 | CC0-1.0 |
| 469 | [电影色彩 · CINEMA NOIR｜黑白 · 压暗中灰 · 中段收窄](look-profiles/401-500.md#preset-fl-0000222-cinema-noir)<br>`fl-0000222-cinema-noir` | 黑白 · 压暗中灰 · 中段收窄 | 黑白纪实、建筑与轮廓试片 | 1–1 | CC0-1.0 |
| 470 | [电影色彩 · MATRIX｜冷色 · 压暗中灰 · 中段拉开](look-profiles/401-500.md#preset-fl-0000223-matrix)<br>`fl-0000223-matrix` | 冷色 · 压暗中灰 · 中段拉开 | 冷色城市、夜景与科技试片 | 0.35–0.8 | CC0-1.0 |
| 471 | [创意色彩 · ETERNA for Flog｜中性 · 提亮中灰 · 中段拉开](look-profiles/401-500.md#preset-fl-0000224-eterna-for-flog)<br>`fl-0000224-eterna-for-flog` | 中性 · 提亮中灰 · 中段拉开 | 产品、生活与风景对照试片 | 0.35–0.8 | CC0-1.0 |
| 472 | [创意色彩 · DAY4NITE｜冷色 · 压暗中灰 · 中段拉开](look-profiles/401-500.md#preset-fl-0000225-day4nite)<br>`fl-0000225-day4nite` | 冷色 · 压暗中灰 · 中段拉开 | 冷色城市、夜景与科技试片 | 0.35–0.8 | CC0-1.0 |
| 473 | [创意色彩 · Flog to Rec 709｜中性 · 压暗中灰 · 中段拉开](look-profiles/401-500.md#preset-fl-0000226-flog-to-rec-709)<br>`fl-0000226-flog-to-rec-709` | 中性 · 压暗中灰 · 中段拉开 | 产品、生活与风景对照试片 | 0.35–0.8 | CC0-1.0 |
| 474 | [创意色彩 · OLD WEST｜暖色 · 压暗中灰 · 中段跨度接近原值](look-profiles/401-500.md#preset-fl-0000227-old-west)<br>`fl-0000227-old-west` | 暖色 · 压暗中灰 · 中段跨度接近原值 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC0-1.0 |
| 475 | [电影色彩 · Science Fiction for Flog｜冷色 · 压暗中灰 · 中段拉开](look-profiles/401-500.md#preset-fl-0000228-science-fiction-for-flog)<br>`fl-0000228-science-fiction-for-flog` | 冷色 · 压暗中灰 · 中段拉开 | 冷色城市、夜景与科技试片 | 0.35–0.8 | CC0-1.0 |
| 476 | [创意色彩 · The Bubble is Pink｜冷色 · 提亮中灰 · 中段跨度接近原值](look-profiles/401-500.md#preset-fl-0000261-the-bubble-is-pink)<br>`fl-0000261-the-bubble-is-pink` | 冷色 · 提亮中灰 · 中段跨度接近原值 | 冷色城市、夜景与科技试片 | 0.35–0.8 | CC0-1.0 |
| 477 | [创意色彩 · soft Teal and Orange look｜暖色 · 压暗中灰 · 中段收窄](look-profiles/401-500.md#preset-fl-0000264-soft-teal-and-orange-look)<br>`fl-0000264-soft-teal-and-orange-look` | 暖色 · 压暗中灰 · 中段收窄 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC0-1.0 |
| 478 | [电影色彩 · Grungy Cinematic Teal｜暖色 · 压暗中灰 · 中段跨度接近原值](look-profiles/401-500.md#preset-fl-0000265-grungy-cinematic-teal)<br>`fl-0000265-grungy-cinematic-teal` | 暖色 · 压暗中灰 · 中段跨度接近原值 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC0-1.0 |
| 479 | [创意色彩 · Dusty Orange｜暖色 · 压暗中灰 · 中段跨度接近原值](look-profiles/401-500.md#preset-fl-0000266-dusty-orange)<br>`fl-0000266-dusty-orange` | 暖色 · 压暗中灰 · 中段跨度接近原值 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC0-1.0 |
| 480 | [创意色彩 · Canon Look｜中性 · 压暗中灰 · 中段拉开](look-profiles/401-500.md#preset-fl-0000267-canon-look)<br>`fl-0000267-canon-look` | 中性 · 压暗中灰 · 中段拉开 | 产品、生活与风景对照试片 | 0.35–0.8 | CC0-1.0 |
| 481 | [创意色彩 · Storm｜中性 · 压暗中灰 · 中段收窄](look-profiles/401-500.md#preset-fl-0000268-storm)<br>`fl-0000268-storm` | 中性 · 压暗中灰 · 中段收窄 | 产品、生活与风景对照试片 | 0.35–0.8 | CC0-1.0 |
| 482 | [电影色彩 · Cinematic for Flog｜中性 · 压暗中灰 · 中段拉开](look-profiles/401-500.md#preset-fl-0000269-cinematic-for-flog)<br>`fl-0000269-cinematic-for-flog` | 中性 · 压暗中灰 · 中段拉开 | 产品、生活与风景对照试片 | 0.35–0.8 | CC0-1.0 |
| 483 | [创意色彩 · Abraham_Braun_Orange｜中性 · 提亮中灰 · 中段拉开](look-profiles/401-500.md#preset-fl-0000270-abraham-braun-orange)<br>`fl-0000270-abraham-braun-orange` | 中性 · 提亮中灰 · 中段拉开 | 产品、生活与风景对照试片 | 0.35–0.8 | CC0-1.0 |
| 484 | [电影色彩 · cinematic  green｜暖色 · 压暗中灰 · 中段跨度接近原值](look-profiles/401-500.md#preset-fl-0000276-cinematic-green)<br>`fl-0000276-cinematic-green` | 暖色 · 压暗中灰 · 中段跨度接近原值 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC0-1.0 |
| 485 | [电影色彩 · Wonder Woman Look (New Version Lut Update https://freshluts.com/luts/285)｜冷色 · 压暗中灰 · 中段跨度接近原值](look-profiles/401-500.md#preset-fl-0000282-wonder-woman-look-new-version-lut-update-httpsfreshlutscomlu)<br>`fl-0000282-wonder-woman-look-new-version-lut-update-httpsfreshlutscomlu` | 冷色 · 压暗中灰 · 中段跨度接近原值 | 冷色城市、夜景与科技试片 | 0.35–0.8 | CC0-1.0 |
| 486 | [电影色彩 · TEAL LOOK FOR REC 709 V2｜冷色 · 压暗中灰 · 中段跨度接近原值](look-profiles/401-500.md#preset-fl-0000285-teal-look-for-rec-709-v2)<br>`fl-0000285-teal-look-for-rec-709-v2` | 冷色 · 压暗中灰 · 中段跨度接近原值 | 冷色城市、夜景与科技试片 | 0.35–0.8 | CC0-1.0 |
| 487 | [创意色彩 · BlueCine｜冷色 · 提亮中灰 · 中段拉开](look-profiles/401-500.md#preset-fl-0000291-bluecine)<br>`fl-0000291-bluecine` | 冷色 · 提亮中灰 · 中段拉开 | 冷色城市、夜景与科技试片 | 0.35–0.8 | CC0-1.0 |
| 488 | [创意色彩 · RedMood｜冷色 · 提亮中灰 · 中段拉开](look-profiles/401-500.md#preset-fl-0000292-redmood)<br>`fl-0000292-redmood` | 冷色 · 提亮中灰 · 中段拉开 | 冷色城市、夜景与科技试片 | 0.35–0.8 | CC0-1.0 |
| 489 | [创意色彩 · Crizo Mzeyah｜中性 · 中灰近原值 · 中段拉开](look-profiles/401-500.md#preset-fl-0000296-crizo-mzeyah)<br>`fl-0000296-crizo-mzeyah` | 中性 · 中灰近原值 · 中段拉开 | 产品、生活与风景对照试片 | 0.35–0.8 | CC0-1.0 |
| 490 | [创意色彩 · moody 1｜冷色 · 压暗中灰 · 中段收窄](look-profiles/401-500.md#preset-fl-0000335-moody-1)<br>`fl-0000335-moody-1` | 冷色 · 压暗中灰 · 中段收窄 | 冷色城市、夜景与科技试片 | 0.35–0.8 | CC0-1.0 |
| 491 | [创意色彩 · Retro Red｜冷色 · 压暗中灰 · 中段跨度接近原值](look-profiles/401-500.md#preset-fl-0000336-retro-red)<br>`fl-0000336-retro-red` | 冷色 · 压暗中灰 · 中段跨度接近原值 | 冷色城市、夜景与科技试片 | 0.35–0.8 | CC0-1.0 |
| 492 | [创意色彩 · Pirabook Horror Movie｜暖色 · 中灰近原值 · 中段跨度接近原值](look-profiles/401-500.md#preset-fl-0000338-pirabook-horror-movie)<br>`fl-0000338-pirabook-horror-movie` | 暖色 · 中灰近原值 · 中段跨度接近原值 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC0-1.0 |
| 493 | [创意色彩 · Night Glow (Enhanced Blues)｜冷色 · 提亮中灰 · 中段拉开](look-profiles/401-500.md#preset-fl-0000357-night-glow-enhanced-blues)<br>`fl-0000357-night-glow-enhanced-blues` | 冷色 · 提亮中灰 · 中段拉开 | 冷色城市、夜景与科技试片 | 0.35–0.8 | CC0-1.0 |
| 494 | [创意色彩 · Nikon Z6 contrast based on FLAT-Profile｜中性 · 提亮中灰 · 中段拉开](look-profiles/401-500.md#preset-fl-0000359-nikon-z6-contrast-based-on-flat-profile)<br>`fl-0000359-nikon-z6-contrast-based-on-flat-profile` | 中性 · 提亮中灰 · 中段拉开 | 产品、生活与风景对照试片 | 0.35–0.8 | CC0-1.0 |
| 495 | [创意色彩 · @crizomzeyahke｜冷色 · 提亮中灰 · 中段拉开](look-profiles/401-500.md#preset-fl-0000539-crizomzeyahke)<br>`fl-0000539-crizomzeyahke` | 冷色 · 提亮中灰 · 中段拉开 | 冷色城市、夜景与科技试片 | 0.35–0.8 | CC0-1.0 |
| 496 | [创意色彩 · ROYALS｜暖色 · 提亮中灰 · 中段拉开](look-profiles/401-500.md#preset-fl-0000596-royals)<br>`fl-0000596-royals` | 暖色 · 提亮中灰 · 中段拉开 | 暖色生活、餐饮与怀旧试片 | 0.35–0.8 | CC0-1.0 |
| 497 | [创意色彩 · TIL｜冷色 · 中灰近原值 · 中段跨度接近原值](look-profiles/401-500.md#preset-fl-0000624-til)<br>`fl-0000624-til` | 冷色 · 中灰近原值 · 中段跨度接近原值 | 冷色城市、夜景与科技试片 | 0.35–0.8 | CC0-1.0 |
| 498 | [创意色彩 · COOL.GREEN｜冷色 · 中灰近原值 · 中段跨度接近原值](look-profiles/401-500.md#preset-fl-0000627-coolgreen)<br>`fl-0000627-coolgreen` | 冷色 · 中灰近原值 · 中段跨度接近原值 | 冷色城市、夜景与科技试片 | 0.35–0.8 | CC0-1.0 |
| 499 | [创意色彩 · BLACK&WHITE｜黑白 · 压暗中灰 · 中段拉开](look-profiles/401-500.md#preset-fl-0000629-blackwhite)<br>`fl-0000629-blackwhite` | 黑白 · 压暗中灰 · 中段拉开 | 黑白纪实、建筑与轮廓试片 | 1–1 | CC0-1.0 |
| 500 | [创意色彩 · DARK.BLUE｜冷色 · 中灰近原值 · 中段跨度接近原值](look-profiles/401-500.md#preset-fl-0000634-darkblue)<br>`fl-0000634-darkblue` | 冷色 · 中灰近原值 · 中段跨度接近原值 | 冷色城市、夜景与科技试片 | 0.35–0.8 | CC0-1.0 |
