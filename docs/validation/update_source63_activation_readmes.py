"""Publish actual activation refusals and installed groups without promotion."""
import json,re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2];BASE=ROOT/'docs/validation/evidence/job-enumeration-20261029-r1'
for group,count in [('bootstrap',31),('loop',37),('control',26),('selection',57)]:
 r=json.loads((BASE/f'installed63-{group}-r1/verification.json').read_bytes())
 assert r['status']=='passed' and r['tests']==count and r['source_and_installed_equal'] and r['frozen_equal']
 assert r['failures']==r['errors']==r['skipped']==0
link='docs/validation/evidence/job-enumeration-20261029-r1/activation-preflight-r1/verification.json'
details='docs/validation/CLI63候选交付门禁_2026-10-29.md'
texts={
'README.md':[
'正式切换脚本要求注册最终实测93文件，禁止测后文档覆盖；缺门禁时普通/--apply两种调用均实际返回pending/exit2，95正式文件不变；真实原子替换及失败临时文件清理通过，完整切换/回滚尚未执行。',
'安装版隔离启动31、循环37、进程控制26、选材57各组通过，源码/安装模块相同、冻结一致，分组零失败/错误/跳过；104语义、406完整合同与真实模型继续另验。'],
'README.zh-TW.md':[
'正式切換腳本要求註冊最終實測93檔案，禁止測後文件覆蓋；缺門禁時一般/--apply兩種呼叫均實際回傳pending/exit2，95正式檔案不變；真實原子替換及失敗暫存檔案清理通過，完整切換/回滾尚未執行。',
'安裝版隔離啟動31、循環37、程序控制26、選材57各組通過，原始碼/安裝模組相同、凍結一致，各組零失敗/錯誤/跳過；104語義、406完整合同及真實模型繼續另驗。'],
'README.en.md':[
'Activation requires the exact93 tested files,with no post-test documentation overlay. Both ordinary and --apply calls actually refused missing gates with pending/exit2;95 formal files unchanged. Actual atomic replacement and failed-replace temporary cleanup passed;full transition/rollback not executed.',
'Installed bootstrap31,loop37,process-control26 and selection57 groups each passed,source/installed modules equal and frozen,zero failures/errors/skips per group. Semantic104,full406 and actual models remain separate gates.']}
for name,items in texts.items():
 p=ROOT/name;t=p.read_text(encoding='utf-8');old=re.findall(r'^\| R\d+ \|.*$',t,re.M);assert len(old)==516
 rows=f'| R517 | CLI63 exact-tested-byte activation preparation | {items[0]} [Evidence]({link}) |\n| R518 | CLI63 installed regression groups | {items[1]} [Details]({details}#cli63-本地候选安装) |'
 t=t.replace(old[-1],old[-1]+'\n'+rows,1)
 assert re.findall(r'^\| R\d+ \|.*$',t,re.M)[:516]==old
 p.write_text(t,encoding='utf-8',newline='\n')
print('Three READMEs now518 rows;all516 prior rows retained.')
