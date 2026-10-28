"""Record actual terminal receipts and correct premature case-run interpretation."""
from pathlib import Path
import hashlib,json,re
ROOT=Path(__file__).resolve().parents[1];BASE=ROOT/'docs/validation/evidence/gpu-gamut-20261029-r1'
def load(p):return json.loads(Path(p).read_bytes())
def write(p,s):Path(p).write_text(s,encoding='utf8',newline='\n')
def main():
    out=BASE/'terminal-followup-r1';out.mkdir(exist_ok=False);(out/'executed-generator.py').write_bytes(Path(__file__).read_bytes())
    pins={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (ROOT/'product/src/ai_ad_editor').glob('*.py')}
    for name in ('case-r1','case-r2'):
        v=load(BASE/name/'verification.json');assert v['status']=='passed' and v['source_files']==pins and v['calls']==18
    t=load(BASE/'installed-measure-r1/verification.json');assert t['status']=='passed' and t['tests']==70 and t['skipped']==0 and t['product_files']==pins and t['frozen_equal']
    assert t['installed'] and Path(t['installed']).resolve()==Path(load(BASE/'installation-final-r1/verification.json')['installed']).resolve()
    write(BASE/'case-r1/run-status.json',json.dumps(dict(status='passed',complete_verification_receipt=True,successful_calls=18,source_files=278,
        correction='Earlier incomplete observation was wrongly documented as interrupted; actual terminal receipt proves passed. Case r2 is a second execution of the same case, not a separate functional acceptance.',counted_as_one_case_with='case-r2'),ensure_ascii=False,indent=2)+'\n')
    row='| R358 | CLI52 native candidate installed HDR/GPU/measurement | 70/70; no failures/errors/skips; all 278 source files frozen | [raw](docs/validation/evidence/gpu-gamut-20261029-r1/installed-measure-r1/verification.json) | independent candidate installation; registered Skill remains CLI51; installed compatibility pending |'
    preserved={}
    descriptions={'':'候选安装版70项专项已通过；源码与安装版352项兼容回归仍在运行，统一Skill尚未切换。',
        '.zh-TW':'候選安裝版70項專項已通過；源碼與安裝版352項相容回歸仍在執行，統一Skill尚未切換。',
        '.en':'The candidate installation passed its separate 70-test group. Source and installed 352-test compatibility runs are still active; the unified Skill has not switched.'}
    for suffix in ('','.zh-TW','.en'):
        p=ROOT/('README'+suffix+'.md');s=p.read_text('utf8');old=re.findall(r'^\| R\d+ .*$',s,re.M);assert len(old)==357
        s=s.replace(old[-1],old[-1]+'\n'+row,1)
        s=s.replace('<!-- /gpu-gamut-source-current -->',descriptions[suffix]+'\n\n<!-- /gpu-gamut-source-current -->',1)
        assert re.findall(r'^\| R\d+ .*$',s,re.M)[:357]==old;write(p,s);preserved[p.name]=357
    p=ROOT/'docs/validation/GPU色域映射源码实测_2026-10-29.md';s=p.read_text('utf8').replace('候选安装版专项/兼容、实际注册Skill案例、统一Skill及kit同步','候选安装版兼容回归、实际注册Skill案例、统一Skill及kit同步')
    s+='\n终态补记：候选安装70/70通过，278模块冻结一致，见D07/R358。[记录与更正](evidence/gpu-gamut-20261029-r1/terminal-followup-r1/verification.json)。C63 r1/r2均通过，只计一个案例能力；两个352项兼容组仍需读取终态。\n';write(p,s)
    p=ROOT/'docs/releases/CLI_0.1.52_SOURCE.md';s=p.read_text('utf8');s+='\n候选安装版专项已完成：[70/70通过、无失败/跳过](../validation/evidence/gpu-gamut-20261029-r1/installed-measure-r1/verification.json)。安装版352项兼容组仍在运行，统一Skill保持51。\n';write(p,s)
    result=dict(status='passed',installed_tests=70,installed_source_files=278,case_r1_actual_terminal_status='passed',case_r2_actual_terminal_status='passed',same_case_not_double_counted=True,previous_history_rows_preserved=preserved,current_R_rows=358,registered_skill_cli='0.1.51',compatibility_status='running-not-counted-as-passed',goal_complete=False)
    write(out/'verification.json',json.dumps(result,ensure_ascii=False,indent=2)+'\n');print(json.dumps(result,ensure_ascii=False))
if __name__=='__main__':main()
