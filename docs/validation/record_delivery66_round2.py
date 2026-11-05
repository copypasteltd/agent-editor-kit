"""Record the complete correction and a configured whole-suite start checkpoint."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'docs/validation/evidence/delivery66-20261106-r1'
GIT = Path('C:/Users/carzy/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/git/mingw64/bin/git.exe')
PARENT = '256f54f77ebbf40e86fc2a7a492c38058a2a186c'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    return json.loads(path.read_bytes())


def once(value, old, new):
    assert value.count(old) == 1, old[:100]
    return value.replace(old, new, 1)


def main():
    assert sys.dont_write_bytecode
    freeze = load(BASE / 'freeze-r2/verification.json')
    assert freeze['status'] == 'frozen' and freeze['code_completed_before_tests']
    assert all(sha(ROOT / name) == pin for name, pin in freeze['file_hashes'].items())
    assert all(sha(ROOT / name) == pin for name, pin in freeze['formal_guard'].items())
    old = load(BASE / 'source-all-r1/verification.json')
    assert old['status'] == 'interrupted' and old['observed_skips'] == 8 and old['owner_confirmed_stopped']
    assert load(BASE / 'source-all-r2/native-dependencies.json')['status'] == 'ready'
    assert (BASE / 'source-all-r2/tests.stderr').is_file()
    assert not (BASE / 'source-all-r2/verification.json').exists(), 'Use a terminal report instead if the suite has completed'
    out = BASE / 'round2-r1'
    out.mkdir()
    (out / 'executed-runner.py').write_bytes(Path(__file__).read_bytes())
    for i, name in enumerate(('README.md', 'README.zh-TW.md', 'README.en.md')):
        path = ROOT / name
        text = path.read_text(encoding='utf-8')
        history = re.findall(r'^\| R\d+ \|.*$', text, re.M)
        features = re.findall(r'^\| F\d+ \|.*$', text, re.M)
        assert len(history) == 576 and len(features) == 88
        notices = (
            '**开发状态2026-11-06：源码CLI0.1.66已合入完整交付修正并冻结r2，配置完整的4,110项源码回归运行中，尚无终态。** 正式入口仍CLI0.1.63／local61／r58。初轮4,101项因明确缺少测试依赖配置而中断，8处跳过原样保留。新版增加五类交付门禁、实际CUDA配乐／完整PCM证据绑定、完整恢复预检及15个测试文件的安装路径修正；尚未正式切换。[整批修正](docs/product/DELIVERY66_CORRECTION.md) · [全部剩余范围](docs/product/UNFINISHED_20261106.md)',
            '**開發狀態2026-11-06：原始碼CLI0.1.66已合入完整交付修正並凍結r2，設定完整的4,110項原始碼回歸執行中，尚無終態。** 正式入口仍CLI0.1.63／local61／r58。首輪4,101項因明確缺少測試依賴設定而中斷，8處跳過原樣保留。新版增加五類交付門檻、實際CUDA配樂／完整PCM證據綁定、完整恢復預檢及15個測試檔案的安裝路徑修正；尚未正式切換。[整批修正](docs/product/DELIVERY66_CORRECTION.md) · [全部剩餘範圍](docs/product/UNFINISHED_20261106.md)',
            '**Development status 2026-11-06: source CLI0.1.66 complete delivery correction is frozen as r2; the configured whole 4,110-test source suite is running without a terminal result.** Registered entry stays CLI0.1.63/local61/r58. The first 4,101-test run was deliberately interrupted after missing dependency configuration caused eight observed skips; its log is retained. Adds five delivery gates, actual CUDA/complete PCM evidence bindings, full restore preflight and installed-path corrections in15 test files. Formal activation is pending. [Correction batch](docs/product/DELIVERY66_CORRECTION.md) · [Remaining scope](docs/product/UNFINISHED_20261106.md)')
        text, count = re.subn(r'<!-- aek-cli65-current -->.*?<!-- /aek-cli65-current -->',
            '<!-- aek-cli65-current -->\n' + notices[i] + '\n<!-- /aek-cli65-current -->', text, flags=re.S)
        assert count == 1
        records = (
            ('整批交付修正已合入66并冻结', '整批交付修正已合入66並凍結', 'Complete delivery correction integrated and frozen'),
            ('完整回归配置修正与初轮中断保留', '完整回歸設定修正與首輪中斷保留', 'Whole-suite configuration fixed; first interruption retained'))
        details = (
            ('五类独立证据与应用／Skill／WAV／请求／工程摘要绑定；前向设备及PCM检查；坏输入、缺失备份和中断后用户修改保护；补能力查询。整批完成后冻结，功能验收待定。',
             '五類獨立證據與應用／Skill／WAV／請求／專案摘要綁定；前向裝置及PCM檢查；錯誤輸入、缺失備份及中斷後使用者修改保護；補能力查詢。整批完成後凍結，功能驗收待定。',
             'Five independent gates bind application/Skill/audio/request/project bytes, CUDA devices and PCM. Adds bounded input and restore validation, foreign-edit protection and discovery. Full code batch frozen; acceptance pending.'),
            ('原4,101项保留8处跳过及中断终态；显式核验Rubber Band／Node／HTML依赖，15个测试文件绑定实际所选包。新4,110项完整回归已启动，原断言与20秒门槛保留；未计通过数。',
             '原4,101項保留8處跳過及中斷終態；明確核驗Rubber Band／Node／HTML依賴，15個測試檔案綁定實際所選套件。新4,110項完整回歸已啟動，原斷言與20秒門檻保留；未計通過數。',
             'Retains eight observed skips and the interrupted original run. Explicit Rubber Band/Node/HTML preflight and15 test-file package bindings precede the new whole4,110 run. Original assertions and20s deadline stay; no passing total claimed.'))
        rows = [f'| R{577+j} | {records[j][i]} | {details[j][i]} [Record](docs/product/DELIVERY66_CORRECTION.md) |' for j in range(2)]
        text, count = re.subn(r'(^\| R576 \|.*$)', lambda match: match[0] + '\n' + '\n'.join(rows), text, flags=re.M)
        assert count == 1
        feature = (
            '| F89 | 正式Skill交付控制（开发66） | 候选检查、切换、完整备份预检、恢复、回滚；五类证据及应用／Skill字节绑定。正式63尚无此命令，新版验收中。 | `delivery inspect/activate/recover/rollback` | [流程与边界](docs/product/DELIVERY_CONTROLLER.md) |',
            '| F89 | 正式Skill交付控制（開發66） | 候選檢查、切換、完整備份預檢、恢復、回滾；五類證據及應用／Skill位元組綁定。正式63尚無此命令，新版驗收中。 | `delivery inspect/activate/recover/rollback` | [流程與邊界](docs/product/DELIVERY_CONTROLLER.md) |',
            '| F89 | Formal Skill delivery control (development66) | Inspect, activate, full backup preflight, recover and rollback; five evidence roles bind application/Skill bytes. Registered63 lacks these commands; new-version acceptance is pending. | `delivery inspect/activate/recover/rollback` | [Workflow and limits](docs/product/DELIVERY_CONTROLLER.md) |')
        text, count = re.subn(r'(^\| F88 \|.*$)', lambda match: match[0] + '\n' + feature[i], text, flags=re.M)
        assert count == 1
        assert set(history) <= set(re.findall(r'^\| R\d+ \|.*$', text, re.M))
        assert set(features) <= set(re.findall(r'^\| F\d+ \|.*$', text, re.M))
        path.write_text(text, encoding='utf-8', newline='\n')
    summary = ROOT / 'docs/product/UNFINISHED_20261106.md'
    text = summary.read_text(encoding='utf-8')
    text = text.replace('最新代码已冻结并启动完整4,101项源码回归；测试仍在运行，没有终态通过结论。',
        '完整交付修正已合入并冻结r2，新4,110项源码全套运行中，没有终态通过结论。初轮因依赖配置遗漏观察到8处跳过，已中断并保留原日志。')
    text = text.replace('CLI66完整4,101项源码回归运行中；', 'CLI66配置完整的4,110项源码回归运行中；初轮4,101项已中断并保留8处跳过；')
    text = text.replace('下列条目是CLI66冻结后的审阅发现与后续验收，不把“已写代码”写成“用户已可用”。集中回归运行期间保留冻结字节；待完整结果返回后，与实际失败一起进入完整修正批次。',
        '下列审阅缺口已形成完整修正批次并一次合入，再冻结r2、启动配置完整的全套回归。初轮中断及8处跳过保留；不把代码完成写成用户已可用，回归期间不修改新冻结字节。')
    for old, new in (
        ('整轮工程包工具使用了错误的导出格式字符串', '导出格式参数已修正，尚未实际重放'),
        ('新`delivery`命令尚未进入Agent能力查询清单', '已补`delivery`能力查询，待实际安装与入口验收'),
        ('新交付门禁的Skill检查目前只要求真实PowerShell入口', '已增加实际CUDA配乐第五类证据，待真实66生成'),
        ('交付描述与恢复日志的畸形字段处理仍须加强', '畸形字段、有界读取、完整恢复预检和用户修改保护已实现，待回归'),
        ('源码回归运行中，安装与交付尚未执行', '依赖显式预检及15文件安装路径绑定已补齐；4,110项运行中，安装和交付未执行')):
        text = once(text, old, new)
    text += '\n最新整批代码及验收顺序见[CLI66交付修正](DELIVERY66_CORRECTION.md)。原38组关闭条件保持。\n'
    summary.write_text(text, encoding='utf-8', newline='\n')
    document = ROOT / 'docs/product/DELIVERY_CONTROLLER.md'
    text = document.read_text(encoding='utf-8')
    text = once(text, 'Use the installed `delivery` commands for a reviewed single-Skill update.',
        'The registered CLI63 does not provide these commands. After CLI66 candidate installation and acceptance, use its installed `delivery` commands for a reviewed single-Skill update.')
    document.write_text(text, encoding='utf-8', newline='\n')
    scope = {'README.md', 'README.zh-TW.md', 'README.en.md', 'docs/product/UNFINISHED_20261106.md',
        'docs/product/DELIVERY_CONTROLLER.md', 'docs/product/DELIVERY66_CORRECTION.md',
        'docs/validation/prepare_delivery66_correction.py', 'docs/validation/prepare_delivery66_environment.py',
        'docs/validation/interrupt_delivery66_misconfigured.py', 'docs/validation/record_delivery66_round2.py',
        'docs/validation/commit_delivery66_round2.py', 'docs/validation/delivery66.py'}
    candidate = load(ROOT / 'docs/validation/candidates/delivery66-r3/implementation.json')
    scope.update(candidate['mapping'].values())
    directories = ['correction-code-r1', 'correction-code-r2', 'correction-apply-r2',
        'source-all-r1-interruption-r1', 'freeze-r2']
    for name in directories:
        scope.update(path.relative_to(ROOT).as_posix() for path in (BASE / name).rglob('*') if path.is_file())
    for name in ('delivery66-r2', 'delivery66-r3'):
        scope.update(path.relative_to(ROOT).as_posix() for path in (ROOT / 'docs/validation/candidates' / name).rglob('*') if path.is_file())
    for name in ('verification.json', 'tests.stderr'):
        scope.add((BASE / 'source-all-r1' / name).relative_to(ROOT).as_posix())
    scope.update(path.relative_to(ROOT).as_posix() for path in (BASE / 'source-all-r2').iterdir()
                 if path.is_file() and path.name != 'tests.stderr')
    scope.add((out / 'executed-runner.py').relative_to(ROOT).as_posix())
    for name in scope:
        if name.endswith('.py'):
            compile((ROOT / name).read_bytes(), name, 'exec')
    report = dict(status='implementation-frozen-tests-running', base_commit=PARENT, source_cli='0.1.66',
        formal_cli='0.1.63', code_completed_before_tests=True, terminal_test_result=False,
        discovered_tests=4110, initial_run='interrupted', initial_observed_skips=8,
        formal_activation=False, full_product_goal_closed=False,
        files={name: sha(ROOT / name) for name in scope}, source_hashes=freeze['file_hashes'],
        formal_guard_sha256=freeze['formal_guard'], README_rows=578, feature_rows=89)
    save = out / 'verification.json'
    save.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
    scope.add(save.relative_to(ROOT).as_posix())
    pathspec = ROOT / 'local/agent-ffmpeg/delivery66-round2-r1.nul'
    pathspec.write_bytes(('\0'.join(sorted(scope)) + '\0').encode('utf-8'))
    result = subprocess.run([str(GIT), '--no-optional-locks', '-c', 'core.fsmonitor=false',
        '-c', 'gc.auto=0', '-c', 'maintenance.auto=0', 'add', '--pathspec-from-file=' + str(pathspec),
        '--pathspec-file-nul'], cwd=ROOT, capture_output=True, timeout=600)
    assert result.returncode == 0, result.stderr[-2000:]
    print(json.dumps(dict(status=report['status'], scope_files=len(scope), README_rows=578)), flush=True)


if __name__ == '__main__':
    main()
