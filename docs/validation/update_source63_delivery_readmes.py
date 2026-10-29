"""Keep all historical rows and update the three current delivery summaries."""
import re
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
prefix='docs/validation/evidence/job-enumeration-20261029-r1/'
rows={
'README.md':[
('CLI63 full source contracts','406项源码合同全部通过，零失败/错误/跳过；应用283模块与测试192文件冻结一致。安装和Skill另验。','source63-contracts-r1'),
('CLI63 pre-test voice documentation','候选暂存前核对103个CLI61既有WAV哈希，93文件Skill静态校验通过，绑定前其余92文件相同；缺门禁实际拒绝且95正式文件不变。未重新推理、未经人工听审。','voice-preparation-r1'),
('CLI63 native installation','local61候选ZIP原生离线安装及1707载荷/283模块精确核对通过；不等于安装版406或正式Skill验收。','installation-candidate-r1')],
'README.zh-TW.md':[
('CLI63 full source contracts','406項原始碼合同全部通過，零失敗/錯誤/跳過；應用283模組及測試192檔案凍結一致。安裝與Skill另驗。','source63-contracts-r1'),
('CLI63 pre-test voice documentation','候選暫存前核對103個CLI61既有WAV雜湊，93檔案Skill靜態校驗通過，綁定前其餘92檔案相同；缺門禁實際拒絕且95正式檔案不變。未重新推理、未經人工聽審。','voice-preparation-r1'),
('CLI63 native installation','local61候選ZIP原生離線安裝及1707載荷/283模組精確核對通過；不等於安裝版406或正式Skill驗收。','installation-candidate-r1')],
'README.en.md':[
('CLI63 full source contracts','All406 source contracts passed,zero failures/errors/skips;283 app modules and192 test files frozen. Installed and Skill acceptance remain separate.','source63-contracts-r1'),
('CLI63 pre-test voice documentation','Audited103 existing CLI61 WAV hashes before staging;93-file Skill static validation passed,other92 files equal before runtime binding. Missing gates actually refused;95 formal files unchanged. No new inference or human listening acceptance.','voice-preparation-r1'),
('CLI63 native installation','Native offline local61 candidate installation and exact1707-payload/283-module comparison passed. Installed406 and formal Skill acceptance remain separate.','installation-candidate-r1')]}
tops={
'README.md':'**当前开发状态：源码 CLI0.1.63 的406项完整合同及原生进程修复核验通过；local61候选已原生安装、1707载荷和283模块精确一致，安装版回归继续。103音色预览说明已准备在候选实测前写入，未冒充CLI63重新生成。正式Skill仍CLI59/local57/r57，完整目标未完成。**',
'README.zh-TW.md':'**目前開發狀態：原始碼 CLI0.1.63 的406項完整合同及原生程序修復核驗通過；local61候選已原生安裝、1707載荷與283模組精確一致，安裝版回歸繼續。103音色預覽說明已準備在候選實測前寫入，未冒充CLI63重新生成。正式Skill仍CLI59/local57/r57，完整目標未完成。**',
'README.en.md':'**Development status: source CLI0.1.63 passed all406 contracts and native-process fix checks. Native local61 candidate installed with exact1707 payloads/283 modules; installed regression continues. Existing103-voice audition guidance is prepared before candidate testing,not relabeled as new CLI63 inference. Formal Skill remains CLI59/local57/r57;the full goal is open.**'}
for name,items in rows.items():
 p=ROOT/name;text=p.read_text(encoding='utf-8')
 old=re.findall(r'^\| R\d+ \|.*$',text,re.M);assert len(old)==513
 lines=text.splitlines();assert lines[2].startswith('**')
 lines[2]=tops[name]+' [Delivery details](docs/validation/CLI63候选交付门禁_2026-10-29.md)'
 text='\n'.join(lines)+'\n'
 tail='\n'.join(f'| R{514+i} | {title} | {body} [Evidence]({prefix}{directory}/verification.json) |' for i,(title,body,directory) in enumerate(items))
 last=old[-1];assert text.count(last)==1;text=text.replace(last,last+'\n'+tail,1)
 assert re.findall(r'^\| R\d+ \|.*$',text,re.M)[:513]==old
 assert len(re.findall(r'^\| R\d+ \|',text,re.M))==516
 p.write_text(text,encoding='utf-8',newline='\n')
print('Three READMEs updated;all513 historical rows retained;516 current rows.')
