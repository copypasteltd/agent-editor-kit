"""Add the latest assessment without removing any earlier README evidence."""
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def main():
    rows={
        'README.md':'| R44 | 最新目标差距与开发候选分层复核 | 真实注册入口另 6 次只读调用通过，安装版仍为 CLI 0.1.4 / 72 项声明；开发候选 25 项契约测试、13 次准备命令另列，GPU 索引 2 次实际前向不冒充检索质量 | [38 组差距](docs/product/GOAL_GAPS_20261025.md) · [新核对](docs/validation/evidence/goal-gaps-20261025-r3/inventory.json) · [证据边界](docs/validation/evidence/goal-gaps-20261025-r3/review.json) · [开发索引](docs/validation/evidence/goal-gaps-20261025-r3/candidate-progress.json)；2026-10-25，无新增安装版渲染/推理或人工听审；公开包仍为 alpha.3，G01–G38 均有未关闭条件 |',
        'README.zh-TW.md':'| R44 | 最新目標差距與開發候選分層複核 | 真實註冊入口另 6 次唯讀調用通過，安裝版仍為 CLI 0.1.4 / 72 項聲明；開發候選 25 項契約測試、13 次準備命令另列，GPU 索引 2 次實際前向不冒充檢索品質 | [38 組差距](docs/product/GOAL_GAPS_20261025.md) · [新核對](docs/validation/evidence/goal-gaps-20261025-r3/inventory.json) · [證據邊界](docs/validation/evidence/goal-gaps-20261025-r3/review.json) · [開發索引](docs/validation/evidence/goal-gaps-20261025-r3/candidate-progress.json)；2026-10-25，無新增安裝版渲染/推論或人工聽審；公開套件仍為 alpha.3，G01–G38 均有未關閉條件 |',
        'README.en.md':'| R44 | Latest goal review separates installed and candidate work | Six more actual discovery-entry read-only calls passed; installed CLI remains 0.1.4 / 72 declarations. The separate candidate has 25 contract tests, 13 setup calls and two actual GPU image forwards, none establishing retrieval relevance | [38 gaps](docs/product/GOAL_GAPS_20261025.md) · [New inventory](docs/validation/evidence/goal-gaps-20261025-r3/inventory.json) · [Evidence scope](docs/validation/evidence/goal-gaps-20261025-r3/review.json) · [Candidate index](docs/validation/evidence/goal-gaps-20261025-r3/candidate-progress.json); 2026-10-25, no new installed renders/inference or human listening; public package stays alpha.3 and G01–G38 retain open gates |',
    }
    notes={
        'README.md':'**最新复核（R44，2026-10-25 04:38 台北）：** 当前可用的是 Agent 编辑 CLI 底座；完整剪映水准还缺高级 AI、复杂组合与自然视听验收、内容模板生态、Agent 自主任务成功率和稳定交付。G26 候选已实现图文索引/查询 CLI，并在 RTX 3060 上为 10 个素材生成 15 条索引（14 张去重图、2 次实际前向）；相关性、CPU/GPU 对照和安装/Skill 交付尚未验收。开发索引全阶段约 306 秒，含完整性核验、进程/模型加载及校验，实际模型推理约 26 秒；不能据此宣称实时检索或跨命令模型复用。安装版仍为 CLI 0.1.4，完整 38 组差距继续开放，不给出未经建立的总体完成率。',
        'README.zh-TW.md':'**最新複核（R44，2026-10-25 04:38 台北）：** 目前可用的是 Agent 編輯 CLI 底座；完整剪映水準仍缺進階 AI、複雜組合與自然視聽驗收、內容範本生態、Agent 自主任務成功率和穩定交付。G26 候選已實作圖文索引/查詢 CLI，並在 RTX 3060 上為 10 個素材產生 15 條索引（14 張去重圖、2 次實際前向）；相關性、CPU/GPU 對照和安裝/Skill 交付尚未驗收。開發索引全階段約 306 秒，含完整性核驗、程序/模型載入及校驗，實際模型推論約 26 秒；不能據此宣稱即時檢索或跨命令模型重用。安裝版仍為 CLI 0.1.4，完整 38 組差距繼續開放，不給出未經建立的整體完成率。',
        'README.en.md':'**Latest review (R44, 2026-10-25 04:38 Taipei):** A usable Agent editing CLI foundation is delivered. Advanced AI, complex combinations, natural visual/audio quality, content/templates, autonomous Agent success and reliable delivery remain open for full CapCut parity. The separate G26 candidate implements image/text index/query commands and built 15 index rows for 10 assets on RTX 3060 (14 unique encoded images, two actual forwards). Retrieval relevance, CPU/GPU comparison and installed/Skill delivery are not accepted yet. The complete indexing phase took about 306 seconds including integrity verification, process/model startup and verification; actual model inference took about 26 seconds. This establishes neither real-time retrieval nor persistent reuse between commands. Installed CLI remains 0.1.4; all 38 gap groups retain open conditions, with no established overall completion percentage.',
    }
    for name,row in rows.items():
        path=ROOT/name;text=path.read_text('utf8')
        assert '| R44 |' not in text
        position=text.index('\n',text.index('| R43 |'))
        text=text[:position+1]+row+'\n'+text[position+1:]
        # Preserve every existing section, command and historical verification row.
        section=text.index('\n## ',position+len(row)+1)
        following=text.index('\n## ',section+1)
        text=text[:following]+'\n'+notes[name]+'\n'+text[following:]
        path.write_text(text,encoding='utf8',newline='\n')
    path=ROOT/'docs/README.md';text=path.read_text('utf8')
    old='[最新 6 次安装版只读核对](validation/evidence/goal-gaps-20261025-r2/inventory.json) · [证据复核](validation/evidence/goal-gaps-20261025-r2/review.json)'
    assert old in text
    text=text.replace(old,'[最新 6 次安装版只读核对](validation/evidence/goal-gaps-20261025-r3/inventory.json) · [证据复核](validation/evidence/goal-gaps-20261025-r3/review.json) · [另行开发的 GPU 索引](validation/evidence/goal-gaps-20261025-r3/candidate-progress.json)')
    path.write_text(text,encoding='utf8',newline='\n')
    path=ROOT/'docs/product/IMPLEMENTATION_PLAN_20261025.md';text=path.read_text('utf8')
    old='G26 开发准备中：离线图文契约草稿、校验代码与权重已准备，索引/查询链路、相关性实测和安装交付未完成；其余待执行。500 LUT 与 359 资源保留，不按目录数量充当质量通过'
    assert old in text
    text=text.replace(old,'G26 候选索引/查询 CLI 已写出，25 项契约测试与 13 次准备命令通过；另完成实际 CUDA 图像索引和完整性核验。真实查询相关性、CPU/GPU 对照、成片复用、安装及 Skill 交付仍未验收；其余待执行。500 LUT 与 359 资源保留，不按目录数量充当质量通过')
    text+='\n2026-10-25 04:38（台北）[第三次安装版复核](../validation/evidence/goal-gaps-20261025-r3/inventory.json)仍为 CLI 0.1.4、72 项声明。另行开发的 G26 候选完成 10 个素材/15 条索引、14 张去重图/2 次 CUDA BF16 前向及索引完整性验证；[开发进展证据](../validation/evidence/goal-gaps-20261025-r3/candidate-progress.json)与只读核对分开。约 306 秒全阶段包含完整性核验及进程/模型加载，模型推理约 26 秒；性能与模型复用仍是 G32 开放项。检索相关性及本地安装/Skill 尚未交付，不关闭 G26 或任何其他差距组。\n'
    path.write_text(text,encoding='utf8',newline='\n')
    print('Updated all three READMEs, documentation index and full-goal implementation ledger.')


if __name__=='__main__':main()
