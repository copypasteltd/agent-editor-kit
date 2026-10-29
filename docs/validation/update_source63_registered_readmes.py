"""Record real installed semantic acceptance and guarded final-kit preparation."""
import json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];BASE=ROOT/'docs/validation/evidence/job-enumeration-20261029-r1'
r=json.loads((BASE/'installed63-semantic-r1/verification.json').read_bytes())
assert r['status']=='passed' and r['tests']==104 and r['frozen_equal'] and r['source_and_installed_equal']
assert r['failures']==r['errors']==r['skipped']==0
link='docs/validation/evidence/job-enumeration-20261029-r1/'
texts={
'README.md':[
'正式C盘入口循环/DF3/MuseTalk复核与r58工具包独立解包流程已准备；未激活时复核和构建均实际拒绝/exit2，95正式文件不变。仅编译及拒绝检查，不是实际正式入口模型或工具包通过；循环功能手册同步CLI63候选边界。',
'104项安装版语义/决策/任务/工程包/升级回归全部通过，零失败/错误/跳过，源码与安装相同且冻结。406完整合同和真实模型仍另验，非独立Agent成功率或真实语义质量接受。'],
'README.zh-TW.md':[
'正式C盤入口循環/DF3/MuseTalk複核與r58工具包獨立解包流程已準備；未啟用時複核和構建均實際拒絕/exit2，95正式檔案不變。僅編譯與拒絕檢查，不是真實正式入口模型或工具包通過；循環功能手冊同步CLI63候選邊界。',
'104項安裝版語義/決策/任務/專案包/升級回歸全部通過，零失敗/錯誤/跳過，原始碼與安裝相同且凍結。406完整合同與真實模型仍另驗，非獨立Agent成功率或真實語義品質接受。'],
'README.en.md':[
'Prepared real registered C-drive loop/DF3/MuseTalk checks and independent r58 kit extraction. Before activation,both acceptance and packaging actually refused/exit2;95 formal files unchanged. Compile/refusal checks only,no registered neural-case or kit pass. Loop manual now describes CLI63 candidate boundaries.',
'All104 installed semantic/decision/job/package/upgrade regressions passed,zero failures/errors/skips,source/installed equal and frozen. Full406 and actual models remain separate;not independent Agent success-rate or real semantic-quality acceptance.']}
for name,items in texts.items():
 p=ROOT/name;t=p.read_text(encoding='utf-8');old=re.findall(r'^\| R\d+ \|.*$',t,re.M);assert len(old)==518
 rows=f'| R519 | CLI63 registered-entry and final-kit preparation | {items[0]} [Evidence]({link}registered-preflight-r1/verification.json) |\n| R520 | CLI63 installed semantic regression | {items[1]} [Evidence]({link}installed63-semantic-r1/verification.json) |'
 t=t.replace(old[-1],old[-1]+'\n'+rows,1);assert re.findall(r'^\| R\d+ \|.*$',t,re.M)[:518]==old
 p.write_text(t,encoding='utf-8',newline='\n')
print('Three READMEs now520 rows;all518 previous rows retained.')
