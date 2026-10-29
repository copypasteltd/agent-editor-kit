"""Document terminal actual results while keeping all previous evidence rows."""
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
    case = load(BASE / 'actual-piano4/verification.json')
    full = load(BASE / 'source64-contracts-r1/verification.json')
    refusal = load(BASE / 'activation-refusal-r2/verification.json')
    latency = load(BASE / 'transaction-latency-r1/verification.json')
    replay = load(BASE / 'package-r1/verification.json')
    assert case['status'] == 'passed' and case['complete_PCM_roundtrip_verified'] and case['source_frozen_equal']
    assert full['status'] == 'failed' and full['tests'] == 431 and full['failures'] == 1
    assert full['errors'] == full['skipped'] == 0 and full['frozen_equal']
    assert refusal['status'] == 'passed' and refusal['apply_requested'] and refusal['formal_entry_unchanged']
    assert latency['status'] == 'passed' and latency['metadata_restored_exactly'] and not latency['fsync_disabled']
    assert replay['status'] == 'passed' and replay['complete_master_WAV_equal']
    assert replay['complete_generation_recipe_equal'] and replay['complete_rendered_RGBA_PCM_equal']
    assert all(sha(ROOT / name) == pin for name,pin in case['source_hashes'].items())
    worker = case['actual_generation']['worker']
    model = worker['model']
    assert model['forwards'] == dict(text=2, language_model=50, diffusion=8, vae=1)
    assert worker['samples'] == 480000 and worker['channels'] == 2 and worker['sample_rate'] == 48000
    assert all(devices == ['cuda:0'] for devices in model['forward_output_devices'].values())
    calls = load(BASE / 'actual-piano4/calls.json')
    total = next(row['elapsed_seconds'] for row in calls if row['name'] == 'generate')
    timing = f'{total:.2f}s / {worker["elapsed_seconds"]:.2f}s / {model["elapsed_seconds"]:.2f}s'
    rows = {
        'README.md': [
            ('R547', 'CLI64完整兼容回归（失败）', '431执行：430通过、1失败，零错误／跳过，288应用与193测试源冻结一致；失败为20秒启动等待，不计整组通过。', 'source64-contracts-r1/verification.json'),
            ('R548', 'CLI64正式切换拒绝验证', '实际带--apply调用因失败的兼容前提被拒绝；93个正式Skill文件与2份配置摘要原样。不是64已注册。', 'activation-refusal-r2/verification.json'),
            ('R549', 'CLI64原生运行栈诊断', '同一音乐进程身份下保存导入、文本和权重载入采样；不请求局部变量。栈采样不等于模型生成验收。', 'process-diagnostic-r4/verification.json'),
            ('R550', 'CLI64真实CUDA神经配乐', f'RTX3060：10秒／48kHz双声道Float32／480000样本；前向2／50／8／1均CUDA0，全量PCM与入轨通过。完整命令／工作进程／模型函数耗时{timing}；模型函数不含此前导入。仅1个纯音乐样例，未听审。', 'actual-piano4/verification.json'),
            ('R551', 'CLI64小型事务时延测量', f'11文件／35637字节：准备{latency["prepare_seconds"]:.3f}s，恢复{latency["recover_seconds"]:.3f}s；12／11次真实fsync，精确恢复。未复现启动等待，不能据栈采样确认写盘是主因。', 'transaction-latency-r1/verification.json')],
        'README.zh-TW.md': [
            ('R547', 'CLI64完整相容回歸（失敗）', '431執行：430通過、1失敗，零錯誤／跳過，288應用與193測試原始碼凍結一致；失敗為20秒啟動等待，不計整組通過。', 'source64-contracts-r1/verification.json'),
            ('R548', 'CLI64正式切換拒絕驗證', '實際帶--apply呼叫因失敗的相容前提被拒絕；93個正式Skill檔案與2份設定摘要原樣。不是64已註冊。', 'activation-refusal-r2/verification.json'),
            ('R549', 'CLI64原生執行堆疊診斷', '在同一音樂進程身分下保存匯入、文字和權重載入採樣；不請求區域變數。堆疊採樣不等於模型生成驗收。', 'process-diagnostic-r4/verification.json'),
            ('R550', 'CLI64真實CUDA神經配樂', f'RTX3060：10秒／48kHz雙聲道Float32／480000樣本；前向2／50／8／1均CUDA0，全量PCM與入軌通過。完整命令／工作進程／模型函式耗時{timing}；模型函式不含此前匯入。僅1個純音樂樣例，未聽審。', 'actual-piano4/verification.json'),
            ('R551', 'CLI64小型事務延遲測量', f'11檔案／35637位元組：準備{latency["prepare_seconds"]:.3f}s，恢復{latency["recover_seconds"]:.3f}s；12／11次真實fsync，精確恢復。未重現啟動等待，不能據堆疊採樣確認寫盤是主因。', 'transaction-latency-r1/verification.json')],
        'README.en.md': [
            ('R547', 'CLI64 full compatibility regression (FAILED)', '431 executed: 430 passed, one failed, no errors/skips; 288 application and 193 test modules remained frozen. Failure:20s startup wait. Full group not accepted.', 'source64-contracts-r1/verification.json'),
            ('R548', 'CLI64 formal activation refusal', 'An actual --apply invocation was rejected for the failed compatibility prerequisite. All93 registered Skill files and two configurations retain exact hashes. CLI64 was not registered.', 'activation-refusal-r2/verification.json'),
            ('R549', 'CLI64 native stack diagnostics', 'Import, text and weight-loading stack samples retain the same music worker identity; local variables not requested. Captured stacks do not establish generation acceptance.', 'process-diagnostic-r4/verification.json'),
            ('R550', 'CLI64 actual CUDA neural music', f'RTX3060:10s,48kHz stereo Float32,480000 samples;2/50/8/1 forwards onCUDA0, complete PCM and track insertion passed. Full command / worker / model-function time:{timing}; model function excludes earlier imports. One instrumental case; no listening review.', 'actual-piano4/verification.json'),
            ('R551', 'CLI64 small transaction latency measurement', f'11 files /35637 bytes: prepare{latency["prepare_seconds"]:.3f}s, restore{latency["recover_seconds"]:.3f}s;12/11 real fsync calls with exact recovery. Startup failure not reproduced; a sampled flush frame does not establish the cause.', 'transaction-latency-r1/verification.json')],
    }
    status = {
        'README.md':'**CLI0.1.64 开发中：真实GPU神经配乐首例通过。** 10秒纯音乐已完成四阶段CUDA、完整PCM核验和入轨；首次完整命令约66分钟。完整431兼容组仍有1项失败，安装版音乐与Skill实测尚待完成。正式入口仍为CLI0.1.63／local61／r58。',
        'README.zh-TW.md':'**CLI0.1.64 開發中：真實GPU神經配樂首例通過。** 10秒純音樂已完成四階段CUDA、完整PCM核驗和入軌；首次完整命令約66分鐘。完整431相容組仍有1項失敗，安裝版音樂與Skill實測尚待完成。正式入口仍為CLI0.1.63／local61／r58。',
        'README.en.md':'**CLI0.1.64 in development: the first actual GPU music case passed.** A10s instrumental completed four CUDA stages, complete PCM checks and track insertion. First complete command took about66minutes. Full431 compatibility still has one failure; installed music and Skill execution remain pending. Registered:CLI0.1.63 /local61 /r58.',
    }
    package_labels = {
        'README.md': ('CLI64神经配乐工程包闭环', '母带WAV与生成请求配方保持完整；原始及包回放成片全部69120000字节RGBA、3842048字节解码PCM分别相同。没有重新生成模型，AAC成片不等于无损母带；音频仅本地internal。'),
        'README.zh-TW.md': ('CLI64神經配樂工程套件閉環', '母帶WAV與生成請求配方保持完整；原始及套件回放成片全部69120000位元組RGBA、3842048位元組解碼PCM分別相同。沒有重新生成模型，AAC成片不等於無損母帶；音訊僅本地internal。'),
        'README.en.md': ('CLI64 neural music project package', 'Master WAV and generation recipe remain exact; all69120000 RGBA bytes and3842048 decoded PCM bytes match the replay. Zero new model forwards. AAC movie is not a lossless master; audio remains local/internal.'),
    }
    for filename,(label,detail) in package_labels.items():
        rows[filename].append(('R552', label, detail, 'package-r1/verification.json'))
    proof = BASE / ('round-finalization-' + args.run)
    proof.mkdir()
    (proof / 'executed-runner.py').write_bytes(Path(__file__).read_bytes())
    changed = {}
    for filename in rows:
        path = ROOT / filename
        text = path.read_text(encoding='utf-8')
        old = re.findall(r'^\| R\d+ \|.*$', text, re.M)
        assert len(old) == 546
        for identifier,label,detail,target in rows[filename]:
            assert (BASE / target).is_file() and not re.search(r'^\| ' + identifier + r' \|', text, re.M)
            anchor = 'R' + str(int(identifier[1:]) - 1)
            line = f'| {identifier} | {label} | {detail} [Proof](docs/validation/evidence/music-generation-20261030-r1/{target}) |'
            text, count = re.subn(r'(^\| ' + anchor + r' \|.*$)', lambda m:m[0] + '\n' + line, text, flags=re.M)
            assert count == 1
        text, count = re.subn(r'(<!-- aek-cli64-current -->\n).*?(\n<!-- /aek-cli64-current -->)',
            lambda m:m[1] + status[filename] + ' [Music](docs/product/NEURAL_MUSIC_GENERATION.md)' + m[2], text, flags=re.S)
        assert count == 1
        current = re.findall(r'^\| R\d+ \|.*$', text, re.M)
        assert len(current) == len(set(current)) == 552 and set(old) <= set(current)
        assert len(re.findall(r'^\| F\d+ \|', text, re.M)) == 87
        path.write_text(text, encoding='utf-8', newline='\n')
        changed[filename] = sha(path)
    document = ROOT / 'docs/validation/CLI64原生神经配乐_2026-10-30.md'
    text = document.read_text(encoding='utf-8').replace('R529—R546', 'R529—R552').replace('当前546行', '当前552行')
    text = text.replace('完整431组仍在执行。', '完整431组已执行：430通过、1失败；整组不计通过。')
    text = text.replace('四阶段实际 GPU 音乐生成尚在执行；不能由设备发现或接口导入推断通过。',
        '10秒纯音乐源码实测已通过；演唱、长曲、安装版和人类听审尚待验收。')
    text = text.replace('尚缺验收时切换工具返回pending且不修改正式配置。', '缺收据时返回pending、已有失败时返回rejected，均不修改正式配置。')
    text = text.replace('生成后的完整工程包回放，以及实际推理中途取消／超时仍待验收。',
        '源码64完整工程包回放已通过；新音乐推理中途取消、故障与超时的完整字节回滚仍待验收。')
    text = re.sub(r'^- piano4：.*$', '- piano4：真实生成通过，RTX3060完成文本2／语言模型50／扩散8／VAE1次CUDA0前向；480000个48kHz立体声样本、完整PCM及独立音轨均核验通过。正式Skill仍为63，未完成自然音质听审。[实际收据](evidence/music-generation-20261030-r1/actual-piano4/verification.json)。', text, flags=re.M)
    text += ('\n## 首次真实运行终态与边界\n\n'
        f'完整生成命令 {total:.2f} 秒，工作进程 {worker["elapsed_seconds"]:.2f} 秒，模型函数 {model["elapsed_seconds"]:.2f} 秒。'
        f'文本载入及编码 {model["timings"]["text_load_and_encode_seconds"]:.2f} 秒，扩散载入及生成 {model["timings"]["diffusion_load_and_generate_seconds"]:.2f} 秒，VAE载入及解码 {model["timings"]["vae_load_and_decode_seconds"]:.2f} 秒。'
        '模型函数计时不包括该函数内此前的运行库导入；这三个阶段包含载入，不能当成纯GPU计算时间。首次完整调用约66分钟，交互性能未达目标。\n\n'
        '[完整431组](evidence/music-generation-20261030-r1/source64-contracts-r1/verification.json)零错误／跳过、源码冻结一致，但有1项失败；'
        '[带--apply的真实切换拒绝](evidence/music-generation-20261030-r1/activation-refusal-r2/verification.json)确认正式93文件和两份配置摘要原样。\n\n'
        f'[独立小型事务测量](evidence/music-generation-20261030-r1/transaction-latency-r1/verification.json)包含11文件、35637字节，准备 {latency["prepare_seconds"]:.3f} 秒、恢复 {latency["recover_seconds"]:.3f} 秒，保留12／11次真实fsync并精确恢复。'
        '该测量未复现20秒等待失败；此前栈落在一次写盘上不足以认定写盘是主因。不据此削弱持久化保证，也不删除原失败。\n')
    text += ('\n[源码工程包回放](evidence/music-generation-20261030-r1/package-r1/verification.json)的母带WAV、生成请求配方均完整相同；'
        '原始与重放成片全部69120000字节RGBA和3842048字节解码Float32 PCM分别相同。'
        'AAC解码含编码时钟差异，不称其与480000样本无损母带相同；重放没有新增模型前向。音频与样片只保存在本机内部审阅目录。\n')
    document.write_text(text, encoding='utf-8', newline='\n')
    changed[document.relative_to(ROOT).as_posix()] = sha(document)
    manual = ROOT / 'docs/product/NEURAL_MUSIC_GENERATION.md'
    text = manual.read_text(encoding='utf-8')
    text += ('\n## 首个实测结果\n\n'
        '[源码64首个真实案例](../validation/evidence/music-generation-20261030-r1/actual-piano4/verification.json)已产生10秒、48kHz双声道Float32 WAV，480000样本；'
        '文本2、语言模型50、扩散8和VAE1次实际前向均在CUDA0，完整PCM回读和入轨通过。'
        f'首次完整生成命令 {total:.2f} 秒，工作进程 {worker["elapsed_seconds"]:.2f} 秒；模型函数 {model["elapsed_seconds"]:.2f} 秒不包含此前导入，也包含各阶段权重载入，不能当作纯计算时间。'
        '这仍是开发候选，正式入口63不含新命令；完整兼容组431中有1项启动等待失败。新音乐的安装版、Skill、人类听审和更广案例仍按各自收据验收。'
        '[源码工程包回放](../validation/evidence/music-generation-20261030-r1/package-r1/verification.json)已确认母带WAV与配方完整相同，成片全部RGBA与解码PCM重放相同；AAC成片不是无损母带。\n')
    manual.write_text(text, encoding='utf-8', newline='\n')
    changed[manual.relative_to(ROOT).as_posix()] = sha(manual)
    cases = ROOT / 'docs/product/CASES.md'
    text = cases.read_text(encoding='utf-8')
    assert '## C78' not in text
    text += ('\n\n<a id="c78-native-neural-music"></a>\n## C78：源码64原生CUDA神经配乐与工程包\n\n'
        '[完整请求与实际GPU收据](../validation/evidence/music-generation-20261030-r1/actual-piano4/verification.json) · '
        '[母带／配方／全部音画回放](../validation/evidence/music-generation-20261030-r1/package-r1/verification.json) · '
        '[接口与当前使用流程](NEURAL_MUSIC_GENERATION.md)。\n\n'
        '输入为原创室内爵士纯音乐提示，10秒、90BPM、D小调、种子20261030、8步。RTX3060原生运行ACE-Step1.5 Turbo，'
        '文本2／语言模型50／扩散8／VAE1次实际神经前向均在CUDA0。输出48kHz双声道Float32 WAV，480000样本，完整PCM与入轨通过。'
        '母带和请求配方在工程包中完整保留；300帧成片全部69120000字节RGBA和3842048字节AAC解码Float32 PCM与包回放分别相同，未重新执行模型。\n\n'
        f'本机首次完整生成命令 {total:.2f} 秒，交互性能未达目标；完整兼容431中仍有1项启动等待失败。'
        '音频、诊断波形PNG、样片MP4和ZIP的本机绝对路径见回放收据artifacts。诊断图属于实际测量波形，不是GUI截图、质量评分或人工试听。'
        '生成音频权利保持unverified／internal，未上传演示音频；AAC成片不冒称无损母带。正式入口仍63，安装版独立生成、Skill、自然质量与G25完整范围继续开放。\n')
    cases.write_text(text, encoding='utf-8', newline='\n')
    changed[cases.relative_to(ROOT).as_posix()] = sha(cases)
    report = dict(status='passed', README_rows=552, previous_546_rows_retained=True,
        files=changed, actual_music_case_sha256=sha(BASE / 'actual-piano4/verification.json'),
        full_431_status='failed', formal_cli='0.1.63', formal_activation=False,
        full_product_goal_closed=False, human_listening=False, natural_quality_accepted=False)
    (proof / 'verification.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8', newline='\n')
    print(json.dumps(report), flush=True)


if __name__ == '__main__':
    main()
