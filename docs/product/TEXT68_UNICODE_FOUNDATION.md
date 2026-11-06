# 文字基础独立开发批：Unicode 17、原文位置与逐字时钟

2026-11-06，Asia/Taipei。`text68`是下一批文字内核的独立开发目录名，**没有把正式CLI升级为0.1.68**。正式入口仍为CLI0.1.66／local64／r59；CLI67的原始验收进程继续运行。本批文件位于`development/text68/`，未改当前冻结产品、安装包、唯一Skill及其95文件。

本批实际补齐的是字幕渲染的基础计算层。现有`text_layout.py`仅处理常见组合符号、肤色和ZWJ，不能完整识别国旗、Hangul、Prepend或印度文字连接；以空格优先的折行也没有完整Unicode换行规则。现在独立候选提供固定Unicode 17数据、完整默认分字／换行规则和原文位置映射，供后续渲染接入；它尚未改变客户当前生成的视频。

## 本轮实际实现与证据

| 编号 | 实现事项 | 具体行为与限制 |
| --- | --- | --- |
| C01 | 固定Unicode 17数据 | 分字属性、Indic连接、扩展象形符、换行属性、一般类别、东亚宽度、双向类别共7表；178,367字节，加载时核对摘要。不会随主机Python的Unicode版本改变 |
| C02 | 完整默认扩展字素簇 | 保留国旗对、ZWJ职业表情／肤色、组合音标、Hangul、Prepend及Indic连接；返回原文`start/end/text`，不做文字归一化 |
| C03 | 默认换行与安全折行 | 区分软换行、强制换行与结尾；默认UAX14和保留完整字素的交集策略分别提供。CJK标点、NBSP／NNBSP、word joiner及CRLF均有覆盖 |
| C04 | 无损原文范围 | 每行`start:end`连续保留原文、空格和换行符；显示范围另列。仅可按明确选项去掉行尾ASCII空格／TAB，不会把NBSP误删 |
| C05 | 全文塑形度量接口 | 调用方必须提供完整候选字符串的真实宽度计算；不使用平均字符宽度回退。逐一考虑合法候选，允许塑形宽度非单调；不可拆单元过宽时明确标记或拒绝 |
| C06 | 字符位置与段落方向 | Unicode scalar和UTF-16位置双向换算，拒绝切开代理对；提供考虑嵌套isolate的首段P2/P3基方向。**没有实现完整双向重排或视觉字形选区** |
| C07 | 精确逐字时间计划 | 使用整型创作时钟及有理帧率计算完整字素的出现帧，同帧合并为最长完整前缀；包含30000/1001及大时钟检查。输出逻辑事件，不自行绘制字形 |
| C08 | 明确预算与失败行为 | 最多16,384码点／4,096字素／512行／32,768次塑形度量；拒绝孤立代理、无效数字、非法位置和超预算；返回稳定错误码，不输出静默截断版 |

整批实现、15项接口用例、官方语料核对程序和数据生成程序先写齐，再[冻结全部输入](../validation/evidence/text68-20261106-r1/freeze-r1/verification.json)，之后集中测试。**源码CLI67的554项产品／用例／依赖、6项工具／说明和69项构建来源在前后检查中均保持冻结摘要一致**。

| 编号 | 本轮实际检查 | 结果 | 证据与适用边界 |
| --- | --- | --- | --- |
| T01 | 公共计算接口契约 | 15项通过，0失败／错误／跳过 | [逐项日志](../validation/evidence/text68-20261106-r1/tests-r1/tests.stderr)。覆盖无损范围、UTF-16边界、非单调宽度、预算、首段方向及独立Fraction时钟oracle；宽度回调为受控夹具 |
| T02 | Unicode 17官方GraphemeBreakTest | 766／766通过，0排除／跳过 | [完整收据](../validation/evidence/text68-20261106-r1/tests-r1/verification.json)。比较文件内每条原始边界，没有删改预期 |
| T03 | Unicode 17官方LineBreakTest | 19,338／19,338通过，0排除／跳过 | 同一收据单独计数。验证默认UAX14规则，不把字素交集、排版、字体或自然阅读质量混入官方计数 |
| T04 | 正式入口与开发批隔离 | 产品67冻结未改；没有安装依赖、模型前向或GPU调用 | 计算层在原生Python隔离模式下运行；不是新增CLI完整回归，也不是已安装Skill的功能验收 |

三组计数分别记录，不与CLI66的4,124项、CLI67的4,154项或人像／交付工具的30／17项相加。官方边界语料通过不能证明字体塑形、图像绘制、RTL高亮、动画版式或剪映等价。

## 接口与开发用法

候选入口为[`aek_unicode17`](../../development/text68/src/aek_unicode17/__init__.py)，核心代码为[`core.py`](../../development/text68/src/aek_unicode17/core.py)。这是直接供后续产品代码调用的库，本批没有新增已注册Skill或正式CLI命令。

```python
from pathlib import Path
import sys
sys.path.insert(0, str(Path('development/text68/src').resolve()))
from aek_unicode17 import graphemes, line_breaks, reveal_plan

clusters = graphemes('A🇹🇼e\u0301👩🏽\u200d💻')
breaks = line_breaks('你好，世界。')
events = reveal_plan(
    'A🇹🇼e\u0301👩🏽\u200d💻',
    start_tick=0, duration_ticks=2000, clock_hz=1000,
    fps_num=30000, fps_den=1001,
)
```

