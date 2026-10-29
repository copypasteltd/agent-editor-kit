"""Document isolated disk rollback only after both actual checks pass."""
import hashlib,json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];BASE=ROOT/'docs/validation/evidence/job-enumeration-20261029-r1'
def load(p):return json.loads(p.read_bytes())
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
first=load(BASE/'activation-rollback-r1/verification.json');full=load(BASE/'activation-rollback-r2/verification.json')
for r in (first,full):
 assert r['status']=='passed' and r['synthetic_gate_inputs'] and r['synthetic_CLI_failure']
 assert r['production_files_unchanged']==95 and not r['model_inference'] and not r['formal_activation']
 assert r['script_sha256']==sha(ROOT/'docs/validation/activate_source63_skill.py')
assert len(first['cases'])==3 and len(full['cases'])==1
assert full['cases'][0]['files_changed_before_entry_failure']==95
assert full['cases'][0]['actual_atomic_writes']==192
note=ROOT/'docs/validation/CLI63Skill隔离回滚_2026-10-29.md'
assert not note.exists()
note.write_text('''# CLI63 Skill 切换隔离回滚（2026-10-29）

本轮验证 `activate_source63_skill.py` 的文件事务，不验证模型质量或正式入口。正式CLI仍59/local57/r57，CLI63/local61候选完整安装回归继续执行。全部38项原目标关闭条件保持，G33仅增加隔离回滚证据。

## 实际执行与边界

所有夹具在项目E盘 `local/agent-ffmpeg/source63-activation-rollback-r1` 与 `...-r2`。验收门禁输入是明确标注的合成夹具，模型字段仅用于走到文件事务，不能作为真实模型或406合同通过的证据。硬编码C盘发现路径在测试中映射至E盘隔离目录；没有调用真实C盘入口，没有启动子模型进程。入口失败由替身返回非零退出码。

原子临时文件建立、写入、flush/fsync、os.replace、备份、异常分支和恢复均实际操作E盘文件。四个情形均恢复93个Skill文件加命名空间与运行时共95文件的原始字节状态；正式95文件逐项SHA256始终相同。

| 编号 | 失败位置 | 实际原子替换次数（含恢复） | 恢复验证 |
|---|---|---:|---|
| RB01 | 过渡态运行时写入后注入异常 | 4 | 95文件状态逐字节相同 |
| RB02 | 首个Skill文件实际替换后注入异常 | 6 | 已改Skill及元数据恢复，其余文件相同 |
| RB03 | 一个Skill文件及元数据替换后，入口查询替身失败 | 8 | 95文件状态逐字节相同 |
| RB04 | 全部93个Skill文件、命名空间及运行时均已改变后，入口查询替身失败 | 192 | 失败前确实95文件全变；恢复后95文件全量相同 |

RB01–03：[原始证据](evidence/job-enumeration-20261029-r1/activation-rollback-r1/verification.json)。RB04：[全文件证据](evidence/job-enumeration-20261029-r1/activation-rollback-r2/verification.json)。两个证据目录保留实际执行脚本快照；夹具及逐文件备份只在被忽略的E盘本地目录，避免把合成通过收据混进正式门禁。

## 复现

原记录不可覆盖。脚本默认使用新目录并拒绝已有目录；新一轮复现应另命名运行系列并保留原证据。

```powershell
& 'C:/Python313/python.exe' -E -B -u -X utf8 docs/validation/check_source63_activation_rollback.py
& 'C:/Python313/python.exe' -E -B -u -X utf8 docs/validation/prepare_source63_full_rollback_check.py
& 'C:/Python313/python.exe' -E -B -u -X utf8 docs/validation/check_source63_activation_full_rollback.py
```

本轮无新模型推理、无GUI录制或视听质量声明，不把四个文件事务案例计入406功能合同通过数。未覆盖断电/进程被杀、磁盘耗尽、文件ACL/时间戳恢复、恢复步骤本身失败、真实C盘入口退出、设备丢失、长并发和干净主机；正式切换及正式模型入口验收仍须单独执行。
''',encoding='utf-8',newline='\n')
texts={
'README.md':'E盘隔离验证4类切换失败；含全部93个Skill文件及两项元数据共95文件全变后恢复，192次实际原子替换，95文件原始字节恢复且正式95文件不变。门禁与CLI失败均为合成夹具，无真实C盘入口、模型推理或断电恢复验收。',
'README.zh-TW.md':'E盤隔離驗證4類切換失敗；含全部93個Skill檔案及兩項中繼資料共95檔案全變後恢復，192次實際原子替換，95檔案原始位元組恢復且正式95檔案不變。門禁與CLI失敗均為合成夾具，無真實C盤入口、模型推理或斷電恢復驗收。',
'README.en.md':'Four isolated E-drive transition failures checked,including all93 Skill files plus two metadata files changed before rollback. The full case performed192 actual atomic replacements and restored all95 original byte states;95 production files unchanged. Synthetic gates/CLI failure,no real C-drive entry,model inference or power-loss acceptance.'}
for name,body in texts.items():
 p=ROOT/name;t=p.read_text(encoding='utf-8');old=re.findall(r'^\| R\d+ \|.*$',t,re.M);assert len(old)==520
 row='| R521 | CLI63 isolated file-transaction rollback | '+body+' [Evidence](docs/validation/CLI63Skill隔离回滚_2026-10-29.md) |'
 t=t.replace(old[-1],old[-1]+'\n'+row,1);assert re.findall(r'^\| R\d+ \|.*$',t,re.M)[:520]==old
 p.write_text(t,encoding='utf-8',newline='\n')
p=ROOT/'docs/product/GOAL_GAPS_20261025.md';t=p.read_text(encoding='utf-8');head=t.splitlines()[0]
assert 'CLI63Skill隔离回滚_2026-10-29.md' not in t
t=t.replace(head,head+'\n\n2026-10-29 G33：CLI63切换脚本新增[隔离文件事务回滚证据](../validation/CLI63Skill隔离回滚_2026-10-29.md)，四种合成失败条件下实际E盘替换/恢复通过，含全部95文件全变后恢复；正式文件未变。没有真实模型/C盘入口、断电或干净主机验收，不关闭原38项条件。',1)
p.write_text(t,encoding='utf-8',newline='\n')
print('Rollback boundaries documented;three READMEs521 rows;38 original closure cells retained.')
