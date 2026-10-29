"""Add explicit development status and evidence without deleting README history."""
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
BEGIN, END = '<!-- aek-cli64-current -->', '<!-- /aek-cli64-current -->'
DOCUMENT = 'docs/product/NEURAL_MUSIC_GENERATION.md'
UNIT = 'docs/validation/evidence/music-generation-20261030-r5/unit/verification.json'
BOOT = 'docs/validation/evidence/music-generation-20261030-r1/source64-bootstrap-r1/verification.json'
ACQUIRED = 'docs/validation/evidence/acestep15-admission-20261029-r1/acquisition-r1/verification.json'
BASE = 'docs/validation/evidence/music-generation-20261030-r1/'
GROUP_ROWS = {
    'README.md': [
        ('R532', 'CLI64配乐回归组', '62通过，含新增25项与既有循环18／谱面19；该25项与R529重叠，不累计。', 'source64-music-r1/verification.json'),
        ('R533', 'CLI64原生进程与执行预算', '26通过；原生子进程归属、清理与预算，不等于新增模型中途取消已经验收。', 'source64-control-r1/verification.json'),
        ('R534', 'CLI64语义服务兼容回归', '104通过，零失败／错误／跳过，源码冻结一致；不是自然语义准确率。', 'source64-semantic-r1/verification.json'),
        ('R535', 'CLI64素材选型与分镜兼容回归', '57通过，零失败／错误／跳过，源码冻结一致；不是新模型质量验收。', 'source64-selection-r1/verification.json'),
        ('R536', 'CLI64实际CLI启动前失败处理', '6通过：取消、无效超时／存储／时钟／歌词和缺适配器；工程与权利台账原样，模型前向0。', 'source64-preflight-r1/verification.json')],
    'README.zh-TW.md': [
        ('R532', 'CLI64配樂回歸組', '62通過，含新增25項與既有循環18／譜面19；該25項與R529重疊，不累計。', 'source64-music-r1/verification.json'),
        ('R533', 'CLI64原生進程與執行預算', '26通過；原生子進程歸屬、清理與預算，不等於新增模型中途取消已經驗收。', 'source64-control-r1/verification.json'),
        ('R534', 'CLI64語義服務相容回歸', '104通過，零失敗／錯誤／跳過，原始碼凍結一致；不是自然語義準確率。', 'source64-semantic-r1/verification.json'),
        ('R535', 'CLI64素材選型與分鏡相容回歸', '57通過，零失敗／錯誤／跳過，原始碼凍結一致；不是新模型品質驗收。', 'source64-selection-r1/verification.json'),
        ('R536', 'CLI64實際CLI啟動前失敗處理', '6通過：取消、無效逾時／儲存／時鐘／歌詞和缺適配器；工程與權利台帳原樣，模型前向0。', 'source64-preflight-r1/verification.json')],
    'README.en.md': [
        ('R532', 'CLI64 music regression group', '62 passed: 25 new contracts plus 18 loop and 19 score checks. The 25 overlap R529; do not add them twice.', 'source64-music-r1/verification.json'),
        ('R533', 'CLI64 native process and operation budgets', '26 passed for owned process cleanup and budgets. New model cancellation during inference remains separate.', 'source64-control-r1/verification.json'),
        ('R534', 'CLI64 semantic service compatibility', '104 passed, no failures/errors/skips, frozen source unchanged. Not a natural semantic accuracy score.', 'source64-semantic-r1/verification.json'),
        ('R535', 'CLI64 selection and storyboard compatibility', '57 passed, no failures/errors/skips, frozen source unchanged. Not new model quality acceptance.', 'source64-selection-r1/verification.json'),
        ('R536', 'CLI64 actual pre-launch CLI failures', 'Six passed: cancellation, invalid timeout/storage/clock/lyrics and missing adapter. Project/rights unchanged; zero model forwards.', 'source64-preflight-r1/verification.json')],
}
DELIVERY_ROWS = {
    'README.md': [
        ('R537', 'CLI64独立候选包与安装', 'local62离线构建／安装通过，288应用模块逐字节匹配源码；正式入口63不变。实际音乐与完整安装验收另验。', 'candidate-r1/verification.json'),
        ('R538', 'CLI64统一Skill候选入口', '未注册94文件／17内部模块，正文校验、脚本编译、实际PowerShell version／help通过；本项没有运行模型。', 'skill-stage-r1/verification.json')],
    'README.zh-TW.md': [
        ('R537', 'CLI64獨立候選套件與安裝', 'local62離線構建／安裝通過，288應用模組逐位元組符合原始碼；正式入口63不變。實際音樂與完整安裝驗收另驗。', 'candidate-r1/verification.json'),
        ('R538', 'CLI64統一Skill候選入口', '未註冊94檔案／17內部模組，正文校驗、腳本編譯、實際PowerShell version／help通過；本項沒有執行模型。', 'skill-stage-r1/verification.json')],
    'README.en.md': [
        ('R537', 'CLI64 independent candidate and installation', 'local62 built/installed offline; all 288 application modules match source bytes. Registered63 unchanged; actual music and full installed acceptance are separate.', 'candidate-r1/verification.json'),
        ('R538', 'CLI64 unified Skill candidate entry', 'Unregistered94 files/17 internal modules: frontmatter, script compilation and actual PowerShell version/help passed. No model execution in this check.', 'skill-stage-r1/verification.json')],
}
CURRENT_ROWS = {
    'README.md': [
        ('R539', 'CLI64真实音乐生成超时与回收', '实际生成失败：1800秒工作进程预算内无模型结果；完整命令2398秒。清理检查通过，原工作进程退出／临时目录清空／未发布音频；不是配乐生成通过。', 'timeout-piano3-r1/verification.json'),
        ('R540', 'CLI64安装版配乐回归', '62通过，独立安装模块与源码一致，无源码回落；包含R529的25项，不重复累计。', 'installed64-music-r1/verification.json'),
        ('R541', 'CLI64安装版工作进程隔离', '33通过，零失败／错误／跳过，安装与源码字节冻结一致；无音乐模型推理。', 'installed64-bootstrap-r1/verification.json'),
        ('R542', 'CLI64安装版执行控制', '26通过，零失败／错误／跳过，安装与源码字节冻结一致；新音乐的中途取消另验。', 'installed64-control-r1/verification.json')],
    'README.zh-TW.md': [
        ('R539', 'CLI64真實音樂生成逾時與回收', '實際生成失敗：1800秒工作進程預算內無模型結果；完整命令2398秒。清理檢查通過，原工作進程退出／暫存目錄清空／未發布音訊；不是配樂生成通過。', 'timeout-piano3-r1/verification.json'),
        ('R540', 'CLI64安裝版配樂回歸', '62通過，獨立安裝模組與原始碼一致，無原始碼回落；包含R529的25項，不重複累計。', 'installed64-music-r1/verification.json'),
        ('R541', 'CLI64安裝版工作進程隔離', '33通過，零失敗／錯誤／跳過，安裝與原始碼位元組凍結一致；無音樂模型推理。', 'installed64-bootstrap-r1/verification.json'),
        ('R542', 'CLI64安裝版執行控制', '26通過，零失敗／錯誤／跳過，安裝與原始碼位元組凍結一致；新音樂的中途取消另驗。', 'installed64-control-r1/verification.json')],
    'README.en.md': [
        ('R539', 'CLI64 actual music timeout and cleanup', 'Generation FAILED: no model result within the 1800s worker budget; full command2398s. Cleanup passed: original worker exited, workspace empty, no audio published. Not music-generation acceptance.', 'timeout-piano3-r1/verification.json'),
        ('R540', 'CLI64 installed music regression', '62 passed with byte-identical installed modules and no source fallback. Includes the25 R529 contracts; do not add twice.', 'installed64-music-r1/verification.json'),
        ('R541', 'CLI64 installed worker isolation', '33 passed, zero failures/errors/skips, frozen installed/source bytes equal. No music model inference.', 'installed64-bootstrap-r1/verification.json'),
        ('R542', 'CLI64 installed execution control', '26 passed, zero failures/errors/skips, frozen installed/source bytes equal. New music cancellation during inference remains separate.', 'installed64-control-r1/verification.json')],
}
WORDS = {
    'README.md':dict(
        status='**CLI0.1.64 开发中：新增原生GPU神经配乐接口。** 25项请求／BF16载荷／配方检查及33项工作进程隔离检查已通过；真实生成、安装和Skill更新分别验收。当前正式入口仍为下述CLI0.1.63。',
        label='完整配乐接口、参数与边界',
        feature='原生GPU神经配乐（开发中）',
        detail='显式风格／歌词请求、固定ACE-Step1.5 Turbo、CUDA前向证据、原生48kHz双声道Float32 WAV、生成配方与独立音轨。',
        boundary='CLI64开发接口；正式63暂不含。不是MIDI、乐器分轨或已验收自然音质。',
        rows=[
            ('R529','CLI64配乐请求与载荷检查','25通过；含BF16、大词表、原生时钟、歌词、配方及伪GPU响应拒绝；无模型推理。',UNIT),
            ('R530','CLI64工作进程隔离','33通过，含新增音乐进程的依赖归属与拒绝外部应用加载；无模型推理。',BOOT),
            ('R531','ACE1.5权重与原生接口准入','4组件完整SHA256校验；673运行文件覆盖393实际导入文件；本项不是音乐生成或听审通过。',ACQUIRED)]),
    'README.zh-TW.md':dict(
        status='**CLI0.1.64 開發中：新增原生GPU神經配樂介面。** 25項請求／BF16載荷／配方檢查及33項工作進程隔離檢查已通過；真實生成、安裝和Skill更新分別驗收。目前正式入口仍為下述CLI0.1.63。',
        label='完整配樂介面、參數與邊界',
        feature='原生GPU神經配樂（開發中）',
        detail='明確風格／歌詞請求、固定ACE-Step1.5 Turbo、CUDA前向證據、原生48kHz雙聲道Float32 WAV、生成配方與獨立音軌。',
        boundary='CLI64開發介面；正式63暫不含。不是MIDI、樂器分軌或已驗收自然音質。',
        rows=[
            ('R529','CLI64配樂請求與載荷檢查','25通過；含BF16、大詞表、原生時鐘、歌詞、配方及偽GPU回應拒絕；無模型推理。',UNIT),
            ('R530','CLI64工作進程隔離','33通過，含新增音樂進程的依賴歸屬與拒絕外部應用載入；無模型推理。',BOOT),
            ('R531','ACE1.5權重與原生介面準入','4組件完整SHA256校驗；673執行檔案涵蓋393實際匯入檔案；本項不是音樂生成或聽審通過。',ACQUIRED)]),
    'README.en.md':dict(
        status='**CLI0.1.64 in development: native GPU neural music commands.** The 25 request/BF16/recipe checks and 33 worker isolation checks passed. Actual generation, installed execution and Skill rollout have separate gates. The registered runtime remains CLI0.1.63 as described below.',
        label='Complete music interface, parameters and limits',
        feature='Native GPU neural music (development)',
        detail='Explicit style/lyrics, pinned ACE-Step1.5 Turbo, observed CUDA forwards, native48kHz stereo Float32 WAV, generation recipes and an independent audio track.',
        boundary='CLI64 development interface; absent from registered63. Not MIDI, instrument stems or accepted natural music quality.',
        rows=[
            ('R529','CLI64 music request and payload checks','25 passed: BF16/large vocabulary, native clock, lyrics, recipes and refusal of false GPU responses. No inference.',UNIT),
            ('R530','CLI64 worker isolation','33 passed, including native music dependency ownership and rejection of a foreign application. No inference.',BOOT),
            ('R531','ACE1.5 weight and native-interface admission','Four complete model SHA256 checks;673 runtime files cover393 actual imports. This is not music-generation or listening acceptance.',ACQUIRED)]),
}


