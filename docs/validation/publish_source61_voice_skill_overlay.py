"""Document actual immutable-stage/doc-only checks without claiming activation."""
import hashlib,json,re
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
BASE=ROOT/'docs/validation/evidence/lipsync-timeout-20261029-r1'
NOTE='docs/validation/CLI61Skill音色说明同步_2026-10-29.md'


def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def load(path):return json.loads(path.read_bytes())


def main():
    overlay=load(BASE/'voice-skill-overlay-r1/verification.json')
    assert overlay['status']=='passed' and overlay['static_validation_exit_code']==0
    assert overlay['changed_files']==['references/community-materials.md'] and overlay['other92_tested_files_byte_equal']
    assert overlay['actual_voice_samples']==103 and len(overlay['negative_checks'])==4
    assert overlay['original_tested_stage_unchanged'] and overlay['protected_files_unchanged']==95
    assert sha(ROOT/'docs/validation/source61_voice_skill_overlay.py')==overlay['overlay']['overlay_helper_sha256']
    activation=load(BASE/'activation-gate-check-r2/verification.json')
    assert activation['status']=='passed' and not activation['activated'] and activation['voice103_evidence_required']
    assert activation['activation_runner_sha256']==sha(ROOT/'docs/validation/activate_source61_skill.py')
    registered=load(BASE/'registered-delivery-gate-check-r2/verification.json')
    assert registered['status']=='passed' and registered['protected_files_unchanged']
    for row in registered['checks']:assert sha(ROOT/'docs/validation'/row['runner'])==row['SHA256']
    loop=load(BASE/'staged-actual-case-r1/verification.json')
    gpu=load(BASE/'staged61-gpu-r1/verification.json')
    assert loop['status']=='passed' and loop['actual_PowerShell_entry'] and loop['complete_source_installed_PCM_equal']
    assert loop['complete_repaired_PCM_bytes']==2557440 and loop['complete_package_recipe_repair_PCM_equal']
    assert gpu['status']=='passed' and gpu['actual_PowerShell_entry'] and gpu['actual_CUDA_model']
    assert gpu['complete_PCM_bytes']==1124160 and gpu['complete_source_installed_PCM_equal'] and gpu['complete_PCM_replay_equal']
    installation=load(BASE/'installation-candidate-r1/verification.json')
    assert all(sha(p)==h for p,h in installation['registered_skill_file_hashes'].items())
    assert load(ROOT/'agent-ffmpeg-local-install-manifest.json')['cli_version']=='0.1.59'
    out=BASE/'voice-overlay-publication-r1';out.mkdir(exist_ok=False)
    (out/'executed-runner.py').write_bytes(Path(__file__).read_bytes())
    texts={
        'README.md':[
            'CLI61候选Skill已通过静态校验及实际PowerShell循环／DF3 CUDA：完整2557440／1124160字节PCM与源码及工程包重放一致；候选MuseTalk与正式切换仍另验。',
            '103音色Skill说明同步已备妥并验证：只变更community-materials说明，其余92个已测试文件相同；静态及四类错误拒绝通过。新版激活仍拒绝缺少候选MuseTalk；95正式文件不变，未假称已同步注册。'],
        'README.zh-TW.md':[
            'CLI61候選Skill已通過靜態校驗及實際PowerShell循環／DF3 CUDA：完整2557440／1124160位元組PCM與原始碼及工程包重播一致；候選MuseTalk及正式切換仍另驗。',
            '103音色Skill說明同步已備妥並驗證：只變更community-materials說明，其餘92個已測試檔案相同；靜態及四類錯誤拒絕通過。新版啟用仍拒絕缺少候選MuseTalk；95正式檔案不變，未假稱已同步註冊。'],
        'README.en.md':[
            'CLI61 candidate Skill passed static validation and actual PowerShell loop/DF3 CUDA cases.All2557440/1124160 PCM bytes match source and package replay.Candidate MuseTalk and formal activation remain separate gates.',
            'The103-voice Skill documentation update is prepared and verified:only community-materials changes,the other92 tested files remain exact.Static validation and four mismatch refusals passed.Activation still rejects missing candidate MuseTalk;95 formal files unchanged.No registered update is claimed.']}
    paths=[]
    for name,values in texts.items():
        p=ROOT/name;text=p.read_text(encoding='utf-8');old=[line for line in text.splitlines() if re.match(r'^\| R\d+ \|',line)]
        assert len(old)==494
        lines=text.splitlines();i=next(i for i,line in enumerate(lines) if line.startswith('| R494 |'))
        for j,value in enumerate(values):lines.insert(i+1+j,f'| R{495+j} | CLI61 Skill candidate | '+value+' [Evidence / sync]('+NOTE+') |')
        text='\n'.join(lines)+'\n';assert all(line in text for line in old)
        p.write_text(text,encoding='utf-8',newline='\n');paths.append(p)
    text='''# CLI61 Skill音色说明同步与冻结验证

本轮发现正式及已测试候选的音色说明仍保留早期“三个音色已生成样音”状态；CLI61独立安装版已实际生成全部103音色，该旧说明需要同步。正式注册当前仍CLI59；本页不声称已经切换。

## 实际完成与待完成

| 编号 | 项目 | 实际证据与状态 |
| --- | --- | --- |
| S01 | 候选静态与PowerShell循环 | 已通过；完整2557440字节PCM、三次重复、未处理主体和工程包配方重做均一致 |
| S02 | 候选PowerShell DF3 CUDA | 已通过；完整1124160字节PCM与源码及工程包相同，无CPU回退 |
| S03 | 候选PowerShell MuseTalk | 独立实际案例另验，终态通过前禁止激活 |
| S04 | 103音色说明 | 已准备为明确的文档补丁，仅修改 `references/community-materials.md`；其余92文件含全部执行脚本保持已测试字节 |
| S05 | 文档补丁静态与错误拒绝 | 完整候选静态通过；错误音色数量、错误音频哈希、执行脚本改动、未知文档路径均被拒绝 |
| S06 | 实际激活与注册入口缺证拒绝 | 新版门禁已实际请求验证；缺少候选MuseTalk时拒绝激活，三个注册案例及最终打包也在未激活时停止；95正式文件未改变 |
| S07 | 正式切换、实际C盘三案例、最终r58包 | 尚待按完整门禁执行，不以文档补丁验证替代 |

原93文件候选及其真实模型证据保持不变。激活程序在完整安装403、源／安装／候选循环、DF3、MuseTalk全部通过后，再读取103个真实WAV及元数据，构造说明补丁并记录前后哈希；只有一个已知Markdown路径可以不同。运行时、启动器、模型与其余92文件不得借文档更新改变。

正式切换保留E盘原文件备份和回滚，维持唯一C盘发现联接；注册清单保存更新后的93文件。随后真实C盘入口案例会同时检查原已测试文件映射、文档唯一差异及103音色证据，再执行实际功能。最终工具包必须包含实际注册后的说明。新说明明确本机试听页位置、音频不随Skill打包、其他机器生成方法、按voice_id选型及内部／未听审边界。

验证脚本首次因将字符串直接传给Path读取而在只读预检处退出，未开始正向校验或激活；原失败保留，修复路径类型后正向及四项拒绝检查通过。该失败属于验证脚本，不是模型失败。

## 原始证据

- [候选实际循环](evidence/lipsync-timeout-20261029-r1/staged-actual-case-r1/verification.json)
- [候选实际DF3 CUDA](evidence/lipsync-timeout-20261029-r1/staged61-gpu-r1/verification.json)
- [文档唯一差异、静态及四项拒绝](evidence/lipsync-timeout-20261029-r1/voice-skill-overlay-r1/verification.json)
- [只读预检路径类型失败](evidence/lipsync-timeout-20261029-r1/voice-skill-overlay-preflight-r1/verification.json)
- [新版实际激活缺证拒绝](evidence/lipsync-timeout-20261029-r1/activation-gate-check-r2/verification.json)
- [新版三个注册入口及打包拒绝](evidence/lipsync-timeout-20261029-r1/registered-delivery-gate-check-r2/verification.json)
- [全部103音色及本地试听流程](CLI61全音色试听_2026-10-29.md)

没有新增公开Skill入口或模型下载，未使用Docker／WSL。103项样音生成、自动音频核验及文档同步均不代表人类听审、自然口型或完整剪映等价已完成，38组关闭条件保持。
'''
    p=ROOT/NOTE;p.write_text(text,encoding='utf-8',newline='\n');paths.append(p)
    report=dict(status='passed',README_rows=496,previous494_rows_preserved=True,
                staged_actual_loop_and_DF3_passed=True,documentation_only_overlay_validated=True,
                other92_files_equal=True,negative_overlay_checks=4,
                protected_files_unchanged=95,formal_activation=False,
                file_hashes={p.relative_to(ROOT).as_posix():sha(p) for p in paths})
    (out/'verification.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='file_hashes'}),flush=True)


if __name__=='__main__':main()
