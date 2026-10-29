"""Document, audit and normally push the isolated recovery candidate."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'docs/validation/evidence/transaction-preflight-20261030-r1'
MUSIC = ROOT / 'docs/validation/evidence/music-loading-20261030-r1'
GIT_ROOT = Path('C:/Users/carzy/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/git')
GIT = GIT_ROOT / 'mingw64/bin/git.exe'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    return json.loads(path.read_bytes())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run', required=True)
    args = parser.parse_args()
    assert args.run.isalnum() and sys.dont_write_bytecode and os.name == 'nt'
    env = dict(os.environ)
    env['PATH'] = str(GIT_ROOT / 'cmd') + os.pathsep + env.get('PATH', '')

    def git(*arguments, input=None, alternate=None, timeout=1200):
        child_env = dict(env)
        if alternate:
            child_env['GIT_INDEX_FILE'] = str(alternate)
        command = [str(GIT), '--no-optional-locks', '-c', 'core.fsmonitor=false',
            '-c', 'gc.auto=0', '-c', 'maintenance.auto=0', *arguments]
        assert len(subprocess.list2cmdline(command)) < 30000
        result = subprocess.run(command, input=input, cwd=ROOT, env=child_env,
            capture_output=True, timeout=timeout, creationflags=subprocess.CREATE_NO_WINDOW)
        if result.returncode:
            raise RuntimeError(result.stderr[-4000:].decode('utf-8', errors='replace'))
        return result.stdout

    prior = ROOT / 'local/agent-ffmpeg/music65-checkpoint-commit-r1'
    committed = load(prior / 'verification.json')
    assert committed['status'] == 'committed-and-pushed'
    parent = committed['commit']
    assert parent == '26e851d1a96cf8724e58501b797712a7b076cc8e'
    assert git('rev-parse', 'HEAD').decode().strip() == parent
    assert git('symbolic-ref', '--short', 'HEAD').strip() == b'main'
    assert git('remote', 'get-url', '--push', 'origin').strip() == b'git@github.com:copypasteltd/agent-editor-kit.git'
    recovery = load(BASE / 'candidate-r1/verification.json')
    assert recovery['status'] == 'passed' and recovery['tests'] == 15 and not recovery['product_integrated']
    assert recovery['failures'] == recovery['errors'] == recovery['skipped'] == 0 and recovery['frozen_equal']
    assert all(sha(ROOT / name) == pin for name, pin in recovery['file_hashes'].items())
    assert recovery['candidate_definitions_sha256'] == sha(ROOT / 'docs/validation/recovery66_preflight_candidate.py')
    candidate = load(MUSIC / 'candidate-r1/verification.json')
    assert len(candidate['registered_files']) == 95
    assert all(sha(Path(name)) == pin for name, pin in candidate['registered_files'].items())
    goal = 'docs/product/GOAL_GAPS_20261025.md'
    assert (ROOT / goal).read_bytes() == git('show', 'HEAD:' + goal)
    rejected = MUSIC / 'native-stack-controller1'
    captured = MUSIC / 'native-stack-controller2'
    index_probe = MUSIC / 'tree-probe-r1'
    assert load(rejected / 'verification.json')['status'] == 'rejected-before-stack'
    assert load(captured / 'verification.json')['status'] == 'captured'
    assert load(captured / 'verification.json')['process_identity_equal']
    assert not load(captured / 'verification.json')['requested_locals']
    assert 'execute (ai_ad_editor\\music_generation_pipeline.py:144)' in (captured / 'stack.stdout').read_text(encoding='utf-8')
    assert load(index_probe / 'verification.json')['status'] == 'passed'
    proof = BASE / ('followup-' + args.run)
    proof.mkdir()
    (proof / 'executed-runner.py').write_bytes(Path(__file__).read_bytes())

    labels = (('恢复前完整核验的隔离候选', '恢復前完整核驗的隔離候選', 'Isolated recovery preflight candidate'),
              ('CLI65运行中控制进程的只读采样', 'CLI65執行中控制進程的唯讀採樣', 'CLI65 read-only controller stack sample'))
    details = (
        ('15项通过：全部备份先核验大小／SHA／归属／重复路径；已知损坏／末项缺失均零写回，真实写回中断保留日志并可重试。仅独立候选，尚未合入产品或正式Skill。',
         '15項通過：全部備份先核驗大小／SHA／歸屬／重複路徑；已知損壞／末項缺失均零寫回，真實寫回中斷保留日誌並可重試。僅獨立候選，尚未合入產品或正式Skill。',
         '15 passed: preflight all backup sizes/digests/ownership/duplicates; known corruption or missing final backup causes zero restore writes; an interrupted actual restore retains its journal and retries. Isolated candidate; not integrated or registered.'),
        ('创建时间／可执行文件前后相同，采样位于音乐工作进程等待循环；无局部变量。首次中文路径编码检查拒绝记录保留；显式UTF8后原归属检查通过。不证明GPU生成或全部耗时原因。',
         '建立時間／執行檔前後相同，採樣位於音樂工作進程等待迴圈；無區域變數。首次中文路徑編碼檢查拒絕記錄保留；明確UTF8後原歸屬檢查通過。不證明GPU生成或全部耗時原因。',
         'Creation-time/executable identity matched before/after; sample captured the music-worker wait loop, without locals. Initial Unicode command-path guard refusal retained; explicit UTF8 passed the original ownership check. No GPU-generation or complete-duration acceptance.'))
    targets = ('docs/validation/evidence/transaction-preflight-20261030-r1/candidate-r1/verification.json',
               'docs/validation/evidence/music-loading-20261030-r1/native-stack-controller2/verification.json')
    for language, filename in enumerate(('README.md', 'README.zh-TW.md', 'README.en.md')):
        path = ROOT / filename
        old = git('show', 'HEAD:' + filename).decode('utf-8')
        text = path.read_text(encoding='utf-8')
        before = re.findall(r'^\| R\d+ \|.*$', text, re.M)
        assert len(before) == 570 and before == re.findall(r'^\| R\d+ \|.*$', old, re.M)
        rows = [f'| R{571+i} | {labels[i][language]} | {details[i][language]} [Proof]({targets[i]}) |' for i in range(2)]
        text, count = re.subn(r'(^\| R570 \|.*$)', lambda match: match[0] + '\n' + '\n'.join(rows), text, flags=re.M)
        assert count == 1
        old_notice = ('另外已复现两个备份完整性缺陷，修复待完成。',
                      '另外已重現兩個備份完整性缺陷，修復待完成。',
                      'Two backup-integrity defects are reproduced and remain unfixed.')
        new_notice = ('另外已复现两个备份完整性缺陷；修复隔离候选15项通过，尚未合入。',
                      '另外已重現兩個備份完整性缺陷；修復隔離候選15項通過，尚未合入。',
                      'Two backup-integrity defects are reproduced; an isolated repair candidate passed 15 checks and remains unintegrated.')
        assert text.count(old_notice[language]) == 1
        text = text.replace(old_notice[language], new_notice[language])
        after = re.findall(r'^\| R\d+ \|.*$', text, re.M)
        assert len(after) == 572 and set(before) <= set(after)
        assert len(re.findall(r'^\| F\d+ \|', text, re.M)) == 88
        path.write_text(text, encoding='utf-8', newline='\n')
    round_path = ROOT / 'docs/validation/CLI65配乐读取与计时_2026-10-30.md'
    text = round_path.read_text(encoding='utf-8')
    text = text.replace('三语核验表连续到R570', '三语核验表连续到R572')
    text = text.replace('在冻结的音乐任务终态后，新增完整预检：所有条目、归属、大小、SHA及重复路径先通过，之后才写回；原损坏备份保留并拒绝恢复',
        '隔离修复候选15项通过；音乐任务终态后合入程序，并验证实际CLI、现有回滚、独立安装及完整兼容；原损坏备份保留并拒绝恢复')
    text += '''
\n## 恢复修复的隔离候选（未合入）

已在E盘的一次性测试工程执行完整候选project模块，15项全部通过，零失败／错误／跳过；不是只对日志格式做模拟断言。新流程先核验全部条目的身份、归属、路径、大小和SHA，再进行写回和元数据清理。相同长度损坏、大小不符、末项备份缺失、重复目标／备份、其他事务备份、媒体／日志目标、路径别名、无效提交身份均拒绝且零恢复写入；日志、备份、已有元数据和媒体保持原字节。

有效快照逐项恢复并保留媒体；已提交事务仅清理；真实第二次写回注入故障后保留日志，再次恢复成功。真实fsync保持，未调度Docker／WSL，未修改被冻结的288应用模块。候选仍未合入、安装或注册，不把它算作当前版本已经修复；不承诺多文件原子替换或对任意并发外部写者的保证。

- [15项实际候选模块检查](evidence/transaction-preflight-20261030-r1/candidate-r1/verification.json)
- [实际测试原日志](evidence/transaction-preflight-20261030-r1/candidate-r1/tests.stderr)
- [候选恢复代码](recovery66_preflight_candidate.py)
- [可重做的独立验证](validate_recovery66_candidate.py)

## 运行中只读观察和提交操作

一次控制进程采样前后核对创建时间和可执行文件，实际栈位于音乐工作进程等待循环，未请求局部变量。首次诊断因Windows PowerShell中文输出编码未能匹配精确路径而被拒绝；原失败及脚本保留，明确UTF8后相同归属约束通过。它不代表音乐生成通过，也不确定全部耗时原因。

- [原中文路径检查拒绝](evidence/music-loading-20261030-r1/native-stack-controller1/verification.json)
- [只读实际栈采样](evidence/music-loading-20261030-r1/native-stack-controller2/verification.json)

CLI65源码、local63独立安装核验及R556–R570记录已经普通推送到main：26e851d1a96cf8724e58501b797712a7b076cc8e。随后提交的隔离恢复候选仍不修改产品代码。Git私有索引试算得到与既有提交完全相同的根树；后续只在私有索引使用missing-ok计算，所有本轮新对象仍逐项读取并核验，既有main父提交和普通推送也必须验证。该操作不等于产品功能测试。
'''
    round_path.write_text(text, encoding='utf-8', newline='\n')
    attributes_path = ROOT / '.gitattributes'
    attributes = attributes_path.read_text(encoding='utf-8')
    additions = (
        'docs/validation/evidence/transaction-preflight-20261030-r1/** -text -whitespace',
        'docs/validation/recovery66_preflight_candidate.py text eol=lf',
        'docs/validation/validate_recovery66_candidate.py text eol=lf',
        'docs/validation/probe_music65_index_tree.py text eol=lf',
        'docs/validation/record_recovery66_followup.py text eol=lf')
    assert not any(value in attributes for value in additions)
    attributes_path.write_text(attributes.rstrip() + '\n' + '\n'.join(additions) + '\n', encoding='utf-8', newline='\n')

    raw = set()
    for folder in (BASE / 'candidate-r1', rejected, captured, index_probe):
        for path in folder.iterdir():
            assert path.is_file() and path.stat().st_size < 8 * 1024**2
            raw.add(path.relative_to(ROOT).as_posix())
    raw.add((proof / 'executed-runner.py').relative_to(ROOT).as_posix())
    authored = {'.gitattributes', 'README.md', 'README.zh-TW.md', 'README.en.md',
        round_path.relative_to(ROOT).as_posix(), *('docs/validation/' + name for name in (
            'capture_music65_native_stack.py', 'recovery66_preflight_candidate.py',
            'validate_recovery66_candidate.py', 'probe_music65_index_tree.py', 'record_recovery66_followup.py'))}
    scope = raw | authored
    assert not any(name.startswith('product/') or '/actual-stage1/' in name for name in scope)
    for name in authored:
        if name.endswith('.py'):
            compile((ROOT / name).read_bytes(), name, 'exec')
    frozen = {name: sha(ROOT / name) for name in scope}
    pathspec = ROOT / ('local/agent-ffmpeg/recovery66-followup-' + args.run + '.nul')
    pathspec.write_bytes(('\0'.join(sorted(scope)) + '\0').encode('utf-8'))
    print('Staging candidate evidence and trilingual docs; the product and live case remain unchanged.', flush=True)
    git('add', '--pathspec-from-file=' + str(pathspec), '--pathspec-file-nul')
    output = git('cat-file', '--batch', input=''.join(':' + name + '\n' for name in sorted(raw)).encode('utf-8'))
    offset, raw_pins = 0, {}
    for name in sorted(raw):
        end = output.index(b'\n', offset)
        oid, kind, length = output[offset:end].split()
        assert kind == b'blob'
        length = int(length)
        data = output[end + 1:end + 1 + length]
        assert data == (ROOT / name).read_bytes()
        raw_pins[name] = hashlib.sha256(data).hexdigest()
        offset = end + length + 2
    assert offset == len(output) and all(sha(ROOT / name) == pin for name, pin in frozen.items())
    audit = dict(status='passed', base_commit=parent, README_rows=572, previous_570_rows_retained=True,
        feature_rows=88, source_cli='0.1.65', candidate='v0.1.0-alpha.4-local.63', formal_cli='0.1.63',
        recovery_candidate_tests=15, recovery_product_integrated=False, actual65_generation_accepted=False,
        original_goal_document_unchanged=True, formal_activation=False, product_files_changed=False,
        files=frozen, raw_staged_Git_blobs_equal_captured_bytes=raw_pins,
        full_product_goal_closed=False, live_actual_case_excluded=True)
    (proof / 'verification.json').write_text(json.dumps(audit, indent=2) + '\n', encoding='utf-8', newline='\n')
    scope.add((proof / 'verification.json').relative_to(ROOT).as_posix())
    pathspec.write_bytes(('\0'.join(sorted(scope)) + '\0').encode('utf-8'))
    git('add', '--pathspec-from-file=' + str(pathspec), '--pathspec-file-nul')
    # Every new object is read back before computing the tree with missing-ok.
    parsed = {}
    for entry in git('ls-files', '--stage', '-z', '--', *sorted(scope)).split(b'\0')[:-1]:
        metadata, name = entry.split(b'\t', 1)
        mode, oid, stage = metadata.split()
        assert mode == b'100644' and stage == b'0'
        parsed[name.decode('utf-8')] = (mode, oid)
    assert set(parsed) == scope
    content = git('cat-file', '--batch', input=''.join(':' + name + '\n' for name in sorted(scope)).encode('utf-8'))
    offset = 0
    for name in sorted(scope):
        end = content.index(b'\n', offset)
        oid, kind, length = content[offset:end].split()
        assert kind == b'blob' and oid == parsed[name][1]
        length = int(length)
        data = content[end + 1:end + 1 + length]
        working = (ROOT / name).read_bytes()
        if data != working:
            assert name not in raw and git('hash-object', '--path', name, '--stdin', input=working).strip() == oid
        offset = end + length + 2
    assert offset == len(content)
    private = ROOT / ('local/agent-ffmpeg/recovery66-followup-commit-' + args.run)
    private.mkdir()
    alternate = private / 'index'
    real_index = ROOT / '.git/index'
    index_pin = sha(real_index)
    shutil.copyfile(prior / 'index', alternate)
    assert git('write-tree', '--missing-ok', alternate=alternate).decode().strip() == committed['tree']
    git('update-index', '-z', '--index-info', alternate=alternate, input=b''.join(
        mode + b' ' + oid + b' 0\t' + name.encode('utf-8') + b'\0'
        for name, (mode, oid) in sorted(parsed.items())))
    tree = git('write-tree', '--missing-ok', alternate=alternate).decode().strip()
    changed = {value.decode('utf-8') for value in git('diff-tree', '--no-commit-id', '--name-only',
        '-r', '-z', parent, tree).split(b'\0') if value}
    assert changed and changed <= scope and sha(real_index) == index_pin
    hooks = ROOT / '.git/hooks'
    hook_config = subprocess.run([str(GIT), 'config', '--get', 'core.hooksPath'], cwd=ROOT,
        capture_output=True, timeout=30, creationflags=subprocess.CREATE_NO_WINDOW)
    assert hook_config.returncode in (0, 1)
    if not hook_config.returncode:
        path = Path(hook_config.stdout.decode().strip())
        hooks = path if path.is_absolute() else ROOT / path
    assert not any((hooks / name).exists() for name in ('pre-commit', 'prepare-commit-msg', 'commit-msg'))
    hook = hooks / 'post-commit'
    assert hook.is_file() and sha(hook) == committed['post_commit_hook_sha256']
    message = private / 'message.txt'
    message.write_text('test: verify isolated metadata recovery preflight candidate\n', encoding='utf-8', newline='\n')
    commit = git('commit-tree', tree, '-p', parent, '-F', str(message)).decode().strip()
    assert git('rev-parse', 'HEAD').decode().strip() == parent
    git('update-ref', '-m', 'commit: isolated recovery preflight candidate', 'HEAD', commit, parent)
    pushed = subprocess.run([str(GIT_ROOT / 'usr/bin/sh.exe'), str(hook)], cwd=ROOT, env=env,
        capture_output=True, timeout=240, creationflags=subprocess.CREATE_NO_WINDOW)
    (private / 'post-commit.stdout').write_bytes(pushed.stdout)
    (private / 'post-commit.stderr').write_bytes(pushed.stderr)
    assert pushed.returncode == 0
    remote = git('ls-remote', 'origin', 'refs/heads/main', timeout=120).decode().split()[0]
    assert remote == commit and sha(real_index) == index_pin
    receipt = dict(status='committed-and-pushed', parent=parent, commit=commit, remote=remote, tree=tree,
        scope_files=len(scope), changed_files=len(changed), force=False, real_index_unchanged=True,
        original_post_commit_hook_executed=True, product_files_changed=False,
        source_cli='0.1.65', formal_cli='0.1.63', recovery_product_integrated=False,
        full_product_goal_closed=False)
    (private / 'verification.json').write_text(json.dumps(receipt, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps(receipt), flush=True)


if __name__ == '__main__':
    main()
