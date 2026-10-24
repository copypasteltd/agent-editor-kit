"""Report actual semantic queries, native timings and editable media without hiding failures."""
from pathlib import Path
import array,json,subprocess
from verify_semantic_20261025 import ROOT,sha,save

BASE=ROOT/'docs/validation/evidence/semantic-20261025-r1'


def load(name):return json.loads((BASE/name).read_bytes())


def main():
    target=ROOT/'docs/validation/离线语义检索实测_2026-10-25.md'
    assert not target.exists()
    source=load('development-r1/queries/quality.json');skill=load('skill-r1/quality.json')
    assert load('skill-r1/verification.json')['status']=='passed-with-quality-limits'
    installed=load('installed-r1/demo/verification.json');demo=installed['demonstration']
    assert installed['status']=='passed' and demo['package_roundtrip_decoded_pixels_equal']
    media=ROOT/'docs/assets/semantic-20261025-r1/demo-installed-r1-workflow/semantic-cut.mp4'
    command=['ffmpeg','-nostdin','-v','error','-i',str(media),'-map','0:a:0','-f','s16le','-acodec','pcm_s16le','-']
    decoded=subprocess.run(command,capture_output=True,timeout=120)
    assert decoded.returncode==0,decoded.stderr
    samples=array.array('h');samples.frombytes(decoded.stdout)
    peak=max(map(abs,samples),default=0)
    sound=dict(status='decoded',command=command,exit_code=decoded.returncode,media_sha256=sha(media),
        decoded_s16_values=len(samples),decoded_peak_abs=peak,silent_pcm=peak==0,human_listening=False,
        interpretation='The renderer adds an audio stream; actual decoded PCM is checked, no content-quality listening claim.')
    save(BASE/'installed-demo-audio.json',sound)
    tests=[]
    for name,label in [('contract-tests-r2.json','开发契约 / development'),('installed-contract-tests-r1.json','安装版契约 / installed'),
                       ('cli-regression-r1.json','开发 CLI 回归'),('offline-regression-r1.json','开发离线策略回归')]:
        record=load(name)
        assert record['exit_code']==0 and record['terminal_ok'] and record['frozen_equal']
        tests.append(f'| {label} | {record["methods"]} / {record["skipped"]} skipped | {record["suite_seconds"]:.3f}s | [原始记录](evidence/semantic-20261025-r1/{name}) |')
    timings=[];forward_total=0
    for phase,label,numbers in [('development-r1/index','开发图像索引',[1]),
        ('development-r1/queries','开发 GPU/CPU 文本、视频与参考图',[1,2,3,4,5]),
        ('installed-r1/index','安装版 GPU 图像索引',[1]),('skill-r1','真实 Skill GPU 文本 / CPU 参考图',[8,9])]:
        calls=load(phase+'/calls.json')
        for number in numbers:
            response=load(phase+f'/{number:02}.stdout.json')['data']['inference']['response']
            forward_total+=response['model_forward_calls']
            timings.append(f'| {label} #{number} | {response["task"]} / {response["device"]} / {response["model_dtype"]} | '
                f'{calls[number-1]["elapsed_seconds"]:.3f} / {response["elapsed_seconds"]:.3f} / {response["load_seconds"]:.3f} / '
                f'{response["inference_seconds"]:.3f} | {response["model_forward_calls"]} | {response.get("peak_cuda_allocated_bytes",0)} |')
    query_rows=[]
    cpu={r['id']:r for r in source['cpu']['queries']};installed_queries={r['id']:r for r in skill['queries']}
    def describe(row):
        hit=row['top_hits'][0] if row['top_hits'] else None
        name=(hit['asset_id']+' @ '+str(hit['sample_seconds'])+'s') if hit else 'none'
        status=('正确' if row['top1_relevant'] else '错选') if row['top1_relevant'] is not None else ('仍返回候选' if hit else '无候选')
        return name+' / '+status
    for row in source['queries']:
        query_rows.append('| '+row['id']+' | '+row['group']+' | '+row['text'].replace('|','\\|')+' | '+
            describe(row)+' | '+describe(cpu[row['id']])+' | '+describe(installed_queries[row['id']])+' |')
    install=load('installation/verification.json');cancel=load('inflight-development-r1/verification.json')
    text='''# 离线图文语义检索：真实执行与边界（2026-10-25）

[README](../../README.md) · [使用流程](../product/SEMANTIC_RETRIEVAL.md) · [G01–G38](../product/GOAL_GAPS_20261025.md) · [原始证据](evidence/semantic-20261025-r1)

本轮交付 CLI **0.1.5 / v0.1.0-alpha.4-local.3** 的有限图文向量检索，接入同一个
`$agent-ffmpeg-local-editor` / 17 内部模块。产品、真实相关性、固定安装、Skill 和
可编辑片段链路分别核验；不以命令或通过测试数量宣称完整 G26/剪映等价。
全部 G01–G38 保留原范围和未关闭条件。公开版本仍为 alpha.3 / CLI 0.1.2。

## 预先冻结的样本与门槛

冻结集 SHA-256 `72bad6009500eddc9e34e4ff55e968c8b2ae56344cf382df110ab04c78f4023e`，
[truth.json](evidence/semantic-20261025-r1/benchmark-frozen/truth.json) 在首次预测前保存。
八类已有自然静态图、误导文件名的猫图重复、裁剪猫参考图，以及咖啡/猫/宇航员
组成的 6 秒/72 帧/12fps 序列；10 个源素材形成 15 条记录、14 张唯一编码图像。
这些常见公开图片可能出现在训练集中，不作为未见训练分布或自然动作证据。

20 条查询包括 16 条中英正向、2 条否定、2 条库外鲨鱼。请求只含 id/text，
文件名/人工答案/相关性标签不送入模型。冻结门槛：正向 top-1≥0.75、mean asset
recall@3≥0.90，前六条视频时间点正确率≥0.80，参考图、同图改名向量逐位一致、
查询不改工程/权利台账。八项冻结门禁均通过，未将否定/库外失败删除或改标签。

## 编号执行记录

| 编号 | 实际执行 | 结果与限制 |
|---|---|---|
| V01 | 开发版 13 次准备命令 | 登记本地模型/许可和素材，不做模型前向；不能证明相关性 |
| V02 | 开发版 GPU 建索引＋verify 2 次 CLI | 真实 CUDA BF16，两次图像前向；15 行/10 源/14 唯一图 |
| V03 | 开发版 5 次检索 CLI / 11 次前向 | GPU 文本、视频时间点、参考图，CPU 文本和参考图；正向质量通过，失败见完整表 |
| V04 | 8 次实际异常 CLI | 重复 index、预取消、文本过长、GPU 31 不存在、向量/源/清单篡改均拒绝，恢复后 verify 通过 |
| V05 | 启动后取消实际存活 worker | Windows 进程句柄及父子关系核验，子进程退出、工程未改；不声称 CUDA 内核或宿主哈希取消延迟通过 |
| V06 | 原生离线安装 8 wheel / 47 文件 | 全部产品 Python 与安装字节摘要相同，无源码回退；同一物理主机 |
| V07 | 安装版 13 次准备及 2 次索引 CLI | 独立登记、真实 GPU 图像索引和 verify；NumPy/Pillow 版本与开发路径分别固定 |
| V08 | 真实 Codex 统一入口 9 次 CLI | 7 次能力/清单核对、20 条 auto→CUDA 文本、CPU 参考图；4 门禁通过，工程/权利未改 |
| V09 | 开发版 11 次 CLI，可编辑案例 | 3 秒/90 帧，实际渲染/质检/包往返/重渲染像素相同；原版标题位于顶部，输出保留 |
| V10 | 安装版另 11 次 CLI，可编辑案例 | 实际 Skill 混合检索中选首个视频候选，保留总体原排名；底部标题，3 秒/90 帧，往返像素相同 |
| V11 | r4 kit 新中文/空格目录 | ZIP 全文件摘要、独立配置、隔离注册与实际安装版入口/索引校验；见 kit receipt，不改真实 Codex 联接 |

开发 GPU/CPU 正向 16/16 首选，mean asset recall@3 均 1.0；六个序列时间点全对。
实际安装 Skill 的同一 16 条正向亦为 1.0；CPU 裁剪猫参考图首选正确。
这些范围有覆盖重叠，不能累加为独立功能完成数。

## 全部查询：包含失败

| ID | 分组 | 原始查询 | 开发 GPU 首选 | 开发 CPU 首选 | 安装 Skill GPU 首选 |
|---|---|---|---|---|---|
'''+ '\n'.join(query_rows)+'''

![All queries including negative/OOD failures](../assets/semantic-20261025-r1/all-query-results.png)

完整排名/分数：[开发 GPU/CPU](evidence/semantic-20261025-r1/development-r1/queries/quality.json) ·
[实际 Skill](evidence/semantic-20261025-r1/skill-r1/quality.json)。中文否定错选咖啡；
英文否定通过；两条库外查询均返回草地。本产品尚无校准的自动拒识，cosine 不是
概率。低分阈值只能显式筛选，不能宣称可靠 no-match。

## 契约与回归（分别统计）

| 范围 | 方法数 / 跳过数 | suite 时间 | 原始证据 |
|---|---|---|---|
'''+ '\n'.join(tests)+'''

契约包含模拟向量的完整性/失败测试，相关性只依据上述真实模型结果。首轮契约
24 项有 2 个失败，已保留 [原日志](evidence/semantic-20261025-r1/contract-tests-r1.log)；
随后修正采样浮点/Fraction 及“外部原件已复制入库”的测试前提，再冻结 25 项通过。
既有 2,930 项历史回归本轮未重新执行。当前产品代码在上述测试/推理阶段冻结。

## 原生 GPU/CPU 性能与模型复用

CPython 3.13.14，Torch 2.13.0+cu130，Transformers 5.14.1，RTX 3060 12GB。
开发 NumPy/Pillow 2.4.6/12.3.0；安装版为 2.4.2/12.1.0。没有启动 ComfyUI 服务。
模型仅在同一 worker 的一批内复用；每个新命令重新完整性核验/载入，不能说实时。
以下是各阶段的实际一次执行，未用重复跑分挑最快值。

| 范围/调用号 | 任务/设备/dtype | CLI / worker / load / inference 秒 | 前向次数 | CUDA allocated peak bytes |
|---|---|---|---|---|'''+ '\n'+ '\n'.join(timings)+f'''

上述实际前向共 {forward_total} 次；登记、verify、渲染和模拟测试不算模型前向。
取消响应 {cancel['cancel_ack_seconds']:.6f}s 仅是 marker 创建后 CLI 确认至退出，
不是完整任务延迟；找到实际 worker 之前等待约 {cancel['seconds_to_worker']:.3f}s。
大型模型/原生库哈希、进程冷启动和模型加载成本明显，常驻复用与大库仍属于 G32。

## 真实可编辑案例与声音范围

![Actual installed editable cut](../assets/semantic-20261025-r1/demo-installed-r1-workflow/semantic-cut.gif)

[输入序列](../assets/semantic-20261025-r1/asset_v1.mp4) ·
[安装输出 MP4](../assets/semantic-20261025-r1/demo-installed-r1-workflow/semantic-cut.mp4) ·
[候选/输出板](../assets/semantic-20261025-r1/demo-installed-r1-workflow/candidate-to-output.png) ·
[可编辑工程包](../assets/semantic-20261025-r1/demo-installed-r1-workflow/editable-project.aevpkg.zip) ·
[选择/排名/源点](../assets/semantic-20261025-r1/demo-installed-r1-workflow/selected-hits.json)。

每段显式写作 1 秒，没有推断完整动作长度。3 秒、640×360、30fps/90 帧，
输出与包导入后重渲染的逐帧解码相同。渲染器添加了音频流，实解 PCM 有
{len(samples)} 个 s16 值、绝对峰值 {peak}；silent_pcm={peak==0}，
[声音检查](evidence/semantic-20261025-r1/installed-demo-audio.json)。无配音/音乐内容或人类听审结论。
静态 Agent 查看与连续人类播放分别记录，不以 GIF 或解码替代人工接受。

## 安装、Skill 与许可

基础 ZIP {install['archive_bytes']:,} 字节，SHA-256 `{install['archive_sha256']}`；
manifest `sha256:{install['manifest_sha256']}`。
单一 Skill 仅指向固定安装版；[交付流程](../product/COMMUNITY_LOCAL_DELIVERY.md)、
[注册与索引证据](evidence/semantic-20261025-r1/skill-r1/verification.json)、
[r4 kit 核验](evidence/semantic-20261025-r1/kit-r1/verification.json)。

SigLIP2 模型权重 1,500,800,904 字节，SHA-256
`612923381c76ec5a9bed335d1c48827e3f2e506ac31b044b63b2031fadee6a0b`。
[官方模型说明](https://huggingface.co/google/siglip2-base-patch16-224)标为 Apache-2.0。
本轮获取的镜像 snapshot/配置/许可证据和所有失败响应保留于
[来源](../../sources/semantic-20261025)与[获取记录](evidence/semantic-20261025-r1/acquisition)。
输入图片逐项 CC0/NASA 依据与 scikit-image 原始说明保留于
[SOURCE](../assets/semantic-20261025-r1/SOURCE.json)、[NOTICE](../assets/semantic-20261025-r1/NOTICE.txt)及
[原始归属文件](../../sources/semantic-20261025/scikit-image-provenance)。
NASA 画面不表示背书或人物权利已清除；工程 render --publish 未执行。
NVIDIA 驱动/CUDA 并非全部开源底层依赖，G37 范围问题继续保留。

## 仍未完成

可靠否定/关系、无匹配拒绝、自然运动/事件边界、跨镜头人物身份、音频 embedding、
配乐与音效推荐、大库/长片/冷启动、跨命令模型常驻、另一台干净物理主机与独立
Agent 成功率。本轮不关闭 G26/G27/G32/G34/G35/G36 或其他原目标组。
全部执行使用原生 Windows；无 Docker/WSL/虚拟环境，也未开启浏览器 UI。
'''
    target.write_text(text,encoding='utf8',newline='\n')
    save(BASE/'report-generation.json',dict(status='generated',report=str(target.relative_to(ROOT)),
        report_sha256=sha(target),actual_model_forward_calls=forward_total,generator_sha256=sha(Path(__file__))))
    print(json.dumps(dict(status='report_generated',forward_calls=forward_total,pcm_peak=peak)),flush=True)


if __name__=='__main__':main()
