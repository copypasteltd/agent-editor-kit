"""Persist a frozen implementation checkpoint while the whole suite stays live."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'docs/validation/evidence/delivery66-20261106-r1'
GIT = Path('C:/Users/carzy/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/git/mingw64/bin/git.exe')
PARENT = '8fffe3a4a123c09b19bb939bb9e344fca6663e60'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    assert sys.dont_write_bytecode
    freeze_path = BASE / 'freeze-r1/verification.json'
    freeze = json.loads(freeze_path.read_bytes())
    assert freeze['code_completed_before_tests'] and freeze['cli_version'] == '0.1.66'
    assert all(sha(ROOT / name) == pin for name, pin in freeze['file_hashes'].items())
    assert all(sha(ROOT / name) == pin for name, pin in freeze['formal_guard'].items())
    def git(*args, input=None):
        result = subprocess.run([str(GIT), '--no-optional-locks', '-c', 'core.fsmonitor=false',
            '-c', 'gc.auto=0', '-c', 'maintenance.auto=0', *args], cwd=ROOT, input=input,
            capture_output=True, timeout=600, creationflags=subprocess.CREATE_NO_WINDOW)
        assert result.returncode == 0, result.stderr[-2000:]
        return result.stdout
    assert git('rev-parse', 'HEAD').decode().strip() == PARENT
    out = BASE / 'checkpoint-r1'
    out.mkdir()
    (out / 'executed-runner.py').write_bytes(Path(__file__).read_bytes())
    records = (
        ('CLI66整批实现并冻结', 'CLI66整批實作並凍結', 'CLI66 complete implementation batch frozen'),
        ('完整4101项回归已启动，尚无终态', '完整4101項回歸已啟動，尚無終態', 'Whole 4101-test suite started; no terminal result'))
    details = (
        ('恢复完整预检合入产品；有界并行耐久备份；配乐进度有限读取；通用交付切换／恢复／回滚及整轮工具。T01—T06全部写完后冻结，尚未通过功能验收。',
         '恢復完整預檢合入產品；有界並行耐久備份；配樂進度有限讀取；通用交付切換／恢復／回滾及整輪工具。T01—T06全部寫完後凍結，尚未通過功能驗收。',
         'Integrates recovery preflight, bounded concurrent durable backups, bounded music progress, generic activation/recovery/rollback and whole-round tooling. T01–T06 completed before freeze; functional acceptance is pending.'),
        ('保持原用例、断言与时间门槛，执行完整源码测试集；本记录仅为启动检查点，不计通过数。已展开38组差距及新版6项交付缺口；正式Skill仍CLI63。',
         '保留原用例、斷言與時間門檻，執行完整原始碼測試集；本記錄僅為啟動檢查點，不計通過數。已展開38組差距及新版6項交付缺口；正式Skill仍CLI63。',
         'Runs the whole source suite with original assertions and deadlines. This is a start checkpoint, not a passing result. Documents all38 scope gaps and six delivery gaps; registered Skill stays CLI63.'))
    for i, filename in enumerate(('README.md', 'README.zh-TW.md', 'README.en.md')):
        path = ROOT / filename
        text = path.read_text(encoding='utf-8')
        previous = re.findall(r'^\| R\d+ \|.*$', text, re.M)
        features = re.findall(r'^\| F\d+ \|.*$', text, re.M)
        assert len(previous) == 574 and len(features) == 88
        rows = [f'| R{575+j} | {records[j][i]} | {details[j][i]} [Record](docs/product/DELIVERY66_IMPLEMENTATION.md) |' for j in range(2)]
        text, count = re.subn(r'(^\| R574 \|.*$)', lambda match: match[0] + '\n' + '\n'.join(rows), text, flags=re.M)
        assert count == 1
        notices = (
            '**开发状态2026-11-06：源码CLI0.1.66已完成整批代码冻结，完整4,101项回归进行中，尚无终态。** 正式入口仍CLI0.1.63／local61／r58。恢复预检已合入源码；交付控制器、并行耐久备份与配乐读取改动尚未完成整轮验收。此前CLI65真实10秒CUDA配乐成功属于历史版本证据。[本轮实现与验证顺序](docs/product/DELIVERY66_IMPLEMENTATION.md) · [完整38组差距](docs/product/UNFINISHED_20261106.md)',
            '**開發狀態2026-11-06：原始碼CLI0.1.66已完成整批程式凍結，完整4,101項回歸進行中，尚無終態。** 正式入口仍CLI0.1.63／local61／r58。恢復預檢已合入原始碼；交付控制器、並行耐久備份與配樂讀取變更尚未完成整輪驗收。此前CLI65真實10秒CUDA配樂成功屬歷史版本證據。[本輪實作與驗證順序](docs/product/DELIVERY66_IMPLEMENTATION.md) · [完整38組差距](docs/product/UNFINISHED_20261106.md)',
            '**Development status 2026-11-06: source CLI0.1.66 implementation batch is frozen; the complete 4,101-test suite is running without a terminal result.** Registered entry remains CLI0.1.63/local61/r58. Recovery preflight is integrated in source; delivery control, concurrent durable backups and music progress changes await whole-round acceptance. Actual CLI65 CUDA music is historical evidence for that version. [Batch and validation order](docs/product/DELIVERY66_IMPLEMENTATION.md) · [Original remaining scope](docs/product/UNFINISHED_20261106.md)')
        text, count = re.subn(r'<!-- aek-cli65-current -->.*?<!-- /aek-cli65-current -->',
            '<!-- aek-cli65-current -->\n' + notices[i] + '\n<!-- /aek-cli65-current -->', text, flags=re.S)
        assert count == 1
        assert set(previous) <= set(re.findall(r'^\| R\d+ \|.*$', text, re.M))
        assert re.findall(r'^\| F\d+ \|.*$', text, re.M) == features
        path.write_text(text, encoding='utf-8', newline='\n')
    document = ROOT / 'docs/product/DELIVERY66_IMPLEMENTATION.md'
    with document.open('a', encoding='utf-8', newline='\n') as handle:
        handle.write('\n## 代码冻结后的第一轮整体回归\n\n'
            'T01—T06的产品、交付工具、候选Skill模板及必要用例均先完成，再产生'
            '[冻结清单](../validation/evidence/delivery66-20261106-r1/freeze-r1/verification.json)。'
            '随后一次发现并启动4101项完整源码回归，保留原断言、时间门槛和失败。'
            '本检查点没有终态通过结论；安装构建、安装完整回归、真实配乐工程包重放、正式切换均待完成。'
            '回归期间不修改冻结的产品和测试文件。\n')
    attributes = ROOT / '.gitattributes'
    text = attributes.read_text(encoding='utf-8')
    addition = 'docs/validation/evidence/delivery66-20261106-r1/** -text -whitespace'
    assert addition not in text
    attributes.write_text(text.rstrip() + '\n' + addition + '\n', encoding='utf-8', newline='\n')
    scope = {'.gitattributes', 'README.md', 'README.zh-TW.md', 'README.en.md',
        'product/pyproject.toml', 'product/src/ai_ad_editor/__init__.py',
        'product/src/ai_ad_editor/project.py', 'product/src/ai_ad_editor/cli.py',
        'product/src/ai_ad_editor/music_generation_pipeline.py', 'product/src/ai_ad_editor/delivery.py',
        'product/tests/test_transaction_preflight.py', 'product/tests/test_delivery.py',
        'docs/product/DELIVERY66_IMPLEMENTATION.md', 'docs/product/DELIVERY_CONTROLLER.md',
        'docs/product/UNFINISHED_20261106.md',
        'docs/validation/delivery66.py', 'docs/validation/implement_delivery66.py',
        'docs/validation/prepare_delivery66_tests.py', 'docs/validation/record_delivery66_checkpoint.py',
        'docs/validation/commit_delivery66_checkpoint.py'}
    scope.update(p.relative_to(ROOT).as_posix() for p in (BASE / 'freeze-r1').iterdir() if p.is_file())
    scope.add((BASE / 'source-all-r1/executed-runner.py').relative_to(ROOT).as_posix())
    scope.add((out / 'executed-runner.py').relative_to(ROOT).as_posix())
    for name in scope:
        if name.endswith('.py'):
            compile((ROOT / name).read_bytes(), name, 'exec')
    frozen = {name: sha(ROOT / name) for name in scope}
    report = dict(status='implementation-frozen-tests-running', base_commit=PARENT, cli_version='0.1.66',
        source_cli='0.1.66', formal_cli='0.1.63', README_rows=576, feature_rows=88,
        code_completed_before_tests=True, discovered_tests=4101, terminal_test_result=False,
        full_product_goal_closed=False, formal_activation=False, files=frozen,
        source_hashes=freeze['file_hashes'], formal_guard_sha256=freeze['formal_guard'])
    save = out / 'verification.json'
    save.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
    scope.add(save.relative_to(ROOT).as_posix())
    pathspec = ROOT / 'local/agent-ffmpeg/delivery66-checkpoint-r1.nul'
    pathspec.write_bytes(('\0'.join(sorted(scope)) + '\0').encode('utf-8'))
    git('add', '--pathspec-from-file=' + str(pathspec), '--pathspec-file-nul')
    assert all(sha(ROOT / name) == pin for name, pin in freeze['file_hashes'].items())
    print(json.dumps(dict(status=report['status'], scope_files=len(scope), formal_activation=False)), flush=True)


if __name__ == '__main__':
    main()
