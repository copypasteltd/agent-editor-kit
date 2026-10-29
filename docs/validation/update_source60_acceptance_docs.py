"""Publish terminal source60 contracts and actual non-mutating Skill gate evidence."""
import json
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'docs/validation/evidence/music-loop-20261029-r1'

def main():
    contract=json.loads((BASE/'source60-contracts-r1/verification.json').read_bytes())
    assert contract['status']=='passed' and contract['tests']==400 and contract['frozen_equal']
    assert contract['failures']==contract['errors']==contract['skipped']==0
    gate=json.loads((BASE/'stage-gate-check-r1/verification.json').read_bytes())
    assert gate['status']=='passed' and gate['protected_files']==95 and gate['live_skill_unchanged']
    texts={
      'README.md':[
        '| R471 | CLI60完整源码契约终态 | 400通过，零失败／错误／跳过；283应用模块与192测试模块冻结一致；[收据](docs/validation/evidence/music-loop-20261029-r1/source60-contracts-r1/verification.json)。独立安装另验 |',
        '| R472 | CLI60统一Skill交付拦截 | 缺少安装与真实案例前置收据时实际返回2，95个正式配置／Skill文件不变且不生成候选；[证据](docs/validation/evidence/music-loop-20261029-r1/stage-gate-check-r1/verification.json)。正式Skill仍59 |'],
      'README.en.md':[
        '| R471 | CLI60 complete source contracts | 400 passed;zero failures/errors/skips;283 application and192 test modules frozen;[receipt](docs/validation/evidence/music-loop-20261029-r1/source60-contracts-r1/verification.json).Independent installation is separate |',
        '| R472 | CLI60 Skill delivery gate | Actual exit2 with missing install/case receipts;95 formal configuration/Skill files unchanged,no candidate generated;[proof](docs/validation/evidence/music-loop-20261029-r1/stage-gate-check-r1/verification.json).Registered Skill remains59 |'],
      'README.zh-TW.md':[
        '| R471 | CLI60完整原始碼契約終態 | 400通過，零失敗／錯誤／跳過；283應用模組與192測試模組凍結一致；[收據](docs/validation/evidence/music-loop-20261029-r1/source60-contracts-r1/verification.json)。獨立安裝另驗 |',
        '| R472 | CLI60統一Skill交付攔截 | 缺少安裝與實際案例前置收據時實際回傳2，95個正式設定／Skill檔案不變且不產生候選；[證據](docs/validation/evidence/music-loop-20261029-r1/stage-gate-check-r1/verification.json)。正式Skill仍59 |']}
    preserved={}
    for name,rows in texts.items():
        p=ROOT/name;text=p.read_text(encoding='utf-8');lines=text.splitlines()
        old=[x for x in lines if re.match(r'^\| R\d+ \|',x)]
        assert len(old)==470 and not any(x.startswith('| R471 |') for x in lines)
        i=next(i for i,x in enumerate(lines) if x.startswith('| R470 |'))
        lines[i+1:i+1]=rows;updated='\n'.join(lines)+'\n'
        assert all(x in updated for x in old);p.write_text(updated,encoding='utf-8');preserved[name]=len(old)
    p=ROOT/'docs/validation/CLI60循环修复_2026-10-29.md';text=p.read_text(encoding='utf-8')
    text=text.replace('以本系列 `source60-contracts-r1/verification.json` 的实际终态为准；未出收据不计完成',
        '[400项通过](evidence/music-loop-20261029-r1/source60-contracts-r1/verification.json)，零失败／错误／跳过，耗时1460.821秒，冻结一致')
    text=text.replace('以 `source60-gpu-r1/verification.json` 实际终态为准；仅受控噪声，不替代其它模型验收',
        '[实际通过](evidence/music-loop-20261029-r1/source60-gpu-r1/verification.json)，RTX3060／4次前向／完整1124160字节PCM重放一致／12.25dB受控MSE改善；不替代自然质量或其它模型验收')
    text+='''

## 后续交付工具的实际检查

`stage_source60_skill.py` 在缺少独立安装、完整安装回归及真实案例收据时实际返回2，没有生成候选；95个正式文件摘要不变。[实际拒绝收据](evidence/music-loop-20261029-r1/stage-gate-check-r1/verification.json)。

已准备循环修复及CUDA的真实PowerShell候选测试脚本，并做语法检查。生成脚本首轮只替换了多行prefix赋值的第一行，导致缩进错误；该文件在编译失败前未写入。改为替换整个赋值区间后语法通过，已生成的循环案例文件按相同内容校验后保留。此修复只涉及验证工具，不修改冻结的程序或测试，也不算实际Skill入口已通过。

CLI60/local58离线包正在独立构建；正式Skill保持59。实际包的构建、安装及后续测试收据分别记录，不以工具准备或语法通过替代。
'''
    p.write_text(text,encoding='utf-8')
    out=BASE/'acceptance-docs-r1';out.mkdir(exist_ok=False)
    (out/'verification.json').write_text(json.dumps(dict(status='passed',preserved_R_rows=preserved,
        current_R_rows=472,source_contract_tests=400,formal_skill_cli='0.1.59',
        stage_gate_check_only=True,actual_candidate_entry_accepted=False),ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(status='passed',current_R_rows=472)),flush=True)

if __name__=='__main__':main()