def main():
    assert json.loads((ROOT / UNIT).read_bytes())['tests'] == 25
    assert json.loads((ROOT / BOOT).read_bytes())['status'] == 'passed'
    assert json.loads((ROOT / ACQUIRED).read_bytes())['status'] == 'passed'
    for rows in GROUP_ROWS.values():
        assert all(json.loads((ROOT / BASE / row[3]).read_bytes())['status'] == 'passed' for row in rows)
    assert json.loads((ROOT / BASE / 'candidate-r1/verification.json').read_bytes())['status'] == 'installed-and-byte-verified'
    assert json.loads((ROOT / BASE / 'skill-stage-r1/verification.json').read_bytes())['status'] == 'passed'
    for row in CURRENT_ROWS['README.md']:
        assert json.loads((ROOT / BASE / row[3]).read_bytes())['status'] == 'passed'
    changes = []
    for filename, words in WORDS.items():
        path = ROOT / filename
        text = path.read_text(encoding='utf-8')
        original_rows = set(re.findall(r'^\| (R\d+) \|', text, re.M))
        # Historical R466 pointed to a nonexistent58 directory inside59 evidence.
        # Keep its stable row ID and correct the proven59 receipt and module count.
        old_target = 'docs/validation/evidence/music-score-20261029-r1/installed58-contracts-r1/verification.json'
        target = 'docs/validation/evidence/music-score-20261029-r1/installed59-contracts-r1/verification.json'
        corrected = []
        for line in text.splitlines():
            if line.startswith('| R466 |'):
                line = line.replace(old_target, target).replace('281源码', '282源码').replace('281原始碼', '282原始碼')
            corrected.append(line)
        text = '\n'.join(corrected) + '\n'
        block = BEGIN + '\n' + words['status'] + f' [{words["label"]}]({DOCUMENT})\n' + END
        if BEGIN in text:
            text, count = re.subn(re.escape(BEGIN) + '.*?' + re.escape(END), lambda _:block, text, flags=re.S)
            assert count == 1
        else:
            title, rest = text.split('\n', 1)
            text = title + '\n\n' + block + '\n' + rest
        feature = f'| F87 | {words["feature"]} | {words["detail"]} | `music generator-adapter; music inspect-generation; music generate` | [{words["label"]}]({DOCUMENT})；{words["boundary"]} |'
        if re.search(r'^\| F87 \|', text, re.M):
            text = re.sub(r'^\| F87 \|.*$', lambda _:feature, text, flags=re.M)
        else:
            text, count = re.subn(r'(^\| F86 \|.*$)', lambda match:match[0] + '\n' + feature, text, flags=re.M)
            assert count == 1
        anchor = 'R528'
        rows = [*words['rows'], *((identifier, label, detail, BASE + target)
                                 for identifier,label,detail,target in [*GROUP_ROWS[filename], *DELIVERY_ROWS[filename], *CURRENT_ROWS[filename]])]
        for identifier, label, detail, target in rows:
            row = f'| {identifier} | {label} | {detail} [Proof]({target}) |'
            if re.search(r'^\| ' + identifier + r' \|', text, re.M):
                text = re.sub(r'^\| ' + identifier + r' \|.*$', lambda _:row, text, flags=re.M)
            else:
                text, count = re.subn(r'(^\| ' + anchor + r' \|.*$)', lambda match:match[0] + '\n' + row, text, flags=re.M)
                assert count == 1
            anchor = identifier
        current_rows = re.findall(r'^\| (R\d+) \|', text, re.M)
        assert original_rows <= set(current_rows) and len(current_rows) == len(set(current_rows))
        assert len(current_rows) == 542
        path.write_text(text, encoding='utf-8', newline='\n')
        changes.append(dict(path=filename, numbered_checks=len(current_rows), history_removed=False))
    print(json.dumps(changes), flush=True)


if __name__ == '__main__':
    main()
