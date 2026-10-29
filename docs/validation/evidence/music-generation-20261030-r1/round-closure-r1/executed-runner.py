"""Record terminal staged-package replay without promoting the formal Skill."""
import argparse
import hashlib
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / 'docs/validation/evidence/music-generation-20261030-r1'


def load(path):
    return json.loads(path.read_bytes())


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run', required=True)
    args = parser.parse_args()
    assert args.run.isalnum()
    replay = load(BASE / 'installed-package-stage1/verification.json')
    single = load(BASE / 'source64-session-control-r4/verification.json')
    full = load(BASE / 'source64-contracts-r1/verification.json')
    earlier = load(BASE / 'round-finalization-r1/verification.json')
    assert earlier['status'] == replay['status'] == single['status'] == 'passed'
    assert all(sha(ROOT / path) == pin for path, pin in earlier['files'].items())
    assert replay['actual_PowerShell_entry'] and not replay['registered_C_drive_entry']
    assert replay['complete_master_WAV_equal'] and replay['complete_generation_recipe_equal']
    assert replay['complete_rendered_RGBA_PCM_equal'] and not replay['source_fallback']
    assert replay['new_model_forwards'] == 0 and not replay['independent_installed_generation_accepted']
    assert replay['staged_skill_files'] == 94 and replay['registered_skill_unchanged']
    assert single['tests'] == 1 and single['failures'] == single['errors'] == single['skipped'] == 0
    assert single['frozen_equal'] and not single['test_assertions_changed'] and not single['process_deadlines_changed']
    assert full['status'] == 'failed' and full['tests'] == 431 and full['failures'] == 1
    assert all(sha(ROOT / path) == pin for path, pin in single['file_hashes'].items())
    manifest = load(ROOT / 'agent-ffmpeg-local-install-manifest.json')
    assert manifest['cli_version'] == '0.1.63' and len(manifest['files']) == 93
    assert all(sha(ROOT / row['path']) == row['sha256'] for row in manifest['files'])

    texts = {
        'README.md': (
            '**CLI0.1.64 开发中：真实GPU神经配乐及工程包回放通过。** 10秒纯音乐完成四阶段CUDA、完整PCM和入轨；候选Skill的PowerShell入口也完成独立安装版工程包回放。首次生成约66分钟。完整431兼容组仍有1项失败，独立安装版新生成尚待验收。正式入口：CLI0.1.63／local61／r58。',
            'CLI64候选Skill实际工程包回放',
            '实际未注册PowerShell入口→独立安装64：母带、配方、完整RGBA／PCM相同，94候选文件与正式93文件原样，无源码回落；新模型前向0，不代表安装版独立生成或正式切换。',
            'CLI64原会话控制断言复测通过',
            '相同源码／测试字节与20秒启动、30秒控制时限，单项通过，状态／停止断言已执行；此前完整431组和单项失败原样保留，负载相关原因未定位。'),
        'README.zh-TW.md': (
            '**CLI0.1.64 開發中：真實GPU神經配樂及工程套件回放通過。** 10秒純音樂完成四階段CUDA、完整PCM和入軌；候選Skill的PowerShell入口也完成獨立安裝版工程套件回放。首次生成約66分鐘。完整431相容組仍有1項失敗，獨立安裝版新生成尚待驗收。正式入口：CLI0.1.63／local61／r58。',
            'CLI64候選Skill實際工程套件回放',
            '實際未註冊PowerShell入口→獨立安裝64：母帶、配方、完整RGBA／PCM相同，94候選檔案與正式93檔案原樣，無原始碼回落；新模型前向0，不代表安裝版獨立生成或正式切換。',
            'CLI64原會話控制斷言複測通過',
            '相同原始碼／測試位元組與20秒啟動、30秒控制時限，單項通過，狀態／停止斷言已執行；先前完整431組和單項失敗原樣保留，負載相關原因未定位。'),
        'README.en.md': (
            '**CLI0.1.64 in development: actual GPU music and project replay passed.** A 10s instrumental completed four CUDA stages, complete PCM checks and track insertion. The staged Skill PowerShell entry also replayed its project through the independent installation. First generation took about 66 minutes. Full compatibility still has one failure among 431 tests; independent installed generation is pending. Registered: CLI0.1.63 / local61 / r58.',
            'CLI64 staged Skill actual project replay',
            'Actual unregistered PowerShell entry to independent CLI64 installation: exact master, recipe and complete RGBA/PCM, all 94 staged and 93 formal files unchanged, no source fallback. Zero new model forwards; neither independent installed generation nor formal activation accepted.',
            'CLI64 unchanged session-control test passed on rerun',
            'Identical application/test bytes and original 20s startup / 30s control deadlines. Status/stop assertions ran and passed. Previous full431 and single-test failures remain; load-related cause unresolved.'),
    }
    proof = BASE / ('round-closure-' + args.run)
    proof.mkdir()
    (proof / 'executed-runner.py').write_bytes(Path(__file__).read_bytes())
    documents = list(texts) + [
        'docs/validation/CLI64原生神经配乐_2026-10-30.md',
        'docs/product/NEURAL_MUSIC_GENERATION.md', 'docs/product/CASES.md']
    previous = {name: sha(ROOT / name) for name in documents}
    for name, (status, label1, detail1, label2, detail2) in texts.items():
        path = ROOT / name
        text = path.read_text(encoding='utf-8')
        old_rows = re.findall(r'^\| R\d+ \|.*$', text, re.M)
        assert len(old_rows) == 552
        new = []
        for number, label, detail, target in [
            (553, label1, detail1, 'installed-package-stage1'),
            (554, label2, detail2, 'source64-session-control-r4')]:
            new.append(f'| R{number} | {label} | {detail} [Proof](docs/validation/evidence/music-generation-20261030-r1/{target}/verification.json) |')
        text, count = re.subn(r'(^\| R552 \|.*$)', lambda m: m[0] + '\n' + '\n'.join(new), text, flags=re.M)
        assert count == 1
        text, count = re.subn(r'(<!-- aek-cli64-current -->\n).*?(\n<!-- /aek-cli64-current -->)',
            lambda m: m[1] + status + ' [Music](docs/product/NEURAL_MUSIC_GENERATION.md)' + m[2], text, flags=re.S)
        assert count == 1
        rows = re.findall(r'^\| R\d+ \|.*$', text, re.M)
        assert len(rows) == len(set(rows)) == 554 and set(old_rows) <= set(rows)
        assert len(re.findall(r'^\| F\d+ \|', text, re.M)) == 87
        path.write_text(text, encoding='utf-8', newline='\n')

    document = ROOT / documents[3]
    text = document.read_text(encoding='utf-8').replace('R529—R552', 'R529—R554').replace('当前552行', '当前554行')
    text = text.replace(
        '| P01 | 首个真实神经配乐与工程闭环。 | 完成四阶段 CUDA 观察、完整样本与 PCM 检查、入轨、可编辑工程包和全成片音画回放。 | G25 |',
        '| P01 | 独立安装版真实新生成尚缺；源码首例与两种工程回放已通过。 | 用候选PowerShell入口新建工程、重新执行四阶段CUDA生成、保存完整PCM／配方与工程包证据；不拿既有音频回放代替新生成。 | G25／G34 |')
    text = text.replace('10秒纯音乐源码实测已通过；演唱、长曲、安装版和人类听审尚待验收。',
        '10秒纯音乐源码实测与候选PowerShell安装版工程回放已通过；安装版新生成、演唱、长曲和人类听审尚待验收。')
    text += ('\n## 候选Skill独立安装版回放与单项复测\n\n'
        '[未注册候选PowerShell入口回放](evidence/music-generation-20261030-r1/installed-package-stage1/verification.json)'
        '通过：实际version／convert import／render命令均退出0，全部288安装模块与94个候选Skill文件保持不变，无源码回落。'
        '母带WAV、请求配方、全部69120000字节RGBA和3842048字节PCM均与源码案例相同。'
        '这是已有资产的独立安装版回放，新增模型前向为0；不是安装版独立生成，也没有改动C盘注册入口。\n\n'
        '[原会话控制测试r4](evidence/music-generation-20261030-r1/source64-session-control-r4/verification.json)'
        '在相同288应用／193测试模块、原20秒启动和30秒控制时限下通过，状态和停止断言均已执行。'
        '原完整431组与r1／r3单项失败收据保留；r2属于诊断脚本缺少导入的错误，亦保留。'
        '本次单项通过不能替换完整431失败，也不能确定负载相关原因已修复。\n')
    document.write_text(text, encoding='utf-8', newline='\n')

    manual = ROOT / documents[4]
    text = manual.read_text(encoding='utf-8')
    old_intro = '首个生成任务在1800秒工作进程预算内未取得模型结果并超时；[失败记录](../validation/evidence/music-generation-20261030-r1/actual-piano3/verification.json)保留，不能当作GPU音乐生成通过。'
    new_intro = ('[源码首个真实GPU生成](../validation/evidence/music-generation-20261030-r1/actual-piano4/verification.json)'
        '和[候选PowerShell入口的安装版工程包回放](../validation/evidence/music-generation-20261030-r1/installed-package-stage1/verification.json)已通过。'
        '此前1800秒预算超时的[失败记录](../validation/evidence/music-generation-20261030-r1/actual-piano3/verification.json)保留。'
        '独立安装版的新生成和完整回归尚待验收。')
    assert old_intro in text
    text = text.replace(old_intro, new_intro)
    text += ('\n## 使用已生成的本地工程包\n\n'
        '本机已实际执行下面的候选入口流程，完整命令及退出码见'
        '[回放记录](../validation/evidence/music-generation-20261030-r1/installed-package-stage1/calls.json)。'
        '将`$musicReplayProject`设为E盘尚不存在的目录，将`$musicProjectZip`设为调用方拥有的工程包。'
        '本轮内部音频未提交到公开仓库；公开克隆本身不包含这个ZIP。\n\n'
        '```powershell\n'
        "$avk = 'E:/dev/sandbox/AI广告剪辑/local/agent-ffmpeg/music64-skill-stage-r1/skills/agent-ffmpeg-local-editor/scripts/run.ps1'\n"
        "$musicProjectZip = 'E:/dev/sandbox/AI广告剪辑/local/agent-ffmpeg/music-generation64-package-r1/editable-neural-music.zip'\n"
        "$musicReplayProject = 'E:/dev/sandbox/AI广告剪辑/local/agent-ffmpeg/my-music-replay'\n"
        '& $avk version\n'
        '& $avk convert import --input $musicProjectZip --output $musicReplayProject\n'
        '& $avk render --project $musicReplayProject --output "$musicReplayProject/renders/replay.mp4"\n'
        '```\n\n'
        '这条流程只使用工程包内既有音频和配方，模型前向为0。重新生成须重新登记外部模型／核心／Python并调用`music generate`。'
        '本轮安装回放通过不能代替独立安装版新生成、正式Skill切换、人类完整听审或具体输出权利结论。\n')
    manual.write_text(text, encoding='utf-8', newline='\n')
    cases = ROOT / documents[5]
    text = cases.read_text(encoding='utf-8')
    text += ('\nC78后续独立安装验证：'
        '[候选Skill实际PowerShell入口](../validation/evidence/music-generation-20261030-r1/installed-package-stage1/verification.json)'
        '已导入同一工程包并重新渲染，全量母带／配方／RGBA／PCM一致；288安装模块及94候选文件原样。'
        '新增模型前向0，正式入口仍63；不视作安装版独立生成或新的自然质量案例。\n')
    cases.write_text(text, encoding='utf-8', newline='\n')
    report = dict(status='passed', README_rows=554, previous_552_rows_retained=True,
        previous_document_sha256=previous, files={name: sha(ROOT / name) for name in documents},
        installed_package_replay_sha256=sha(BASE / 'installed-package-stage1/verification.json'),
        unchanged_single_test_sha256=sha(BASE / 'source64-session-control-r4/verification.json'),
        full_431_status='failed', formal_cli='0.1.63', formal_activation=False,
        independent_installed_generation_accepted=False, full_product_goal_closed=False)
    (proof / 'verification.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps(dict(status='passed', README_rows=554, documents=len(documents), formal_activation=False)), flush=True)


if __name__ == '__main__':
    main()
