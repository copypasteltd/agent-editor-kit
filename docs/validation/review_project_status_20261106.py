"""Record current evidence, update docs, and stage an exact documentation scope.

This is a static status review, not a new functional test or inference run.
"""
import argparse
import ast
import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'docs/validation/evidence/status-review-20261106-r1'
MUSIC = ROOT / 'docs/validation/evidence/music-loading-20261030-r1'
GIT = Path('C:/Users/carzy/.cache/codex-runtimes/codex-primary-runtime/dependencies/native/git/mingw64/bin/git.exe')
PARENT = '952dca24074579b3c00e3cb93b6d715bb7e1b718'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load(path):
    return json.loads(path.read_bytes())


def git(*arguments, input=None):
    command = [str(GIT), '--no-optional-locks', '-c', 'core.fsmonitor=false',
        '-c', 'gc.auto=0', '-c', 'maintenance.auto=0', *arguments]
    assert len(subprocess.list2cmdline(command)) < 30000
    result = subprocess.run(command, input=input, cwd=ROOT, capture_output=True,
        timeout=1200, creationflags=subprocess.CREATE_NO_WINDOW)
    if result.returncode:
        raise RuntimeError(result.stderr[-4000:].decode('utf-8', errors='replace'))
    return result.stdout


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run', required=True)
    args = parser.parse_args()
    assert args.run.isalnum() and sys.dont_write_bytecode
    assert git('rev-parse', 'HEAD').decode().strip() == PARENT
    assert git('symbolic-ref', '--short', 'HEAD').strip() == b'main'
    assert git('remote', 'get-url', '--push', 'origin').strip() == b'git@github.com:copypasteltd/agent-editor-kit.git'
    goal = 'docs/product/GOAL_GAPS_20261025.md'
    assert (ROOT / goal).read_bytes() == git('show', 'HEAD:' + goal)
    ids = re.findall(r'^\| (G\d{2}) \|', (ROOT / goal).read_text(encoding='utf-8'), re.M)
    assert ids == [f'G{index:02d}' for index in range(1, 39)]
    source = ROOT / 'product/src/ai_ad_editor'
    version_node = ast.parse((source / '__init__.py').read_bytes()).body[1]
    assert isinstance(version_node, ast.Assign) and ast.literal_eval(version_node.value) == '0.1.65'
    source_pins = {path.relative_to(ROOT).as_posix(): sha(path) for path in source.glob('*.py')}
    assert len(source_pins) == 288
    candidate = load(MUSIC / 'candidate-r1/verification.json')
    assert candidate['status'] == 'installed-and-byte-verified'
    assert candidate['cli_version'] == '0.1.65' and candidate['local_release'] == 'v0.1.0-alpha.4-local.63'
    installed = Path(candidate['installed'])
    assert all(sha(source / name) == sha(installed / 'site/ai_ad_editor' / name) == pin
               for name, pin in candidate['source_hashes'].items())
    formal = candidate['registered_files']
    assert len(formal) == 95 and all(sha(Path(name)) == pin for name, pin in formal.items())
    manifest = load(ROOT / 'agent-ffmpeg-local-install-manifest.json')
    assert manifest['cli_version'] == '0.1.63' and manifest['release'] == 'v0.1.0-alpha.4-local.61'
    assert len(manifest['files']) == 93 and manifest['skill_count'] == 1 and manifest['module_count'] == 17
    actual_folder = MUSIC / 'actual-stage1'
    actual = load(actual_folder / 'verification.json')
    assert actual['status'] == 'passed' and actual['cli_version'] == '0.1.65'
    assert actual['source_hashes'] == source_pins and actual['source_frozen_equal']
    assert actual['actual_PowerShell_entry'] and actual['installed'] and not actual['source_fallback']
    assert actual['complete_PCM_roundtrip_verified'] and actual['audio_track_applied']
    assert actual['registered_skill_unchanged'] and not actual['actual_C_drive_entry']
    assert not actual['human_listening'] and not actual['natural_quality_accepted']
    assert not actual['generated_audio_publication_approved']
    generation = actual['actual_generation']
    worker = generation['worker']
    model = worker['model']
    assert worker['samples'] == 480000 and worker['sample_rate'] == 48000 and worker['channels'] == 2
    assert model['neural_backend'] == 'cuda' and model['forwards'] == dict(text=2, language_model=50, diffusion=8, vae=1)
    assert all(value == ['cuda:0'] for value in model['forward_output_devices'].values())
    assert len(model['local_weight_reads']) == 4 and all(row['backend'] == 'pread' for row in model['local_weight_reads'])
    assert model['dynamic_vram'] is False and model['elapsed_includes_runtime_import'] is True
    assert generation['cleanup']['worker_exited'] and generation['cleanup']['owner_job_closed']
    wav = Path(actual['artifacts']['wav'])
    assert 'sha256:' + sha(wav) == actual['asset']['sha256']
    assert wav.stat().st_size == 3840092
    assert actual['rights']['verification_status'] == 'unverified' and actual['rights']['permitted_uses'] == ['internal']
    calls = load(actual_folder / 'calls.json')
    assert [row['name'] for row in calls] == ['version', 'init', 'register', 'inspect', 'dry-run', 'generate']
    assert all(row['exit_code'] == 0 for row in calls)
    session = load(MUSIC / 'source65-session-r1/verification.json')
    assert session['status'] == 'failed' and session['tests'] == 12 and session['failures'] == 1
    recovery_path = ROOT / 'docs/validation/evidence/transaction-preflight-20261030-r1/candidate-r1/verification.json'
    recovery = load(recovery_path)
    assert recovery['status'] == 'passed' and recovery['tests'] == 15 and not recovery['product_integrated']
    code = (source / 'project.py').read_text(encoding='utf-8')
    assert '_preflight_transaction_recovery' not in code
    assert '_atomic_write_bytes(destination, backup.read_bytes())' in code
    missing = [name for name in ('source65-contracts-r1', 'installed65-contracts-r1')
               if not (MUSIC / name / 'verification.json').is_file()]
    assert len(missing) == 2
    assert not any(path.is_dir() and 'package' in path.name for path in MUSIC.iterdir())
    document = ROOT / 'docs/product/UNFINISHED_20261106.md'
    text = document.read_text(encoding='utf-8')
    coverage = re.findall(r'^\| (G\d{2}) ', text, re.M)
    assert coverage == ids
    proof = BASE / ('review-' + args.run)
    proof.mkdir(parents=True)
    (proof / 'executed-runner.py').write_bytes(Path(__file__).read_bytes())
    descriptions = (
        ('CLI65历史配乐终态补录（2026-10-30执行，11-06核查）',
         'CLI65歷史配樂終態補錄（2026-10-30執行，11-06核查）',
         'CLI65 historical music completion (run 2026-10-30; reviewed 11-06)'),
        ('完整未完成范围静态复核（2026-11-06）',
         '完整未完成範圍靜態複核（2026-11-06）',
         'Static review of the remaining scope (2026-11-06)'))
    details = (
        ('候选Skill实际调用安装65的10秒CUDA音乐已成功；四组件pread、完整PCM、入轨和退出通过。核对原WAV／288源码摘要；本次未新生成或试听，65包重放／正式注册未完成。',
         '候選Skill實際呼叫安裝65的10秒CUDA音樂已成功；四組件pread、完整PCM、入軌和退出通過。核對原WAV／288原始碼摘要；本次未新生成或試聽，65包重放／正式註冊未完成。',
         'Installed65, invoked through its staged Skill, completed 10s CUDA music: four pread components, complete PCM, track placement and cleanup passed. Existing WAV/288 source hashes checked; no new generation/listening. CLI65 package replay and formal registration remain open.'),
        ('对照G01—G38、当前源码／安装清单和历史收据展开剩余实现、质量及交付条件；恢复15项仅隔离候选，原12组1失败保留。本项不是新功能测试，也未启动自动开发。',
         '對照G01—G38、目前原始碼／安裝清單和歷史收據展開剩餘實作、品質及交付條件；恢復15項僅隔離候選，原12組1失敗保留。本項不是新功能測試，也未啟動自動開發。',
         'Reconciles G01–G38 with current source/install records and historical receipts, separating implementation, quality and delivery gaps. The 15-check repair is unintegrated; the original session-group failure remains. No new functional testing or automatic development.'))
    targets = ('docs/validation/evidence/music-loading-20261030-r1/actual-stage1/verification.json',
               'docs/product/UNFINISHED_20261106.md')
    old_rows_by_file = {}
    for language, filename in enumerate(('README.md', 'README.zh-TW.md', 'README.en.md')):
        path = ROOT / filename
        text = path.read_text(encoding='utf-8')
        old = git('show', 'HEAD:' + filename).decode('utf-8')
        rows = re.findall(r'^\| R\d+ \|.*$', text, re.M)
        assert len(rows) == 572 and rows == re.findall(r'^\| R\d+ \|.*$', old, re.M)
        features = re.findall(r'^\| F\d+ \|.*$', text, re.M)
        assert len(features) == 88
        old_rows_by_file[filename] = len(rows)
        additions = [f'| R{573+i} | {descriptions[i][language]} | {details[i][language]} [Record]({targets[i]}) |'
                     for i in range(2)]
        text, count = re.subn(r'(^\| R572 \|.*$)', lambda match: match[0] + '\n' + '\n'.join(additions), text, flags=re.M)
        assert count == 1
        current = (
            '**2026-11-06状态核对：源码CLI0.1.65／验证候选local63；正式入口仍CLI0.1.63／local61／r58。** 候选Skill调用安装65的真实10秒CUDA音乐已成功，完整PCM／入轨／退出通过；65工程包重放、完整443、听审和正式切换未验收。恢复修复15项仅隔离候选，原会话12项仍有1失败。 [未完成内容详解](docs/product/UNFINISHED_20261106.md)',
            '**2026-11-06狀態核對：原始碼CLI0.1.65／驗證候選local63；正式入口仍CLI0.1.63／local61／r58。** 候選Skill呼叫安裝65的真實10秒CUDA音樂已成功，完整PCM／入軌／退出通過；65工程包重放、完整443、聽審和正式切換未驗收。恢復修復15項僅隔離候選，原會話12項仍有1失敗。 [未完成內容詳解](docs/product/UNFINISHED_20261106.md)',
            '**Status reviewed 2026-11-06: source CLI0.1.65 / validation candidate local63; registered CLI0.1.63/local61/r58.** Actual 10s CUDA music through the staged Skill and installed65 passed complete PCM, placement and cleanup. CLI65 package replay, full443, listening and formal activation remain open. The 15-check recovery repair is unintegrated; the original 12-check session group retains one failure. [Remaining scope](docs/product/UNFINISHED_20261106.md)')
        text, count = re.subn(r'<!-- aek-cli65-current -->.*?<!-- /aek-cli65-current -->',
            '<!-- aek-cli65-current -->\n' + current[language] + '\n<!-- /aek-cli65-current -->', text, flags=re.S)
        assert count == 1
        after = re.findall(r'^\| R\d+ \|.*$', text, re.M)
        assert len(after) == 574 and set(rows) <= set(after)
        assert re.findall(r'^\| F\d+ \|.*$', text, re.M) == features
        path.write_text(text, encoding='utf-8', newline='\n')
    manuals = ('docs/product/NEURAL_MUSIC_GENERATION.md', 'docs/product/NEURAL_MUSIC_LOADING.md')
    for name in manuals:
        path = ROOT / name
        text = path.read_text(encoding='utf-8')
        title, tail = text.split('\n', 1)
        notice = ('\n> 2026-11-06状态补录：未注册候选Skill实际调用安装版65的10秒CUDA生成已经成功，'
            '完整PCM／入轨／退出核验通过；本次仅复核历史收据和现有音频摘要，未重新生成或听审。'
            '正式入口仍63，65工程包重放和完整兼容未验收。'
            '[当前全部未完成内容](UNFINISHED_20261106.md) · '
            '[实际65终态](../validation/evidence/music-loading-20261030-r1/actual-stage1/verification.json)。'
            '下方64/65启动阶段说明保留为历史，按具体版本阅读。\n')
        path.write_text(title + '\n' + notice + tail, encoding='utf-8', newline='\n')
    round_path = ROOT / 'docs/validation/CLI65配乐读取与计时_2026-10-30.md'
    with round_path.open('a', encoding='utf-8', newline='\n') as stream:
        stream.write('\n## 2026-11-06静态复核补录\n\n'
            '该轮最后仍运行的stage1后来已经成功，终态见[实际安装65生成收据]'
            '(evidence/music-loading-20261030-r1/actual-stage1/verification.json)。'
            '10秒、48kHz双声道Float32、480000样本，四组件pread与CUDA前向、完整PCM、入轨和清理通过。'
            '本次重新核对现有音频摘要与288应用源码，无新推理或听审。完整命令2355.01秒，'
            '6条CLI调用合计3460.53秒；不同层计时不能重复相加。'
            '65工程包／故障闭环、正式注册、完整443、自然听审和权利仍未验收，'
            '恢复候选仍未合入，原失败保留。完整剩余范围见'
            '[当前38组详解](../product/UNFINISHED_20261106.md)。\n')
    attributes_path = ROOT / '.gitattributes'
    attributes = attributes_path.read_text(encoding='utf-8')
    additions = ('docs/validation/evidence/status-review-20261106-r1/** -text -whitespace',
        'docs/validation/review_project_status_20261106.py text eol=lf',
        'docs/validation/commit_project_status_20261106.py text eol=lf')
    assert not any(value in attributes for value in additions)
    attributes_path.write_text(attributes.rstrip() + '\n' + '\n'.join(additions) + '\n', encoding='utf-8', newline='\n')
    raw = {(proof / 'executed-runner.py').relative_to(ROOT).as_posix()}
    for path in actual_folder.iterdir():
        assert path.is_file() and path.stat().st_size < 8 * 1024**2
        raw.add(path.relative_to(ROOT).as_posix())
    authored = {'.gitattributes', 'README.md', 'README.zh-TW.md', 'README.en.md',
        document.relative_to(ROOT).as_posix(), round_path.relative_to(ROOT).as_posix(), *manuals,
        'docs/validation/review_project_status_20261106.py',
        'docs/validation/commit_project_status_20261106.py'}
    for name in authored:
        if name.endswith('.py'):
            compile((ROOT / name).read_bytes(), name, 'exec')
    scope = raw | authored
    assert not any(name.startswith(('product/', 'skills/', 'local/')) for name in scope)
    banned = {'.wav', '.mp4', '.mp3', '.zip', '.png', '.exe', '.safetensors', '.f32', '.pcm', '.rgba'}
    assert all(Path(name).suffix.lower() not in banned for name in scope)
    frozen = {name: sha(ROOT / name) for name in scope}
    audit = dict(status='passed', review_date='2026-11-06', timezone='Asia/Taipei', base_commit=PARENT,
        kind='static-evidence-review-not-functional-acceptance', original_goal_groups=ids,
        original_goal_document_unchanged=True, original_goal_sha256=sha(ROOT / goal),
        source_cli='0.1.65', candidate='v0.1.0-alpha.4-local.63', formal_cli='0.1.63',
        formal_release='v0.1.0-alpha.4-local.61', formal_skill_archive='r58',
        application_modules=288, formal_skill_count=1, formal_modules=17, formal_skill_files=93,
        source_and_candidate_bytes_equal=True, formal_95_files_unchanged=True,
        source_hashes=source_pins, formal_guard_sha256={name: pin for name, pin in formal.items()},
        historical_actual65=dict(status=actual['status'], receipt_sha256=sha(actual_folder / 'verification.json'),
            complete_PCM_roundtrip_verified=True, samples=worker['samples'], sample_rate=worker['sample_rate'],
            channels=worker['channels'], neural_forwards=model['forwards'], pread_reads=model['local_weight_reads'],
            actual_PowerShell_entry=True, audio_track_applied=True, cleanup=generation['cleanup'],
            WAV_bytes=wav.stat().st_size, WAV_sha256=sha(wav), WAV_path=str(wav),
            model_including_import_seconds=model['elapsed_seconds'], worker_seconds=worker['elapsed_seconds'],
            pipeline_seconds=generation['elapsed_seconds'], generation_command_seconds=calls[-1]['elapsed_seconds'],
            all_six_CLI_calls_seconds=sum(row['elapsed_seconds'] for row in calls),
            human_listening=False, rights_unverified_internal=True),
        recovery_candidate_tests=15, recovery_product_integrated=False,
        session_group_tests=12, session_group_failures=1, full443_terminal_missing=missing,
        CLI65_package_replay_evidence_present=False, README_rows=574, previous_README_rows_retained=old_rows_by_file,
        feature_rows=88, new_functional_tests_executed=False, new_inference_executed=False,
        automatic_goal_created_or_resumed=False, product_files_changed=False, formal_activation=False,
        media_published=False, full_product_goal_closed=False, files=frozen)
    audit_path = proof / 'verification.json'
    audit_path.write_text(json.dumps(audit, ensure_ascii=False, indent=2) + '\n', encoding='utf-8', newline='\n')
    scope.add(audit_path.relative_to(ROOT).as_posix())
    raw.add(audit_path.relative_to(ROOT).as_posix())
    pathspec = ROOT / ('local/agent-ffmpeg/status-review-20261106-' + args.run + '.nul')
    pathspec.write_bytes(('\0'.join(sorted(scope)) + '\0').encode('utf-8'))
    print('Staging the bounded status report and completed historical receipts; no product changes.', flush=True)
    git('add', '--pathspec-from-file=' + str(pathspec), '--pathspec-file-nul')
    ordered = sorted(raw)
    output = git('cat-file', '--batch', input=''.join(':' + name + '\n' for name in ordered).encode('utf-8'))
    offset = 0
    for name in ordered:
        end = output.index(b'\n', offset)
        oid, kind, length = output[offset:end].split()
        assert kind == b'blob'
        length = int(length)
        assert output[end + 1:end + 1 + length] == (ROOT / name).read_bytes(), name
        offset = end + length + 2
    assert offset == len(output)
    assert all(sha(ROOT / name) == pin for name, pin in frozen.items())
    assert all(sha(ROOT / name) == pin for name, pin in source_pins.items())
    assert all(sha(Path(name)) == pin for name, pin in formal.items())
    print(json.dumps(dict(status='passed', scope_files=len(scope), README_rows=574, goal_groups=38,
        new_functional_tests_executed=False, new_inference_executed=False, formal_activation=False)), flush=True)


if __name__ == '__main__':
    main()
