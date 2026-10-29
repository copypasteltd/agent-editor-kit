"""Publish terminal installed61 evidence without promoting pending cases."""
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT/'docs/validation/evidence/lipsync-timeout-20261029-r1'
NOTE = 'docs/validation/CLI61安装版实际案例_2026-10-29.md'


def load(p): return json.loads(p.read_bytes())


def sha(p):
    with Path(p).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def main():
    semantic = load(BASE/'installed61-semantic-r1/verification.json')
    assert semantic['status']=='passed' and semantic['tests']==104 and semantic['frozen_equal']
    assert semantic['source_and_installed_equal'] and semantic['failures']==semantic['errors']==semantic['skipped']==0
    assert all(sha(ROOT/p)==h for p,h in semantic['file_hashes'].items())
    gpu = load(BASE/'installed61-gpu-r1/verification.json')
    assert gpu['status']=='passed' and gpu['actual_CUDA_model'] and not gpu['source_fallback']
    assert gpu['complete_PCM_bytes']==1124160 and gpu['complete_PCM_replay_equal'] and gpu['complete_source_installed_PCM_equal']
    assert gpu['native_model']['model_forwards']==4 and not gpu['native_model']['CPU_fallback']
    loop = load(BASE/'installed-actual-case-r1/verification.json')
    assert loop['status']=='passed' and loop['complete_repaired_PCM_bytes']==2557440
    assert loop['complete_source_installed_PCM_equal'] and loop['complete_package_recipe_repair_PCM_equal']
    assert loop['unprocessed_body_PCM_equal'] and loop['complete_repeated_PCM_equal']
    negative = load(BASE/'registered-delivery-gate-check-r1/verification.json')
    assert negative['status']=='passed' and negative['protected_files_unchanged'] and negative['protected_files']==95
    assert negative['no_case_or_archive_created'] and not negative['activation_performed']
    for row in negative['checks']:
        assert sha(ROOT/'docs/validation'/row['runner'])==row['SHA256'] and row['rejected_before_case']
    install = load(BASE/'installation-candidate-r1/verification.json')
    assert all(sha(p)==h for p,h in install['registered_skill_file_hashes'].items())
    assert load(ROOT/'agent-ffmpeg-local-install-manifest.json')['cli_version']=='0.1.59'
    statuses = {}
    for name in ['installed61-contracts-r1','installed61-lipsync-cuda-r1']:
        p = BASE/name/'verification.json'
        statuses[name] = load(p)['status'] if p.exists() else 'not-terminal'
    out = BASE/'installed-cases-publication-r1'
    out.mkdir(exist_ok=False)
    (out/'executed-runner.py').write_bytes(Path(__file__).read_bytes())
    rows = {
        'README.md': [
            '独立安装版语义104项全部通过，零失败／错误／跳过；283模块与源码及测试冻结一致。',
            '独立安装版DF3实际RTX3060 CUDA四次前向通过；完整1124160字节PCM与源码及工程包重放相同，无CPU回退。受控噪声MSE改善不等于自然听审。',
            '独立安装版循环修复完整2557440字节PCM、三次循环、未处理主体及工程包配方重做均一致；CPU DSP缩短每周期50ms，未宣称神经音乐或听感无缝。',
            '三个正式C盘入口案例和最终打包程序已实际验证缺少激活时提前停止；95正式文件不变，未创建案例／归档。正向入口及最终r58包仍须实际验收。'],
        'README.zh-TW.md': [
            '獨立安裝版語義104項全部通過，零失敗／錯誤／跳過；283模組與原始碼及測試凍結一致。',
            '獨立安裝版DF3實際RTX3060 CUDA四次前向通過；完整1124160位元組PCM與原始碼及工程包重播相同，無CPU回退。受控雜訊MSE改善不等於自然聽審。',
            '獨立安裝版循環修復完整2557440位元組PCM、三次循環、未處理主體及工程包配方重做皆一致；CPU DSP縮短每週期50ms，未宣稱神經音樂或聽感無縫。',
            '三個正式C磁碟入口案例及最終打包程式已實際驗證缺少啟用時提前停止；95正式檔案不變，未建立案例／歸檔。正向入口及最終r58包仍須實際驗收。'],
        'README.en.md': [
            'Independent installed semantic104 passed with zero failures/errors/skips;283 application modules and test hashes frozen against source.',
            'Installed DF3 completed four real RTX3060 CUDA forwards;all1124160 PCM bytes match source and package replay,without CPU fallback.Controlled-noise MSE improvement is not natural listening acceptance.',
            'Installed loop repair verified all2557440 PCM bytes,three repeats,untouched body and package recipe reconstruction.CPU DSP shortens each cycle by50ms;neural music and perceptual seamlessness remain unaccepted.',
            'Three real C-drive entry runners and the final kit builder actually rejected absent activation before creating cases/archives;95 formal files unchanged.Positive registered cases and the final r58 archive still require execution.']}
    paths = []
    for name, values in rows.items():
        p = ROOT/name
        text = p.read_text(encoding='utf-8')
        old = [line for line in text.splitlines() if re.match(r'^\| R\d+ \|',line)]
        assert len(old)==486
        lines = text.splitlines(); index = next(i for i,line in enumerate(lines) if line.startswith('| R486 |'))
        for j,value in enumerate(values):
            lines.insert(index+1+j, f'| R{487+j} | CLI61 installed cases | {value} [Evidence / workflow]({NOTE}) |')
        text = '\n'.join(lines)+'\n'
        assert all(line in text for line in old)
        ids = re.findall(r'^\| (R\d+) \|',text,re.M)
        assert len(ids)==len(set(ids))==490
        p.write_text(text, encoding='utf-8', newline='\n');paths.append(p)
    body = f'''# CLI61 独立安装实际案例与剩余门禁

正式入口仍为 CLI59／local57／r57，安装候选为 CLI61／local59。本轮只发布终态通过的证据，未激活新版Skill。

| 编号 | 实际执行 | 验收范围 | 结果 |
| --- | --- | --- | --- |
| I01 | 安装语义104项 | 独立安装模块加载、测试和283源码模块冻结；零失败／错误／跳过 | 通过 |
| I02 | DF3 RTX3060 CUDA | 实际4次前向、无CPU回退；1124160字节完整PCM与源码及工程包重放相同 | 通过 |
| I03 | 循环修复 | 2557440字节完整PCM、三次重复、未处理主体、工程包迁移后配方重新生成 | 通过 |
| I04 | 正式入口及归档缺证拒绝 | 实际调用三个C盘入口案例程序和最终打包程序；激活缺失时提前停止，95文件未变、无案例／归档产物 | 通过；不是正向功能验收 |
| I05 | 完整安装403项 | 发布时原始收据状态 `{statuses['installed61-contracts-r1']}` | 另按终态验收 |
| I06 | 安装MuseTalk实际CUDA | 发布时原始收据状态 `{statuses['installed61-lipsync-cuda-r1']}` | 另按终态验收 |

## 使用与交付顺序

1. 需要立即试用本次安装候选时，按[独立安装入口与完整使用命令](CLI61独立安装交付_2026-10-29.md)明确调用CLI61目录；旧注册入口暂不提供新循环修复命令。
2. 先登记本地素材及权利，预检参数，生成新资产ID，检查／试听，再挂接时间线。循环交叠每周期缩短50ms，工作格式48kHz双声道16bit；它是CPU DSP，不能代替节拍／乐句重写或听审。[源／输出音频、GIF及配方](../product/MUSIC_LOOP.md)保留。
3. GPU降噪仍须显式登记本地DF3权重和原生CUDA运行时；本轮完整PCM SHA256为 `{gpu['complete_PCM_sha256']}`。受控噪声MSE改善 `{gpu['MSE_improvement_dB']:.6f} dB` 不是自然对白、音乐保真或听审完成。[服务与限制](../product/SPEECH_ENHANCEMENT.md)。
4. 安装403与安装MuseTalk通过后才能生成未注册候选Skill，再执行静态校验及候选PowerShell循环／DF3／MuseTalk三类正向案例。全部通过后才允许原子切换现有唯一Skill入口。
5. 切换后用真实C盘发现路径重新执行三类案例。最终r58包还要独立解包至E盘中文／空格目录、配置四个已有模型包、隔离注册并验证完整谱面PCM、循环配方PCM、ACES像素／PCM／PNG。程序已准备不等于上述正向案例通过。

本轮未公开新的MuseTalk人像／语音素材；其权利记录仍为内部／未核验。源码抽帧所见下半脸柔化及连续播放、自然口型、听审仍开放。38组完整产品关闭条件保持，不宣称剪映全功能完成。

## 原始证据

- [安装语义104](evidence/lipsync-timeout-20261029-r1/installed61-semantic-r1/verification.json)
- [安装实际DF3 CUDA](evidence/lipsync-timeout-20261029-r1/installed61-gpu-r1/verification.json)
- [安装实际循环及完整配方重做](evidence/lipsync-timeout-20261029-r1/installed-actual-case-r1/verification.json)
- [正式入口与打包缺证拒绝](evidence/lipsync-timeout-20261029-r1/registered-delivery-gate-check-r1/verification.json)
'''
    note = ROOT/NOTE;note.write_text(body,encoding='utf-8',newline='\n');paths.append(note)
    guide = ROOT/'docs/validation/CLI61独立安装交付_2026-10-29.md'
    text = guide.read_text(encoding='utf-8'); index = text.index('\n\n')+2
    text = text[:index]+'后续实测：安装语义104、实际DF3 CUDA完整PCM、循环修复完整PCM及配方重做已分别通过；正式C盘入口和归档缺证拒绝也已实测。正式Skill仍59，完整403与MuseTalk按各自终态。[本轮实际证据及交付顺序](CLI61安装版实际案例_2026-10-29.md)。\n\n'+text[index:]
    guide.write_text(text,encoding='utf-8',newline='\n');paths.append(guide)
    report = dict(status='passed', source_cli='0.1.61',candidate_cli='0.1.61',formal_cli='0.1.59',
                  README_rows=490,previous486_rows_preserved=True,protected_files_unchanged=95,
                  installed_semantic_tests=104,actual_installed_DF3=True,actual_installed_loop=True,
                  actual_registered_delivery_negative_checks=4,pending_status_at_publication=statuses,
                  formal_activation=False,file_hashes={p.relative_to(ROOT).as_posix():sha(p) for p in paths})
    (out/'verification.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k!='file_hashes'},ensure_ascii=False),flush=True)


if __name__=='__main__': main()