| 接口 | 输入与输出 | 调用约束 |
| --- | --- | --- |
| `graphemes(text)` | 按顺序返回不可拆字素及原文范围 | 范围单位是Unicode scalar／Python码点索引，不是UTF-8字节或UTF-16单元 |
| `line_breaks(text, preserve_graphemes=True)` | 返回`offset/kind`；`False`提供默认UAX14边界 | 默认交集策略不切开字素；空串返回结尾位置0 |
| `wrap_text(text, max_width, measure, overflow='preserve', trim_line_end=True)` | 返回原文、各行原文／显示范围、宽度、溢出与度量次数 | `measure`须为真实全文塑形宽度函数；默认保留不可拆长单元并标记溢出，也可明确选择`reject`。没有词典断词、软连字符插入或字体替代策略 |
| `scalar_to_utf16`／`utf16_to_scalar` | 无损转换合法字符边界 | 拒绝代理对中间位置和越界，不接受布尔值冒充整数 |
| `paragraph_direction(text, default='ltr')` | 取得首段基方向`ltr/rtl` | 只实现P2/P3基础判断；不提供视觉顺序、镜像或字形簇几何 |
| `reveal_plan(...)` | 返回出现帧、原文前缀终点与累计字素数 | 首字素在`start+duration/N`，最后在`start+duration`；向上取整到帧，同帧合并。不改变旧工程逐字时钟语义 |

本机完整核对程序是[`validate_text68.py`](../validation/validate_text68.py)，其额外保护会检查当前CLI67冻结，属于当前工作区的开发验收工具。官方输入由[`prepare_text68_sources.py`](../validation/prepare_text68_sources.py)获取并逐项锁定摘要。独立库自身无网络、第三方Python包、子进程或模型依赖；测试使用原生Python，没有创建虚拟环境。

## 开源复用与来源

算法以MIT许可的[uniseg 0.10.1](https://pypi.org/project/uniseg/0.10.1/)为基础，原实现对应Unicode 16；本批替换为固定Unicode 17全部所需属性，并实现UAX14修订55新增HH及LB12a／LB20a／LB21／LB21a变化。不能把原包未经修改就称为Unicode 17实现。

原始wheel、被复用文件的摘要、数据来源和改动清单见[`SOURCE_MANIFEST.json`](../../development/text68/src/aek_unicode17/SOURCE_MANIFEST.json)；保留[MIT许可](../../development/text68/src/aek_unicode17/LICENSE_UNISEG.txt)与[Unicode许可](../../development/text68/src/aek_unicode17/LICENSE_UNICODE.txt)。[数据／代码准备程序](../validation/build_text68_candidate.py)只在首次构建时写入新的生成文件，不覆盖既有候选，也不执行下载代码或改安装环境。研究HTML保留在本地忽略目录，没有把Unicode附件正文再分发进产品。

规范入口：[UAX29修订47](https://www.unicode.org/reports/tr29/tr29-47.html)、[UAX14修订55](https://www.unicode.org/reports/tr14/tr14-55.html)、[UAX9修订51](https://www.unicode.org/reports/tr9/tr9-51.html)。这里选择固定Unicode 17版本，不宣称它是随时变化的最新版。

## 后续仍待完成

| 编号 | 待完成事项 | 下一步与验收要求 | 原目标 |
| --- | --- | --- | --- |
| P01 | 正式字幕折行与打字机接入 | 原CLI67批终态处理后，写齐版本化排版策略、工程／配方序列化、预览与编码调用；保持旧工程重放语义，再冻结整批测试 | G13／I06 |
| P02 | 词内塑形簇及RTL视觉高亮 | 获取真实塑形后的glyph cluster／双向视觉顺序／几何；覆盖Arabic连接、连字、数字、混排及isolate；不能用逻辑前缀宽度冒充视觉选区 | G13／I06 |
| P03 | 字体、动态版式与标题 | 固定字体及替代声明，补锚点／动画／多画幅／文本变化；全动画逐帧检查换行、边界、安全区及缺字 | G13／I06 |
| P04 | 渲染组合与可移植重放 | 原生／富ASS／Float32、HDR、透明度、效果及多音轨组合；源码与安装版分别完整回归、工程包和异机重放 | G02／G08／G09／G13 |
| P05 | 真实展示与交付 | 用有公开权利的多语字体／文案生成源工程、真实MP4／GIF和完整字幕几何检查；完成同版包、唯一Skill、便携及回滚门槛 | G13／G32—G38 |
| P06 | 当前CLI67人像交付 | 原4,154项源码完整终态→安装整套→实际GPU与故障→配乐／完整音画／便携→正式升级回滚；原进程不重启 | [CLI67门槛](PORTRAIT67_DELIVERY.md) |

本批未生成假字幕演示，也未把逻辑分段结果称为自然视觉质量。完整剩余工作见[逐项展开清单](UNFINISHED_DETAIL_20261106.md)；原G01—G38关闭条件保持。
