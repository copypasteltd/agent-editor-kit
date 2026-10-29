"""Append terminal CLI65 installation checks and reproducible open defects."""
import argparse
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'docs/validation/evidence/music-loading-20261030-r1'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    return json.loads(path.read_bytes())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run', required=True)
    args = parser.parse_args()
    assert args.run.isalnum()
    required = {name: BASE / (name + '/verification.json') for name in (
        'session-startup-trace-r1', 'recovery-integrity-r1',
        'installed65-music-i1', 'installed65-bootstrap-i1', 'installed65-control-i1')}
    missing = [name for name, path in required.items() if not path.is_file()]
    if missing:
        print(json.dumps(dict(status='pending', missing=missing, documents_changed=False)), flush=True)
        return 2
    reports = {name: load(path) for name, path in required.items()}
    for name, report in reports.items():
        assert report['status'] == ('reproduced' if name == 'recovery-integrity-r1' else 'passed'), name
    trace = reports['session-startup-trace-r1']
    assert trace['original_assertions_and_deadlines'] and trace['real_fsync_preserved']
    assert trace['tests'] == 1 and trace['frozen_equal']
    clock = {name: next(row['monotonic'] for row in trace['events'] if row['event'] == name) for name in (
        'interpreter-ready', 'cli-imported', 'prepare-transaction-begin', 'prepare-transaction-end')}
    imported = clock['cli-imported'] - clock['interpreter-ready']
    prepared = clock['prepare-transaction-end'] - clock['prepare-transaction-begin']
    flushes = trace['completed_fsync_seconds']
    assert len(flushes) == 31 and not trace['last_fsync_unfinished_at_child_exit']
    failed = load(BASE / 'source65-session-r1/verification.json')
    assert failed['status'] == 'failed' and failed['tests'] == 12 and failed['failures'] == 1
    repro = reports['recovery-integrity-r1']
    assert len(repro['cases']) == 2 and all(row['reproduced'] for row in repro['cases'])
    for group, count in (('music', 74), ('bootstrap', 33), ('control', 26)):
        report = reports['installed65-' + group + '-i1']
        assert report['cli_version'] == '0.1.65' and report['tests'] == count
        assert report['failures'] == report['errors'] == report['skipped'] == 0
        assert report['frozen_equal'] and report['installed'] and not report['source_fallback']
    proof = BASE / ('documentation-close-' + args.run)
    proof.mkdir()
    (proof / 'executed-runner.py').write_bytes(Path(__file__).read_bytes())
    labels = (
        ('CLI65原启动门槛的内存观测', 'CLI65原啟動門檻的記憶體觀測', 'CLI65 original startup deadline with memory tracing'),
        ('CLI65恢复备份缺陷复现（未修复）', 'CLI65恢復備份缺陷重現（未修復）', 'CLI65 recovery backup defects reproduced (UNFIXED)'),
        ('CLI65独立安装版配乐回归', 'CLI65獨立安裝版配樂回歸', 'CLI65 independently installed music regression'),
        ('CLI65独立安装版原生隔离', 'CLI65獨立安裝版原生隔離', 'CLI65 independently installed native isolation'),
        ('CLI65独立安装版执行控制', 'CLI65獨立安裝版執行控制', 'CLI65 independently installed execution control'))
    details = (
        (f'原断言和20秒门槛的单项通过；CLI导入{imported:.3f}s、事务准备{prepared:.3f}s。全程31次真实fsync合计{sum(flushes):.3f}s，并非全在准备阶段；未复现整组失败，不替代R565。',
         f'原斷言和20秒門檻的單項通過；CLI匯入{imported:.3f}s、事務準備{prepared:.3f}s。全程31次真實fsync合計{sum(flushes):.3f}s，並非全在準備階段；未重現整組失敗，不替代R565。',
         f'Original assertions/20s deadline: single check passed. CLI import {imported:.3f}s; prepare {prepared:.3f}s. All 31 actual fsync calls totaled {sum(flushes):.3f}s across the child lifetime. Group failure not reproduced; R565 remains failed.'),
        ('两个一次性工程确认：同长度损坏备份被恢复并删除日志；末项备份缺失时，前两项已被写回。仅复现，不是恢复验收；G33修复待完成。',
         '兩個一次性工程確認：同長度損壞備份被恢復並刪除日誌；末項備份缺失時，前兩項已被寫回。僅重現，不是恢復驗收；G33修復待完成。',
         'Two disposable projects confirmed: same-size corrupted backup restored and journal deleted; missing final backup detected after two earlier writes. Reproduction only; G33 repair remains open.'),
        ('74通过，288应用模块与源码相同，加载实际安装包，无源码回落；含37项请求／读取检查，不重复累计。无神经音乐生成。',
         '74通過，288應用模組與原始碼相同，載入實際安裝包，無原始碼回退；含37項請求／讀取檢查，不重複累計。無神經音樂生成。',
         '74 passed against the installed package; all 288 modules match source, with no source fallback. Includes the 37 request/loader checks; no duplicate total or neural music generation.'),
        ('33通过，实际加载独立安装包，原生依赖归属与拒绝外部应用检查，无神经推理。',
         '33通過，實際載入獨立安裝包，原生依賴歸屬與拒絕外部應用檢查，無神經推理。',
         '33 passed against the independently installed package: native dependency ownership and foreign application refusal. No neural inference.'),
        ('26通过，实际加载独立安装包，进程树、执行预算、清理检查；音乐中途故障与完整443仍须另验。',
         '26通過，實際載入獨立安裝包，進程樹、執行預算、清理檢查；音樂中途故障與完整443仍須另驗。',
         '26 passed against the independently installed package: process ownership, budgets and cleanup. Actual music faults and full443 remain separate.'))
    names = list(required)
    changed = {}
    for language, filename in enumerate(('README.md', 'README.zh-TW.md', 'README.en.md')):
        path = ROOT / filename
        text = path.read_text(encoding='utf-8')
        previous = re.findall(r'^\| R\d+ \|.*$', text, re.M)
        assert len(previous) == 565
        additions = [f'| R{566 + index} | {labels[index][language]} | {details[index][language]} [Proof](docs/validation/evidence/music-loading-20261030-r1/{name}/verification.json) |'
            for index, name in enumerate(names)]
        text, count = re.subn(r'(^\| R565 \|.*$)', lambda m: m[0] + '\n' + '\n'.join(additions), text, flags=re.M)
        assert count == 1
        warning = (
            '原12项会话组有1项启动失败；内存观测下的单项通过尚未确认原因。另外已复现两个备份完整性缺陷，修复待完成。',
            '原12項會話組有1項啟動失敗；記憶體觀測下的單項通過尚未確認原因。另外已重現兩個備份完整性缺陷，修復待完成。',
            'The original 12-check session group has one startup failure; a traced single pass has not established its cause. Two backup-integrity defects are reproduced and remain unfixed.')
        text, count = re.subn(r'(<!-- aek-cli65-current -->\n.*?)(\n<!-- /aek-cli65-current -->)',
            lambda m: m[1] + '\n\n' + warning[language] + ' [Round](docs/validation/CLI65配乐读取与计时_2026-10-30.md)' + m[2], text, flags=re.S)
        assert count == 1
        current = re.findall(r'^\| R\d+ \|.*$', text, re.M)
        assert len(current) == 570 and set(previous) <= set(current)
        assert len(re.findall(r'^\| F\d+ \|', text, re.M)) == 88
        path.write_text(text, encoding='utf-8', newline='\n')
        changed[filename] = sha(path)
    manual = ROOT / 'docs/product/NEURAL_MUSIC_LOADING.md'
    text = manual.read_text(encoding='utf-8')
    text += ('\n## 独立安装回归与恢复限制\n\n'
        'local63候选的独立安装版分别通过74项配乐、33项原生隔离和26项执行控制回归，实际模块路径来自安装目录，无源码回落。'
        '这三组不代替新音乐模型前向、完整443兼容、自然听审或正式注册。\n\n'
        '原12项会话组保留一项20秒启动失败。保留原门槛的内存观测单项后来通过，只说明该次未复现；'
        '不能据此确认写盘是唯一原因或宣布原失败已修复。另以两个一次性工程复现恢复备份未核验SHA和后续缺失导致部分写回的问题，'
        '尚未修复。完整证据和下一步见[本轮记录](../validation/CLI65配乐读取与计时_2026-10-30.md)。\n')
    manual.write_text(text, encoding='utf-8', newline='\n')
    changed[manual.relative_to(ROOT).as_posix()] = sha(manual)
    round_path = ROOT / 'docs/validation/CLI65配乐读取与计时_2026-10-30.md'
    assert not round_path.exists()
    round_text = '''# CLI65配乐读取与完整计时开发记录

证据日期：2026-10-30，原生Windows。源程序CLI0.1.65；验证候选local63；正式统一Skill仍CLI0.1.63／local61／r58，1个入口、17个内部模块。公开alpha.3／CLI0.1.2保持。原38项目标范围不变；本轮不是剪映等价或正式升级验收。

## 本轮实现事项

| 编号 | 实现或检查 | 实际结果 | 边界 |
| --- | --- | --- | --- |
| D01 | 四组件权重固定原生pread，逐阶段核对实际打开清单；异常恢复原读取器，禁用动态显存；仅传核心实际声明的可选offline参数 | 源码37项请求／读取检查通过；两套已有原生环境都实际读回四份微型BF16，数值和metadata相同 | 小张量检查没有音乐模型前向；网络阻断和CUDA前向要求保留 |
| D02 | 模型函数时钟包含运行库导入，保留三个大阶段并新增checkpoint／编码／采样／解码计时，共10字段 | 源码74项配乐回归通过，包含D01的37项，不重复累计 | 墙钟包含设备加载，不是GPU kernel时间；CLI64旧同名总时钟不含此前导入，不能直接比较 |
| D03 | 独立构建ZIP、离线安装与未注册统一Skill说明 | local63 ZIP和全部288应用模块逐字节核对；94文件／17模块的候选Skill实际PowerShell version/help通过 | 模型／运行库未打包；正式93文件入口和两份配置未切换 |
| D04 | 独立安装版兼容回归 | 配乐74、原生隔离33、执行控制26分别通过，无失败／错误／跳过、无源码回落；源码对应组也分别通过 | 不把组数重复累计，不代替完整443或实际音乐中途故障 |
| D05 | 原会话失败与无诊断写盘的启动观测 | 原12项：11通过、1项20秒启动失败；随后原单项在内存记录下通过，原断言／门槛和真实fsync均保留 | 后一次通过未重现前一次失败；未确认唯一原因，完整443仍未验收 |
| D06 | 一次性工程验证事务恢复完整性 | 同长度损坏备份被错误接受并删除日志；末项备份缺失前，project.json和project.lock.json已写回，两个缺陷确实复现 | 这是缺陷复现，不是恢复修复或验收 |
| D07 | 三语README、手册、原始证据同步 | 三语核验表连续到R570，旧555项原文保留；功能表F88，使用命令及计时字段见手册 | 测试数量不表示剪映功能等价 |

## 关键证据

'''
    for name in ('source65-unit-r1', 'source65-music-r1', 'source65-bootstrap-r1', 'source65-control-r1',
        'source65-session-r1', 'native-reader-r1', 'native-reader-d1', 'native-stack-reader1',
        'candidate-r1', 'skill-stage-r1', *names):
        round_text += f'- [{name}](evidence/music-loading-20261030-r1/{name}/verification.json)\n'
    round_text += f'''
内存观测：CLI导入{imported:.6f}秒、事务准备{prepared:.6f}秒。整个子进程生命周期31次真实fsync合计{sum(flushes):.6f}秒，最长{max(flushes):.6f}秒；并非全部处于事务准备阶段。该次原单项共{trace['elapsed_seconds']:.6f}秒，未执行音乐模型。

## 实际GPU新生成

run_neural_music65_case.py --run stage1 已从未注册候选Skill的PowerShell入口启动，调用独立安装版65和已有D盘原生运行库。源码288模块在其完整验证期间冻结；预检、登记、生成及后检按真实完成状态记录。该任务尚无终态收据时，不算GPU生成通过，也不把CLI64旧音频当作CLI65新生成。

新文件和缓存仅在E盘，未调度Docker／WSL／虚拟化环境服务，未打开浏览器。当前不发布任何权利尚未确认的音频或模型文件。

## 待处理、待完成事项

| 编号 | 待办 | 下一步 | 原目标 |
| --- | --- | --- | --- |
| P01 | CLI65真实安装版GPU新生成与工程包闭环 | 沿用同一个任务，核对四组件pread、实际CUDA前向、原生样本／完整PCM、入轨、清理和包重放；保留失败及完整时钟 | G25、G33、G34 |
| P02 | 已复现的恢复备份完整性缺陷 | 在冻结的音乐任务终态后，新增完整预检：所有条目、归属、大小、SHA及重复路径先通过，之后才写回；原损坏备份保留并拒绝恢复 | G33 |
| P03 | 原20秒启动失败原因未明 | 保留原断言和期限，以低干扰诊断重现后修复；完整443必须独立实际执行，不用单项通过覆盖整组失败 | G33 |
| P04 | 正式Skill与公开发行版本落后于开发候选 | 完成源码／独立安装／真实生成／故障和交付门禁后，另建新版本普通推送，保留旧安装、标签与附件 | G34、G35、G38 |
| P05 | 自然音乐听审、长曲、歌词和跨设备覆盖 | 独立记录完整试听与风格匹配，增加实际场景和硬件；不以PCM或模型调用次数替代自然质量 | G25、G36 |

未列出的原需求仍见[完整38项目标](../product/GOAL_GAPS_20261025.md)。使用流程见[神经配乐主手册](../product/NEURAL_MUSIC_GENERATION.md)和[CLI65读取／计时说明](../product/NEURAL_MUSIC_LOADING.md)。
'''
    round_path.write_text(round_text, encoding='utf-8', newline='\n')
    changed[round_path.relative_to(ROOT).as_posix()] = sha(round_path)
    report = dict(status='passed', source_cli='0.1.65', candidate='v0.1.0-alpha.4-local.63', formal_cli='0.1.63',
        README_rows=570, previous_565_rows_retained=True, feature_rows=88,
        original_session_group_failed=True, backup_defects_reproduced=2, backup_defects_repaired=False,
        original_startup_deadline_preserved=True, actual65_generation_accepted=False,
        formal_activation=False, full_product_goal_closed=False,
        evidence={name: sha(path) for name, path in required.items()}, files=changed)
    (proof / 'verification.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps(dict(status='passed', README_rows=570, formal_activation=False)), flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
