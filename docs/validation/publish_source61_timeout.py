"""Publish terminal-only regression evidence and preserve all historical rows."""
import hashlib,json,re,subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'docs/validation/evidence/lipsync-timeout-20261029-r1'
OLD=ROOT/'docs/validation/evidence/music-loop-20261029-r1'
GIT='C:/Users/carzy/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/git/cmd/git.exe'

def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    groups={}
    for group,count in [('lipsync',31),('bootstrap',31),('loop',37)]:
        r=json.loads((BASE/('source61-'+group+'-r1')/'verification.json').read_bytes())
        assert r['status']=='passed' and r['tests']==count and r['frozen_equal']
        assert r['failures']==r['errors']==r['skipped']==0
        assert all(sha(ROOT/p)==pin for p,pin in r['file_hashes'].items())
        groups[group]=count
    failed=json.loads((OLD/'installed60-contracts-r1/verification.json').read_bytes())
    assert failed['status']=='failed' and failed['tests']==400 and failed['failures']==1
    install=json.loads((OLD/'installation-candidate-r1/verification.json').read_bytes())
    protected=install['registered_skill_file_hashes']
    assert len(protected)==95 and all(sha(Path(p))==pin for p,pin in protected.items())
    source=ROOT/'product/src/ai_ad_editor';installed=Path(install['installed'])/'site/ai_ad_editor'
    changed=sorted(p.name for p in source.glob('*.py') if sha(p)!=sha(installed/p.name))
    assert changed==['__init__.py','lipsync_pipeline.py']
    for name in ['staged-actual-case-r1','staged60-gpu-r1']:
        assert json.loads((OLD/name/'verification.json').read_bytes())['status']=='passed'
    out=BASE/'publication-r1';out.mkdir(exist_ok=False)
    note='docs/validation/CLI61口型超时修复_2026-10-29.md'
    values={
        'README.md':'31项口型专项、31项隔离入口、37项循环／配乐分别通过；零失败／错误／跳过，应用与测试冻结一致。403项完整契约另行运行，不计通过。95个正式文件未变；CLI60草稿真实PowerShell循环及CUDA均通过，但不替代失败的400项安装回归。',
        'README.zh-TW.md':'31項口型專項、31項隔離入口、37項循環／配樂分別通過；零失敗／錯誤／跳過，應用與測試凍結一致。403項完整契約另行執行，不計通過。95個正式檔案未變；CLI60草稿真實PowerShell循環及CUDA均通過，但不替代失敗的400項安裝回歸。',
        'README.en.md':'Lip-sync31,isolated bootstrap31,and loop/score37 passed separately,zero failures/errors/skips;app and tests frozen.403 full contracts run separately and are not counted as passed.95 registered files unchanged;CLI60 draft PowerShell loop and CUDA passed but do not replace the failed installed400 gate.'}
    for f,text in values.items():
        p=ROOT/f;s=p.read_text(encoding='utf-8')
        old=subprocess.check_output([GIT,'--no-optional-locks','show','3989e4a166c46daa576880c6544a86e5080d9f5d:'+f],cwd=ROOT).decode('utf-8')
        prior=[x for x in old.splitlines() if re.match(r'^\| R\d+ \|',x)]
        assert len(prior)==473 and all(x in s for x in prior)
        lines=s.splitlines();i=next(i for i,l in enumerate(lines) if l.startswith('| R476 |'))
        lines.insert(i+1,'| R477 | CLI61 source timeout acceptance | '+text+' [Evidence]('+note+') |')
        p.write_text('\n'.join(lines)+'\n',encoding='utf-8',newline='\n')
        ids=re.findall(r'^\| (R\d+) \|',p.read_text(encoding='utf-8'),re.M)
        assert len(ids)==len(set(ids))==477
    p=ROOT/note
    with p.open('a',encoding='utf-8',newline='\n') as f:
        f.write('\n## 本轮专项终态\n\n31项口型专项、31项隔离入口及37项循环／配乐回归分别通过，零失败／错误／跳过，运行前后应用与测试哈希一致。三组分别计数，不与403项完整回归叠加为独立功能数量。完整回归仍以其终态收据为准。95个正式文件与旧安装构建快照一致。\n')
    gaps=ROOT/'docs/product/GOAL_GAPS_20261025.md'
    prior=subprocess.check_output([GIT,'--no-optional-locks','show','3989e4a166c46daa576880c6544a86e5080d9f5d:docs/product/GOAL_GAPS_20261025.md'],cwd=ROOT)
    assert prior.decode('utf-8').splitlines()==gaps.read_text(encoding='utf-8').splitlines()
    paths=[ROOT/f for f in values]+[ROOT/note,ROOT/'docs/product/LIP_SYNC.md',gaps]
    report=dict(status='passed',source_cli='0.1.61',installed_candidate_cli='0.1.60',formal_cli='0.1.59',
        terminal_groups=groups,installed60_contracts_status='failed',source61_full_contracts_accepted=False,
        formal_skill_unchanged_files=95,changed_source_modules=changed,README_rows=477,
        previous473_rows_preserved=True,all_goal_conditions_unchanged=True,full_goal_closed=False,
        file_hashes={p.relative_to(ROOT).as_posix():sha(p) for p in paths})
    (out/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='file_hashes'}),flush=True)

if __name__=='__main__':main()
