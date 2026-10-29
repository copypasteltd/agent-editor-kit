"""Record full403 terminal acceptance plus the limited, private visual review."""
import hashlib,json,re,subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'docs/validation/evidence/lipsync-timeout-20261029-r1'
GIT='C:/Users/carzy/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/git/cmd/git.exe'
NOTE='docs/validation/CLI61完整源码验收_2026-10-29.md'

def load(p):return json.loads(p.read_bytes())
def sha(p):return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def main():
    previous=load(ROOT/'local/agent-ffmpeg/source61-delivery-checks-commit-r1/verification.json')
    assert previous['status']=='passed'
    r=load(BASE/'source61-contracts-r1/verification.json')
    assert r['status']=='passed' and r['tests']==403 and r['cli_version']=='0.1.61'
    assert r['frozen_equal'] and r['failures']==r['errors']==r['skipped']==0
    assert all(sha(ROOT/p)==h for p,h in r['file_hashes'].items())
    preview=load(BASE/'private-frame-preview-r1/verification.json')
    review=load(BASE/'private-frame-preview-r1/agent-visual-review.json')
    assert preview['status']=='passed' and sha(preview['contact_sheet'])==preview['contact_sheet_sha256']
    assert review['status']=='reviewed-with-limitations' and review['contact_sheet_sha256']==preview['contact_sheet_sha256']
    assert not review['natural_lip_sync_accepted'] and not review['human_review']
    old=load(ROOT/'docs/validation/evidence/music-loop-20261029-r1/installation-candidate-r1/verification.json')
    assert all(sha(p)==h for p,h in old['registered_skill_file_hashes'].items())
    kit=ROOT/'docs/skills/agent-editor-kit-community-unified-skill-r57.zip'
    assert sha(kit)=='46815047a247e32b85d4c5516062486c3f181c54a8d38b9c21710b1757e3b7fd'
    initial=load(BASE/'publication-r1/verification.json')
    goal='docs/product/GOAL_GAPS_20261025.md';assert sha(ROOT/goal)==initial['file_hashes'][goal]
    out=BASE/'source-acceptance-r1';out.mkdir(exist_ok=False)
    texts={
        'README.md':('源码CLI61完整403项服务契约已通过，零失败／错误／跳过，应用与测试冻结一致；独立安装与正式Skill升级仍需另验。',
            '实际查看源图与第0／66／132帧：口形有变化，三张样本未见明显撕裂，但下半脸比源图明显柔化。仅内部抽帧目检，无人类播放／听审或自然质量验收。'),
        'README.zh-TW.md':('原始碼CLI61完整403項服務契約已通過，零失敗／錯誤／跳過，應用與測試凍結一致；獨立安裝及正式Skill升級仍須另驗。',
            '實際查看來源圖與第0／66／132影格：口形有變化，三張樣本未見明顯撕裂，但下半臉比來源圖明顯柔化。僅內部抽幀目檢，無人類播放／聽審或自然品質驗收。'),
        'README.en.md':('Source CLI61 full403 service contracts passed,zero failures/errors/skips,app and tests frozen.Independent installation and registered Skill promotion require separate acceptance.',
            'Actually inspected source/frame0/66/132:mouth shape changes,no obvious tearing in these samples,but the generated lower face is visibly softer than source.Private sampled-frame review only;no human playback,listening or natural-quality acceptance.')}
    for name,(full,visual) in texts.items():
        p=ROOT/name;s=p.read_text(encoding='utf-8')
        oldtext=subprocess.check_output([GIT,'--no-optional-locks','show',previous['refs']['head']+':'+name],cwd=ROOT).decode('utf-8')
        prior=[l for l in oldtext.splitlines() if re.match(r'^\| R\d+ \|',l)]
        assert len(prior)==481 and all(l in s for l in prior)
        lines=s.splitlines();i=next(i for i,l in enumerate(lines) if l.startswith('| R481 |'))
        lines.insert(i+1,'| R482 | CLI61 full source contracts | '+full+' [Evidence]('+NOTE+') |')
        lines.insert(i+2,'| R483 | CLI61 actual frame review / G24 | '+visual+' [Details](docs/validation/CLI61口型抽帧目检_2026-10-29.md) |')
        s='\n'.join(lines)+'\n';i=s.index('\n')+1;s=s[:i]+'\n**'+full+'** [Evidence]('+NOTE+')\n'+s[i:]
        ids=re.findall(r'^\| (R\d+) \|',s,re.M);assert len(ids)==len(set(ids))==483
        p.write_text(s,encoding='utf-8',newline='\n')
    doc='''# CLI61 完整源码验收

完整403项服务契约已取得通过终态，零失败／错误／跳过，283个应用模块与192个测试模块在运行前后保持哈希一致。[原始收据](evidence/lipsync-timeout-20261029-r1/source61-contracts-r1/verification.json)。此前CLI60安装400项的1项超时错误码失败保留，没有覆盖或改写失败收据。

口型31、隔离入口31、循环／配乐37、控制19、选材57、语义104为分别执行的组；完整403含部分相同测试，不重复汇总为独立功能总数。真实循环、DF3 CUDA完整PCM、MuseTalk CUDA133帧及完整成片RGBA／PCM工程重放已分别通过，见 [原生核验](CLI61原生交付核验_2026-10-29.md)。

已实际查看源图与生成的0／66／132帧：口形变化，但下半脸明显柔化，G24自然细节与感知质量仍有差距。抽帧／完整数据重放都不替代自然动态、人类连续播放或听审；[独立目检记录](CLI61口型抽帧目检_2026-10-29.md)保留该限制。媒体权利仍为internal／unverified，本轮不公开新口型视频。

95个正式文件及r57 ZIP哈希不变。正式入口仍CLI59／local57／r57，旧候选CLI60／local58未晋升。构建CLI61／local59后仍须验证新安装版各组、真实模型和完整工程案例，再验统一Skill入口与最终工具包；源码通过不等于安装交付通过。构建脚本的缺证拒绝已有实际证据，不能绕过门禁。

完整产品38项关闭条件保持原文，未宣称完整剪映等价。
'''
    (ROOT/NOTE).write_text(doc,encoding='utf-8',newline='\n')
    paths=[ROOT/n for n in texts]+[ROOT/NOTE,ROOT/'docs/validation/CLI61口型抽帧目检_2026-10-29.md']
    report=dict(status='passed',source_cli='0.1.61',full_contracts=403,failures=0,errors=0,skipped=0,
        registered_skill_cli='0.1.59',protected_files_unchanged=95,r57_unchanged=True,
        all_goal_conditions_unchanged=True,README_rows=483,previous481_rows_preserved=True,
        agent_sampled_visual_review=True,natural_lip_sync_accepted=False,full_goal_closed=False,
        file_hashes={p.relative_to(ROOT).as_posix():sha(p) for p in paths})
    (out/'verification.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8');print(json.dumps({k:v for k,v in report.items() if k!='file_hashes'}),flush=True)

if __name__=='__main__':main()
