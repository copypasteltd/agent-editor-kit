"""Write the relocation report only from completed native evidence."""
from pathlib import Path
import json

ROOT=Path(__file__).resolve().parents[1]
BASE=ROOT/'docs/validation/evidence/semantic-upgrade-20261025-r1'


def load(name):return json.loads((BASE/name).read_bytes())


def link(name,label='原始证据'):return '['+label+'](evidence/semantic-upgrade-20261025-r1/'+name+')'


def main():
    installation=load('installation-r3/verification.json')
    assert installation['status']=='installed-and-byte-verified'
    tests=[]
    for name,count in (('development-r6',122),('installed-contracts-r3',122),('installed-cli-r3',122)):
        value=load('tests/'+name+'/verification.json')
        assert value['status']=='passed' and value['result']==dict(methods=count,skipped=0,failures=0,errors=0,success=True)
        tests.append((name,count))
    for phase in ('setup-r2','upgrade-r2','roundtrip-r2','faults-r3','kit-r1'):
        assert load(phase+'/verification.json')['status']=='passed'
    assert load('before-cuda-r1/verification.json')['status']=='failed'
    queries=[]
    for phase in ('before-cpu','before-cuda','after-cpu','after-cuda','skill-cuda'):
        value=load(phase+'-r2/verification.json')
        assert value['status']=='passed-with-known-quality-errors'
        queries.append((phase,value))
    faults=load('faults-r3/verification.json')
    upgrade=load('upgrade-r2/verification.json');package=load('roundtrip-r2/verification.json')
    response=load('upgrade-r2/upgrade.stdout.json')['data']
    text='''# 语义运行时升级实测（2026-10-25）

CLI **0.1.15 / alpha.4-local.13 / r14 kit** 已安装，唯一入口 `$agent-ffmpeg-local-editor`、17 内部模块。
本批修复旧安装绝对路径绑定及随应用安装的 NumPy/Pillow 模块路径；相同字节实现/依赖可显式迁移，不重复图文嵌入。
这是 G31/G34 的子项交付，全部 G01–G38 原关闭条件保持，总目标继续进行。

[完整使用流程](../product/SEMANTIC_RUNTIME_UPGRADE.md) · [契约](../specs/语义工程运行时升级契约_20261025.md) · [案例 C24](../product/CASES.md#c24-semantic-upgrade)

## 固定安装与测试范围

'''
    text+=f"最终 ZIP `{installation['archive_bytes']}` bytes，SHA-256 `{installation['archive_sha256']}`；manifest `{installation['manifest_sha256']}`。206 产品 Python 文件与安装版逐字节相同。"+link('installation-r3/verification.json')+'。\n\n'
    text+='| 范围 | 实际通过/总数 | 证据 |\n|---|---:|---|\n'
    for name,count in tests:text+=f"| {name} | {count}/{count}，0 skip | "+link('tests/'+name+'/verification.json')+' |\n'
    text+='''
这些范围不相加，历史完整 2930 方法未重跑。新增 17 个升级测试使用小型真实文件和合成向量，覆盖旧安装不可用、外部/应用内依赖变化、损坏输入、读锁、两索引/两校准、局部选择、幂等、预算、取消、复制中断及模拟写后回滚；这些单元测试不是模型质量测试。真实推理另列如下。

## 真实迁移和模型对照

使用既有第二次工程包、原 80 查询和独立标签，标签不交给模型。先从同一固定 ZIP 在案例独有目录安装旧位置，显式迁移后进行 CPU/CUDA 基线查询。所有该案例 CLI/worker 结束后，只移走此独有安装目录；不移动历史共享安装、不终止其他 GPU 任务。

旧路径直接查询先返回 `SEMANTIC_ADAPTER_INTEGRITY_FAILED`，随后以新 ID 执行 dry-run、正式升级和同键重放。原适配器/索引/校准/资产/权利/编辑序列保持，新 ID 单独派生。

'''
    text+=f"实际派生 **{upgrade['index_count']} 个索引、{upgrade['profile_count']} 个设备校准**；19 实现模块 SHA/长度相同，随应用迁移 **{response['adapter']['runtime_upgrade']['relocated_bundled_runtime_files']} 个原生依赖文件**，复制负载 `{response['copied_payload_bytes']}`；新模型前向 **0**。"+link('upgrade-r2/verification.json')+' · '+link('upgrade-r2/upgrade.stdout.json','完整映射/文件清单')+'。\n\n'
    text+='| 实际入口/阶段 | 查询 | 决定/素材排序 | 最大分数误差 | 原错误 |\n|---|---:|---|---:|---|\n'
    for phase,value in queries:
        text+=f"| {phase} | {value['query_count']} | 与前一固定结果一致 | {value['maximum_score_error']:.9g} | `q14` / `hout00zh` / `hout08zh`；"+link(phase+'-r2/verification.json')+' |\n'
    text+='''
CPU 与 CUDA 分别使用原设备校准，各自在升级前后对比，未把跨设备阈值混用。结果保留原错误：两条库外误接受和一条钟表误拒；迁移一致不代表语义改善、概率校准或自然素材验收。Native Torch/SigLIP2 使用既有离线目录，GPU 查询为真实 CUDA；无下载、无容器、无虚拟环境，也没有启动这些库原属的服务。

升级后导出/导入工程包，完整 `project.json`、Rights Ledger 和全部资产 SHA 对照保持；原工程移走后验证并通过真实注册 Skill 执行 80 查询。

'''
    text+=f"工程包 `{package['package_bytes']}` bytes、SHA-256 `{package['package_sha256']}`；"+link('roundtrip-r2/verification.json')+' · '+link('skill-cuda-r2/verification.json','真实统一入口')+'。\n\n'
    text+='## 原生超时、取消与原数据保护\n\n| 案例 | 实际墙钟秒 | 取消至退出秒 | 行为 |\n|---|---:|---:|---|\n'
    for value in faults['cases']:
        delay='—' if value['cancel_to_exit_seconds'] is None else f"{value['cancel_to_exit_seconds']:.3f}"
        behavior='读取中断，部分摘要丢弃' if value['error'].get('diagnostics',{}).get('phase')=='integrity-read' else '读取前/文件间中断，无部分摘要诊断'
        text+=f"| {value['case']} | {value['elapsed_seconds']:.3f} | {delay} | `{value['error']['code']}`，{behavior} |\n"
    text+='\n'+link('faults-r3/verification.json','四例实际命令/诊断')+'。取消标记分别在 Win32 句柄观测总读取超过 64MiB 与 512MiB 后写入，前者可能发生在摘要读取前，后者明确核对读取中断诊断；没有模型/计时 hook。工程元数据和资产保持；这些是固定及时性边界检查，不是独占性能 benchmark。OS 阻塞读取、任意断电/设备丢失/磁盘耗尽及其他 worker 的完整恢复仍开放。\n\n'
    text+='''## 失败保留与交付边界

首次实现只迁移语义模块，真实 worker 从新安装导入 NumPy/Pillow 时返回 `SEMANTIC_RUNTIME_CHANGED`。原始 worker 版本/模块路径响应留存，随后增加应用内依赖逐文件相同字节迁移；没有放宽 worker 校验。开发 r5 还暴露测试夹具重复登记 Rights Ledger 的错误，已修正夹具，原日志保留。r1/r2 候选包与当时测试收据保留，不冒充最终包。

'''
    text+=link('before-cuda-r1/query80.stdout.json','原 CLI 失败')+' · '+link('before-cuda-r1/worker-failure-response.json','原 worker 响应')+' · '+link('tests/development-r5/tests.log','测试夹具原失败')+'。\n\n'
    text+='原生及时性测试最初把短超时或累计 64MiB 的总 I/O 都当作摘要读取中的证明；实际正确返回了读取前/文件间的超时或取消，因此缺少部分摘要诊断。原 1 秒墙钟及取消及时性门槛保持，最终区分启动、真实读取和早期取消，另用 512MiB 案例检查读取中取消。'+link('faults-r1/verification.json','原测试假设失败 r1')+' · '+link('faults-r2/verification.json','原测试假设失败 r2')+'。\n\n'
    text+='r14 kit 为 89 文件/66 Skill 文件，独立中文/空格目录完成配置、注册、版本/能力/帮助、真实升级 dry-run、工程验证和恢复预览共 8 次进程调用；真实 Codex 发现联接未改动。'+link('kit-r1/verification.json')+'。本地固定安装和四个既有配音/翻译模型包重新核验，语义模型/运行依赖另行登记。\n\n'
    text+='依赖字节核验针对原适配器登记清单中的模块、原生文件与权重，不宣称冻结整个 Python 环境或所有 OS DLL。该批没有新视频效果或音频生成，不制作替代性 GIF，不将历史媒体冒充本次输出。既有 500 母图滤镜、广告视频/GIF 和实际检索预览仍可查看。人类听审、自然语义质量、Agent 独立成功率、干净主机和匹配新版公开 Release 未因此完成；旧公开标签/附件保持。\n'
    (ROOT/'docs/validation/语义运行时升级实测_2026-10-25.md').write_text(text,encoding='utf8',newline='\n')
    print(json.dumps(dict(status='written',query_phases=5,upgrade_model_forwards=0)))


if __name__=='__main__':main()
