"""Record the interrupted run, real recovery owner and unchanged formal Skill."""
import ctypes
from ctypes import wintypes
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'docs/validation/evidence/job-enumeration-20261029-r1'


def load(p):
    return json.loads(p.read_bytes())


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def save(p, value):
    p.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')


def main():
    original = load(BASE / 'recovery-controller-r2/interruption.json')
    assert original['status'] == 'interrupted-without-terminal-receipt'
    assert not original['original_complete_contract_acceptance']
    assert all(sha(Path(p)) == h for p, h in original['preserved_original_files'].items())
    pid = int((ROOT / 'local/agent-ffmpeg/recovery63-launch-r2/pid.txt').read_text())
    api = ctypes.WinDLL('kernel32', use_last_error=True)
    api.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    api.OpenProcess.restype = wintypes.HANDLE
    api.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
    api.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = api.OpenProcess(0x1000, False, pid)
    assert handle, 'Recovery owner is not live'
    try:
        code = wintypes.DWORD()
        assert api.GetExitCodeProcess(handle, ctypes.byref(code)) and code.value == 259
    finally:
        api.CloseHandle(handle)
    script = ROOT / 'docs/validation/activate_source63_skill.py'
    for run in ('r3', 'r4'):
        r = load(BASE / ('activation-rollback-' + run + '/verification.json'))
        assert r['status'] == 'passed' and r['synthetic_gate_inputs'] and r['synthetic_CLI_failure']
        assert r['script_sha256'] == sha(script) and r['production_files_unchanged'] == 95
    full = load(BASE / 'activation-rollback-r4/verification.json')['cases'][0]
    assert full['files_changed_before_entry_failure'] == 95 and full['actual_atomic_writes'] == 192
    installation = load(BASE / 'installation-candidate-r1/verification.json')
    guard = installation['registered_skill_file_hashes']
    assert all(sha(Path(p)) == h for p, h in guard.items())
    out = BASE / 'recovery-preparation-r1'
    out.mkdir(exist_ok=False)
    (out / 'executed-runner.py').write_bytes(Path(__file__).read_bytes())
    cases = [('activation', 'activate_source63_skill.py', ['--run', 'recovery-refusal']),
             ('documentation', 'complete_source63_rollout_docs.py', ['--phase', 'registered'])]
    calls = []
    for name, filename, args in cases:
        command = ['C:/Python313/python.exe', '-E', '-B', '-u', '-X', 'utf8', str(ROOT / 'docs/validation' / filename), *args]
        result = subprocess.run(command, cwd=ROOT, capture_output=True, timeout=60,
                                creationflags=subprocess.CREATE_NO_WINDOW)
        (out / (name + '.stdout')).write_bytes(result.stdout)
        (out / (name + '.stderr')).write_bytes(result.stderr)
        assert result.returncode == 2 and load(out / (name + '.stdout'))['mutated'] is False
        calls.append(dict(name=name, exit_code=result.returncode))
    note = ROOT / 'docs/validation/CLI63安装回归中断与恢复_2026-10-29.md'
    assert not note.exists()
    note.write_text('''# CLI63安装回归中断与恢复

CLI63/local61独立候选已经原生安装，源码完整406项及安装31入口／37循环／26控制／57选材／104语义分组已分别通过。安装完整406的r1在执行中失去原生进程和工具句柄，没有终态收据；不将部分`ok`日志累计为完整通过。

## 原运行保留

实际查询确认原交付PID30156、安装控制PID34996、完整测试PID39660及等待PID29408均已不存在。没有终止或重启仍活跃的原任务。最后原日志停在补帧配方测试，完整套件未结束；中断原因未建立，不推断为产品缺陷或环境根因。

[中断记录和原文件摘要](evidence/job-enumeration-20261029-r1/recovery-controller-r2/interruption.json)。原`installed63-contracts-r1`日志、依赖输出、执行脚本与控制器进度保持字节不变；原通过的五个安装分组继续保留其原始独立证据，只有完整406套件在新`installed63-contracts-r2`目录从头执行。

## 原生恢复程序

`resume_source63_delivery.py`在启动前核验旧PID均已退出、原r1无终态、候选版本和已通过五组的冻结摘要、正式95文件相同。后台隐藏原生进程依次执行完整406-r2、实际安装DF3 CUDA／循环修复／MuseTalk CUDA、单一Skill暂存及真实候选PowerShell三类案例；任一失败即停止，不继续注册。它不自动激活正式入口。

每五秒更新进度，保存当前子PID、启动时间、参数、终态退出码和独立日志。进度文件不是存活证据：继续观察时仍需查询具体原生PID或已持有句柄；只有真实终态收据通过后才接受结果。原生后台启动不使用Docker、WSL、容器或新虚拟环境。

正式门禁明确引用`installed63-contracts-r2/verification.json`，不会把新结果复制到原r1目录。正式Skill仍CLI59/local57/r57；CLI63源码／独立安装／候选／注册入口／独立工具包分层报告。已有公开Release和旧r57 ZIP保持不变。

## 切换与文档

更改门禁路径后，重新生成并核验实际注册入口脚本；r3/r4四种隔离回滚均通过，含全部93个Skill文件与两项元数据全变后192次真实原子替换恢复。合成门禁／CLI失败只验证文件事务，不能当成406合同、真实C盘入口、模型推理、断电或干净机器验收。

[r3三种隔离故障](evidence/job-enumeration-20261029-r1/activation-rollback-r3/verification.json) · [r4全部95文件恢复](evidence/job-enumeration-20261029-r1/activation-rollback-r4/verification.json)。原r1/r2回滚记录对应先前脚本摘要，保留为历史，不改标成本轮新脚本结果。

`complete_source63_rollout_docs.py`分`registered`和`kit`两阶段，只有实际注册案例通过才更新正式版本与使用流程，只有工具包独立验收通过才添加下载；新状态保留旧README正文和全部编号行。它不修改已实测Skill正文。两项实际缺门禁调用均返回pending／2且未修改正式95文件。

没有新增功能性内核；本轮是恢复执行、门禁路径与交付文档准备。全部38项原目标继续开放。
''', encoding='utf-8', newline='\n')
    texts = {
        'README.md': ('**CLI63安装回归恢复：** 完整406-r1因进程退出且无终态而记为中断；原日志保留，正在新r2目录重跑。正式Skill仍CLI59/local57/r57。', '原PID已确认退出，五个已完成分组保留；完整406在新r2重跑，GPU／候选／正式切换另验。r2门禁脚本四种隔离回滚通过；无新增内核或自然质量验收。'),
        'README.zh-TW.md': ('**CLI63安裝回歸恢復：** 完整406-r1因程序退出且無終態記為中斷；保留原日誌，正在新r2目錄重跑。正式Skill仍CLI59/local57/r57。', '已確認原PID退出，保留五個已完成分組；完整406在新r2重跑，GPU／候選／正式切換另驗。r2門禁腳本四種隔離回滾通過；無新增內核或自然品質驗收。'),
        'README.en.md': ('**CLI63 installed regression recovery:** complete406-r1 ended without a terminal receipt and is recorded as interrupted. Original logs remain; a new full r2 run is active. Formal Skill stays CLI59/local57/r57.', 'Original PIDs verified absent; five completed groups retained. Full406 reruns as r2; GPU/staged/formal promotion remain separate. Four isolated rollback cases passed for the r2 gate script; no new core feature or natural-quality acceptance.')}
    audit = {}
    for name, (top, description) in texts.items():
        p = ROOT / name
        old = p.read_text(encoding='utf-8')
        old_rows = re.findall(r'^\| R\d+ \|.*$', old, re.M)
        assert len(old_rows) == 522
        title = old.splitlines()[0]
        new = old.replace(title, title + '\n\n' + top + ' [Recovery](docs/validation/CLI63安装回归中断与恢复_2026-10-29.md)', 1)
        row = '| R523 | CLI63 interrupted installation recovery | ' + description + ' [Evidence](docs/validation/CLI63安装回归中断与恢复_2026-10-29.md) |'
        new = new.replace(old_rows[-1], old_rows[-1] + '\n' + row, 1)
        assert re.findall(r'^\| R\d+ \|.*$', new, re.M)[:522] == old_rows
        p.write_text(new, encoding='utf-8', newline='\n')
        audit[name] = sha(p)
    path = ROOT / 'docs/validation/CLI63候选交付门禁_2026-10-29.md'
    with path.open('a', encoding='utf-8') as stream:
        stream.write('\n\n## 安装完整回归r1中断与r2恢复\n\n2026-10-29原安装完整406进程及父控制器均已不存在，r1没有终态；保留原日志，新原生后台控制器在r2目录重跑完整406。前五个安装组的独立通过证据保留。正式Skill仍59，门禁现明确读取installed63-contracts-r2；[实际中断、恢复程序与隔离回滚](CLI63安装回归中断与恢复_2026-10-29.md)。不把中断或存活进度写成通过。\n')
    goal = ROOT / 'docs/product/GOAL_GAPS_20261025.md'
    old = goal.read_text(encoding='utf-8')
    previous = re.findall(r'^\| G\d\d \|.*$', old, re.M)
    assert len(previous) == 38
    title = old.splitlines()[0]
    new = old.replace(title, title + '\n\n2026-10-29 G33/G34：CLI63安装完整406-r1已确认原进程退出、无终态，按中断保留；新原生后台r2重跑，正式Skill仍59。[恢复与新门禁回滚证据](../validation/CLI63安装回归中断与恢复_2026-10-29.md)。全部38项原关闭条件不变。', 1)
    assert re.findall(r'^\| G\d\d \|.*$', new, re.M) == previous
    goal.write_text(new, encoding='utf-8', newline='\n')
    assert all(sha(Path(p)) == h for p, h in guard.items())
    report = dict(status='passed', checked_at_utc=datetime.now(timezone.utc).isoformat(),
                  recovery_pid_confirmed_live=pid, calls=calls, README_rows=523,
                  previous_README_rows_preserved=522, original_goal_rows_preserved=38,
                  formal_files_unchanged=95, source='0.1.63', candidate='0.1.63/local61',
                  formal='0.1.59/local57/r57', formal_activation=False,
                  full_installed_contracts_accepted=False, full_goal_closed=False, readmes=audit)
    save(out / 'verification.json', report)
    print(json.dumps(report), flush=True)


if __name__ == '__main__':
    main()
