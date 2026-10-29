"""Add the verified CLI65 scope to all three READMEs without dropping history."""
import argparse
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'docs/validation/evidence/music-loading-20261030-r1'


def load(path):
    return json.loads(path.read_bytes())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run', required=True)
    args = parser.parse_args()
    assert args.run.isalnum()
    required = {name: BASE / (name + '/verification.json') for name in (
        'source65-unit-r1', 'source65-music-r1', 'source65-bootstrap-r1', 'source65-control-r1',
        'native-reader-r1', 'native-reader-d1', 'candidate-r1', 'skill-stage-r1', 'native-stack-reader1')}
    missing = [name for name, path in required.items() if not path.is_file()]
    if missing:
        print(json.dumps(dict(status='pending', missing=missing, documents_changed=False)), flush=True)
        return 2
    reports = {name: load(path) for name, path in required.items()}
    for name, report in reports.items():
        expected = 'installed-and-byte-verified' if name == 'candidate-r1' else 'captured' if name == 'native-stack-reader1' else 'passed'
        assert report['status'] == expected, (name, report['status'])
    assert all(sha(ROOT / name) == pin for name, pin in reports['source65-unit-r1']['file_hashes'].items())
    session_path = BASE / 'source65-session-r1/verification.json'
    session = load(session_path) if session_path.is_file() else None
    rows = [
        ('source65-unit-r1', ('CLI65配乐请求与读取边界', 'CLI65配樂請求與讀取邊界', 'CLI65 music request and loader boundaries'),
         ('37通过，包含12项新读取与计时边界；未加载音乐模型。', '37通過，包含12項新讀取與計時邊界；未載入音樂模型。', '37 passed, including 12 new loader/clock boundaries. No music model loaded.')),
        ('source65-bootstrap-r1', ('CLI65原生工作进程隔离', 'CLI65原生工作進程隔離', 'CLI65 native worker isolation'),
         ('33通过，原生依赖归属及拒绝外部应用；无神经推理。', '33通過，原生依賴歸屬及拒絕外部應用；無神經推理。', '33 passed: native dependency ownership and foreign application refusal; no neural inference.')),
        ('source65-control-r1', ('CLI65执行控制回归', 'CLI65執行控制回歸', 'CLI65 execution control regression'),
         ('26通过，原生进程树、执行预算与清理；不代替新音乐中途故障验证。', '26通過，原生進程樹、執行預算與清理；不代替新音樂中途故障驗證。', '26 passed: native process ownership, budgets and cleanup. New music mid-inference fault checks remain separate.')),
        ('source65-music-r1', ('CLI65配乐兼容回归', 'CLI65配樂相容回歸', 'CLI65 music compatibility regression'),
         ('74通过，零失败／错误／跳过，源码冻结一致；包含前述37项，不重复累计。', '74通過，零失敗／錯誤／跳過，原始碼凍結一致；包含前述37項，不重複累計。', '74 passed with no failures/errors/skips, frozen source unchanged. Includes the preceding 37; no duplicate total.')),
        ('native-reader-r1', ('CLI65已有E盘原生BF16读取', 'CLI65既有E盤原生BF16讀取', 'CLI65 existing E-drive native BF16 reads'),
         ('Torch2.14／safetensors0.8：四份微型BF16张量实际pread、数值及metadata相同，读取器恢复。无音乐权重／前向。', 'Torch2.14／safetensors0.8：四份微型BF16張量實際pread、數值及metadata相同，讀取器恢復。無音樂權重／前向。', 'Torch2.14 / safetensors0.8: actual pread of four tiny BF16 tensors, exact values/metadata, reader restored. No music weights/forwards.')),
        ('native-reader-d1', ('CLI65已有D盘原生BF16读取', 'CLI65既有D盤原生BF16讀取', 'CLI65 existing D-drive native BF16 reads'),
         ('Torch2.13／safetensors0.8：相同微型BF16与metadata核验通过；缓存及新文件在E盘。不是完整音乐核心兼容验收。', 'Torch2.13／safetensors0.8：相同微型BF16與metadata核驗通過；快取及新檔案在E盤。不是完整音樂核心相容驗收。', 'Torch2.13 / safetensors0.8: actual tiny BF16/metadata checks passed; caches/new files remain on E. Not complete music-core compatibility acceptance.')),
        ('native-stack-reader1', ('CLI65原生导入栈观察', 'CLI65原生匯入堆疊觀察', 'CLI65 native import stack observation'),
         ('原生进程创建时间／可执行文件前后匹配，采样时位于Torch文件读取；不请求局部变量，不据单次采样确认全部耗时原因。', '原生進程建立時間／執行檔前後相符，採樣時位於Torch檔案讀取；不請求區域變數，不據單次採樣確認全部耗時原因。', 'Native creation-time/executable identity matched before/after. Sample captured Torch file reads, without locals. One sample does not establish the complete duration cause.')),
        ('candidate-r1', ('CLI65独立候选构建与安装', 'CLI65獨立候選構建與安裝', 'CLI65 independent candidate build and installation'),
         ('local63候选离线安装、version及288应用模块精确核验通过；只作后续实测，正式63／local61不变。', 'local63候選離線安裝、version及288應用模組精確核驗通過；僅作後續實測，正式63／local61不變。', 'local63 candidate installed offline; version and all 288 modules verified exactly. For validation; formal CLI63/local61 unchanged.')),
        ('skill-stage-r1', ('CLI65统一Skill候选入口', 'CLI65統一Skill候選入口', 'CLI65 unified Skill staged entry'),
         ('94文件／17模块正文与脚本、实际PowerShell version／help通过；尚未注册为正式入口，本项无模型推理。', '94檔案／17模組正文與腳本、實際PowerShell version／help通過；尚未註冊為正式入口，本項無模型推理。', '94 files /17 modules: instructions/scripts and actual PowerShell version/help passed. Unregistered; this check performs no model inference.'))]
    if session:
        assert session['cli_version'] == '0.1.65' and session['frozen_equal']
        required['source65-session-r1'] = session_path
        details = (
            f"{session['tests']}项执行，{session['failures']}失败、{session['errors']}错误、{session['skipped']}跳过，状态{session['status']}。原断言与时限保留；20秒启动等待仍失败，状态／停止断言未到达。完整443不验收，旧431失败保留。",
            f"{session['tests']}項執行，{session['failures']}失敗、{session['errors']}錯誤、{session['skipped']}跳過，狀態{session['status']}。原斷言與時限保留；20秒啟動等待仍失敗，狀態／停止斷言未到達。完整443不驗收，舊431失敗保留。",
            f"{session['tests']} executed / {session['failures']} failures / {session['errors']} errors / {session['skipped']} skipped; status {session['status']}. Original assertions/deadlines retained; 20s startup wait still failed before status/stop assertions. Full443 not accepted; previous431 failure retained.")
        assert session['status'] == 'failed' and session['failures'] == 1
        rows.append(('source65-session-r1', ('CLI65原会话控制回归（失败）', 'CLI65原會話控制回歸（失敗）', 'CLI65 original session-control regression (FAILED)'), details))
    proof = BASE / ('documentation-' + args.run)
    proof.mkdir()
    (proof / 'executed-runner.py').write_bytes(Path(__file__).read_bytes())
    hashes = {}
    for language, filename in enumerate(('README.md', 'README.zh-TW.md', 'README.en.md')):
        path = ROOT / filename
        text = path.read_text(encoding='utf-8')
        old_rows = re.findall(r'^\| R\d+ \|.*$', text, re.M)
        assert len(old_rows) == 555 and len(re.findall(r'^\| F\d+ \|', text, re.M)) == 87
        additions = []
        for number, (name, label, detail) in enumerate(rows, 556):
            additions.append(f'| R{number} | {label[language]} | {detail[language]} [Proof](docs/validation/evidence/music-loading-20261030-r1/{name}/verification.json) |')
        text, count = re.subn(r'(^\| R555 \|.*$)', lambda m: m[0] + '\n' + '\n'.join(additions), text, flags=re.M)
        assert count == 1
        status = (
            '**CLI0.1.65 开发中：固定pread读取与完整计时。** 源码配乐74／隔离33／控制26分别通过；两套已有原生环境的微型BF16实际读取通过。local63候选及未注册Skill入口已核验，真实GPU新生成继续验证。正式入口仍CLI0.1.63／local61／r58；完整兼容与听审未收口。',
            '**CLI0.1.65 開發中：固定pread讀取與完整計時。** 原始碼配樂74／隔離33／控制26分別通過；兩套既有原生環境的微型BF16實際讀取通過。local63候選及未註冊Skill入口已核驗，真實GPU新生成繼續驗證。正式入口仍CLI0.1.63／local61／r58；完整相容與聽審未收口。',
            '**CLI0.1.65 in development: pinned pread loading and complete timing.** Source music74 / isolation33 / control26 passed separately; tiny BF16 reads passed in two existing native environments. local63 candidate and unregistered Skill entry verified; actual new GPU generation under validation. Registered CLI0.1.63/local61/r58; full compatibility and listening remain open.')
        text, count = re.subn(r'<!-- aek-cli64-current -->.*?<!-- /aek-cli64-current -->',
            '<!-- aek-cli65-current -->\n' + status[language] + ' [Loading](docs/product/NEURAL_MUSIC_LOADING.md)\n<!-- /aek-cli65-current -->', text, flags=re.S)
        assert count == 1
        feature = (
            '| F88 | 神经配乐权重读取与完整计时（开发中） | 四组件实际pread读取记录、静态加载策略、导入／checkpoint／生成分段计时；失败不回退mmap或CPU神经推理。 | `music generator-adapter; music generate` | [CLI65使用逻辑和计时范围](docs/product/NEURAL_MUSIC_LOADING.md)；自然质量与性能按真实任务分别验收。 |',
            '| F88 | 神經配樂權重讀取與完整計時（開發中） | 四組件實際pread讀取記錄、靜態載入策略、匯入／checkpoint／生成分段計時；失敗不回退mmap或CPU神經推理。 | `music generator-adapter; music generate` | [CLI65使用邏輯和計時範圍](docs/product/NEURAL_MUSIC_LOADING.md)；自然品質與效能依真實任務分別驗收。 |',
            '| F88 | Neural music weight reads and complete timing (development) | Observed pread for four components, static loading, import/checkpoint/generation clocks; no mmap or CPU neural fallback. | `music generator-adapter; music generate` | [CLI65 workflow and timing scope](docs/product/NEURAL_MUSIC_LOADING.md); quality/performance require actual tasks. |')
        text, count = re.subn(r'(^\| F87 \|.*$)', lambda m: m[0] + '\n' + feature[language], text, flags=re.M)
        assert count == 1
        current = re.findall(r'^\| R\d+ \|.*$', text, re.M)
        assert len(current) == 555 + len(rows) and set(old_rows) <= set(current)
        assert len(re.findall(r'^\| F\d+ \|', text, re.M)) == 88
        path.write_text(text, encoding='utf-8', newline='\n')
        hashes[filename] = sha(path)
    manual = ROOT / 'docs/product/NEURAL_MUSIC_GENERATION.md'
    text = manual.read_text(encoding='utf-8')
    text += ('\n## CLI65读取与计时更新\n\n'
        '开发候选65固定四组件pread与静态加载策略，并将运行库导入纳入模型函数总时钟；'
        '实际命令、字段范围、新适配器登记、两套原生小型BF16核验及验收限制见'
        '[CLI65读取与完整计时手册](NEURAL_MUSIC_LOADING.md)。旧CLI64实测和失败收据原样保留；正式入口仍63。\n')
    manual.write_text(text, encoding='utf-8', newline='\n')
    hashes[manual.relative_to(ROOT).as_posix()] = sha(manual)
    report = dict(status='passed', README_rows=555 + len(rows), previous_555_rows_retained=True,
        feature_rows=88, evidence={name: sha(path) for name, path in required.items()}, files=hashes,
        source_cli='0.1.65', candidate='v0.1.0-alpha.4-local.63', formal_cli='0.1.63', formal_activation=False,
        actual_music_generation_accepted=False, full_product_goal_closed=False)
    (proof / 'verification.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps(dict(status='passed', README_rows=report['README_rows'], formal_activation=False)), flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
